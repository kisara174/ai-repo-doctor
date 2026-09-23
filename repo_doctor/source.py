"""Read scanned Python source without following repository path symlinks."""

import os
import stat
import tokenize
from pathlib import Path, PurePosixPath


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
    root: Path, relative_path: str, root_identity: tuple[int, int] | None = None
) -> str:
    """Read Python source with encoding-cookie support and path containment."""
    relative = PurePosixPath(relative_path)
    parts = relative.parts
    if not parts or relative.is_absolute() or ".." in parts or "\\" in relative_path:
        raise ValueError(f"Unsafe source path: {relative_path}")
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
        encoding, _ = tokenize.detect_encoding(stream.readline)
        stream.seek(0)
        return stream.read().decode(encoding)
