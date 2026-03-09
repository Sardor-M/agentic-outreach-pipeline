"""
Shared test fixtures — mock Anthropic client, sample data, response builders.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


# ── Mock response builder ──

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
    """Build a mock Claude API response."""
    return MockResponse(
        content=[MockTextBlock(text=text)],
        usage=MockUsage(input_tokens=tokens_in, output_tokens=tokens_out),
        stop_reason=stop_reason,
    )


def build_mock_tool_response(tool_name, tool_input, tool_id="tool_123"):
    """Build a mock Claude API response with tool use."""
    return MockResponse(
        content=[MockToolUseBlock(name=tool_name, input=tool_input, id=tool_id)],
        usage=MockUsage(),
        stop_reason="tool_use",
    )


# ── Fixtures ──

@pytest.fixture
def mock_anthropic():
    """Mock the Anthropic client."""
    with patch("agents.base.Anthropic") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        client.messages.create.return_value = build_mock_response()
        yield client


@pytest.fixture
def sample_company_config():
    """Sample company config matching company.yaml structure."""
    return {
        "name": "TestCo",
        "location": "San Jose, CA",
        "short_description": "TestCo sells smart factory products.",
        "contact": {"email": "test@example.com", "phone": "+1-555-0000"},
        "email_signature": "Best regards,\nTestCo Team",
        "pricing": {
            "hardware_unit_range": "$8,000 - $15,000",
            "software_license_range": "$2,000 - $6,000/month",
            "implementation_range": "$15,000 - $50,000",
            "annual_support": "15-20% of hardware cost",
        },
        "research": {"depth": "standard"},
    }


@pytest.fixture
def sample_context_packet(sample_company_config):
    """Sample ContextPacket for testing agents."""
    from models import ContextPacket

    return ContextPacket(
        task_description="Research TestTarget GmbH, Germany",
        relevant_data={},
        summaries=[],
        token_budget=3000,
        company_config=sample_company_config,
    )
