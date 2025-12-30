"""Tests for audio generation."""

from pathlib import Path

from chiron.content.audio import (
    AudioConfig,
    extract_audio_script,
    generate_audio,
    segment_script,
)


def test_extract_audio_script() -> None:
    """Should extract audio script sections from lesson."""
    content = """
# Lesson

## Audio Script

[SECTION: Introduction]
Welcome to today's lesson.

[SECTION: Main Content]
Let's talk about pods.

## Exercises
...
"""
    script = extract_audio_script(content)
    assert "Welcome to today's lesson" in script
    assert "Let's talk about pods" in script


def test_segment_script() -> None:
    """Should segment script for TTS processing."""
    script = """[SECTION: Introduction]
This is a long section that needs to be processed.

[SECTION: Content]
More content here."""

    segments = segment_script(script, max_chars=100)
    assert len(segments) >= 1
    assert all(len(s) <= 100 for s in segments)


def test_audio_config_defaults() -> None:
    """AudioConfig should have sensible defaults."""
    config = AudioConfig()
    assert config.engine in ("coqui", "piper", "export")
    assert config.sample_rate == 22050
    assert config.voice_model == "default"


def test_generate_audio_export_mode(tmp_path: Path) -> None:
    """Should export script to text file in export mode."""
    script = "Welcome to today's lesson about Kubernetes."
    output_path = tmp_path / "lesson.mp3"

    result = generate_audio(script, output_path)

    assert result is not None
    assert result.suffix == ".txt"
    assert result.exists()
    assert result.read_text(encoding="utf-8") == script
