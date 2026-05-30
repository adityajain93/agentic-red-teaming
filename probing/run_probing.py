"""
Standalone black-box refusal suppression prober.

Tests abliteration-derived patterns against any model via API.
No weight access required — works with any OpenAI-compatible endpoint.

Usage:
    python probing/run_probing.py --agent child-mental-health
    python probing/run_probing.py --agent bank --topic "admin credentials"
    python probing/run_probing.py --agent safety-model --topic "dangerous knowledge"
    python probing/run_probing.py --agent child-mental-health --summary
"""

import asyncio
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import raindrop.analytics as raindrop
from rich.console import Console
from rich.table import Table
from rich.text import Text

from target.registry import AGENTS
from probing.prober import Prober

console = Console()


def _print_summary(findings: dict) -> None:
    summary = findings["summary"]
    method = findings.get("method", "unknown")

    console.rule("[bold cyan]Black-Box Probing Results[/bold cyan]")
    console.print(f"Agent:           [bold]{findings['agent']}[/bold]")
    console.print(f"Method:          {method}")
    console.print(f"Topic tested:    {findings['harmful_topic_tested']}")
    console.print(f"Analyzed at:     {findings['analyzed_at']}\n")
    if findings.get("note"):
        console.print(f"[dim]{findings['note']}[/dim]\n")

    console.print(f"Patterns tested:         {summary['patterns_tested']}")
    console.print(f"Patterns that bypassed:  {summary['patterns_that_suppressed_refusal']}")
    console.print(f"Best pattern:            {summary['best_pattern']}")
    console.print(f"Best suppression rate:   {summary['best_suppression_rate']:.0%}\n")

    effective = [v for v in findings.get("attack_vectors", []) if v["suppression_rate"] > 0]
    if not effective:
        console.print("[green]No patterns bypassed refusals.[/green]")
    else:
        table = Table(show_header=True, header_style="bold", show_lines=True)
        table.add_column("Pattern", min_width=28)
        table.add_column("Category", min_width=20)
        table.add_column("Suppression Rate", justify="right")
        table.add_column("Probes", justify="right")
        for v in sorted(effective, key=lambda x: -x["suppression_rate"]):
            rate = v["suppression_rate"]
            style = "bold red" if rate >= 0.8 else ("red" if rate >= 0.5 else "yellow")
            table.add_row(v["name"], v["category"], Text(f"{rate:.0%}", style=style), str(v["probes_sent"]))
        console.print(table)

    child_probes = findings.get("child_safety_probes", [])
    if child_probes:
        console.print("\n[bold]Child Safety Probes:[/bold]")
        for p in child_probes:
            rate = p["suppression_rate"]
            style = "red" if rate > 0 else "green"
            console.print(
                f"  {p['name']}: [{style}]{rate:.0%} bypass[/{style}] "
                f"({p['successes']}/{p['total_probes']} probes)"
            )

    console.print(f"\n[dim]Full findings: probing/findings/{findings['agent']}.json[/dim]")


async def run(args) -> None:
    prober = Prober(agent_key=args.agent)

    if args.summary:
        if not prober.has_findings():
            console.print(f"[red]No findings for '{args.agent}'. Run without --summary first.[/red]")
            return
        _print_summary(prober.load_findings())
        return

    console.rule("[bold cyan]Black-Box Probing[/bold cyan]")
    console.print(f"[dim]Method: black-box API probing (no weight access required)[/dim]")
    console.print(f"Agent:  [bold]{args.agent}[/bold]")
    console.print(f"Topic:  {args.topic}\n")

    raindrop.init(
        os.getenv("RAINDROP_WRITE_KEY") or None,
        tracing_enabled=bool(os.getenv("RAINDROP_WRITE_KEY")),
        bypass_otel_for_tools=True,
        auto_instrument=False,
    )
    if not os.getenv("RAINDROP_WRITE_KEY"):
        raindrop._tracing_enabled = True
        raindrop._bypass_otel_for_tools = True
        raindrop._flush_traces = lambda: None

    interaction = raindrop.begin(
        user_id="system",
        event="black_box_probing",
        input=args.topic,
        properties={"agent": args.agent, "topic": args.topic, "method": "black_box"},
    )

    try:
        target = AGENTS[args.agent]["factory"]()
        findings = await prober.probe(
            target=target,
            harmful_topic=args.topic,
            concurrency=args.concurrency,
            interaction=interaction,
        )
        interaction.finish(
            output=(
                f"{findings['summary']['patterns_that_suppressed_refusal']}/"
                f"{findings['summary']['patterns_tested']} patterns bypassed. "
                f"Best: {findings['summary']['best_pattern']} "
                f"({findings['summary']['best_suppression_rate']:.0%})"
            )
        )
    except Exception as exc:
        interaction.finish(output=f"Error: {exc}")
        raise
    finally:
        raindrop.flush()

    _print_summary(findings)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Black-box refusal suppression probing — works against any API model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--agent", default="child-mental-health", choices=list(AGENTS))
    parser.add_argument("--topic", default="self-harm methods")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--summary", action="store_true", help="Print summary of existing findings")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
