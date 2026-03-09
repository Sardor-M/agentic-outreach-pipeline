"""Tests for Pydantic data models."""

from models import (
    AgentResult,
    AgentRole,
    Confidence,
    DealCategory,
    DealEstimate,
    PipelinePlan,
    PipelineResult,
    PipelineStep,
    ProposalOutput,
    ResearchBrief,
    CompanyProfile,
    SolutionType,
)


def test_agent_role_values():
    assert AgentRole.RESEARCHER.value == "researcher"
    assert AgentRole.WRITER.value == "writer"
    assert AgentRole.SCORER.value == "scorer"


def test_deal_category_enum():
    assert DealCategory.SMALL.value == "Small"
    assert DealCategory.ENTERPRISE.value == "Enterprise"


def test_confidence_enum():
    assert Confidence.LOW.value == "Low"
    assert Confidence.HIGH.value == "High"


def test_solution_type_enum():
    assert SolutionType.BOTH.value == "Hardware + Software"


def test_deal_estimate_defaults():
    d = DealEstimate()
    assert d.company_name == ""
    assert d.estimated_machines == 0
    assert d.first_year_value == 0
    assert d.deal_category == DealCategory.SMALL
    assert d.confidence == Confidence.LOW


def test_deal_estimate_serialization():
    d = DealEstimate(
        company_name="Acme",
        industry="Manufacturing",
        estimated_machines=50,
        first_year_value=200000,
        deal_category=DealCategory.MEDIUM,
        confidence=Confidence.HIGH,
        reasoning="Good fit",
    )
    data = d.model_dump()
    assert data["company_name"] == "Acme"
    assert data["first_year_value"] == 200000
    assert data["deal_category"] == "Medium"

    # Round-trip
    d2 = DealEstimate(**data)
    assert d2.company_name == "Acme"


def test_proposal_output_defaults():
    p = ProposalOutput()
    assert p.proposal_markdown == ""
    assert p.email_subject == ""
    assert p.email_body == ""


def test_pipeline_step_criticality():
    step = PipelineStep(agent=AgentRole.ANALYST)
    assert step.criticality == "required"

    optional = PipelineStep(agent=AgentRole.ANALYST, criticality="optional")
    assert optional.criticality == "optional"


def test_pipeline_result_cost_report():
    r = PipelineResult(target_company="Test")
    assert r.cost_report == {}
    r.cost_report = {"total_cost": 0.05}
    assert r.cost_report["total_cost"] == 0.05


def test_research_brief_quality_fields():
    brief = ResearchBrief(
        company=CompanyProfile(name="Test"),
        sources_used=["search_web:query1", "scrape_company_website:url1"],
        facts_verified=5,
        facts_inferred=3,
        research_confidence=0.8,
    )
    assert len(brief.sources_used) == 2
    assert brief.facts_verified == 5
    assert brief.research_confidence == 0.8


def test_agent_result_defaults():
    r = AgentResult(agent=AgentRole.RESEARCHER)
    assert r.success is True
    assert r.tokens_in == 0
    assert r.error == ""


def test_pipeline_plan_defaults():
    plan = PipelinePlan(target_company="Test")
    assert plan.steps == []
    assert plan.estimated_cost == 0.0
