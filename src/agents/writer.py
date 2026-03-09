"""
Writer Agent — Proposal and cold email generation with structured output.

Uses Claude's tool_choice to guarantee structured proposal + email output.
"""

from __future__ import annotations

from agents.base import BaseAgent, StreamCallback
from models import AgentResult, AgentRole, ContextPacket

PROPOSAL_TOOL = {
    "name": "submit_proposal",
    "description": "Submit the sales proposal and cold email for this prospect.",
    "input_schema": {
        "type": "object",
        "properties": {
            "proposal_markdown": {
                "type": "string",
                "description": "The full sales proposal in Markdown format",
            },
            "email_subject": {
                "type": "string",
                "description": "Subject line for the cold email",
            },
            "email_body": {
                "type": "string",
                "description": "Body of the cold email (plain text, no markdown)",
            },
        },
        "required": ["proposal_markdown", "email_subject", "email_body"],
    },
}


class WriterAgent(BaseAgent):
    role = AgentRole.WRITER
    prompt_file = "writer.md"
    temperature = 0.7

    def execute(self, context: ContextPacket, on_event: StreamCallback = None) -> AgentResult:
        """Execute with forced tool use for guaranteed structured output."""
        system_prompt = self.build_system_prompt(context)
        user_message = self.build_user_message(context)

        response, tokens_in, tokens_out = self._api_call(
            system_prompt,
            [{"role": "user", "content": user_message}],
            tools=[PROPOSAL_TOOL],
            tool_choice={"type": "tool", "name": "submit_proposal"},
            on_event=on_event,
        )

        # Extract structured input directly from tool use block
        for block in response.content:
            if block.type == "tool_use":
                return AgentResult(
                    agent=self.role,
                    success=True,
                    output={
                        "proposal_markdown": block.input.get("proposal_markdown", ""),
                        "email_subject": block.input.get("email_subject", ""),
                        "email_body": block.input.get("email_body", ""),
                    },
                    raw_text=block.input.get("proposal_markdown", ""),
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
