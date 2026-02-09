# Agentic Pipeline

An AI-powered B2B sales pipeline that automates company research, deal estimation, proposal generation, and cold email outreach for manufacturing companies. Built with Claude (Anthropic), ChromaDB RAG, agentic tool-use, DuckDuckGo search, and Gmail SMTP.

## What It Does

Six specialized Claude AI agents collaborate in two pipeline modes, powered by a RAG knowledge base and agentic tool-use:

```
                         ┌──────────────────────────┐
                         │     RAG Knowledge Base    │
                         │  (ChromaDB Vector Store)  │
                         │  Product docs + past runs │
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
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
    Search Pipeline            Proposal Pipeline
    ──────────────             ─────────────────
    Deal Estimator             Solution Architect
         │                          │
    Email Writer               Proposal Writer
         │
    Gmail Send
         │
    Save + Index to RAG
```

### Search Mode

Find companies, estimate deals, write and send personalized cold emails:

```
Search Query → DuckDuckGo → Contact Extraction → Deal Estimator → Table Display
→ User Selection → Agentic Researcher → Email Writer → Gmail Send → Save + RAG Index
```

### Proposal Mode

Generate a detailed multi-page sales proposal:

```
Company Input → Agentic Researcher → Solution Architect → Proposal Writer → Save
```

## What's New: RAG + Agentic Tool-Use

The Researcher agent is now **truly agentic** — instead of guessing about companies, it autonomously uses 3 tools in a multi-turn loop:

| Tool | What It Does | Source |
|------|-------------|--------|
| `search_web` | Search DuckDuckGo for company info, news, industry data | `prospector.py` |
| `query_knowledge_base` | Semantic search over product docs + past outreach history | `rag.py` (ChromaDB) |
| `scrape_company_website` | Fetch and read a company's website | `scraper.py` |

The agent decides which tools to call and in what order (up to 5 turns). Example flow:

```
Turn 1: query_knowledge_base("past outreach similar companies")
Turn 2: scrape_company_website("https://company.com")
Turn 3: search_web("company manufacturing details")
Turn 4: query_knowledge_base("relevant case studies energy")
Turn 5: Final structured research brief
```

A **ChromaDB vector store** indexes all product knowledge (~16 semantic chunks) and past outreach results. Each completed search run is automatically indexed, so future research can reference past engagement history.

## Setup

### Prerequisites

- Python 3.13 (required — ChromaDB does not support Python 3.14)
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Clone and create virtual environment

```bash
cd agentic-pipeline
python3.13 -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

First run will download the ChromaDB embedding model (~80MB, cached at `~/.cache/chroma/`).

### 3. Configure environment variables

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...

# Optional — only needed if you want to send emails
GMAIL_ADDRESS=yourname@gmail.com
GMAIL_APP_PASSWORD=abcd-efgh-ijkl-mnop
```

**Gmail App Password**: Go to [Google App Passwords](https://myaccount.google.com/apppasswords), generate a new app password, and paste it above. This is NOT your regular Gmail password.

## Usage

All commands are run from the `src/` directory:

```bash
cd src
```

### Search & Outreach

Find companies via web search, estimate deals, write and send personalized cold emails:

```bash
python run.py search "metal stamping companies Germany"
python run.py search "automotive parts manufacturer Japan"
python run.py search "copper fittings factory USA"
```

**What happens:**

1. DuckDuckGo finds 5-10 matching companies
2. Follow-up searches extract email addresses and phone numbers
3. Deal Estimator agent sizes each opportunity (JSON output)
4. A rich table shows all prospects with deal estimates
5. You select which companies to pursue (e.g. `1,3,5` or `all`)
6. Agentic Researcher generates a brief per company (using tools: web search, KB, scraper)
7. Email Writer agent creates a personalized cold email for each
8. Emails are previewed in terminal
9. You confirm before sending via Gmail (or skip — emails save to `outputs/` either way)
10. Results are indexed into ChromaDB for future reference

### Full Proposal

Generate a detailed multi-page sales proposal for a specific company:

```bash
python run.py proposal "Koelle GmbH, Germany"
python run.py proposal "Mueller Automotive GmbH, Germany, 150 press machines"
```

### Other Modes

```bash
python run.py --example       # pick from 3 pre-configured example prospects
python run.py --interactive   # enter company details interactively
```

## Project Structure

```
agentic-pipeline/
├── src/
│   ├── run.py           # CLI entry point — search, proposal, interactive modes
│   ├── agents.py        # 5 Claude agents + agentic researcher with tool-use
│   ├── knowledge.py     # Product knowledge base (MV900 + Machine365.Ai)
│   ├── rag.py           # ChromaDB RAG knowledge base (product + outreach indexing)
│   ├── scraper.py       # Website text extraction (requests + BeautifulSoup)
│   ├── prospector.py    # DuckDuckGo web search + contact extraction
│   └── emailer.py       # Gmail SMTP sender
├── chroma_data/         # ChromaDB persistent storage (auto-created, gitignored)
├── outputs/             # Generated proposals and outreach JSON (auto-created)
├── requirements.txt
├── .env                 # API keys (not committed)
└── app.py               # Streamlit UI (separate scope)
```

## The Agents

| # | Agent | Type | Temp | Purpose |
|---|-------|------|------|---------|
| 1 | **Prospect Researcher** | Agentic (multi-turn, 3 tools) | 0.6 | Researches companies using web search, knowledge base, and website scraping |
| 2 | **Solution Architect** | Single-turn | 0.5 | Maps pain points to specific MV900 / Machine365.Ai features + ROI estimates |
| 3 | **Proposal Writer** | Single-turn | 0.7 | Generates a polished, ready-to-send Markdown sales proposal |
| 4 | **Deal Estimator** | Single-turn | 0.3 | Estimates deal size as structured JSON (machine count, value, category) |
| 5 | **Cold Email Writer** | Single-turn | 0.7 | Writes a short, personalized cold outreach email (under 200 words, plain text) |

Agents 1-3 are used in **proposal** mode. Agents 1, 4, 5 are used in **search** mode.

Only the Researcher is agentic (multi-turn tool-use). The other 4 agents stay single-turn — they receive enriched context from the researcher and don't need tools.

## RAG Knowledge Base

ChromaDB runs in **embedded mode** (no external server) with persistent storage at `chroma_data/`.

### What's Indexed

**Product knowledge** (~16 chunks):
- Company profile
- MV900 overview, features, functions, benefits, specs
- Machine365.Ai overview, features, functions, benefits
- Combined solution synergies
- Ideal customer profile + ROI data
- Case studies (one chunk per study)

**Past outreach** (grows over time):
- Every completed search run is indexed
- Includes: company name, industry, deal category, research brief
- Enables the researcher to reference past engagement when researching similar companies

### Embeddings

Uses ChromaDB's default Sentence Transformers model (all-MiniLM-L6-v2). No additional API keys needed.

## Output Examples

### Search mode output (`outputs/outreach_YYYYMMDD_HHMMSS.json`)

```json
{
  "query": "metal stamping companies Germany",
  "timestamp": "20260209_180100",
  "prospects": [
    {
      "company": "Koelle GmbH",
      "url": "https://www.koelle-gmbh.de",
      "email": "info@koelle-gmbh.de",
      "deal_estimate": {
        "company_name": "Koelle GmbH",
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

### Proposal mode output (`outputs/proposal_Company_Name_YYYYMMDD_HHMMSS.md`)

A full Markdown proposal with sections: Executive Summary, Challenges, Recommended Solution (MV900 + Machine365.Ai feature mapping), Expected Impact (ROI table), Implementation Approach (phased rollout), Relevant Success Stories, and Next Steps.

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| AI agents | Claude Sonnet (Anthropic) | Best balance of quality and speed for structured outputs |
| Vector store | ChromaDB (embedded) | Local, no server, persistent, Python-native |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) | Default in ChromaDB, no API keys needed |
| Web search | DuckDuckGo (`ddgs`) | Free, no API key, good B2B results |
| Web scraping | requests + BeautifulSoup | Simple, reliable HTML text extraction |
| CLI tables | Rich | Beautiful terminal tables with plain text fallback |
| Email sending | Gmail SMTP (SSL) | Simple, reliable, uses App Passwords |
| Config | python-dotenv | Standard .env file for secrets |
| Language | Python 3.13 | ChromaDB compatible, stable |

## Dependencies

```
anthropic>=0.40.0        # Claude API client
streamlit>=1.38.0        # Web UI (optional)
python-dotenv>=1.0.0     # .env file loading
ddgs>=9.0.0              # DuckDuckGo search
rich>=13.0.0             # Terminal formatting
chromadb>=0.4.0          # Vector store for RAG
requests>=2.31.0         # HTTP client for scraper
beautifulsoup4>=4.12.0   # HTML parsing for scraper
```

## Configuration Notes

- **Anthropic API key** is required for all modes
- **Gmail credentials** are only needed to send emails — without them, emails are still generated and saved
- The pipeline uses **Claude Sonnet** (`claude-sonnet-4-20250514`) for all agents
- **ChromaDB requires Python 3.13 or lower** — it does not work on Python 3.14 (pydantic v1 compatibility issue)
- If ChromaDB fails to initialize, the pipeline still works — the researcher falls back to legacy mode (single-turn, no tools)
- DuckDuckGo search is free and requires no API key
- Search results are deduplicated by domain and filtered to remove irrelevant sites

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `credit balance is too low` | Add credits at https://console.anthropic.com/settings/billing |
| `Gmail authentication failed` | Use a [Google App Password](https://myaccount.google.com/apppasswords), not your regular password |
| `No companies found` | Try more specific search terms, e.g. "CNC machining factory Vietnam" |
| `pydantic.v1.errors.ConfigError` | You're on Python 3.14 — downgrade to Python 3.13 |
| ChromaDB embedding model download slow | First run downloads ~80MB model. Cached after that at `~/.cache/chroma/` |
| Search finds irrelevant results | Add keywords like "manufacturer", "factory", "GmbH" to your query |
| Researcher fallback to legacy mode | ChromaDB init failed. Check Python version and reinstall deps |
