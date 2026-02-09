# Agentic Pipeline — Demo Guide

Quick-start guide to run and test every feature of the pipeline.

---

## Prerequisites

```bash
# Python 3.13 (required — ChromaDB doesn't work on 3.14)
python3.13 --version   # should show 3.13.x

# Anthropic API key set in .env
cat .env   # should contain ANTHROPIC_API_KEY=sk-ant-...
```

## Setup (one-time)

```bash
cd agentic-pipeline
source venv/bin/activate
pip install -r requirements.txt
```

First run downloads the ChromaDB embedding model (~80MB). Cached after that.

---

## Test 1: Verify RAG Knowledge Base

```bash
cd src
python -c "
from rag import initialize, query_knowledge_base
print(initialize(force_rebuild=True))
print()
print(query_knowledge_base('energy monitoring for stamping'))
"
```

**Expected:** `RAG initialized: 16 total chunks` + relevant Machine365.Ai/MV900 results.

---

## Test 2: Verify Website Scraper

```bash
python -c "
from scraper import scrape_website
print(scrape_website('https://httpbin.org/html')[:300])
"
```

**Expected:** Clean text from the page (Moby Dick excerpt). Errors return strings like `Error: Could not connect...`, not crashes.

---

## Test 3: Generate a Proposal (Main Test)

```bash
python run.py proposal "Koelle GmbH, Germany"
```

**What to watch for:**
1. `📚 RAG initialized: 16 total chunks` — ChromaDB loaded
2. `🤖 Agent: Agentic Researcher` — multi-turn research starts
3. `🔧 Tool: query_knowledge_base(...)` — KB queries
4. `🔧 Tool: search_web(...)` — DuckDuckGo searches
5. `🔧 Tool: scrape_company_website(...)` — website scraping
6. `✅ Research complete (... tokens, N turns)` — research done
7. `🤖 Agent: Solution Architect` — solution mapping
8. `🤖 Agent: Proposal Writer` — proposal generation
9. `✅ PIPELINE COMPLETE` — output saved

**Output:** Check `outputs/proposal_Koelle_GmbH_*.md` for the full proposal.

---

## Test 4: Try Example Prospects

```bash
python run.py --example
```

Pick 1, 2, or 3 from the menu. Each runs the full proposal pipeline with a pre-configured company.

| # | Prospect | Industry |
|---|----------|----------|
| 1 | Mueller Automotive GmbH, Germany | Auto parts stamping, 150 presses |
| 2 | Pacific Brass & Copper, USA | Copper fittings, 40+ machines |
| 3 | Vina Precision Parts, Vietnam | Electronics stamping, 80 presses |

---

## Test 5: Interactive Mode

```bash
python run.py --interactive
```

Type a company description (press Enter twice to submit):

```
Samsung SDI, South Korea
Battery cell manufacturer for EV market
Large-scale production with 200+ machines
ESG compliance critical for European automotive customers
```

---

## Test 6: Search & Outreach Pipeline

```bash
python run.py search "metal stamping companies Germany"
```

**What happens:**
1. DuckDuckGo finds companies
2. Contact info extracted
3. Deal sizes estimated (JSON)
4. Rich table displayed — pick companies to pursue
5. Agentic researcher generates briefs
6. Cold emails written
7. Email preview shown
8. Confirm to send via Gmail (or skip)
9. Results saved to `outputs/outreach_*.json`
10. Results indexed into RAG for future runs

**Try also:**
```bash
python run.py search "automotive parts manufacturer Japan"
python run.py search "copper fittings factory USA"
python run.py search "injection molding company Vietnam"
```

---

## Test 7: Streamlit Web UI

```bash
cd ..   # back to project root
source venv/bin/activate
streamlit run app.py
```

Open http://localhost:8501. Select an example prospect or enter custom input, then click "Run Sales Agent Pipeline".

---

## Test 8: Verify RAG Learns From Past Runs

After running Test 6 (search), run this:

```bash
cd src
python -c "
from rag import initialize, query_knowledge_base
initialize()
print(query_knowledge_base('past outreach metal stamping'))
"
```

**Expected:** Results now include past outreach data from your search run, not just product knowledge.

---

## Output Files

After running tests, check:

```bash
ls -la outputs/
```

| File | From |
|------|------|
| `proposal_*.md` | Test 3, 4, 5 (proposal mode) |
| `pipeline_*.json` | Test 3, 4, 5 (full debug output) |
| `outreach_*.json` | Test 6 (search mode) |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: chromadb` | `source venv/bin/activate && pip install -r requirements.txt` |
| `pydantic.v1.errors.ConfigError` | Wrong Python version. Use Python 3.13, not 3.14 |
| `credit balance is too low` | Add credits at https://console.anthropic.com/settings/billing |
| `No companies found` (search) | Try more specific terms: "CNC machining factory Vietnam" |
| Researcher falls back to legacy | ChromaDB init failed. Check `python --version` is 3.13.x |
| Embedding model downloading slow | First run only (~80MB). Cached at `~/.cache/chroma/` |

---

## Quick Smoke Test (30 seconds)

If you just want to verify everything works:

```bash
cd src
python -c "
from rag import initialize, query_knowledge_base
from scraper import scrape_website
from agents import _execute_tool, RESEARCHER_TOOLS

# 1. RAG
print(initialize())

# 2. KB query
result = query_knowledge_base('defect detection')
print(f'KB: {result[:80]}...')

# 3. Scraper
result = scrape_website('https://httpbin.org/html')
print(f'Scraper: {result[:80]}...')

# 4. Tool dispatch
result = _execute_tool('query_knowledge_base', {'query': 'energy'})
print(f'Tool dispatch: {result[:80]}...')

# 5. Tools registered
print(f'Tools: {[t[\"name\"] for t in RESEARCHER_TOOLS]}')

print('\n✅ All systems operational')
"
```
