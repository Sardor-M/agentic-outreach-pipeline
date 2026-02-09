"""
RAG Knowledge Base — ChromaDB vector store for product knowledge + past outreach

Indexes:
1. Product knowledge from knowledge.py (chunked semantically)
2. Past outreach JSON files from outputs/

Provides semantic search via query_knowledge_base().
"""

import os
import json
import glob
from pathlib import Path

from knowledge import (
    COMPANY_PROFILE,
    MV900_KNOWLEDGE,
    MACHINE365_KNOWLEDGE,
    COMBINED_SOLUTION,
    CASE_STUDIES,
)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = str(PROJECT_ROOT / "chroma_data")
OUTPUTS_DIR = str(PROJECT_ROOT / "outputs")

COLLECTION_NAME = "3view_knowledge"

# Module-level reference to ChromaDB collection
_collection = None


def _build_product_chunks() -> list[dict]:
    """Break product knowledge into semantic chunks for indexing."""
    chunks = []

    # Company profile
    chunks.append({
        "id": "company_profile",
        "text": f"3View Company Profile: {COMPANY_PROFILE.strip()}",
        "metadata": {"source": "knowledge", "category": "company"},
    })

    # MV900 overview
    chunks.append({
        "id": "mv900_overview",
        "text": (
            f"MV900 — {MV900_KNOWLEDGE['tagline']}. "
            f"{MV900_KNOWLEDGE['description']} "
            f"Category: {MV900_KNOWLEDGE['category']}. "
            f"Best for: {', '.join(MV900_KNOWLEDGE['best_for'])}."
        ),
        "metadata": {"source": "knowledge", "category": "mv900"},
    })

    # MV900 features
    chunks.append({
        "id": "mv900_features",
        "text": (
            "MV900 Key Features: "
            + ". ".join(MV900_KNOWLEDGE["key_features"])
        ),
        "metadata": {"source": "knowledge", "category": "mv900"},
    })

    # MV900 functions
    chunks.append({
        "id": "mv900_functions",
        "text": (
            "MV900 Key Functions: "
            + ". ".join(MV900_KNOWLEDGE["key_functions"])
        ),
        "metadata": {"source": "knowledge", "category": "mv900"},
    })

    # MV900 benefits
    chunks.append({
        "id": "mv900_benefits",
        "text": (
            "MV900 Expected Benefits: "
            + ". ".join(MV900_KNOWLEDGE["expected_benefits"])
        ),
        "metadata": {"source": "knowledge", "category": "mv900"},
    })

    # MV900 specs
    specs_str = ", ".join(
        f"{k}: {v}" for k, v in MV900_KNOWLEDGE["specs"].items()
    )
    chunks.append({
        "id": "mv900_specs",
        "text": f"MV900 Hardware Specifications: {specs_str}",
        "metadata": {"source": "knowledge", "category": "mv900"},
    })

    # Machine365.Ai overview
    chunks.append({
        "id": "machine365_overview",
        "text": (
            f"Machine365.Ai — {MACHINE365_KNOWLEDGE['tagline']}. "
            f"{MACHINE365_KNOWLEDGE['description']} "
            f"Category: {MACHINE365_KNOWLEDGE['category']}. "
            f"Best for: {', '.join(MACHINE365_KNOWLEDGE['best_for'])}."
        ),
        "metadata": {"source": "knowledge", "category": "machine365"},
    })

    # Machine365 features
    chunks.append({
        "id": "machine365_features",
        "text": (
            "Machine365.Ai Key Features: "
            + ". ".join(MACHINE365_KNOWLEDGE["key_features"])
        ),
        "metadata": {"source": "knowledge", "category": "machine365"},
    })

    # Machine365 functions — group them into one chunk
    funcs_text = ". ".join(
        f"{k}: {v}"
        for k, v in MACHINE365_KNOWLEDGE["key_functions"].items()
    )
    chunks.append({
        "id": "machine365_functions",
        "text": f"Machine365.Ai Key Functions: {funcs_text}",
        "metadata": {"source": "knowledge", "category": "machine365"},
    })

    # Machine365 implementation benefits
    benefits_text = ". ".join(
        f"{k}: {v}"
        for k, v in MACHINE365_KNOWLEDGE["implementation_benefits"].items()
    )
    chunks.append({
        "id": "machine365_benefits",
        "text": f"Machine365.Ai Implementation Benefits: {benefits_text}",
        "metadata": {"source": "knowledge", "category": "machine365"},
    })

    # Combined solution
    synergies = ". ".join(COMBINED_SOLUTION["synergies"])
    chunks.append({
        "id": "combined_solution",
        "text": (
            f"Combined MV900 + Machine365.Ai Solution: "
            f"{COMBINED_SOLUTION['description']} "
            f"Synergies: {synergies}"
        ),
        "metadata": {"source": "knowledge", "category": "combined"},
    })

    # Ideal customer profile + ROI
    pain_points = ". ".join(
        COMBINED_SOLUTION["ideal_customer_profile"]["pain_points"]
    )
    roi_text = ". ".join(
        f"{k}: {v}"
        for k, v in COMBINED_SOLUTION["ideal_customer_profile"]["typical_roi"].items()
    )
    chunks.append({
        "id": "ideal_customer",
        "text": (
            f"Ideal Customer Profile — "
            f"Industry: {COMBINED_SOLUTION['ideal_customer_profile']['industry']}. "
            f"Factory size: {COMBINED_SOLUTION['ideal_customer_profile']['factory_size']}. "
            f"Pain points: {pain_points}. "
            f"Typical ROI: {roi_text}."
        ),
        "metadata": {"source": "knowledge", "category": "sales"},
    })

    # Case studies — one chunk per study
    for i, cs in enumerate(CASE_STUDIES):
        chunks.append({
            "id": f"case_study_{i}",
            "text": (
                f"Case Study: {cs['title']}. "
                f"Solution: {cs['solution']}. "
                f"Result: {cs['result']}. "
                f"Tags: {', '.join(cs['tags'])}."
            ),
            "metadata": {"source": "knowledge", "category": "case_study"},
        })

    return chunks


def _load_outreach_chunks() -> list[dict]:
    """Load past outreach JSON files from outputs/ and create chunks."""
    chunks = []
    pattern = os.path.join(OUTPUTS_DIR, "outreach_*.json")

    for filepath in glob.glob(pattern):
        try:
            with open(filepath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        query = data.get("query", "unknown")
        timestamp = data.get("timestamp", "unknown")

        for j, prospect in enumerate(data.get("prospects", [])):
            company = prospect.get("company", "Unknown")
            industry = prospect.get("deal_estimate", {}).get("industry", "Unknown")
            deal_cat = prospect.get("deal_estimate", {}).get("deal_category", "Unknown")
            brief = prospect.get("research_brief", "")
            sent = prospect.get("sent", False)

            # Truncate brief to keep chunks reasonable
            if len(brief) > 800:
                brief = brief[:800] + "..."

            chunk_id = f"outreach_{timestamp}_{j}"
            text = (
                f"Past outreach to {company}. "
                f"Industry: {industry}. Deal category: {deal_cat}. "
                f"Email sent: {sent}. Search query: {query}. "
                f"Research brief: {brief}"
            )
            chunks.append({
                "id": chunk_id,
                "text": text,
                "metadata": {
                    "source": "outreach",
                    "category": "past_outreach",
                    "company": company,
                    "timestamp": timestamp,
                },
            })

    return chunks


def initialize(force_rebuild: bool = False) -> str:
    """
    Build or update the ChromaDB knowledge base.

    Returns a status message string.
    """
    global _collection

    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if force_rebuild:
        # Delete and recreate
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Check what's already indexed
    existing = _collection.get()
    existing_ids = set(existing["ids"]) if existing["ids"] else set()

    # Build all chunks
    product_chunks = _build_product_chunks()
    outreach_chunks = _load_outreach_chunks()
    all_chunks = product_chunks + outreach_chunks

    # Find new chunks to add
    new_chunks = [c for c in all_chunks if c["id"] not in existing_ids]

    if new_chunks:
        _collection.add(
            ids=[c["id"] for c in new_chunks],
            documents=[c["text"] for c in new_chunks],
            metadatas=[c["metadata"] for c in new_chunks],
        )

    total = len(existing_ids) + len(new_chunks)
    return (
        f"RAG initialized: {total} total chunks "
        f"({len(product_chunks)} product, {len(outreach_chunks)} outreach, "
        f"{len(new_chunks)} newly added)"
    )


def query_knowledge_base(query: str, n_results: int = 3) -> str:
    """
    Semantic search over the knowledge base.

    Returns formatted results as a string for the agent.
    """
    global _collection

    if _collection is None:
        return "Knowledge base not initialized. No results available."

    results = _collection.query(
        query_texts=[query],
        n_results=min(n_results, _collection.count()),
    )

    if not results["documents"][0]:
        return "No relevant results found."

    output_parts = []
    for i, (doc, meta) in enumerate(
        zip(results["documents"][0], results["metadatas"][0])
    ):
        source = meta.get("source", "unknown")
        category = meta.get("category", "unknown")
        output_parts.append(
            f"[Result {i+1}] (source: {source}, category: {category})\n{doc}"
        )

    return "\n\n".join(output_parts)


def index_new_outreach(data: dict) -> str:
    """
    Index a new outreach result into the knowledge base.

    Args:
        data: The outreach JSON dict (with 'prospects', 'query', 'timestamp' keys)

    Returns a status message.
    """
    global _collection

    if _collection is None:
        return "Knowledge base not initialized. Skipping indexing."

    query = data.get("query", "unknown")
    timestamp = data.get("timestamp", "unknown")
    indexed = 0

    for j, prospect in enumerate(data.get("prospects", [])):
        company = prospect.get("company", "Unknown")
        industry = prospect.get("deal_estimate", {}).get("industry", "Unknown")
        deal_cat = prospect.get("deal_estimate", {}).get("deal_category", "Unknown")
        brief = prospect.get("research_brief", "")
        sent = prospect.get("sent", False)

        if len(brief) > 800:
            brief = brief[:800] + "..."

        chunk_id = f"outreach_{timestamp}_{j}"
        text = (
            f"Past outreach to {company}. "
            f"Industry: {industry}. Deal category: {deal_cat}. "
            f"Email sent: {sent}. Search query: {query}. "
            f"Research brief: {brief}"
        )

        try:
            _collection.add(
                ids=[chunk_id],
                documents=[text],
                metadatas=[{
                    "source": "outreach",
                    "category": "past_outreach",
                    "company": company,
                    "timestamp": timestamp,
                }],
            )
            indexed += 1
        except Exception:
            pass  # Duplicate ID — already indexed

    return f"Indexed {indexed} new outreach record(s)"
