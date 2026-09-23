"""Check whether proposed findings cite exact, current repository source."""

from pathlib import PurePosixPath

from .model import RepoIndex
from .source import read_source


_REQUIRED_TEXT = ("title", "category", "reasoning", "impact", "suggested_fix")


def _unsafe_spelling(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return not parts or PurePosixPath(path).is_absolute() or "\\" in path or any(part in {"..", "."} for part in parts)


def _validate_evidence(index: RepoIndex, item: object, number: int, known_files: set[str]) -> list[str]:
    prefix = f"evidence[{number}]"
    if not isinstance(item, dict):
        return [f"{prefix} must be an object"]
    reasons: list[str] = []
    path = item.get("file")
    if not isinstance(path, str) or _unsafe_spelling(path):
        return [f"{prefix} has an Unsafe evidence path"]
    if path not in known_files:
        return [f"{prefix} file is not in scanned Python files: {path}"]

    start = item.get("start_line")
    end = item.get("end_line")
    if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
        reasons.append(f"{prefix} line range must contain integers")
    else:
        try:
            lines = read_source(index.root, path, index.root_identity).splitlines()
        except ValueError:
            return [f"{prefix} has an Unsafe evidence path"]
        except (OSError, SyntaxError, UnicodeError) as exc:
            return [f"{prefix} source cannot be read: {exc}"]
        if not (1 <= start <= end <= len(lines)):
            reasons.append(f"{prefix} line range is outside the current file")
        else:
            quote = item.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                reasons.append(f"{prefix} quote must be nonempty text")
            elif quote not in "\n".join(lines[start - 1 : end]):
                reasons.append(f"{prefix} quote does not match the source lines")
            symbol_id = item.get("symbol")
            if symbol_id is not None:
                symbol = index.symbols.get(symbol_id) if isinstance(symbol_id, str) else None
                if symbol is None:
                    reasons.append(f"{prefix} symbol does not exist in the index")
                elif symbol.file != path or symbol.start_line > end or symbol.end_line < start:
                    reasons.append(f"{prefix} lines do not overlap the cited symbol")
    return reasons


def validate_findings(index: RepoIndex, payload: object) -> dict:
    """Separate structurally grounded findings from rejected proposals."""
    findings = payload if isinstance(payload, list) else [payload]
    known_files = {file.path for file in index.files}
    accepted: list[dict] = []
    rejected: list[dict] = []
    for position, finding in enumerate(findings):
        reasons: list[str] = []
        if not isinstance(finding, dict):
            reasons.append("finding must be an object")
        else:
            for field in _REQUIRED_TEXT:
                value = finding.get(field)
                if not isinstance(value, str) or not value.strip():
                    reasons.append(f"{field} must be nonempty text")
            confidence = finding.get("confidence")
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1
            ):
                reasons.append("confidence must be a number from 0 to 1")
            evidence = finding.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                reasons.append("evidence must be a nonempty list")
            else:
                for number, item in enumerate(evidence):
                    reasons.extend(_validate_evidence(index, item, number, known_files))
        entry = {"index": position, "finding": finding}
        if reasons:
            rejected.append({**entry, "reasons": reasons})
        else:
            accepted.append(entry)
    return {"schema_version": 1, "accepted": accepted, "rejected": rejected}
