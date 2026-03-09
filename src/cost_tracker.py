"""
Cost Tracker — Per-agent token and cost accounting.

Thread-safe cost recording with budget guards.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

# Cost per 1M tokens (input / output)
MODEL_RATES: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}

# Fallback rate for unknown models
DEFAULT_RATE = (3.0, 15.0)


@dataclass
class AgentCostRecord:
    """Cost record for a single agent API call."""

    agent: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_in: float
    cost_out: float

    @property
    def total_cost(self) -> float:
        return self.cost_in + self.cost_out


@dataclass
class CostTracker:
    """Thread-safe cost tracker with optional budget limit."""

    budget_limit: float | None = None
    records: list[AgentCostRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, agent: str, model: str, tokens_in: int, tokens_out: int) -> AgentCostRecord:
        """Record an API call and return the cost record."""
        rate_in, rate_out = MODEL_RATES.get(model, DEFAULT_RATE)
        cost_in = (tokens_in / 1_000_000) * rate_in
        cost_out = (tokens_out / 1_000_000) * rate_out

        entry = AgentCostRecord(
            agent=agent,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_in=cost_in,
            cost_out=cost_out,
        )

        with self._lock:
            self.records.append(entry)

        return entry

    @property
    def total_cost(self) -> float:
        with self._lock:
            return sum(r.total_cost for r in self.records)

    @property
    def total_tokens_in(self) -> int:
        with self._lock:
            return sum(r.tokens_in for r in self.records)

    @property
    def total_tokens_out(self) -> int:
        with self._lock:
            return sum(r.tokens_out for r in self.records)

    def check_budget(self) -> bool:
        """Return True if within budget (or no budget set)."""
        if self.budget_limit is None:
            return True
        return self.total_cost <= self.budget_limit

    def get_report(self) -> dict:
        """Get a cost report with per-agent breakdown."""
        with self._lock:
            by_agent: dict[str, dict] = {}
            for r in self.records:
                if r.agent not in by_agent:
                    by_agent[r.agent] = {
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "cost": 0.0,
                        "calls": 0,
                    }
                entry = by_agent[r.agent]
                entry["tokens_in"] += r.tokens_in
                entry["tokens_out"] += r.tokens_out
                entry["cost"] += r.total_cost
                entry["calls"] += 1

            total = sum(r.total_cost for r in self.records)
            within = self.budget_limit is None or total <= self.budget_limit

            return {
                "total_cost": total,
                "total_tokens_in": sum(r.tokens_in for r in self.records),
                "total_tokens_out": sum(r.tokens_out for r in self.records),
                "budget_limit": self.budget_limit,
                "within_budget": within,
                "by_agent": by_agent,
            }
