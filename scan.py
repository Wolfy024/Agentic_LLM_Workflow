"""
AST inventory and architecture checks for LLM Orchestrator.

Default: validate that Python sources parse and follow project import rules.
Use --inventory for per-file function/class size report (legacy behavior).
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

SKIP_DIR_NAMES = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache"}


def iter_py_files(root: str, *, include_tests: bool = True) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        rel = os.path.relpath(dirpath, root)
        if not include_tests and rel != "." and rel.split(os.sep)[0] == "tests":
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def check_imports(tree: ast.AST, path: str) -> list[str]:
    """Return human-readable violations (empty if OK)."""
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "theme" or alias.name.startswith("theme."):
                    bad.append(f"{path}: forbidden import `{alias.name}` (use ui.* modules)")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "theme" or mod.startswith("theme."):
                bad.append(f"{path}: forbidden import from `{mod}` (use ui.* modules)")
    return bad


def validate_file(path: str, *, check_theme_imports: bool) -> tuple[list[str], list[str]]:
    """Returns (parse_errors, rule_violations)."""
    violations: list[str] = []
    parse_errs: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        return [f"{path}: read error: {e}"], []

    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as e:
        parse_errs.append(f"{path}: syntax error: {e}")
        return parse_errs, []

    if check_theme_imports:
        violations.extend(check_imports(tree, path))
    return parse_errs, violations


def report_functions(path: str) -> None:
    print(f"--- {path} ---")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return

    try:
        tree = ast.parse(content)
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        return

    funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    print(f"Total functions: {len(funcs)}")
    for f in funcs:
        lines = f.end_lineno - f.lineno + 1
        print(f"  def {f.name}(): {lines} lines")

    print(f"Total classes: {len(classes)}")
    for c in classes:
        lines = c.end_lineno - c.lineno + 1
        methods = [n for n in c.body if isinstance(n, ast.FunctionDef)]
        print(f"  class {c.name}: {lines} lines, {len(methods)} methods")
        for m in methods:
            mlines = m.end_lineno - m.lineno + 1
            print(f"    def {m.name}(): {mlines} lines")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="LLM Orchestrator AST scan")
    ap.add_argument(
        "--inventory",
        action="store_true",
        help="Print function/class counts per file (walk tree, skip tests/)",
    )
    ap.add_argument(
        "--root",
        default=".",
        help="Project root (default: current directory)",
    )
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    if args.inventory:
        for path in iter_py_files(root, include_tests=False):
            if os.path.basename(path) == "scan.py":
                continue
            report_functions(path)
        return

    paths = iter_py_files(root, include_tests=True)
    all_parse: list[str] = []
    all_bad: list[str] = []
    for path in paths:
        under_tests = f"{os.sep}tests{os.sep}" in path or path.endswith(f"{os.sep}tests")
        parse_errs, violations = validate_file(path, check_theme_imports=not under_tests)
        all_parse.extend(parse_errs)
        all_bad.extend(violations)

    if all_parse:
        print("Parse failures:", file=sys.stderr)
        for line in all_parse:
            print(f"  {line}", file=sys.stderr)
    if all_bad:
        print("Rule violations:", file=sys.stderr)
        for line in all_bad:
            print(f"  {line}", file=sys.stderr)

    if all_parse or all_bad:
        sys.exit(1)

    print(f"OK - {len(paths)} Python file(s) under {root} (parse + import rules)")


if __name__ == "__main__":
    main()
