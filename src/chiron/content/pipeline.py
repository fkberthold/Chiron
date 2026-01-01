"""Pipeline for generating lesson artifacts."""

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from chiron.content.audio import AudioConfig, generate_audio
from chiron.content.diagrams import render_diagram, save_diagram
from chiron.content.parser import ParsedLesson

logger = logging.getLogger(__name__)


@dataclass
class DiagramResult:
    """Result of diagram processing."""

    puml_path: Path
    png_path: Path | None  # None if rendering failed
    title: str
    caption: str

    @property
    def rendered(self) -> bool:
        """Check if the diagram was successfully rendered to PNG."""
        return self.png_path is not None and self.png_path.exists()


@dataclass
class LessonArtifacts:
    """Container for all generated lesson artifacts."""

    output_dir: Path
    script_path: Path
    audio_path: Path | None
    markdown_path: Path
    pdf_path: Path | None
    diagrams: list[DiagramResult]
    exercises_path: Path
    srs_items_added: int

    @property
    def diagrams_rendered(self) -> int:
        """Count of successfully rendered diagrams."""
        return sum(1 for d in self.diagrams if d.rendered)

    @property
    def diagrams_total(self) -> int:
        """Total number of diagrams."""
        return len(self.diagrams)


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
        "weasyprint": shutil.which("weasyprint") is not None,
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
    audio_config: AudioConfig | None = None,
) -> LessonArtifacts:
    """Generate all lesson artifacts from parsed content.

    Args:
        parsed: Parsed lesson content
        output_dir: Directory to write artifacts
        audio_config: Optional audio generation config. If None, uses default
            which exports script.txt for external TTS.

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
    diagram_results: list[DiagramResult] = []

    if parsed.diagrams:
        diagrams_dir = output_dir / "diagrams"
        for diagram in parsed.diagrams:
            slug = slugify(diagram.title)
            puml_path = save_diagram(diagram.puml_code, diagrams_dir, slug)

            # Try to render to PNG
            png_path = render_diagram(puml_path, "png")

            diagram_results.append(
                DiagramResult(
                    puml_path=puml_path,
                    png_path=png_path,
                    title=diagram.title,
                    caption=diagram.caption,
                )
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

    # Add Visual Aids section - only include successfully rendered diagrams
    rendered_diagrams = [d for d in diagram_results if d.rendered]
    if rendered_diagrams:
        md_lines.append("## Visual Aids")
        md_lines.append("")
        for diag in rendered_diagrams:
            md_lines.append(f"### {diag.title}")
            md_lines.append("")
            # png_path is guaranteed non-None when rendered is True
            assert diag.png_path is not None
            md_lines.append(f"![{diag.title}](diagrams/{diag.png_path.name})")
            md_lines.append("")
            if diag.caption:
                md_lines.append(diag.caption)
                md_lines.append("")

    # Log warning for failed diagrams
    failed_diagrams = [d for d in diagram_results if not d.rendered]
    for diag in failed_diagrams:
        logger.warning(
            "Diagram '%s' not included in markdown (rendering failed): %s",
            diag.title,
            diag.puml_path,
        )

    markdown_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Generate PDF via pandoc with weasyprint engine (no LaTeX needed)
    pdf_path: Path | None = None
    tools = check_available_tools()
    if tools.get("pandoc") and tools.get("weasyprint"):
        pdf_path = output_dir / "lesson.pdf"
        try:
            result = subprocess.run(
                [
                    "pandoc",
                    str(markdown_path),
                    "-o",
                    str(pdf_path),
                    "--pdf-engine=weasyprint",
                ],
                capture_output=True,
                text=True,
                cwd=output_dir,  # Run from output dir so relative image paths work
            )
            if result.returncode != 0:
                logger.warning("Pandoc failed: %s", result.stderr)
                pdf_path = None
        except Exception as e:
            logger.warning("Pandoc error: %s", e)
            pdf_path = None
    elif tools.get("pandoc") and not tools.get("weasyprint"):
        logger.info("PDF generation skipped: weasyprint not available")

    # Generate audio from script
    audio_path: Path | None = None
    audio_config = audio_config or AudioConfig()

    # Auto-select TTS engine based on availability if using default export mode
    if audio_config.engine == "export":
        # Check if a TTS engine is available and upgrade if so
        if tools.get("coqui"):
            audio_config = AudioConfig(engine="coqui")
            logger.info("Using Coqui TTS for audio generation")
        elif tools.get("piper"):
            audio_config = AudioConfig(engine="piper")
            logger.info("Using Piper TTS for audio generation")
        else:
            logger.info("No TTS engine available, exporting script.txt for external TTS")

    audio_output = output_dir / "audio"
    audio_path = generate_audio(parsed.audio_script, audio_output, audio_config)

    if audio_path and audio_config.engine != "export":
        logger.info("Audio generated: %s", audio_path)
    elif audio_path:
        logger.info("Script exported for external TTS: %s", audio_path)

    return LessonArtifacts(
        output_dir=output_dir,
        script_path=script_path,
        audio_path=audio_path,
        markdown_path=markdown_path,
        pdf_path=pdf_path,
        diagrams=diagram_results,
        exercises_path=exercises_path,
        srs_items_added=0,  # Database integration not yet done
    )
