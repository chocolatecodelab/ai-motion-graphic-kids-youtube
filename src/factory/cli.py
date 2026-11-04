"""`factory` command-line interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from factory import __version__
from factory.config import get_settings
from factory.doctor import Status, run_all
from factory.log import configure_logging

app = typer.Typer(help="AI Kids Educational Animation Factory", no_args_is_help=True)
console = Console()

_STYLE = {Status.OK: "green", Status.WARN: "yellow", Status.FAIL: "red"}


@app.callback()
def _main() -> None:
    configure_logging(get_settings().log_level)


@app.command()
def version() -> None:
    """Print the factory version."""
    console.print(__version__)


@app.command()
def doctor() -> None:
    """Check tools, services and configuration. Exits 1 if any check fails."""
    results = run_all(get_settings())
    table = Table(title="factory doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail", overflow="fold")
    for r in results:
        table.add_row(r.name, f"[{_STYLE[r.status]}]{r.status.value}[/]", r.detail)
    console.print(table)
    if any(r.status is Status.FAIL for r in results):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
