"""Command-line interface for Chiron."""

import json
import threading
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.tree import Tree

from chiron import __version__
from chiron.config import get_config
from chiron.display.progress import ResearchProgressDisplay
from chiron.orchestrator import Orchestrator
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore

console = Console()

# Phrases that suggest the agent has finished its analysis
_CONCLUSION_PHRASES = [
    "good luck",
    "you're all set",
    "you are all set",
    "ready to proceed",
    "let me know if",
    "feel free to",
    "happy learning",
    "enjoy your",
    "best of luck",
]


def _appears_concluded(response: str) -> bool:
    """Check if an agent response appears to conclude the conversation.

    Args:
        response: The agent's response text.

    Returns:
        True if the response contains conclusion phrases.
    """
    lower_response = response.lower()
    return any(phrase in lower_response for phrase in _CONCLUSION_PHRASES)


def _word_count(path: Path) -> int:
    """Count words in a text file."""
    return len(path.read_text().split())


def get_orchestrator() -> Orchestrator:
    """Create and return a configured Orchestrator instance.

    Returns:
        Orchestrator instance with all dependencies initialized.
    """
    config = get_config()
    config.ensure_directories()

    db = Database(config.database_path)
    db.initialize()

    vector_store = VectorStore(config.knowledge_bases_dir)

    return Orchestrator(
        db=db,
        vector_store=vector_store,
        lessons_dir=config.lessons_dir,
    )


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Chiron: AI-powered adaptive learning platform."""
    pass


@cli.command()
def init() -> None:
    """Initialize a new learning subject."""
    console.print("\n[bold cyan]Initialize a New Learning Subject[/bold cyan]\n")

    # Prompt for subject name
    subject_name = Prompt.ask(
        "[green]What subject do you want to learn?[/green]",
        default="",
    )
    if not subject_name.strip():
        console.print("[red]Subject name is required.[/red]")
        return

    # Convert to subject ID (lowercase, hyphens for spaces)
    subject_id = subject_name.lower().replace(" ", "-")

    # Prompt for purpose
    purpose = Prompt.ask(
        "[green]Why do you want to learn this? (Your learning goal)[/green]",
        default="",
    )
    if not purpose.strip():
        console.print("[red]Purpose statement is required.[/red]")
        return

    try:
        orchestrator = get_orchestrator()

        # Check if subject already exists
        existing = orchestrator.db.get_learning_goal(subject_id)
        if existing is not None:
            console.print(
                f"\n[yellow]Subject '{subject_id}' already exists.[/yellow]"
            )
            console.print(f"[dim]Purpose: {existing.purpose_statement}[/dim]\n")

            choice = Prompt.ask(
                "What would you like to do?",
                choices=["switch", "delete", "cancel"],
                default="switch",
            )

            if choice == "switch":
                orchestrator.set_active_subject(subject_id)
                console.print(
                    f"[green]Switched to subject: [bold]{subject_id}[/bold][/green]"
                )
                return
            elif choice == "delete":
                if Confirm.ask(
                    "[red]Delete and re-create this subject?[/red]",
                    default=False,
                ):
                    orchestrator.delete_subject(subject_id)
                    console.print(f"[dim]Deleted '{subject_id}'[/dim]")
                    # Continue to create new subject below
                else:
                    console.print("[dim]Cancelled.[/dim]")
                    return
            else:
                console.print("[dim]Cancelled.[/dim]")
                return

        # Initialize the subject
        goal = orchestrator.initialize_subject(subject_id, purpose)
        console.print(
            f"\n[green]Created learning subject:[/green] [bold]{goal.subject_id}[/bold]"
        )
        console.print(f"[dim]Purpose: {goal.purpose_statement}[/dim]")

        # Optionally start curriculum design
        if Confirm.ask(
            "\n[cyan]Would you like to start curriculum design now?[/cyan]",
            default=False,
        ):
            console.print(
                "\n[yellow]Starting curriculum design... "
                "(this may take a moment)[/yellow]\n"
            )
            try:
                response = orchestrator.start_curriculum_design()
                console.print(response)

                # Interactive curriculum design loop
                console.print(
                    "\n[dim]Answer the agent's questions to refine your curriculum. "
                    "Type [bold]'done'[/bold] to save and finalize, "
                    "or 'quit' to exit without saving.[/dim]\n"
                )

                while True:
                    user_input = Prompt.ask("[green]Your response[/green]")

                    if user_input.lower().strip() in ("quit", "exit", "q"):
                        console.print("[yellow]Exiting curriculum design.[/yellow]")
                        break

                    if user_input.lower().strip() == "done":
                        console.print(
                            "\n[green]Curriculum design complete! "
                            "Use 'chiron research start' to begin research.[/green]"
                        )
                        break

                    # Handle empty input
                    if not user_input.strip():
                        console.print(
                            "[dim]Type [bold]'done'[/bold] to save curriculum, "
                            "'quit' to exit, or enter a response.[/dim]"
                        )
                        continue

                    # Continue the conversation
                    response = orchestrator.continue_curriculum_design(user_input)
                    console.print(f"\n{response}\n")

                    # Check if agent appears to have concluded
                    if _appears_concluded(response):
                        console.print(
                            "\n[cyan]The agent seems to have finished. "
                            "Type [bold]'done'[/bold] to save the curriculum, "
                            "or continue if you have more questions.[/cyan]\n"
                        )

            except Exception as e:
                console.print(f"[red]Error during curriculum design: {e}[/red]")
        else:
            console.print(
                "\n[dim]You can start curriculum design later with "
                "'chiron research start'[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error initializing subject: {e}[/red]")


@cli.command()
def lesson() -> None:
    """Start today's lesson (assessment + learning)."""
    try:
        orchestrator = get_orchestrator()
        subject_id = orchestrator.get_active_subject()

        if subject_id is None:
            console.print(
                "[red]No active subject. Use 'chiron init' to create one "
                "or 'chiron use <subject>' to switch.[/red]"
            )
            return

        console.print(f"\n[bold cyan]Starting lesson for: {subject_id}[/bold cyan]\n")

        # Start assessment
        console.print("[yellow]Beginning knowledge assessment...[/yellow]\n")
        try:
            response = orchestrator.start_lesson()
            console.print(response)

            # Interactive assessment loop
            console.print(
                "\n[dim]Type your responses. Type 'done' when ready to "
                "generate your lesson.[/dim]\n"
            )

            while True:
                user_input = Prompt.ask("[green]Your response[/green]")

                if user_input.lower().strip() in ("quit", "exit", "q"):
                    console.print("[yellow]Exiting lesson.[/yellow]")
                    break

                if user_input.lower().strip() == "done":
                    console.print(
                        "\n[yellow]Generating personalized lesson...[/yellow]\n"
                    )

                    with console.status("[bold green]Creating lesson materials..."):
                        artifacts = orchestrator.generate_lesson()

                    # Display summary tree
                    tree = Tree(f"[bold]Lesson generated: {artifacts.output_dir}[/bold]")

                    # Script
                    word_count = _word_count(artifacts.script_path)
                    tree.add(f"[green]✓[/green] script.txt ({word_count:,} words)")

                    # Audio
                    if artifacts.audio_path:
                        audio_name = artifacts.audio_path.name
                        if artifacts.audio_path.suffix == ".txt":
                            tree.add(
                                f"[yellow]○[/yellow] {audio_name} (script for external TTS)"
                            )
                        else:
                            tree.add(f"[green]✓[/green] {audio_name}")
                    else:
                        tree.add("[yellow]○[/yellow] audio (TTS not available)")

                    # Markdown
                    tree.add("[green]✓[/green] lesson.md")

                    # PDF
                    if artifacts.pdf_path:
                        tree.add("[green]✓[/green] lesson.pdf")
                    else:
                        tree.add(
                            "[yellow]○[/yellow] lesson.pdf (pandoc/weasyprint not available)"
                        )

                    # Diagrams
                    if artifacts.diagrams:
                        rendered = artifacts.diagrams_rendered
                        total = artifacts.diagrams_total
                        if rendered == total:
                            status = f"[green]✓[/green] ({total} rendered)"
                        elif rendered > 0:
                            status = f"[yellow]△[/yellow] ({rendered}/{total} rendered)"
                        else:
                            status = f"[red]✗[/red] (0/{total} rendered)"
                        diagrams_branch = tree.add(f"diagrams/ {status}")
                        for d in artifacts.diagrams:
                            if d.rendered and d.png_path is not None:
                                diagrams_branch.add(
                                    f"[green]✓[/green] {d.png_path.name}"
                                )
                            else:
                                diagrams_branch.add(
                                    f"[red]✗[/red] {d.puml_path.name} (render failed)"
                                )
                    else:
                        tree.add("[dim]○[/dim] diagrams/ (none generated)")

                    # Exercises
                    exercises = json.loads(artifacts.exercises_path.read_text())
                    tree.add(f"[green]✓[/green] exercises.json ({len(exercises)} seeds)")

                    # SRS
                    if artifacts.srs_items_added > 0:
                        tree.add(
                            f"[green]✓[/green] {artifacts.srs_items_added} SRS items added"
                        )

                    console.print(tree)
                    console.print("\n[dim]Run 'chiron exercises' to practice.[/dim]")
                    break

                # Continue assessment
                response = orchestrator.continue_assessment(user_input)
                console.print(f"\n{response}\n")

        except Exception as e:
            console.print(f"[red]Error during lesson: {e}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
def exercises() -> None:
    """Work through reinforcement exercises."""
    console.print("[yellow]Exercises command not yet implemented[/yellow]")


@cli.command()
@click.option("--view", is_flag=True, help="View skill tree visualization")
def tree(view: bool) -> None:
    """View or manage the skill tree."""
    try:
        orchestrator = get_orchestrator()
        subject_id = orchestrator.get_active_subject()

        if subject_id is None:
            console.print(
                "[red]No active subject. Use 'chiron init' to create one "
                "or 'chiron use <subject>' to switch.[/red]"
            )
            return

        # Get knowledge tree from database
        nodes = orchestrator.db.get_knowledge_tree(subject_id)

        if not nodes:
            console.print(
                f"[yellow]No skill tree found for '{subject_id}'. "
                f"Run 'chiron research start' to build the curriculum.[/yellow]"
            )
            return

        # Display as Rich table
        table = Table(
            title=f"Skill Tree: {subject_id}",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("ID", style="dim", width=6)
        table.add_column("Title", style="green")
        table.add_column("Depth", justify="center", width=6)
        table.add_column("Critical", justify="center", width=8)
        table.add_column("Description", style="dim")

        for node in nodes:
            # Indent based on depth
            indent = "  " * node.depth
            title = f"{indent}{node.title}"
            critical = "[bold red]*[/bold red]" if node.is_goal_critical else ""

            table.add_row(
                str(node.id) if node.id else "-",
                title,
                str(node.depth),
                critical,
                (node.description or "")[:50] + "..."
                if node.description and len(node.description) > 50
                else node.description or "",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
def progress() -> None:
    """Show learning progress statistics."""
    console.print("[yellow]Progress command not yet implemented[/yellow]")


@cli.command()
def subjects() -> None:
    """List all learning subjects."""
    try:
        orchestrator = get_orchestrator()
        goals = orchestrator.list_subjects()
        active_subject = orchestrator.get_active_subject()

        if not goals:
            console.print(
                "[yellow]No subjects found. Use 'chiron init' to create one.[/yellow]"
            )
            return

        table = Table(
            title="Learning Subjects",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Subject", style="green")
        table.add_column("Status", justify="center")
        table.add_column("Purpose", style="dim")
        table.add_column("Active", justify="center", width=8)

        for goal in goals:
            is_active = goal.subject_id == active_subject
            active_marker = "[bold green]*[/bold green]" if is_active else ""

            # Status styling
            status_style = {
                "initializing": "[yellow]",
                "researching": "[blue]",
                "ready": "[green]",
                "paused": "[dim]",
            }.get(goal.status.value, "")
            status_display = f"{status_style}{goal.status.value}[/]"

            table.add_row(
                goal.subject_id,
                status_display,
                (goal.purpose_statement[:40] + "...")
                if len(goal.purpose_statement) > 40
                else goal.purpose_statement,
                active_marker,
            )

        console.print(table)
        console.print(
            "\n[dim]Use 'chiron use <subject>' to switch active subject[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error listing subjects: {e}[/red]")


@cli.command()
@click.argument("subject_id")
def use(subject_id: str) -> None:
    """Switch to a different learning subject."""
    try:
        orchestrator = get_orchestrator()
        orchestrator.set_active_subject(subject_id)
        console.print(f"[green]Switched to subject: [bold]{subject_id}[/bold][/green]")

    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        console.print("[dim]Use 'chiron subjects' to see available subjects.[/dim]")
    except Exception as e:
        console.print(f"[red]Error switching subject: {e}[/red]")


@cli.command()
@click.argument("subject_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def delete(subject_id: str, force: bool) -> None:
    """Delete a learning subject and all its data."""
    try:
        orchestrator = get_orchestrator()

        # Check if subject exists
        goal = orchestrator.db.get_learning_goal(subject_id)
        if goal is None:
            console.print(f"[red]Subject '{subject_id}' not found.[/red]")
            console.print("[dim]Use 'chiron subjects' to see available subjects.[/dim]")
            return

        # Confirm deletion unless --force
        if not force:
            console.print("\n[yellow]This will permanently delete:[/yellow]")
            console.print(f"  - Subject: [bold]{subject_id}[/bold]")
            console.print(f"  - Purpose: {goal.purpose_statement}")
            console.print("  - All lessons, progress, and research data\n")

            if not Confirm.ask(
                "[red]Are you sure you want to delete this subject?[/red]",
                default=False,
            ):
                console.print("[dim]Deletion cancelled.[/dim]")
                return

        # Delete the subject
        if orchestrator.delete_subject(subject_id):
            console.print(
                f"[green]Deleted subject: [bold]{subject_id}[/bold][/green]"
            )
        else:
            console.print(f"[red]Failed to delete subject '{subject_id}'.[/red]")

    except Exception as e:
        console.print(f"[red]Error deleting subject: {e}[/red]")


@cli.group()
def research() -> None:
    """Manage research phase."""
    pass


@research.command("start")
def research_start() -> None:
    """Start research for current subject."""
    try:
        orchestrator = get_orchestrator()
        subject_id = orchestrator.get_active_subject()

        if subject_id is None:
            console.print(
                "[red]No active subject. Use 'chiron init' to create one "
                "or 'chiron use <subject>' to switch.[/red]"
            )
            return

        console.print(
            f"\n[bold cyan]Starting research for: {subject_id}[/bold cyan]\n"
        )

        # Check if curriculum design has been done
        nodes = orchestrator.db.get_knowledge_tree(subject_id)
        if not nodes:
            console.print(
                "[yellow]No curriculum found for this subject.[/yellow]\n"
                "[dim]The research agent will explore the topic generally. "
                "For structured research, run curriculum design first during "
                "'chiron init'.[/dim]\n"
            )

        progress_display = ResearchProgressDisplay(console, orchestrator)
        progress_display.start_timer()

        try:
            # Run initial research with live updating progress display
            response_container = {}

            def run_research():
                response_container["result"] = orchestrator.start_research()

            # Start research in background thread
            research_thread = threading.Thread(target=run_research, daemon=True)
            research_thread.start()

            # Live update the progress display while research runs
            with Live(
                progress_display.render(), console=console, refresh_per_second=2
            ) as live:
                while research_thread.is_alive():
                    live.update(progress_display.render())
                    time.sleep(0.5)

                # Final update after completion
                progress_display.update_status("Research complete.")
                live.update(progress_display.render())

            response = response_container.get("result", "")
            console.print(f"\n{response}\n")

            # Interactive loop
            console.print(
                "[dim]Enter a topic to research, or type "
                "[bold]'done'[/bold] to finish.[/dim]\n"
            )

            while True:
                user_input = Prompt.ask("[green]Topic or command[/green]")

                if user_input.lower().strip() in ("quit", "exit", "q", "done"):
                    console.print("\n[green]Research session complete![/green]")
                    break

                if not user_input.strip():
                    continue

                # Research with live updates
                progress_display.set_active_topic(user_input)
                response_container = {}

                def run_continue_research():
                    response_container["result"] = orchestrator.continue_research(
                        user_input
                    )

                # Start research in background thread
                research_thread = threading.Thread(
                    target=run_continue_research, daemon=True
                )
                research_thread.start()

                # Live update the progress display while research runs
                with Live(
                    progress_display.render(), console=console, refresh_per_second=2
                ) as live:
                    while research_thread.is_alive():
                        live.update(progress_display.render())
                        time.sleep(0.5)

                    # Final update after completion
                    progress_display.set_active_topic(None)
                    progress_display.update_status("Research complete.")
                    live.update(progress_display.render())

                response = response_container.get("result", "")
                console.print(f"\n{response}\n")

        except Exception as e:
            console.print(f"[red]Error during research: {e}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


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
