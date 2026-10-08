"""Export the packaged Codex skill without changing client configuration."""

from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess

from ._version import __version__


def _verified_cli(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError('Skill CLI path must be absolute')
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError('Skill CLI must be an existing executable file') from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError('Skill CLI must be an existing executable file')
    env = {key: value for key, value in os.environ.items()
           if key not in {'PYTHONPATH', 'PYTHONHOME'}}
    try:
        result = subprocess.run([str(resolved), '--version'], cwd=resolved.parent,
                                env=env, capture_output=True, text=True,
                                encoding='utf-8', timeout=5)
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Could not validate Skill CLI version; check the installation') from exc
    if result.returncode != 0 or result.stdout.strip() != f'repo-doctor {__version__}':
        raise ValueError(f'Skill CLI version must match exporting package {__version__}')
    return resolved


def export_skill(destination: Path, *, cli_path: Path | None = None) -> None:
    if destination.exists() or destination.is_symlink():
        raise ValueError('Skill destination already exists; choose a new directory')
    content = files('repo_doctor').joinpath('resources/skill/SKILL.md').read_text(encoding='utf-8')
    binding = None
    if cli_path is not None:
        binding = {'schema_version': 1, 'cli': str(_verified_cli(cli_path)), 'version': __version__}
    destination.mkdir(parents=True)
    created = []
    artifacts = {'SKILL.md': content}
    if binding is not None:
        artifacts['installation.json'] = json.dumps(binding, ensure_ascii=False, indent=2) + '\n'
    try:
        for name, text in artifacts.items():
            path = destination / name
            with path.open('x', encoding='utf-8') as stream:
                created.append(path)
                stream.write(text)
    except (OSError, UnicodeError):
        # Only remove files created by this export; other entries must survive.
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        try:
            destination.rmdir()
        except OSError:
            pass
        raise
