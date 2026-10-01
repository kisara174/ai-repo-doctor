"""Export the packaged Codex skill without changing client configuration."""

from importlib.resources import files
from pathlib import Path


def export_skill(destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise ValueError('Skill destination already exists; choose a new directory')
    content = files('repo_doctor').joinpath('resources/skill/SKILL.md').read_text(encoding='utf-8')
    destination.mkdir(parents=True)
    (destination / 'SKILL.md').write_text(content, encoding='utf-8')
