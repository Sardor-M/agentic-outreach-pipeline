"""
JSON Knowledge Store — Replaces ChromaDB vector store.

Simple file-based structured store. Facts are stored as JSON records
with categories, searchable by field matching and keyword search.
No embeddings, no vector DB — just structured data + keyword matching.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from models import CompanyFact

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STORE_DIR = PROJECT_ROOT / "knowledge_store"
STORE_FILE = STORE_DIR / "facts.json"
OUTREACH_FILE = STORE_DIR / "outreach_history.json"


class KnowledgeStore:
    """JSON-based knowledge store for structured facts."""

    def __init__(self, store_dir: str | Path | None = None):
        self.store_dir = Path(store_dir) if store_dir else STORE_DIR
        self.store_file = self.store_dir / "facts.json"
        self.outreach_file = self.store_dir / "outreach_history.json"
        self.facts: list[dict] = []
        self.outreach: list[dict] = []
        self._product_chunks: list[dict] = []

    def load(self):
        """Load knowledge store from disk and build product chunks."""
        os.makedirs(self.store_dir, exist_ok=True)

        if self.store_file.exists():
            with open(self.store_file, encoding="utf-8") as f:
                self.facts = json.load(f)

        if self.outreach_file.exists():
            with open(self.outreach_file, encoding="utf-8") as f:
                self.outreach = json.load(f)

        self._build_product_chunks()

    def save(self):
        """Persist knowledge store to disk."""
        os.makedirs(self.store_dir, exist_ok=True)

        with open(self.store_file, "w", encoding="utf-8") as f:
            json.dump(self.facts, f, indent=2, ensure_ascii=False)

        with open(self.outreach_file, "w", encoding="utf-8") as f:
            json.dump(self.outreach, f, indent=2, ensure_ascii=False)

    def _build_product_chunks(self):
        """Build searchable product knowledge chunks from YAML config."""
        try:
            from knowledge.product_loader import COMPANY_CONFIG, PRODUCTS_CONFIG

            products = PRODUCTS_CONFIG
            combo = products["combined_solution"]
            icp = products["ideal_customer"]
            case_studies = products["case_studies"]

            self._product_chunks = [
                {"category": "company", "source": "knowledge",
                 "text": f"Company profile: {COMPANY_CONFIG['name']} — {COMPANY_CONFIG.get('industry', '')}"},
            ]

            # Dynamically build chunks for each product
            for product_key, product in products["products"].items():
                name = product["name"]
                self._product_chunks.append(
                    {"category": product_key, "source": "knowledge",
                     "text": f"{name} — {product['tagline']}. {product['description'].strip()} Best for: {', '.join(product['best_for'])}"})
                self._product_chunks.append(
                    {"category": product_key, "source": "knowledge",
                     "text": f"{name} Key Features: " + ". ".join(product["key_features"])})
                if isinstance(product.get("key_functions"), list):
                    self._product_chunks.append(
                        {"category": product_key, "source": "knowledge",
                         "text": f"{name} Key Functions: " + ". ".join(product["key_functions"])})
                elif isinstance(product.get("key_functions"), dict):
                    self._product_chunks.append(
                        {"category": product_key, "source": "knowledge",
                         "text": f"{name} Functions: " + ". ".join(f"{k}: {v}" for k, v in product["key_functions"].items())})
                if "expected_benefits" in product:
                    self._product_chunks.append(
                        {"category": product_key, "source": "knowledge",
                         "text": f"{name} Expected Benefits: " + ". ".join(product["expected_benefits"])})

            self._product_chunks.extend([
                {"category": "combined", "source": "knowledge",
                 "text": f"Combined Solution: {combo['description'].strip()} Synergies: " + ". ".join(combo["synergies"])},
                {"category": "sales", "source": "knowledge",
                 "text": f"Ideal Customer — Industry: {icp['industry']}. Factory size: {icp['factory_size']}. "
                         f"Pain points: " + ". ".join(icp["pain_points"])},
                {"category": "sales", "source": "knowledge",
                 "text": "Typical ROI: " + ". ".join(f"{k}: {v}" for k, v in icp["typical_roi"].items())},
            ])

            for cs in case_studies:
                self._product_chunks.append({
                    "category": "case_study", "source": "knowledge",
                    "text": f"Case Study: {cs['title']}. Solution: {cs['solution']}. Result: {cs['result']}. Tags: {', '.join(cs['tags'])}.",
                })

        except Exception:
            pass

    def add_facts(self, facts: list[CompanyFact]):
        """Add extracted facts to the store."""
        for fact in facts:
            self.facts.append(fact.model_dump())
        self.save()

    def add_outreach(self, data: dict):
        """Index a new outreach result for future reference."""
        self.outreach.append(data)
        self.save()

    def query(self, query: str, n_results: int = 5) -> list[dict]:
        """Search the knowledge store by keyword matching.

        Searches across product chunks, extracted facts, and outreach history.
        Returns the most relevant records.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []

        # Search product chunks
        for chunk in self._product_chunks:
            score = self._score_match(chunk.get("text", ""), query_words, query_lower)
            if score > 0:
                scored.append((score, chunk))

        # Search extracted facts
        for fact in self.facts:
            score = self._score_match(fact.get("text", ""), query_words, query_lower)
            if score > 0:
                scored.append((score, fact))

        # Search outreach history
        for record in self.outreach:
            text = self._outreach_to_text(record)
            score = self._score_match(text, query_words, query_lower)
            if score > 0:
                scored.append((score, {"category": "past_outreach", "source": "outreach", "text": text}))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:n_results]]

    def _score_match(self, text: str, query_words: set, query_lower: str) -> int:
        """Score how well a text matches the query."""
        text_lower = text.lower()
        score = 0

        # Exact phrase match (high score)
        if query_lower in text_lower:
            score += 10

        # Word matches
        for word in query_words:
            if len(word) > 2 and word in text_lower:
                score += 1

        return score

    def _outreach_to_text(self, record: dict) -> str:
        """Convert an outreach record to searchable text."""
        parts = []
        if "company" in record:
            parts.append(f"Past outreach to {record['company']}")
        if "industry" in record:
            parts.append(f"Industry: {record['industry']}")
        if "query" in record:
            parts.append(f"Search query: {record['query']}")
        if "research_brief" in record:
            brief = record["research_brief"]
            if len(brief) > 500:
                brief = brief[:500] + "..."
            parts.append(f"Brief: {brief}")
        return ". ".join(parts)

    def get_formatted_results(self, query: str, n_results: int = 3) -> str:
        """Get formatted results string (backward-compatible with old RAG query)."""
        results = self.query(query, n_results)
        if not results:
            return "No relevant results found."

        parts = []
        for i, record in enumerate(results):
            source = record.get("source", "unknown")
            category = record.get("category", "unknown")
            text = record.get("text", "")
            parts.append(f"[Result {i + 1}] (source: {source}, category: {category})\n{text}")

        return "\n\n".join(parts)
