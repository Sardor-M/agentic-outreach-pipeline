"""
Prospect Finder — DuckDuckGo web search + contact extraction

Searches for manufacturing companies matching a query, then does
follow-up searches to extract email addresses and phone numbers.
"""

import re
import time

from ddgs import DDGS


# Email regex — catches common patterns in search snippets
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# Phone regex — international formats
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}",
)

# Generic / junk emails to skip
JUNK_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "googleapis.com",
    "google.com", "facebook.com", "twitter.com", "schema.org",
    "youtube.com", "instagram.com", "linkedin.com", "tiktok.com",
}

# Domains that are never real company websites
IRRELEVANT_DOMAINS = {
    # Social media / general
    "wikipedia.org", "youtube.com", "tiktok.com", "pinterest.com",
    "facebook.com", "instagram.com", "reddit.com", "twitter.com",
    "x.com", "linkedin.com", "amazon.com", "ebay.com", "alibaba.com",
    "apple.com", "developer.apple.com", "google.com", "yelp.com",
    "glassdoor.com", "indeed.com", "quora.com", "medium.com",
    "bbb.org", "trustpilot.com",
    # Directory / listing / market research sites
    "thomasnet.com", "iqsdirectory.com", "globalspec.com",
    "mordorintelligence.com", "grandviewresearch.com", "statista.com",
    "ibisworld.com", "dnb.com", "zoominfo.com", "crunchbase.com",
    "ensun.com", "inven.ai", "marketsandmarkets.com",
    "made-in-china.com", "globalsources.com", "indiamart.com",
    "europages.com", "kompass.com", "yellowpages.com",
}

# Title patterns that indicate directory/listing pages, not real companies
DIRECTORY_PATTERNS = re.compile(
    r"(?i)"
    r"(^top\s+\d+\s)"            # "Top 100 ..."
    r"|(best\s+\d+\s)"           # "Best 10 ..."
    r"|(\d+\s+best\s)"           # "10 Best ..."
    r"|(companies\s+in\s)"       # "Companies in Germany"
    r"|(market\s+size)"          # "Market Size & Outlook"
    r"|(market\s+report)"        # "Market Report"
    r"|(companies\s+list)"       # "Companies List"
    r"|(manufacturers\s*&\s*suppliers)"  # "Manufacturers & Suppliers"
    r"|(manufacturers,\s*factories)"     # "Manufacturers, Factories"
    r"|(manufacturers\s+and\s+suppliers)" # "Manufacturers and Suppliers"
    r"|(\|\s*b2b\s)"                     # "| B2B companies"
    r"|(suppliers\s+in\s+\w+$)"          # "Suppliers in Germany"
    r"|(buy\s+or\s+sell)"                # "Buy or Sell a Business"
)


def _is_valid_email(email: str) -> bool:
    """Filter out obviously fake or generic emails."""
    domain = email.split("@")[-1].lower()
    if domain in JUNK_DOMAINS:
        return False
    if email.startswith("noreply") or email.startswith("no-reply"):
        return False
    return True


def _extract_emails(text: str) -> list[str]:
    """Pull email addresses from a block of text."""
    found = EMAIL_RE.findall(text)
    return list(dict.fromkeys(e for e in found if _is_valid_email(e)))


def _extract_phones(text: str) -> list[str]:
    """Pull phone numbers from a block of text."""
    found = PHONE_RE.findall(text)
    cleaned = []
    for p in found:
        digits = re.sub(r"\D", "", p)
        if 7 <= len(digits) <= 15:
            cleaned.append(p.strip())
    return list(dict.fromkeys(cleaned))


def _is_relevant_result(url: str, title: str) -> bool:
    """Filter out irrelevant search results (directories, social media, etc.)."""
    domain = re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0].lower()
    for bad in IRRELEVANT_DOMAINS:
        if domain == bad or domain.endswith("." + bad):
            return False
    if DIRECTORY_PATTERNS.search(title):
        return False
    return True


def search_companies(query: str, max_results: int = 10) -> list[dict]:
    """
    Search DuckDuckGo for companies matching the query.

    Appends 'manufacturer company' to the query if not already present
    to improve result quality for B2B manufacturing searches.

    Returns list of dicts:
        {"title": str, "url": str, "snippet": str, "domain": str}
    """
    # Enhance query for manufacturing-specific results
    q_lower = query.lower()
    enhanced = query
    if not any(w in q_lower for w in ["manufacturer", "company", "factory", "supplier", "gmbh", "inc", "ltd", "corp"]):
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

        # Deduplicate by domain
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


def enrich_contacts(companies: list[dict], delay: float = 1.0) -> list[dict]:
    """
    For each company, do a follow-up search to find email/phone.
    Adds 'emails' and 'phones' keys to each company dict.
    """
    print(f"\n  Enriching contact info for {len(companies)} companies...")

    ddgs = DDGS()

    for i, company in enumerate(companies):
        name = company["title"]
        domain = company["domain"]

        # Combine snippet text for initial extraction
        combined_text = f"{company['snippet']} {company['url']}"

        # Follow-up search for contact info
        contact_query = f'"{domain}" email contact'
        try:
            contact_results = list(ddgs.text(contact_query, max_results=5))
            for cr in contact_results:
                combined_text += f" {cr.get('body', '')} {cr.get('title', '')}"
        except Exception:
            pass  # Contact enrichment is best-effort

        company["emails"] = _extract_emails(combined_text)
        company["phones"] = _extract_phones(combined_text)

        print(f"    [{i+1}/{len(companies)}] {name[:40]} — "
              f"{len(company['emails'])} emails, {len(company['phones'])} phones")

        if delay and i < len(companies) - 1:
            time.sleep(delay)

    return companies


def find_prospects(
    query: str,
    max_results: int = 10,
    search_delay: float = 1.0,
) -> list[dict]:
    """
    Full pipeline: search for companies, then enrich with contact info.

    Returns list of dicts with keys:
        title, url, snippet, domain, emails, phones
    """
    companies = search_companies(query, max_results=max_results)
    if not companies:
        print("  No companies found.")
        return []

    companies = enrich_contacts(companies, delay=search_delay)
    return companies


def format_prospect_for_agent(prospect: dict) -> str:
    """Format a prospect dict into a text block for Claude agents."""
    email_str = ", ".join(prospect["emails"]) if prospect["emails"] else "Not found"
    phone_str = ", ".join(prospect["phones"]) if prospect["phones"] else "Not found"

    return (
        f"Company: {prospect['title']}\n"
        f"Website: {prospect['url']}\n"
        f"Description: {prospect['snippet']}\n"
        f"Email(s): {email_str}\n"
        f"Phone(s): {phone_str}"
    )
