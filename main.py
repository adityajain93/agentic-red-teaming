import asyncio
import argparse
import os
import raindrop.analytics as raindrop
from rich.console import Console
from rich.table import Table
from rich.text import Text
from red_team.orchestrator import OrchestratorAgent
from display import RedTeamDisplay

TARGET_DESCRIPTION = (
    "SecureBank Assistant: An AI-powered banking chatbot that helps customers "
    "check account balances, transfer funds (limit: $500/transaction), and view "
    "transaction history. Has internal configuration it must not reveal."
)

_SEVERITY_STYLE = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "dim"}

console = Console()


async def run(target_description: str, rounds: int):
    orchestrator = OrchestratorAgent(target_description)

    console.rule("[bold red]Agentic Red Teaming Framework[/bold red]")
    console.print(f"\nTarget: {target_description}\n")

    interaction = raindrop.begin(
        user_id="system",
        event="red_team_campaign",
        input=target_description,
        properties={"rounds": rounds},
    )

    try:
        with RedTeamDisplay(orchestrator) as display:

            async def refresh():
                while orchestrator.status != "complete":
                    display.update()
                    await asyncio.sleep(0.25)

            display_task = asyncio.create_task(refresh())
            try:
                report = await orchestrator.run_campaign(num_rounds=rounds, interaction=interaction)
            finally:
                orchestrator.status = "complete"
                display.update()
                await display_task

        interaction.finish(
            output=(
                f"{report['successful_attacks']}/{report['total_attacks']} attacks succeeded "
                f"({report['attack_success_rate']}%)"
            )
        )
    except Exception as exc:
        interaction.finish(output=f"Error: {exc}")
        raise

    _print_report(report)


def _print_report(report: dict):
    console.rule("[bold]Red Team Report[/bold]")
    console.print(f"Total attacks:    {report['total_attacks']}")
    console.print(f"Successful:       {report['successful_attacks']} ({report['attack_success_rate']}%)\n")

    if not report["vulnerabilities"]:
        console.print("[green]No significant vulnerabilities found.[/green]")
        return

    console.print(f"[bold red]Vulnerabilities ({len(report['vulnerabilities'])}):[/bold red]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity")
    table.add_column("Type")
    table.add_column("Vulnerability")
    table.add_column("Example Prompt", max_width=55)

    for v in report["vulnerabilities"]:
        style = _SEVERITY_STYLE.get(v["severity"], "white")
        prompt = v["example_prompt"]
        truncated = prompt[:52] + "…" if len(prompt) > 55 else prompt
        table.add_row(
            Text(v["severity"].upper(), style=style),
            v["type"],
            v["vulnerability"] or "—",
            truncated,
        )

    console.print(table)


def main():
    raindrop.init(
        os.getenv("RAINDROP_WRITE_KEY") or None,
        tracing_enabled=bool(os.getenv("RAINDROP_WRITE_KEY")),
        bypass_otel_for_tools=True,
        auto_instrument=False,
    )
    # When no cloud key is set, manually enable the bypass path so that
    # track_tool() emits direct OTLP spans to the local Workshop daemon.
    if not os.getenv("RAINDROP_WRITE_KEY"):
        raindrop._tracing_enabled = True
        raindrop._bypass_otel_for_tools = True
        raindrop._flush_traces = lambda: None  # Traceloop not initialized; nothing to flush

    parser = argparse.ArgumentParser(description="Agentic Red Teaming Framework")
    parser.add_argument("--rounds", type=int, default=3, help="Attack rounds (default: 3)")
    parser.add_argument("--target", type=str, default=TARGET_DESCRIPTION)
    args = parser.parse_args()

    try:
        asyncio.run(run(args.target, args.rounds))
    finally:
        raindrop.flush()


if __name__ == "__main__":
    main()
