"""Tests for audio generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chiron.content.audio import (
    AudioConfig,
    VoiceConfig,
    extract_audio_script,
    generate_audio,
    generate_audio_coqui,
    generate_audio_fish,
    load_voice_config,
    segment_for_fish,
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
    assert config.engine in ("fish", "coqui", "piper", "export")
    assert config.sample_rate == 22050
    assert config.voice_model == "tts_models/en/ljspeech/tacotron2-DDC"


def test_voice_config_defaults() -> None:
    """VoiceConfig should have sensible defaults for Fish TTS."""
    config = VoiceConfig()
    assert config.reference_audio is None
    assert config.reference_text is None
    assert config.chunk_length == 396
    assert config.top_p == 0.95


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


def test_load_voice_config_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Should return default config when voice directory doesn't exist."""
    monkeypatch.setenv("HOME", str(tmp_path))

    config, voice_dir = load_voice_config("default")

    assert config.reference_audio is None
    assert config.chunk_length == 396
    assert voice_dir is None


def test_load_voice_config_with_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Should load voice config from YAML file."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # Create voice config directory and file
    voice_dir = tmp_path / ".chiron" / "voices" / "default"
    voice_dir.mkdir(parents=True)

    config_file = voice_dir / "voice.yaml"
    config_file.write_text("""
reference_audio: reference.wav
reference_text: "Hello, this is a test."
chunk_length: 200
top_p: 0.9
""")

    config, returned_dir = load_voice_config("default")

    assert config.reference_audio == "reference.wav"
    assert config.reference_text == "Hello, this is a test."
    assert config.chunk_length == 200
    assert config.top_p == 0.9
    assert returned_dir == voice_dir


# --- segment_for_fish tests ---


def test_segment_for_fish_combines_short_sentences() -> None:
    """Should combine short sentences under threshold."""
    script = "Yes. I agree. This is important."

    segments = segment_for_fish(script, max_chars=300, min_chars=50)

    assert len(segments) == 1
    assert segments[0] == "Yes. I agree. This is important."


def test_segment_for_fish_splits_long_sentences() -> None:
    """Should keep sentences separate when they exceed threshold."""
    script = (
        "This is a longer sentence about the topic. "
        "Here is another one that is also quite long."
    )

    segments = segment_for_fish(script, max_chars=50, min_chars=10)

    assert len(segments) == 2
    assert "This is a longer sentence" in segments[0]
    assert "Here is another one" in segments[1]


def test_segment_for_fish_handles_empty() -> None:
    """Should return empty list for empty input."""
    segments = segment_for_fish("")
    assert segments == []


def test_segment_for_fish_handles_no_punctuation() -> None:
    """Should treat text without sentence boundaries as one chunk."""
    script = "This is text without any sentence ending punctuation"

    segments = segment_for_fish(script)

    assert len(segments) == 1
    assert segments[0] == script


def test_audio_config_fish_engine() -> None:
    """AudioConfig should accept fish as engine."""
    config = AudioConfig(engine="fish")
    assert config.engine == "fish"


def test_generate_audio_fish_not_installed(tmp_path: Path) -> None:
    """Should return None when Fish Speech is not installed."""
    script = "Test audio content."
    output_path = tmp_path / "audio.wav"

    with patch.dict("sys.modules", {"fish_speech": None}):
        result = generate_audio_fish(script, output_path)

    assert result is None
