"""Pipeline for generating lesson artifacts."""

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from chiron.content.parser import ParsedLesson


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

    markdown_path.write_text("\n".join(md_lines), encoding="utf-8")

    return LessonArtifacts(
        output_dir=output_dir,
        script_path=script_path,
        audio_path=None,  # TTS not yet implemented
        markdown_path=markdown_path,
        pdf_path=None,  # Pandoc not yet implemented
        diagram_paths=[],  # Diagrams not yet implemented
        exercises_path=exercises_path,
        srs_items_added=0,  # Database integration not yet done
    )
