from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from rich.padding import Padding

_SEVERITY_STYLE = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "dim"}
_STATUS_STYLE = {"success": "bold green", "running": "cyan", "idle": "dim", "done": "blue"}


class RedTeamDisplay:
    """Live terminal display — mirrors display.py from the reference repo."""

    def __init__(self, orchestrator):
        self.orch = orchestrator
        self._live = Live(refresh_per_second=4, screen=False)

    def __enter__(self):
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        self._live.__exit__(*args)

    def update(self):
        self._live.update(self._render())

    def _render(self) -> Group:
        findings = sum(1 for r in self.orch.all_results if r.success)

        info = Table(show_header=False, box=None, padding=(0, 1))
        info.add_row("Status", Text(self.orch.status, style="cyan"))
        info.add_row("Round", str(self.orch.turns))
        info.add_row("Skills", ", ".join(self.orch.loaded_skills) or "—")
        info.add_row("Findings", Text(str(findings), style="bold red" if findings else "dim"))
        orch_panel = Panel(info, title="[bold red]Orchestrator[/bold red]", border_style="red")

        pool = Table(border_style="dim")
        pool.add_column("Name", style="dim")
        pool.add_column("Attack Type")
        pool.add_column("Status")
        pool.add_column("Turns", justify="right")
        pool.add_column("Hits", justify="right")

        for a in self.orch.pool.attackers.values():
            hits = sum(1 for r in a.results if r.success)
            pool.add_row(
                a.name,
                a.attack_type[:45],
                Text(a.status, style=_STATUS_STYLE.get(a.status, "white")),
                str(a.turns),
                Text(str(hits), style="bold red" if hits else "dim"),
            )

        return Group(orch_panel, Padding(pool, (1, 0, 0, 0)))
