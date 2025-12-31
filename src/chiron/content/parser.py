"""Parser for LessonAgent structured output."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DiagramSpec:
    """Specification for a PlantUML diagram."""

    title: str
    puml_code: str
    caption: str


@dataclass
class ParsedLesson:
    """Parsed lesson content with all sections extracted."""

    title: str
    objectives: list[str]
    audio_script: str
    diagrams: list[DiagramSpec]
    exercise_seeds: list[dict[str, Any]]
    srs_items: list[tuple[str, str]]


def parse_lesson_content(content: str) -> ParsedLesson:
    """Parse structured lesson content into sections.

    Args:
        content: Raw markdown output from LessonAgent

    Returns:
        ParsedLesson with extracted sections
    """
    # Extract title from "# Lesson: Title" header
    title_match = re.search(r"^# Lesson:\s*(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Untitled Lesson"

    # Extract objectives from numbered list under ## Learning Objectives
    objectives: list[str] = []
    objectives_match = re.search(
        r"## Learning Objectives\s*\n((?:\d+\.\s+.+\n?)+)",
        content,
        re.MULTILINE,
    )
    if objectives_match:
        objectives_text = objectives_match.group(1)
        objectives = [
            re.sub(r"^\d+\.\s+", "", line.strip())
            for line in objectives_text.strip().split("\n")
            if line.strip()
        ]

    # Extract audio script - everything between ## Audio Script and next ## header
    audio_script = ""
    audio_match = re.search(
        r"## Audio Script\s*\n(.*?)(?=\n## |\Z)",
        content,
        re.DOTALL,
    )
    if audio_match:
        audio_script = audio_match.group(1).strip()

    # Extract diagrams from Visual Aids section
    diagrams: list[DiagramSpec] = []
    # Pattern: ### Diagram N: Title, then plantuml block, then caption paragraph
    diagram_pattern = re.compile(
        r"### Diagram \d+:\s*(.+?)\n\s*"  # Title
        r"```plantuml\s*\n(.*?)```\s*\n"  # PlantUML code
        r"(.*?)(?=\n\s*### Diagram|\n\s*## |\Z)",  # Caption (until next diagram or section)
        re.DOTALL,
    )
    for match in diagram_pattern.finditer(content):
        caption_text = match.group(3).strip()
        # Post-process: ensure section headers aren't captured as caption
        # (handles edge cases where regex lookahead didn't catch it)
        if caption_text.startswith("## ") or caption_text.startswith("### "):
            caption_text = ""
        diagrams.append(
            DiagramSpec(
                title=match.group(1).strip(),
                puml_code=match.group(2).strip(),
                caption=caption_text,
            )
        )

    # Extract exercise seeds from JSON code block
    exercise_seeds: list[dict[str, Any]] = []
    exercises_match = re.search(
        r"## Exercise Seeds\s*\n\s*```json\s*\n(.*?)```",
        content,
        re.DOTALL,
    )
    if exercises_match:
        try:
            exercise_seeds = json.loads(exercises_match.group(1).strip())
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse exercise seeds JSON: %s", e)
            exercise_seeds = []

    # Extract SRS items from "- front | back" format
    srs_items: list[tuple[str, str]] = []
    srs_match = re.search(
        r"## SRS Items\s*\n((?:- .+\n?)+)",
        content,
        re.MULTILINE,
    )
    if srs_match:
        srs_text = srs_match.group(1)
        for line in srs_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("- ") and "|" in line:
                parts = line[2:].split("|", 1)  # Remove "- " prefix, split on first |
                if len(parts) == 2:
                    srs_items.append((parts[0].strip(), parts[1].strip()))

    return ParsedLesson(
        title=title,
        objectives=objectives,
        audio_script=audio_script,
        diagrams=diagrams,
        exercise_seeds=exercise_seeds,
        srs_items=srs_items,
    )
