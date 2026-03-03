"""
Architect Agent — Solution mapping to products.

Single-turn agent that receives a ContextPacket with pain points + full product
context, and maps them to specific product features.

This is the ONLY agent that gets full product context in its system prompt.
"""

from __future__ import annotations

from agents.base import SingleTurnAgent
from models import AgentRole


class ArchitectAgent(SingleTurnAgent):
    role = AgentRole.ARCHITECT
    prompt_file = "architect.md"
    temperature = 0.5
