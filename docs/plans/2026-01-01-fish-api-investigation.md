# Fish Speech API Investigation

## Context

We've implemented Fish TTS infrastructure but need to complete the actual audio generation. The `generate_audio_fish()` function has segmentation and setup ready, but returns `None` because we haven't implemented the Fish Speech library API calls yet.

## Your Task

Investigate the Fish Speech Python API and implement the actual audio generation in `generate_audio_fish()`.

## Current State

**What's done:**
- `VoiceConfig` model with `reference_audio`, `reference_text`, `chunk_length`, `top_p`
- `load_voice_config()` loads YAML from `~/.chiron/voices/{name}/voice.yaml`
- `segment_for_fish()` splits text into GPU-safe chunks (max 300 chars)
- `generate_audio_fish()` stub sets up output path and segments, returns `None`
- Pipeline detects Fish and prioritizes it over Coqui/Piper

**Key file:** `src/chiron/content/audio.py` - the `generate_audio_fish()` function starting around line 350

## Investigation Steps

1. **Explore the Fish Speech API:**
   ```bash
   uv sync --extra fish
   uv run python -c "import fish_speech; print(dir(fish_speech))"
   ```

2. **Check the Fish Speech repo for examples:**
   - Look at https://github.com/fishaudio/fish-speech
   - Find the inference/generation API
   - Note: The user has a working web API example in `~/Working/fish_ttf/generate_chunks.py` but we need the direct library API

3. **Implement audio generation:**
   - Load model once at function start
   - For each segment: generate audio, call `torch.cuda.empty_cache()`
   - Handle voice cloning if `voice_config.reference_audio` is set
   - Stitch segments using `_stitch_wav_files()` (already exists in audio.py)

4. **Test with actual GPU:**
   - Verify sentence-level chunking prevents OOM
   - Test voice cloning with reference files

## GPU Memory Constraints

The user's GPU crashes on inputs longer than ~1 sentence. The `segment_for_fish()` function already handles this by:
- Splitting on sentence boundaries (`.!?`)
- Max 300 chars per segment
- Combining very short sentences to reduce API calls

After each chunk, call `torch.cuda.empty_cache()` to reclaim VRAM.

## Voice Cloning

If `voice_config.reference_audio` is set:
- Reference wav is at `voice_dir / voice_config.reference_audio`
- Reference transcript is `voice_config.reference_text`
- Pass these to Fish Speech inference

If not set, use Fish's built-in default voice.

## Commands

```bash
# Install fish-speech
uv sync --extra fish

# Run tests
uv run pytest tests/test_audio.py -v

# Check linting
uv run ruff check src/ tests/
```
