"""
Base Agent — Abstract class for all sub-agents.

Each agent:
- Gets a fresh API call with isolated context (no inherited conversation history)
- Receives a ContextPacket (not raw text)
- Returns structured output
- Loads its prompt template from config/agent_prompts/
- Respects token budgets
- Supports streaming via optional on_event callback
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from anthropic import Anthropic, APIError
from dotenv import load_dotenv

from context import ContextManager, count_tokens
from cost_tracker import CostTracker
from logging_config import get_logger
from models import AgentResult, AgentRole, ContextPacket

logger = get_logger(__name__)

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "agent_prompts"
MODEL = "claude-sonnet-4-20250514"
FALLBACK_MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES = 3

# Callback for streaming events: {"type": "text_delta", "agent": "writer", "text": "..."}
StreamCallback = Callable[[dict], None] | None


def _load_prompt_template(filename: str) -> str:
    """Load a prompt template from config/agent_prompts/."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


class BaseAgent(ABC):
    """Abstract base class for all pipeline agents."""

    role: AgentRole
    prompt_file: str  # e.g., "researcher.md"
    temperature: float = 0.7
    max_tokens: int = 4096
    fallback_model: str | None = None

    def __init__(
        self,
        context_manager: ContextManager | None = None,
        cost_tracker: CostTracker | None = None,
    ):
        self.context_manager = context_manager or ContextManager()
        self.cost_tracker = cost_tracker
        self._client: Anthropic | None = None
        self._prompt_template: str | None = None

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            self._client = Anthropic()
        return self._client

    @property
    def prompt_template(self) -> str:
        if self._prompt_template is None:
            self._prompt_template = _load_prompt_template(self.prompt_file)
        return self._prompt_template

    def build_system_prompt(self, context: ContextPacket) -> str:
        """Build the system prompt by filling template placeholders."""
        prompt = self.prompt_template
        if not prompt:
            prompt = self._default_system_prompt(context)

        # Replace common placeholders
        company = context.company_config
        prompt = prompt.replace("{{company_name}}", company.get("name", ""))
        prompt = prompt.replace("{{company_profile}}", company.get("short_description", ""))
        prompt = prompt.replace("{{company_location}}", company.get("location", ""))
        prompt = prompt.replace("{{contact_email}}", company.get("contact", {}).get("email", ""))
        prompt = prompt.replace("{{contact_phone}}", company.get("contact", {}).get("phone", ""))
        prompt = prompt.replace("{{email_signature}}", company.get("email_signature", ""))

        # Product context placeholder (only Architect gets full context)
        if "{{full_product_context}}" in prompt:
            from knowledge.product_loader import get_full_product_context

            prompt = prompt.replace("{{full_product_context}}", get_full_product_context())

        # Pricing guidelines placeholder (for Scorer)
        if "{{pricing_guidelines}}" in prompt:
            pricing = company.get("pricing", {})
            lines = []
            if pricing.get("hardware_unit_range"):
                lines.append(f"- Hardware unit: {pricing['hardware_unit_range']}")
            if pricing.get("software_license_range"):
                lines.append(f"- Software license: {pricing['software_license_range']}")
            if pricing.get("implementation_range"):
                lines.append(f"- Implementation & setup: {pricing['implementation_range']}")
            if pricing.get("annual_support"):
                lines.append(f"- Annual support & maintenance: {pricing['annual_support']}")
            prompt = prompt.replace("{{pricing_guidelines}}", "\n".join(lines) if lines else "See company config.")

        return prompt

    def _default_system_prompt(self, context: ContextPacket) -> str:
        """Fallback system prompt if no template file exists."""
        return f"You are a {self.role.value} agent. {context.task_description}"

    def build_user_message(self, context: ContextPacket) -> str:
        """Build the user message from the context packet."""
        parts = [context.task_description]

        if context.summaries:
            parts.append("\n=== CONTEXT FROM PRIOR AGENTS ===")
            for summary in context.summaries:
                parts.append(summary)

        if context.relevant_data:
            parts.append("\n=== RELEVANT DATA ===")
            for key, value in context.relevant_data.items():
                if isinstance(value, str):
                    parts.append(f"\n--- {key.upper()} ---\n{value}")
                else:
                    import json

                    parts.append(f"\n--- {key.upper()} ---\n{json.dumps(value, indent=2, default=str)}")

        return "\n".join(parts)

    # ── API calls ──

    def _api_call(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        on_event: StreamCallback = None,
    ) -> tuple[Any, int, int]:
        """Make a Claude API call with retry logic and optional streaming.

        When on_event is provided, uses the streaming API and emits text_delta
        events via callback. Returns (response, tokens_in, tokens_out).
        """
        for attempt in range(MAX_RETRIES):
            try:
                kwargs = {
                    "model": MODEL,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "system": system_prompt,
                    "messages": messages,
                }
                if tools:
                    kwargs["tools"] = tools
                if tool_choice:
                    kwargs["tool_choice"] = tool_choice

                if on_event:
                    with self.client.messages.stream(**kwargs) as stream:
                        for event in stream:
                            self._handle_stream_event(event, on_event)
                        response = stream.get_final_message()
                else:
                    response = self.client.messages.create(**kwargs)

                tokens_in = response.usage.input_tokens
                tokens_out = response.usage.output_tokens

                if self.cost_tracker:
                    model = kwargs.get("model", MODEL)
                    self.cost_tracker.record(self.role.value, model, tokens_in, tokens_out)

                return response, tokens_in, tokens_out

            except APIError as e:
                error_msg = str(e)
                if "rate_limit" in error_msg.lower() or "overloaded" in error_msg.lower():
                    wait = 2**attempt * 10
                    if attempt < MAX_RETRIES - 1:
                        if on_event:
                            on_event({"type": "retry", "agent": self.role.value, "wait": wait})
                        else:
                            logger.warning("rate_limited", agent=self.role.value, wait=wait, attempt=attempt + 1)
                        time.sleep(wait)
                        continue
                    raise
                # Non-rate-limit error: try fallback model once
                if self.fallback_model and kwargs.get("model") != self.fallback_model:
                    logger.warning("fallback_model", agent=self.role.value, model=self.fallback_model, error=error_msg)
                    kwargs["model"] = self.fallback_model
                    continue
                raise

        raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded")

    def _handle_stream_event(self, event, on_event):
        """Convert raw SDK stream events to text_delta callbacks."""
        event_type = getattr(event, "type", "")
        if event_type == "content_block_delta":
            delta = getattr(event, "delta", None)
            if delta and hasattr(delta, "text"):
                on_event({
                    "type": "text_delta",
                    "agent": self.role.value,
                    "text": delta.text,
                })
            elif delta and hasattr(delta, "partial_json"):
                on_event({
                    "type": "input_json_delta",
                    "agent": self.role.value,
                    "partial_json": delta.partial_json,
                })

    def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict] | None = None,
    ) -> tuple[Any, int, int]:
        """Make a single Claude API call with retry logic (non-streaming).

        Returns (response, tokens_in, tokens_out).
        """
        return self._api_call(
            system_prompt,
            [{"role": "user", "content": user_message}],
            tools,
        )

    # ── Execution ──

    @abstractmethod
    def execute(self, context: ContextPacket, on_event: StreamCallback = None) -> AgentResult:
        """Execute the agent with the given context. Must be implemented by subclasses."""
        ...

    def run(self, context: ContextPacket, on_event: StreamCallback = None) -> AgentResult:
        """Public entry point — wraps execute() with timing and error handling."""
        if on_event:
            on_event({"type": "agent_start", "agent": self.role.value, "task": context.task_description[:120]})
        else:
            logger.info("agent_start", agent=self.role.value, task=context.task_description[:120])

        start = time.time()
        try:
            result = self.execute(context, on_event=on_event)
            result.duration_seconds = time.time() - start
            if on_event:
                on_event({
                    "type": "agent_end",
                    "agent": self.role.value,
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "duration": result.duration_seconds,
                    "success": result.success,
                })
            else:
                logger.info(
                    "agent_end",
                    agent=self.role.value,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    duration=f"{result.duration_seconds:.1f}s",
                )
            return result
        except SystemExit:
            raise
        except Exception as e:
            duration = time.time() - start
            if on_event:
                on_event({"type": "agent_error", "agent": self.role.value, "error": str(e)})
            else:
                logger.error("agent_error", agent=self.role.value, error=str(e))
            return AgentResult(
                agent=self.role,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )


class SingleTurnAgent(BaseAgent):
    """Agent that makes a single LLM call (no tool use)."""

    def execute(self, context: ContextPacket, on_event: StreamCallback = None) -> AgentResult:
        system_prompt = self.build_system_prompt(context)
        user_message = self.build_user_message(context)

        response, tokens_in, tokens_out = self._api_call(
            system_prompt,
            [{"role": "user", "content": user_message}],
            on_event=on_event,
        )

        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        return AgentResult(
            agent=self.role,
            success=True,
            raw_text=raw_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
