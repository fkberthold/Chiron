# Fish TTS GPU Fix - Continuation Prompt

## Problem
Fish Speech TTS times out during `chiron lesson` audio generation. The server starts but requests timeout after 30s on segment 1, suggesting it's running on CPU instead of GPU.

## Root Cause Analysis Complete

### Issue 1: SOLVED - Detection
`check_available_tools()` now uses `_find_fish_speech_dir()` instead of import check.

### Issue 2: SOLVED - Nix Environment Isolation
Fish Speech server needs clean env to avoid Nix Python 3.11/3.12 conflicts. Fixed with explicit env dict.

### Issue 3: SOLVED - Working Directory
Model checkpoints use relative paths (`checkpoints/openaudio-s1-mini`). Fixed with bash wrapper: `cd $fish_dir && python ...`

### Issue 4: SOLVED - LD_LIBRARY_PATH Missing CUDA Paths

**Root cause:** The `LD_LIBRARY_PATH` inherited from Cursor IDE's AppImage contained only AppImage-specific paths like `/tmp/.mount_CursoridoGEN/usr/lib/`, not the system CUDA library path `/usr/lib/x86_64-linux-gnu/` where `libcuda.so` lives.

**Fix applied:** Now explicitly prepend known CUDA library paths to `LD_LIBRARY_PATH`:
```python
cuda_lib_paths = [
    "/usr/lib/x86_64-linux-gnu",  # Ubuntu/Debian CUDA location
    "/usr/local/cuda/lib64",       # Standard CUDA install location
]
existing_ld = os.environ.get("LD_LIBRARY_PATH", "")
all_paths = [p for p in cuda_lib_paths + existing_ld.split(":") if p]
clean_env["LD_LIBRARY_PATH"] = ":".join(all_paths)
```

This ensures CUDA libraries are found regardless of what IDE or environment spawned Chiron.

### Issue 5: SOLVED - Stale Fish Processes Holding GPU Memory

**Root cause:** When Chiron crashed or was killed, or when the IDE restarted, orphan Fish Speech server processes remained running and held GPU memory (~4.5GB). When a new lesson was generated, the new server would try to start and immediately crash with CUDA OOM.

**Fix applied:** Added `_kill_stale_fish_processes()` function that runs before starting a new server:
- Uses `pgrep -f "api_server.py.*--listen"` to find any Fish server processes
- Sends SIGTERM to kill them
- Waits 2s for GPU memory to be released

This ensures GPU memory is freed before starting a new server instance.

### Issue 6: SOLVED - Timeout Too Short

**Root cause:** The original 30s timeout was too short for GPU JIT compilation on first segment.

**Fix applied:** Increased `FISH_API_TIMEOUT` from 30s to 120s.

### Issue 7: Added Progress Logging

Added detailed logging to `generate_audio_fish()` to help debug timing issues:
- Logs estimated total time based on ~9 chars/sec GPU performance
- Logs each segment start with character count
- Logs segment completion time
- Logs total generation time

## Expected Performance

With GPU acceleration, Fish TTS generates at approximately:
- ~8-9 tokens/second
- ~9 characters/second for audio output
- A 6000 character script (~26 segments) takes ~11-13 minutes

Each 300-character segment takes ~25-35 seconds to generate.

## Verification

To verify the fix works:

1. **Kill any stale processes first:**
   ```bash
   pkill -f "api_server.py"
   ```

2. **Watch GPU memory:**
   ```bash
   watch -n 1 nvidia-smi
   ```

3. **Run audio generation test:**
   ```bash
   devbox run "uv run python -c \"
   import tempfile, logging
   from pathlib import Path
   from chiron.content.audio import generate_audio_fish
   logging.basicConfig(level=logging.INFO)

   with tempfile.TemporaryDirectory() as d:
       result = generate_audio_fish('Hello, this is a test.', Path(d) / 'test.wav')
       print('Success!' if result else 'Failed')
   \""
   ```

GPU memory should jump to ~5GB when Fish Speech starts, and the test should complete in ~5 seconds.

All audio tests pass: `devbox run "uv run python -m pytest tests/test_audio.py -v"`
