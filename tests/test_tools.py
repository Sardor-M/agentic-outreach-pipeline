"""Tests for tools: circuit breaker, relevance filtering, tool definitions."""

import time

from tools.base import CircuitBreaker
from tools.web_search import _is_relevant_result, WebSearchTool


# ── CircuitBreaker ──

def test_circuit_breaker_starts_closed():
    cb = CircuitBreaker(failure_threshold=3)
    assert not cb.is_open


def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
    cb.record_failure()
    assert not cb.is_open
    cb.record_failure()
    assert cb.is_open


def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_failure()
    cb.record_success()
    assert cb.consecutive_failures == 0
    assert not cb.is_open


def test_circuit_breaker_resets_after_cooldown():
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.1)
    cb.record_failure()
    assert cb.is_open
    time.sleep(0.15)
    assert not cb.is_open


# ── _is_relevant_result ──

def test_filters_wikipedia():
    assert not _is_relevant_result("https://en.wikipedia.org/wiki/Test", "Test Company")


def test_filters_linkedin():
    assert not _is_relevant_result("https://www.linkedin.com/company/test", "Test Company")


def test_filters_directory_patterns():
    assert not _is_relevant_result("https://example.com", "Top 10 Companies in Manufacturing")
    assert not _is_relevant_result("https://example.com", "Best 5 Metal Stamping Suppliers")


def test_accepts_company_website():
    assert _is_relevant_result("https://www.acme-manufacturing.com", "ACME Manufacturing GmbH")


def test_accepts_normal_result():
    assert _is_relevant_result("https://mueller-auto.de", "Mueller Automotive - About Us")


# ── WebSearchTool definition ──

def test_web_search_tool_definition():
    tool = WebSearchTool()
    defn = tool.get_tool_definition()
    assert defn["name"] == "search_web"
    assert "query" in defn["input_schema"]["properties"]
    assert "query" in defn["input_schema"]["required"]
