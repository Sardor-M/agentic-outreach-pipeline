import json
import os
import sys

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from knowledge.product_loader import COMPANY_CONFIG, PRODUCTS_CONFIG
from orchestrator import (
    Orchestrator,
    run_deal_estimator,
    run_quick_summary,
)
from tools.contact_finder import find_prospects
from tools.email_sender import is_configured as gmail_configured
from tools.email_sender import send_outreach_email

# ── Page Config ──
st.set_page_config(
    page_title="Agentic Pipeline",
    page_icon="AP",
    layout="wide",
)

# ── Custom CSS ──
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# ── Header ──
st.title("Agentic Pipeline")
st.caption(
    "AI-powered prospect research, proposal generation & outreach | "
    "Orchestrator + Sub-agents | Structured I/O"
)

# ── Load product data from YAML config (dynamic) ──
products = PRODUCTS_CONFIG
product_list = list(products["products"].values())
case_studies = products["case_studies"]

# ── Sidebar ──
with st.sidebar:
    st.header("Products in Scope")

    for product in product_list:
        with st.expander(f"{product['name']} — {product.get('category', '')}"):
            st.write(product["description"])
            st.write("**Best for:**")
            for item in product["best_for"]:
                st.write(f"- {item}")

    with st.expander("Case Studies"):
        for cs in case_studies:
            st.write(f"**{cs['title']}**")
            st.write(f"→ {cs['result']}")
            st.write("---")

    st.header("Settings")
    model = st.selectbox(
        "LLM Model", ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"], index=0
    )

    st.header("Pipeline Info")
    st.caption(f"Company: {COMPANY_CONFIG['name']}")
    st.caption(f"Config: config/company.yaml")


# ── Helpers ──


def _parse_deal_json(raw: str) -> dict:
    """Safely parse deal estimator JSON output."""
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "company_name": "Unknown",
            "industry": "Unknown",
            "estimated_machines": 0,
            "first_year_value": 0,
            "annual_recurring": 0,
            "deal_category": "Unknown",
            "confidence": "Low",
            "reasoning": f"Could not parse: {raw[:100]}",
        }


def format_prospect_for_agent(prospect: dict) -> str:
    """Format a prospect dict into a text block for agents."""
    email_str = ", ".join(prospect["emails"]) if prospect.get("emails") else "Not found"
    phone_str = ", ".join(prospect["phones"]) if prospect.get("phones") else "Not found"
    return (
        f"Company: {prospect['title']}\n"
        f"Website: {prospect['url']}\n"
        f"Description: {prospect['snippet']}\n"
        f"Email(s): {email_str}\n"
        f"Phone(s): {phone_str}"
    )


# ── Main Content: Two Tabs ──
EXAMPLES = {
    "Custom input": "",
    "Auto Parts Stamping (Germany)": (
        "Mueller Automotive GmbH, Germany. Mid-size automotive parts manufacturer "
        "specializing in metal stamping for car body panels and structural components. "
        "Operates 3 factories with approximately 150 press machines ranging from 200 to 2000 tons. "
        "Supplies to BMW and Volkswagen. Facing EU carbon reporting regulations and rising energy costs."
    ),
    "Copper Fittings (USA)": (
        "Pacific Brass & Copper, California, USA. Manufacturer of copper pipe fittings "
        "and brass valves for plumbing industry. Single factory with 40+ forging and forming machines. "
        "High energy costs due to California electricity rates. No current smart factory systems."
    ),
    "Electronics Stamping (Vietnam)": (
        "Vina Precision Parts Co., Ltd, Ho Chi Minh City, Vietnam. Precision metal stamping "
        "for consumer electronics — connector pins, shielding cases, battery contacts. "
        "80 high-speed stamping presses. Struggling with defect rates and no centralized monitoring. "
        "Japanese parent company requires detailed production reporting."
    ),
}

tab1, tab2 = st.tabs(["Single Proposal", "Prospect Search"])

# ════════════════════════════════════════════════
# TAB 1: Single Proposal (orchestrator-based)
# ════════════════════════════════════════════════
with tab1:
    st.header("Target Company")

    selected = st.selectbox(
        "Choose an example or enter custom:", list(EXAMPLES.keys()), key="sp_example"
    )

    if selected == "Custom input":
        company_input = st.text_area(
            "Describe the target company",
            height=150,
            placeholder=(
                "Company name, location, what they manufacture, factory size, "
                "number of machines, known pain points..."
            ),
            key="sp_input_custom",
        )
    else:
        company_input = st.text_area(
            "Edit or use as-is:", value=EXAMPLES[selected], height=150, key="sp_input_example"
        )

    run_btn = st.button("Run Pipeline", type="primary", use_container_width=True)

    if run_btn and company_input.strip():
        company_name = company_input.split(",")[0].split("\n")[0].strip()
        st.session_state["sp_company_name"] = company_name

        orchestrator = Orchestrator(interactive=False)

        # Show plan
        plan = orchestrator.plan(company_input)
        with st.expander("Execution Plan", expanded=True):
            for step in plan.steps:
                deps = f" (after: {', '.join(d.value for d in step.depends_on)})" if step.depends_on else ""
                st.write(f"**{step.agent.value.title()}** — {step.description}{deps}")

        # Execute pipeline with real-time streaming progress
        with st.status("Running pipeline...", expanded=True) as status:
            def on_event(event, _status=status):
                event_type = event.get("type")
                agent = event.get("agent", "")
                try:
                    if event_type == "agent_start":
                        _status.update(label=f"Agent: {agent.title()} — running...")
                    elif event_type == "agent_end":
                        duration = event.get("duration", 0)
                        if event.get("success"):
                            _status.update(label=f"{agent.title()} done ({duration:.1f}s) — next...")
                    elif event_type == "tool_call":
                        tool = event.get("tool", "")
                        _status.update(label=f"Agent: {agent.title()} — calling {tool}...")
                except Exception:
                    pass  # Swallow thread-safety issues from parallel agents

            result = orchestrator.execute(company_input, plan, on_event=on_event)
            status.update(label="Pipeline complete!", state="complete")

        st.session_state["sp_result"] = result
        st.session_state["sp_pipeline_complete"] = True

        # Save results
        paths = orchestrator.save_results(result)
        st.session_state["sp_paths"] = paths

    elif run_btn:
        st.warning("Please enter a company description first.")

    # ── Display results ──
    if st.session_state.get("sp_pipeline_complete"):
        result = st.session_state["sp_result"]
        company_name = st.session_state["sp_company_name"]

        # Token usage summary
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.metric("Tokens In", f"{result.total_tokens_in:,}")
        with col_t2:
            st.metric("Tokens Out", f"{result.total_tokens_out:,}")
        with col_t3:
            st.metric("Duration", f"{result.total_duration_seconds:.1f}s")

        st.success("Pipeline complete!")

        # Agent outputs
        with st.expander("Research Brief", expanded=False):
            if result.research_brief:
                st.markdown(result.research_brief.raw_brief)

        with st.expander("Competitive Analysis", expanded=False):
            if result.competitive_analysis:
                st.markdown(result.competitive_analysis.raw_analysis)

        with st.expander("Solution Mapping", expanded=False):
            if result.solution_map:
                st.markdown(result.solution_map.raw_solution_map)

        with st.expander("Deal Estimate", expanded=False):
            if result.deal_estimate:
                st.json(result.deal_estimate.model_dump())

        # Proposal
        st.header("Generated Proposal")
        if result.proposal:
            st.markdown(result.proposal.proposal_markdown)

            col_dl, col_email = st.columns(2)
            with col_dl:
                st.download_button(
                    label="Download Proposal (Markdown)",
                    data=result.proposal.proposal_markdown,
                    file_name=f"proposal_{company_name.replace(' ', '_')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            # Email section
            if result.proposal.email_subject or result.proposal.email_body:
                st.subheader("Cold Email")
                email_text = f"Subject: {result.proposal.email_subject}\n\n{result.proposal.email_body}"
                edited_email = st.text_area(
                    "Edit email before sending:",
                    value=email_text,
                    height=300,
                    key="sp_email_editor",
                )

                recipient = st.text_input("Recipient email:", key="sp_recipient")

                col_send, col_dl_email = st.columns(2)
                with col_send:
                    if st.button("Send Email", use_container_width=True, key="sp_send"):
                        if not recipient or "@" not in recipient:
                            st.error("Please enter a valid email address.")
                        elif not gmail_configured():
                            st.error(
                                "Gmail not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env"
                            )
                        else:
                            send_result = send_outreach_email(recipient, edited_email)
                            if send_result["success"]:
                                st.success(f"Email sent to {recipient}!")
                            else:
                                st.error(f"Send failed: {send_result['error']}")
                with col_dl_email:
                    st.download_button(
                        label="Download Email (.txt)",
                        data=edited_email,
                        file_name=f"email_{company_name.replace(' ', '_')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

    # ── Architecture Diagram ──
    with st.expander("How the Pipeline Works"):
        st.markdown("""
        ```
        User Input (company description)
                │
                ▼
        ┌────────────────────────────────┐
        │  ORCHESTRATOR                   │
        │  1. Plan execution steps        │
        │  2. Dispatch sub-agents         │
        │  3. Aggregate results           │
        └────────────┬───────────────────┘
                     │
           ┌─────────┼─────────┐
           ▼         ▼         ▼
        Researcher  Analyst  Architect  (parallel)
           │         │         │
           └─────────┼─────────┘
                     ▼
                  Scorer
                     │
                     ▼
                  Writer
                     │
                     ▼
              Proposal + Email
        ```
        """)


# ════════════════════════════════════════════════
# TAB 2: Prospect Search
# ════════════════════════════════════════════════
with tab2:
    st.header("Find Prospects")
    ps_query = st.text_input(
        "Search for companies (e.g. 'metal stamping companies Germany'):",
        key="ps_query",
    )
    ps_max = st.slider("Max results", min_value=5, max_value=20, value=10, key="ps_max")
    search_btn = st.button("Search", type="primary", use_container_width=True, key="ps_search_btn")

    # ── Phase 2: Search + Quick Qualify ──
    if search_btn and ps_query.strip():
        with st.status("Searching for companies...", expanded=True) as s:
            prospects = find_prospects(ps_query, max_results=ps_max, search_delay=0.5)
            s.update(label=f"Found {len(prospects)} companies", state="complete")

        if not prospects:
            st.warning("No companies found. Try a different search query.")
        else:
            deals = []
            summaries = []
            progress = st.progress(0, text="Qualifying prospects...")

            for i, p in enumerate(prospects):
                brief = format_prospect_for_agent(p)
                raw = run_deal_estimator(brief)
                deal = _parse_deal_json(raw)
                deals.append(deal)

                summary = run_quick_summary(brief, json.dumps(deal, indent=2))
                summaries.append(summary)

                progress.progress(
                    (i + 1) / len(prospects),
                    text=f"Qualified {i + 1}/{len(prospects)}: {p['title'][:40]}",
                )

            progress.empty()

            st.session_state["ps_prospects"] = prospects
            st.session_state["ps_deals"] = deals
            st.session_state["ps_summaries"] = summaries
            st.session_state["ps_search_done"] = True
            st.session_state.pop("ps_proposals", None)
            st.session_state.pop("ps_batch_done", None)

    # ── Phase 3: Results Table + Selection ──
    if st.session_state.get("ps_search_done"):
        prospects = st.session_state["ps_prospects"]
        deals = st.session_state["ps_deals"]
        summaries = st.session_state["ps_summaries"]

        st.subheader("Prospect Pipeline")

        import pandas as pd

        rows = []
        for i, (p, d) in enumerate(zip(prospects, deals)):
            email = p["emails"][0] if p["emails"] else "—"
            rows.append({
                "#": i + 1,
                "Company": p["title"][:35],
                "Industry": d.get("industry", "—")[:20],
                "Email": email,
                "Est. Deal": f"${d.get('first_year_value', 0):,.0f}",
                "Category": d.get("deal_category", "—"),
                "Confidence": d.get("confidence", "—"),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("Quick Assessments", expanded=False):
            for i, (p, summary) in enumerate(zip(prospects, summaries)):
                st.markdown(f"**{i + 1}. {p['title'][:40]}**")
                st.write(summary)
                st.write("---")

        # Selection
        options = [f"{i + 1}. {p['title'][:40]}" for i, p in enumerate(prospects)]
        selected_labels = st.multiselect(
            "Select companies for detailed proposals:",
            options,
            key="ps_selection",
        )

        generate_btn = st.button(
            "Generate Detailed Proposals",
            type="primary",
            use_container_width=True,
            disabled=len(selected_labels) == 0,
            key="ps_generate_btn",
        )

        # ── Phase 4: Batch Proposal Generation ──
        if generate_btn and selected_labels:
            selected_indices = [int(label.split(".")[0]) - 1 for label in selected_labels]
            proposal_results = {}

            for idx in selected_indices:
                p = prospects[idx]
                d = deals[idx]
                company_name = p["title"].split(" - ")[0].split(" | ")[0].strip()

                with st.status(
                    f"Generating proposal for {company_name[:30]}...", expanded=True
                ) as s:
                    def on_event(event, _status=s, _name=company_name):
                        event_type = event.get("type")
                        agent = event.get("agent", "")
                        try:
                            if event_type == "agent_start":
                                _status.update(label=f"{_name[:20]} — {agent.title()}...")
                            elif event_type == "tool_call":
                                tool = event.get("tool", "")
                                _status.update(label=f"{_name[:20]} — {agent.title()}: {tool}...")
                        except Exception:
                            pass

                    brief = format_prospect_for_agent(p)
                    orchestrator = Orchestrator(interactive=False)
                    pipeline_result = orchestrator.execute(brief, on_event=on_event)

                    s.update(label=f"Done: {company_name[:30]}", state="complete")

                proposal_results[idx] = {
                    "company_name": company_name,
                    "pipeline_result": pipeline_result,
                    "prospect": p,
                    "deal": d,
                }

            st.session_state["ps_proposals"] = proposal_results
            st.session_state["ps_batch_done"] = True

    # ── Phase 5: Display + Actions ──
    if st.session_state.get("ps_batch_done"):
        proposal_results = st.session_state["ps_proposals"]

        st.subheader("Generated Proposals")

        for idx, data in proposal_results.items():
            name = data["company_name"]
            pr = data["pipeline_result"]

            with st.expander(f"{name}", expanded=False):
                ptab1, ptab2, ptab3 = st.tabs(["Proposal", "Email", "Research"])

                with ptab1:
                    if pr.proposal:
                        st.markdown(pr.proposal.proposal_markdown)
                        st.download_button(
                            label="Download Proposal",
                            data=pr.proposal.proposal_markdown,
                            file_name=f"proposal_{name.replace(' ', '_')}.md",
                            mime="text/markdown",
                            use_container_width=True,
                            key=f"ps_dl_prop_{idx}",
                        )

                with ptab2:
                    email_text = ""
                    if pr.proposal and pr.proposal.email_subject:
                        email_text = f"Subject: {pr.proposal.email_subject}\n\n{pr.proposal.email_body}"

                    edited = st.text_area(
                        "Edit email:",
                        value=email_text,
                        height=250,
                        key=f"ps_email_edit_{idx}",
                    )
                    p = data["prospect"]
                    default_email = p["emails"][0] if p["emails"] else ""
                    recipient = st.text_input(
                        "Recipient:",
                        value=default_email,
                        key=f"ps_recipient_{idx}",
                    )

                    col_s, col_d = st.columns(2)
                    with col_s:
                        if st.button("Send Email", use_container_width=True, key=f"ps_send_{idx}"):
                            if not recipient or "@" not in recipient:
                                st.error("Please enter a valid email address.")
                            elif not gmail_configured():
                                st.error(
                                    "Gmail not configured. "
                                    "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env"
                                )
                            else:
                                result = send_outreach_email(recipient, edited)
                                if result["success"]:
                                    st.success(f"Sent to {recipient}!")
                                else:
                                    st.error(f"Failed: {result['error']}")
                    with col_d:
                        st.download_button(
                            label="Download Email",
                            data=edited,
                            file_name=f"email_{name.replace(' ', '_')}.txt",
                            mime="text/plain",
                            use_container_width=True,
                            key=f"ps_dl_email_{idx}",
                        )

                with ptab3:
                    if pr.research_brief:
                        st.markdown("**Research Brief**")
                        st.markdown(pr.research_brief.raw_brief)
                    if pr.solution_map:
                        st.markdown("---")
                        st.markdown("**Solution Map**")
                        st.markdown(pr.solution_map.raw_solution_map)
                    if pr.competitive_analysis:
                        st.markdown("---")
                        st.markdown("**Competitive Analysis**")
                        st.markdown(pr.competitive_analysis.raw_analysis)
