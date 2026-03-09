# Agentic Outreach Pipeline — Demo Guide

Quick-start guide to run and test every feature of the pipeline.

---

## Prerequisites

```bash
# Python 3.13 required (ChromaDB does not support 3.14)
python3 --version   # should show 3.13.x

# Anthropic API key set in .env
cat .env   # should contain ANTHROPIC_API_KEY=sk-ant-...
```

## Setup (one-time)

```bash
cd agentic-outreach-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Test 1: Verify Imports and Configuration

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from orchestrator import Orchestrator
from knowledge.product_loader import COMPANY_CONFIG, PRODUCTS_CONFIG
from context import ContextManager

print(f'Company: {COMPANY_CONFIG[\"name\"]}')
print(f'Products: {list(PRODUCTS_CONFIG[\"products\"].keys())}')
print(f'Case studies: {len(PRODUCTS_CONFIG[\"case_studies\"])}')
print('All imports OK')
"
```

**Expected:** Company name, product keys, case study count, and "All imports OK".

---

## Test 2: View Execution Plan (No API Calls)

```bash
python src/main.py plan "Mueller Automotive GmbH, Germany"
```

**Expected:** Structured log output showing the pipeline plan:
```
pipeline_plan                  target='Mueller Automotive GmbH'
plan_step                      agent=researcher  criticality=required   group=0
plan_step_parallel             agents='Analyst + Architect'             group=1
plan_step                      agent=analyst     criticality=optional   group=1
plan_step                      agent=architect   criticality=required   group=1
plan_step                      agent=scorer      criticality=optional   group=2
plan_step                      agent=writer      criticality=required   group=3
```

This verifies the orchestrator and models work without spending any API credits.

---

## Test 3: Verify Knowledge Base Query (ChromaDB Semantic Search)

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from tools.knowledge_query import KnowledgeQueryTool

tool = KnowledgeQueryTool()
result = tool.run(query='energy monitoring for stamping factories')
print(result[:500])
"
```

**Expected:** Relevant product knowledge matching the query — product features, case studies, or ideal customer data. Results include relevance scores from ChromaDB vector similarity search.

> **First run note:** ChromaDB downloads the all-MiniLM-L6-v2 embedding model (~80MB) on first use. Subsequent runs are instant.

---

## Test 3b: Verify Semantic Search (RAG Verification)

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from tools.knowledge_query import KnowledgeQueryTool

tool = KnowledgeQueryTool()

# Semantic search: no shared words with 'energy monitoring' but should still match
result = tool.run(query='power consumption analysis for metal forming')
print('=== Semantic match test ===')
print(result[:500])
print()

# Verify ChromaDB collections
from knowledge.store import get_knowledge_store
store = get_knowledge_store()
print(f'Store type: {type(store).__name__}')
print(f'ChromaDB initialized: {hasattr(store, \"_client\")}')
"
```

**Expected:** Semantic search returns relevant product knowledge about energy/power monitoring even though the query uses different words ("power consumption analysis" vs "energy monitoring"). Store type should be `VectorKnowledgeStore`.

---

## Test 4: Verify Web Scraper

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from tools.web_scraper import WebScraperTool

scraper = WebScraperTool()
result = scraper.run(url='https://httpbin.org/html')
print(result[:300])
"
```

**Expected:** Clean text from the page. Errors return strings like `Error: Could not connect...`, not crashes.

---

## Test 5: Generate a Proposal (Main Test)

```bash
python src/main.py proposal "Koelle GmbH, Germany"
```

**What to watch for:**
1. `▸ Researcher` — multi-turn agentic research starts
2. Tool calls: `search_web(...)`, `query_knowledge_base(...)`, `scrape_company_website(...)`
3. Turn progress: `Turn 1/5`, `Turn 2/5`, etc.
4. `✓ Done` — researcher complete with token counts
5. `▸ Analyst` + `▸ Architect` — running in parallel
6. `▸ Scorer` — deal estimation
7. `▸ Writer` — proposal generation
8. Pipeline summary table with total tokens and duration

**Output:** Check `outputs/proposal_Koelle_GmbH_*.md` for the full proposal.

---

## Test 6: Try Example Prospects

```bash
python src/main.py --example
```

Pick 1, 2, or 3 from the menu. Each runs the full proposal pipeline with a pre-configured company.

| # | Prospect | Industry |
|---|----------|----------|
| 1 | Mueller Automotive GmbH, Germany | Auto parts stamping, 150 presses |
| 2 | Pacific Brass & Copper, USA | Copper fittings, 40+ machines |
| 3 | Vina Precision Parts, Vietnam | Electronics stamping, 80 presses |

---

## Test 7: Interactive Mode

```bash
python src/main.py --interactive
```

Type a company description (press Enter twice to submit):

```
Samsung SDI, South Korea
Battery cell manufacturer for EV market
Large-scale production with 200+ machines
ESG compliance critical for European automotive customers
```

---

## Test 8: Search & Outreach Pipeline

```bash
python src/main.py search "metal stamping companies Germany"
```

**What happens:**
1. DuckDuckGo finds companies
2. Contact info extracted (emails, phones)
3. Deal sizes estimated (structured JSON via tool_choice)
4. Rich table displayed — pick companies to pursue
5. Full pipeline runs for each selected prospect (researcher + architect + writer)
6. Cold emails written and previewed
7. Confirm to send via Gmail (or skip)
8. Results saved to `outputs/outreach_*.json`

**Try also:**
```bash
python src/main.py search "automotive parts manufacturer Japan"
python src/main.py search "copper fittings factory USA"
python src/main.py search "injection molding company Vietnam"
```

---

## Test 9: Streamlit Web UI

```bash
streamlit run app.py
```

Open http://localhost:8501. The UI has two tabs:

### Tab 1: Single Proposal

1. Select an example prospect from the dropdown (or enter custom input)
2. Click **"Run Sales Agent Pipeline"** — watch all agents run with streaming progress
3. Expand **Research Brief** and **Solution Mapping** to review intermediate outputs
4. Download the proposal as Markdown
5. Click **"Generate Cold Email"** — runs the Deal Estimator + Email Writer
6. Edit the email, enter a recipient, and click **"Send Email"** (requires Gmail in `.env`)

### Tab 2: Prospect Search

1. Enter a search query (e.g. "metal stamping companies Germany")
2. Set max results and click **"Search"**
3. Review the prospect table (company, industry, email, estimated deal, category)
4. Select companies and click **"Generate Detailed Proposals"**
5. Full pipeline runs per company: Researcher → Architect → Writer
6. Review proposals, emails, and research for each company
7. Download or send emails directly from the UI

---

## Test 10: Run Tests

```bash
pytest tests/ -v
```

**Expected:** All tests pass. Tests use mocked API calls and don't require an Anthropic API key.

---

## Output Files

After running tests, check:

```bash
ls -la outputs/
```

| File Pattern | From |
|------|------|
| `proposal_*.md` | Proposal mode — full Markdown proposal |
| `pipeline_*.json` | Proposal mode — debug output with agent results |
| `trace_*.json` | Proposal mode — per-agent timing and cost |
| `outreach_*.json` | Search mode — prospects, deals, emails |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | `source venv/bin/activate && pip install -r requirements.txt` |
| `credit balance is too low` | Add credits at https://console.anthropic.com/settings/billing |
| `No companies found` (search) | Try more specific terms: "CNC machining factory Vietnam" |
| Rate limited during pipeline | Built-in exponential backoff handles this (3 retries, 10-40s waits) |
| Researcher falls back to legacy | API error during multi-turn research — check terminal logs |
| Gmail authentication failed | Use a [Google App Password](https://myaccount.google.com/apppasswords), not your regular password |
| ChromaDB import error | ChromaDB requires Python <=3.13. Recreate venv: `python3.13 -m venv venv` |
| Slow first knowledge query | ChromaDB downloads all-MiniLM-L6-v2 (~80MB) on first run. Cached at `~/.cache/chroma/` |
| Stale knowledge results | Delete `chroma_data/` directory and restart — it auto-recreates and re-seeds from YAML config |
| `chromadb.errors` on startup | Delete `chroma_data/` and let it regenerate: `rm -rf chroma_data/` |

---

## Quick Smoke Test (30 seconds)

Verify everything works without spending API credits:

```bash
python -c "
import sys; sys.path.insert(0, 'src')

# 1. Models
from models import PipelineResult, DealEstimate, ContextPacket
print('Models OK')

# 2. Knowledge
from knowledge.product_loader import COMPANY_CONFIG, get_full_product_context
ctx = get_full_product_context()
print(f'Knowledge OK ({len(ctx)} chars, {len(ctx.split(chr(10)))} lines)')

# 3. Tools
from tools.web_search import WebSearchTool
from tools.web_scraper import WebScraperTool
from tools.knowledge_query import KnowledgeQueryTool
print(f'Tools OK (3 tools loaded)')

# 4. ChromaDB vector store
from knowledge.store import get_knowledge_store
store = get_knowledge_store()
print(f'ChromaDB OK (store type: {type(store).__name__})')

# 5. Knowledge query (semantic search)
kb = KnowledgeQueryTool()
result = kb.run(query='defect detection')
print(f'KB query OK ({len(result)} chars)')

# 6. Orchestrator
from orchestrator import Orchestrator
o = Orchestrator(interactive=True)
plan = o.plan('Test Company, Germany')
print(f'Orchestrator OK ({len(plan.steps)} steps)')

# 7. Context
from context import ContextManager
cm = ContextManager()
tokens = cm.count_tokens('hello world')
print(f'Context OK ({tokens} tokens)')

print()
print('All systems operational')
"
```
