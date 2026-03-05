"""
Writer Agent — Proposal and cold email generation.

Single-turn agent that generates both the sales proposal (Markdown)
and the cold outreach email from the solution map summary.
"""

from __future__ import annotations

import re

from agents.base import SingleTurnAgent, StreamCallback
from models import AgentResult, AgentRole, ContextPacket, ProposalOutput


class WriterAgent(SingleTurnAgent):
    role = AgentRole.WRITER
    prompt_file = "writer.md"
    temperature = 0.7

    def execute(self, context: ContextPacket, on_event: StreamCallback = None) -> AgentResult:
        """Execute and parse the output into proposal + email."""
        result = super().execute(context, on_event=on_event)
        if not result.success:
            return result

        # Parse the raw text to extract proposal and email separately
        raw = result.raw_text
        proposal_output = self._parse_output(raw)

        result.output = {
            "proposal_markdown": proposal_output.proposal_markdown,
            "email_subject": proposal_output.email_subject,
            "email_body": proposal_output.email_body,
        }

        return result

    def _parse_output(self, raw: str) -> ProposalOutput:
        """Split raw output into proposal markdown and email."""
        # Try to find the email section
        # Common markers: "## OUTPUT 2", "Subject:", email section after proposal
        email_markers = [
            r"##\s*OUTPUT\s*2[:\s]*COLD\s*EMAIL",
            r"##\s*Cold\s*Email",
            r"---\s*\n\s*Subject:",
        ]

        proposal = raw
        email_subject = ""
        email_body = ""

        for pattern in email_markers:
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                proposal = raw[: match.start()].strip()
                email_section = raw[match.end() :].strip()

                # Extract subject line
                subj_match = re.match(r"^.*?Subject:\s*(.+?)(?:\n\n|\n)", email_section, re.DOTALL)
                if subj_match:
                    email_subject = subj_match.group(1).strip()
                    email_body = email_section[subj_match.end() :].strip()
                else:
                    email_body = email_section
                break

        # If no split found, check if email is at the end with "Subject:" marker
        if not email_subject:
            subj_match = re.search(r"\nSubject:\s*(.+?)(?:\n\n|\n)", raw)
            if subj_match:
                # Check if this subject line is in the second half of the text
                if subj_match.start() > len(raw) * 0.4:
                    proposal = raw[: subj_match.start()].strip()
                    email_subject = subj_match.group(1).strip()
                    email_body = raw[subj_match.end() :].strip()

        return ProposalOutput(
            proposal_markdown=proposal,
            email_subject=email_subject,
            email_body=email_body,
        )
