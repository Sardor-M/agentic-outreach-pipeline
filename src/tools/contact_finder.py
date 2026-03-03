"""
Contact Finder Tool — Email and phone extraction from web search results.

Ported from prospector.py:enrich_contacts() with the email/phone regex patterns
and junk domain filtering.
"""

from __future__ import annotations

import re
import time

from ddgs import DDGS

from tools.base import BaseTool

# Email regex
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Phone regex — international formats
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
)

# Generic / junk emails to skip
JUNK_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "googleapis.com",
    "google.com", "facebook.com", "twitter.com", "schema.org",
    "youtube.com", "instagram.com", "linkedin.com", "tiktok.com",
}


def _is_valid_email(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    if domain in JUNK_DOMAINS:
        return False
    if email.startswith("noreply") or email.startswith("no-reply"):
        return False
    return True


def _extract_emails(text: str) -> list[str]:
    found = EMAIL_RE.findall(text)
    return list(dict.fromkeys(e for e in found if _is_valid_email(e)))


def _extract_phones(text: str) -> list[str]:
    found = PHONE_RE.findall(text)
    cleaned = []
    for p in found:
        digits = re.sub(r"\D", "", p)
        if 7 <= len(digits) <= 15:
            cleaned.append(p.strip())
    return list(dict.fromkeys(cleaned))


class ContactFinderTool(BaseTool):
    name = "find_contacts"
    description = (
        "Search for email addresses and phone numbers for a company. "
        "Uses DuckDuckGo follow-up searches to extract contact information."
    )

    def _input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The company name to find contacts for.",
                },
                "domain": {
                    "type": "string",
                    "description": "The company's website domain (e.g., 'example.com').",
                },
            },
            "required": ["company_name"],
        }

    def _execute(self, company_name: str = "", domain: str = "") -> str:
        if not company_name:
            return "Error: No company name provided."

        query = f'"{domain}" email contact' if domain else f'"{company_name}" email contact'

        ddgs = DDGS()
        combined_text = ""

        try:
            results = list(ddgs.text(query, max_results=5))
            for cr in results:
                combined_text += f" {cr.get('body', '')} {cr.get('title', '')}"
        except Exception:
            pass

        emails = _extract_emails(combined_text)
        phones = _extract_phones(combined_text)

        parts = []
        if emails:
            parts.append(f"Emails: {', '.join(emails)}")
        if phones:
            parts.append(f"Phones: {', '.join(phones)}")

        return "\n".join(parts) if parts else "No contact information found."


def enrich_contacts(companies: list[dict], delay: float = 1.0) -> list[dict]:
    """Enrich a list of company dicts with emails and phones.

    Backward-compatible with old prospector.enrich_contacts() signature.
    """
    print(f"\n  Enriching contact info for {len(companies)} companies...")

    ddgs = DDGS()

    for i, company in enumerate(companies):
        name = company["title"]
        domain = company.get("domain", "")

        combined_text = f"{company.get('snippet', '')} {company.get('url', '')}"

        contact_query = f'"{domain}" email contact' if domain else f'"{name}" email contact'
        try:
            contact_results = list(ddgs.text(contact_query, max_results=5))
            for cr in contact_results:
                combined_text += f" {cr.get('body', '')} {cr.get('title', '')}"
        except Exception:
            pass

        company["emails"] = _extract_emails(combined_text)
        company["phones"] = _extract_phones(combined_text)

        print(
            f"    [{i + 1}/{len(companies)}] {name[:40]} — "
            f"{len(company['emails'])} emails, {len(company['phones'])} phones"
        )

        if delay and i < len(companies) - 1:
            time.sleep(delay)

    return companies


def find_prospects(query: str, max_results: int = 10, search_delay: float = 1.0) -> list[dict]:
    """Full pipeline: search for companies then enrich with contact info.

    Backward-compatible with old prospector.find_prospects() signature.
    """
    from tools.web_search import search_companies

    companies = search_companies(query, max_results=max_results)
    if not companies:
        print("  No companies found.")
        return []

    companies = enrich_contacts(companies, delay=search_delay)
    return companies
