"""
Structured Extractor — Uses LangExtract (Gemini) for web page fact extraction.

Replaces ChromaDB's unstructured embedding approach with structured extraction.
Every extracted fact is grounded to its source text.

Falls back to regex-based extraction if LangExtract/Gemini is unavailable.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

from models import CompanyFact

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class StructuredExtractor:
    """Extract structured facts from web page text."""

    def __init__(self):
        self._langextract_available = False
        self._check_langextract()

    def _check_langextract(self):
        """Check if langextract + Gemini API key are available."""
        try:
            import langextract  # noqa: F401

            if os.getenv("GOOGLE_API_KEY"):
                self._langextract_available = True
        except ImportError:
            pass

    def extract_company_facts(
        self,
        text: str,
        source_url: str = "",
        schemas: list[str] | None = None,
    ) -> list[CompanyFact]:
        """Extract structured facts from raw text.

        Uses LangExtract if available, otherwise falls back to regex patterns.
        """
        if self._langextract_available:
            return self._extract_with_langextract(text, source_url, schemas)
        return self._extract_with_regex(text, source_url)

    def _extract_with_langextract(
        self,
        text: str,
        source_url: str,
        schemas: list[str] | None = None,
    ) -> list[CompanyFact]:
        """Use LangExtract to extract structured facts."""
        try:
            from langextract import extract

            from knowledge.schemas import get_schema

            schema_names = schemas or ["company_facts", "manufacturing", "esg"]
            facts = []

            for schema_name in schema_names:
                schema = get_schema(schema_name)
                if not schema:
                    continue

                fields = schema.get("fields", {})
                prompt = f"Extract the following from this text about a company:\n"
                for field, desc in fields.items():
                    prompt += f"- {field}: {desc}\n"

                try:
                    result = extract(text, prompt)
                    if isinstance(result, dict):
                        for key, value in result.items():
                            if value and str(value).strip() and str(value).lower() != "none":
                                facts.append(
                                    CompanyFact(
                                        category=schema_name,
                                        text=f"{key}: {value}",
                                        source_url=source_url,
                                        confidence=0.85,
                                    )
                                )
                    elif isinstance(result, str) and result.strip():
                        facts.append(
                            CompanyFact(
                                category=schema_name,
                                text=result.strip(),
                                source_url=source_url,
                                confidence=0.8,
                            )
                        )
                except Exception:
                    continue

            return facts
        except Exception:
            return self._extract_with_regex(text, source_url)

    def _extract_with_regex(self, text: str, source_url: str) -> list[CompanyFact]:
        """Fallback: extract basic facts using regex patterns."""
        facts = []

        # Extract employee counts
        emp_match = re.search(r"(\d[\d,]*)\s*(?:employees|workers|staff|people)", text, re.IGNORECASE)
        if emp_match:
            facts.append(
                CompanyFact(
                    category="company",
                    text=f"Employee count: {emp_match.group(1)}",
                    source_url=source_url,
                    confidence=0.7,
                )
            )

        # Extract revenue mentions
        rev_match = re.search(
            r"(?:revenue|sales|turnover)\s*(?:of\s*)?[\$€£]?\s*(\d[\d,.]*\s*(?:million|billion|M|B))",
            text,
            re.IGNORECASE,
        )
        if rev_match:
            facts.append(
                CompanyFact(
                    category="financial",
                    text=f"Revenue: {rev_match.group(1)}",
                    source_url=source_url,
                    confidence=0.7,
                )
            )

        # Extract machine/equipment counts
        machine_match = re.search(
            r"(\d+)\s*(?:machines?|presses?|lines?|CNC|equipment)", text, re.IGNORECASE
        )
        if machine_match:
            facts.append(
                CompanyFact(
                    category="manufacturing",
                    text=f"Equipment count: {machine_match.group(0)}",
                    source_url=source_url,
                    confidence=0.6,
                )
            )

        # Extract certifications
        cert_matches = re.findall(
            r"(?:ISO\s*\d{4,5}|IATF\s*\d+|CE\s+mark|UL\s+listed)",
            text,
            re.IGNORECASE,
        )
        for cert in set(cert_matches):
            facts.append(
                CompanyFact(
                    category="company",
                    text=f"Certification: {cert}",
                    source_url=source_url,
                    confidence=0.8,
                )
            )

        # Extract ESG keywords
        esg_keywords = ["carbon neutral", "sustainability", "ESG", "carbon footprint", "renewable energy"]
        text_lower = text.lower()
        for kw in esg_keywords:
            if kw.lower() in text_lower:
                # Find the sentence containing the keyword
                for sentence in re.split(r"[.!?]+", text):
                    if kw.lower() in sentence.lower():
                        facts.append(
                            CompanyFact(
                                category="esg",
                                text=sentence.strip()[:200],
                                source_url=source_url,
                                confidence=0.6,
                            )
                        )
                        break

        return facts
