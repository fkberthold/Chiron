# Fish TTS Implementation Continuation

## Status

Basic infrastructure is in place:
- `VoiceConfig` model for voice cloning settings
- `load_voice_config()` for loading YAML configs from `~/.chiron/voices/`
- `segment_for_fish()` for GPU-safe sentence chunking (max 300 chars)
- `generate_audio_fish()` stub with segmentation setup
- Pipeline priority: Fish > Coqui > Piper > export

## Remaining Work

1. **Investigate Fish Speech library API**
   ```bash
   # Install Fish Speech
   uv sync --extra fish

   # Test import and explore API
   uv run python -c "import fish_speech; print(dir(fish_speech))"
   ```
   - The PyPI package points to github.com/fishaudio/fish-speech
   - Check the library's Python API for inference
   - May differ from the web API used in ~/Working/fish_ttf/

2. **Implement `_generate_fish_chunk()`**
   - Load model once at start of `generate_audio_fish()`
   - For each segment from `segment_for_fish()`:
     - Generate audio
     - Call `torch.cuda.empty_cache()` after each chunk
     - Save to temp file
   - Handle errors with fail-fast (stop on first failure)

3. **Implement audio stitching**
   - Reuse existing `_stitch_wav_files()` function from Coqui implementation
   - Concatenate all segment wav files into final output

4. **Add voice cloning support**
   - Load reference audio from `voice_dir / voice_config.reference_audio`
   - Load reference text from `voice_config.reference_text`
   - Pass to Fish Speech inference API

5. **Integration test**
   - Test with actual Fish Speech on GPU
   - Verify GPU memory management works with sentence-level chunking
   - Confirm voice cloning works with reference files

## Voice Configuration

Voice configs live in `~/.chiron/voices/<name>/voice.yaml`:

```yaml
# Optional - omit for Fish's built-in voice
reference_audio: reference.wav
reference_text: "The transcript of what's said in reference.wav..."

# Fish Speech parameters
chunk_length: 396
top_p: 0.95
```

## Key Files

- `src/chiron/content/audio.py` - Main audio generation, Fish TTS functions
- `src/chiron/content/pipeline.py` - Pipeline with Fish detection and priority
- `tests/test_audio.py` - Audio generation tests
- `docs/plans/2026-01-01-fish-tts-design.md` - Original design document
