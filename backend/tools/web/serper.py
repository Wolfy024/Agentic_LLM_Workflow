"""
Searches the web via Serper API.

Provides tools for standard Google searches, news, and images.
"""

from __future__ import annotations
from tools.registry import tool

SERPER_API_KEY: str | None = None


def set_serper_key(key: str) -> None:
    """Inject the global Serper API key for authentication."""
    global SERPER_API_KEY
    SERPER_API_KEY = key


def _serper_request(endpoint: str, payload: dict) -> dict:
    import httpx
    if not SERPER_API_KEY:
        return {"error": "Serper API key not configured. Set SERPER_API_KEY in your .env file."}
    resp = httpx.post(
        f"https://google.serper.dev/{endpoint}",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@tool(
    name="web_search",
    description="Search the web using Google (via Serper). Returns titles, snippets, and URLs.",
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
