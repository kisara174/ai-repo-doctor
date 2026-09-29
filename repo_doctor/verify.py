"""Run only a user-supplied regression argv in the selected repository."""

import os
import signal
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


MAX_OUTPUT_BYTES = 16 * 1024
MAX_TIMEOUT_SECONDS = 300
_ENV_ALLOWLIST = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "VIRTUAL_ENV", "SYSTEMROOT")


def _minimal_environment() -> dict[str, str]:
    return {name: os.environ[name] for name in _ENV_ALLOWLIST if name in os.environ}


def run_verification(root: Path, argv: list[str], *, timeout: int = 120) -> dict:
    if not argv or any(not isinstance(item, str) or not item or "\0" in item for item in argv):
        raise ValueError("verify requires a nonempty command argv after --")
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"--timeout must be from 1 through {MAX_TIMEOUT_SECONDS} seconds")
    output = bytearray()
    truncated = False
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    start = time.monotonic()
    cache_dir = tempfile.TemporaryDirectory(prefix="repo-doctor-pycache-")
    environment = _minimal_environment()
    environment["PYTHONPYCACHEPREFIX"] = cache_dir.name
    try:
        process = subprocess.Popen(
            argv, cwd=root, env=environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            shell=False, start_new_session=True,
        )
    except OSError:
        cache_dir.cleanup()
        return {
            "at": started_at, "status": "command_error", "exit_code": None,
            "duration_seconds": round(time.monotonic() - start, 3),
            "argv": list(argv), "output": "Could not start the command.", "output_truncated": False,
        }

    def drain() -> None:
        nonlocal truncated
        assert process.stdout is not None
        while True:
            try:
                chunk = process.stdout.read(4096)
            except OSError:
                break
            if not chunk:
                break
            remaining = MAX_OUTPUT_BYTES - len(output)
            if remaining > 0:
                output.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = False
    def kill_group() -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group()
        exit_code = process.wait()
    reader.join(timeout=max(0, timeout - (time.monotonic() - start)))
    if reader.is_alive():
        timed_out = True
        kill_group()
        reader.join(timeout=2)
    if process.stdout is not None:
        process.stdout.close()
    cache_dir.cleanup()
    decoded = bytes(output).decode("utf-8", errors="replace")
    encoded = decoded.encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        truncated = True
    safe_output = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore")
    return {
        "at": started_at,
        "status": "timeout" if timed_out else "passed" if exit_code == 0 else "failed",
        "exit_code": exit_code,
        "duration_seconds": round(time.monotonic() - start, 3),
        "argv": list(argv),
        "output": safe_output,
        "output_truncated": truncated,
    }
