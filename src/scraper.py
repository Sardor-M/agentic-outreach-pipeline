"""
Website Scraper — extract clean text from web pages

Used by the agentic researcher to scrape company websites
for information about their manufacturing operations.
"""

import requests
from bs4 import BeautifulSoup


# Tags that contain noise, not content
STRIP_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "form", "noscript", "iframe",
]

MAX_CHARS = 4000
TIMEOUT = 10


def scrape_website(url: str) -> str:
    """
    Fetch a URL and return clean text content.

    Returns an error string (not exception) if the request fails,
    so the agent can see the error and adapt.
    """
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; 3ViewResearchBot/1.0; "
                    "+https://e3view.com)"
                ),
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

    # Parse HTML and extract text
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise tags
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    # Get text, collapse whitespace
    text = soup.get_text(separator=" ", strip=True)

    # Collapse multiple spaces/newlines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    # Truncate to limit
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[...truncated]"

    return text
