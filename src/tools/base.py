"""
Base Tool — Abstract class with circuit breaker pattern.

All tools inherit from this. The circuit breaker prevents hammering
a failing service (e.g., DuckDuckGo rate limit, unreachable website).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any


class CircuitBreaker:
    """Simple circuit breaker: after N consecutive failures, stop trying for a cooldown period."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.consecutive_failures = 0
        self.last_failure_time: float = 0.0

    @property
    def is_open(self) -> bool:
        """True if circuit is open (tool should not be called)."""
        if self.consecutive_failures < self.failure_threshold:
            return False
        elapsed = time.time() - self.last_failure_time
        if elapsed >= self.cooldown_seconds:
            # Reset after cooldown
            self.consecutive_failures = 0
            return False
        return True

    def record_success(self):
        self.consecutive_failures = 0

    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()


class BaseTool(ABC):
    """Abstract base class for all pipeline tools."""

    name: str
    description: str

    def __init__(self):
        self.circuit_breaker = CircuitBreaker()

    @abstractmethod
    def _execute(self, **kwargs) -> str:
        """Execute the tool. Must be implemented by subclasses."""
        ...

    def run(self, **kwargs) -> str:
        """Public entry point with circuit breaker."""
        if self.circuit_breaker.is_open:
            return f"Error: {self.name} is temporarily unavailable (too many recent failures). Try again later."

        try:
            result = self._execute(**kwargs)
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            return f"Error: {self.name} failed — {e}"

    def get_tool_definition(self) -> dict:
        """Return the Claude API tool definition for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._input_schema(),
        }

    @abstractmethod
    def _input_schema(self) -> dict:
        """Return the JSON schema for tool input."""
        ...
