# Fish TTS Debugging Continuation

## Problem Statement

Fish Speech TTS audio generation is failing silently during `chiron lesson`. User sees no output about why audio failed - just "○ audio (TTS not available)" in the CLI output.

## Two Issues to Fix

### 1. No Logging Visible to User

The `generate_audio_fish()` function logs errors but they don't appear in CLI output. Need to:
- Add Rich console output for Fish TTS status
- Show server startup progress to user
- Display clear error messages when Fish fails

### 2. Hardcoded Path to Fish Speech

Current code in `src/chiron/content/audio.py` has:
```python
FISH_SPEECH_DIR = Path.home() / "Working" / "fish_ttf" / "fish-speech"
```

This is wrong - it's a developer-specific path. Should look in:
- `FISH_SPEECH_DIR` env var (if set)
- Standard locations like `~/.local/share/fish-speech`
- Or use the installed `fish_speech` module's `__path__` to find it

## Current Architecture

### File: `src/chiron/content/audio.py`

Key functions:
- `_find_fish_speech_dir()` - Locates fish-speech installation (lines ~96-120)
- `_start_fish_server()` - Starts API server subprocess (lines ~123-171)
- `_ensure_fish_server_running()` - Orchestrates server startup (lines ~205-266)
- `generate_audio_fish()` - Main entry point (lines ~641+)

### File: `src/chiron/content/pipeline.py`

- `check_available_tools()` at line 66 - checks `_try_import("fish_speech")`
- `generate_lesson_artifacts()` at line 102 - calls `generate_audio()` at line 239

### File: `src/chiron/cli.py`

- `lesson()` command at line 222 - displays artifact tree showing audio status

## What Happens Now

1. `check_available_tools()` returns `{"fish": True}` because `fish_speech` module imports
2. `generate_lesson_artifacts()` sets `audio_config.engine = "fish"`
3. `generate_audio()` calls `generate_audio_fish()`
4. `_ensure_fish_server_running()` tries to find and start server
5. `_find_fish_speech_dir()` returns `None` (can't find `~/Working/fish_ttf/fish-speech`)
6. Logs error but user doesn't see it
7. Returns `None`, CLI shows "TTS not available"

## Fix Plan

### Step 1: Better Fish Speech Discovery

Update `_find_fish_speech_dir()` to:

```python
def _find_fish_speech_dir() -> Path | None:
    """Find the Fish Speech installation directory."""
    # 1. Check environment variable
    env_path = os.environ.get("FISH_SPEECH_DIR")
    if env_path:
        path = Path(env_path)
        if (path / "tools" / "api_server.py").exists():
            return path

    # 2. Try to find via installed module
    try:
        import fish_speech
        module_path = Path(fish_speech.__path__[0])
        # The repo structure has tools/ as sibling to fish_speech/
        repo_root = module_path.parent
        if (repo_root / "tools" / "api_server.py").exists():
            return repo_root
    except (ImportError, AttributeError, IndexError):
        pass

    # 3. Check standard locations
    standard_paths = [
        Path.home() / ".local" / "share" / "fish-speech",
        Path("/opt/fish-speech"),
        Path.home() / "fish-speech",
    ]
    for path in standard_paths:
        if (path / "tools" / "api_server.py").exists():
            return path

    return None
```

### Step 2: Add User-Visible Feedback

In `generate_audio_fish()`, add Rich console output:

```python
from rich.console import Console

console = Console()

def generate_audio_fish(...) -> Path | None:
    # Show user what's happening
    with console.status("[bold blue]Checking Fish Speech server..."):
        if not _ensure_fish_server_running(api_url):
            console.print("[red]✗ Fish Speech server not available[/red]")
            console.print("[dim]Set FISH_SPEECH_DIR or install fish-speech[/dim]")
            return None

    console.print("[green]✓ Fish Speech server ready[/green]")
    # ... rest of function
```

### Step 3: Better Error Messages

Update `_ensure_fish_server_running()` to return more info:

```python
def _ensure_fish_server_running(...) -> tuple[bool, str]:
    """Returns (success, message)"""
    if _is_fish_server_running(api_url):
        return True, "Server already running"

    fish_dir = _find_fish_speech_dir()
    if fish_dir is None:
        return False, "Fish Speech installation not found. Set FISH_SPEECH_DIR environment variable."

    # ... start server logic
```

## Test Commands

```bash
# Run tests
/bin/bash -c "/home/frank/repos/Chiron/.venv/bin/python -m pytest tests/test_audio.py -v"

# Run linting
/bin/bash -c "/home/frank/repos/Chiron/.venv/bin/python -m ruff check src/chiron/content/audio.py"

# Run type checking
/bin/bash -c "/home/frank/repos/Chiron/.venv/bin/python -m mypy src/chiron/content/audio.py"

# Test Fish discovery manually
/bin/bash -c "/home/frank/repos/Chiron/.venv/bin/python -c \"
import fish_speech
print('Module path:', fish_speech.__path__)
print('Module file:', fish_speech.__file__)
\""
```

## User's Fish Speech Setup

The user has Fish Speech installed at:
- `~/Working/fish_ttf/fish-speech/` (git clone)
- Has working `tools/api_server.py`
- Has checkpoints in `checkpoints/openaudio-s1-mini/`

The fish_speech pip package is installed in Chiron's venv but doesn't include the tools/ directory.

## Key Files to Modify

1. `src/chiron/content/audio.py` - Fix discovery, add user feedback
2. `tests/test_audio.py` - Update tests for new behavior
3. Possibly `src/chiron/cli.py` - Add --verbose flag for audio debugging

## Environment Info

- Working directory: `/home/frank/repos/Chiron`
- Python: 3.11 in `.venv`
- Run tests with: `/bin/bash -c "/home/frank/repos/Chiron/.venv/bin/python -m pytest ..."`
