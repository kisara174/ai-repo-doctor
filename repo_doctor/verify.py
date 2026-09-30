"""Run only a user-supplied regression argv in the selected repository."""

import os
import selectors
import signal
import subprocess
import tempfile
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

    timed_out = False

    def kill_group() -> None:
        # Reap an exited leader before signalling its remaining descendants.
        # macOS reports EPERM for a group containing only an unreaped zombie.
        process.poll()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    assert process.stdout is not None
    deadline = start + timeout
    try:
        # Pipe EOF can be delayed by a descendant even after the parent exits.
        # Read only ready bytes and apply one deadline to output and process exit.
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                time_left = deadline - time.monotonic()
                if time_left <= 0:
                    timed_out = True
                    break
                for key, _ in selector.select(time_left):
                    try:
                        chunk = os.read(key.fd, 4096)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        break
                    remaining = MAX_OUTPUT_BYTES - len(output)
                    if remaining > 0:
                        output.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        truncated = True
        if not timed_out:
            try:
                exit_code = process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
        if timed_out:
            kill_group()
            exit_code = process.wait()
    finally:
        if process.poll() is None:
            kill_group()
            process.wait()
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
