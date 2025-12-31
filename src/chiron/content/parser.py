"""Parser for LessonAgent structured output."""

from dataclasses import dataclass


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
    exercise_seeds: list[dict]
    srs_items: list[tuple[str, str]]
