# Agentic Outreach Pipeline

An AI-powered B2B sales pipeline that automates company research, competitive analysis, deal estimation, proposal generation, and cold email outreach. Built with a multi-agent orchestrator pattern, Claude (Anthropic), agentic tool-use, structured I/O, and real-time streaming.

## What It Does

Five specialized Claude AI agents collaborate through a central orchestrator, each with isolated context and structured inputs/outputs:

```
                          ┌──────────────────────────┐
                          │    Knowledge Subsystem    │
                          │  Product YAML + ChromaDB  │
                          │  Semantic search + history │
                          └────────────┬─────────────┘
                                       │
               ┌───────────────────────┼───────────────────────┐
               │                       │                       │
     ┌─────────v──────────┐  ┌────────v─────────┐  ┌─────────v──────────┐
     │   search_web       │  │ query_knowledge  │  │ scrape_company     │
     │   (DuckDuckGo)     │  │     _base        │  │   _website         │
     └─────────┬──────────┘  └────────┬─────────┘  └─────────┬──────────┘
               │                      │                      │
               └──────────────────────┼──────────────────────┘
                                      │
                           ┌──────────v──────────┐
                           │  Agentic Researcher │
                           │  (multi-turn loop)  │
                           └──────────┬──────────┘
                                      │ Research Brief
                     ┌────────────────┼────────────────┐
                     │                │                │
               ┌─────v─────┐   ┌─────v─────┐         │
               │  Analyst   │   │ Architect  │         │
               │ (optional) │   │ (required) │         │
               └─────┬─────┘   └─────┬─────┘         │
                     │    parallel    │                │
                     └────────┬───────┘                │
                              │                        │
                        ┌─────v─────┐                  │
                        │  Scorer   │                  │
                        │ (optional)│                  │
                        └─────┬─────┘                  │
                              │                        │
                        ┌─────v─────┐                  │
                        │  Writer   │◄─────────────────┘
                        │ (required)│
                        └─────┬─────┘
                              │
                    Proposal + Cold Email
```

### Single Proposal Mode

Generate a detailed multi-page sales proposal with a cold email:

```
Company Input → Researcher → Analyst + Architect (parallel)
→ Scorer → Writer → Proposal + Email
```

### Prospect Search Mode

Search for companies, qualify prospects, then generate batch proposals and emails:

```
Search Query → DuckDuckGo → Deal Estimator → Prospect Table
→ User Selection → Full Pipeline per Company → Gmail Send
```

## Architecture

### Orchestrator Pattern

The orchestrator follows a **plan → dispatch → aggregate** pattern inspired by Claude Code:

1. **Plan**: Generate a `PipelinePlan` with steps, parallel groups, dependencies, and criticality levels
2. **Execute**: Dispatch sub-agents per plan — each receives a curated `ContextPacket` (no raw text dumps)
3. **Aggregate**: Collect structured results into a `PipelineResult`

Context rot is solved by:
- Each agent gets **fresh context** (no inherited conversation history)
- Agent outputs are **summarized via Claude Haiku** before handoff (not passed raw)
- Only **relevant data** goes to each agent (e.g., Writer doesn't get raw scraped pages)

### The Five Agents

| # | Agent | Type | Temp | Tools | Purpose |
|---|-------|------|------|-------|---------|
| 1 | **Researcher** | Multi-turn agentic | 0.6 | search_web, scrape_website, query_kb | Autonomous company research with reflection |
| 2 | **Analyst** | Single-turn | 0.5 | — | Competitive landscape and financial analysis |
| 3 | **Architect** | Single-turn | 0.5 | — | Map pain points to product features + ROI |
| 4 | **Scorer** | Single-turn (tool_choice) | 0.3 | submit_deal_estimate | Structured deal estimation (guaranteed JSON) |
| 5 | **Writer** | Single-turn (tool_choice) | 0.7 | submit_proposal | Proposal + cold email generation |

Only the Researcher is agentic (multi-turn tool-use). The other agents are single-turn — they receive enriched context from prior agents and don't need tools. Scorer and Writer use Claude's `tool_choice` for **guaranteed structured output** (no regex parsing).

### Agentic Research Loop

The Researcher autonomously decides which tools to call and in what order (up to 5 turns, configurable):

```
Turn 1: query_knowledge_base("past outreach similar companies")
Turn 2: scrape_company_website("https://company.com")
Turn 3: search_web("company manufacturing details")
Turn 4: query_knowledge_base("relevant case studies energy")
Turn 5: Reflection → Final structured research brief
```

Features:
- **Reflection**: On the second-to-last turn, reviews research, rates confidence, identifies gaps
- **Context pruning**: Messages are summarized between turns to prevent context overflow
- **Checkpointing**: State saved after each turn — recovers partial results on failure
- **Configurable depth**: `quick` (2 turns), `standard` (5), `deep` (8) via `config/company.yaml`

### Knowledge Subsystem

The knowledge subsystem provides product information, case studies, and past outreach history to agents via **ChromaDB vector search**:

- **Product knowledge**: Loaded from `config/products.yaml` — product features, specs, benefits, case studies, ideal customer profiles, ROI data. Auto-seeded into ChromaDB (~17 chunks), re-seeded when config changes (tracked via MD5 hash)
- **Company config**: Loaded from `config/company.yaml` — company profile, pricing guidelines, research depth
- **Extracted facts**: Structured facts extracted from web pages via regex patterns (or LangExtract/Gemini if available)
- **Outreach history**: Past pipeline runs automatically indexed into ChromaDB after each run — the system learns from its own outreach
- **Semantic search**: ChromaDB with all-MiniLM-L6-v2 embeddings enables true semantic matching — e.g., "power consumption analysis" matches "energy monitoring for stamping" even with no shared words
- **3 collections**: `product_knowledge`, `company_facts`, `outreach_history`
- **Hybrid fallback**: If ChromaDB is unavailable, falls back to keyword search

### Structured Output

Scorer and Writer use Claude's native `tool_choice` to guarantee valid JSON output:

```python
# Scorer forces structured deal estimation
response = client.messages.create(
    tools=[DEAL_ESTIMATE_TOOL],
    tool_choice={"type": "tool", "name": "submit_deal_estimate"},
)
# response.content[0].input is guaranteed valid JSON
```

No regex parsing, no JSON extraction heuristics — type-safe end-to-end.

### Error Recovery

- **Criticality levels**: Each pipeline step is `required` or `optional` — optional agents can fail without stopping the pipeline
- **Fallback models**: Analyst and Scorer fall back to Claude Haiku if Sonnet fails
- **Researcher checkpointing**: If the researcher fails on turn 4 of 5, partial results from turn 3 are recovered
- **Legacy fallback**: If all agentic research fails, falls back to single-turn inference mode

### Cost Tracking

Thread-safe `CostTracker` monitors API spend per pipeline:
- Per-agent cost breakdown (input/output tokens at model-specific rates)
- Budget guards — pipeline stops before next agent group if budget exceeded
- Cost report attached to every `PipelineResult`

### Observability

- **Structured logging**: `structlog` with ISO timestamps, log levels, JSON or console rendering
- **Trace files**: Every pipeline run saves `trace_*.json` with per-agent timing and token counts
- **Streaming events**: Real-time `on_event` callbacks for CLI (Rich) and Streamlit progress display

## Setup

### Prerequisites

- Python 3.13 (ChromaDB requires <=3.13; does not work on 3.14)
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Clone and create virtual environment

```bash
git clone https://github.com/Sardor-M/agentic-outreach-pipeline.git
cd agentic-outreach-pipeline
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** On first run, ChromaDB downloads the all-MiniLM-L6-v2 embedding model (~80MB) to `~/.cache/chroma/`. This is a one-time download.

### 3. Configure environment variables

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Gmail integration for sending outreach emails
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Optional: Google Custom Search API (enhances web search)
GOOGLE_API_KEY=
GOOGLE_CSE_ID=

# Optional: Logging
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=console      # console or json
```

**Gmail App Password**: Go to [Google App Passwords](https://myaccount.google.com/apppasswords), generate a new app password, and paste it above. This is NOT your regular Gmail password.

## Usage

### Generate a Proposal

```bash
python src/main.py proposal "Mueller Automotive GmbH, Germany"
python src/main.py proposal "Pacific Brass & Copper, California, USA, 40+ forging machines"
```

**What happens:**
1. Researcher autonomously gathers information (web search, website scraping, knowledge base queries)
2. Analyst + Architect run in parallel (competitive analysis + solution mapping)
3. Scorer estimates deal size as structured JSON
4. Writer generates a polished Markdown proposal + cold email
5. Results saved to `outputs/`

### Search & Outreach

```bash
python src/main.py search "metal stamping companies Germany"
python src/main.py search "automotive parts manufacturer Japan"
```

**What happens:**
1. DuckDuckGo finds 5-10 matching companies
2. Contact info extracted (emails, phone numbers)
3. Deal Estimator sizes each opportunity
4. Rich table displayed — pick companies to pursue
5. Full pipeline runs for each selected prospect
6. Cold emails generated and previewed
7. Confirm before sending via Gmail (or skip)
8. Results saved to `outputs/outreach_*.json`

### View Execution Plan

```bash
python src/main.py plan "Company Name, Country"
```

Shows the orchestrator's execution plan without calling any APIs.

### Other Modes

```bash
python src/main.py --example       # Pick from 3 pre-configured example prospects
python src/main.py --interactive   # Enter company details interactively
```

### Streamlit Web UI

```bash
streamlit run app.py
```

Two tabs: **Single Proposal** (full pipeline with streaming progress) and **Prospect Search** (batch search, qualify, and outreach).

## Project Structure

```
agentic-outreach-pipeline/
├── src/
│   ├── main.py                 # CLI entry point
│   ├── orchestrator.py         # Central brain — plan/execute/aggregate
│   ├── models.py               # All Pydantic models (ContextPacket, PipelineResult, etc.)
│   ├── context.py              # Token counting, summarization, context pruning
│   ├── cost_tracker.py         # Per-agent cost tracking with budget guards
│   ├── logging_config.py       # structlog configuration
│   ├── agents/
│   │   ├── base.py             # BaseAgent with retry, fallback, streaming
│   │   ├── researcher.py       # Multi-turn agentic research with reflection
│   │   ├── analyst.py          # Competitive analysis (single-turn)
│   │   ├── architect.py        # Solution mapping (single-turn)
│   │   ├── scorer.py           # Deal estimation (structured output via tool_choice)
│   │   └── writer.py           # Proposal + email (structured output via tool_choice)
│   ├── tools/
│   │   ├── base.py             # BaseTool with circuit breaker pattern
│   │   ├── web_search.py       # DuckDuckGo search with domain filtering
│   │   ├── web_scraper.py      # Website text extraction + fact extraction
│   │   ├── knowledge_query.py  # Knowledge base query tool
│   │   ├── contact_finder.py   # Email/phone extraction from web search
│   │   └── email_sender.py     # Gmail SMTP sender
│   └── knowledge/
│       ├── product_loader.py   # YAML config loader (company + products)
│       ├── store.py            # ChromaDB vector store with semantic search
│       ├── extractor.py        # Structured fact extraction (regex + LangExtract)
│       └── schemas.py          # Extraction schema definitions
├── config/
│   ├── company.yaml            # Company profile, pricing, research depth
│   ├── products.yaml           # Product catalog, case studies, ideal customer
│   ├── extraction_schemas.yaml # Web page extraction field definitions
│   └── agent_prompts/          # Prompt templates with {{placeholders}}
│       ├── researcher.md
│       ├── analyst.md
│       ├── architect.md
│       ├── scorer.md
│       └── writer.md
├── tests/                      # pytest test suite
├── chroma_data/                # ChromaDB vector store (auto-created on first run)
├── outputs/                    # Generated proposals, traces, outreach data
├── app.py                      # Streamlit web UI
├── requirements.txt
├── .env.example
└── .env                        # API keys (not committed)
```

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| AI Agents | Claude Sonnet (Anthropic) | Best balance of quality and speed for structured outputs |
| Fallback Model | Claude Haiku | Fast + cheap for summaries, optional agents |
| Structured Output | Claude tool_choice | Guaranteed JSON — no regex parsing |
| Knowledge Store | ChromaDB + all-MiniLM-L6-v2 | Semantic vector search, embedded mode, no API keys needed |
| Web Search | DuckDuckGo (`ddgs`) | Free, no API key, good B2B results |
| Web Scraping | requests + BeautifulSoup | Simple, reliable HTML text extraction |
| Token Counting | tiktoken (`cl100k_base`) | Fast, accurate token estimation |
| CLI Output | Rich | Beautiful terminal tables and streaming |
| Logging | structlog | Structured, leveled, JSON-compatible |
| Config | YAML + python-dotenv | Human-readable config, secrets in .env |
| Models | Pydantic v2 | Type-safe data flow between agents |
| Streaming | on_event callbacks | Real-time progress in CLI and Streamlit |
| Web UI | Streamlit | Rapid prototyping, built-in components |
| Testing | pytest | Standard Python test framework |
| Language | Python 3.13 | Required by ChromaDB (<=3.13) |

## Dependencies

```
anthropic>=0.40.0        # Claude API client
streamlit>=1.38.0        # Web UI
python-dotenv>=1.0.0     # .env file loading
ddgs>=9.0.0              # DuckDuckGo search
rich>=13.0.0             # Terminal formatting
requests>=2.31.0         # HTTP client for scraper
beautifulsoup4>=4.12.0   # HTML parsing for scraper
pydantic>=2.0            # Data models
tiktoken>=0.5.0          # Token counting
pyyaml>=6.0              # YAML config loading
pandas>=2.0.0            # Data tables in Streamlit
structlog>=24.0.0        # Structured logging
chromadb>=1.0.0          # Vector store with semantic search
pytest>=8.0.0            # Testing
ruff>=0.8.0              # Linting
```

## Configuration

### Company & Products

Edit `config/company.yaml` to configure your company profile, pricing, and research depth:

```yaml
research:
  depth: "standard"  # quick (2 turns), standard (5), deep (8)
```

Edit `config/products.yaml` to configure your product catalog, case studies, and ideal customer profile. The pipeline dynamically adapts to any number of products.

### Agent Prompts

All agent prompts are in `config/agent_prompts/*.md` with `{{placeholder}}` substitution. Edit these to customize agent behavior without changing code.

## Output Examples

### Proposal mode output (`outputs/proposal_Company_Name_*.md`)

A full Markdown proposal with sections: Executive Summary, Challenges, Recommended Solution (feature mapping), Expected Impact (ROI table), Implementation Approach (phased rollout), Relevant Success Stories, and Next Steps.

### Search mode output (`outputs/outreach_*.json`)

```json
{
  "query": "metal stamping companies Germany",
  "timestamp": "20260307_150000",
  "prospects": [
    {
      "company": "Example Metalworks GmbH",
      "url": "https://www.example-metalworks.de",
      "email": "info@example-metalworks.de",
      "deal_estimate": {
        "company_name": "Example Metalworks GmbH",
        "industry": "Automotive Metal Stamping",
        "estimated_machines": 50,
        "first_year_value": 280000,
        "annual_recurring": 36000,
        "deal_category": "Medium"
      },
      "email_subject": "Reducing energy costs in automotive stamping",
      "email_body": "..."
    }
  ]
}
```

### Trace output (`outputs/trace_Company_Name_*.json`)

```json
{
  "target_company": "Example GmbH",
  "total_duration_seconds": 42.3,
  "cost_report": {
    "total_cost": 0.069,
    "agents": {
      "researcher": {"cost": 0.018, "tokens_in": 4200, "tokens_out": 3100},
      "analyst": {"cost": 0.010, "tokens_in": 2800, "tokens_out": 1500},
      "architect": {"cost": 0.013, "tokens_in": 2900, "tokens_out": 1800},
      "scorer": {"cost": 0.004, "tokens_in": 1200, "tokens_out": 400},
      "writer": {"cost": 0.021, "tokens_in": 3500, "tokens_out": 2800}
    }
  }
}
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `credit balance is too low` | Add credits at https://console.anthropic.com/settings/billing |
| `Gmail authentication failed` | Use a [Google App Password](https://myaccount.google.com/apppasswords), not your regular password |
| `No companies found` | Try more specific search terms, e.g. "CNC machining factory Vietnam" |
| Search finds irrelevant results | Add keywords like "manufacturer", "factory", "GmbH" to your query |
| Researcher falls back to legacy | API error during research — check logs for details |
| Rate limited | Pipeline has built-in exponential backoff (3 retries) |
| ChromaDB import error on Python 3.14 | ChromaDB requires Python <=3.13. Recreate venv with `python3.13 -m venv venv` |
| Slow first run | ChromaDB downloads all-MiniLM-L6-v2 embeddings (~80MB) on first run. Cached at `~/.cache/chroma/` |

## License

MIT

---

*Repository: [agentic-outreach-pipeline](https://github.com/Sardor-M/agentic-outreach-pipeline)*
