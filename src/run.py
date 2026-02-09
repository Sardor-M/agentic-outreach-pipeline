#!/usr/bin/env python3
"""
Agentic Pipeline - CLI Entry Point

Usage:
    python run.py search "metal stamping companies Germany"   # full outreach pipeline
    python run.py proposal "Bosch automotive, Germany"         # generate proposal only
    python run.py --interactive                                # interactive input
    python run.py --example                                    # example menu
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = str(PROJECT_ROOT / "outputs")

from agents import (
    run_pipeline,
    run_researcher,
    run_deal_estimator,
    run_email_writer,
)
from prospector import find_prospects, format_prospect_for_agent
from emailer import send_outreach_email, is_configured as gmail_configured, parse_email_text

# RAG knowledge base (optional — pipeline works without it)
try:
    from rag import initialize as init_rag, index_new_outreach
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Try to import rich for pretty tables; fall back to plain text
try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


EXAMPLE_PROSPECTS = [
    {
        "name": "Auto Parts Stamping (Germany)",
        "input": (
            "Mueller Automotive GmbH, Germany. "
            "Mid-size automotive parts manufacturer specializing in metal stamping "
            "for car body panels and structural components. Operates 3 factories with "
            "approximately 150 press machines ranging from 200 to 2000 tons. "
            "Supplies to BMW and Volkswagen. Currently facing pressure from EU carbon "
            "reporting regulations and rising energy costs in Germany."
        ),
    },
    {
        "name": "Copper Fittings (USA)",
        "input": (
            "Pacific Brass & Copper, California, USA. "
            "Manufacturer of copper pipe fittings and brass valves for plumbing industry. "
            "Single factory with 40+ forging and forming machines. High energy costs due to "
            "California electricity rates. Looking to reduce production costs and improve "
            "quality control. No current smart factory systems in place."
        ),
    },
    {
        "name": "Electronics Stamping (Vietnam)",
        "input": (
            "Vina Precision Parts Co., Ltd, Ho Chi Minh City, Vietnam. "
            "Precision metal stamping for consumer electronics — connector pins, "
            "shielding cases, and battery contacts. 80 high-speed stamping presses. "
            "Rapidly growing, adding new lines quarterly. Struggling with defect rates "
            "on micro-parts and no centralized production monitoring. Japanese parent "
            "company requires detailed production reporting."
        ),
    },
]


# ─────────────────────────────────────────────
# Search & Outreach Pipeline
# ─────────────────────────────────────────────

def _parse_deal_json(raw: str) -> dict:
    """Safely parse deal estimator JSON output."""
    # Strip markdown code fences if present
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


def _display_table(prospects: list[dict], deals: list[dict]):
    """Display a rich table of prospects + deal estimates."""
    if RICH_AVAILABLE:
        console = Console()
        table = Table(title="\n3View Prospect Pipeline", show_lines=True)
        table.add_column("#", style="bold cyan", width=3)
        table.add_column("Company", style="bold", max_width=30)
        table.add_column("Industry", max_width=20)
        table.add_column("Email", style="green", max_width=30)
        table.add_column("Est. Deal", style="yellow", justify="right")
        table.add_column("Category", style="magenta")

        for i, (p, d) in enumerate(zip(prospects, deals)):
            email = p["emails"][0] if p["emails"] else "—"
            value = f"${d.get('first_year_value', 0):,.0f}"
            table.add_row(
                str(i + 1),
                p["title"][:30],
                d.get("industry", "—")[:20],
                email,
                value,
                d.get("deal_category", "—"),
            )

        console.print(table)
    else:
        # Plain text fallback
        print(f"\n{'#':<4} {'Company':<30} {'Industry':<20} {'Email':<30} {'Est. Deal':>12} {'Category':<10}")
        print("-" * 110)
        for i, (p, d) in enumerate(zip(prospects, deals)):
            email = p["emails"][0] if p["emails"] else "—"
            value = f"${d.get('first_year_value', 0):,.0f}"
            print(f"{i+1:<4} {p['title'][:30]:<30} {d.get('industry', '—')[:20]:<20} {email:<30} {value:>12} {d.get('deal_category', '—'):<10}")


def _get_user_selection(count: int) -> list[int]:
    """Ask user which prospects to pursue. Returns 0-indexed list."""
    print(f"\nSelect prospects to pursue:")
    print(f"  Enter numbers separated by commas (e.g. 1,3,5)")
    print(f"  'all' to select all")
    print(f"  'q' to quit")

    choice = input("\n> ").strip().lower()

    if choice == "q":
        return []
    if choice == "all":
        return list(range(count))

    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
        return [i for i in indices if 0 <= i < count]
    except ValueError:
        print("Invalid selection.")
        return []


def search_command(query: str):
    """
    Full search → estimate → email outreach pipeline.

    Steps:
    1. DuckDuckGo search for companies
    2. Extract contact info
    3. Estimate deal size per company
    4. Display table for user selection
    5. Research selected companies
    6. Write personalized emails
    7. Preview and optionally send via Gmail
    8. Save results to outputs/
    """
    print("\n" + "=" * 60)
    print("  3VIEW SALES OUTREACH PIPELINE")
    print("=" * 60)
    print(f"\nQuery: {query}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Step 1-2: Find prospects ──
    print(f"\n--- Step 1: Finding companies ---")
    prospects = find_prospects(query, max_results=10, search_delay=1.0)

    if not prospects:
        print("\nNo companies found. Try a different search query.")
        return

    # ── Step 3: Estimate deals ──
    print(f"\n--- Step 2: Estimating deal sizes ---")
    deals = []
    for p in prospects:
        brief = format_prospect_for_agent(p)
        raw = run_deal_estimator(brief)
        deal = _parse_deal_json(raw)
        deals.append(deal)

    # ── Step 4: Display table ──
    print(f"\n--- Step 3: Results ---")
    _display_table(prospects, deals)

    # ── Step 5: User selection ──
    selected_indices = _get_user_selection(len(prospects))
    if not selected_indices:
        print("\nNo prospects selected. Exiting.")
        return

    selected_prospects = [prospects[i] for i in selected_indices]
    selected_deals = [deals[i] for i in selected_indices]

    print(f"\nSelected {len(selected_indices)} prospect(s). Starting outreach pipeline...\n")

    # ── Step 6-7: Research + Write emails ──
    outreach_results = []
    for i, (prospect, deal) in enumerate(zip(selected_prospects, selected_deals)):
        print(f"\n{'─'*60}")
        print(f"  Prospect {i+1}/{len(selected_prospects)}: {prospect['title']}")
        print(f"{'─'*60}")

        # Research
        brief = format_prospect_for_agent(prospect)
        research = run_researcher(brief)

        # Write email
        deal_context = json.dumps(deal, indent=2)
        email_text = run_email_writer(research, deal_context)

        to_email = prospect["emails"][0] if prospect["emails"] else None

        outreach_results.append({
            "prospect": prospect,
            "deal": deal,
            "research": research,
            "email_text": email_text,
            "to_email": to_email,
        })

    # ── Step 8: Preview emails ──
    print(f"\n{'='*60}")
    print("  EMAIL PREVIEWS")
    print(f"{'='*60}")

    for i, result in enumerate(outreach_results):
        to = result["to_email"] or "(no email found)"
        print(f"\n--- Email {i+1}: {result['prospect']['title'][:40]} → {to} ---")
        print(result["email_text"])
        print()

    # ── Step 8.5: Fill in missing emails ──
    missing = [r for r in outreach_results if not r["to_email"]]
    if missing:
        print(f"\n{'─'*60}")
        print(f"  {len(missing)} prospect(s) have no email address.")
        print(f"  You can enter emails manually, or press Enter to skip each.")
        print(f"{'─'*60}")

        for result in missing:
            name = result["prospect"]["title"][:40]
            addr = input(f"\n  Email for {name}: ").strip()
            if addr and "@" in addr:
                result["to_email"] = addr
                print(f"    Set: {addr}")
            else:
                if addr:
                    print(f"    Skipped (invalid)")
                else:
                    print(f"    Skipped")

    # ── Step 9: Send emails ──
    sent_count = 0
    sendable = [r for r in outreach_results if r["to_email"]]

    if sendable:
        print(f"\n{'='*60}")
        print(f"  READY TO SEND ({len(sendable)} emails)")
        print(f"{'='*60}")
        for i, r in enumerate(sendable):
            parsed = parse_email_text(r["email_text"])
            print(f"  {i+1}. {r['prospect']['title'][:35]} → {r['to_email']}")
            print(f"     Subject: {parsed['subject']}")

        if gmail_configured():
            confirm = input(f"\nSend {len(sendable)} email(s) via Gmail? (y/n): ").strip().lower()
            if confirm == "y":
                for result in sendable:
                    send_result = send_outreach_email(result["to_email"], result["email_text"])
                    if send_result["success"]:
                        print(f"  Sent to {result['to_email']}")
                        sent_count += 1
                    else:
                        print(f"  Failed: {result['to_email']} — {send_result['error']}")
                print(f"\n{sent_count}/{len(sendable)} emails sent successfully.")
            else:
                print("\nEmails not sent. Saved to output file.")
        else:
            print("\nGmail not configured (set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env).")
            print("Emails saved to output file only.")
    else:
        print("\nNo email addresses available. Emails saved to output file only.")

    # ── Step 10: Save results ──
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_data = {
        "query": query,
        "timestamp": timestamp,
        "prospects": [],
    }

    sent_emails = set()
    if sent_count > 0:
        sent_emails = {r["to_email"] for r in sendable if r["to_email"]}

    for result in outreach_results:
        parsed = parse_email_text(result["email_text"])
        output_data["prospects"].append({
            "company": result["prospect"]["title"],
            "url": result["prospect"]["url"],
            "email": result["to_email"],
            "deal_estimate": result["deal"],
            "research_brief": result["research"],
            "email_subject": parsed["subject"],
            "email_body": parsed["body"],
            "sent": result["to_email"] in sent_emails if result["to_email"] else False,
        })

    output_path = os.path.join(OUTPUTS_DIR, f"outreach_{timestamp}.json")
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Index new outreach into RAG for future runs
    if RAG_AVAILABLE:
        try:
            rag_status = index_new_outreach(output_data)
            print(f"📚 {rag_status}")
        except Exception as e:
            print(f"⚠️ RAG indexing skipped: {e}")

    print(f"\nResults saved: {output_path}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# ─────────────────────────────────────────────
# Legacy Modes (preserved)
# ─────────────────────────────────────────────

def interactive_mode():
    """Run in interactive mode — ask user for company details."""
    print("\n" + "=" * 60)
    print("  3VIEW MACHINE365 SALES AGENT PIPELINE")
    print("  Powered by AI | Scoped to MV900 + Machine365.Ai")
    print("=" * 60)

    print("\nDescribe your target company. Include as much as you can:")
    print("  - Company name and location")
    print("  - What they manufacture")
    print("  - Factory size (number of machines)")
    print("  - Known pain points")
    print("  - Any specific context\n")

    lines = []
    print("Enter company details (press Enter twice to submit):")
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)

    company_input = "\n".join(lines).strip()
    if not company_input:
        print("No input provided. Exiting.")
        return

    result = run_pipeline(company_input)
    print(f"\nOpen your proposal: {result['proposal_path']}")


def example_mode():
    """Run with a pre-configured example."""
    print("\n" + "=" * 60)
    print("  3VIEW SALES PIPELINE — EXAMPLE PROSPECTS")
    print("=" * 60)

    for i, prospect in enumerate(EXAMPLE_PROSPECTS):
        print(f"\n  [{i + 1}] {prospect['name']}")
        print(f"      {prospect['input'][:80]}...")

    print(f"\n  [0] Enter custom company")

    choice = input("\nSelect a prospect (1-3, or 0 for custom): ").strip()

    if choice == "0":
        interactive_mode()
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(EXAMPLE_PROSPECTS):
            prospect = EXAMPLE_PROSPECTS[idx]
            print(f"\nSelected: {prospect['name']}")
            result = run_pipeline(prospect["input"])
            print(f"\nOpen your proposal: {result['proposal_path']}")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def _init_rag_safe():
    """Initialize RAG knowledge base. Fails silently if unavailable."""
    if not RAG_AVAILABLE:
        return
    try:
        status = init_rag()
        print(f"📚 {status}")
    except Exception as e:
        print(f"⚠️ RAG init skipped: {e}")


def main():
    _init_rag_safe()

    if len(sys.argv) < 2:
        example_mode()
        return

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: python run.py search \"metal stamping companies Germany\"")
            return
        query = " ".join(sys.argv[2:])
        search_command(query)

    elif command == "proposal":
        if len(sys.argv) < 3:
            print("Usage: python run.py proposal \"Company name, Country\"")
            return
        company_input = " ".join(sys.argv[2:])
        result = run_pipeline(company_input)
        print(f"\nOpen your proposal: {result['proposal_path']}")

    elif command == "--interactive":
        interactive_mode()

    elif command == "--example":
        example_mode()

    else:
        # Backward compat: treat all args as company input for proposal
        company_input = " ".join(sys.argv[1:])
        result = run_pipeline(company_input)
        print(f"\nOpen your proposal: {result['proposal_path']}")


if __name__ == "__main__":
    main()
