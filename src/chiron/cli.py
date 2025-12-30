"""Command-line interface for Chiron."""

import click
from rich.console import Console

from chiron import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Chiron: AI-powered adaptive learning platform."""
    pass


@cli.command()
def init() -> None:
    """Initialize a new learning subject."""
    console.print("[yellow]Init command not yet implemented[/yellow]")


@cli.command()
def lesson() -> None:
    """Start today's lesson (assessment + learning)."""
    console.print("[yellow]Lesson command not yet implemented[/yellow]")


@cli.command()
def exercises() -> None:
    """Work through reinforcement exercises."""
    console.print("[yellow]Exercises command not yet implemented[/yellow]")


@cli.command()
@click.option("--view", is_flag=True, help="View skill tree visualization")
def tree(view: bool) -> None:
    """View or manage the skill tree."""
    console.print("[yellow]Tree command not yet implemented[/yellow]")


@cli.command()
def progress() -> None:
    """Show learning progress statistics."""
    console.print("[yellow]Progress command not yet implemented[/yellow]")


@cli.command()
def subjects() -> None:
    """List all learning subjects."""
    console.print("[yellow]Subjects command not yet implemented[/yellow]")


@cli.command()
@click.argument("subject_id")
def use(subject_id: str) -> None:
    """Switch to a different learning subject."""
    console.print(f"[yellow]Switching to {subject_id} not yet implemented[/yellow]")


@cli.group()
def research() -> None:
    """Manage research phase."""
    pass


@research.command("start")
def research_start() -> None:
    """Start research for current subject."""
    console.print("[yellow]Research start not yet implemented[/yellow]")


@research.command("status")
def research_status() -> None:
    """Check research progress."""
    console.print("[yellow]Research status not yet implemented[/yellow]")


@research.command("pause")
def research_pause() -> None:
    """Pause research."""
    console.print("[yellow]Research pause not yet implemented[/yellow]")


@research.command("resume")
def research_resume() -> None:
    """Resume research."""
    console.print("[yellow]Research resume not yet implemented[/yellow]")
