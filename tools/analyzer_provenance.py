"""Read and validate the Git identity of the analyzer source tree."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


class AnalyzerProvenanceError(ValueError):
    """The analyzer Git state cannot be attributed to a clean commit."""


def analyzer_snapshot(root: Path) -> tuple[str, bool]:
    """Return the full HEAD SHA and whether tracked or unignored files are dirty."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise AnalyzerProvenanceError("cannot verify analyzer Git state") from exc
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise AnalyzerProvenanceError("analyzer Git commit is not a full SHA")
    return commit, bool(status.strip())


def require_clean_analyzer(root: Path, expected_commit: str | None = None) -> str:
    """Require a clean analyzer checkout, optionally pinned to one commit."""
    commit, dirty = analyzer_snapshot(root)
    if dirty:
        raise AnalyzerProvenanceError("analyzer worktree must be clean")
    if expected_commit is not None and commit != expected_commit:
        raise AnalyzerProvenanceError("analyzer commit changed during evaluation")
    return commit
