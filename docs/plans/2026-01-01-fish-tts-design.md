# Fish TTS Integration Design

## Overview

Integrate Fish Speech as the primary TTS engine for Chiron, handling GPU memory constraints through conservative sentence-level chunking.

### Key Constraints

- GPU crashes on inputs longer than ~1 sentence (OOM)
- Short sentences work reliably
- Voice cloning is optional (via reference audio + transcript)

### Architecture

```
~/.chiron/
└── voices/
    └── default/
        ├── voice.yaml        # Config: transcript, params
        └── reference.wav     # Reference audio file (optional)

Chiron Pipeline:
  Lesson content
    → extract_audio_script()
    → segment_for_fish()         # Smart sentence splitting
    → generate_audio_fish()      # Per-chunk with GPU cleanup
    → stitch_wav_files()
    → final audio.wav
```

### Engine Priority

Fish → Coqui → Piper → Export script

## Voice Configuration

### Location

`~/.chiron/voices/<voice-name>/`

### Structure

```
~/.chiron/voices/
├── default/                    # Optional custom voice
│   ├── voice.yaml
│   └── reference.wav
└── narrator/                   # Can have multiple voices
    ├── voice.yaml
    └── reference.wav
```

### voice.yaml Format

```yaml
# Reference for voice cloning (optional - omit entirely for Fish default voice)
reference_audio: reference.wav
reference_text: "The transcript of what's said in reference.wav..."

# Fish Speech parameters
chunk_length: 396
top_p: 0.95
```

### Behavior

- If `~/.chiron/voices/default/` exists with valid config → use it for cloning
- If no voice configured OR no reference_audio → use Fish's built-in default voice
- Engine auto-detects Fish availability, falls back to Coqui/Piper/export

## Sentence Segmentation

### Strategy

Smart hybrid - single sentences by default, combine very short ones.

### Algorithm

```python
def segment_for_fish(script: str, max_chars: int = 300) -> list[str]:
    """
    1. Split on sentence boundaries (.!?)
    2. For each sentence:
       - If current_chunk + sentence <= max_chars: append to chunk
       - Else: emit current_chunk, start new chunk
    3. Minimum chunk threshold (~50 chars) to combine tiny sentences
    """
```

### Examples

```
Input: "Yes. I agree. This is important."
Output: ["Yes. I agree. This is important."]  # Combined (under threshold)

Input: "This is a longer sentence about the topic. Here is another one."
Output: ["This is a longer sentence about the topic.",
         "Here is another one."]  # Separate (each safe size)
```

### Edge Cases

- Very long sentence (>300 chars): Send as-is, fail fast if GPU chokes
- Empty/whitespace: Skip
- No sentence boundaries: Treat whole text as one chunk

## Generation Flow

### Core Function

```python
def generate_audio_fish(
    script: str,
    output_path: Path,
    voice_dir: Path | None = None,  # ~/.chiron/voices/default/
) -> Path | None:
    """
    1. Load voice config from voice_dir (if provided)
    2. Initialize Fish model (GPU if available)
    3. Segment script with segment_for_fish()
    4. For each chunk:
       a. Generate audio (with reference voice if configured)
       b. torch.cuda.empty_cache()
       c. Save to temp file
    5. Stitch temp files → output_path
    6. Cleanup temps
    7. Return output_path or None on failure
    """
```

### Error Handling

- Any chunk fails → stop immediately, log which chunk, return None
- Partial audio files cleaned up on failure
- Caller (pipeline) falls back to next engine or exports script.txt

### GPU Memory Management

- `torch.cuda.empty_cache()` after each chunk
- No model reload between chunks (too slow)

## Voice Config Loading

### Pydantic Model

```python
class VoiceConfig(BaseModel):
    """Voice configuration for Fish TTS."""
    reference_audio: str | None = None  # Filename in voice dir
    reference_text: str | None = None   # Transcript of reference
    chunk_length: int = 396
    top_p: float = 0.95
```

### Loading Logic

```python
def load_voice_config(voice_name: str = "default") -> tuple[VoiceConfig, Path | None]:
    """
    1. Check ~/.chiron/voices/{voice_name}/voice.yaml
    2. If exists: parse YAML, return (config, voice_dir)
    3. If not: return (VoiceConfig(), None)  # defaults, no reference
    """
```

### Reference Audio Resolution

- `reference_audio` is relative to voice directory
- Full path: `~/.chiron/voices/default/reference.wav`
- If `reference_audio` is None → Fish uses its built-in voice

## Integration with Existing Code

### Changes to audio.py

1. Add `"fish"` to `AudioConfig.engine` literal type
2. Add Fish as first priority in `generate_audio()`
3. New `generate_audio_fish()` function
4. New `segment_for_fish()` function (separate from existing `segment_script()`)
5. New `VoiceConfig` model and `load_voice_config()` function

### Changes to pipeline.py

Update `check_tool_availability()` to detect Fish:

```python
def _check_fish_available() -> bool:
    try:
        import fish_speech
        return True
    except ImportError:
        return False
```

Engine priority in pipeline: Fish → Coqui → Piper → export

### New Dependencies

- `fish-speech` as optional dependency in `pyproject.toml`
- `pyyaml` for voice config parsing

## Summary

### Files Changed

| File | Changes |
|------|---------|
| `src/chiron/content/audio.py` | Add `generate_audio_fish()`, `segment_for_fish()`, `VoiceConfig`, `load_voice_config()` |
| `src/chiron/content/pipeline.py` | Add Fish detection, update engine priority |
| `pyproject.toml` | Add `fish-speech` and `pyyaml` dependencies |

### Not in Scope

- Per-subject voice selection
- CLI flags for TTS engine selection
- Progress display during generation
