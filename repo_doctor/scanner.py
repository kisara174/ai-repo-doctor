import os
import stat
import subprocess
from pathlib import Path


_GENERATED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
}


def discover_python_files(root: Path) -> tuple[list[str], str]:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        result = None

    if result is not None and result.returncode == 0:
        top = Path(os.fsdecode(result.stdout.removesuffix(b"\n"))).resolve()
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(top),
                "ls-files",
                "-co",
                "--exclude-standard",
                "-z",
            ],
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        files = set()
        for entry in listed.split(b"\0"):
            if not entry:
                continue
            candidate = top / os.fsdecode(entry)
            try:
                relative = candidate.relative_to(root)
            except ValueError:
                continue
            if relative.suffix != ".py" or any(
                part in _GENERATED_DIRS for part in relative.parts[:-1]
            ):
                continue
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, ValueError):
                continue
            path = root
            has_symlink = False
            for part in relative.parts:
                path /= part
                if path.is_symlink():
                    has_symlink = True
                    break
            if has_symlink or not stat.S_ISREG(candidate.stat().st_mode):
                continue
            files.add(relative.as_posix())
        return sorted(files), "git"

    files = []
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name
            for name in directories
            if name not in _GENERATED_DIRS
            and not (current_path / name).is_symlink()
        ]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            files.append(path.relative_to(root).as_posix())
    return sorted(set(files)), "walk"
