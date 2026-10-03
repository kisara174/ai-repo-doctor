"""Explicit source-language selection and bounded analysis scope."""
from dataclasses import asdict
from pathlib import PurePosixPath

from .model import AnalysisLimit, RepoIndex

SUPPORTED_LANGUAGES = ("python", "javascript", "typescript")


def normalize_languages(value: str) -> tuple[str, ...]:
    names = [part.strip() for part in value.split(",")]
    if not names or any(name not in SUPPORTED_LANGUAGES for name in names):
        raise ValueError("languages must be a nonempty CSV of python,javascript,typescript")
    return tuple(name for name in SUPPORTED_LANGUAGES if name in names)


def language_for_path(path: str) -> str | None:
    if path.endswith(".d.ts"):
        return None
    return {".py": "python", ".js": "javascript", ".mjs": "javascript",
            ".ts": "typescript"}.get(PurePosixPath(path).suffix)


def analysis_metadata(index: RepoIndex) -> dict:
    errors = [AnalysisLimit(row.file, row.line, "parse-error", row.message) for row in index.parse_errors]
    limits = sorted([*index.analysis_limits, *errors], key=lambda row: (row.file, row.line or 0, row.reason, row.message))
    return {
        "schema_version": 1,
        "requested_languages": list(index.analysis_languages),
        "files_by_language": {name: sum(index.file_languages.get(row.path, "python") == name
                                       for row in index.files) for name in SUPPORTED_LANGUAGES},
        "capabilities": {name: (["symbols", "imports", "context", "calls"] if name == "python"
                               else ["symbols", "esm-file-imports", "context"])
                         for name in index.analysis_languages},
        "limits": [asdict(row) for row in limits[:50]],
        "limits_omitted": max(0, len(limits) - 50),
        "scope": "static selected source languages; no runtime completeness",
    }
