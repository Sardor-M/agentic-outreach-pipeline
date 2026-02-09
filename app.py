"""
Agentic Pipeline — Streamlit UI
Run: streamlit run app.py
"""

import streamlit as st
import sys
import os
import time
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from agents import run_researcher, run_architect, run_proposal_writer
from knowledge import (
    get_full_product_context,
    MV900_KNOWLEDGE,
    MACHINE365_KNOWLEDGE,
    CASE_STUDIES,
)


# ── Page Config ──
st.set_page_config(
    page_title="Agentic Pipeline",
    page_icon="🏭",
    layout="wide",
)

# ── Custom CSS ──
st.markdown("""
<style>
    .agent-card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.title("🏭 Agentic Pipeline")
st.caption("AI-powered prospect research, proposal generation & outreach | RAG + Tool-Use | **MV900** + **Machine365.Ai**")

# ── Sidebar: Product Info ──
with st.sidebar:
    st.header("📦 Products in Scope")

    with st.expander("MV900 — Process Monitoring Hardware"):
        st.write(MV900_KNOWLEDGE["description"])
        st.write("**Best for:**")
        for item in MV900_KNOWLEDGE["best_for"]:
            st.write(f"- {item}")

    with st.expander("Machine365.Ai — Monitoring Platform"):
        st.write(MACHINE365_KNOWLEDGE["description"])
        st.write("**Best for:**")
        for item in MACHINE365_KNOWLEDGE["best_for"]:
            st.write(f"- {item}")

    with st.expander("📊 Case Studies"):
        for cs in CASE_STUDIES:
            st.write(f"**{cs['title']}**")
            st.write(f"→ {cs['result']}")
            st.write("---")

    st.header("⚙️ Settings")
    model = st.selectbox("LLM Model", ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"], index=0)

# ── Main Content ──
EXAMPLES = {
    "Custom input": "",
    "🇩🇪 Auto Parts Stamping (Germany)": (
        "Mueller Automotive GmbH, Germany. Mid-size automotive parts manufacturer "
        "specializing in metal stamping for car body panels and structural components. "
        "Operates 3 factories with approximately 150 press machines ranging from 200 to 2000 tons. "
        "Supplies to BMW and Volkswagen. Facing EU carbon reporting regulations and rising energy costs."
    ),
    "🇺🇸 Copper Fittings (USA)": (
        "Pacific Brass & Copper, California, USA. Manufacturer of copper pipe fittings "
        "and brass valves for plumbing industry. Single factory with 40+ forging and forming machines. "
        "High energy costs due to California electricity rates. No current smart factory systems."
    ),
    "🇻🇳 Electronics Stamping (Vietnam)": (
        "Vina Precision Parts Co., Ltd, Ho Chi Minh City, Vietnam. Precision metal stamping "
        "for consumer electronics — connector pins, shielding cases, battery contacts. "
        "80 high-speed stamping presses. Struggling with defect rates and no centralized monitoring. "
        "Japanese parent company requires detailed production reporting."
    ),
}

# ── Input Section ──
st.header("🎯 Target Company")

selected = st.selectbox("Choose an example or enter custom:", list(EXAMPLES.keys()))

if selected == "Custom input":
    company_input = st.text_area(
        "Describe the target company",
        height=150,
        placeholder=(
            "Company name, location, what they manufacture, factory size, "
            "number of machines, known pain points..."
        ),
    )
else:
    company_input = st.text_area(
        "Edit or use as-is:", value=EXAMPLES[selected], height=150
    )

# ── Run Pipeline ──
run_btn = st.button("🚀 Run Sales Agent Pipeline", type="primary", use_container_width=True)

if run_btn and company_input.strip():
    company_name = company_input.split(",")[0].split("\n")[0].strip()

    # Agent 1: Researcher
    with st.status("🔍 Agent 1: Prospect Researcher — analyzing company...", expanded=True) as status:
        research = run_researcher(company_input)
        status.update(label="✅ Agent 1: Research complete", state="complete")

    with st.expander("📋 Research Brief", expanded=False):
        st.markdown(research)

    # Agent 2: Solution Architect
    with st.status("🏗️ Agent 2: Solution Architect — mapping solutions...", expanded=True) as status:
        solution_map = run_architect(research)
        status.update(label="✅ Agent 2: Solution mapping complete", state="complete")

    with st.expander("🔧 Solution Mapping", expanded=False):
        st.markdown(solution_map)

    # Agent 3: Proposal Writer
    with st.status("✍️ Agent 3: Proposal Writer — generating proposal...", expanded=True) as status:
        proposal = run_proposal_writer(research, solution_map, company_name)
        status.update(label="✅ Agent 3: Proposal complete", state="complete")

    # ── Final Output ──
    st.success("🎉 Pipeline complete! Proposal generated below.")

    st.header("📄 Generated Proposal")
    st.markdown(proposal)

    # Download button
    st.download_button(
        label="⬇️ Download Proposal (Markdown)",
        data=proposal,
        file_name=f"3view_proposal_{company_name.replace(' ', '_')}.md",
        mime="text/markdown",
        use_container_width=True,
    )

    # Store in session for reference
    st.session_state["last_result"] = {
        "research": research,
        "solution_map": solution_map,
        "proposal": proposal,
    }

elif run_btn:
    st.warning("Please enter a company description first.")

# ── Pipeline Architecture Diagram ──
with st.expander("🏗️ How the Pipeline Works"):
    st.markdown("""
    ```
    Company Input (name, industry, size, pain points)
            │
            ▼
    ┌─────────────────────────────┐
    │  Agent 1: Prospect          │
    │  Researcher                 │
    │  → Company profile          │
    │  → Manufacturing analysis   │
    │  → Energy & ESG exposure    │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │  Agent 2: Solution          │
    │  Architect                  │
    │  → Pain point mapping       │
    │  → MV900 / Machine365.Ai    │
    │  → ROI estimation           │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │  Agent 3: Proposal          │
    │  Writer                     │
    │  → Executive summary        │
    │  → Solution details         │
    │  → Implementation plan      │
    │  → Personalized proposal    │
    └─────────────────────────────┘
            │
            ▼
    📄 Ready-to-Send Proposal (Markdown)
    ```
    """)
