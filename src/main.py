#!/usr/bin/env python3
"""
Agentic Outreach Pipeline — CLI Entry Point

Usage:
    python src/main.py search "metal stamping companies Germany"
    python src/main.py proposal "Company name, Country"
    python src/main.py plan "Company name, Country"
    python src/main.py --interactive
    python src/main.py --example
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = str(PROJECT_ROOT / "outputs")

from orchestrator import Orchestrator
from tools.contact_finder import find_prospects
from tools.email_sender import is_configured as gmail_configured
from tools.email_sender import parse_email_text, send_outreach_email

# Try to import rich for pretty tables
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


# ── Helpers ──


def _display_table(prospects: list[dict], deals: list[dict]):
    """Display a rich table of prospects + deal estimates."""
    if RICH_AVAILABLE:
        console = Console()
        table = Table(title="\nProspect Pipeline", show_lines=True)
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
        print(
            f"\n{'#':<4} {'Company':<30} {'Industry':<20} {'Email':<30} "
            f"{'Est. Deal':>12} {'Category':<10}"
        )
        print("-" * 110)
        for i, (p, d) in enumerate(zip(prospects, deals)):
            email = p["emails"][0] if p["emails"] else "—"
            value = f"${d.get('first_year_value', 0):,.0f}"
            print(
                f"{i + 1:<4} {p['title'][:30]:<30} {d.get('industry', '—')[:20]:<20} "
                f"{email:<30} {value:>12} {d.get('deal_category', '—'):<10}"
            )


def _get_user_selection(count: int) -> list[int]:
    """Ask user which prospects to pursue."""
    print("\nSelect prospects to pursue:")
    print("  Enter numbers separated by commas (e.g. 1,3,5)")
    print("  'all' to select all")
    print("  'q' to quit")

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


def _format_prospect(prospect: dict) -> str:
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


# ── Streaming ──


def _create_stream_handler():
    """Create a Rich-based streaming event handler for CLI output.

    Returns a callback that formats agent events with Rich styling,
    or None if Rich is not available (falls back to print-based output).
    Thread-safe for parallel agent execution.
    """
    if not RICH_AVAILABLE:
        return None

    import threading

    console = Console()
    lock = threading.Lock()

    def handler(event):
        event_type = event.get("type")
        agent = event.get("agent", "")

        with lock:
            if event_type == "agent_start":
                task = event.get("task", "")[:60]
                console.print(f"\n[bold blue]▸ {agent.title()}[/] — {task}...")

            elif event_type == "turn":
                turn = event.get("turn", 0)
                max_turns = event.get("max_turns", 0)
                console.print(f"  [dim]Turn {turn}/{max_turns}[/]")

            elif event_type == "tool_call":
                tool = event.get("tool", "")
                tool_input = json.dumps(event.get("input", {}))[:60]
                console.print(f"  [dim]Tool: {tool}[/]({tool_input})")

            elif event_type == "tool_result":
                preview = event.get("result_preview", "")[:80]
                console.print(f"  [dim]→ {preview}[/]")

            elif event_type == "agent_end":
                tokens_in = event.get("tokens_in", 0)
                tokens_out = event.get("tokens_out", 0)
                duration = event.get("duration", 0)
                success = event.get("success", False)
                icon = "✓" if success else "✗"
                color = "green" if success else "red"
                console.print(
                    f"  [{color}]{icon}[/] Done — "
                    f"{tokens_in:,}+{tokens_out:,} tokens, {duration:.1f}s"
                )

            elif event_type == "agent_error":
                console.print(f"  [red]✗ Error: {event.get('error', '')}[/]")

            elif event_type == "pipeline_end":
                console.print()
                table = Table(show_edge=False, pad_edge=False)
                table.add_column("Metric", style="bold")
                table.add_column("Value", justify="right")
                table.add_row("Tokens In", f"{event.get('tokens_in', 0):,}")
                table.add_row("Tokens Out", f"{event.get('tokens_out', 0):,}")
                table.add_row("Duration", f"{event.get('duration', 0):.1f}s")
                console.print(table)

            elif event_type == "retry":
                wait = event.get("wait", 0)
                console.print(f"  [yellow]Rate limited. Waiting {wait}s...[/]")

            elif event_type == "fallback":
                error = event.get("error", "")
                console.print(f"  [yellow]Fallback: {error}[/]")

    return handler


# ── Commands ──


def search_command(query: str):
    """Full search → estimate → email outreach pipeline."""
    from agents.scorer import ScorerAgent
    from agents.writer import WriterAgent
    from context import ContextManager
    from knowledge.product_loader import COMPANY_CONFIG

    print(f"\nQuery: {query}")

    # Step 1-2: Find prospects
    prospects = find_prospects(query, max_results=10, search_delay=1.0)
    if not prospects:
        print("\nNo companies found. Try a different search query.")
        return

    # Step 3: Estimate deals using ScorerAgent directly
    cm = ContextManager()
    scorer = ScorerAgent(cm)
    deals = []
    for p in prospects:
        brief = _format_prospect(p)
        context = cm.build_context_packet(
            task_description=f"Estimate the deal size for this prospect:\n\n{brief}",
            relevant_data={},
            company_config=COMPANY_CONFIG,
        )
        result = scorer.run(context)
        deals.append(result.output if result.output else {})

    # Step 4: Display table
    _display_table(prospects, deals)

    # Step 5: User selection
    selected_indices = _get_user_selection(len(prospects))
    if not selected_indices:
        print("\nNo prospects selected. Exiting.")
        return

    selected_prospects = [prospects[i] for i in selected_indices]
    selected_deals = [deals[i] for i in selected_indices]

    print(f"\nSelected {len(selected_indices)} prospect(s). Starting outreach pipeline...\n")

    # Step 6-7: Full pipeline for each selected prospect
    outreach_results = []
    for i, (prospect, deal) in enumerate(zip(selected_prospects, selected_deals)):
        brief = _format_prospect(prospect)
        on_event = _create_stream_handler()
        orchestrator = Orchestrator(interactive=False)
        pipeline_result = orchestrator.execute(brief, on_event=on_event)

        email_text = ""
        if pipeline_result.proposal:
            email_text = f"Subject: {pipeline_result.proposal.email_subject}\n\n{pipeline_result.proposal.email_body}"

        to_email = prospect["emails"][0] if prospect["emails"] else None

        outreach_results.append({
            "prospect": prospect,
            "deal": deal,
            "research": pipeline_result.research_brief.raw_brief if pipeline_result.research_brief else "",
            "email_text": email_text,
            "to_email": to_email,
        })

    # Step 8: Preview emails
    for i, result in enumerate(outreach_results):
        to = result["to_email"] or "(no email found)"
        print(f"\nEmail {i + 1}: {result['prospect']['title'][:40]} → {to}")
        print(result["email_text"])

    # Step 8.5: Fill missing emails
    missing = [r for r in outreach_results if not r["to_email"]]
    if missing:
        print(f"\n{len(missing)} prospect(s) have no email address.")
        for result in missing:
            name = result["prospect"]["title"][:40]
            addr = input(f"\n  Email for {name}: ").strip()
            if addr and "@" in addr:
                result["to_email"] = addr

    # Step 9: Send emails
    sent_count = 0
    sendable = [r for r in outreach_results if r["to_email"]]

    if sendable and gmail_configured():
        for i, r in enumerate(sendable):
            parsed = parse_email_text(r["email_text"])
            print(f"  {i + 1}. {r['prospect']['title'][:35]} → {r['to_email']}")
            print(f"     Subject: {parsed['subject']}")

        confirm = input(f"\nSend {len(sendable)} email(s) via Gmail? (y/n): ").strip().lower()
        if confirm == "y":
            for result in sendable:
                send_result = send_outreach_email(result["to_email"], result["email_text"])
                if send_result["success"]:
                    print(f"  Sent to {result['to_email']}")
                    sent_count += 1
                else:
                    print(f"  Failed: {result['to_email']} — {send_result['error']}")

    # Step 10: Save results
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_data = {
        "query": query,
        "timestamp": timestamp,
        "prospects": [],
    }

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
            "sent": bool(result["to_email"] and sent_count > 0),
        })

    output_path = os.path.join(OUTPUTS_DIR, f"outreach_{timestamp}.json")
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved: {output_path}")


def plan_command(company_input: str):
    """Show the execution plan without running it."""
    orchestrator = Orchestrator(interactive=True)
    orchestrator.plan(company_input)


def proposal_command(company_input: str):
    """Generate a full proposal with real-time streaming progress."""
    on_event = _create_stream_handler()
    orchestrator = Orchestrator(interactive=not on_event)
    result = orchestrator.execute(company_input, on_event=on_event)
    paths = orchestrator.save_results(result)
    print(f"\nOpen your proposal: {paths.get('proposal', 'N/A')}")


def interactive_mode():
    """Interactive input mode."""
    print("\nDescribe your target company. Include:")
    print("  - Company name and location")
    print("  - What they manufacture")
    print("  - Factory size (number of machines)")
    print("  - Known pain points")

    lines = []
    print("\nEnter company details (press Enter twice to submit):")
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)

    company_input = "\n".join(lines).strip()
    if not company_input:
        print("No input provided. Exiting.")
        return

    on_event = _create_stream_handler()
    orchestrator = Orchestrator(interactive=not on_event)
    result = orchestrator.execute(company_input, on_event=on_event)
    paths = orchestrator.save_results(result)
    print(f"\nOpen your proposal: {paths.get('proposal', 'N/A')}")


def example_mode():
    """Run with a pre-configured example."""
    for i, prospect in enumerate(EXAMPLE_PROSPECTS):
        print(f"\n  [{i + 1}] {prospect['name']}")
        print(f"      {prospect['input'][:80]}...")

    print("\n  [0] Enter custom company")

    choice = input("\nSelect a prospect (1-3, or 0 for custom): ").strip()
    if choice == "0":
        interactive_mode()
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(EXAMPLE_PROSPECTS):
            prospect = EXAMPLE_PROSPECTS[idx]
            print(f"\nSelected: {prospect['name']}")
            on_event = _create_stream_handler()
            orchestrator = Orchestrator(interactive=not on_event)
            result = orchestrator.execute(prospect["input"], on_event=on_event)
            paths = orchestrator.save_results(result)
            print(f"\nOpen your proposal: {paths.get('proposal', 'N/A')}")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")


# ── Main ──


def main():
    if len(sys.argv) < 2:
        example_mode()
        return

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print('Usage: python src/main.py search "metal stamping companies Germany"')
            return
        query = " ".join(sys.argv[2:])
        search_command(query)

    elif command == "proposal":
        if len(sys.argv) < 3:
            print('Usage: python src/main.py proposal "Company name, Country"')
            return
        company_input = " ".join(sys.argv[2:])
        proposal_command(company_input)

    elif command == "plan":
        if len(sys.argv) < 3:
            print('Usage: python src/main.py plan "Company name, Country"')
            return
        company_input = " ".join(sys.argv[2:])
        plan_command(company_input)

    elif command == "--interactive":
        interactive_mode()

    elif command == "--example":
        example_mode()

    else:
        # Backward compat: treat all args as company input for proposal
        company_input = " ".join(sys.argv[1:])
        proposal_command(company_input)


if __name__ == "__main__":
    main()
