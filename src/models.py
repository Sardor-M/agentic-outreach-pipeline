"""
Pydantic data models for the agentic outreach pipeline.

All structured data flows through these models — no raw text passing between agents.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──

class DealCategory(str, Enum):
    SMALL = "Small"
    MEDIUM = "Medium"
    ENTERPRISE = "Enterprise"


class Confidence(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class SolutionType(str, Enum):
    HARDWARE_ONLY = "Hardware only"
    SOFTWARE_ONLY = "Software only"
    BOTH = "Hardware + Software"


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    ARCHITECT = "architect"
    WRITER = "writer"
    SCORER = "scorer"


# ── Knowledge / Extraction Models ──


class CompanyFact(BaseModel):
    """A single structured fact extracted from a web page."""

    category: str = Field(description="Fact category: company, manufacturing, energy, esg, financial, general")
    text: str = Field(description="The extracted fact")
    source_url: str = Field(default="", description="URL where this fact was found")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class CompanyProfile(BaseModel):
    """Structured company profile built from research."""

    name: str
    location: str = ""
    website: str = ""
    industry: str = ""
    description: str = ""
    employee_count: str = ""
    factory_count: int = 0
    machine_count: int = 0
    products_manufactured: list[str] = Field(default_factory=list)
    key_customers: list[str] = Field(default_factory=list)
    facts: list[CompanyFact] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)


# ── Agent I/O Models ──


class ContextPacket(BaseModel):
    """Curated context given to each sub-agent. No raw text dumps."""

    task_description: str = Field(description="What this specific agent should do")
    relevant_data: dict[str, Any] = Field(default_factory=dict, description="Only the data this agent needs")
    summaries: list[str] = Field(default_factory=list, description="LLM-summarized outputs from prior agents")
    token_budget: int = Field(default=3000, description="Max context tokens allocated")
    company_config: dict[str, Any] = Field(default_factory=dict, description="From config/company.yaml")


class ResearchBrief(BaseModel):
    """Output of the Researcher agent."""

    company: CompanyProfile
    pain_points: list[str] = Field(default_factory=list)
    esg_exposure: str = ""
    energy_profile: str = ""
    manufacturing_process: str = ""
    decision_factors: list[str] = Field(default_factory=list)
    raw_brief: str = Field(default="", description="Full text research brief for downstream agents")
    sources_used: list[str] = Field(default_factory=list)
    facts_verified: int = 0
    facts_inferred: int = 0
    research_confidence: float = 0.0


class CompetitiveAnalysis(BaseModel):
    """Output of the Analyst agent."""

    competitors: list[dict[str, str]] = Field(default_factory=list)
    market_position: str = ""
    financial_indicators: str = ""
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    raw_analysis: str = ""


class SolutionMap(BaseModel):
    """Output of the Architect agent."""

    recommended_solution: SolutionType = SolutionType.BOTH
    pain_point_mappings: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of {pain_point, product_feature, how_it_solves, estimated_impact}",
    )
    implementation_approach: str = ""
    roi_breakdown: dict[str, str] = Field(default_factory=dict)
    relevant_case_studies: list[str] = Field(default_factory=list)
    raw_solution_map: str = ""


class DealEstimate(BaseModel):
    """Output of the Scorer agent."""

    company_name: str = ""
    industry: str = ""
    estimated_machines: int = 0
    recommended_solution: str = "Hardware + Software"
    first_year_value: float = 0
    annual_recurring: float = 0
    deal_category: DealCategory = DealCategory.SMALL
    confidence: Confidence = Confidence.LOW
    reasoning: str = ""


class ProposalOutput(BaseModel):
    """Output of the Writer agent."""

    proposal_markdown: str = ""
    email_subject: str = ""
    email_body: str = ""


# ── Pipeline Models ──


class PipelineStep(BaseModel):
    """A single step in the pipeline plan."""

    agent: AgentRole
    parallel_group: int = Field(default=0, description="Steps with same group run concurrently")
    depends_on: list[AgentRole] = Field(default_factory=list)
    description: str = ""
    criticality: str = Field(default="required", description="'required' or 'optional'")


class PipelinePlan(BaseModel):
    """The orchestrator's execution plan."""

    target_company: str
    steps: list[PipelineStep] = Field(default_factory=list)
    estimated_cost: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)


class AgentResult(BaseModel):
    """Result from a single agent execution."""

    agent: AgentRole
    success: bool = True
    output: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_seconds: float = 0.0
    error: str = ""


class PipelineResult(BaseModel):
    """Final aggregated result from the full pipeline."""

    target_company: str
    plan: PipelinePlan | None = None
    agent_results: dict[str, AgentResult] = Field(default_factory=dict)
    research_brief: ResearchBrief | None = None
    competitive_analysis: CompetitiveAnalysis | None = None
    solution_map: SolutionMap | None = None
    deal_estimate: DealEstimate | None = None
    proposal: ProposalOutput | None = None
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_duration_seconds: float = 0.0
    cost_report: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))


# ── Prospect Models (for search flow) ──


class Prospect(BaseModel):
    """A prospect found via web search."""

    title: str
    url: str = ""
    snippet: str = ""
    domain: str = ""
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)

    def format_for_agent(self) -> str:
        """Format prospect into a text block for agent consumption."""
        email_str = ", ".join(self.emails) if self.emails else "Not found"
        phone_str = ", ".join(self.phones) if self.phones else "Not found"
        return (
            f"Company: {self.title}\n"
            f"Website: {self.url}\n"
            f"Description: {self.snippet}\n"
            f"Email(s): {email_str}\n"
            f"Phone(s): {phone_str}"
        )
