# Fish TTS Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Fish Speech as the primary TTS engine with GPU-safe sentence-level chunking and optional voice cloning.

**Architecture:** Fish TTS generates audio one sentence at a time to avoid GPU OOM. Voice configs in `~/.chiron/voices/` enable optional voice cloning. The pipeline auto-detects Fish and uses it as first priority.

**Tech Stack:** Fish Speech, PyYAML, Pydantic, torch (for GPU cache management)

---

### Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml:30-35`

**Step 1: Add fish-speech and pyyaml to optional dependencies**

Edit `pyproject.toml` to add a new `fish` optional dependency group after the `piper` group:

```toml
fish = [
    "fish-speech>=1.4.0",
    "pyyaml>=6.0",
]
```

**Step 2: Verify dependency syntax**

Run: `uv sync --extra fish --dry-run`
Expected: Shows packages that would be installed (or error if syntax wrong)

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add fish-speech optional dependency"
```

---

### Task 2: VoiceConfig Pydantic Model

**Files:**
- Modify: `src/chiron/content/audio.py:21-28`
- Test: `tests/test_audio.py`

**Step 1: Write the failing test**

Add to `tests/test_audio.py`:

```python
from chiron.content.audio import VoiceConfig


def test_voice_config_defaults() -> None:
    """VoiceConfig should have sensible defaults for Fish TTS."""
    config = VoiceConfig()
    assert config.reference_audio is None
    assert config.reference_text is None
    assert config.chunk_length == 396
    assert config.top_p == 0.95
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio.py::test_voice_config_defaults -v`
Expected: FAIL with "cannot import name 'VoiceConfig'"

**Step 3: Write minimal implementation**

Add to `src/chiron/content/audio.py` after the imports, before `AudioConfig`:

```python
from pydantic import BaseModel


class VoiceConfig(BaseModel):
    """Voice configuration for Fish TTS."""

    reference_audio: str | None = None
    reference_text: str | None = None
    chunk_length: int = 396
    top_p: float = 0.95
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audio.py::test_voice_config_defaults -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/chiron/content/audio.py tests/test_audio.py
git commit -m "feat(audio): add VoiceConfig model for Fish TTS"
```

---

### Task 3: Load Voice Config from YAML

**Files:**
- Modify: `src/chiron/content/audio.py`
- Test: `tests/test_audio.py`

**Step 1: Write the failing test for loading config**

Add to `tests/test_audio.py`:

```python
from chiron.content.audio import load_voice_config


def test_load_voice_config_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Should return default config when voice directory doesn't exist."""
    monkeypatch.setenv("HOME", str(tmp_path))

    config, voice_dir = load_voice_config("default")

    assert config.reference_audio is None
    assert config.chunk_length == 396
    assert voice_dir is None
```

Also add `import pytest` at top if not present.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio.py::test_load_voice_config_not_found -v`
Expected: FAIL with "cannot import name 'load_voice_config'"

**Step 3: Write minimal implementation**

Add to `src/chiron/content/audio.py`:

```python
import yaml
from pathlib import Path as PathlibPath


def load_voice_config(voice_name: str = "default") -> tuple[VoiceConfig, PathlibPath | None]:
    """Load voice configuration from ~/.chiron/voices/{voice_name}/.

    Args:
        voice_name: Name of the voice directory to load.

    Returns:
        Tuple of (VoiceConfig, voice_dir_path or None if not found).
    """
    home = PathlibPath.home()
    voice_dir = home / ".chiron" / "voices" / voice_name
    config_path = voice_dir / "voice.yaml"

    if not config_path.exists():
        return VoiceConfig(), None

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return VoiceConfig(**data), voice_dir
```

Note: Also need to rename the `Path` import to avoid collision. Change line 13 from:
```python
from pathlib import Path
```
to:
```python
from pathlib import Path
from pathlib import Path as PathlibPath
```

Actually, simpler: just use `Path` throughout (it's already imported). Update the function:

```python
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
```

Add `import yaml` near top of file with other imports.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audio.py::test_load_voice_config_not_found -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/chiron/content/audio.py tests/test_audio.py
git commit -m "feat(audio): add load_voice_config for YAML voice configs"
```

---

### Task 4: Load Voice Config with Existing File

**Files:**
- Modify: `tests/test_audio.py`

**Step 1: Write the failing test for loading existing config**

Add to `tests/test_audio.py`:

```python
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
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_audio.py::test_load_voice_config_with_file -v`
Expected: PASS (implementation from Task 3 should handle this)

**Step 3: Commit**

```bash
git add tests/test_audio.py
git commit -m "test(audio): add test for loading voice config from YAML"
```

---

### Task 5: Sentence Segmentation for Fish

**Files:**
- Modify: `src/chiron/content/audio.py`
- Test: `tests/test_audio.py`

**Step 1: Write the failing test for sentence segmentation**

Add to `tests/test_audio.py`:

```python
from chiron.content.audio import segment_for_fish


def test_segment_for_fish_combines_short_sentences() -> None:
    """Should combine short sentences under threshold."""
    script = "Yes. I agree. This is important."

    segments = segment_for_fish(script, max_chars=300, min_chars=50)

    assert len(segments) == 1
    assert segments[0] == "Yes. I agree. This is important."


def test_segment_for_fish_splits_long_sentences() -> None:
    """Should keep sentences separate when they exceed threshold."""
    script = "This is a longer sentence about the topic. Here is another one that is also quite long."

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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio.py::test_segment_for_fish_combines_short_sentences -v`
Expected: FAIL with "cannot import name 'segment_for_fish'"

**Step 3: Write minimal implementation**

Add to `src/chiron/content/audio.py`:

```python
def segment_for_fish(
    script: str,
    max_chars: int = 300,
    min_chars: int = 50,
) -> list[str]:
    """Segment script for Fish TTS processing.

    Uses smart hybrid approach: splits on sentence boundaries but combines
    very short sentences to reduce API calls while staying GPU-safe.

    Args:
        script: Full audio script text.
        max_chars: Maximum characters per segment (GPU safety limit).
        min_chars: Minimum chars before emitting a segment (combine tiny sentences).

    Returns:
        List of text segments ready for TTS processing.
    """
    if not script or not script.strip():
        return []

    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", script.strip())

    segments: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Check if adding this sentence would exceed max
        if current and len(current) + len(sentence) + 1 > max_chars:
            # Emit current segment
            segments.append(current)
            current = sentence
        else:
            # Add to current segment
            current = f"{current} {sentence}".strip() if current else sentence

    # Emit final segment
    if current:
        segments.append(current)

    return segments
```

**Step 4: Run all segment_for_fish tests to verify they pass**

Run: `uv run pytest tests/test_audio.py -k segment_for_fish -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/chiron/content/audio.py tests/test_audio.py
git commit -m "feat(audio): add segment_for_fish for GPU-safe chunking"
```

---

### Task 6: Add Fish to AudioConfig Engine Type

**Files:**
- Modify: `src/chiron/content/audio.py:25`
- Test: `tests/test_audio.py`

**Step 1: Write the failing test**

Add to `tests/test_audio.py`:

```python
def test_audio_config_fish_engine() -> None:
    """AudioConfig should accept fish as engine."""
    config = AudioConfig(engine="fish")
    assert config.engine == "fish"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio.py::test_audio_config_fish_engine -v`
Expected: FAIL with validation error (fish not in Literal)

**Step 3: Update AudioConfig**

In `src/chiron/content/audio.py`, change the `engine` type in `AudioConfig`:

```python
engine: Literal["fish", "coqui", "piper", "export"] = "export"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audio.py::test_audio_config_fish_engine -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/chiron/content/audio.py tests/test_audio.py
git commit -m "feat(audio): add fish to AudioConfig engine options"
```

---

### Task 7: Generate Audio Fish - Basic Structure

**Files:**
- Modify: `src/chiron/content/audio.py`
- Test: `tests/test_audio.py`

**Step 1: Write the failing test for Fish not installed**

Add to `tests/test_audio.py`:

```python
from chiron.content.audio import generate_audio_fish


def test_generate_audio_fish_not_installed(tmp_path: Path) -> None:
    """Should return None when Fish Speech is not installed."""
    script = "Test audio content."
    output_path = tmp_path / "audio.wav"

    with patch.dict("sys.modules", {"fish_speech": None}):
        result = generate_audio_fish(script, output_path)

    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio.py::test_generate_audio_fish_not_installed -v`
Expected: FAIL with "cannot import name 'generate_audio_fish'"

**Step 3: Write minimal implementation stub**

Add to `src/chiron/content/audio.py`:

```python
def generate_audio_fish(
    script: str,
    output_path: Path,
    voice_config: VoiceConfig | None = None,
    voice_dir: Path | None = None,
) -> Path | None:
    """Generate audio using Fish Speech.

    Fish Speech provides high-quality neural TTS with voice cloning.
    Segments text conservatively to avoid GPU OOM.

    Args:
        script: Text to convert to speech.
        output_path: Where to save the audio file.
        voice_config: Optional voice configuration for cloning.
        voice_dir: Directory containing reference audio (if cloning).

    Returns:
        Path to generated WAV file, or None if generation failed.
    """
    try:
        import fish_speech  # noqa: F401
    except ImportError:
        logger.warning("Fish Speech not installed. Install with: uv sync --extra fish")
        return None

    # TODO: Implement generation
    return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audio.py::test_generate_audio_fish_not_installed -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/chiron/content/audio.py tests/test_audio.py
git commit -m "feat(audio): add generate_audio_fish stub"
```

---

### Task 8: Wire Fish into generate_audio

**Files:**
- Modify: `src/chiron/content/audio.py:107-136`
- Test: `tests/test_audio.py`

**Step 1: Write the failing test**

Add to `tests/test_audio.py`:

```python
def test_generate_audio_calls_fish(tmp_path: Path) -> None:
    """Should call generate_audio_fish when engine is fish."""
    script = "Test content."
    output_path = tmp_path / "audio"
    config = AudioConfig(engine="fish")

    with patch("chiron.content.audio.generate_audio_fish", return_value=tmp_path / "audio.wav") as mock_fish:
        result = generate_audio(script, output_path, config)

    mock_fish.assert_called_once()
    assert result == tmp_path / "audio.wav"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio.py::test_generate_audio_calls_fish -v`
Expected: FAIL (generate_audio doesn't call fish yet)

**Step 3: Update generate_audio function**

In `src/chiron/content/audio.py`, update the `generate_audio` function to add fish handling after the export check and before coqui:

```python
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

    if config.engine == "fish":
        voice_config, voice_dir = load_voice_config()
        return generate_audio_fish(script, output_path, voice_config, voice_dir)

    if config.engine == "coqui":
        return generate_audio_coqui(script, output_path, config)

    if config.engine == "piper":
        return generate_audio_piper(script, output_path, config)

    return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audio.py::test_generate_audio_calls_fish -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/chiron/content/audio.py tests/test_audio.py
git commit -m "feat(audio): wire fish engine into generate_audio"
```

---

### Task 9: Add Fish Detection to Pipeline

**Files:**
- Modify: `src/chiron/content/pipeline.py:66-78`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
from unittest.mock import patch

from chiron.content.pipeline import check_available_tools


def test_check_available_tools_detects_fish() -> None:
    """Should detect Fish Speech availability."""
    with patch("chiron.content.pipeline._try_import", return_value=True):
        tools = check_available_tools()

    assert "fish" in tools
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py::test_check_available_tools_detects_fish -v`
Expected: FAIL ("fish" not in tools)

**Step 3: Update check_available_tools**

In `src/chiron/content/pipeline.py`, update `check_available_tools`:

```python
def check_available_tools() -> dict[str, bool]:
    """Check which content generation tools are available.

    Returns:
        Dictionary mapping tool names to availability booleans.
    """
    return {
        "fish": _try_import("fish_speech"),
        "coqui": _try_import("TTS"),
        "piper": _try_import("piper"),
        "plantuml": shutil.which("plantuml") is not None,
        "pandoc": shutil.which("pandoc") is not None,
        "weasyprint": shutil.which("weasyprint") is not None,
    }
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pipeline.py::test_check_available_tools_detects_fish -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/chiron/content/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): add fish detection to check_available_tools"
```

---

### Task 10: Update Pipeline TTS Priority

**Files:**
- Modify: `src/chiron/content/pipeline.py:218-232`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
def test_pipeline_prefers_fish_over_coqui(tmp_path: Path) -> None:
    """Pipeline should prefer Fish when both Fish and Coqui are available."""
    from chiron.content.parser import ParsedLesson
    from chiron.content.pipeline import generate_lesson_artifacts

    parsed = ParsedLesson(
        title="Test Lesson",
        objectives=["Learn stuff"],
        audio_script="Hello world.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    with patch("chiron.content.pipeline.check_available_tools", return_value={
        "fish": True,
        "coqui": True,
        "piper": False,
        "plantuml": False,
        "pandoc": False,
        "weasyprint": False,
    }):
        with patch("chiron.content.pipeline.generate_audio") as mock_gen:
            mock_gen.return_value = tmp_path / "audio.wav"
            generate_lesson_artifacts(parsed, tmp_path)

            # Check that AudioConfig was created with fish engine
            call_args = mock_gen.call_args
            config = call_args[1].get("config") or call_args[0][2] if len(call_args[0]) > 2 else None
            # Actually we need to check the AudioConfig passed
```

Actually, let me simplify this test:

```python
def test_pipeline_selects_fish_engine(tmp_path: Path) -> None:
    """Pipeline should select Fish as TTS engine when available."""
    from chiron.content.audio import AudioConfig
    from chiron.content.parser import ParsedLesson
    from chiron.content.pipeline import generate_lesson_artifacts

    parsed = ParsedLesson(
        title="Test Lesson",
        objectives=["Learn stuff"],
        audio_script="Hello world.",
        diagrams=[],
        exercise_seeds=[],
        srs_items=[],
    )

    with patch("chiron.content.pipeline.check_available_tools", return_value={
        "fish": True,
        "coqui": True,
        "piper": False,
        "plantuml": False,
        "pandoc": False,
        "weasyprint": False,
    }):
        with patch("chiron.content.pipeline.generate_audio") as mock_gen:
            mock_gen.return_value = tmp_path / "audio.wav"
            generate_lesson_artifacts(parsed, tmp_path)

            # Verify generate_audio was called
            mock_gen.assert_called_once()
            # Get the AudioConfig that was passed
            _, _, config = mock_gen.call_args[0]
            assert config.engine == "fish"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py::test_pipeline_selects_fish_engine -v`
Expected: FAIL (engine will be "coqui" not "fish")

**Step 3: Update pipeline TTS selection**

In `src/chiron/content/pipeline.py`, update the TTS selection logic in `generate_lesson_artifacts` (around line 222-232):

```python
    # Auto-select TTS engine based on availability if using default export mode
    if audio_config.engine == "export":
        # Check if a TTS engine is available and upgrade if so
        if tools.get("fish"):
            audio_config = AudioConfig(engine="fish")
            logger.info("Using Fish TTS for audio generation")
        elif tools.get("coqui"):
            audio_config = AudioConfig(engine="coqui")
            logger.info("Using Coqui TTS for audio generation")
        elif tools.get("piper"):
            audio_config = AudioConfig(engine="piper")
            logger.info("Using Piper TTS for audio generation")
        else:
            logger.info("No TTS engine available, exporting script.txt for external TTS")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pipeline.py::test_pipeline_selects_fish_engine -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/chiron/content/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): prioritize Fish TTS over Coqui"
```

---

### Task 11: Implement Fish Audio Generation Core

**Files:**
- Modify: `src/chiron/content/audio.py`
- Test: `tests/test_audio.py`

**Step 1: Write test for successful generation (mocked)**

Add to `tests/test_audio.py`:

```python
def test_generate_audio_fish_success(tmp_path: Path) -> None:
    """Should generate audio when Fish Speech is available."""
    script = "Hello world. This is a test."
    output_path = tmp_path / "audio.wav"

    # Create mock fish_speech module
    mock_fish = MagicMock()
    mock_model = MagicMock()
    mock_fish.load_model.return_value = mock_model

    # Mock the inference to write a dummy wav file
    def mock_infer(text, **kwargs):
        # Return fake audio data (just zeros for testing)
        import numpy as np
        return np.zeros(1000, dtype=np.float32), 22050

    mock_model.infer = mock_infer

    with patch.dict("sys.modules", {"fish_speech": mock_fish}):
        with patch("chiron.content.audio.segment_for_fish", return_value=["Hello world.", "This is a test."]):
            # We need to mock the actual Fish Speech API - this will depend on the real API
            # For now, test that it tries to import and segment
            result = generate_audio_fish(script, output_path)

    # Result will be None until we implement, but structure is tested
```

This test will need adjustment once we understand the Fish Speech API. Let me write a simpler integration test structure:

```python
def test_generate_audio_fish_segments_script(tmp_path: Path) -> None:
    """Should segment script before generating."""
    script = "Hello world. This is a test."
    output_path = tmp_path / "audio.wav"

    with patch("chiron.content.audio.segment_for_fish") as mock_segment:
        mock_segment.return_value = ["Hello world.", "This is a test."]

        # Fish not installed, but we can verify segmentation would be called
        with patch.dict("sys.modules", {"fish_speech": MagicMock()}):
            with patch("chiron.content.audio._generate_fish_chunk", return_value=None):
                generate_audio_fish(script, output_path)

        mock_segment.assert_called_once_with(script)
```

Actually, let's pause on the full Fish implementation. We need to understand the Fish Speech API first. Let me check if there's documentation or examples.

**Step 2: Research Fish Speech API**

Before implementing, we need to understand how Fish Speech is called as a library. Check:
- Fish Speech PyPI page
- The generate_chunks.py in ~/Working/fish_ttf uses the web API

**Important:** The Fish Speech library API may differ from the web API. We'll need to investigate before fully implementing Task 11.

**Step 3: Create placeholder implementation with TODO**

For now, add a working skeleton that logs and returns None:

```python
def generate_audio_fish(
    script: str,
    output_path: Path,
    voice_config: VoiceConfig | None = None,
    voice_dir: Path | None = None,
) -> Path | None:
    """Generate audio using Fish Speech.

    Fish Speech provides high-quality neural TTS with voice cloning.
    Segments text conservatively to avoid GPU OOM.

    Args:
        script: Text to convert to speech.
        output_path: Where to save the audio file.
        voice_config: Optional voice configuration for cloning.
        voice_dir: Directory containing reference audio (if cloning).

    Returns:
        Path to generated WAV file, or None if generation failed.
    """
    try:
        import fish_speech  # noqa: F401
    except ImportError:
        logger.warning("Fish Speech not installed. Install with: uv sync --extra fish")
        return None

    voice_config = voice_config or VoiceConfig()
    output_path = output_path.with_suffix(".wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Segment for GPU safety
    segments = segment_for_fish(script)
    if not segments:
        logger.warning("No segments to generate audio for")
        return None

    logger.info("Generating Fish TTS audio: %d segments", len(segments))

    # TODO: Implement actual Fish Speech generation
    # This requires investigating the fish_speech library API
    # For now, fall through to return None
    logger.warning("Fish Speech generation not yet implemented")
    return None
```

**Step 4: Commit placeholder**

```bash
git add src/chiron/content/audio.py
git commit -m "feat(audio): add Fish generation placeholder (API investigation needed)"
```

---

### Task 12: Run Full Test Suite

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linting**

Run: `uv run ruff check src/ tests/`
Expected: No errors

**Step 3: Run type checking**

Run: `uv run mypy src/chiron/`
Expected: No errors (or only pre-existing ones)

**Step 4: Commit any fixes if needed**

---

### Task 13: Document Fish Speech API Investigation

**Files:**
- Create: `docs/plans/2026-01-01-fish-tts-continue.md`

**Step 1: Write continuation prompt**

Create a file with instructions for completing the Fish Speech integration once the API is understood:

```markdown
# Fish TTS Implementation Continuation

## Status

Basic infrastructure is in place:
- VoiceConfig model
- load_voice_config() for YAML configs
- segment_for_fish() for GPU-safe chunking
- generate_audio_fish() stub
- Pipeline priority: Fish > Coqui > Piper > export

## Remaining Work

1. **Investigate Fish Speech library API**
   - Check: `python -c "import fish_speech; help(fish_speech)"`
   - Or: Read fish_speech source code
   - Document the actual inference API

2. **Implement _generate_fish_chunk()**
   - Load model once at start
   - Generate audio for each segment
   - Call torch.cuda.empty_cache() after each chunk
   - Handle errors with fail-fast

3. **Implement audio stitching**
   - Reuse existing _stitch_wav_files() function

4. **Add voice cloning support**
   - Load reference audio from voice_dir
   - Pass to Fish Speech inference

5. **Integration test**
   - Test with actual Fish Speech on GPU
   - Verify GPU memory management works

## Commands

```bash
# Install Fish Speech
uv sync --extra fish

# Test import
uv run python -c "import fish_speech; print(dir(fish_speech))"
```
```

**Step 2: Commit**

```bash
git add docs/plans/2026-01-01-fish-tts-continue.md
git commit -m "docs: add Fish TTS implementation continuation notes"
```

---

## Summary

This plan sets up all the infrastructure for Fish TTS integration:

| Task | Component |
|------|-----------|
| 1 | Dependencies in pyproject.toml |
| 2-4 | VoiceConfig model and YAML loading |
| 5 | GPU-safe sentence segmentation |
| 6-8 | AudioConfig and generate_audio wiring |
| 9-10 | Pipeline detection and priority |
| 11 | Generation placeholder (needs API research) |
| 12 | Verification |
| 13 | Continuation documentation |

The actual Fish Speech API implementation (Task 11) requires investigating the library's Python API, which may differ from the web API used in ~/Working/fish_ttf/.
