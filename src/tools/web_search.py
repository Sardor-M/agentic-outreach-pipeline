"""
Web Search Tool — DuckDuckGo search with domain filtering.

Ported from prospector.py:search_companies() with the full domain
filtering logic (92 blocked domains, directory patterns).
"""

from __future__ import annotations

import re

from ddgs import DDGS

from tools.base import BaseTool

# Domains that are never real company websites
IRRELEVANT_DOMAINS = {
    "wikipedia.org", "youtube.com", "tiktok.com", "pinterest.com",
    "facebook.com", "instagram.com", "reddit.com", "twitter.com",
    "x.com", "linkedin.com", "amazon.com", "ebay.com", "alibaba.com",
    "apple.com", "developer.apple.com", "google.com", "yelp.com",
    "glassdoor.com", "indeed.com", "quora.com", "medium.com", "bbb.org",
    "trustpilot.com", "thomasnet.com", "iqsdirectory.com", "globalspec.com",
    "mordorintelligence.com", "grandviewresearch.com", "statista.com",
    "ibisworld.com", "dnb.com", "zoominfo.com", "crunchbase.com",
    "ensun.com", "inven.ai", "marketsandmarkets.com", "made-in-china.com",
    "globalsources.com", "indiamart.com", "europages.com", "kompass.com",
    "yellowpages.com",
}

# Title patterns indicating directory/listing pages
DIRECTORY_PATTERNS = re.compile(
    r"(?i)"
    r"(^top\s+\d+\s)"
    r"|(best\s+\d+\s)"
    r"|(\d+\s+best\s)"
    r"|(companies\s+in\s)"
    r"|(market\s+size)"
    r"|(market\s+report)"
    r"|(companies\s+list)"
    r"|(manufacturers\s*&\s*suppliers)"
    r"|(manufacturers,\s*factories)"
    r"|(manufacturers\s+and\s+suppliers)"
    r"|(\|\s*b2b\s)"
    r"|(suppliers\s+in\s+\w+$)"
    r"|(buy\s+or\s+sell)"
)


def _is_relevant_result(url: str, title: str) -> bool:
    """Filter out irrelevant search results."""
    domain = re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0].lower()
    for bad in IRRELEVANT_DOMAINS:
        if domain == bad or domain.endswith("." + bad):
            return False
    if DIRECTORY_PATTERNS.search(title):
        return False
    return True


class WebSearchTool(BaseTool):
    name = "search_web"
    description = (
        "Search the web using DuckDuckGo. Use this to find information about "
        "the target company, their industry, recent news, and competitors. "
        "Returns a list of search results with titles, URLs, and snippets."
    )

    def _input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific — include company name, industry, or topic.",
                },
            },
            "required": ["query"],
        }

    def _execute(self, query: str = "", max_results: int = 5) -> str:
        if not query:
            return "Error: No search query provided."

        ddgs = DDGS()
        try:
            results = list(ddgs.text(query, max_results=max_results * 2))
        except Exception as e:
            raise RuntimeError(f"DuckDuckGo search failed: {e}")

        companies = []
        seen_domains = set()

        for r in results:
            url = r.get("href", "")
            title = r.get("title", "")
            snippet = r.get("body", "")

            if not _is_relevant_result(url, title):
                continue

            domain = re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0].lower()
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            companies.append(f"- {title}\n  URL: {url}\n  {snippet}")

            if len(companies) >= max_results:
                break

        if not companies:
            return "No search results found."

        return "\n".join(companies)


def search_companies(query: str, max_results: int = 10) -> list[dict]:
    """Search DuckDuckGo for companies matching the query.

    This is the public API matching the old prospector.search_companies() signature.
    """
    q_lower = query.lower()
    enhanced = query
    if not any(
        w in q_lower
        for w in ["manufacturer", "company", "factory", "supplier", "gmbh", "inc", "ltd", "corp"]
    ):
        enhanced = f"{query} manufacturer company"

    print(f"\n  Searching DuckDuckGo: '{enhanced}'")

    ddgs = DDGS()
    try:
        results = list(ddgs.text(enhanced, max_results=max_results * 2))
    except Exception as e:
        print(f"  Search error: {e}")
        return []

    companies = []
    seen_domains = set()

    for r in results:
        url = r.get("href", "")
        title = r.get("title", "")
        snippet = r.get("body", "")

        if not _is_relevant_result(url, title):
            continue

        domain = re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0].lower()
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        companies.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "domain": domain,
        })

        if len(companies) >= max_results:
            break

    print(f"  Found {len(companies)} unique company results")
    return companies
