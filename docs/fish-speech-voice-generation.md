# Fish Speech Voice Generation

This document captures learnings from a week of experimentation with Fish Speech TTS integration for the Chiron project.

## Overview

Fish Speech is a local TTS engine with voice cloning capabilities. While powerful, it has server instability issues that require careful management. The key innovation discovered is the **synthetic anchor** approach for consistent voice cloning.

## The Anchor System

### Problem with Direct Voice Cloning

Direct voice cloning from variable-quality reference audio produces inconsistent results. Short references don't provide enough voice data, and quality varies with recording conditions.

### Solution: Synthetic Anchors

Generate a **synthetic anchor** by having Fish Speech produce a standardized text using the reference voice with a specific seed. This anchor then becomes the voice source for all subsequent generation.

### Anchor Generation Process

1. **Original Voice Source**: `~/.chiron/voices/default/reference.wav` (~9.9 seconds)

2. **Anchor Text**: A neutral, varied text that exercises different phonemes:
   > "Hello, and welcome. Have you ever wondered how things really work beneath the surface? It's a fascinating question, one worth measuring carefully. Let's take a closer look together. Pay attention to the details, because they often reveal something surprising. The journey itself can be just as rewarding as the destination. That's the pleasure of discovery."

3. **Seed Sweep**: Generate anchors with 50 different seeds, then evaluate for voice quality and stability

4. **Selected Anchor**: Seed 41 was selected after comprehensive testing

### Why Anchors Work

- Normalizes voice characteristics into a consistent, high-quality sample
- Anchor is longer (~18 seconds) than typical reference, providing more voice data
- Standardized text ensures consistent phoneme coverage
- Fixed seed makes the anchor reproducible

## Optimal Generation Parameters

```python
# Generation parameters (from depth testing)
GENERATION_SEED = 42        # Fixed for reproducibility
max_new_tokens = 2048       # Sufficient for long outputs
chunk_length = 200          # Conservative for GPU safety
top_p = 0.9                 # Good variety while stable (tested at 1.0)
temperature = 0.8           # Balance of variety/stability
use_memory_cache = "on"     # Performance optimization
repetition_penalty = 1.1    # Prevent loops
```

## Server Management

Fish Speech server is unstable and crashes frequently. Required protocol:

```python
def generate_single_text(anchor_seed, test, ref_id):
    kill_fish_server()                    # Kill any existing
    _ensure_fish_server_running()         # Start fresh
    time.sleep(5)                         # Warmup delay
    register_reference(ref_id, anchor)    # Register anchor
    success = generate_audio(...)         # Generate
    kill_fish_server()                    # Clean kill
```

Key points:
- **Kill server before each generation** - Don't reuse server state
- **Fresh server per generation** - Complete restart cycle
- **5 second warmup** after server start before API calls
- **Kill server after generation** - Free VRAM

## Text Chunking Strategy

Long-form content must be segmented to avoid GPU OOM:

```python
MAX_CHARS_PER_CHUNK = 300   # Conservative limit
MIN_CHARS_PER_CHUNK = 50    # Combine tiny sentences
```

### Segmentation Rules

1. Split on sentence boundaries (`.!?`)
2. Preserve emotion markers in parentheses like `(excited)`
3. Combine short sentences under minimum threshold
4. Very long sentences: send as-is, fail fast if GPU chokes

### Example

```
Input: "Yes. I agree. This is important."
Output: ["Yes. I agree. This is important."]  # Combined (under threshold)

Input: "This is a longer sentence about the topic. Here is another one."
Output: ["This is a longer sentence about the topic.",
         "Here is another one."]  # Separate (each safe size)
```

## Output Validation

Validate generated audio duration against expected speech rate:

```python
MIN_SPEECH_RATE = 8   # chars/second (very slow speech)
MAX_SPEECH_RATE = 20  # chars/second (very fast speech)
```

Audio is flagged as invalid if duration falls outside the expected range based on input text length. This catches truncated outputs from server crashes.

## Voice Configuration

### File Structure

```
~/.chiron/voices/
└── default/
    ├── voice.yaml        # Configuration
    └── reference.wav     # Original voice recording
```

### voice.yaml Format

```yaml
# Voice configuration for Fish Speech TTS
references:
  - audio: "reference.wav"
    text: "Transcript of what's said in reference.wav..."

# Generation parameters
chunk_length: 200
top_p: 0.7
seed: 42
```

## Emotion Markers

Fish Speech responds to emotion markers embedded in text:

### Supported Markers

**Emotions** (38 tested):
- excited, surprised, satisfied, delighted, scared, worried, upset, nervous
- frustrated, embarrassed, moved, proud, relaxed, grateful, confident
- interested, curious, confused, joyful, anxious, impatient, guilty
- panicked, furious, reluctant, keen, astonished, serious, sarcastic
- comforting, sincere, hesitating, yielding, painful, awkward, amused, angry, disdainful

**Tones** (5 tested):
- `(soft tone)`, `(whispering)`, `(shouting)`, `(screaming)`, `(in a hurry tone)`

**Effects** (5 tested):
- `(sighing)`, `(panting)`, `(groaning)`, `(laughing)`, `(chuckling)`

### Usage Example

```
(soft tone) Hey, come here. (whispering) I want to tell you something.
(excited) Oh my god, did you see that? (laughing) That was amazing!
```

## Architecture Flow

```
reference.wav (original recording)
    |
    v [Fish Speech + seed 41]
anchor_seed_41.wav (synthetic anchor)
    |
    v [registered as reference_id]
Production Generation
    |
    v [uses anchor for voice cloning]
output.wav (consistent voice output)
```

## Anchor Selection Methodology

### Evaluation Process

1. **Sweep**: Generate 50 anchors with seeds 1-50
2. **Initial Filter**: Select 7 candidates based on voice quality: seeds 1, 20, 22, 26, 28, 41, 46
3. **Stability Test**: Generate multiple samples per anchor to test consistency
4. **Depth Test**: Generate 32 diverse emotional/tonal texts per anchor (224 total files)
5. **Selection**: Choose anchor with best stability, emotion responsiveness, and character authenticity

### Test Suite Coverage

32 test texts covering:
- Core voice characteristics
- Emotional range (nervous, calm, excited, frustrated, etc.)
- Tones (whispering, shouting, soft)
- Effects (panting, sighing, laughing)

## Production Recommendations

1. **Use the Seed 41 anchor** for voice generation
2. **Register anchor with full transcript** before each generation session
3. **Restart server per generation** (reliability over speed)
4. **Chunk at 300 chars max** for GPU safety
5. **Validate output duration** against expected speech rate
6. **Fixed generation seed (42)** for reproducible outputs

## Known Limitations

1. **Server instability** - Requires restart per generation (slow)
2. **No streaming** - Full generation completes before playback
3. **GPU memory** - Long inputs cause OOM crashes
4. **Warmup time** - 5+ seconds needed after server start

## File Locations

| File | Purpose |
|------|---------|
| `~/.chiron/voices/default/voice.yaml` | Voice configuration |
| `~/.chiron/voices/default/reference.wav` | Original voice recording |
| `/tmp/fish_reference_anchor_sweep/anchor_seed_41.wav` | Selected synthetic anchor |
| `src/chiron/content/audio.py` | TTS implementation |
| `src/chiron/content/pipeline.py` | Lesson generation pipeline |
