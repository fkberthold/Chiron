"""Pipeline for generating lesson artifacts."""

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
