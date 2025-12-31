"""Tests for lesson artifact pipeline."""

import json
from pathlib import Path
from unittest.mock import patch

from chiron.content.parser import DiagramSpec, ParsedLesson
from chiron.content.pipeline import (
    LessonArtifacts,
    check_available_tools,
    generate_lesson_artifacts,
    slugify,
)


def test_lesson_artifacts_dataclass():
    """Test that LessonArtifacts can be instantiated."""
    artifacts = LessonArtifacts(
        output_dir=Path("/tmp/lesson"),
        script_path=Path("/tmp/lesson/script.txt"),
        audio_path=None,
        markdown_path=Path("/tmp/lesson/lesson.md"),
        pdf_path=None,
        diagram_paths=[],
        exercises_path=Path("/tmp/lesson/exercises.json"),
        srs_items_added=5,
    )
    assert artifacts.output_dir == Path("/tmp/lesson")
    assert artifacts.audio_path is None
    assert artifacts.srs_items_added == 5


def test_check_available_tools_returns_dict():
    """Test that check_available_tools returns expected keys."""
    tools = check_available_tools()
    assert "coqui" in tools
    assert "piper" in tools
    assert "plantuml" in tools
    assert "pandoc" in tools
    # All values should be booleans
    assert all(isinstance(v, bool) for v in tools.values())


def test_slugify_simple():
    """Test slugify with simple title."""
    assert slugify("Card Strength") == "card-strength"


def test_slugify_special_chars():
    """Test slugify removes special characters."""
    assert slugify("What's Next?") == "whats-next"
    assert slugify("Class/Type Hierarchy") == "classtype-hierarchy"


def test_slugify_multiple_spaces():
    """Test slugify handles multiple spaces."""
    assert slugify("Too   Many   Spaces") == "too-many-spaces"


def test_slugify_preserves_hyphens():
    """Test slugify preserves meaningful hyphens."""
    assert slugify("UTF-8 Encoding") == "utf-8-encoding"


def test_generate_lesson_artifacts_creates_directory(tmp_path):
    """Test that output directory is created."""
    parsed = ParsedLesson(
        title="Test Lesson",
        objectives=["Learn X"],
        audio_script="Hello world.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )
    output_dir = tmp_path / "lesson-2025-01-01"

    artifacts = generate_lesson_artifacts(parsed, output_dir)

    assert output_dir.exists()
    assert artifacts.output_dir == output_dir


def test_generate_lesson_artifacts_creates_script_txt(tmp_path):
    """Test that script.txt is created with audio script."""
    parsed = ParsedLesson(
        title="Test Lesson",
        objectives=["Learn X"],
        audio_script="Welcome to the lesson.\n\nThis is the content.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    artifacts = generate_lesson_artifacts(parsed, tmp_path)

    assert artifacts.script_path.exists()
    assert artifacts.script_path.name == "script.txt"
    content = artifacts.script_path.read_text()
    assert "Welcome to the lesson" in content


def test_generate_lesson_artifacts_creates_exercises_json(tmp_path):
    """Test that exercises.json is created."""
    seeds = [{"type": "scenario", "prompt": "What if?"}]
    parsed = ParsedLesson(
        title="Test Lesson",
        objectives=["Learn X"],
        audio_script="Content.",
        diagrams=[],
        exercise_seeds=seeds,
        srs_items=[],
    )

    artifacts = generate_lesson_artifacts(parsed, tmp_path)

    assert artifacts.exercises_path.exists()
    assert artifacts.exercises_path.name == "exercises.json"
    loaded = json.loads(artifacts.exercises_path.read_text())
    assert loaded == seeds


def test_generate_lesson_artifacts_creates_lesson_md(tmp_path):
    """Test that lesson.md is created with title and objectives."""
    parsed = ParsedLesson(
        title="My Test Lesson",
        objectives=["Understand concepts", "Apply knowledge"],
        audio_script="Content.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    artifacts = generate_lesson_artifacts(parsed, tmp_path)

    assert artifacts.markdown_path.exists()
    md_content = artifacts.markdown_path.read_text()
    assert "# My Test Lesson" in md_content
    assert "Understand concepts" in md_content
    assert "Apply knowledge" in md_content


def test_generate_lesson_artifacts_saves_diagrams(tmp_path):
    """Test that diagrams are saved as .puml files."""
    parsed = ParsedLesson(
        title="Test",
        objectives=["Learn"],
        audio_script="Content.",
        diagrams=[
            DiagramSpec(
                title="Class Diagram",
                puml_code="@startuml\nclass Foo\n@enduml",
                caption="Shows classes.",
            ),
        ],
        exercise_seeds=[],
        srs_items=[],
    )

    generate_lesson_artifacts(parsed, tmp_path)

    diagrams_dir = tmp_path / "diagrams"
    assert diagrams_dir.exists()
    puml_files = list(diagrams_dir.glob("*.puml"))
    assert len(puml_files) == 1
    assert "class-diagram.puml" in [f.name for f in puml_files]


def test_generate_lesson_artifacts_includes_diagrams_in_markdown(tmp_path):
    """Test that markdown includes diagram image references."""
    parsed = ParsedLesson(
        title="Test",
        objectives=["Learn"],
        audio_script="Content.",
        diagrams=[
            DiagramSpec(
                title="Flow Chart",
                puml_code="@startuml\nA -> B\n@enduml",
                caption="Shows the flow.",
            ),
        ],
        exercise_seeds=[],
        srs_items=[],
    )

    artifacts = generate_lesson_artifacts(parsed, tmp_path)

    md_content = artifacts.markdown_path.read_text()
    assert "![Flow Chart]" in md_content
    assert "diagrams/flow-chart.png" in md_content
    assert "Shows the flow" in md_content


def test_generate_lesson_artifacts_creates_pdf_when_pandoc_available(tmp_path):
    """Test that PDF is created when pandoc is available."""
    parsed = ParsedLesson(
        title="Test",
        objectives=["Learn"],
        audio_script="Content.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    # Mock pandoc being available and successful
    with patch("shutil.which", return_value="/usr/bin/pandoc"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            artifacts = generate_lesson_artifacts(parsed, tmp_path)

    # PDF path should be set (even though file won't exist in mock)
    assert artifacts.pdf_path == tmp_path / "lesson.pdf"


def test_generate_lesson_artifacts_pdf_none_when_pandoc_unavailable(tmp_path):
    """Test that PDF is None when pandoc not available."""
    parsed = ParsedLesson(
        title="Test",
        objectives=["Learn"],
        audio_script="Content.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    with patch(
        "chiron.content.pipeline.check_available_tools",
        return_value={"pandoc": False, "plantuml": False, "coqui": False, "piper": False},
    ):
        artifacts = generate_lesson_artifacts(parsed, tmp_path)

    assert artifacts.pdf_path is None
