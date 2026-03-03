"""
Knowledge Query Tool — Query the structured JSON knowledge store.

Replaces the old ChromaDB RAG query with field-based querying over
the JSON knowledge store.
"""

from __future__ import annotations

from tools.base import BaseTool


class KnowledgeQueryTool(BaseTool):
    name = "query_knowledge_base"
    description = (
        "Search the internal knowledge base. Contains product information, "
        "case studies, ideal customer profiles, ROI data, and records of past "
        "outreach to other companies. Use this to find relevant product features, "
        "similar past deals, and case studies."
    )

    def __init__(self):
        super().__init__()
        self._store = None

    @property
    def store(self):
        if self._store is None:
            try:
                from knowledge.store import KnowledgeStore

                self._store = KnowledgeStore()
                self._store.load()
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
                        "Search query. E.g., 'energy monitoring for forging companies' "
                        "or 'past outreach automotive stamping'."
                    ),
                },
            },
            "required": ["query"],
        }

    def _execute(self, query: str = "") -> str:
        if not query:
            return "Error: No query provided."

        if self.store is None:
            # Fallback: return product info from YAML config
            return self._fallback_query(query)

        results = self.store.query(query)
        if not results:
            return self._fallback_query(query)

        parts = []
        for i, record in enumerate(results[:5]):
            category = record.get("category", "unknown")
            text = record.get("text", "")
            source = record.get("source", "knowledge")
            parts.append(f"[Result {i + 1}] (source: {source}, category: {category})\n{text}")

        return "\n\n".join(parts)

    def _fallback_query(self, query: str) -> str:
        """Fallback to product loader when knowledge store isn't available."""
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
