"""PlantUML diagram handling."""

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class RenderResult:
    """Result of a PlantUML render attempt."""

    success: bool
    output_path: Path | None
    error_message: str | None = None


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


def render_diagram(puml_path: Path, output_format: str = "png") -> RenderResult:
    """Render PlantUML to image using plantuml command.

    Args:
        puml_path: Path to .puml file
        output_format: Output format (png, svg)

    Returns:
        RenderResult with success status, output path, and any error message
    """
    try:
        result = subprocess.run(
            ["plantuml", f"-t{output_format}", str(puml_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return RenderResult(
                success=True,
                output_path=puml_path.with_suffix(f".{output_format}"),
            )
        else:
            error_msg = result.stderr or result.stdout
            logger.warning(
                "PlantUML rendering failed for %s: %s",
                puml_path,
                error_msg,
            )
            return RenderResult(
                success=False,
                output_path=None,
                error_message=error_msg,
            )
    except FileNotFoundError:
        logger.debug("plantuml command not found - skipping diagram rendering")
        return RenderResult(
            success=False,
            output_path=None,
            error_message="plantuml command not found",
        )


PLANTUML_FIX_PROMPT = """\
You are a PlantUML syntax expert. Fix the following PlantUML code that failed to render.

## PlantUML Code That Failed:
```plantuml
{puml_code}
```

## Error Message:
{error_message}

## Common Issues to Check:
1. Mindmaps require @startmindmap/@endmindmap, NOT @startuml/@enduml
2. Avoid special characters, emojis, or unicode in labels
3. Keep labels short (under 30 characters)
4. Use proper arrow syntax: ->, -->, ->>
5. Class/state/sequence diagrams use @startuml/@enduml
6. Each diagram type has specific syntax requirements

## Your Task:
Return ONLY the corrected PlantUML code. No explanations, no markdown code fences.
Just the raw PlantUML starting with @ and ending with @end*.
"""


def fix_plantuml_with_claude(
    puml_code: str,
    error_message: str,
    client: Anthropic | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """Use Claude to fix PlantUML syntax errors.

    Args:
        puml_code: The PlantUML code that failed to render
        error_message: The error message from PlantUML
        client: Optional Anthropic client (creates one if not provided)
        model: Model to use for fixing

    Returns:
        Corrected PlantUML code
    """
    if client is None:
        client = Anthropic()

    prompt = PLANTUML_FIX_PROMPT.format(
        puml_code=puml_code,
        error_message=error_message,
    )

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text from response
    fixed_code = ""
    for block in response.content:
        if hasattr(block, "text"):
            fixed_code += block.text

    return fixed_code.strip()


def render_diagram_with_retry(
    puml_path: Path,
    output_format: str = "png",
    max_retries: int = 2,
    client: Anthropic | None = None,
) -> RenderResult:
    """Render PlantUML with automatic retry using Claude to fix errors.

    Args:
        puml_path: Path to .puml file
        output_format: Output format (png, svg)
        max_retries: Maximum number of fix attempts
        client: Optional Anthropic client for fix attempts

    Returns:
        RenderResult with success status, output path, and any error message
    """
    # First attempt
    result = render_diagram(puml_path, output_format)

    if result.success:
        return result

    # If plantuml not found, no point retrying
    if result.error_message == "plantuml command not found":
        return result

    # Read the original PUML content
    puml_code = puml_path.read_text()

    # Retry loop with Claude fixes
    for attempt in range(max_retries):
        logger.info(
            "Attempting to fix PlantUML diagram %s (attempt %d/%d)",
            puml_path.name,
            attempt + 1,
            max_retries,
        )

        try:
            fixed_code = fix_plantuml_with_claude(
                puml_code,
                result.error_message or "Unknown error",
                client=client,
            )

            # Write fixed code back to file
            puml_path.write_text(fixed_code)
            puml_code = fixed_code  # Use fixed code for next iteration if needed

            # Try rendering again
            result = render_diagram(puml_path, output_format)

            if result.success:
                logger.info("Successfully fixed PlantUML diagram %s", puml_path.name)
                return result

        except Exception as e:
            logger.warning("Failed to fix PlantUML with Claude: %s", e)
            # Continue to next retry or return failure

    logger.warning(
        "Failed to fix PlantUML diagram %s after %d attempts",
        puml_path.name,
        max_retries,
    )
    return result
