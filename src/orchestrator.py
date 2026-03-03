"""
Orchestrator — Central brain of the pipeline.

Like Claude Code: plan → decompose → dispatch sub-agents with isolated context → aggregate.

Key responsibilities:
1. PLAN: Analyze task → generate PipelinePlan (which agents, what order, what's parallel)
2. EXECUTE: Dispatch sub-agents per plan, each with curated ContextPacket
3. AGGREGATE: Collect structured results → PipelineResult

Context rot is solved by:
- Each agent gets fresh context (no inherited conversation history)
- Agent outputs are summarized for handoff (not passed raw)
- Only relevant data goes to each agent (e.g., Writer doesn't get raw scraped pages)
"""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from context import ContextManager
from knowledge.product_loader import COMPANY_CONFIG
from models import (
    AgentResult,
    AgentRole,
    ContextPacket,
    DealEstimate,
    PipelinePlan,
    PipelineResult,
    PipelineStep,
    ProposalOutput,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = str(PROJECT_ROOT / "outputs")


class Orchestrator:
    """Central pipeline orchestrator."""

    def __init__(self, interactive: bool = False):
        self.interactive = interactive
        self.context_manager = ContextManager()
        self._agents: dict = {}

    def _get_agent(self, role: AgentRole):
        """Lazy-load agents."""
        if role not in self._agents:
            if role == AgentRole.RESEARCHER:
                from agents.researcher import ResearcherAgent

                self._agents[role] = ResearcherAgent(self.context_manager)
            elif role == AgentRole.ANALYST:
                from agents.analyst import AnalystAgent

                self._agents[role] = AnalystAgent(self.context_manager)
            elif role == AgentRole.ARCHITECT:
                from agents.architect import ArchitectAgent

                self._agents[role] = ArchitectAgent(self.context_manager)
            elif role == AgentRole.WRITER:
                from agents.writer import WriterAgent

                self._agents[role] = WriterAgent(self.context_manager)
            elif role == AgentRole.SCORER:
                from agents.scorer import ScorerAgent

                self._agents[role] = ScorerAgent(self.context_manager)
        return self._agents[role]

    def plan(self, task: str) -> PipelinePlan:
        """Generate an execution plan for the given task.

        For now, uses a deterministic plan. A future version could use
        Claude to dynamically generate the plan based on the task.
        """
        company_name = task.split(",")[0].split("\n")[0].strip()

        # Default full pipeline plan
        steps = [
            PipelineStep(
                agent=AgentRole.RESEARCHER,
                parallel_group=0,
                description="Research the target company",
            ),
            PipelineStep(
                agent=AgentRole.ANALYST,
                parallel_group=1,
                depends_on=[AgentRole.RESEARCHER],
                description="Analyze competitive landscape",
            ),
            PipelineStep(
                agent=AgentRole.ARCHITECT,
                parallel_group=1,
                depends_on=[AgentRole.RESEARCHER],
                description="Map solutions to pain points",
            ),
            PipelineStep(
                agent=AgentRole.SCORER,
                parallel_group=2,
                depends_on=[AgentRole.RESEARCHER],
                description="Estimate deal size",
            ),
            PipelineStep(
                agent=AgentRole.WRITER,
                parallel_group=3,
                depends_on=[AgentRole.ARCHITECT],
                description="Generate proposal and email",
            ),
        ]

        plan = PipelinePlan(target_company=company_name, steps=steps)

        if self.interactive:
            self._display_plan(plan)

        return plan

    def _display_plan(self, plan: PipelinePlan):
        """Display the execution plan to the user."""
        print(f"\nTarget: {plan.target_company}")

        groups: dict[int, list[PipelineStep]] = {}
        for step in plan.steps:
            groups.setdefault(step.parallel_group, []).append(step)

        for group_id in sorted(groups):
            steps = groups[group_id]
            if len(steps) == 1:
                s = steps[0]
                print(f"  Step {group_id}: {s.agent.value.title()} — {s.description}")
            else:
                names = " + ".join(s.agent.value.title() for s in steps)
                print(f"  Step {group_id}: [{names}] (parallel)")
                for s in steps:
                    print(f"           └─ {s.agent.value.title()} — {s.description}")
        print()

    def execute(self, task: str, plan: PipelinePlan | None = None) -> PipelineResult:
        """Execute the full pipeline."""
        start_time = time.time()

        if plan is None:
            plan = self.plan(task)

        print(f"\nTarget: {plan.target_company}")

        result = PipelineResult(target_company=plan.target_company, plan=plan)
        agent_outputs: dict[str, AgentResult] = {}

        # Execute groups in order
        groups: dict[int, list[PipelineStep]] = {}
        for step in plan.steps:
            groups.setdefault(step.parallel_group, []).append(step)

        for group_id in sorted(groups):
            steps = groups[group_id]

            if len(steps) == 1:
                # Sequential execution
                step = steps[0]
                context = self._build_context_for_agent(step.agent, task, agent_outputs)
                agent = self._get_agent(step.agent)
                agent_result = agent.run(context)
                agent_outputs[step.agent.value] = agent_result
            else:
                # Parallel execution
                self._execute_parallel(steps, task, agent_outputs)

        # Aggregate results
        result.agent_results = {k: v for k, v in agent_outputs.items()}
        result = self._aggregate(result, agent_outputs)
        result.total_duration_seconds = time.time() - start_time

        # Calculate totals
        for ar in agent_outputs.values():
            result.total_tokens_in += ar.tokens_in
            result.total_tokens_out += ar.tokens_out

        print(f"\nTotal tokens: {result.total_tokens_in} in / {result.total_tokens_out} out")
        print(f"Duration: {result.total_duration_seconds:.1f}s")

        return result

    def _execute_parallel(
        self, steps: list[PipelineStep], task: str, agent_outputs: dict[str, AgentResult]
    ):
        """Execute multiple steps in parallel using threads."""
        print(f"\n  Running in parallel: {', '.join(s.agent.value for s in steps)}")

        def _run_step(step: PipelineStep) -> tuple[str, AgentResult]:
            context = self._build_context_for_agent(step.agent, task, agent_outputs)
            agent = self._get_agent(step.agent)
            return step.agent.value, agent.run(context)

        with ThreadPoolExecutor(max_workers=len(steps)) as executor:
            futures = {executor.submit(_run_step, step): step for step in steps}
            for future in futures:
                name, result = future.result()
                agent_outputs[name] = result

    def _build_context_for_agent(
        self,
        agent_role: AgentRole,
        task: str,
        agent_outputs: dict[str, AgentResult],
    ) -> ContextPacket:
        """Build a curated ContextPacket for a specific agent.

        Each agent only gets the data it needs — no raw text dumps.
        """
        company_config = COMPANY_CONFIG.copy()

        if agent_role == AgentRole.RESEARCHER:
            return self.context_manager.build_context_packet(
                task_description=task,
                relevant_data={},
                company_config=company_config,
                token_budget=4000,
            )

        if agent_role == AgentRole.ANALYST:
            research = agent_outputs.get("researcher")
            summaries = []
            if research and research.success:
                summaries.append(
                    self.context_manager.summarize_for_handoff(research.raw_text, "analyst")
                )
            return self.context_manager.build_context_packet(
                task_description=f"Analyze the competitive landscape and financial position of the target company from the research.",
                relevant_data={},
                prior_summaries=summaries,
                company_config=company_config,
                token_budget=3000,
            )

        if agent_role == AgentRole.ARCHITECT:
            research = agent_outputs.get("researcher")
            summaries = []
            if research and research.success:
                summaries.append(
                    self.context_manager.summarize_for_handoff(research.raw_text, "architect")
                )
            return self.context_manager.build_context_packet(
                task_description=f"Map the prospect's pain points to specific product features.",
                relevant_data={},
                prior_summaries=summaries,
                company_config=company_config,
                token_budget=4000,
            )

        if agent_role == AgentRole.SCORER:
            research = agent_outputs.get("researcher")
            summaries = []
            if research and research.success:
                summaries.append(
                    self.context_manager.summarize_for_handoff(research.raw_text, "scorer")
                )
            return self.context_manager.build_context_packet(
                task_description=f"Estimate the deal size for this prospect.",
                relevant_data={},
                prior_summaries=summaries,
                company_config=company_config,
                token_budget=2000,
            )

        if agent_role == AgentRole.WRITER:
            research = agent_outputs.get("researcher")
            architect = agent_outputs.get("architect")
            company_name = task.split(",")[0].split("\n")[0].strip()

            summaries = []
            relevant_data = {"company_name": company_name}

            if research and research.success:
                summaries.append(
                    self.context_manager.summarize_for_handoff(research.raw_text, "writer")
                )
            if architect and architect.success:
                summaries.append(
                    self.context_manager.summarize_for_handoff(architect.raw_text, "writer")
                )

            return self.context_manager.build_context_packet(
                task_description=f"Create a sales proposal and cold email for {company_name}.",
                relevant_data=relevant_data,
                prior_summaries=summaries,
                company_config=company_config,
                token_budget=4000,
            )

    def _aggregate(self, result: PipelineResult, agent_outputs: dict[str, AgentResult]) -> PipelineResult:
        """Aggregate agent results into the final PipelineResult."""

        # Research brief
        research = agent_outputs.get("researcher")
        if research and research.success:
            from models import ResearchBrief, CompanyProfile

            result.research_brief = ResearchBrief(
                company=CompanyProfile(name=result.target_company),
                raw_brief=research.raw_text,
            )

        # Competitive analysis
        analyst = agent_outputs.get("analyst")
        if analyst and analyst.success:
            from models import CompetitiveAnalysis

            result.competitive_analysis = CompetitiveAnalysis(raw_analysis=analyst.raw_text)

        # Solution map
        architect = agent_outputs.get("architect")
        if architect and architect.success:
            from models import SolutionMap

            result.solution_map = SolutionMap(raw_solution_map=architect.raw_text)

        # Deal estimate
        scorer = agent_outputs.get("scorer")
        if scorer and scorer.success and scorer.output:
            try:
                result.deal_estimate = DealEstimate(**scorer.output)
            except Exception:
                result.deal_estimate = DealEstimate(company_name=result.target_company)

        # Proposal
        writer = agent_outputs.get("writer")
        if writer and writer.success:
            result.proposal = ProposalOutput(
                proposal_markdown=writer.output.get("proposal_markdown", writer.raw_text),
                email_subject=writer.output.get("email_subject", ""),
                email_body=writer.output.get("email_body", ""),
            )

        return result

    def save_results(self, result: PipelineResult, output_dir: str = OUTPUTS_DIR) -> dict[str, str]:
        """Save pipeline results to files."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = result.timestamp
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", result.target_company)[:40]
        paths = {}

        # Save proposal
        if result.proposal and result.proposal.proposal_markdown:
            proposal_path = os.path.join(output_dir, f"proposal_{safe_name}_{timestamp}.md")
            with open(proposal_path, "w") as f:
                f.write(result.proposal.proposal_markdown)
            paths["proposal"] = proposal_path

        # Save full pipeline output (debug)
        debug_data = {
            "target_company": result.target_company,
            "timestamp": timestamp,
            "total_tokens_in": result.total_tokens_in,
            "total_tokens_out": result.total_tokens_out,
            "total_duration_seconds": result.total_duration_seconds,
            "agent_outputs": {
                name: {"success": ar.success, "raw_text": ar.raw_text[:2000], "tokens_in": ar.tokens_in, "tokens_out": ar.tokens_out}
                for name, ar in result.agent_results.items()
            },
        }
        debug_path = os.path.join(output_dir, f"pipeline_{safe_name}_{timestamp}.json")
        with open(debug_path, "w") as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)
        paths["debug"] = debug_path

        return paths


# ── Convenience functions (backward-compatible with old agents.py) ──


def run_pipeline(company_input: str, output_dir: str = OUTPUTS_DIR) -> dict:
    """Run the full pipeline — backward-compatible with old agents.run_pipeline()."""
    orchestrator = Orchestrator(interactive=True)
    result = orchestrator.execute(company_input)
    paths = orchestrator.save_results(result, output_dir)

    # Return dict matching old interface
    return {
        "research": result.research_brief.raw_brief if result.research_brief else "",
        "solution_map": result.solution_map.raw_solution_map if result.solution_map else "",
        "proposal": result.proposal.proposal_markdown if result.proposal else "",
        "proposal_path": paths.get("proposal", ""),
        "debug_path": paths.get("debug", ""),
        "result": result,
    }


def run_researcher(company_input: str) -> str:
    """Run just the researcher — backward-compatible."""
    cm = ContextManager()
    from agents.researcher import ResearcherAgent

    agent = ResearcherAgent(cm)
    context = cm.build_context_packet(
        task_description=company_input,
        relevant_data={},
        company_config=COMPANY_CONFIG,
    )
    result = agent.run(context)
    return result.raw_text


def run_architect(research_brief: str) -> str:
    """Run just the architect — backward-compatible."""
    cm = ContextManager()
    from agents.architect import ArchitectAgent

    agent = ArchitectAgent(cm)
    context = cm.build_context_packet(
        task_description="Map the prospect's pain points to specific product features.",
        relevant_data={},
        prior_summaries=[research_brief],
        company_config=COMPANY_CONFIG,
    )
    result = agent.run(context)
    return result.raw_text


def run_proposal_writer(research_brief: str, solution_map: str, company_name: str) -> str:
    """Run just the writer — backward-compatible."""
    cm = ContextManager()
    from agents.writer import WriterAgent

    agent = WriterAgent(cm)
    context = cm.build_context_packet(
        task_description=f"Create a sales proposal and cold email for {company_name}.",
        relevant_data={"company_name": company_name},
        prior_summaries=[research_brief, solution_map],
        company_config=COMPANY_CONFIG,
    )
    result = agent.run(context)
    return result.output.get("proposal_markdown", result.raw_text)


def run_deal_estimator(company_brief: str) -> str:
    """Run just the scorer — backward-compatible."""
    cm = ContextManager()
    from agents.scorer import ScorerAgent

    agent = ScorerAgent(cm)
    context = cm.build_context_packet(
        task_description=f"Estimate the deal size for this prospect:\n\n{company_brief}",
        relevant_data={},
        company_config=COMPANY_CONFIG,
    )
    result = agent.run(context)
    return result.raw_text


def run_email_writer(research_brief: str, deal_context: str) -> str:
    """Run just the writer for email — backward-compatible."""
    cm = ContextManager()
    from agents.writer import WriterAgent

    agent = WriterAgent(cm)
    context = cm.build_context_packet(
        task_description="Write a personalized cold email for this prospect.",
        relevant_data={"deal_context": deal_context},
        prior_summaries=[research_brief],
        company_config=COMPANY_CONFIG,
    )
    result = agent.run(context)
    email_body = result.output.get("email_body", "")
    email_subject = result.output.get("email_subject", "")
    if email_subject and email_body:
        return f"Subject: {email_subject}\n\n{email_body}"
    return result.raw_text


def run_quick_summary(company_brief: str, deal_json: str) -> str:
    """Run a quick fit assessment — backward-compatible."""
    from agents.scorer import QuickSummaryMixin

    from anthropic import Anthropic

    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0.5,
        system=QuickSummaryMixin.QUICK_SUMMARY_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Summarize this prospect's fit in 3-8 sentences.\n\n"
                       f"=== COMPANY INFO ===\n{company_brief}\n\n"
                       f"=== DEAL ESTIMATE ===\n{deal_json}",
        }],
    )
    return response.content[0].text
