"""Tests for context management."""

from unittest.mock import patch, MagicMock

from context import ContextManager, count_tokens, count_messages_tokens


def test_count_tokens_basic():
    tokens = count_tokens("Hello, world!")
    assert tokens > 0
    assert isinstance(tokens, int)


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_count_messages_tokens_string():
    messages = [{"role": "user", "content": "Hello"}]
    tokens = count_messages_tokens(messages)
    assert tokens > 0


def test_count_messages_tokens_list():
    messages = [{"role": "user", "content": [{"text": "Hello"}]}]
    tokens = count_messages_tokens(messages)
    assert tokens > 0


def test_prune_messages_short():
    """Short message lists should pass through unchanged."""
    cm = ContextManager(max_history_tokens=10000)
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    result = cm.prune_messages(messages)
    assert result == messages


def test_build_context_packet():
    cm = ContextManager()
    packet = cm.build_context_packet(
        task_description="Test task",
        relevant_data={"key": "value"},
        company_config={"name": "TestCo"},
        token_budget=2000,
    )
    assert packet.task_description == "Test task"
    assert packet.relevant_data == {"key": "value"}
    assert packet.company_config["name"] == "TestCo"
    assert packet.token_budget == 2000


def test_build_context_packet_defaults():
    cm = ContextManager()
    packet = cm.build_context_packet(
        task_description="Test",
        relevant_data={},
    )
    assert packet.summaries == []
    assert packet.company_config == {}
    assert packet.token_budget == 3000
