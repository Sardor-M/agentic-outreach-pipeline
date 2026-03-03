"""
Web Scraper Tool — Fetch and extract clean text from web pages.

Ported from scraper.py with added LangExtract fact extraction capability.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from tools.base import BaseTool

STRIP_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]
MAX_CHARS = 4000
TIMEOUT = 10


def _fetch_text(url: str) -> str:
    """Fetch a URL and return clean text content.

    Returns an error string (not exception) if the request fails,
    so the agent can see the error and adapt.
    """
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/2.0)",
            },
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return f"Error: Request timed out after {TIMEOUT}s for {url}"
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to {url}"
    except requests.exceptions.HTTPError as e:
        return f"Error: HTTP {e.response.status_code} for {url}"
    except requests.exceptions.RequestException as e:
        return f"Error: Failed to fetch {url} — {e}"

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[...truncated]"

    return text


class WebScraperTool(BaseTool):
    name = "scrape_company_website"
    description = (
        "Fetch and read the text content of a web page. Use this to read a "
        "company's website and learn about their products, operations, and scale. "
        "Returns clean text (HTML stripped), truncated to ~4000 characters."
    )

    def __init__(self):
        super().__init__()
        self._extractor = None

    def _input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to scrape (must start with http:// or https://).",
                },
            },
            "required": ["url"],
        }

    def _execute(self, url: str = "") -> str:
        if not url:
            return "Error: No URL provided."
        return _fetch_text(url)

    def scrape_and_extract(self, url: str) -> dict:
        """Scrape a page and extract structured facts using LangExtract.

        Returns dict with 'text' (raw) and 'facts' (structured CompanyFact list).
        Falls back to raw text if LangExtract is unavailable.
        """
        text = self.run(url=url)
        if text.startswith("Error:"):
            return {"text": text, "facts": []}

        facts = []
        try:
            from knowledge.extractor import StructuredExtractor

            if self._extractor is None:
                self._extractor = StructuredExtractor()
            facts = self._extractor.extract_company_facts(text, source_url=url)
        except Exception:
            pass  # LangExtract is optional

        return {"text": text, "facts": facts}


# Backward-compatible function
def scrape_website(url: str) -> str:
    """Backward-compatible wrapper matching old scraper.scrape_website()."""
    return _fetch_text(url)
