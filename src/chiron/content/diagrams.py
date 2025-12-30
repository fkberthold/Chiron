"""PlantUML diagram handling."""

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_plantuml_blocks(content: str) -> list[str]:
    """Extract PlantUML code blocks from markdown content.

    Args:
        content: Markdown content potentially containing PlantUML blocks

    Returns:
        List of PlantUML source code strings
    """
    pattern = r"```plantuml\s*\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)
    return [match.strip() for match in matches]


def save_diagram(
    puml_content: str,
    output_dir: Path,
    name: str,
) -> Path:
    """Save PlantUML content to a file.

    Args:
        puml_content: PlantUML source code
        output_dir: Directory to save the file
        name: Base name for the file (without extension)

    Returns:
        Path to the saved file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.puml"
    output_path.write_text(puml_content)
    return output_path


def render_diagram(puml_path: Path, output_format: str = "png") -> Path | None:
    """Render PlantUML to image using plantuml command.

    Args:
        puml_path: Path to .puml file
        output_format: Output format (png, svg)

    Returns:
        Path to rendered image, or None if rendering failed
    """
    try:
        result = subprocess.run(
            ["plantuml", f"-t{output_format}", str(puml_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return puml_path.with_suffix(f".{output_format}")
        else:
            logger.warning(
                "PlantUML rendering failed for %s: %s",
                puml_path,
                result.stderr or result.stdout,
            )
    except FileNotFoundError:
        logger.debug("plantuml command not found - skipping diagram rendering")

    return None
