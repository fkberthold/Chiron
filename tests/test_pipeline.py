"""Tests for lesson artifact pipeline."""

import json
from pathlib import Path
from unittest.mock import patch

from chiron.content.parser import DiagramSpec, ParsedLesson
from chiron.content.pipeline import (
    DiagramResult,
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
        diagrams=[],
        exercises_path=Path("/tmp/lesson/exercises.json"),
        srs_items_added=5,
    )
    assert artifacts.output_dir == Path("/tmp/lesson")
    assert artifacts.audio_path is None
    assert artifacts.srs_items_added == 5
    assert artifacts.diagrams_total == 0
    assert artifacts.diagrams_rendered == 0


def test_diagram_result_rendered_property(tmp_path):
    """Test that DiagramResult.rendered checks for file existence."""
    puml_path = tmp_path / "test.puml"
    puml_path.write_text("@startuml\n@enduml")
    png_path = tmp_path / "test.png"

    # Not rendered when PNG doesn't exist
    result = DiagramResult(
        puml_path=puml_path,
        png_path=png_path,
        title="Test",
        caption="Caption",
    )
    assert not result.rendered

    # Create the PNG file
    png_path.write_bytes(b"fake png")
    assert result.rendered

    # Not rendered when png_path is None
    result_none = DiagramResult(
        puml_path=puml_path,
        png_path=None,
        title="Test",
        caption="Caption",
    )
    assert not result_none.rendered


def test_check_available_tools_returns_dict():
    """Test that check_available_tools returns expected keys."""
    tools = check_available_tools()
    assert "fish" in tools
    assert "coqui" in tools
    assert "piper" in tools
    assert "plantuml" in tools
    assert "pandoc" in tools
    assert "weasyprint" in tools
    # All values should be booleans
    assert all(isinstance(v, bool) for v in tools.values())


def test_check_available_tools_detects_fish() -> None:
    """Should detect Fish Speech availability."""
    with patch("chiron.content.pipeline._try_import", return_value=True):
        tools = check_available_tools()

    assert "fish" in tools


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
    """Test that markdown includes diagram image references when rendered."""
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

    # Mock successful diagram rendering
    def mock_render(puml_path, fmt):
        png_path = puml_path.with_suffix(".png")
        png_path.write_bytes(b"fake png")
        return png_path

    with patch("chiron.content.pipeline.render_diagram", side_effect=mock_render):
        artifacts = generate_lesson_artifacts(parsed, tmp_path)

    md_content = artifacts.markdown_path.read_text()
    assert "![Flow Chart]" in md_content
    assert "diagrams/flow-chart.png" in md_content
    assert "Shows the flow" in md_content
    assert artifacts.diagrams_rendered == 1
    assert artifacts.diagrams_total == 1


def test_generate_lesson_artifacts_excludes_failed_diagrams_from_markdown(tmp_path):
    """Test that markdown excludes diagrams that failed to render."""
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

    # Mock failed diagram rendering
    with patch("chiron.content.pipeline.render_diagram", return_value=None):
        artifacts = generate_lesson_artifacts(parsed, tmp_path)

    md_content = artifacts.markdown_path.read_text()
    # Diagram should NOT be in markdown when rendering failed
    assert "![Flow Chart]" not in md_content
    assert "Visual Aids" not in md_content
    assert artifacts.diagrams_rendered == 0
    assert artifacts.diagrams_total == 1


def test_generate_lesson_artifacts_creates_pdf_when_pandoc_available(tmp_path):
    """Test that PDF is created when pandoc and weasyprint are available."""
    parsed = ParsedLesson(
        title="Test",
        objectives=["Learn"],
        audio_script="Content.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    # Mock pandoc and weasyprint being available and successful
    def which_mock(cmd):
        if cmd in ("pandoc", "weasyprint"):
            return f"/usr/bin/{cmd}"
        return None

    with patch("shutil.which", side_effect=which_mock):
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
        return_value={
            "pandoc": False,
            "weasyprint": False,
            "plantuml": False,
            "coqui": False,
            "piper": False,
        },
    ):
        artifacts = generate_lesson_artifacts(parsed, tmp_path)

    assert artifacts.pdf_path is None


def test_generate_lesson_artifacts_pdf_none_when_weasyprint_unavailable(tmp_path):
    """Test that PDF is None when pandoc available but weasyprint not available."""
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
        return_value={
            "pandoc": True,
            "weasyprint": False,
            "plantuml": False,
            "coqui": False,
            "piper": False,
        },
    ):
        artifacts = generate_lesson_artifacts(parsed, tmp_path)

    assert artifacts.pdf_path is None


def test_generate_lesson_artifacts_creates_audio_script_when_no_tts(tmp_path):
    """Test that audio script is exported when no TTS engine is available."""
    parsed = ParsedLesson(
        title="Test",
        objectives=["Learn"],
        audio_script="Welcome to the lesson.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    with patch(
        "chiron.content.pipeline.check_available_tools",
        return_value={
            "pandoc": False,
            "weasyprint": False,
            "plantuml": False,
            "coqui": False,
            "piper": False,
        },
    ):
        artifacts = generate_lesson_artifacts(parsed, tmp_path)

    # Should export script.txt for external TTS
    assert artifacts.audio_path is not None
    assert artifacts.audio_path.suffix == ".txt"
    assert artifacts.audio_path.exists()
    assert "Welcome to the lesson" in artifacts.audio_path.read_text()


def test_generate_lesson_artifacts_uses_coqui_when_available(tmp_path):
    """Test that Coqui TTS is used when available."""
    parsed = ParsedLesson(
        title="Test",
        objectives=["Learn"],
        audio_script="Hello world.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    mock_audio_path = tmp_path / "audio.wav"
    mock_audio_path.write_bytes(b"fake wav")

    with patch(
        "chiron.content.pipeline.check_available_tools",
        return_value={
            "pandoc": False,
            "weasyprint": False,
            "plantuml": False,
            "coqui": True,
            "piper": False,
        },
    ):
        with patch(
            "chiron.content.pipeline.generate_audio",
            return_value=mock_audio_path,
        ) as mock_generate:
            artifacts = generate_lesson_artifacts(parsed, tmp_path)

            # Should have called generate_audio with coqui engine
            call_args = mock_generate.call_args
            assert call_args is not None
            config = call_args[0][2]  # Third positional arg is config
            assert config.engine == "coqui"

    assert artifacts.audio_path == mock_audio_path
