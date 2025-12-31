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


def test_parse_audio_script():
    """Test that audio script section is extracted."""
    content = """# Lesson: Test

## Learning Objectives
1. Learn stuff

## Audio Script

Welcome to today's lesson on Python.

We'll cover variables and types.

Let's get started with the basics.

## Visual Aids

### Diagram 1: Overview
"""
    parsed = parse_lesson_content(content)
    assert "Welcome to today's lesson" in parsed.audio_script
    assert "Let's get started" in parsed.audio_script
    # Should not include next section header
    assert "## Visual Aids" not in parsed.audio_script
    assert "### Diagram" not in parsed.audio_script


def test_parse_audio_script_strips_whitespace():
    """Test that audio script has leading/trailing whitespace stripped."""
    content = """# Lesson: Test

## Learning Objectives
1. Learn

## Audio Script


   Hello there.


## Visual Aids
"""
    parsed = parse_lesson_content(content)
    assert parsed.audio_script == "Hello there."


def test_parse_diagrams():
    """Test that PlantUML diagrams are extracted with titles and captions."""
    content = """# Lesson: Test

## Learning Objectives
1. Learn

## Audio Script

Content here.

## Visual Aids

### Diagram 1: Class Hierarchy

```plantuml
@startuml
class Animal
class Dog extends Animal
@enduml
```

This diagram shows the class hierarchy.

### Diagram 2: Sequence Flow

```plantuml
@startuml
A -> B: message
B -> C: response
@enduml
```

Shows the message flow between components.

## Exercise Seeds
"""
    parsed = parse_lesson_content(content)
    assert len(parsed.diagrams) == 2

    assert parsed.diagrams[0].title == "Class Hierarchy"
    assert "@startuml" in parsed.diagrams[0].puml_code
    assert "class Animal" in parsed.diagrams[0].puml_code
    assert "class hierarchy" in parsed.diagrams[0].caption.lower()

    assert parsed.diagrams[1].title == "Sequence Flow"
    assert "A -> B" in parsed.diagrams[1].puml_code
    assert "message flow" in parsed.diagrams[1].caption.lower()


def test_parse_diagrams_empty_when_no_visual_aids():
    """Test that diagrams list is empty when section missing."""
    content = """# Lesson: Test

## Learning Objectives
1. Learn

## Audio Script

Content.

## Exercise Seeds
"""
    parsed = parse_lesson_content(content)
    assert parsed.diagrams == []


def test_parse_diagram_no_caption_before_next_section():
    """Test diagram with no caption text immediately before next section header.

    Regression test: The regex should not capture the section header as caption.
    """
    content = """# Lesson: Test

## Learning Objectives
1. Learn

## Audio Script

Content here.

## Visual Aids

### Diagram 1: Simple Diagram

```plantuml
@startuml
A -> B
@enduml
```

## Exercise Seeds

1. Some exercise
"""
    parsed = parse_lesson_content(content)
    assert len(parsed.diagrams) == 1
    assert parsed.diagrams[0].title == "Simple Diagram"
    assert "A -> B" in parsed.diagrams[0].puml_code
    # The caption should be empty, NOT contain the next section header
    assert parsed.diagrams[0].caption == ""
    assert "Exercise Seeds" not in parsed.diagrams[0].caption
    assert "##" not in parsed.diagrams[0].caption
