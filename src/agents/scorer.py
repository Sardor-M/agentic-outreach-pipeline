"""
Scorer Agent — Deal sizing with structured tool output.

Uses Claude's tool_choice to guarantee valid JSON output
matching the DealEstimate schema.
"""

from __future__ import annotations

from agents.base import FALLBACK_MODEL, BaseAgent, StreamCallback
from models import AgentResult, AgentRole, ContextPacket, DealEstimate

DEAL_ESTIMATE_TOOL = {
    "name": "submit_deal_estimate",
    "description": "Submit the structured deal estimate for this prospect.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company_name": {"type": "string", "description": "Name of the target company"},
            "industry": {"type": "string", "description": "Company's industry"},
            "estimated_machines": {"type": "integer", "description": "Estimated number of machines"},
            "recommended_solution": {
                "type": "string",
                "enum": ["Hardware only", "Software only", "Hardware + Software"],
            },
            "first_year_value": {"type": "number", "description": "Estimated first-year deal value in USD"},
            "annual_recurring": {"type": "number", "description": "Estimated annual recurring revenue in USD"},
            "deal_category": {
                "type": "string",
                "enum": ["Small", "Medium", "Enterprise"],
            },
            "confidence": {
                "type": "string",
                "enum": ["Low", "Medium", "High"],
            },
            "reasoning": {"type": "string", "description": "1-2 sentence explanation of the estimate"},
        },
        "required": [
            "company_name", "industry", "estimated_machines",
            "recommended_solution", "first_year_value", "annual_recurring",
            "deal_category", "confidence", "reasoning",
        ],
    },
}


class ScorerAgent(BaseAgent):
    role = AgentRole.SCORER
    prompt_file = "scorer.md"
    temperature = 0.3
    fallback_model = FALLBACK_MODEL

    def execute(self, context: ContextPacket, on_event: StreamCallback = None) -> AgentResult:
        """Execute with forced tool use for guaranteed structured output."""
        system_prompt = self.build_system_prompt(context)
        user_message = self.build_user_message(context)

        response, tokens_in, tokens_out = self._api_call(
            system_prompt,
            [{"role": "user", "content": user_message}],
            tools=[DEAL_ESTIMATE_TOOL],
            tool_choice={"type": "tool", "name": "submit_deal_estimate"},
            on_event=on_event,
        )

        # Extract structured input directly from tool use block
        for block in response.content:
            if block.type == "tool_use":
                deal = DealEstimate(**block.input)
                return AgentResult(
                    agent=self.role,
                    success=True,
                    output=deal.model_dump(),
                    raw_text=str(block.input),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )

        return AgentResult(
            agent=self.role,
            success=False,
            error="No tool use block in response",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
