"""Tests for audio generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from chiron.content.audio import (
    AudioConfig,
    extract_audio_script,
    generate_audio,
    generate_audio_coqui,
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
    assert config.voice_model == "tts_models/en/ljspeech/tacotron2-DDC"


def test_generate_audio_export_mode(tmp_path: Path) -> None:
    """Should export script to text file in export mode."""
    script = "Welcome to today's lesson about Kubernetes."
    output_path = tmp_path / "lesson.mp3"

    result = generate_audio(script, output_path)

    assert result is not None
    assert result.suffix == ".txt"
    assert result.exists()
    assert result.read_text(encoding="utf-8") == script


def test_generate_audio_coqui_not_installed(tmp_path: Path) -> None:
    """Should return None when Coqui TTS is not installed."""
    script = "Test audio content."
    output_path = tmp_path / "audio.wav"
    config = AudioConfig(engine="coqui")

    # Simulate TTS not being installed
    with patch.dict("sys.modules", {"TTS": None, "TTS.api": None}):
        result = generate_audio_coqui(script, output_path, config)

    assert result is None


def test_generate_audio_coqui_success(tmp_path: Path) -> None:
    """Should generate audio when Coqui TTS is available."""
    script = "Short test script."
    output_path = tmp_path / "audio.wav"
    config = AudioConfig(engine="coqui")

    # Mock the TTS module and class
    mock_tts_instance = MagicMock()
    mock_tts_class = MagicMock(return_value=mock_tts_instance)

    with patch.dict("sys.modules", {"TTS": MagicMock(), "TTS.api": MagicMock()}):
        with patch("chiron.content.audio.TTS", mock_tts_class, create=True):
            # Patch the import inside generate_audio_coqui
            import sys

            mock_tts_module = MagicMock()
            mock_tts_module.TTS = mock_tts_class
            sys.modules["TTS.api"] = mock_tts_module

            result = generate_audio_coqui(script, output_path, config)

            # TTS was initialized with model name
            mock_tts_class.assert_called_once_with(
                model_name=config.voice_model, progress_bar=False
            )
            # tts_to_file was called with the script
            mock_tts_instance.tts_to_file.assert_called_once()

    # Result should be the wav path
    assert result is not None
    assert result.suffix == ".wav"


def test_generate_audio_selects_coqui_engine(tmp_path: Path) -> None:
    """Should use coqui engine when explicitly configured."""
    script = "Test content."
    output_path = tmp_path / "audio"
    config = AudioConfig(engine="coqui")

    # Mock to simulate TTS not installed (returns None)
    with patch("chiron.content.audio.generate_audio_coqui", return_value=None):
        result = generate_audio(script, output_path, config)

    assert result is None  # Falls through when coqui not available
