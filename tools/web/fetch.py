"""
Read URL web tool and HTTP(S) download to workspace.

`read_url` returns extracted text for browsing docs.
`download_url` streams bytes to a workspace file (binaries, archives, etc.).
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from tools.registry import tool, _resolve

# Cap downloads to avoid filling disk / memory (streaming; enforced while reading).
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MiB


def _validate_http_url(url: str) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http(s) URLs are allowed (got {parsed.scheme!r})")
    if not parsed.netloc:
        raise ValueError("Invalid URL: missing host")


@tool(
    name="read_url",
    description="Fetch and read a URL (documentation, web page). Returns text content.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
        },
        "required": ["url"],
    },
)
def read_url(url: str) -> str:
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            try:
                from html.parser import HTMLParser

                class TextExtractor(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.parts: list[str] = []
                        self._skip = False
                        self._skip_tags = {"script", "style", "nav", "footer", "header"}

                    def handle_starttag(self, tag, attrs):
                        if tag in self._skip_tags:
                            self._skip = True

                    def handle_endtag(self, tag):
                        if tag in self._skip_tags:
                            self._skip = False

                    def handle_data(self, data):
                        if not self._skip:
                            text = data.strip()
                            if text:
                                self.parts.append(text)

                extractor = TextExtractor()
                extractor.feed(resp.text)
                return "\n".join(extractor.parts)[:8000]
            except Exception:
                return resp.text[:8000]
        return resp.text[:8000]
    except Exception as e:
        return f"Error fetching URL: {e}"


@tool(
    name="download_url",
    description=(
        "Download a file from an http(s) URL into the workspace. "
        "Use for archives, images, binaries, or large docs. "
        "Path is relative to the workspace. Max size 100 MiB."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "http(s) URL to download"},
            "path": {
                "type": "string",
                "description": "Destination file path inside the workspace (e.g. vendor/lib.zip)",
            },
        },
        "required": ["url", "path"],
    },
)
def download_url(url: str, path: str) -> str:
    _validate_http_url(url)
    resolved = _resolve(path)
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)

    written = 0
    try:
        with httpx.stream(
            "GET",
            url.strip(),
            follow_redirects=True,
            timeout=httpx.Timeout(120.0, connect=30.0),
            headers={"User-Agent": "LLM-Orchestrator/1.0 (download_url)"},
        ) as resp:
            resp.raise_for_status()
            with open(resolved, "wb") as out:
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    written += len(chunk)
                    if written > MAX_DOWNLOAD_BYTES:
                        raise ValueError(
                            f"Download exceeded max size ({MAX_DOWNLOAD_BYTES // (1024 * 1024)} MiB)"
                        )
                    out.write(chunk)
    except Exception:
        try:
            if os.path.isfile(resolved):
                os.remove(resolved)
        except OSError:
            pass
        raise

    return f"Downloaded {written} bytes to {path}"
