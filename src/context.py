"""
Context Budget Manager

Solves context rot by:
1. Summarizing tool results to ~800 tokens instead of blind truncation
2. Pruning message history when it exceeds budget (keep first + last 2 turns)
3. Summarizing agent outputs for handoff to downstream agents (~1500 tokens)
4. Building curated ContextPackets per agent (not raw text dumps)

Uses tiktoken for token counting, Claude Haiku for fast summarization.
"""

from __future__ import annotations

from pathlib import Path

import tiktoken
from anthropic import Anthropic
from dotenv import load_dotenv

from models import ContextPacket

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Token counting
_encoding = tiktoken.get_encoding("cl100k_base")

# Summarization model (fast + cheap)
SUMMARIZE_MODEL = "claude-haiku-4-5-20251001"
SUMMARIZE_MAX_TOKENS = 1024


def count_tokens(text: str) -> int:
    """Count tokens in a string using tiktoken."""
    return len(_encoding.encode(text))


def count_messages_tokens(messages: list[dict]) -> int:
    """Approximate token count for a list of Claude API messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += count_tokens(block.get("text", "") or block.get("content", "") or "")
                elif hasattr(block, "text"):
                    total += count_tokens(block.text or "")
    return total


class ContextManager:
    """Manages context budgets and summarization for the pipeline."""

    def __init__(
        self,
        max_tool_result_tokens: int = 800,
        max_handoff_tokens: int = 1500,
        max_history_tokens: int = 8000,
    ):
        self.max_tool_result_tokens = max_tool_result_tokens
        self.max_handoff_tokens = max_handoff_tokens
        self.max_history_tokens = max_history_tokens
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            self._client = Anthropic()
        return self._client

    def _summarize(self, text: str, instruction: str, max_tokens: int = SUMMARIZE_MAX_TOKENS) -> str:
        """Use Claude Haiku to summarize text."""
        try:
            response = self.client.messages.create(
                model=SUMMARIZE_MODEL,
                max_tokens=max_tokens,
                temperature=0.0,
                messages=[
                    {
                        "role": "user",
                        "content": f"{instruction}\n\n---\n{text}",
                    }
                ],
            )
            return response.content[0].text
        except Exception:
            # Fallback to truncation if summarization fails
            tokens = count_tokens(text)
            if tokens > max_tokens * 4:
                # Rough char estimate: ~4 chars per token
                return text[: max_tokens * 4] + "\n\n[...truncated]"
            return text

    def summarize_tool_result(self, tool_name: str, result: str) -> str:
        """Summarize a tool result to fit within token budget.

        Instead of blindly truncating at 3000 chars, we LLM-summarize
        to ~800 tokens, preserving the most useful information.
        """
        tokens = count_tokens(result)
        if tokens <= self.max_tool_result_tokens:
            return result

        return self._summarize(
            result,
            (
                f"Summarize this {tool_name} result in a concise format. "
                f"Keep the most important facts, numbers, company names, and URLs. "
                f"Remove boilerplate and repetition. Be factual and specific."
            ),
            max_tokens=self.max_tool_result_tokens,
        )

    def summarize_for_handoff(self, agent_output: str, target_agent: str) -> str:
        """Summarize an agent's output for the specific downstream agent.

        Instead of passing raw text between agents, we create a focused
        summary (~1500 tokens) tailored to what the downstream agent needs.
        """
        tokens = count_tokens(agent_output)
        if tokens <= self.max_handoff_tokens:
            return agent_output

        return self._summarize(
            agent_output,
            (
                f"Summarize this for a downstream {target_agent} agent. "
                f"Keep all key findings, pain points, numbers, company details, "
                f"and actionable insights. Remove verbose explanations. "
                f"Output a concise, structured summary."
            ),
            max_tokens=self.max_handoff_tokens,
        )

    def prune_messages(self, messages: list[dict]) -> list[dict]:
        """Prune message history when it exceeds token budget.

        Strategy: Keep first message (task) + last 2 turns. Summarize
        the middle turns into a single context message.
        """
        total = count_messages_tokens(messages)
        if total <= self.max_history_tokens:
            return messages

        if len(messages) <= 4:
            return messages

        # Keep first message and last 2 pairs
        first = messages[0]
        middle = messages[1:-4]
        last = messages[-4:]

        if not middle:
            return messages

        # Summarize middle turns
        middle_text = ""
        for msg in middle:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str):
                middle_text += f"\n[{role}]: {content[:500]}"
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        middle_text += f"\n[{role}]: {block.get('content', '')[:300]}"

        summary = self._summarize(
            middle_text,
            "Summarize this conversation history concisely. Keep key facts and tool results.",
            max_tokens=600,
        )

        return [
            first,
            {"role": "user", "content": f"[Previous research summary]: {summary}"},
            {"role": "assistant", "content": "I'll continue the research with this context."},
            *last,
        ]

    def build_context_packet(
        self,
        task_description: str,
        relevant_data: dict,
        prior_summaries: list[str] | None = None,
        company_config: dict | None = None,
        token_budget: int = 3000,
    ) -> ContextPacket:
        """Build a curated ContextPacket for a sub-agent."""
        return ContextPacket(
            task_description=task_description,
            relevant_data=relevant_data,
            summaries=prior_summaries or [],
            token_budget=token_budget,
            company_config=company_config or {},
        )
