"""
Analyst Agent — Competitive and financial analysis.

NEW agent that provides competitive intelligence and financial analysis.
Runs in parallel with Architect (both depend on Research, not each other).
"""

from __future__ import annotations

from agents.base import SingleTurnAgent
from models import AgentRole


class AnalystAgent(SingleTurnAgent):
    role = AgentRole.ANALYST
    prompt_file = "analyst.md"
    temperature = 0.5
