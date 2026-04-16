"""
Read URL web tool.

Fetches web pages, extracts main body text by stripping scripts and styles,
and returns readable content.
"""

from __future__ import annotations
from tools.registry import tool


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
    import httpx
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
