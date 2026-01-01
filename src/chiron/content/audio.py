"""Audio generation for Chiron lessons.

Audio rendering priority (per design doc):
1. Coqui TTS with GPU acceleration (high quality)
2. Piper TTS (fallback, faster but more robotic)
3. Export script for external TTS like Speechify (last resort)
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:
    pass  # TTS types would go here if we had stubs

logger = logging.getLogger(__name__)


class VoiceConfig(BaseModel):
    """Voice configuration for Fish TTS."""

    reference_audio: str | None = None
    reference_text: str | None = None
    chunk_length: int = 396
    top_p: float = 0.95


def load_voice_config(voice_name: str = "default") -> tuple[VoiceConfig, Path | None]:
    """Load voice configuration from ~/.chiron/voices/{voice_name}/.

    Args:
        voice_name: Name of the voice directory to load.

    Returns:
        Tuple of (VoiceConfig, voice_dir_path or None if not found).
    """
    voice_dir = Path.home() / ".chiron" / "voices" / voice_name
    config_path = voice_dir / "voice.yaml"

    if not config_path.exists():
        return VoiceConfig(), None

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return VoiceConfig(**data), voice_dir


@dataclass
class AudioConfig:
    """Configuration for audio generation."""

    engine: Literal["coqui", "piper", "export"] = "export"
    sample_rate: int = 22050
    voice_model: str = "tts_models/en/ljspeech/tacotron2-DDC"  # Default Coqui model


def extract_audio_script(content: str) -> str:
    """Extract the audio script portion from lesson content.

    Args:
        content: Full lesson markdown content

    Returns:
        Extracted audio script text
    """
    # Look for ## Audio Script section
    pattern = r"## Audio Script\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()

    # Fallback: look for [SECTION: ...] markers anywhere
    section_pattern = r"\[SECTION:.*?\](.*?)(?=\[SECTION:|\Z)"
    matches = re.findall(section_pattern, content, re.DOTALL)

    if matches:
        return "\n\n".join(m.strip() for m in matches)

    return content


def segment_script(script: str, max_chars: int = 5000) -> list[str]:
    """Segment script for TTS processing.

    Splits on section boundaries or sentence boundaries to stay
    under max_chars per segment. This is important for GPU memory
    management when using Coqui TTS.

    Args:
        script: Full audio script
        max_chars: Maximum characters per segment

    Returns:
        List of script segments
    """
    segments = []
    current = ""

    # Split by section markers first
    parts = re.split(r"\[SECTION:.*?\]\s*", script)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if len(current) + len(part) + 2 <= max_chars:
            current = f"{current}\n\n{part}".strip()
        else:
            if current:
                segments.append(current)

            # If single part is too long, split by sentences
            if len(part) > max_chars:
                sentences = re.split(r"(?<=[.!?])\s+", part)
                current = ""
                for sentence in sentences:
                    if len(current) + len(sentence) + 1 <= max_chars:
                        current = f"{current} {sentence}".strip()
                    else:
                        if current:
                            segments.append(current)
                        current = sentence
            else:
                current = part

    if current:
        segments.append(current)

    return segments


def generate_audio(
    script: str,
    output_path: Path,
    config: AudioConfig | None = None,
) -> Path | None:
    """Generate audio from script.

    Args:
        script: Text to convert to speech
        output_path: Where to save the audio file
        config: Audio generation configuration

    Returns:
        Path to generated audio, or None if generation not available
    """
    config = config or AudioConfig()

    if config.engine == "export":
        # Just save the script for external TTS (e.g., Speechify)
        script_path = output_path.with_suffix(".txt")
        script_path.write_text(script, encoding="utf-8")
        return script_path

    if config.engine == "coqui":
        return generate_audio_coqui(script, output_path, config)

    if config.engine == "piper":
        return generate_audio_piper(script, output_path, config)

    return None


def generate_audio_coqui(
    script: str,
    output_path: Path,
    config: AudioConfig,
) -> Path | None:
    """Generate audio using Coqui TTS.

    Coqui TTS provides high-quality neural TTS with GPU acceleration.
    For long scripts, we segment the text and stitch the audio together.

    Args:
        script: Text to convert to speech
        output_path: Where to save the audio file
        config: Audio configuration

    Returns:
        Path to generated WAV file, or None if generation failed
    """
    try:
        from TTS.api import TTS  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Coqui TTS not installed. Install with: uv sync --extra tts")
        return None

    output_path = output_path.with_suffix(".wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Initialize TTS with the specified model
        tts = TTS(model_name=config.voice_model, progress_bar=False)

        # Segment script for GPU memory management
        segments = segment_script(script)

        if len(segments) == 1:
            # Single segment - generate directly
            tts.tts_to_file(text=script, file_path=str(output_path))
        else:
            # Multiple segments - generate and stitch
            _generate_and_stitch_segments(tts, segments, output_path, config)

        return output_path

    except Exception as e:
        logger.error("Coqui TTS generation failed: %s", e)
        return None


def _generate_and_stitch_segments(
    tts: Any,  # TTS instance from Coqui TTS
    segments: list[str],
    output_path: Path,
    config: AudioConfig,
) -> None:
    """Generate audio for each segment and stitch them together.

    Args:
        tts: Initialized TTS instance
        segments: List of text segments
        output_path: Final output path
        config: Audio configuration
    """
    import tempfile

    temp_files: list[Path] = []

    try:
        # Generate each segment
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            for i, segment in enumerate(segments):
                segment_path = temp_path / f"segment_{i:03d}.wav"
                tts.tts_to_file(text=segment, file_path=str(segment_path))
                temp_files.append(segment_path)

            # Stitch segments together
            _stitch_wav_files(temp_files, output_path)

    except Exception as e:
        logger.error("Failed to generate/stitch segments: %s", e)
        raise


def _stitch_wav_files(input_files: list[Path], output_path: Path) -> None:
    """Concatenate multiple WAV files into one.

    Args:
        input_files: List of WAV file paths to concatenate
        output_path: Output WAV file path
    """
    import wave

    if not input_files:
        return

    # Read parameters from first file
    with wave.open(str(input_files[0]), "rb") as first_wav:
        params = first_wav.getparams()

    # Write combined audio
    with wave.open(str(output_path), "wb") as output_wav:
        output_wav.setparams(params)

        for wav_path in input_files:
            with wave.open(str(wav_path), "rb") as input_wav:
                output_wav.writeframes(input_wav.readframes(input_wav.getnframes()))


def generate_audio_piper(
    script: str,
    output_path: Path,
    config: AudioConfig,
) -> Path | None:
    """Generate audio using Piper TTS.

    Piper is a fast, lightweight TTS system. It's more robotic than Coqui
    but runs well on CPU without GPU requirements.

    Args:
        script: Text to convert to speech
        output_path: Where to save the audio file
        config: Audio configuration

    Returns:
        Path to generated WAV file, or None if generation failed
    """
    try:
        import piper  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Piper TTS not installed. Install with: uv sync --extra piper")
        return None

    output_path = output_path.with_suffix(".wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Piper uses a different API - synthesize to file
        # Note: Actual piper-tts API may differ, this is a placeholder
        voice = piper.PiperVoice.load(config.voice_model)
        audio = voice.synthesize(script)

        with open(output_path, "wb") as f:
            f.write(audio)

        return output_path

    except Exception as e:
        logger.error("Piper TTS generation failed: %s", e)
        return None
