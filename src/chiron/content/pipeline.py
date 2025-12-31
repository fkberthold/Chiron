"""Pipeline for generating lesson artifacts."""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path


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
    # Remove non-alphanumeric (except spaces)
    slug = re.sub(r"[^a-z0-9\s]", "", slug)
    # Replace spaces with hyphens
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug
