"""Audio generation for Chiron lessons."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class AudioConfig:
    """Configuration for audio generation."""

    engine: Literal["coqui", "piper", "export"] = "export"
    sample_rate: int = 22050
    voice_model: str = "default"


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
    under max_chars per segment.

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
        # Just save the script for external TTS
        script_path = output_path.with_suffix(".txt")
        script_path.write_text(script, encoding="utf-8")
        return script_path

    # TODO: Implement Coqui TTS
    # TODO: Implement Piper TTS

    return None
