"""Pipeline for generating lesson artifacts."""

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from chiron.content.diagrams import render_diagram, save_diagram
from chiron.content.parser import ParsedLesson

logger = logging.getLogger(__name__)


@dataclass
class LessonArtifacts:
    """Container for all generated lesson artifacts."""

    output_dir: Path
    script_path: Path
    audio_path: Path | None
    markdown_path: Path
    pdf_path: Path | None
    diagram_paths: list[Path]
    exercises_path: Path
    srs_items_added: int


def _try_import(module_name: str) -> bool:
    """Try to import a module and return whether it succeeded."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def check_available_tools() -> dict[str, bool]:
    """Check which content generation tools are available.

    Returns:
        Dictionary mapping tool names to availability booleans.
    """
    return {
        "coqui": _try_import("TTS"),
        "piper": _try_import("piper"),
        "plantuml": shutil.which("plantuml") is not None,
        "pandoc": shutil.which("pandoc") is not None,
    }


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug.

    Args:
        text: Text to slugify

    Returns:
        Lowercase slug with hyphens instead of spaces
    """
    # Lowercase
    slug = text.lower()
    # Remove non-alphanumeric (except spaces and hyphens)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    # Collapse multiple hyphens/spaces into single hyphen
    slug = re.sub(r"[\s-]+", "-", slug.strip())
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug


def generate_lesson_artifacts(
    parsed: ParsedLesson,
    output_dir: Path,
) -> LessonArtifacts:
    """Generate all lesson artifacts from parsed content.

    Args:
        parsed: Parsed lesson content
        output_dir: Directory to write artifacts

    Returns:
        LessonArtifacts with paths to all generated files
    """
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write script.txt
    script_path = output_dir / "script.txt"
    script_path.write_text(parsed.audio_script, encoding="utf-8")

    # Write exercises.json
    exercises_path = output_dir / "exercises.json"
    exercises_path.write_text(
        json.dumps(parsed.exercise_seeds, indent=2),
        encoding="utf-8",
    )

    # Process diagrams
    diagram_paths: list[Path] = []
    diagram_refs: list[tuple[str, str, str]] = []  # (title, filename, caption)

    if parsed.diagrams:
        diagrams_dir = output_dir / "diagrams"
        for diagram in parsed.diagrams:
            slug = slugify(diagram.title)
            puml_path = save_diagram(diagram.puml_code, diagrams_dir, slug)
            diagram_paths.append(puml_path)

            # Try to render to PNG
            render_diagram(puml_path, "png")

            # Store reference for markdown (use .png extension for image ref)
            diagram_refs.append((diagram.title, f"{slug}.png", diagram.caption))

    # Write lesson.md
    markdown_path = output_dir / "lesson.md"
    md_lines = [
        f"# {parsed.title}",
        "",
        "## Learning Objectives",
        "",
    ]
    for i, obj in enumerate(parsed.objectives, 1):
        md_lines.append(f"{i}. {obj}")
    md_lines.append("")

    # Add Visual Aids section if there are diagrams
    if diagram_refs:
        md_lines.append("## Visual Aids")
        md_lines.append("")
        for title, filename, caption in diagram_refs:
            md_lines.append(f"### {title}")
            md_lines.append("")
            md_lines.append(f"![{title}](diagrams/{filename})")
            md_lines.append("")
            if caption:
                md_lines.append(caption)
                md_lines.append("")

    markdown_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Generate PDF via pandoc if available
    pdf_path: Path | None = None
    tools = check_available_tools()
    if tools.get("pandoc"):
        pdf_path = output_dir / "lesson.pdf"
        try:
            result = subprocess.run(
                ["pandoc", str(markdown_path), "-o", str(pdf_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.warning("Pandoc failed: %s", result.stderr)
                pdf_path = None
        except Exception as e:
            logger.warning("Pandoc error: %s", e)
            pdf_path = None

    return LessonArtifacts(
        output_dir=output_dir,
        script_path=script_path,
        audio_path=None,  # TTS not yet implemented
        markdown_path=markdown_path,
        pdf_path=pdf_path,
        diagram_paths=diagram_paths,
        exercises_path=exercises_path,
        srs_items_added=0,  # Database integration not yet done
    )
