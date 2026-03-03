"""
Researcher Agent — Multi-turn agentic research with tool use.

The only truly multi-turn agent. Uses search, scraping, and knowledge
base tools autonomously. Context is pruned between turns.

Ported from agents.py:call_agentic_researcher() with added context management.
"""

from __future__ import annotations

import json

from anthropic import APIError

from agents.base import BaseAgent
from context import ContextManager
from models import AgentResult, AgentRole, ContextPacket
from tools.knowledge_query import KnowledgeQueryTool
from tools.web_scraper import WebScraperTool
from tools.web_search import WebSearchTool

# Legacy fallback system prompt (no tools)
LEGACY_RESEARCHER_PROMPT = """You are a B2B sales researcher specializing in the manufacturing industry.
Your job is to analyze a target company and produce a structured research brief that
a solutions architect can use to recommend smart factory products.

Given a company name and description, you must research and infer:

1. **Company Overview**: What they manufacture, their scale, and market position
2. **Manufacturing Process**: What equipment they likely use
3. **Energy Profile**: Estimated energy consumption patterns
4. **Pain Points**: Based on their industry, what problems they likely face
5. **ESG Exposure**: Whether they face regulatory pressure
6. **Decision Factors**: What would matter most when evaluating a monitoring solution

Output your research as a structured brief with clear sections.
Be specific to their industry — don't be generic.
"""


class ResearcherAgent(BaseAgent):
    role = AgentRole.RESEARCHER
    prompt_file = "researcher.md"
    temperature = 0.6
    max_turns = 5

    def __init__(self, context_manager: ContextManager | None = None):
        super().__init__(context_manager)
        self.web_search = WebSearchTool()
        self.web_scraper = WebScraperTool()
        self.knowledge_query = KnowledgeQueryTool()
        self.tools = [
            self.web_search.get_tool_definition(),
            self.web_scraper.get_tool_definition(),
            self.knowledge_query.get_tool_definition(),
        ]

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Dispatch a tool call to the actual function."""
        if tool_name == "search_web":
            return self.web_search.run(query=tool_input.get("query", ""))
        elif tool_name == "query_knowledge_base":
            return self.knowledge_query.run(query=tool_input.get("query", ""))
        elif tool_name == "scrape_company_website":
            return self.web_scraper.run(url=tool_input.get("url", ""))
        else:
            return f"Unknown tool: {tool_name}"

    def execute(self, context: ContextPacket) -> AgentResult:
        """Multi-turn agentic research loop with context pruning."""
        system_prompt = self.build_system_prompt(context)
        user_message = self.build_user_message(context)

        # Build initial user message for research
        research_prompt = (
            f"Research this target company for a smart manufacturing sales engagement:\n\n"
            f"{user_message}\n\n"
            f"Use your tools to gather real information. Start by checking the knowledge base "
            f"for any past outreach to similar companies, then search the web and scrape "
            f"their website if a URL is available. Produce a detailed research brief."
        )

        messages = [{"role": "user", "content": research_prompt}]
        total_in = 0
        total_out = 0

        try:
            return self._agentic_loop(system_prompt, messages, total_in, total_out)
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            # Fallback to legacy single-turn mode
            print(f"\n  Warning: Agentic research failed ({e}). Falling back to legacy mode.")
            return self._legacy_research(context, user_message)

    def _agentic_loop(
        self, system_prompt: str, messages: list, total_in: int, total_out: int
    ) -> AgentResult:
        """Run the multi-turn tool-use loop."""
        for turn in range(self.max_turns):
            print(f"  Turn {turn + 1}/{self.max_turns}")

            # Prune context if needed
            messages = self.context_manager.prune_messages(messages)

            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    tools=self.tools,
                    messages=messages,
                )
            except APIError as e:
                error_msg = str(e)
                if "credit balance" in error_msg.lower() or "billing" in error_msg.lower():
                    print("Error: API billing — credit balance is too low.")
                    raise SystemExit(1)
                elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                    print("Error: API key invalid.")
                    raise SystemExit(1)
                else:
                    raise

            total_in += response.usage.input_tokens
            total_out += response.usage.output_tokens

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_id = block.id
                        print(f"  Tool: {tool_name}({json.dumps(tool_input)[:80]})")

                        result = self._execute_tool(tool_name, tool_input)

                        # Summarize tool results instead of blind truncation
                        result = self.context_manager.summarize_tool_result(tool_name, result)
                        print(f"  Result: {result[:80]}")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # Final text response
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                print(f"  Research complete ({total_in} in / {total_out} out, {turn + 1} turns)")
                return AgentResult(
                    agent=self.role,
                    success=True,
                    raw_text=final_text,
                    tokens_in=total_in,
                    tokens_out=total_out,
                )

        # Hit max turns — ask for final summary
        print(f"  Max turns ({self.max_turns}) reached. Extracting final response.")
        messages.append({
            "role": "user",
            "content": (
                "You've used all available research turns. Please now produce your "
                "final structured research brief based on everything you've gathered."
            ),
        })

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=messages,
            )
            total_in += response.usage.input_tokens
            total_out += response.usage.output_tokens
            final_text = response.content[0].text

            return AgentResult(
                agent=self.role,
                success=True,
                raw_text=final_text,
                tokens_in=total_in,
                tokens_out=total_out,
            )
        except APIError:
            return AgentResult(
                agent=self.role,
                success=False,
                error=f"Failed to get summary after {self.max_turns} turns",
                tokens_in=total_in,
                tokens_out=total_out,
            )

    def _legacy_research(self, context: ContextPacket, user_message: str) -> AgentResult:
        """Fallback: single-turn research without tools."""
        prompt = (
            f"Research this target company for a smart manufacturing sales engagement:\n\n"
            f"{user_message}\n\n"
            f"Produce a detailed research brief covering: company overview, manufacturing "
            f"processes, energy profile, likely pain points, ESG exposure, and key decision "
            f"factors. Be specific to their industry and operations."
        )

        response, tokens_in, tokens_out = self.call_llm(LEGACY_RESEARCHER_PROMPT, prompt)
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        return AgentResult(
            agent=self.role,
            success=True,
            raw_text=raw_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
