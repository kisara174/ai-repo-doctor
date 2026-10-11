"""Read scanned source without following repository path symlinks."""

import hashlib
import io
import os
import stat
import tokenize
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from .limits import AnalysisBudget, AnalysisLimitError

if TYPE_CHECKING:
    from .model import RepoIndex


def split_source_lines(source: str, *, language: str = "python") -> list[str]:
    """Match parser line coordinates without splitting on source control characters."""
    # Python's AST accepts universal newlines. The JS/TS byte-offset backend
    # counts LF only; a bare CR or Unicode separator must stay within its row.
    source = source.replace("\r\n", "\n")
    if language == "python":
        source = source.replace("\r", "\n")
    if not source:
        return []
    lines = source.split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def _open_no_follow(
    root: Path, parts: tuple[str, ...], root_identity: tuple[int, int] | None
) -> int:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd = os.open(root.anchor, directory_flags)
    try:
        for part in root.parts[1:]:
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        if root_identity is not None:
            current = os.fstat(directory_fd)
            if (current.st_dev, current.st_ino) != root_identity:
                raise ValueError("repository directory changed after scanning")
        for part in parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)


def _open_checked_fallback(
    root: Path, parts: tuple[str, ...], root_identity: tuple[int, int] | None
) -> int:
    ancestor = Path(root.anchor)
    for part in root.parts[1:]:
        ancestor /= part
        if ancestor.is_symlink():
            raise ValueError("repository path contains a symlink")
    if root_identity is not None:
        current = root.stat(follow_symlinks=False)
        if (current.st_dev, current.st_ino) != root_identity:
            raise ValueError("repository directory changed after scanning")
    candidate = root
    for part in parts:
        candidate /= part
        if candidate.is_symlink():
            raise ValueError("source path contains a symlink")
    candidate.resolve(strict=True).relative_to(root)
    return os.open(candidate, os.O_RDONLY | getattr(os, "O_BINARY", 0))


def read_source(
    root: Path, relative_path: str, root_identity: tuple[int, int] | None = None,
    *, language: str = "python", budget: AnalysisBudget | None = None,
    source_digests: dict[str, str] | None = None,
) -> str:
    """Read selected source with path containment; Python retains encoding cookies."""
    if language not in ("python", "javascript", "typescript"):
        raise ValueError(f"Unsupported source language: {language}")
    relative = PurePosixPath(relative_path)
    parts = relative.parts
    if not parts or relative.is_absolute() or ".." in parts or "\\" in relative_path:
        raise ValueError(f"Unsafe source path: {relative_path}")
    budget = budget if budget is not None else AnalysisBudget()
    budget.checkpoint(relative_path)
    root = Path(root).absolute()
    try:
        if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"):
            descriptor = _open_no_follow(root, parts, root_identity)
        else:
            descriptor = _open_checked_fallback(root, parts, root_identity)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unsafe source path: {relative_path}") from exc
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"Unsafe source path: {relative_path}")
        raw = stream.read(budget.read_size())
        budget.record_read(len(raw), relative_path)
        budget.checkpoint(relative_path)
        if source_digests is not None:
            source_digests[relative_path] = hashlib.sha256(raw).hexdigest()
        encoding = "utf-8-sig"
        if language == "python":
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding)


class SourceConsistencyError(ValueError):
    """Parsed source identity changed; callers must not publish stale evidence."""


def read_index_source(index: "RepoIndex", relative_path: str) -> str:
    digests: dict[str, str] = {}
    expected = index.source_digests.get(relative_path)
    captured = relative_path in index.source_digests
    try:
        source = read_source(index.root, relative_path, index.root_identity,
                             language=index.file_languages.get(relative_path, 'python'),
                             budget=index.budget, source_digests=digests)
    except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
        if isinstance(exc, AnalysisLimitError):
            raise
        if captured and digests.get(relative_path) != expected:
            raise SourceConsistencyError(f'source changed after parsing: {relative_path} ({exc}); collect again') from exc
        raise
    if captured and digests.get(relative_path) != expected:
        raise SourceConsistencyError(f'source changed after parsing: {relative_path}; collect again')
    return source


def validate_index_paths(index: "RepoIndex") -> None:
    if index.discovered_paths is None:
        return  # Compatibility for manually constructed, non-scanned records.
    from .scanner import discover_files
    from .languages import language_for_path
    paths, _ = discover_files(index.root, budget=index.budget)
    def relevant(path):
        # ESM ambiguity also depends on extensionless, .json/.node and package
        # configuration paths; the resolver consumes the full discovery set.
        return index.analysis_languages != ('python',) or language_for_path(path) in index.analysis_languages
    if {p for p in paths if relevant(p)} != {p for p in index.discovered_paths if relevant(p)}:
        raise SourceConsistencyError('source changed after scanning: source candidate set; collect again')


def validate_index_sources(index: "RepoIndex") -> None:
    for path in index.source_digests:
        try:
            read_index_source(index, path)
        except SourceConsistencyError:
            raise
        except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
            if isinstance(exc, AnalysisLimitError):
                raise
            # Stable unreadable/undecodable input remains a coverage limitation.
    validate_index_paths(index)
    index.budget.checkpoint('parsed source consistency')
