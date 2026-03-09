"""
Knowledge Query Tool — Semantic search over the ChromaDB vector knowledge store.

Provides agents with access to product knowledge, case studies,
ideal customer profiles, extracted company facts, and past outreach history
via vector similarity search (embeddings).

Falls back to keyword search over product config if ChromaDB is unavailable.
"""

from __future__ import annotations

from tools.base import BaseTool


class KnowledgeQueryTool(BaseTool):
    name = "query_knowledge_base"
    description = (
        "Search the internal knowledge base using semantic similarity. "
        "Contains product information (features, specs, benefits), "
        "case studies, ideal customer profiles, ROI data, and records of past "
        "outreach to other companies. Use this to find relevant product features, "
        "similar past deals, and case studies that match the prospect's situation."
    )

    def __init__(self):
        super().__init__()
        self._store = None
        self._initialized = False

    @property
    def store(self):
        if not self._initialized:
            self._initialized = True
            try:
                from knowledge.store import get_knowledge_store

                self._store = get_knowledge_store()
            except Exception:
                pass
        return self._store

    def _input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language search query. The knowledge base uses "
                        "semantic similarity, so describe what you're looking for "
                        "in plain language. E.g., 'energy monitoring for forging companies', "
                        "'past outreach to automotive stamping manufacturers', "
                        "'defect detection case studies', or 'ROI data for medium factories'."
                    ),
                },
            },
            "required": ["query"],
        }

    def _execute(self, query: str = "") -> str:
        if not query:
            return "Error: No query provided."

        if self.store is not None:
            results = self.store.query(query)
            if results:
                return self._format_vector_results(results)

        # Fallback: product context with keyword filtering
        return self._fallback_query(query)

    def _format_vector_results(self, results: list[dict]) -> str:
        """Format ChromaDB vector search results for agent consumption."""
        parts = []
        for i, record in enumerate(results[:5]):
            category = record.get("category", "unknown")
            text = record.get("text", "")
            source = record.get("source", "knowledge")
            distance = record.get("distance", 0)
            similarity = max(0, 1 - distance / 2)  # Normalize to 0-1 range

            parts.append(
                f"[Result {i + 1}] (source: {source}, category: {category}, "
                f"relevance: {similarity:.0%})\n{text}"
            )

        return "\n\n".join(parts)

    def _fallback_query(self, query: str) -> str:
        """Fallback to product loader when vector store isn't available."""
        from knowledge.product_loader import get_full_product_context

        context = get_full_product_context()

        # Simple keyword search within the product context
        query_lower = query.lower()
        relevant_sections = []
        current_section = ""

        for line in context.split("\n"):
            if line.startswith("==="):
                if current_section and any(kw in current_section.lower() for kw in query_lower.split()):
                    relevant_sections.append(current_section.strip())
                current_section = line + "\n"
            else:
                current_section += line + "\n"

        # Check last section
        if current_section and any(kw in current_section.lower() for kw in query_lower.split()):
            relevant_sections.append(current_section.strip())

        if relevant_sections:
            return "\n\n".join(relevant_sections[:3])

        # If no keyword match, return full context (truncated)
        if len(context) > 2000:
            return context[:2000] + "\n\n[...truncated]"
        return context
