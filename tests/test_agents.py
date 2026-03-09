"""Tests for agents — mocked API calls, structured output, fallback model."""

from unittest.mock import patch, MagicMock

import pytest

from context import ContextManager
from models import AgentResult, AgentRole, ContextPacket, DealEstimate


# ── Inline mock helpers (conftest fixtures loaded by pytest, not importable) ──

from dataclasses import dataclass


@dataclass
class MockUsage:
    input_tokens: int = 100
    output_tokens: int = 200


@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = "Mock response text"


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "tool_123"
    name: str = "submit_deal_estimate"
    input: dict = None

    def __post_init__(self):
        if self.input is None:
            self.input = {}


@dataclass
class MockResponse:
    content: list = None
    usage: MockUsage = None
    stop_reason: str = "end_turn"

    def __post_init__(self):
        if self.content is None:
            self.content = [MockTextBlock()]
        if self.usage is None:
            self.usage = MockUsage()


def build_mock_response(text="Mock response", tokens_in=100, tokens_out=200, stop_reason="end_turn"):
    return MockResponse(
        content=[MockTextBlock(text=text)],
        usage=MockUsage(input_tokens=tokens_in, output_tokens=tokens_out),
        stop_reason=stop_reason,
    )


# ── Helpers ──

def _make_context(task="Test task"):
    return ContextPacket(
        task_description=task,
        relevant_data={},
        summaries=[],
        token_budget=3000,
        company_config={
            "name": "TestCo",
            "short_description": "TestCo sells smart factory products.",
            "contact": {"email": "test@example.com", "phone": "+1-555-0000"},
            "email_signature": "Best,\nTestCo",
            "pricing": {},
            "research": {"depth": "standard"},
        },
    )


# ── SingleTurnAgent (via AnalystAgent) ──

@patch("agents.base.Anthropic")
def test_single_turn_agent(mock_cls):
    client = MagicMock()
    mock_cls.return_value = client
    client.messages.create.return_value = build_mock_response("Analysis complete")

    from agents.analyst import AnalystAgent
    agent = AnalystAgent(ContextManager())
    result = agent.run(_make_context("Analyze competitive landscape"))

    assert result.success
    assert result.agent == AgentRole.ANALYST
    assert "Analysis complete" in result.raw_text
    assert result.tokens_in == 100
    assert result.tokens_out == 200


# ── ScorerAgent structured output ──

@patch("agents.base.Anthropic")
def test_scorer_structured_output(mock_cls):
    client = MagicMock()
    mock_cls.return_value = client

    tool_input = {
        "company_name": "Acme Inc",
        "industry": "Manufacturing",
        "estimated_machines": 50,
        "recommended_solution": "Hardware + Software",
        "first_year_value": 200000,
        "annual_recurring": 50000,
        "deal_category": "Medium",
        "confidence": "High",
        "reasoning": "Good fit based on scale",
    }

    client.messages.create.return_value = MockResponse(
        content=[MockToolUseBlock(name="submit_deal_estimate", input=tool_input)],
        usage=MockUsage(),
        stop_reason="tool_use",
    )

    from agents.scorer import ScorerAgent
    agent = ScorerAgent(ContextManager())
    result = agent.run(_make_context("Estimate deal"))

    assert result.success
    assert result.output["company_name"] == "Acme Inc"
    assert result.output["first_year_value"] == 200000
    assert result.output["deal_category"] == "Medium"


# ── WriterAgent structured output ──

@patch("agents.base.Anthropic")
def test_writer_structured_output(mock_cls):
    client = MagicMock()
    mock_cls.return_value = client

    tool_input = {
        "proposal_markdown": "# Proposal for Acme\n\nGreat proposal.",
        "email_subject": "Smart Manufacturing for Acme",
        "email_body": "Dear Acme team,\n\nWe'd love to help.",
    }

    client.messages.create.return_value = MockResponse(
        content=[MockToolUseBlock(name="submit_proposal", input=tool_input)],
        usage=MockUsage(),
        stop_reason="tool_use",
    )

    from agents.writer import WriterAgent
    agent = WriterAgent(ContextManager())
    result = agent.run(_make_context("Write proposal"))

    assert result.success
    assert "Proposal for Acme" in result.output["proposal_markdown"]
    assert result.output["email_subject"] == "Smart Manufacturing for Acme"


# ── Fallback model attribute ──

def test_analyst_has_fallback_model():
    from agents.analyst import AnalystAgent
    from agents.base import FALLBACK_MODEL
    agent = AnalystAgent(ContextManager())
    assert agent.fallback_model == FALLBACK_MODEL


def test_scorer_has_fallback_model():
    from agents.scorer import ScorerAgent
    from agents.base import FALLBACK_MODEL
    agent = ScorerAgent(ContextManager())
    assert agent.fallback_model == FALLBACK_MODEL


def test_architect_no_fallback_model():
    from agents.architect import ArchitectAgent
    agent = ArchitectAgent(ContextManager())
    assert agent.fallback_model is None


# ── Cost tracker integration ──

@patch("agents.base.Anthropic")
def test_agent_records_cost(mock_cls):
    from cost_tracker import CostTracker

    client = MagicMock()
    mock_cls.return_value = client
    client.messages.create.return_value = build_mock_response()

    ct = CostTracker()
    from agents.analyst import AnalystAgent
    agent = AnalystAgent(ContextManager(), cost_tracker=ct)
    agent.run(_make_context())

    assert len(ct.records) == 1
    assert ct.records[0].agent == "analyst"
    assert ct.total_tokens_in == 100
