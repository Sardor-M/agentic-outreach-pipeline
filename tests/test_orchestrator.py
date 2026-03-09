"""Tests for orchestrator — plan criticality, context building, error handling."""

from unittest.mock import patch, MagicMock

from models import AgentRole, PipelineStep
from orchestrator import Orchestrator


def test_plan_sets_criticality():
    orch = Orchestrator()
    plan = orch.plan("TestCo, Germany")

    criticality_map = {s.agent: s.criticality for s in plan.steps}
    assert criticality_map[AgentRole.RESEARCHER] == "required"
    assert criticality_map[AgentRole.ANALYST] == "optional"
    assert criticality_map[AgentRole.ARCHITECT] == "required"
    assert criticality_map[AgentRole.SCORER] == "optional"
    assert criticality_map[AgentRole.WRITER] == "required"


def test_plan_parallel_groups():
    orch = Orchestrator()
    plan = orch.plan("TestCo, Germany")

    groups = {}
    for step in plan.steps:
        groups.setdefault(step.parallel_group, []).append(step.agent)

    # Group 0: researcher only
    assert groups[0] == [AgentRole.RESEARCHER]
    # Group 1: analyst + architect (parallel)
    assert set(groups[1]) == {AgentRole.ANALYST, AgentRole.ARCHITECT}


def test_plan_extracts_company_name():
    orch = Orchestrator()
    plan = orch.plan("Mueller Automotive GmbH, Germany")
    assert plan.target_company == "Mueller Automotive GmbH"


def test_orchestrator_has_cost_tracker():
    orch = Orchestrator()
    assert orch.cost_tracker is not None
    assert orch.cost_tracker.budget_limit is None

    orch2 = Orchestrator(budget_limit=5.0)
    assert orch2.cost_tracker.budget_limit == 5.0


def test_build_context_for_researcher():
    orch = Orchestrator()
    context = orch._build_context_for_agent(
        AgentRole.RESEARCHER,
        "TestCo, Germany",
        {},
    )
    assert "TestCo" in context.task_description
    assert context.token_budget == 4000


def test_build_context_for_scorer():
    from models import AgentResult

    orch = Orchestrator()
    agent_outputs = {
        "researcher": AgentResult(
            agent=AgentRole.RESEARCHER,
            success=True,
            raw_text="Research findings about TestCo.",
        ),
    }
    context = orch._build_context_for_agent(
        AgentRole.SCORER,
        "TestCo, Germany",
        agent_outputs,
    )
    assert "Estimate the deal size" in context.task_description
    assert context.token_budget == 2000
