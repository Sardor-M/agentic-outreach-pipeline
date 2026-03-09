"""
ChromaDB Vector Knowledge Store — Semantic search over product knowledge,
extracted company facts, and past outreach history.

Uses ChromaDB in embedded mode with the default Sentence Transformers
embedding model (all-MiniLM-L6-v2 via ONNX). No external server or
additional API keys required.

Three collections:
  - product_knowledge: Product features, specs, benefits, case studies (~20 chunks)
  - company_facts: Structured facts extracted from web pages during research
  - outreach_history: Past pipeline runs for referencing similar engagements

Falls back to keyword-based search if ChromaDB is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from models import CompanyFact

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHROMA_DIR = str(PROJECT_ROOT / "chroma_data")
_SEED_VERSION_FILE = PROJECT_ROOT / "chroma_data" / ".seed_version"


def _config_hash() -> str:
    """Hash the product + company YAML configs to detect changes."""
    config_dir = PROJECT_ROOT / "config"
    hasher = hashlib.md5()
    for name in ("company.yaml", "products.yaml"):
        path = config_dir / name
        if path.exists():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()[:12]


class VectorKnowledgeStore:
    """ChromaDB-backed vector knowledge store with semantic search."""

    def __init__(self, persist_dir: str | None = None):
        self._persist_dir = persist_dir or CHROMA_DIR
        self._client = None
        self._product_col = None
        self._facts_col = None
        self._outreach_col = None
        self._ready = False

    def initialize(self) -> str:
        """Initialize ChromaDB client and seed product knowledge.

        Returns a status string describing what was loaded.
        """
        import chromadb

        os.makedirs(self._persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(path=self._persist_dir)

        self._product_col = self._client.get_or_create_collection(
            name="product_knowledge",
            metadata={"description": "Product features, specs, case studies, ideal customer"},
        )
        self._facts_col = self._client.get_or_create_collection(
            name="company_facts",
            metadata={"description": "Extracted facts from web pages"},
        )
        self._outreach_col = self._client.get_or_create_collection(
            name="outreach_history",
            metadata={"description": "Past pipeline runs"},
        )

        # Seed product knowledge if needed
        product_count = self._product_col.count()
        newly_seeded = 0
        current_hash = _config_hash()

        needs_seed = product_count == 0
        if not needs_seed and _SEED_VERSION_FILE.exists():
            stored_hash = _SEED_VERSION_FILE.read_text().strip()
            if stored_hash != current_hash:
                needs_seed = True

        if needs_seed:
            newly_seeded = self._seed_product_knowledge()
            _SEED_VERSION_FILE.write_text(current_hash)

        product_count = self._product_col.count()
        facts_count = self._facts_col.count()
        outreach_count = self._outreach_col.count()
        self._ready = True

        status = (
            f"RAG initialized: {product_count} product chunks, "
            f"{facts_count} facts, {outreach_count} outreach records"
        )
        if newly_seeded:
            status += f" ({newly_seeded} newly seeded)"

        logger.info(status)
        return status

    def _seed_product_knowledge(self) -> int:
        """Build semantic chunks from YAML config and upsert into ChromaDB.

        Returns the number of chunks seeded.
        """
        try:
            from knowledge.product_loader import COMPANY_CONFIG, PRODUCTS_CONFIG
        except Exception:
            return 0

        # Clear existing product knowledge for re-seeding
        existing = self._product_col.get()
        if existing["ids"]:
            self._product_col.delete(ids=existing["ids"])

        chunks: list[dict] = []
        products = PRODUCTS_CONFIG
        combo = products["combined_solution"]
        icp = products["ideal_customer"]
        case_studies = products["case_studies"]

        # Company profile
        chunks.append({
            "id": "company_profile",
            "text": (
                f"Company Profile: {COMPANY_CONFIG['name']} — "
                f"{COMPANY_CONFIG.get('industry', '')}. "
                f"Based in {COMPANY_CONFIG.get('location', '')}. "
                f"{COMPANY_CONFIG.get('short_description', '')}"
            ),
            "category": "company",
        })

        # Product chunks — multiple focused chunks per product
        for product_key, product in products["products"].items():
            name = product["name"]

            # Overview chunk
            chunks.append({
                "id": f"{product_key}_overview",
                "text": (
                    f"{name} — {product['tagline']}. "
                    f"{product['description'].strip()} "
                    f"Best for: {', '.join(product['best_for'])}"
                ),
                "category": product_key,
            })

            # Features chunk
            chunks.append({
                "id": f"{product_key}_features",
                "text": f"{name} Key Features: " + ". ".join(product["key_features"]),
                "category": product_key,
            })

            # Functions chunk
            if isinstance(product.get("key_functions"), list):
                chunks.append({
                    "id": f"{product_key}_functions",
                    "text": f"{name} Key Functions: " + ". ".join(product["key_functions"]),
                    "category": product_key,
                })
            elif isinstance(product.get("key_functions"), dict):
                funcs = ". ".join(f"{k}: {v}" for k, v in product["key_functions"].items())
                chunks.append({
                    "id": f"{product_key}_functions",
                    "text": f"{name} Functions: {funcs}",
                    "category": product_key,
                })

            # Benefits chunk
            if "expected_benefits" in product:
                chunks.append({
                    "id": f"{product_key}_benefits",
                    "text": f"{name} Expected Benefits: " + ". ".join(product["expected_benefits"]),
                    "category": product_key,
                })
            if "implementation_benefits" in product:
                benefits = ". ".join(f"{k}: {v}" for k, v in product["implementation_benefits"].items())
                chunks.append({
                    "id": f"{product_key}_impl_benefits",
                    "text": f"{name} Implementation Benefits: {benefits}",
                    "category": product_key,
                })

            # Specs chunk (hardware only)
            if "specs" in product:
                specs = ". ".join(f"{k}: {v}" for k, v in product["specs"].items())
                chunks.append({
                    "id": f"{product_key}_specs",
                    "text": f"{name} Hardware Specifications: {specs}",
                    "category": product_key,
                })

        # Combined solution
        chunks.append({
            "id": "combined_solution",
            "text": (
                f"Combined Solution: {combo['name']}. "
                f"{combo['description'].strip()} "
                f"Synergies: " + ". ".join(combo["synergies"])
            ),
            "category": "combined",
        })

        # Ideal customer profile
        chunks.append({
            "id": "ideal_customer",
            "text": (
                f"Ideal Customer — Industry: {icp['industry']}. "
                f"Factory size: {icp['factory_size']}. "
                f"Pain points: " + ". ".join(icp["pain_points"])
            ),
            "category": "sales",
        })

        # ROI data
        roi = ". ".join(f"{k}: {v}" for k, v in icp["typical_roi"].items())
        chunks.append({
            "id": "typical_roi",
            "text": f"Typical ROI for ideal customers: {roi}",
            "category": "sales",
        })

        # Case studies — one chunk per study
        for i, cs in enumerate(case_studies):
            chunks.append({
                "id": f"case_study_{i}",
                "text": (
                    f"Case Study: {cs['title']}. "
                    f"Solution: {cs['solution']}. "
                    f"Result: {cs['result']}. "
                    f"Tags: {', '.join(cs['tags'])}."
                ),
                "category": "case_study",
            })

        # Upsert all chunks
        self._product_col.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[{"category": c["category"], "source": "knowledge"} for c in chunks],
        )

        return len(chunks)

    def add_facts(self, facts: list[CompanyFact], company_name: str = "") -> int:
        """Add extracted company facts to the vector store.

        Returns the number of facts added.
        """
        if not self._ready or not facts:
            return 0

        ids = []
        documents = []
        metadatas = []

        for i, fact in enumerate(facts):
            fact_id = hashlib.md5(
                f"{company_name}:{fact.category}:{fact.text}".encode()
            ).hexdigest()[:16]

            ids.append(f"fact_{fact_id}")
            documents.append(fact.text)
            metadatas.append({
                "category": fact.category,
                "source": "extraction",
                "source_url": fact.source_url,
                "confidence": fact.confidence,
                "company": company_name,
            })

        self._facts_col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def add_outreach(self, data: dict) -> str:
        """Index a completed pipeline run for future reference.

        Returns the outreach record ID.
        """
        if not self._ready:
            return ""

        company = data.get("company", data.get("target_company", "unknown"))
        outreach_id = hashlib.md5(
            f"{company}:{data.get('timestamp', '')}".encode()
        ).hexdigest()[:16]

        # Build a rich text representation for embedding
        parts = [f"Past outreach to {company}."]
        if "industry" in data:
            parts.append(f"Industry: {data['industry']}.")
        if "deal_category" in data:
            parts.append(f"Deal category: {data['deal_category']}.")
        if "recommended_solution" in data:
            parts.append(f"Solution: {data['recommended_solution']}.")
        if "research_brief" in data:
            brief = data["research_brief"]
            if len(brief) > 800:
                brief = brief[:800] + "..."
            parts.append(f"Research: {brief}")
        if "pain_points" in data:
            parts.append(f"Pain points: {', '.join(data['pain_points'])}.")

        text = " ".join(parts)

        metadata = {
            "category": "past_outreach",
            "source": "outreach",
            "company": company,
        }
        for key in ("industry", "deal_category", "timestamp", "recommended_solution"):
            if key in data:
                metadata[key] = str(data[key])

        self._outreach_col.upsert(
            ids=[f"outreach_{outreach_id}"],
            documents=[text],
            metadatas=[metadata],
        )

        return outreach_id

    def query(
        self,
        query: str,
        n_results: int = 5,
        categories: list[str] | None = None,
        include_sources: bool = True,
    ) -> list[dict]:
        """Semantic search across all collections.

        Args:
            query: Natural language search query.
            n_results: Max results to return.
            categories: Optional filter by category (e.g., ["hardware", "case_study"]).
            include_sources: If True, search all collections. If False, only product_knowledge.

        Returns:
            List of dicts with keys: text, category, source, distance, id.
            Sorted by relevance (lowest distance = best match).
        """
        if not self._ready:
            return []

        all_results: list[dict] = []

        # Build where filter for category
        where_filter = None
        if categories:
            if len(categories) == 1:
                where_filter = {"category": categories[0]}
            else:
                where_filter = {"category": {"$in": categories}}

        # Search product knowledge
        product_count = self._product_col.count()
        if product_count > 0:
            n = min(n_results, product_count)
            try:
                results = self._product_col.query(
                    query_texts=[query],
                    n_results=n,
                    where=where_filter,
                )
                all_results.extend(self._format_results(results, "knowledge"))
            except Exception:
                # where filter may not match — retry without filter
                if where_filter:
                    results = self._product_col.query(
                        query_texts=[query],
                        n_results=n,
                    )
                    all_results.extend(self._format_results(results, "knowledge"))

        if include_sources:
            # Search company facts
            facts_count = self._facts_col.count()
            if facts_count > 0:
                n = min(n_results, facts_count)
                results = self._facts_col.query(
                    query_texts=[query],
                    n_results=n,
                )
                all_results.extend(self._format_results(results, "extraction"))

            # Search outreach history
            outreach_count = self._outreach_col.count()
            if outreach_count > 0:
                n = min(n_results, outreach_count)
                results = self._outreach_col.query(
                    query_texts=[query],
                    n_results=n,
                )
                all_results.extend(self._format_results(results, "outreach"))

        # Sort by distance (lowest = most relevant) and return top n
        all_results.sort(key=lambda x: x["distance"])
        return all_results[:n_results]

    def _format_results(self, results: dict, default_source: str) -> list[dict]:
        """Convert ChromaDB query results to a flat list of dicts."""
        formatted = []
        if not results or not results.get("documents"):
            return formatted

        documents = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(documents)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(documents)
        ids = results["ids"][0] if results.get("ids") else [""] * len(documents)

        for doc, meta, dist, doc_id in zip(documents, metadatas, distances, ids):
            formatted.append({
                "text": doc,
                "category": meta.get("category", "unknown"),
                "source": meta.get("source", default_source),
                "distance": dist,
                "id": doc_id,
                **{k: v for k, v in meta.items() if k not in ("category", "source")},
            })

        return formatted

    def get_formatted_results(self, query: str, n_results: int = 5) -> str:
        """Get formatted results string for agent consumption."""
        results = self.query(query, n_results)
        if not results:
            return "No relevant results found."

        parts = []
        for i, record in enumerate(results):
            source = record.get("source", "unknown")
            category = record.get("category", "unknown")
            text = record.get("text", "")
            distance = record.get("distance", 0)
            similarity = max(0, 1 - distance / 2)  # Normalize to 0-1 range
            parts.append(
                f"[Result {i + 1}] (source: {source}, category: {category}, "
                f"relevance: {similarity:.0%})\n{text}"
            )

        return "\n\n".join(parts)

    def get_collection_stats(self) -> dict:
        """Return counts per collection."""
        if not self._ready:
            return {"product_knowledge": 0, "company_facts": 0, "outreach_history": 0}
        return {
            "product_knowledge": self._product_col.count(),
            "company_facts": self._facts_col.count(),
            "outreach_history": self._outreach_col.count(),
        }


# ── Singleton + fallback ──

_store: VectorKnowledgeStore | None = None


def get_knowledge_store() -> VectorKnowledgeStore | None:
    """Get or create the singleton knowledge store.

    Returns None if ChromaDB is unavailable.
    """
    global _store
    if _store is not None:
        return _store

    try:
        _store = VectorKnowledgeStore()
        _store.initialize()
        return _store
    except Exception as e:
        logger.warning(f"ChromaDB unavailable, falling back to keyword search: {e}")
        return None


# ── Legacy compatibility ──


class KnowledgeStore:
    """Backward-compatible wrapper.

    Delegates to VectorKnowledgeStore if ChromaDB is available,
    otherwise falls back to keyword-based search.
    """

    def __init__(self, store_dir=None):
        self._vector_store = None
        self._fallback_chunks: list[dict] = []
        try:
            self._vector_store = VectorKnowledgeStore(
                persist_dir=str(store_dir) if store_dir else None
            )
            self._vector_store.initialize()
        except Exception:
            self._build_fallback_chunks()

    def _build_fallback_chunks(self):
        """Build keyword-searchable chunks as fallback."""
        try:
            from knowledge.product_loader import COMPANY_CONFIG, PRODUCTS_CONFIG

            products = PRODUCTS_CONFIG
            self._fallback_chunks = [
                {"category": "company", "source": "knowledge",
                 "text": f"Company profile: {COMPANY_CONFIG['name']} — {COMPANY_CONFIG.get('industry', '')}"},
            ]
            for product_key, product in products["products"].items():
                name = product["name"]
                self._fallback_chunks.append(
                    {"category": product_key, "source": "knowledge",
                     "text": f"{name} — {product['tagline']}. {product['description'].strip()}"})
        except Exception:
            pass

    def load(self):
        """No-op for backward compatibility (ChromaDB loads on init)."""
        pass

    def query(self, query: str, n_results: int = 5) -> list[dict]:
        if self._vector_store:
            return self._vector_store.query(query, n_results)
        return self._keyword_search(query, n_results)

    def add_facts(self, facts, company_name: str = ""):
        if self._vector_store:
            self._vector_store.add_facts(facts, company_name)

    def add_outreach(self, data: dict):
        if self._vector_store:
            self._vector_store.add_outreach(data)

    def get_formatted_results(self, query: str, n_results: int = 3) -> str:
        if self._vector_store:
            return self._vector_store.get_formatted_results(query, n_results)
        results = self._keyword_search(query, n_results)
        if not results:
            return "No relevant results found."
        parts = []
        for i, record in enumerate(results):
            parts.append(f"[Result {i + 1}] ({record.get('source', 'unknown')})\n{record.get('text', '')}")
        return "\n\n".join(parts)

    def _keyword_search(self, query: str, n_results: int) -> list[dict]:
        """Fallback keyword-based search."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []
        for chunk in self._fallback_chunks:
            text_lower = chunk.get("text", "").lower()
            score = 0
            if query_lower in text_lower:
                score += 10
            for word in query_words:
                if len(word) > 2 and word in text_lower:
                    score += 1
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:n_results]]
