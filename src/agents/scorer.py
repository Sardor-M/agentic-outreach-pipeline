"""
Scorer Agent — Deal sizing and quick summary.

Single-turn agent that produces structured DealEstimate JSON
and optionally a quick fit assessment summary.
"""

from __future__ import annotations

import json
import re

from agents.base import SingleTurnAgent, StreamCallback
from models import AgentResult, AgentRole, ContextPacket, DealEstimate


class ScorerAgent(SingleTurnAgent):
    role = AgentRole.SCORER
    prompt_file = "scorer.md"
    temperature = 0.3

    def execute(self, context: ContextPacket, on_event: StreamCallback = None) -> AgentResult:
        """Execute and parse the JSON output into DealEstimate."""
        result = super().execute(context, on_event=on_event)
        if not result.success:
            return result

        deal = self._parse_deal_json(result.raw_text)
        result.output = deal.model_dump()

        return result

    def _parse_deal_json(self, raw: str) -> DealEstimate:
        """Safely parse deal estimator JSON output."""
        text = raw.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = "\n".join(text.split("\n")[:-1])
        text = text.strip()

        try:
            data = json.loads(text)
            return DealEstimate(**data)
        except (json.JSONDecodeError, Exception):
            # Try to extract JSON from the text
            json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return DealEstimate(**data)
                except (json.JSONDecodeError, Exception):
                    pass

            return DealEstimate(
                company_name="Unknown",
                reasoning=f"Could not parse: {raw[:100]}",
            )


class QuickSummaryMixin:
    """Mixin for generating quick fit assessments (used by orchestrator)."""

    QUICK_SUMMARY_PROMPT = """You are a B2B sales analyst.
Given a brief company description and a deal estimate, produce a concise fit assessment
(3-8 sentences) covering: what the company does, why they are a fit for our products,
the estimated deal size, and a recommended next step.

Be specific. Do NOT repeat the deal JSON — summarize it naturally.
Output plain text only, no markdown headers."""
