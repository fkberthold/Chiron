# Continuation Prompt: Add TTS Audio Generation

## Context

The lesson output pipeline is now generating all artifacts except audio:
- ✓ script.txt (working)
- ✓ lesson.md (working)
- ✓ lesson.pdf (working with weasyprint)
- ✓ diagrams/ (PlantUML rendering working)
- ✓ exercises.json (working)
- ✓ SRS items (working)
- ○ audio.mp3 (TTS not available)

## Goal

Generate audio from script.txt using text-to-speech.

## Current State

- `src/chiron/content/audio.py` exists with stub functions
- `check_available_tools()` in pipeline.py checks for "coqui" and "piper" TTS libraries
- `LessonArtifacts.audio_path` is always `None` (hardcoded)
- pyproject.toml has optional TTS dependencies: `tts = ["TTS>=0.22.0"]`

## Implementation Tasks

### 1. Choose TTS Engine

Options to evaluate:
- **Coqui TTS** (`TTS` package) - High quality but large (~1.5GB models)
- **piper-tts** - Lightweight, fast, offline
- **edge-tts** - Microsoft Edge voices, free, no local models
- **gTTS** - Google TTS, simple but requires internet

Recommendation: Start with **edge-tts** - it's simple, free, high quality, and doesn't require downloading large models.

### 2. Add edge-tts to Dependencies

```bash
uv add edge-tts --optional tts
```

Or add to pyproject.toml under `[project.optional-dependencies]`.

### 3. Implement Audio Generation

In `src/chiron/content/audio.py`:
- Read script.txt content
- Call edge-tts to generate MP3
- Save to output directory as audio.mp3

### 4. Integrate into Pipeline

In `src/chiron/content/pipeline.py`:
- Check if edge-tts is available (add to `check_available_tools()`)
- After writing script.txt, generate audio if TTS available
- Update `LessonArtifacts.audio_path` with actual path

### 5. Update CLI Display

The CLI already handles audio_path correctly - just needs the pipeline to return a real path.

## Files to Modify

1. `pyproject.toml` - Add edge-tts dependency
2. `src/chiron/content/audio.py` - Implement TTS generation
3. `src/chiron/content/pipeline.py` - Integrate audio generation, update check_available_tools
4. `tests/test_audio.py` - Update tests
5. `tests/test_pipeline.py` - Add audio generation test

## Quick Test

```bash
# Install edge-tts
uv add edge-tts --optional tts

# Test it works
uv run python -c "import edge_tts; print('edge-tts available')"

# Test audio generation
uv run python -c "
import asyncio
import edge_tts

async def test():
    communicate = edge_tts.Communicate('Hello world', 'en-US-AriaNeural')
    await communicate.save('/tmp/test.mp3')
    print('Audio saved to /tmp/test.mp3')

asyncio.run(test())
"
```

## Notes

- edge-tts is async, so audio generation will need `asyncio.run()` wrapper
- Consider voice selection - 'en-US-AriaNeural' is a good default
- Script may need chunking for very long lessons (edge-tts handles this internally)
- Audio generation takes time (~30-60 seconds for a 15-minute script)
