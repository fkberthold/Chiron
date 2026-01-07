"""Audio generation for Chiron lessons.

Audio rendering priority (per design doc):
1. Fish TTS with GPU acceleration (highest quality, voice cloning)
2. Coqui TTS with GPU acceleration (high quality)
3. Piper TTS (fallback, faster but more robotic)
4. Export script for external TTS like Speechify (last resort)
"""

import atexit
import logging
import os
import re
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:
    pass  # TTS types would go here if we had stubs

logger = logging.getLogger(__name__)

# Fish Speech API configuration
FISH_API_URL = "http://127.0.0.1:8888/v1/tts"
FISH_API_BASE_URL = "http://127.0.0.1:8888"
FISH_API_TIMEOUT = 90  # seconds per segment (typical: 20-40s, max ~60s)
FISH_SERVER_STARTUP_TIMEOUT = 90  # seconds to wait for server startup (includes model loading)
FISH_SERVER_WARMUP_DELAY = 5  # seconds to wait after server start before API calls

# Optimal generation parameters (from extensive testing - see docs/fish-speech-voice-generation.md)
# These values were determined through anchor sweep and depth testing with 224 test files
FISH_GENERATION_SEED = 42  # Fixed seed for reproducible, consistent prosody
FISH_MAX_NEW_TOKENS = 2048  # Sufficient for long outputs
FISH_CHUNK_LENGTH = 200  # Conservative for GPU safety
FISH_TOP_P = 0.9  # Good variety while maintaining stability (tested at 1.0, 0.9 recommended)
FISH_TEMPERATURE = 0.8  # Good balance of variety/stability
FISH_REPETITION_PENALTY = 1.1  # Prevent loops

# Default Fish Speech installation path
FISH_SPEECH_DIR = Path.home() / "Working" / "fish_ttf" / "fish-speech"

# Global server process reference for cleanup
_fish_server_process: subprocess.Popen[bytes] | None = None


class AnchorConfig(BaseModel):
    """Configuration for synthetic anchor-based voice cloning.

    Anchors provide more stable voice cloning than direct reference audio.
    See docs/fish-speech-voice-generation.md for details on the anchor approach.
    """

    audio: str  # Filename of pre-generated anchor WAV
    text: str  # The standardized text used to generate the anchor
    seed: int  # Seed used to generate this anchor (for reproducibility)


# Standard anchor text used for all anchor generation
# This text exercises diverse phonemes and prosodic patterns
ANCHOR_GENERATION_TEXT = (
    "Hello, and welcome. Have you ever wondered how things really work beneath "
    "the surface? It's a fascinating question, one worth measuring carefully. "
    "Let's take a closer look together. Pay attention to the details, because "
    "they often reveal something surprising. The journey itself can be just as "
    "rewarding as the destination. That's the pleasure of discovery."
)


class VoiceConfig(BaseModel):
    """Voice configuration for Fish TTS.

    Uses anchor-based voice cloning for stable, consistent results.
    See docs/fish-speech-voice-generation.md for the anchor methodology.
    """

    # Anchor-based voice cloning (required)
    # The anchor is a synthetic audio file generated from reference voice + seed
    anchor: AnchorConfig | None = None

    # Server-side cached reference ID (set after anchor registration)
    reference_id: str | None = None

    # Generation parameters (defaults from testing)
    chunk_length: int = FISH_CHUNK_LENGTH
    top_p: float = FISH_TOP_P
    seed: int = FISH_GENERATION_SEED  # Fixed seed for consistent prosody


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


def _is_fish_server_running(api_url: str = FISH_API_URL) -> bool:
    """Check if Fish Speech API server is responding.

    Args:
        api_url: The API endpoint URL.

    Returns:
        True if server is responding, False otherwise.
    """
    try:
        import requests
    except ImportError:
        return False

    # Extract base URL from TTS endpoint
    base_url = api_url.rsplit("/", 2)[0]  # http://127.0.0.1:8888

    try:
        response = requests.get(f"{base_url}/", timeout=2)
        return response.status_code in (200, 404)  # 404 is OK - server is up
    except Exception:
        return False


def _find_fish_speech_dir() -> Path | None:
    """Find the Fish Speech installation directory.

    Checks common locations and environment variable.

    Returns:
        Path to fish-speech directory, or None if not found.
    """
    # Check environment variable first
    env_path = os.environ.get("FISH_SPEECH_DIR")
    if env_path:
        path = Path(env_path)
        if (path / "tools" / "api_server.py").exists():
            return path

    # Check default location
    if (FISH_SPEECH_DIR / "tools" / "api_server.py").exists():
        return FISH_SPEECH_DIR

    # Check ~/.local/share/fish-speech
    local_path = Path.home() / ".local" / "share" / "fish-speech"
    if (local_path / "tools" / "api_server.py").exists():
        return local_path

    return None


def _kill_stale_fish_processes(port: int) -> None:
    """Kill any stale Fish Speech processes that might be holding GPU memory.

    This prevents CUDA OOM errors when starting a new server after a crash
    or improper shutdown left orphan processes.

    Args:
        port: Port number to check for stale processes.
    """
    try:
        # Find processes listening on the target port (check port is in use)
        subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Also find any fish api_server.py processes
        ps_result = subprocess.run(
            ["pgrep", "-f", "api_server.py.*--listen"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ps_result.stdout.strip():
            pids = ps_result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    logger.info("Killed stale Fish process %s", pid)
                except (ProcessLookupError, ValueError):
                    pass
            # Give processes time to release GPU memory
            time.sleep(2)
    except Exception as e:
        logger.debug("Error checking for stale processes: %s", e)


def _start_fish_server(
    fish_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8888,
) -> subprocess.Popen[bytes] | None:
    """Start the Fish Speech API server.

    Args:
        fish_dir: Path to fish-speech installation directory.
        host: Host to bind server to.
        port: Port to bind server to.

    Returns:
        Popen process object, or None if failed to start.
    """
    global _fish_server_process

    server_script = fish_dir / "tools" / "api_server.py"
    if not server_script.exists():
        logger.error("Fish Speech server script not found: %s", server_script)
        return None

    # Kill any stale Fish processes to free GPU memory
    _kill_stale_fish_processes(port)

    logger.info("Starting Fish Speech server at %s:%d...", host, port)

    # Use Fish Speech's own venv Python if available (has required dependencies)
    fish_python = fish_dir / ".venv" / "bin" / "python"
    if not fish_python.exists():
        # Fall back to system python
        fish_python = Path("python")

    try:
        # Build clean environment - Fish Speech's venv needs isolation from Nix
        # to avoid Python version mismatches (e.g., Nix Python 3.11 Pillow vs Fish 3.12)
        clean_env = {
            "PATH": f"{fish_dir / '.venv' / 'bin'}:/usr/bin:/bin",
            "VIRTUAL_ENV": str(fish_dir / ".venv"),
        }
        # Only add non-empty env vars (empty strings can cause issues)
        for var in ("HOME", "USER", "CUDA_VISIBLE_DEVICES"):
            val = os.environ.get(var)
            if val:
                clean_env[var] = val

        # Explicitly set LD_LIBRARY_PATH to include CUDA libraries
        # The inherited LD_LIBRARY_PATH may be from an IDE (e.g., Cursor AppImage)
        # and not contain system CUDA paths needed for GPU acceleration
        cuda_lib_paths = [
            "/usr/lib/x86_64-linux-gnu",  # Ubuntu/Debian CUDA location
            "/usr/local/cuda/lib64",       # Standard CUDA install location
        ]
        existing_ld = os.environ.get("LD_LIBRARY_PATH", "")
        # Filter out empty paths and combine
        all_paths = [p for p in cuda_lib_paths + existing_ld.split(":") if p]
        clean_env["LD_LIBRARY_PATH"] = ":".join(all_paths)

        # Use shell with explicit cd - subprocess cwd doesn't work reliably
        # when env is fully replaced (relative paths break for model loading)
        #
        # IMPORTANT: We redirect stdout/stderr to a log file instead of PIPE.
        # Fish Speech generates lots of output (progress bars, logs), and if
        # we use PIPE without reading, the buffer fills up and deadlocks
        # the server process. The file descriptor is passed directly to Popen
        # which keeps it open even after we lose the Python handle.
        log_file = Path("/tmp/fish_server.log")
        log_fd = open(log_file, "w")
        process = subprocess.Popen(
            [
                "/bin/bash", "-c",
                f"cd {fish_dir} && {fish_python} tools/api_server.py --listen {host}:{port}",
            ],
            stdout=log_fd,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout (log file)
            env=clean_env,
            # Start in new process group so we can kill it cleanly
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )
        # Close our handle - the subprocess has its own copy of the fd
        log_fd.close()

        _fish_server_process = process

        # Register cleanup handler
        atexit.register(_stop_fish_server)

        return process

    except Exception as e:
        logger.error("Failed to start Fish Speech server: %s", e)
        return None


def _kill_fish_server_by_port(port: int = 8888) -> bool:
    """Kill Fish Speech server by finding process listening on port.

    This handles externally-started servers that we don't have a process handle for.

    Args:
        port: The port the server is listening on.

    Returns:
        True if a server was found and killed, False otherwise.
    """
    try:
        # Use lsof to find process on port (works on Linux/Mac)
        import subprocess
        result = subprocess.run(
            ["lsof", "-t", "-i", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    pid_int = int(pid.strip())
                    logger.info("Killing Fish server process %d on port %d", pid_int, port)
                    os.kill(pid_int, signal.SIGTERM)
                except (ValueError, OSError) as e:
                    logger.warning("Failed to kill PID %s: %s", pid, e)
            # Wait for processes to die
            time.sleep(2)
            return True
    except FileNotFoundError:
        # lsof not available, try ss (Linux)
        try:
            result = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse PID from ss output: "users:(("python",pid=12345,fd=5))"
                import re
                pids = re.findall(r'pid=(\d+)', result.stdout)
                for pid in pids:
                    try:
                        pid_int = int(pid)
                        logger.info("Killing Fish server process %d on port %d", pid_int, port)
                        os.kill(pid_int, signal.SIGTERM)
                    except (ValueError, OSError) as e:
                        logger.warning("Failed to kill PID %s: %s", pid, e)
                if pids:
                    time.sleep(2)
                    return True
        except Exception as e:
            logger.debug("ss method failed: %s", e)
    except Exception as e:
        logger.debug("lsof method failed: %s", e)

    return False


def _stop_fish_server(force_kill_external: bool = False) -> None:
    """Stop the Fish Speech server.

    Args:
        force_kill_external: If True, also kill externally-started servers
            by finding processes on the port.
    """
    global _fish_server_process

    if _fish_server_process is None:
        if force_kill_external:
            # Try to kill any external server on the port
            _kill_fish_server_by_port()
        return

    logger.info("Stopping Fish Speech server...")

    try:
        # Kill process group to ensure all children are terminated
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(_fish_server_process.pid), signal.SIGTERM)
        else:
            _fish_server_process.terminate()

        # Wait for clean shutdown
        _fish_server_process.wait(timeout=5)

    except subprocess.TimeoutExpired:
        logger.warning("Fish server didn't stop gracefully, killing...")
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(_fish_server_process.pid), signal.SIGKILL)
        else:
            _fish_server_process.kill()
    except Exception as e:
        logger.warning("Error stopping Fish server: %s", e)

    _fish_server_process = None


def _ensure_fish_server_running(
    api_url: str = FISH_API_URL,
    timeout: int = FISH_SERVER_STARTUP_TIMEOUT,
) -> bool:
    """Ensure Fish Speech server is running, starting it if necessary.

    Args:
        api_url: The API endpoint URL.
        timeout: Maximum seconds to wait for server startup.

    Returns:
        True if server is running (or was started), False otherwise.
    """
    # Check if already running and responsive
    if _is_fish_server_running(api_url):
        logger.debug("Fish Speech server already running")
        return True

    # Find fish-speech installation
    fish_dir = _find_fish_speech_dir()
    if fish_dir is None:
        logger.warning(
            "Fish Speech not found. Set FISH_SPEECH_DIR or install to %s",
            FISH_SPEECH_DIR,
        )
        return False

    # Parse host/port from URL
    import urllib.parse
    parsed = urllib.parse.urlparse(api_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8888

    # Kill any zombie process on the port before starting
    # This handles the case where a previous server is not responding
    # but still holding the port
    if _kill_fish_server_by_port(port):
        logger.info("Killed unresponsive Fish server on port %d", port)
        time.sleep(2)  # Give GPU memory time to release

    # Start server
    process = _start_fish_server(fish_dir, host, port)
    if process is None:
        return False

    # Wait for server to be ready
    logger.info("Waiting for Fish Speech server to start (up to %ds)...", timeout)
    start_time = time.time()

    while time.time() - start_time < timeout:
        if _is_fish_server_running(api_url):
            logger.info("Fish Speech server is ready")
            return True

        # Check if process died
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            logger.error(
                "Fish Speech server exited unexpectedly:\n%s\n%s",
                stdout.decode() if stdout else "",
                stderr.decode() if stderr else "",
            )
            return False

        time.sleep(1)

    logger.error("Fish Speech server failed to start within %ds", timeout)
    _stop_fish_server()
    return False


def _register_anchor(
    anchor_path: Path,
    anchor_text: str,
    reference_id: str,
    base_url: str = FISH_API_BASE_URL,
) -> bool:
    """Register an anchor audio file with the Fish Speech server.

    The anchor is registered as a server-side reference that can be used
    for subsequent generation requests via reference_id. This is more
    efficient than sending the reference audio with each request.

    Args:
        anchor_path: Path to the anchor WAV file.
        anchor_text: Transcript of the anchor audio.
        reference_id: Unique ID to register the anchor under.
        base_url: Fish Speech API base URL.

    Returns:
        True if registration succeeded, False otherwise.
    """
    try:
        import requests
    except ImportError:
        logger.error("requests package not installed")
        return False

    if not anchor_path.exists():
        logger.error("Anchor file not found: %s", anchor_path)
        return False

    try:
        with open(anchor_path, "rb") as f:
            audio_data = f.read()

        files = {"audio": (anchor_path.name, audio_data, "audio/wav")}
        data = {"id": reference_id, "text": anchor_text}

        response = requests.post(
            f"{base_url}/v1/references/add",
            files=files,
            data=data,
            timeout=60,
        )

        # 200 = success, 409 = already registered (also success)
        if response.status_code in (200, 409):
            if response.status_code == 409:
                logger.debug("Anchor already registered: %s", reference_id)
            else:
                logger.info(
                    "Registered anchor: %s (%.1f KB)",
                    reference_id, len(audio_data) / 1024
                )
            return True
        else:
            logger.error(
                "Failed to register anchor: %d - %s",
                response.status_code,
                response.text[:200] if response.text else "No response",
            )
            return False

    except Exception as e:
        logger.error("Error registering anchor: %s", e)
        return False


def _prepare_voice_for_generation(
    voice_config: VoiceConfig,
    voice_dir: Path | None,
    base_url: str = FISH_API_BASE_URL,
) -> str | None:
    """Prepare voice for generation by registering anchor if needed.

    This function handles the anchor registration workflow:
    1. If anchor is configured, register it and return the reference_id
    2. If reference_id is already set, use it directly
    3. Otherwise return None (will use inline references)

    Args:
        voice_config: Voice configuration.
        voice_dir: Directory containing voice files.
        base_url: Fish Speech API base URL.

    Returns:
        Reference ID to use for generation, or None for inline references.
    """
    # If we already have a reference_id, use it
    if voice_config.reference_id:
        logger.debug("Using existing reference_id: %s", voice_config.reference_id)
        return voice_config.reference_id

    # If anchor is configured, register it
    if voice_config.anchor and voice_dir:
        anchor_path = voice_dir / voice_config.anchor.audio
        if anchor_path.exists():
            # Generate a deterministic reference_id from the anchor config
            reference_id = f"chiron-anchor-{voice_config.anchor.seed}"

            if _register_anchor(
                anchor_path=anchor_path,
                anchor_text=voice_config.anchor.text,
                reference_id=reference_id,
                base_url=base_url,
            ):
                return reference_id
            else:
                logger.warning(
                    "Failed to register anchor, falling back to inline references"
                )
        else:
            logger.warning("Anchor file not found: %s", anchor_path)

    return None


@dataclass
class AudioConfig:
    """Configuration for audio generation."""

    engine: Literal["fish", "coqui", "piper", "export"] = "export"
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

            # Stitch segments together with punctuation-aware pauses
            _stitch_wav_files(temp_files, output_path, segment_texts=segments)

    except Exception as e:
        logger.error("Failed to generate/stitch segments: %s", e)
        raise

@dataclass
class PauseConfig:
    """Configuration for inter-segment pause durations (in milliseconds)."""

    period_ms: int = 400  # End of sentence (. ! ?)
    comma_ms: int = 150  # Clause break (,)
    colon_ms: int = 300  # Before list/explanation (: ;)
    default_ms: int = 200  # No clear punctuation


def _get_pause_for_segment(segment_text: str, config: PauseConfig) -> int:
    """Determine pause duration based on how the segment ends.

    Args:
        segment_text: The text of the segment.
        config: Pause duration configuration.

    Returns:
        Pause duration in milliseconds.
    """
    text = segment_text.rstrip()
    if not text:
        return config.default_ms

    last_char = text[-1]
    if last_char in ".!?":
        return config.period_ms
    elif last_char == ",":
        return config.comma_ms
    elif last_char in ":;":
        return config.colon_ms
    else:
        return config.default_ms


def _extract_noise_profile(wav_data: bytes, sample_ms: int = 50) -> bytes:
    """Extract noise profile from the end of a WAV segment.

    Takes a small sample from the tail of the audio (where speech has likely
    faded) to capture the background noise floor. This noise can then be used
    to create natural-sounding silence gaps that match the audio character.

    Args:
        wav_data: Raw WAV file bytes.
        sample_ms: Milliseconds of audio to sample from the end.

    Returns:
        Noise sample bytes that can be tiled to create silence gaps.
    """
    import io
    import wave

    try:
        with wave.open(io.BytesIO(wav_data), "rb") as wav:
            sample_rate = wav.getframerate()
            num_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            total_frames = wav.getnframes()

            # Calculate how many frames to sample
            sample_frames = int(sample_rate * sample_ms / 1000)
            # Don't sample more than 10% of the file or the whole thing
            sample_frames = min(sample_frames, total_frames // 10, total_frames)

            if sample_frames < 10:
                # File too short, return digital silence
                return b"\x00" * (sample_frames * num_channels * sample_width)

            # Seek to near the end and read
            wav.setpos(total_frames - sample_frames)
            noise_sample = wav.readframes(sample_frames)

            return noise_sample
    except Exception as e:
        logger.debug("Failed to extract noise profile: %s", e)
        # Return minimal silence on error
        return b"\x00\x00"


def _create_noise_gap(
    noise_sample: bytes,
    gap_ms: int,
    sample_rate: int,
    num_channels: int,
    sample_width: int,
) -> bytes:
    """Create a silence gap filled with noise matching the audio character.

    Args:
        noise_sample: Noise profile bytes to tile.
        gap_ms: Desired gap duration in milliseconds.
        sample_rate: Audio sample rate.
        num_channels: Number of audio channels.
        sample_width: Bytes per sample.

    Returns:
        Gap audio bytes with matching noise floor.
    """
    gap_frames = int(sample_rate * gap_ms / 1000)
    gap_bytes = gap_frames * num_channels * sample_width

    if not noise_sample or len(noise_sample) < 2:
        return b"\x00" * gap_bytes

    # Tile the noise sample to fill the gap
    repetitions = (gap_bytes // len(noise_sample)) + 1
    tiled = noise_sample * repetitions
    return tiled[:gap_bytes]


def _add_noise_floor(
    audio_path: Path,
    noise_level_db: float = -50.0,
) -> None:
    """Add a uniform noise floor to audio to mask inconsistencies.

    Fish Speech generates segments with varying noise characteristics.
    Adding a consistent low-level noise floor smooths transitions between
    segments without noticeably affecting audio quality.

    Args:
        audio_path: Path to WAV file to process (modified in place).
        noise_level_db: Noise level in dB relative to full scale.
            Default -50 dB is barely perceptible but masks inconsistencies.
    """
    import struct
    import wave

    try:
        # Read the audio
        with wave.open(str(audio_path), "rb") as wav:
            params = wav.getparams()
            frames = wav.readframes(wav.getnframes())

        # Only support 16-bit PCM
        if params.sampwidth != 2:
            logger.debug("Skipping noise floor: only 16-bit PCM supported")
            return

        # Convert to samples
        num_samples = len(frames) // 2
        samples = list(struct.unpack(f"<{num_samples}h", frames))

        # Calculate noise amplitude from dB level
        # -50 dB ≈ 0.003 of full scale, which for 16-bit is ~100 amplitude
        noise_amplitude = int(32768 * (10 ** (noise_level_db / 20)))

        # Generate and add uniform noise
        import random
        for i in range(num_samples):
            noise = random.randint(-noise_amplitude, noise_amplitude)
            # Add noise and clamp to valid range
            samples[i] = max(-32768, min(32767, samples[i] + noise))

        # Write back
        with wave.open(str(audio_path), "wb") as wav:
            wav.setparams(params)
            wav.writeframes(struct.pack(f"<{num_samples}h", *samples))

        logger.debug("Added noise floor at %d dB to %s", noise_level_db, audio_path.name)

    except Exception as e:
        logger.warning("Failed to add noise floor: %s", e)


def _stitch_wav_files(
    input_files: list[Path],
    output_path: Path,
    segment_texts: list[str] | None = None,
    pause_config: PauseConfig | None = None,
    noise_floor_db: float | None = -50.0,
) -> None:
    """Concatenate multiple WAV files with punctuation-aware pauses.

    Pauses between segments vary based on ending punctuation:
    - Period/exclamation/question: longer pause (sentence boundary)
    - Comma: shorter pause (clause boundary)
    - Colon/semicolon: medium pause (before elaboration)

    Silence gaps are filled with noise extracted from the audio to avoid
    jarring transitions between speech (with natural noise floor) and
    digital silence.

    A uniform noise floor is added to the final output to mask any
    remaining inconsistencies between segments.

    Args:
        input_files: List of WAV file paths to concatenate.
        output_path: Output WAV file path.
        segment_texts: Text of each segment (for punctuation-aware pauses).
            If None, uses default pause duration.
        pause_config: Pause duration configuration. If None, uses defaults.
        noise_floor_db: Noise floor level in dB to add (default -50 dB).
            Set to None to disable noise floor addition.
    """
    import wave

    if not input_files:
        return

    if pause_config is None:
        pause_config = PauseConfig()

    # Read parameters from first file
    with wave.open(str(input_files[0]), "rb") as first_wav:
        params = first_wav.getparams()

    sample_rate = params.framerate
    num_channels = params.nchannels
    sample_width = params.sampwidth

    # Extract noise profile from first file for natural-sounding gaps
    with open(input_files[0], "rb") as f:
        first_wav_data = f.read()
    noise_sample = _extract_noise_profile(first_wav_data)

    # Write combined audio
    with wave.open(str(output_path), "wb") as output_wav:
        output_wav.setparams(params)

        for i, wav_path in enumerate(input_files):
            with wave.open(str(wav_path), "rb") as input_wav:
                output_wav.writeframes(input_wav.readframes(input_wav.getnframes()))

            # Add silence gap between segments (not after last)
            if i < len(input_files) - 1:
                # Determine pause duration from segment text
                if segment_texts and i < len(segment_texts):
                    gap_ms = _get_pause_for_segment(segment_texts[i], pause_config)
                else:
                    gap_ms = pause_config.default_ms

                # Create noise-matched gap
                gap = _create_noise_gap(
                    noise_sample, gap_ms, sample_rate, num_channels, sample_width
                )
                output_wav.writeframes(gap)

    # Add uniform noise floor to mask segment inconsistencies
    if noise_floor_db is not None:
        _add_noise_floor(output_path, noise_floor_db)


def _call_fish_api(
    text: str,
    output_path: Path,
    voice_config: VoiceConfig,
    api_url: str = FISH_API_URL,
) -> bool:
    """Call Fish Speech API to generate audio for a single segment.

    Args:
        text: Text to synthesize.
        output_path: Where to save the audio file.
        voice_config: Voice configuration (must have reference_id set).
        api_url: Fish Speech API endpoint URL.

    Returns:
        True if generation succeeded, False otherwise.
    """
    try:
        import ormsgpack  # type: ignore[import-not-found]
        import requests
    except ImportError:
        logger.error("Required packages not installed: requests, ormsgpack")
        return False

    if not voice_config.reference_id:
        logger.error("No reference_id configured - anchor must be registered first")
        return False

    # Build request payload with optimal parameters from testing
    # See docs/fish-speech-voice-generation.md for parameter rationale
    data = {
        "text": text,
        "references": [],  # Always empty - we use server-side reference_id
        "reference_id": voice_config.reference_id,
        "format": "wav",
        "max_new_tokens": FISH_MAX_NEW_TOKENS,
        "chunk_length": voice_config.chunk_length,
        "top_p": voice_config.top_p,
        "repetition_penalty": FISH_REPETITION_PENALTY,
        "temperature": FISH_TEMPERATURE,
        "streaming": False,
        "use_memory_cache": "on",
        "seed": voice_config.seed,
    }

    try:
        response = requests.post(
            api_url,
            params={"format": "msgpack"},
            data=ormsgpack.packb(data),
            headers={"content-type": "application/msgpack"},
            timeout=FISH_API_TIMEOUT,
        )

        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            logger.error(
                "Fish API request failed: %d - %s",
                response.status_code,
                response.text[:200] if response.text else "No response",
            )
            return False

    except requests.exceptions.ConnectionError:
        logger.error(
            "Cannot connect to Fish Speech API at %s. "
            "Start the server with: python tools/api_server.py",
            api_url,
        )
        return False
    except requests.exceptions.Timeout:
        logger.warning("Fish Speech API request timed out after %ds", FISH_API_TIMEOUT)
        raise  # Re-raise so caller can handle retry
    except Exception as e:
        logger.error("Fish Speech API error: %s", e)
        return False


def _restart_fish_server(
    api_url: str = FISH_API_URL,
    voice_config: VoiceConfig | None = None,
    voice_dir: Path | None = None,
) -> bool:
    """Restart Fish Speech server to reclaim GPU memory.

    This handles both Chiron-started servers (via process handle) and
    externally-started servers (by finding and killing processes on the port).

    IMPORTANT: After restart, registered anchors are lost and must be re-registered.
    Pass voice_config and voice_dir to automatically re-register the anchor.

    Args:
        api_url: The API endpoint URL.
        voice_config: Voice configuration (to re-register anchor after restart).
        voice_dir: Voice directory containing anchor files.

    Returns:
        True if server restarted successfully (and anchor re-registered if configured).
    """
    logger.info("Restarting Fish Speech server to reclaim GPU memory...")
    # Use force_kill_external=True to handle servers we didn't start
    _stop_fish_server(force_kill_external=True)
    time.sleep(3)  # Allow GPU memory to be released

    if not _ensure_fish_server_running(api_url):
        return False

    # Re-register anchor if voice config has one (server restart loses all state)
    if voice_config and voice_config.anchor and voice_dir:
        # Extract base URL from api_url (remove /v1/tts path)
        # api_url is http://127.0.0.1:8888/v1/tts, base_url should be http://127.0.0.1:8888
        base_url = api_url.rsplit("/v1/", 1)[0]
        anchor_path = voice_dir / voice_config.anchor.audio
        if anchor_path.exists():
            reference_id = f"chiron-anchor-{voice_config.anchor.seed}"
            logger.info("Re-registering anchor after restart: %s", reference_id)
            if not _register_anchor(
                anchor_path=anchor_path,
                anchor_text=voice_config.anchor.text,
                reference_id=reference_id,
                base_url=base_url,
            ):
                logger.error("Failed to re-register anchor after restart")
                return False
        else:
            logger.warning("Anchor file not found for re-registration: %s", anchor_path)

    return True


def _generate_segment_with_retry(
    segment: str,
    output_path: Path,
    voice_config: VoiceConfig,
    voice_dir: Path | None,
    api_url: str,
) -> tuple[bool, float]:
    """Generate a single segment with retry on failure.

    If the first attempt fails (likely due to GPU memory exhaustion or timeout),
    restarts the server and retries once.

    Args:
        segment: Text to synthesize.
        output_path: Where to save the audio.
        voice_config: Voice configuration (must have reference_id set).
        voice_dir: Voice directory (for re-registering anchor on restart).
        api_url: API endpoint URL.

    Returns:
        Tuple of (success, duration_seconds).
    """
    import requests  # Import here to access exception types

    start = time.time()

    # Check server health before attempting generation
    if not _is_fish_server_running(api_url):
        logger.warning("Server not responding before generation attempt - restarting")
        if not _restart_fish_server(api_url, voice_config, voice_dir):
            logger.error("Failed to restart unresponsive server")
            return False, time.time() - start

    # First attempt
    try:
        success = _call_fish_api(segment, output_path, voice_config, api_url)
        if success:
            return True, time.time() - start
        # API returned False - server responded but failed to generate
        logger.warning("Generation failed (server responded with error)")
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        logger.warning(
            "Generation timed out after %.1fs - server may be in zombie state",
            elapsed
        )
    except requests.exceptions.ConnectionError:
        logger.warning("Connection error - server may have crashed")
    except Exception as e:
        logger.warning("Segment generation failed with unexpected error: %s", type(e).__name__)

    # First attempt failed - restart server and retry
    attempt_time = time.time() - start
    logger.info(
        "First attempt failed after %.1fs, restarting server and retrying...",
        attempt_time
    )
    if not _restart_fish_server(api_url, voice_config, voice_dir):
        logger.error("Failed to restart Fish Speech server")
        return False, time.time() - start

    # Verify server is healthy after restart
    if not _is_fish_server_running(api_url):
        logger.error("Server not responding after restart")
        return False, time.time() - start

    # Retry after restart
    retry_start = time.time()
    try:
        success = _call_fish_api(segment, output_path, voice_config, api_url)
        if success:
            total_time = time.time() - start
            logger.info("Retry succeeded after %.1fs total", total_time)
        return success, time.time() - start
    except requests.exceptions.Timeout:
        elapsed = time.time() - retry_start
        logger.error("Retry also timed out after %.1fs", elapsed)
        return False, time.time() - start
    except Exception as e:
        logger.error("Retry also failed: %s", e)
        return False, time.time() - start


# Fish Speech GPU memory management constants
# With use_memory_cache: "on", reference encoding is cached by hash - minimal memory growth.
# Testing (2026-01-04) showed:
# - 100-300 chars: Reliable success (~13-50s per segment)
# - 400+ chars: Often times out (even with 300s timeout)
# - Memory growth minimal (+2MB) when caching is enabled
# Restart threshold increased since memory leak is no longer the bottleneck.
FISH_REQUESTS_BEFORE_RESTART = 10  # Only restart as safety valve, not for memory

# Optimal segment size: 300 chars (tested reliably)
# Larger segments fail or timeout due to Fish Speech internal limits, not memory.
# This aligns with Fish Speech's chunk_length parameter (100-300 range).
FISH_OPTIMAL_SEGMENT_CHARS = 300


def generate_audio_fish(
    script: str,
    output_path: Path,
    voice_config: VoiceConfig | None = None,
    voice_dir: Path | None = None,
    api_url: str = FISH_API_URL,
) -> Path | None:
    """Generate audio using Fish Speech API with anchor-based voice cloning.

    Fish Speech provides high-quality neural TTS with voice cloning.
    This function uses the anchor workflow for consistent voice quality:

    1. Ensures server is running (starts if needed)
    2. Waits for server warmup
    3. Registers anchor as server-side reference (if configured)
    4. Generates audio segments using the registered anchor
    5. Stitches segments into final output

    The Fish Speech API server will be started automatically if not running.
    Set FISH_SPEECH_DIR environment variable to specify installation path,
    or install to ~/Working/fish_ttf/fish-speech.

    See docs/fish-speech-voice-generation.md for the anchor methodology.

    Args:
        script: Text to convert to speech.
        output_path: Where to save the audio file.
        voice_config: Optional voice configuration for cloning.
        voice_dir: Directory containing voice files (anchor, references).
        api_url: Fish Speech API endpoint URL.

    Returns:
        Path to generated WAV file, or None if generation failed.
    """
    # Ensure server is running (start if necessary)
    if not _ensure_fish_server_running(api_url):
        logger.error("Fish Speech server not available")
        return None

    # Wait for server warmup before API calls
    logger.debug("Waiting %ds for server warmup...", FISH_SERVER_WARMUP_DELAY)
    time.sleep(FISH_SERVER_WARMUP_DELAY)

    voice_config = voice_config or VoiceConfig()
    output_path = output_path.with_suffix(".wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare voice for generation (register anchor if configured)
    # Extract base URL from TTS endpoint for reference registration
    base_url = api_url.rsplit("/", 2)[0]  # http://127.0.0.1:8888
    reference_id = _prepare_voice_for_generation(voice_config, voice_dir, base_url)

    if not reference_id:
        logger.error("No anchor configured - voice.yaml must have anchor section")
        return None

    # Update voice_config with the registered reference_id
    voice_config = voice_config.model_copy(update={"reference_id": reference_id})
    logger.info("Using registered anchor: %s", reference_id)

    # Segment with optimal chunk size for GPU safety
    segments = segment_for_fish(script, max_chars=FISH_OPTIMAL_SEGMENT_CHARS)
    if not segments:
        logger.warning("No segments to generate audio for")
        return None

    # Estimate total time (~7 chars/sec based on profiling)
    total_chars = sum(len(s) for s in segments)
    est_time = total_chars / 7
    num_restarts = max(0, (len(segments) - 1) // FISH_REQUESTS_BEFORE_RESTART)
    restart_overhead = num_restarts * 22  # ~22s per restart
    logger.info(
        "Generating Fish TTS audio: %d segments, ~%d chars, "
        "estimated %.1f minutes (including %d server restart(s))",
        len(segments), total_chars, (est_time + restart_overhead) / 60, num_restarts
    )

    # Generate each segment with memory management
    temp_files: list[Path] = []
    generation_start = time.time()
    requests_since_restart = 0

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            for i, segment in enumerate(segments):
                # Proactive restart before GPU memory exhaustion
                if requests_since_restart >= FISH_REQUESTS_BEFORE_RESTART:
                    logger.info(
                        "Proactive server restart after %d requests to reclaim GPU memory",
                        requests_since_restart
                    )
                    if not _restart_fish_server(api_url, voice_config, voice_dir):
                        logger.error("Failed to restart server")
                        return None
                    requests_since_restart = 0

                segment_path = temp_path / f"segment_{i:03d}.wav"
                logger.info(
                    "Generating segment %d/%d (%d chars): %s...",
                    i + 1, len(segments), len(segment), segment[:50]
                )

                success, segment_time = _generate_segment_with_retry(
                    segment=segment,
                    output_path=segment_path,
                    voice_config=voice_config,
                    voice_dir=voice_dir,
                    api_url=api_url,
                )

                if not success:
                    logger.error(
                        "Failed to generate segment %d after %.1fs (including retry)",
                        i + 1, segment_time
                    )
                    return None

                requests_since_restart += 1
                logger.info(
                    "Segment %d completed in %.1fs (request %d/%d before restart)",
                    i + 1, segment_time, requests_since_restart, FISH_REQUESTS_BEFORE_RESTART
                )
                temp_files.append(segment_path)

                # Small delay between segments
                if i < len(segments) - 1:
                    time.sleep(0.5)

            # Stitch segments together with punctuation-aware pauses
            if len(temp_files) == 1:
                # Single segment - just copy
                import shutil
                shutil.copy(temp_files[0], output_path)
            else:
                _stitch_wav_files(temp_files, output_path, segment_texts=segments)

            total_time = time.time() - generation_start
            logger.info(
                "Generated Fish TTS audio: %s (%.1f minutes)",
                output_path, total_time / 60
            )

            # Stop server to release GPU memory
            # The server tends to accumulate bad state over time, so it's better
            # to stop it after each generation session
            _stop_fish_server(force_kill_external=True)

            return output_path

    except Exception as e:
        total_time = time.time() - generation_start
        logger.error("Fish TTS generation failed after %.1fs: %s", total_time, e)
        # Clean up server on failure too
        _stop_fish_server(force_kill_external=True)
        return None


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
