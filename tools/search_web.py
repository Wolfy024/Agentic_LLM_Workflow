"""Web search and URL fetching tools — Serper integration, read_url."""

from __future__ import annotations

from .registry import tool


SERPER_API_KEY: str | None = None


def set_serper_key(key: str):
    global SERPER_API_KEY
    SERPER_API_KEY = key


def _serper_request(endpoint: str, payload: dict) -> dict:
    import httpx
    if not SERPER_API_KEY:
        return {"error": "Serper API key not configured. Set 'serper_api_key' in config.json."}
    resp = httpx.post(
        f"https://google.serper.dev/{endpoint}",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


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


@tool(
    name="web_search",
    description="Search the web using Google (via Serper). Returns titles, snippets, and URLs. Great for finding documentation, error solutions, library info, current events.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "num_results": {"type": "integer", "description": "Number of results. Default 10. Max 20."},
        },
        "required": ["query"],
    },
)
def web_search(query: str, num_results: int = 10) -> str:
    try:
        data = _serper_request("search", {"q": query, "num": min(num_results, 20)})
    except Exception as e:
        return f"Search error: {e}"

    results = []

    if "answerBox" in data:
        ab = data["answerBox"]
        answer = ab.get("answer") or ab.get("snippet") or ab.get("title", "")
        if answer:
            results.append(f"ANSWER: {answer}\n")

    if "knowledgeGraph" in data:
        kg = data["knowledgeGraph"]
        title = kg.get("title", "")
        desc = kg.get("description", "")
        if title:
            results.append(f"{title}: {desc}\n")

    for i, r in enumerate(data.get("organic", []), 1):
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("link", "")
        results.append(f"{i}. [{title}]({url})\n   {snippet}")

    paa = data.get("peopleAlsoAsk", [])
    if paa:
        results.append("\nPeople also ask:")
        for item in paa[:3]:
            q = item.get("question", "")
            s = item.get("snippet", "")
            results.append(f"  Q: {q}\n  A: {s}")

    return "\n\n".join(results) if results else "No results found."


@tool(
    name="web_search_news",
    description="Search for recent news articles on a topic (via Serper).",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "News search query"},
            "num_results": {"type": "integer", "description": "Number of results. Default 8."},
        },
        "required": ["query"],
    },
)
def web_search_news(query: str, num_results: int = 8) -> str:
    try:
        data = _serper_request("news", {"q": query, "num": min(num_results, 20)})
    except Exception as e:
        return f"News search error: {e}"
    results = []
    for i, r in enumerate(data.get("news", []), 1):
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("link", "")
        date = r.get("date", "")
        source = r.get("source", "")
        results.append(f"{i}. [{title}]({url})\n   {source} · {date}\n   {snippet}")
    return "\n\n".join(results) if results else "No news found."


@tool(
    name="web_search_images",
    description="Search for images on a topic (via Serper). Returns image URLs and context.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Image search query"},
            "num_results": {"type": "integer", "description": "Number of results. Default 5."},
        },
        "required": ["query"],
    },
)
def web_search_images(query: str, num_results: int = 5) -> str:
    try:
        data = _serper_request("images", {"q": query, "num": min(num_results, 20)})
    except Exception as e:
        return f"Image search error: {e}"
    results = []
    for i, r in enumerate(data.get("images", []), 1):
        title = r.get("title", "")
        url = r.get("imageUrl", "")
        source = r.get("link", "")
        results.append(f"{i}. {title}\n   Image: {url}\n   Source: {source}")
    return "\n\n".join(results) if results else "No images found."
