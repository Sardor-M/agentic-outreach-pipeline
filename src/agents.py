"""
Agentic Pipeline — Agent Orchestration
Claude API agents with RAG knowledge base and agentic tool-use

Agents:
1. Prospect Researcher (agentic) - multi-turn tool-use: web search, KB query, website scraping
2. Solution Architect - maps problems to MV900 + Machine365.Ai features
3. Proposal Writer - generates personalized sales proposal
4. Deal Estimator - estimates deal size as structured JSON
5. Cold Email Writer - writes personalized cold outreach emails
"""

import os
import json
import re
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic, APIError

from pathlib import Path

from knowledge import get_full_product_context, COMBINED_SOLUTION, COMPANY_PROFILE
from prospector import search_companies
from scraper import scrape_website

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = str(PROJECT_ROOT / "outputs")

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

client = Anthropic()  # reads ANTHROPIC_API_KEY from environment
MODEL = "claude-sonnet-4-20250514"


def call_agent(
    system_prompt: str,
    user_message: str,
    agent_name: str,
    temperature: float = 0.7,
) -> str:
    """Call Claude API as a specific agent."""
    print(f"\n{'='*60}")
    print(f"🤖 Agent: {agent_name}")
    print(f"{'='*60}")
    print(f"📨 Task: {user_message[:120]}...")
    print(f"⏳ Working...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            result = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            print(f"✅ Done ({tokens_in} in / {tokens_out} out tokens)")
            return result
        except APIError as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower() or "overloaded" in error_msg.lower():
                wait = 2 ** attempt * 10  # 10s, 20s, 40s
                if attempt < max_retries - 1:
                    print(f"⏳ Rate limited. Waiting {wait}s before retry ({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                else:
                    print(f"❌ Rate limit persists after {max_retries} retries. Try again in a few minutes.")
                    raise SystemExit(1)
            elif "credit balance" in error_msg.lower() or "billing" in error_msg.lower():
                print(f"❌ API billing error: Your Anthropic credit balance is too low.")
                print(f"   Go to https://console.anthropic.com/settings/billing to add credits.")
            elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                print(f"❌ API key invalid. Check ANTHROPIC_API_KEY in your .env file.")
            else:
                print(f"❌ API error: {error_msg}")
            raise SystemExit(1)
    raise SystemExit(1)  # should not reach here


# ─────────────────────────────────────────────
# Agent 1: Prospect Researcher
# ─────────────────────────────────────────────

RESEARCHER_SYSTEM_LEGACY = """You are a B2B sales researcher specializing in the manufacturing industry.
Your job is to analyze a target company and produce a structured research brief that
a solutions architect can use to recommend smart factory products.

Given a company name and description, you must research and infer:

1. **Company Overview**: What they manufacture, their scale, and market position
2. **Manufacturing Process**: What equipment they likely use (presses, forming machines, injection molding, etc.)
3. **Energy Profile**: Estimated energy consumption patterns, likely electricity costs as % of operating costs
4. **Pain Points**: Based on their industry, what problems they likely face:
   - Energy cost challenges
   - Quality/defect issues
   - Equipment maintenance challenges
   - ESG/sustainability pressures
   - Production visibility gaps
5. **ESG Exposure**: Whether they face regulatory pressure (EU taxonomy, carbon reporting, etc.)
6. **Decision Factors**: What would matter most to them when evaluating a monitoring solution

Output your research as a structured brief with clear sections.
Be specific to their industry — don't be generic.
If you don't know exact facts, make reasonable inferences based on the industry and state them as inferences.
"""

AGENTIC_RESEARCHER_SYSTEM = """You are a B2B sales researcher specializing in the manufacturing industry.
You work for 3View Inc., a South Korean smart manufacturing company selling MV900 hardware
and Machine365.Ai software to factories worldwide.

Your job is to ACTIVELY RESEARCH a target company using the tools available to you,
then produce a structured research brief for a solutions architect.

YOU HAVE 3 TOOLS:
1. **search_web** — search the internet for company info, industry data, news
2. **query_knowledge_base** — search 3View's product knowledge and past outreach history
3. **scrape_company_website** — fetch and read a company's website for details

RESEARCH STRATEGY:
- Start by querying the knowledge base for any past outreach to similar companies
- If you have a company URL, scrape their website for details about what they do
- Search the web for additional info: company size, products, recent news, ESG initiatives
- Query the knowledge base again for relevant product features and case studies
- You do NOT need to use all tools — use what makes sense for the prospect

After researching, produce a structured brief with:
1. **Company Overview**: What they manufacture, scale, market position
2. **Manufacturing Process**: Equipment they use (from website/search, not guessing)
3. **Energy Profile**: Energy consumption patterns, electricity costs
4. **Pain Points**: Specific problems based on your ACTUAL research findings
5. **ESG Exposure**: Regulatory pressure (EU taxonomy, carbon reporting, etc.)
6. **Decision Factors**: What would matter most when evaluating a monitoring solution
7. **3View Relevance**: Any past outreach or relevant case studies from the knowledge base

Be specific. Cite what you found from each source. Don't fabricate facts.
If you couldn't find something, say so and make a clearly-labeled inference.
"""

RESEARCHER_TOOLS = [
    {
        "name": "search_web",
        "description": (
            "Search the web using DuckDuckGo. Use this to find information about "
            "the target company, their industry, recent news, and competitors. "
            "Returns a list of search results with titles, URLs, and snippets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific — include company name, industry, or topic.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_knowledge_base",
        "description": (
            "Search 3View's internal knowledge base. Contains product information "
            "(MV900, Machine365.Ai), case studies, ideal customer profiles, ROI data, "
            "and records of past outreach to other companies. Use this to find relevant "
            "product features, similar past deals, and case studies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Semantic search query. E.g., 'energy monitoring for forging companies' or 'past outreach automotive stamping'.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "scrape_company_website",
        "description": (
            "Fetch and read the text content of a web page. Use this to read a "
            "company's website and learn about their products, operations, and scale. "
            "Returns clean text (HTML stripped), truncated to ~4000 characters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to scrape (must start with http:// or https://).",
                },
            },
            "required": ["url"],
        },
    },
]


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call to the actual function. Returns result as string."""
    if tool_name == "search_web":
        query = tool_input.get("query", "")
        results = search_companies(query, max_results=5)
        if not results:
            return "No search results found."
        parts = []
        for r in results:
            parts.append(
                f"- {r['title']}\n  URL: {r['url']}\n  {r['snippet']}"
            )
        return "\n".join(parts)

    elif tool_name == "query_knowledge_base":
        query = tool_input.get("query", "")
        try:
            from rag import query_knowledge_base
            return query_knowledge_base(query, n_results=3)
        except Exception as e:
            return f"Knowledge base unavailable: {e}"

    elif tool_name == "scrape_company_website":
        url = tool_input.get("url", "")
        return scrape_website(url)

    else:
        return f"Unknown tool: {tool_name}"


def call_agentic_researcher(company_input: str, max_turns: int = 5) -> str:
    """
    Multi-turn agentic researcher using Claude tool_use.

    The researcher autonomously decides which tools to call and in what order.
    Loops until the model returns a final text response (no more tool calls)
    or max_turns is reached.
    """
    print(f"\n{'='*60}")
    print(f"🤖 Agent: Agentic Researcher")
    print(f"{'='*60}")
    print(f"📨 Target: {company_input[:120]}...")
    print(f"🔧 Tools: search_web, query_knowledge_base, scrape_company_website")
    print(f"🔄 Max turns: {max_turns}")

    messages = [
        {
            "role": "user",
            "content": (
                f"Research this target company for a smart manufacturing sales engagement:\n\n"
                f"{company_input}\n\n"
                f"Use your tools to gather real information. Start by checking the knowledge base "
                f"for any past outreach to similar companies, then search the web and scrape "
                f"their website if a URL is available. Produce a detailed research brief."
            ),
        },
    ]

    total_in = 0
    total_out = 0

    for turn in range(max_turns):
        print(f"\n  ── Turn {turn + 1}/{max_turns} ──")

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                temperature=0.6,
                system=AGENTIC_RESEARCHER_SYSTEM,
                tools=RESEARCHER_TOOLS,
                messages=messages,
            )
        except APIError as e:
            error_msg = str(e)
            if "credit balance" in error_msg.lower() or "billing" in error_msg.lower():
                print(f"❌ API billing error: Your Anthropic credit balance is too low.")
                raise SystemExit(1)
            elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                print(f"❌ API key invalid. Check ANTHROPIC_API_KEY in your .env file.")
                raise SystemExit(1)
            else:
                print(f"❌ API error: {error_msg}")
                raise SystemExit(1)

        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens

        # Check if the model wants to use tools
        if response.stop_reason == "tool_use":
            # Process all tool calls in this response
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_id = block.id
                    print(f"  🔧 Tool: {tool_name}({json.dumps(tool_input)[:80]})")

                    result = _execute_tool(tool_name, tool_input)
                    # Truncate very long results
                    if len(result) > 3000:
                        result = result[:3000] + "\n\n[...truncated]"
                    print(f"  📋 Result: {result[:100]}...")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result,
                    })

            # Add assistant message + tool results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            # Model returned a final text response — we're done
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            print(f"\n✅ Research complete ({total_in} in / {total_out} out tokens, {turn + 1} turns)")
            return final_text

    # If we hit max_turns, extract whatever text we have
    print(f"\n⚠️ Hit max turns ({max_turns}). Extracting final response...")
    # Ask for a final summary
    messages.append({
        "role": "user",
        "content": (
            "You've used all available research turns. Please now produce your "
            "final structured research brief based on everything you've gathered."
        ),
    })

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            temperature=0.6,
            system=AGENTIC_RESEARCHER_SYSTEM,
            messages=messages,
        )
        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens
        final_text = response.content[0].text
        print(f"✅ Research complete ({total_in} in / {total_out} out tokens, {max_turns}+ turns)")
        return final_text
    except APIError:
        print(f"❌ Failed to get final summary after {max_turns} turns.")
        raise SystemExit(1)


def run_researcher(company_input: str) -> str:
    """Agent 1: Research the prospect company using agentic tool-use."""
    try:
        return call_agentic_researcher(company_input)
    except SystemExit:
        raise
    except Exception as e:
        # Fallback to legacy single-turn if agentic fails
        print(f"\n⚠️ Agentic researcher failed ({e}). Falling back to legacy mode.")
        return call_agent(
            system_prompt=RESEARCHER_SYSTEM_LEGACY,
            user_message=f"""Research this target company for a smart manufacturing sales engagement:

{company_input}

Produce a detailed research brief covering: company overview, manufacturing processes,
energy profile, likely pain points, ESG exposure, and key decision factors.
Be specific to their industry and operations.""",
            agent_name="Prospect Researcher (Legacy)",
            temperature=0.6,
        )


# ─────────────────────────────────────────────
# Agent 2: Solution Architect
# ─────────────────────────────────────────────

ARCHITECT_SYSTEM = f"""You are a solutions architect at 3View Inc., a South Korean smart manufacturing company.
You are an expert on exactly TWO products:

{get_full_product_context()}

Your job is to take a research brief about a prospect company and create a detailed
solution mapping that shows EXACTLY which features of MV900 and Machine365.Ai solve
their specific problems.

For each pain point identified in the research:
1. Map it to specific product features (cite the exact feature name)
2. Explain HOW it solves their problem (not just that it does)
3. Estimate the impact using our typical ROI numbers
4. Recommend whether they need MV900 only, Machine365.Ai only, or both

Your output should be a structured solution map with:
- Recommended configuration (MV900 / Machine365.Ai / Both)
- Pain point → Solution mapping (specific features for each problem)
- Implementation approach (phased or full deployment)
- Estimated ROI breakdown
- Relevant case study references

Be precise. Reference exact product features. Don't make up capabilities that aren't listed above.
"""


def run_architect(research_brief: str) -> str:
    """Agent 2: Map prospect problems to 3View solutions."""
    return call_agent(
        system_prompt=ARCHITECT_SYSTEM,
        user_message=f"""Based on this prospect research brief, create a detailed solution mapping
using ONLY MV900 and Machine365.Ai features.

=== PROSPECT RESEARCH BRIEF ===
{research_brief}

Map each identified pain point to specific product features.
Recommend the optimal configuration and estimate ROI.""",
        agent_name="Solution Architect",
        temperature=0.5,
    )


# ─────────────────────────────────────────────
# Agent 3: Proposal Writer
# ─────────────────────────────────────────────

PROPOSAL_SYSTEM = f"""You are a professional B2B proposal writer for 3View Inc.
You create personalized, compelling sales proposals for manufacturing companies.

Company context:
{get_full_product_context()}

Your job is to take the prospect research and solution mapping, and produce a
polished, professional sales proposal in Markdown format.

The proposal must follow this EXACT structure:

# Smart Manufacturing Proposal for [Company Name]
## Prepared by 3View Inc.

### Executive Summary
(2-3 paragraphs: their situation, our understanding, our recommended solution)

### Understanding Your Challenges
(List their specific pain points — show you understand their business)

### Recommended Solution
(What we recommend: MV900, Machine365.Ai, or both — and WHY)

#### MV900: Real-Time Process Monitoring
(Only if recommended — specific benefits for THEIR factory)

#### Machine365.Ai: Integrated Equipment Intelligence
(Only if recommended — specific benefits for THEIR operations)

### How It Works Together
(If both recommended — explain the synergy for their specific case)

### Expected Impact
(ROI table with their specific numbers/estimates)

| Area | Current Challenge | Expected Improvement |
|------|------------------|---------------------|

### Implementation Approach
(Phased rollout recommendation)

### Relevant Success Stories
(Reference our case studies that match their industry)

### Next Steps
(Clear call to action)

### About 3View
(Brief company credentials)
- Contact: 3viewsales@e3view.com | +82-31-776-0677
- Web: https://e3view.com

RULES:
- Write in professional but warm English
- Be specific to THEIR company — no generic language
- Every claim must tie back to actual product features
- Include specific numbers where possible (use estimates if needed)
- Keep it to 2-3 pages equivalent in markdown
- Make it ready to send as-is (no placeholders)
"""


def run_proposal_writer(research_brief: str, solution_map: str, company_name: str) -> str:
    """Agent 3: Generate the final proposal."""
    return call_agent(
        system_prompt=PROPOSAL_SYSTEM,
        user_message=f"""Create a professional sales proposal for this prospect.

=== COMPANY NAME ===
{company_name}

=== PROSPECT RESEARCH ===
{research_brief}

=== SOLUTION MAPPING ===
{solution_map}

Write a polished, ready-to-send proposal in Markdown format.
Make it specific to this company — no generic filler.""",
        agent_name="Proposal Writer",
        temperature=0.7,
    )


# ─────────────────────────────────────────────
# Agent 4: Deal Estimator
# ─────────────────────────────────────────────

DEAL_ESTIMATOR_SYSTEM = f"""You are a deal sizing specialist at 3View Inc.
You estimate potential deal value based on a company research brief.

{COMPANY_PROFILE}

INTERNAL PRICING GUIDELINES (approximate):
- MV900 hardware unit: $8,000 - $12,000 per machine (volume discounts apply)
- Machine365.Ai platform license: $2,000 - $5,000/month depending on machine count
- Implementation & setup: $15,000 - $50,000 one-time
- Annual support & maintenance: 15-20% of hardware cost

DEAL CATEGORIES:
- Small: < $100,000 first-year value (< 20 machines)
- Medium: $100,000 - $400,000 first-year value (20-100 machines)
- Enterprise: > $400,000 first-year value (100+ machines)

Given a company research brief, estimate the deal. Output ONLY valid JSON with this exact structure:
{{
  "company_name": "...",
  "industry": "...",
  "estimated_machines": <number>,
  "recommended_solution": "MV900 only" | "Machine365.Ai only" | "MV900 + Machine365.Ai",
  "first_year_value": <number>,
  "annual_recurring": <number>,
  "deal_category": "Small" | "Medium" | "Enterprise",
  "confidence": "Low" | "Medium" | "High",
  "reasoning": "1-2 sentence explanation"
}}

Output ONLY the JSON object. No markdown, no code fences, no extra text.
"""


def run_deal_estimator(company_brief: str) -> str:
    """Agent 4: Estimate deal size for a prospect."""
    return call_agent(
        system_prompt=DEAL_ESTIMATOR_SYSTEM,
        user_message=f"""Estimate the deal size for this prospect:

{company_brief}

Output only valid JSON with the deal estimate.""",
        agent_name="Deal Estimator",
        temperature=0.3,
    )


# ─────────────────────────────────────────────
# Agent 5: Cold Email Writer
# ─────────────────────────────────────────────

COLD_EMAIL_SYSTEM = f"""You are a professional cold email writer for 3View Inc., a South Korean smart manufacturing company.

{get_full_product_context()}

Write a short, personalized cold outreach email (5-8 short paragraphs).

RULES:
- Subject line must reference their specific industry or challenge
- Opening: reference something specific about THEIR company (from the research brief)
- Middle: briefly explain how 3View solves their specific problem (1-2 features max)
- Include one concrete number (ROI stat, case study result)
- Close with a soft CTA (suggest a 15-minute call, not a demo)
- Sign off as the 3View sales team
- Professional but conversational — NOT salesy or pushy
- Plain text only — no HTML, no markdown formatting
- Keep total length under 200 words

Output format:
Subject: [subject line]

[email body]

Best regards,
3View Sales Team
3viewsales@e3view.com | +82-31-776-0677
https://e3view.com
"""


def run_email_writer(research_brief: str, deal_context: str) -> str:
    """Agent 5: Write a personalized cold email."""
    return call_agent(
        system_prompt=COLD_EMAIL_SYSTEM,
        user_message=f"""Write a personalized cold email for this prospect.

=== COMPANY RESEARCH ===
{research_brief}

=== DEAL CONTEXT ===
{deal_context}

Write a short, personalized cold email. Plain text only.""",
        agent_name="Cold Email Writer",
        temperature=0.7,
    )


# ─────────────────────────────────────────────
# Pipeline Orchestrator
# ─────────────────────────────────────────────

def run_pipeline(company_input: str, output_dir: str = OUTPUTS_DIR) -> dict:
    """
    Run the full 3-agent sales pipeline.
    
    Args:
        company_input: Description of the target company
        output_dir: Directory to save the proposal
    
    Returns:
        dict with research, solution_map, proposal, and file path
    """
    print("\n" + "🏭" * 30)
    print("  3VIEW MACHINE365 SALES AGENT PIPELINE")
    print("🏭" * 30)
    print(f"\n📋 Target: {company_input}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Extract company name (first line or first few words)
    company_name = company_input.split(",")[0].split("\n")[0].strip()

    # ── Agent 1: Research ──
    research = run_researcher(company_input)

    # ── Agent 2: Solution Mapping ──
    solution_map = run_architect(research)

    # ── Agent 3: Proposal ──
    proposal = run_proposal_writer(research, solution_map, company_name)

    # ── Save outputs ──
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", company_name)[:40]

    # Save proposal
    proposal_path = os.path.join(output_dir, f"proposal_{safe_name}_{timestamp}.md")
    with open(proposal_path, "w") as f:
        f.write(proposal)

    # Save full pipeline output (for debugging / article)
    full_output = {
        "company_input": company_input,
        "company_name": company_name,
        "timestamp": timestamp,
        "agent_outputs": {
            "researcher": research,
            "architect": solution_map,
            "proposal_writer": proposal,
        },
    }
    debug_path = os.path.join(output_dir, f"pipeline_{safe_name}_{timestamp}.json")
    with open(debug_path, "w") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"✅ PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"📄 Proposal saved: {proposal_path}")
    print(f"🔍 Debug output:   {debug_path}")
    print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return {
        "research": research,
        "solution_map": solution_map,
        "proposal": proposal,
        "proposal_path": proposal_path,
        "debug_path": debug_path,
    }
