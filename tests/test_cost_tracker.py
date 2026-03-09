"""Tests for cost tracker."""

import threading

from cost_tracker import CostTracker, MODEL_RATES


def test_record_basic():
    ct = CostTracker()
    record = ct.record("researcher", "claude-sonnet-4-20250514", 1000, 500)
    assert record.tokens_in == 1000
    assert record.tokens_out == 500
    assert record.cost_in > 0
    assert record.cost_out > 0
    assert record.total_cost == record.cost_in + record.cost_out


def test_cost_calculation():
    ct = CostTracker()
    # Sonnet: $3/1M input, $15/1M output
    ct.record("test", "claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    assert abs(ct.total_cost - 18.0) < 0.01  # $3 + $15


def test_haiku_cost():
    ct = CostTracker()
    # Haiku: $0.80/1M input, $4/1M output
    ct.record("test", "claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert abs(ct.total_cost - 4.80) < 0.01


def test_total_tokens():
    ct = CostTracker()
    ct.record("agent1", "claude-sonnet-4-20250514", 100, 200)
    ct.record("agent2", "claude-sonnet-4-20250514", 300, 400)
    assert ct.total_tokens_in == 400
    assert ct.total_tokens_out == 600


def test_budget_no_limit():
    ct = CostTracker()
    ct.record("test", "claude-sonnet-4-20250514", 10000, 10000)
    assert ct.check_budget() is True


def test_budget_within():
    ct = CostTracker(budget_limit=1.0)
    ct.record("test", "claude-sonnet-4-20250514", 1000, 500)
    assert ct.check_budget() is True


def test_budget_exceeded():
    ct = CostTracker(budget_limit=0.001)
    ct.record("test", "claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    assert ct.check_budget() is False


def test_report_structure():
    ct = CostTracker(budget_limit=10.0)
    ct.record("researcher", "claude-sonnet-4-20250514", 1000, 2000)
    ct.record("scorer", "claude-haiku-4-5-20251001", 500, 300)

    report = ct.get_report()
    assert "total_cost" in report
    assert "total_tokens_in" in report
    assert "total_tokens_out" in report
    assert "budget_limit" in report
    assert "within_budget" in report
    assert "by_agent" in report
    assert "researcher" in report["by_agent"]
    assert "scorer" in report["by_agent"]
    assert report["by_agent"]["researcher"]["calls"] == 1
    assert report["total_tokens_in"] == 1500


def test_thread_safety():
    ct = CostTracker()
    errors = []

    def record_many():
        try:
            for _ in range(100):
                ct.record("test", "claude-sonnet-4-20250514", 10, 20)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=record_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(ct.records) == 400
    assert ct.total_tokens_in == 4000


def test_unknown_model_uses_default():
    ct = CostTracker()
    record = ct.record("test", "unknown-model-v1", 1000, 1000)
    # Should use default rates (same as Sonnet)
    assert record.cost_in > 0
    assert record.cost_out > 0
