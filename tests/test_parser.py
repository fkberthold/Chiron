"""Tests for lesson content parser."""

from chiron.content.parser import DiagramSpec, ParsedLesson, parse_lesson_content


def test_parsed_lesson_dataclass():
    """Test that ParsedLesson can be instantiated."""
    lesson = ParsedLesson(
        title="Test Lesson",
        objectives=["Learn X", "Understand Y"],
        audio_script="Hello, welcome to the lesson.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )
    assert lesson.title == "Test Lesson"
    assert len(lesson.objectives) == 2
    assert lesson.audio_script == "Hello, welcome to the lesson."


def test_diagram_spec_dataclass():
    """Test that DiagramSpec can be instantiated."""
    diagram = DiagramSpec(
        title="Test Diagram",
        puml_code="@startuml\nA -> B\n@enduml",
        caption="A simple diagram",
    )
    assert diagram.title == "Test Diagram"
    assert "@startuml" in diagram.puml_code


def test_parse_title():
    """Test that title is extracted from lesson header."""
    content = """# Lesson: Introduction to Python

## Learning Objectives
1. Understand variables
2. Learn basic syntax

## Audio Script

Welcome to the lesson.
"""
    parsed = parse_lesson_content(content)
    assert parsed.title == "Introduction to Python"


def test_parse_objectives():
    """Test that objectives are extracted as list."""
    content = """# Lesson: Test

## Learning Objectives
1. First objective
2. Second objective
3. Third objective

## Audio Script

Content here.
"""
    parsed = parse_lesson_content(content)
    assert len(parsed.objectives) == 3
    assert parsed.objectives[0] == "First objective"
    assert parsed.objectives[2] == "Third objective"
