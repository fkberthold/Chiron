"""Tests for lesson content parser."""

from chiron.content.parser import DiagramSpec, ParsedLesson


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
