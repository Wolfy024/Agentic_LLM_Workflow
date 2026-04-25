"""
File searching and metadata inspection tools.

Provides functions to find files by glob or regex, extract structural summaries 
for large files, get file info, and estimate token counts.
"""

from __future__ import annotations
import os
import fnmatch
import pathlib
import re
import ast
import math
import asyncio
import json
from hashlib import sha1
from dataclasses import dataclass
from tools.registry import tool, _resolve, MAX_READ_SIZE
from core.config import get_root_dir

MAX_LINES = 300
MAX_CHUNKS = 5
_MAX_EMBED_CHARS = 4000

_MEMORY_DIR = ".orchestrator_memory"
_MEMORY_FILE = "search_memory.json"
_VECTOR_INDEX_FILE = "vector_index.json"
_memory_loaded = False

# Persisted retrieval memory to avoid redundant scans across restarts.
memory = {"visited_files": set(), "important_symbols": set(), "summaries": {}}

_vector_index: dict[str, dict] = {}
_embedding_model = None
_tree_sitter_cache: dict[str, object] = {}


@dataclass
class SearchChunk:
    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float = 0.0


def _memory_base_dir() -> pathlib.Path:
    """Memory lives next to the orchestrator exe/config.json, NOT inside the user workspace."""
    return get_root_dir() / _MEMORY_DIR


def _memory_file_path() -> pathlib.Path:
    return _memory_base_dir() / _MEMORY_FILE


def _vector_index_path() -> pathlib.Path:
    return _memory_base_dir() / _VECTOR_INDEX_FILE


def _ensure_memory_loaded() -> None:
    global _memory_loaded
    if _memory_loaded:
        return
    _memory_loaded = True
    try:
        path = _memory_file_path()
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        memory["visited_files"] = set(payload.get("visited_files", []))
        memory["important_symbols"] = set(payload.get("important_symbols", []))
        memory["summaries"] = payload.get("summaries", {})
    except Exception:
        # Keep runtime robust even if persisted cache is malformed.
        memory["visited_files"] = set()
        memory["important_symbols"] = set()
        memory["summaries"] = {}


def _persist_memory() -> None:
    try:
        base = _memory_base_dir()
        base.mkdir(parents=True, exist_ok=True)
        payload = {
            "visited_files": sorted(memory["visited_files"]),
            "important_symbols": sorted(memory["important_symbols"]),
            "summaries": memory["summaries"],
        }
        _memory_file_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_vector_index() -> None:
    global _vector_index
    if _vector_index:
        return
    try:
        path = _vector_index_path()
        if path.exists():
            _vector_index = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _vector_index = {}


def _persist_vector_index() -> None:
    try:
        base = _memory_base_dir()
        base.mkdir(parents=True, exist_ok=True)
        _vector_index_path().write_text(json.dumps(_vector_index), encoding="utf-8")
    except Exception:
        pass


def get_retrieval_memory_snapshot() -> dict:
    """Export retrieval memory/index for session persistence."""
    _ensure_memory_loaded()
    _load_vector_index()
    return {
        "visited_files": sorted(memory["visited_files"]),
        "important_symbols": sorted(memory["important_symbols"]),
        "summaries": memory["summaries"],
        "vector_index": _vector_index,
    }


def load_retrieval_memory_snapshot(snapshot: dict | None) -> None:
    """Restore retrieval memory/index from a previously saved session."""
    global _memory_loaded, _vector_index
    if not isinstance(snapshot, dict):
        return
    memory["visited_files"] = set(snapshot.get("visited_files", []))
    memory["important_symbols"] = set(snapshot.get("important_symbols", []))
    memory["summaries"] = snapshot.get("summaries", {})
    _vector_index = snapshot.get("vector_index", {}) if isinstance(snapshot.get("vector_index"), dict) else {}
    _memory_loaded = True
    _persist_memory()
    _persist_vector_index()


def get_retrieval_memory_stats() -> dict:
    """Return compact retrieval-memory stats for CLI display."""
    _ensure_memory_loaded()
    _load_vector_index()
    return {
        "visited_files": len(memory["visited_files"]),
        "important_symbols": len(memory["important_symbols"]),
        "summaries": len(memory["summaries"]),
        "vector_docs": len(_vector_index),
        "memory_file": str(_memory_file_path()),
        "vector_index_file": str(_vector_index_path()),
    }


def track_file(rel_path: str, resolved_path: str, text: str, line_count: int) -> None:
    """Register a file in retrieval memory — called by read/write/edit/search tools.

    Extracts symbols, imports, docstrings and indexes for vector search so the
    agent builds a persistent codebase map across all operations.
    """
    try:
        _ensure_memory_loaded()
        _load_vector_index()

        memory["visited_files"].add(rel_path)

        fpath = pathlib.Path(resolved_path)
        file_meta = _extract_file_metadata(fpath, text)
        syms = set(file_meta.get("symbols", []))
        if syms:
            memory["important_symbols"].update(syms)
        memory["summaries"][rel_path] = {
            "symbols": file_meta.get("symbols", []),
            "symbol_ranges": file_meta.get("symbol_ranges", []),
            "imports": file_meta.get("imports", []),
            "docstrings": file_meta.get("docstrings", []),
            "lines": line_count,
        }

        _index_file_for_vectors(rel_path, text)
        _persist_memory()
        _persist_vector_index()
    except Exception:
        pass  # Never break a tool call for memory tracking


def truncate(text: str, limit: int = 1200) -> str:
    """Trim oversized chunk text while preserving readability."""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated]"


def build_context(chunks: list[SearchChunk]) -> str:
    return "\n\n".join([
        f"{c.file_path}:{c.start_line}-{c.end_line}\n{truncate(c.content)}"
        for c in chunks
    ])


def _relevant_file_summaries(chunks: list[SearchChunk]) -> list[dict]:
    """Build hierarchical summaries for files that appear in search results."""
    seen: set[str] = set()
    summaries: list[dict] = []
    for c in chunks:
        fp = c.file_path
        if fp in seen:
            continue
        seen.add(fp)
        stored = memory.get("summaries", {}).get(fp)
        if stored:
            summaries.append({
                "file": fp,
                "lines": stored.get("lines", 0),
                "symbols": stored.get("symbols", [])[:20],
                "symbol_ranges": stored.get("symbol_ranges", [])[:20],
                "imports": stored.get("imports", [])[:10],
                "docstrings": stored.get("docstrings", [])[:5],
            })
        else:
            summaries.append({"file": fp, "lines": 0, "symbols": [], "symbol_ranges": [], "imports": [], "docstrings": []})
    return summaries


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9_]+", text.lower()) if t]


def _candidate_files(path: str, file_pattern: str | None = None) -> list[pathlib.Path]:
    root = pathlib.Path(_resolve(path))
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}
    files: list[pathlib.Path] = []
    for fpath in root.rglob("*"):
        if any(part in skip_dirs for part in fpath.parts):
            continue
        if not fpath.is_file():
            continue
        if file_pattern and not fnmatch.fnmatch(fpath.name, file_pattern):
            continue
        try:
            if fpath.stat().st_size > MAX_READ_SIZE:
                continue
        except OSError:
            continue
        files.append(fpath)
    return files


def _safe_read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return ""


def _language_for_suffix(suffix: str) -> str | None:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".hpp": "cpp",
    }.get(suffix.lower())


def _tree_sitter_parser_for_suffix(suffix: str):
    """Best-effort parser factory for non-Python symbol extraction."""
    lang_name = _language_for_suffix(suffix)
    if not lang_name or lang_name == "python":
        return None
    if lang_name in _tree_sitter_cache:
        return _tree_sitter_cache[lang_name]
    try:
        from tree_sitter import Parser  # type: ignore
        from tree_sitter_languages import get_language  # type: ignore
        parser = Parser()
        parser.set_language(get_language(lang_name))
        _tree_sitter_cache[lang_name] = parser
        return parser
    except Exception:
        _tree_sitter_cache[lang_name] = None
        return None


def _extract_symbols_with_tree_sitter(file_path: pathlib.Path, text: str) -> set[str]:
    parser = _tree_sitter_parser_for_suffix(file_path.suffix)
    if parser is None:
        return set()
    try:
        tree = parser.parse(text.encode("utf-8", errors="ignore"))
    except Exception:
        return set()

    src = text.encode("utf-8", errors="ignore")
    symbols: set[str] = set()
    symbol_node_types = {
        "function_definition",
        "function_declaration",
        "method_definition",
        "method_declaration",
        "class_definition",
        "class_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "struct_item",
        "impl_item",
        "enum_item",
    }

    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in symbol_node_types:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                try:
                    sym = src[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore").strip()
                    if sym:
                        symbols.add(sym)
                except Exception:
                    pass
        stack.extend(node.children)
    return symbols


def _extract_symbols_with_ast(file_path: pathlib.Path, text: str) -> set[str]:
    """Extract symbols using Python ast or tree-sitter, fallback to regex."""
    symbols: set[str] = set()
    if file_path.suffix == ".py":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.add(node.name)
            return symbols
        except SyntaxError:
            return symbols

    ts_symbols = _extract_symbols_with_tree_sitter(file_path, text)
    if ts_symbols:
        return ts_symbols

    for line in text.splitlines():
        m = re.match(r"\s*(class|def|async def|function)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
        if m:
            symbols.add(m.group(2))
    return symbols


def _extract_file_metadata(file_path: pathlib.Path, text: str) -> dict:
    """Extract rich metadata: symbols with line ranges, imports, and docstrings."""
    meta: dict = {"symbols": [], "symbol_ranges": [], "imports": [], "docstrings": []}
    if file_path.suffix != ".py":
        syms = _extract_symbols_with_ast(file_path, text)
        meta["symbols"] = sorted(syms)[:50]
        return meta
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return meta

    symbols: list[str] = []
    symbol_ranges: list[dict] = []
    imports: list[str] = []
    docstrings: list[str] = []

    for node in ast.iter_child_nodes(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(f"{mod}.{alias.name}")
        # Classes and functions — store line ranges
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)
            symbol_ranges.append({"name": node.name, "start": node.lineno, "end": node.end_lineno or node.lineno})
            ds = ast.get_docstring(node)
            if ds:
                docstrings.append(f"{node.name}: {ds[:120]}")
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)
            symbol_ranges.append({"name": node.name, "start": node.lineno, "end": node.end_lineno or node.lineno})
            ds = ast.get_docstring(node)
            if ds:
                docstrings.append(f"{node.name}: {ds[:120]}")
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(f"{node.name}.{child.name}")
                    symbol_ranges.append({"name": f"{node.name}.{child.name}", "start": child.lineno, "end": child.end_lineno or child.lineno})

    # Module-level docstring
    module_ds = ast.get_docstring(tree)
    if module_ds:
        docstrings.insert(0, f"__module__: {module_ds[:200]}")

    meta["symbols"] = symbols[:50]
    meta["symbol_ranges"] = symbol_ranges[:50]
    meta["imports"] = imports[:30]
    meta["docstrings"] = docstrings[:20]
    return meta


def _get_embedding_model():
    """Lazy-load sentence-transformers for semantic vector search."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        _embedding_model = False
    return _embedding_model


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _embed_text(text: str) -> list[float]:
    model = _get_embedding_model()
    if not model:
        # Deterministic fallback embedding via hashed 3-gram vector.
        dim = 256
        vec = [0.0] * dim
        t = text.lower()
        grams = [t[i:i + 3] for i in range(max(0, len(t) - 2))]
        if not grams:
            return vec
        for g in grams:
            idx = int(sha1(g.encode("utf-8", errors="ignore")).hexdigest(), 16) % dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    emb = model.encode(text[:_MAX_EMBED_CHARS], normalize_embeddings=True)
    return [float(x) for x in emb.tolist()]


def _index_file_for_vectors(rel_path: str, text: str) -> None:
    doc_hash = sha1(text.encode("utf-8", errors="ignore")).hexdigest()
    existing = _vector_index.get(rel_path)
    if existing and existing.get("hash") == doc_hash:
        return
    _vector_index[rel_path] = {
        "hash": doc_hash,
        "embedding": _embed_text(text[:_MAX_EMBED_CHARS]),
    }


def _bm25_score(query_terms: list[str], doc_terms: list[str], doc_freq: dict[str, int], n_docs: int, avgdl: float) -> float:
    if not doc_terms or not query_terms:
        return 0.0
    k1 = 1.5
    b = 0.75
    dl = len(doc_terms)
    tf: dict[str, int] = {}
    for t in doc_terms:
        tf[t] = tf.get(t, 0) + 1
    score = 0.0
    for term in query_terms:
        if term not in tf:
            continue
        df = max(1, doc_freq.get(term, 0))
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        freq = tf[term]
        denom = freq + k1 * (1 - b + b * (dl / max(avgdl, 1.0)))
        score += idf * ((freq * (k1 + 1)) / max(denom, 1e-9))
    return score


def _line_matches(query_terms: list[str], lines: list[str]) -> list[int]:
    hits: list[int] = []
    for i, ln in enumerate(lines):
        ll = ln.lower()
        if any(t in ll for t in query_terms):
            hits.append(i)
    return hits


def _chunk_around_hits(rel_path: str, lines: list[str], hit_idxs: list[int], max_lines: int = MAX_LINES) -> list[SearchChunk]:
    if not hit_idxs:
        return []
    chunks: list[SearchChunk] = []
    half = max(10, min(40, max_lines // 8))
    consumed = 0
    for idx in hit_idxs:
        start = max(0, idx - half)
        end = min(len(lines), idx + half + 1)
        span = end - start
        if consumed + span > max_lines:
            remain = max_lines - consumed
            if remain <= 0:
                break
            end = min(len(lines), start + remain)
            span = end - start
        content = "\n".join(lines[start:end])
        chunks.append(SearchChunk(rel_path, start + 1, end, content))
        consumed += span
        if consumed >= max_lines:
            break
    return chunks


async def _keyword_search(query: str, path: str, file_pattern: str | None = None) -> list[SearchChunk]:
    _ensure_memory_loaded()
    _load_vector_index()
    query_terms = _tokenize(query)
    files = await asyncio.to_thread(_candidate_files, path, file_pattern)
    docs: list[tuple[str, list[str], list[str], set[str]]] = []
    df: dict[str, int] = {}
    total_len = 0

    for fpath in files:
        text = await asyncio.to_thread(_safe_read, fpath)
        if not text:
            continue
        rel = str(fpath.relative_to(_resolve(path)))
        lines = text.splitlines()
        doc_terms = _tokenize(text)
        syms = _extract_symbols_with_ast(fpath, text)
        docs.append((rel, lines, doc_terms, syms))
        total_len += len(doc_terms)
        seen_terms = set(doc_terms)
        for t in seen_terms:
            df[t] = df.get(t, 0) + 1
        memory["visited_files"].add(rel)
        file_meta = await asyncio.to_thread(_extract_file_metadata, fpath, text)
        syms = set(file_meta["symbols"])
        if syms:
            memory["important_symbols"].update(syms)
        memory["summaries"][rel] = {
            "symbols": file_meta["symbols"],
            "symbol_ranges": file_meta.get("symbol_ranges", []),
            "imports": file_meta["imports"],
            "docstrings": file_meta["docstrings"],
            "lines": len(lines),
        }
        await asyncio.to_thread(_index_file_for_vectors, rel, text)

    if not docs:
        return []

    avgdl = total_len / max(len(docs), 1)
    ranked: list[SearchChunk] = []
    for rel, lines, doc_terms, _ in docs:
        score = _bm25_score(query_terms, doc_terms, df, len(docs), avgdl)
        if score <= 0:
            continue
        hits = _line_matches(query_terms, lines)
        chunks = _chunk_around_hits(rel, lines, hits, MAX_LINES)
        for c in chunks:
            c.score = score
            ranked.append(c)
    ranked.sort(key=lambda c: c.score, reverse=True)
    _persist_memory()
    _persist_vector_index()
    return ranked[:MAX_CHUNKS]


def _extract_symbol_ranges_from_ast(file_path: pathlib.Path, text: str) -> list[dict]:
    """Extract symbols with precise {name, start, end} line ranges."""
    if file_path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        ranges: list[dict] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                ranges.append({
                    "name": node.name,
                    "start": node.lineno,
                    "end": node.end_lineno or node.lineno,
                })
        return ranges
    # For non-Python files, use regex with line numbers (no end line)
    ranges = []
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"\s*(class|def|async def|function)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
        if m:
            ranges.append({"name": m.group(2), "start": i, "end": i})
    return ranges


async def _symbol_lookup(query: str, path: str, file_pattern: str | None = None) -> list[SearchChunk]:
    """Precision symbol retrieval: finds matching symbols and returns their actual code."""
    _ensure_memory_loaded()
    query_terms = set(_tokenize(query))
    if not query_terms:
        return []

    files = await asyncio.to_thread(_candidate_files, path, file_pattern)
    found: list[SearchChunk] = []
    for fpath in files:
        text = await asyncio.to_thread(_safe_read, fpath)
        if not text:
            continue
        rel = str(fpath.relative_to(_resolve(path)))
        sym_ranges = _extract_symbol_ranges_from_ast(fpath, text)
        if not sym_ranges:
            continue
        lines = text.splitlines()
        # Find symbols whose names match query terms
        for sr in sym_ranges:
            name_lower = sr["name"].lower()
            if any(q in name_lower for q in query_terms):
                start = sr["start"] - 1  # 0-indexed
                end = sr["end"]          # exclusive
                # Cap individual symbol extraction at 200 lines
                if end - start > 200:
                    end = start + 200
                content = "\n".join(lines[start:end])
                found.append(SearchChunk(
                    rel, sr["start"], sr["end"], content,
                    score=2.0 if sr["name"].lower() in query_terms else 1.0,
                ))
    found.sort(key=lambda c: c.score, reverse=True)
    _persist_memory()
    return found[:MAX_CHUNKS]


async def _vector_search(query: str, path: str, file_pattern: str | None = None) -> list[SearchChunk]:
    _ensure_memory_loaded()
    _load_vector_index()
    files = await asyncio.to_thread(_candidate_files, path, file_pattern)
    query_vec = await asyncio.to_thread(_embed_text, query)
    scored: list[tuple[float, str, list[str]]] = []

    for fpath in files:
        text = await asyncio.to_thread(_safe_read, fpath)
        if not text:
            continue
        rel = str(fpath.relative_to(_resolve(path)))
        await asyncio.to_thread(_index_file_for_vectors, rel, text)
        payload = _vector_index.get(rel, {})
        emb = payload.get("embedding", [])
        score = _cosine_similarity(query_vec, emb)
        if score <= 0:
            continue
        scored.append((score, rel, text.splitlines()))
        memory["visited_files"].add(rel)

    scored.sort(key=lambda x: x[0], reverse=True)
    top: list[SearchChunk] = []
    q_terms = _tokenize(query)
    for score, rel, lines in scored[:MAX_CHUNKS]:
        hits = _line_matches(q_terms, lines)
        if not hits:
            hits = [0]
        chunks = _chunk_around_hits(rel, lines, hits, MAX_LINES)
        if not chunks and lines:
            chunks = [SearchChunk(rel, 1, min(len(lines), min(60, MAX_LINES)), "\n".join(lines[:min(60, MAX_LINES)]))]
        for c in chunks:
            c.score = score
            top.append(c)

    top.sort(key=lambda c: c.score, reverse=True)
    _persist_memory()
    _persist_vector_index()
    return top[:MAX_CHUNKS]


@tool(
    name="find_files",
    description="Find files matching a glob pattern recursively in the workspace.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py', 'src/**/*.ts')"},
            "path": {"type": "string", "description": "Directory to search. Defaults to workspace root."},
        },
        "required": ["pattern"],
    },
)
def find_files(pattern: str, path: str = ".") -> str:
    resolved = _resolve(path)
    matches = []
    for p in pathlib.Path(resolved).rglob(pattern):
        matches.append(str(p.relative_to(resolved)))
    matches.sort()
    if not matches:
        return f"No files matching '{pattern}'"
    return "\n".join(matches[:200]) + (f"\n... and {len(matches)-200} more" if len(matches) > 200 else "")


@tool(
    name="search_files",
    description="Search for a text pattern (regex supported) across files in the workspace. Like ripgrep.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (regex)"},
            "path": {"type": "string", "description": "Directory to search. Defaults to workspace."},
            "file_pattern": {"type": "string", "description": "Glob to filter files (e.g. '*.py'). Optional."},
            "max_results": {"type": "integer", "description": "Max results. Default 50."},
        },
        "required": ["pattern"],
    },
)
def search_files(pattern: str, path: str = ".", file_pattern: str | None = None, max_results: int | None = None) -> str:
    import re
    import core.runtime_config as rc
    _ensure_memory_loaded()
    if max_results is None:
        max_results = int(rc.get("max_search_results", 50))
    resolved = _resolve(path)
    regex = re.compile(pattern, re.IGNORECASE)
    results = []
    total_chars = 0
    _MAX_OUTPUT_CHARS = 30_000  # Hard cap to prevent LLM context blowout
    root = pathlib.Path(resolved)

    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}

    for fpath in root.rglob("*"):
        if any(part in skip_dirs for part in fpath.parts):
            continue
        if not fpath.is_file():
            continue
        if file_pattern and not fnmatch.fnmatch(fpath.name, file_pattern):
            continue
        try:
            if fpath.stat().st_size > MAX_READ_SIZE:
                continue
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except (PermissionError, OSError):
            continue
        has_match = False
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                has_match = True
                rel = str(fpath.relative_to(resolved))
                # Truncate individual match lines to prevent huge single-line results
                trimmed = line.strip()[:200]
                entry = f"{rel}:{i}: {trimmed}"
                total_chars += len(entry) + 1
                results.append(entry)
                if len(results) >= max_results:
                    _persist_memory()
                    return "\n".join(results) + f"\n(capped at {max_results} results)"
                if total_chars >= _MAX_OUTPUT_CHARS:
                    _persist_memory()
                    return "\n".join(results) + f"\n(capped at {_MAX_OUTPUT_CHARS:,} chars — {len(results)} results shown)"
        # Track files we actually read during search
        if has_match:
            rel = str(fpath.relative_to(resolved))
            memory["visited_files"].add(rel)
    _persist_memory()
    return "\n".join(results) if results else f"No matches for '{pattern}'"


@tool(
    name="file_info",
    description="Get metadata about a file (size, modified time, type, line count).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
        },
        "required": ["path"],
    },
)
def file_info(path: str) -> dict:
    resolved = _resolve(path)
    stat = os.stat(resolved)
    import time
    line_count = None
    if os.path.isfile(resolved):
        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                line_count = sum(1 for _ in f)
        except Exception:
            pass
    return {
        "path": path,
        "resolved": resolved,
        "size_bytes": stat.st_size,
        "line_count": line_count,
        "modified": time.ctime(stat.st_mtime),
        "is_file": os.path.isfile(resolved),
        "is_dir": os.path.isdir(resolved),
    }


@tool(
    name="summarize_code",
    description="Extract the structure of a source file: classes, functions, imports. Great for large files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
        },
        "required": ["path"],
    },
)
def summarize_code(path: str) -> str:
    import re as _re
    resolved = _resolve(path)
    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    sections: dict[str, list[str]] = {"imports": [], "classes": [], "functions": [], "exports": [], "other": []}
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        if _re.match(r"^(import |from .+ import |const .+ = require|#include|using )", stripped):
            sections["imports"].append(f"  L{i}: {stripped}")
        elif _re.match(r"^(class |struct |interface |enum |type )\w+", stripped):
            sections["classes"].append(f"  L{i}: {stripped}")
        elif _re.match(r"^(def |async def |function |async function |export (default )?(function|const|class)|pub fn |fn )", stripped):
            sections["functions"].append(f"  L{i}: {stripped}")
        elif _re.match(r"^(export |module\.exports|__all__)", stripped):
            sections["exports"].append(f"  L{i}: {stripped}")

    out = [f"File: {path} ({len(lines)} lines)"]
    for key, items in sections.items():
        if items:
            out.append(f"\n{key.upper()} ({len(items)}):")
            out.extend(items[:50])
            if len(items) > 50:
                out.append(f"  ... and {len(items)-50} more")
    return "\n".join(out) if len(out) > 1 else f"File: {path} ({len(lines)} lines) — no recognizable structure found"


@tool(
    name="count_tokens_estimate",
    description="Rough token count estimate for a file or text (~4 chars per token).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to count. Provide this OR text."},
            "text": {"type": "string", "description": "Raw text to count. Provide this OR path."},
        },
        "required": [],
    },
)
def count_tokens_estimate(path: str | None = None, text: str | None = None) -> dict:
    if path:
        resolved = _resolve(path)
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    if not text:
        return {"error": "Provide path or text"}
    chars = len(text)
    estimated_tokens = chars // 4
    return {"chars": chars, "words": len(text.split()), "estimated_tokens": estimated_tokens}



def _refine_chunks_to_symbols(chunks: list[SearchChunk], query: str, path: str) -> list[SearchChunk]:
    """2-stage zoom: refine large chunks to function-level boundaries using AST.

    If a chunk is >80 lines and contains function/class definitions, split it
    into tighter sub-chunks around the specific symbols that are relevant to
    the query. Small chunks pass through unchanged.
    """
    _REFINE_THRESHOLD = 80  # Only refine chunks larger than this
    query_terms = set(_tokenize(query))
    if not query_terms:
        return chunks

    refined: list[SearchChunk] = []
    for c in chunks:
        span = c.end_line - c.start_line + 1
        if span <= _REFINE_THRESHOLD:
            refined.append(c)
            continue

        # Try to find symbol boundaries within this chunk
        fpath = pathlib.Path(_resolve(path)) / c.file_path
        if not fpath.exists():
            refined.append(c)
            continue

        text = _safe_read(fpath)
        if not text:
            refined.append(c)
            continue

        sym_ranges = _extract_symbol_ranges_from_ast(fpath, text)
        if not sym_ranges:
            refined.append(c)
            continue

        lines = text.splitlines()
        # Find symbols that overlap with this chunk AND match the query
        sub_chunks: list[SearchChunk] = []
        for sr in sym_ranges:
            # Check overlap with chunk range
            if sr["end"] < c.start_line or sr["start"] > c.end_line:
                continue
            # Check if symbol name is relevant to query
            name_lower = sr["name"].lower()
            name_terms = set(_tokenize(sr["name"]))
            if not (name_terms & query_terms) and not any(q in name_lower for q in query_terms):
                # Also check if the symbol body contains query terms
                body_start = sr["start"] - 1
                body_end = min(sr["end"], len(lines))
                body_text = "\n".join(lines[body_start:body_end]).lower()
                if not any(q in body_text for q in query_terms):
                    continue

            start = sr["start"] - 1  # 0-indexed
            end = min(sr["end"], len(lines))
            if end - start > 200:
                end = start + 200
            content = "\n".join(lines[start:end])
            sub_chunks.append(SearchChunk(
                c.file_path, sr["start"], sr["end"], content, c.score
            ))

        if sub_chunks:
            refined.extend(sub_chunks[:3])  # Max 3 sub-chunks per original chunk
        else:
            refined.append(c)  # No refinable symbols found, keep original

    # Re-sort and re-cap after refinement
    refined.sort(key=lambda x: x.score, reverse=True)
    return refined[:MAX_CHUNKS * 2]  # Allow slightly more chunks after refinement


@tool(
    name="smart_context_search",
    description="Parallel retrieval pipeline with BM25 keyword scoring, AST symbol lookup, bounded chunks, and memory-aware context assembly.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "path": {"type": "string", "description": "Where to search. Defaults to workspace root."},
            "file_pattern": {"type": "string", "description": "Optional file glob filter (e.g. '*.py')."},
        },
        "required": ["query"],
    },
)
def smart_context_search(query: str, path: str = ".", file_pattern: str | None = None) -> dict:
    """
    Retrieval strategy:
    1) Decide what to search: query terms + symbols.
    2) Decide where to look: candidate files under path/file_pattern.
    3) Retrieve in parallel, then cap context by MAX_LINES/MAX_CHUNKS.
    """

    async def _run() -> tuple[list[SearchChunk], list[SearchChunk], list[SearchChunk]]:
        return await asyncio.gather(
            _keyword_search(query, path, file_pattern),
            _vector_search(query, path, file_pattern),
            _symbol_lookup(query, path, file_pattern),
        )

    keyword_chunks, vector_chunks, symbol_chunks = asyncio.run(_run())

    merged: dict[tuple[str, int, int], SearchChunk] = {}
    for c in (keyword_chunks + vector_chunks + symbol_chunks):
        key = (c.file_path, c.start_line, c.end_line)
        old = merged.get(key)
        if old is None or c.score > old.score:
            merged[key] = c

    top = sorted(merged.values(), key=lambda c: c.score, reverse=True)[:MAX_CHUNKS]

    # --- 2-stage zoom: refine large chunks to function-level boundaries ---
    top = _refine_chunks_to_symbols(top, query, path)

    total_lines = sum((c.end_line - c.start_line + 1) for c in top)
    if total_lines > MAX_LINES:
        bounded: list[SearchChunk] = []
        used = 0
        for c in top:
            span = c.end_line - c.start_line + 1
            if used + span <= MAX_LINES:
                bounded.append(c)
                used += span
                continue
            remain = MAX_LINES - used
            if remain <= 0:
                break
            lines = c.content.splitlines()
            trimmed = "\n".join(lines[:remain])
            bounded.append(SearchChunk(c.file_path, c.start_line, c.start_line + max(0, len(trimmed.splitlines()) - 1), trimmed, c.score))
            break
        top = bounded

    plan = {
        "what_to_search": _tokenize(query),
        "where_to_look": {"path": path, "file_pattern": file_pattern or "*"},
        "limits": {"MAX_LINES": MAX_LINES, "MAX_CHUNKS": MAX_CHUNKS},
    }

    ctx = build_context(top)
    # Hard cap context payload to prevent LLM context blowout
    if len(ctx) > 30_000:
        ctx = ctx[:30_000] + "\n... [context capped at 30,000 chars]"

    return {
        "plan": plan,
        "context": ctx,
        "chunks": [
            {
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "score": round(c.score, 4),
            }
            for c in top
        ],
        "memory": {
            "visited_files": len(memory["visited_files"]),
            "important_symbols": sorted(memory["important_symbols"])[:100],
            "summaries_count": len(memory["summaries"]),
        },
        "file_summaries": _relevant_file_summaries(top),
    }
