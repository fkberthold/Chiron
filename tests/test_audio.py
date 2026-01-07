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
    """VoiceConfig should have sensible defaults for Fish TTS.

    Defaults are based on extensive testing - see docs/fish-speech-voice-generation.md
    """
    config = VoiceConfig()
    assert config.anchor is None  # No anchor by default
    assert config.reference_id is None  # Set after anchor registration
    # Optimal values from depth testing
    assert config.chunk_length == 200  # GPU-safe chunk size
    assert config.top_p == 0.9  # Good variety while stable
    assert config.seed == 42  # Reproducible prosody


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

    assert config.anchor is None
    assert config.reference_id is None
    assert config.chunk_length == 200  # Default from FISH_CHUNK_LENGTH
    assert voice_dir is None


def test_load_voice_config_with_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Should load voice config from YAML file."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # Create voice config directory and file
    voice_dir = tmp_path / ".chiron" / "voices" / "default"
    voice_dir.mkdir(parents=True)

    config_file = voice_dir / "voice.yaml"
    config_file.write_text("""
anchor:
  audio: anchor.wav
  text: "Hello, this is a test anchor."
  seed: 42
chunk_length: 200
top_p: 0.9
""")

    config, returned_dir = load_voice_config("default")

    assert config.anchor is not None
    assert config.anchor.audio == "anchor.wav"
    assert config.anchor.text == "Hello, this is a test anchor."
    assert config.anchor.seed == 42
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


def test_generate_audio_fish_api_connection_error(tmp_path: Path) -> None:
    """Should return None when Fish Speech API is not reachable."""
    script = "Test audio content."
    output_path = tmp_path / "audio.wav"

    # Mock requests to simulate connection error (fails even after retry)
    with patch("chiron.content.audio._ensure_fish_server_running", return_value=True):
        with patch("chiron.content.audio._restart_fish_server", return_value=True):
            with patch("chiron.content.audio._call_fish_api", return_value=False):
                result = generate_audio_fish(script, output_path)

    assert result is None


def test_generate_audio_fish_success(tmp_path: Path) -> None:
    """Should generate audio when Fish Speech API is available."""
    script = "This is a test sentence."
    output_path = tmp_path / "audio.wav"

    # Create a mock WAV file
    def mock_call_fish_api(
        text: str,
        output_path: Path,
        voice_config: VoiceConfig,
        api_url: str = "",
    ) -> bool:
        # Create a minimal valid WAV file
        import wave

        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(b"\x00\x00" * 1000)
        return True

    # Mock server management, anchor registration, and API call
    with patch("chiron.content.audio._ensure_fish_server_running", return_value=True):
        with patch("chiron.content.audio._prepare_voice_for_generation", return_value="test-anchor"):
            with patch("chiron.content.audio._call_fish_api", side_effect=mock_call_fish_api):
                result = generate_audio_fish(script, output_path)

    assert result is not None
    assert result.suffix == ".wav"
    assert result.exists()


def test_generate_audio_fish_multiple_segments(tmp_path: Path) -> None:
    """Should stitch multiple segments into one file."""
    # Script with multiple sentences that exceed segment limit (300 chars)
    # Need enough text to create multiple segments
    script = (
        "This is the first sentence that needs to be processed by the system. "
        "Here is a second sentence that also needs processing by the TTS engine. "
        "And finally a third sentence for good measure to ensure we test properly. "
    ) * 3  # ~600+ chars to ensure multiple segments
    output_path = tmp_path / "audio.wav"

    segment_count = 0

    def mock_call_fish_api(
        text: str,
        output_path: Path,
        voice_config: VoiceConfig,
        api_url: str = "",
    ) -> bool:
        nonlocal segment_count
        segment_count += 1
        import wave

        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(b"\x00\x00" * 500)
        return True

    # Mock server management, anchor registration, and API call
    with patch("chiron.content.audio._ensure_fish_server_running", return_value=True):
        with patch("chiron.content.audio._prepare_voice_for_generation", return_value="test-anchor"):
            with patch("chiron.content.audio._restart_fish_server", return_value=True):
                with patch("chiron.content.audio._call_fish_api", side_effect=mock_call_fish_api):
                    result = generate_audio_fish(script, output_path)

    assert result is not None
    assert result.exists()
    # Should have called the API multiple times for segments
    assert segment_count >= 2


def test_generate_audio_calls_fish(tmp_path: Path) -> None:
    """Should call generate_audio_fish when engine is fish."""
    script = "Test content."
    output_path = tmp_path / "audio"
    config = AudioConfig(engine="fish")

    with patch(
        "chiron.content.audio.generate_audio_fish", return_value=tmp_path / "audio.wav"
    ) as mock_fish:
        result = generate_audio(script, output_path, config)

    mock_fish.assert_called_once()
    assert result == tmp_path / "audio.wav"


def _create_wav_bytes(duration_seconds: float, sample_rate: int = 44100) -> bytes:
    """Helper to create WAV file bytes with specific duration."""
    import io
    import wave

    num_frames = int(duration_seconds * sample_rate)
    # Create simple audio data (silent)
    audio_data = b"\x00\x00" * num_frames

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio_data)

    return buffer.getvalue()


# --- Pause and stitching tests ---


def test_get_pause_for_segment_period() -> None:
    """Should return long pause for sentences ending with period."""
    from chiron.content.audio import PauseConfig, _get_pause_for_segment

    config = PauseConfig(period_ms=400, comma_ms=150)
    assert _get_pause_for_segment("This is a sentence.", config) == 400
    assert _get_pause_for_segment("Exclamation!", config) == 400
    assert _get_pause_for_segment("Question?", config) == 400


def test_get_pause_for_segment_comma() -> None:
    """Should return short pause for clauses ending with comma."""
    from chiron.content.audio import PauseConfig, _get_pause_for_segment

    config = PauseConfig(period_ms=400, comma_ms=150)
    assert _get_pause_for_segment("First clause,", config) == 150


def test_get_pause_for_segment_colon() -> None:
    """Should return medium pause for colon/semicolon."""
    from chiron.content.audio import PauseConfig, _get_pause_for_segment

    config = PauseConfig(colon_ms=300)
    assert _get_pause_for_segment("Here is a list:", config) == 300
    assert _get_pause_for_segment("First item;", config) == 300


def test_get_pause_for_segment_no_punctuation() -> None:
    """Should return default pause when no recognized punctuation."""
    from chiron.content.audio import PauseConfig, _get_pause_for_segment

    config = PauseConfig(default_ms=200)
    assert _get_pause_for_segment("No punctuation here", config) == 200
    assert _get_pause_for_segment("", config) == 200


def test_extract_noise_profile_returns_bytes() -> None:
    """Should extract noise profile from WAV data."""
    from chiron.content.audio import _extract_noise_profile

    wav_data = _create_wav_bytes(1.0)  # 1 second of audio
    noise = _extract_noise_profile(wav_data, sample_ms=50)

    assert isinstance(noise, bytes)
    assert len(noise) > 0


def test_create_noise_gap_fills_duration() -> None:
    """Should create gap of correct duration."""
    from chiron.content.audio import _create_noise_gap

    # Sample rate 44100, 1 channel, 2 bytes per sample
    noise_sample = b"\x01\x02" * 100  # Small noise sample
    gap = _create_noise_gap(
        noise_sample, gap_ms=100, sample_rate=44100, num_channels=1, sample_width=2
    )

    # 100ms at 44100 Hz = 4410 frames, 2 bytes each = 8820 bytes
    expected_bytes = int(44100 * 0.1) * 2
    assert len(gap) == expected_bytes


def test_stitch_wav_files_with_segment_texts(tmp_path: Path) -> None:
    """Should stitch files with punctuation-aware pauses."""
    import wave

    from chiron.content.audio import _stitch_wav_files

    # Create test WAV files
    files = []
    for i in range(3):
        wav_path = tmp_path / f"segment_{i}.wav"
        with wave.open(str(wav_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(b"\x00\x00" * 4410)  # 0.1 seconds
        files.append(wav_path)

    output_path = tmp_path / "output.wav"
    segments = ["First sentence.", "Second part,", "Final section."]

    _stitch_wav_files(files, output_path, segment_texts=segments)

    assert output_path.exists()
    with wave.open(str(output_path), "rb") as wav:
        # Original: 3 x 0.1s = 0.3s, plus pauses
        # After period: 400ms, after comma: 150ms
        # Total should be > 0.3s
        duration = wav.getnframes() / wav.getframerate()
        assert duration > 0.3


def test_add_noise_floor_modifies_audio(tmp_path: Path) -> None:
    """Should add noise to silent audio."""
    import struct
    import wave

    from chiron.content.audio import _add_noise_floor

    # Create silent WAV file
    wav_path = tmp_path / "silent.wav"
    num_samples = 4410  # 0.1 seconds at 44100 Hz
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x00\x00" * num_samples)

    # Add noise floor
    _add_noise_floor(wav_path, noise_level_db=-40.0)

    # Read back and verify audio is no longer silent
    with wave.open(str(wav_path), "rb") as wav:
        frames = wav.readframes(wav.getnframes())

    # At least some samples should be non-zero now
    samples = struct.unpack(f"<{num_samples}h", frames)
    non_zero = sum(1 for s in samples if s != 0)
    assert non_zero > num_samples * 0.9  # Most samples should have noise
