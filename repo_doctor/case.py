"""Persistent, source-backed investigation cases."""

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ._version import __version__
from .architecture import build_architecture_summary
from .context import build_impact
from .leads import build_review_leads
from .model import RepoIndex
from .source import read_source


SCHEMA_VERSION = 1
TOOL_VERSION = __version__
MAX_CASE_BYTES = 8 * 1024 * 1024


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def source_fingerprint(index: RepoIndex) -> str:
    """Hash the scanned Python paths and source, including local worktree edits."""
    digest = hashlib.sha256()
    for item in sorted(index.files, key=lambda record: record.path):
        digest.update(item.path.encode("utf-8"))
        digest.update(b"\0")
        try:
            content = read_source(index.root, item.path, index.root_identity,
                                  language=index.file_languages.get(item.path, "python"))
        except (OSError, ValueError, UnicodeError, SyntaxError):
            content = "<unreadable>"
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and len(value) == 40 else None


def _static_issues(index: RepoIndex) -> list[dict]:
    issues = []
    for error in sorted(index.parse_errors, key=lambda item: (item.file, item.line)):
        issues.append({
            "id": f"S-{len(issues) + 1:03d}",
            "origin": "static",
            "title": f"Python parse error in {error.file}:{error.line}",
            "category": "parse_error",
            "evidence_status": "static_fact",
            "evidence": [{"file": error.file, "start_line": error.line, "end_line": error.line,
                          "message": error.message}],
            "reasoning": "The local Python parser could not parse this file; analysis of it is incomplete.",
            "impact": "Symbols and relationships in this file may be missing from the scan.",
            "suggested_fix": "Inspect the syntax and rerun a new scan after editing.",
            "human_status": "unreviewed",
            "human_history": [],
            "verification": [],
        })
    for component in sorted(index.import_cycles):
        edges = [
            {"file": edge.source, "start_line": edge.line, "end_line": edge.line,
             "message": f"imports {edge.target}"}
            for edge in index.import_edges
            if edge.source in component and edge.target in component
        ]
        issues.append({
            "id": f"S-{len(issues) + 1:03d}",
            "origin": "static",
            "title": "Local import cycle: " + " ↔ ".join(component),
            "category": "import_cycle",
            "evidence_status": "static_fact",
            "evidence": edges,
            "reasoning": "The local import graph contains this cycle; this is an observation, not proof of a defect.",
            "impact": "Review initialization order if runtime imports behave unexpectedly.",
            "suggested_fix": "Review the participating imports before deciding whether a change is needed.",
            "human_status": "unreviewed",
            "human_history": [],
            "verification": [],
        })
    return issues


def create_case(index: RepoIndex, directory: Path) -> dict:
    if not index.files:
        raise ValueError("No Python files found; Git ignore rules may exclude the selected path")
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("case directory is a symlink")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise ValueError("case directory already exists or is not empty")
    else:
        directory.mkdir(mode=0o700, parents=True)
    os.chmod(directory, 0o700)
    symbols = list(index.symbols.values())
    static_issues = _static_issues(index)
    case = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "created_at": timestamp(),
        "updated_at": timestamp(),
        "repository": {
            "root": str(index.root),
            "revision": _revision(index.root),
            "source_fingerprint": source_fingerprint(index),
            "scan_mode": index.scan_mode,
        },
        "scan": {
            "stats": {
                "python_files": len(index.files),
                "python_lines": sum(item.lines for item in index.files),
                "classes": sum(item.kind == "class" for item in symbols),
                "functions": sum(item.kind == "function" for item in symbols),
                "methods": sum(item.kind == "method" for item in symbols),
                "resolved_calls": len(index.call_edges),
                "unresolved_calls": len(index.calls) - len(index.call_edges),
            },
            "parse_errors": [asdict(item) for item in index.parse_errors],
            "import_cycles": index.import_cycles,
            "review_leads": build_review_leads(index, static_issues),
            "architecture": build_architecture_summary(index),
        },
        "target": None,
        "reproductions": [],
        "previews": [],
        "diagnoses": [],
        "issues": static_issues,
    }
    save_case(directory, case)
    return case


def set_target(case: dict, index: RepoIndex, symbol: str) -> None:
    if str(index.root) != case["repository"]["root"]:
        raise ValueError("repository does not match case")
    case["target"] = {
        "symbol": symbol,
        "impact": build_impact(index, symbol),
        "source_fingerprint": source_fingerprint(index),
        "selected_at": timestamp(),
    }


def _checked_directory(directory: Path) -> Path:
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("case directory is missing or is a symlink")
    for name in ("case.json", "report.md"):
        if (directory / name).is_symlink():
            raise ValueError(f"{name} is a symlink")
    return directory


def _atomic_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_case(directory: Path, case: dict) -> None:
    from .report import render_report

    directory = _checked_directory(directory)
    candidate = {**case, "updated_at": timestamp()}
    _validate_case(candidate)
    case_text = json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    report_text = render_report(candidate)
    if len(case_text.encode("utf-8")) > MAX_CASE_BYTES:
        raise ValueError("case.json exceeds 8 MiB; create a new case for further findings")
    _atomic_write(directory / "report.md", report_text)
    _atomic_write(directory / "case.json", case_text)
    case["updated_at"] = candidate["updated_at"]


def load_case(directory: Path) -> dict:
    directory = _checked_directory(directory)
    with (directory / "case.json").open("rb") as stream:
        data = stream.read(MAX_CASE_BYTES + 1)
    if len(data) > MAX_CASE_BYTES:
        raise ValueError("case.json exceeds 8 MiB")
    return _validate_case(json.loads(data.decode("utf-8")))


def _validate_case(case: object) -> dict:
    """Check the shared readable-case contract without changing its data."""
    if not isinstance(case, dict) or case.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported case schema")
    repo = case.get("repository")
    scan = case.get("scan")
    if (
        not isinstance(repo, dict)
        or not isinstance(repo.get("root"), str)
        or not Path(repo["root"]).is_absolute()
        or not isinstance(repo.get("source_fingerprint"), str)
        or not isinstance(scan, dict)
        or not isinstance(scan.get("stats"), dict)
        or not isinstance(scan.get("parse_errors"), list)
        or not isinstance(scan.get("import_cycles"), list)
        or ("review_leads" in scan and not isinstance(scan["review_leads"], list))
        or ("architecture" in scan and not isinstance(scan["architecture"], dict))
        or not isinstance(case.get("issues"), list)
        or not isinstance(case.get("diagnoses"), list)
        or not isinstance(case.get("previews"), list)
        or not isinstance(case.get("reproductions", []), list)
    ):
        raise ValueError("invalid case.json structure")
    try:
        from .report import render_report
        render_report(case)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("invalid case.json structure") from exc
    return case


def require_issue(case: dict, issue_id: str) -> dict:
    for issue in case["issues"]:
        if issue.get("id") == issue_id:
            return issue
    raise ValueError(f"Unknown issue: {issue_id}")


def record_reproduction(case: dict, result: dict) -> dict:
    runs = case.setdefault("reproductions", [])
    record = {"id": f"R-{len(runs) + 1:03d}", **result}
    runs.append(record)
    return record


def require_reproduction(case: dict, reproduction_id: str, current_fingerprint: str) -> dict:
    runs = case.get("reproductions", [])
    record = next((item for item in runs if item.get("id") == reproduction_id), None)
    if record is None:
        raise ValueError(f"Unknown reproduction: {reproduction_id}")
    if record.get("status") != "failed":
        raise ValueError("reproduction must be a failed command")
    if record.get("output_truncated"):
        raise ValueError("reproduction output was truncated; rerun a narrower command")
    if record.get("source_fingerprint") != record.get("source_fingerprint_after"):
        raise ValueError("reproduction changed Python source during execution")
    if record.get("source_fingerprint") != current_fingerprint:
        raise ValueError("Python source changed since reproduction; rerun reproduce")
    if next((item for item in reversed(runs) if item.get("argv") == record.get("argv")), None) is not record:
        raise ValueError("a newer run of this command supersedes the reproduction")
    return record


def update_issue(case: dict, issue_id: str, status: str, note: str, *, related_test: bool = False,
                 actor: str = 'human') -> dict:
    if not note.strip():
        raise ValueError("--note is required when changing issue status")
    issue = require_issue(case, issue_id)
    if status not in {"confirmed", "rejected", "resolved"}:
        raise ValueError("invalid issue status")
    if actor not in {'human', 'codex'}:
        raise ValueError('invalid review actor')
    review = {
        "at": timestamp(), "status": status, "note": note.strip(), "related_test": related_test,
        "actor": actor,
    }
    if related_test:
        history = issue.get("verification", [])
        argv = history[-1].get("argv") if history else None
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            raise ValueError("--related-test requires a recorded regression command")
        review["related_test_argv"] = list(argv)
    issue["human_status"] = status
    issue["human_history"].append(review)
    return issue


def record_import(case: dict, index: RepoIndex, context: dict, report: dict,
                  snapshot_sha256: str, *, reproduction_id: str | None = None) -> dict:
    """Reuse issue construction, recording an offline producer rather than a cloud call."""
    attempt = record_diagnosis(case, index, context, '', '', '', report,
                               reproduction_id=reproduction_id)
    case['diagnoses'].pop()
    for key in ('request_sha256', 'response_format', 'model'):
        attempt.pop(key)
    attempt.update(producer='codex', snapshot_sha256=snapshot_sha256)
    for issue_id in attempt['accepted_issue_ids']:
        require_issue(case, issue_id)['producer'] = 'codex'
    case.setdefault('imports', []).append(attempt)
    return attempt


def record_diagnosis(
    case: dict, index: RepoIndex, context: dict, request_sha256: str,
    response_format: str, model: str, report: dict, *, reproduction_id: str | None = None,
) -> dict:
    set_target(case, index, context["symbol"])
    reproduction = (
        require_reproduction(case, reproduction_id, source_fingerprint(index))
        if reproduction_id is not None else None
    )
    next_id = 1 + max(
        (int(issue["id"][2:]) for issue in case["issues"] if issue["id"].startswith("A-")),
        default=0,
    )
    accepted_ids = []
    for entry in report["accepted"]:
        finding = entry["finding"]
        issue_id = f"A-{next_id:03d}"
        next_id += 1
        issue = {
            "id": issue_id,
            "origin": "ai",
            "title": finding["title"],
            "category": finding["category"],
            "confidence": finding["confidence"],
            "evidence_status": "quote_verified",
            "evidence": finding["evidence"],
            "reasoning": finding["reasoning"],
            "impact": finding["impact"],
            "suggested_fix": finding["suggested_fix"],
            "finding": finding,
            "human_status": "unreviewed",
            "human_history": [],
            "verification": [],
        }
        if reproduction is not None:
            issue["reproduction_id"] = reproduction_id
            issue["verification"].append({
                key: reproduction[key] for key in (
                    "at", "status", "exit_code", "duration_seconds", "argv",
                    "source_fingerprint", "source_fingerprint_after",
                )
            } | {"phase": "before", "reproduction_id": reproduction_id})
        case["issues"].append(issue)
        accepted_ids.append(issue_id)
    rejected = [
        {
            "title": entry["finding"].get("title", "(untitled)")
            if isinstance(entry["finding"], dict) else "(invalid finding)",
            "reasons": entry["reasons"],
        }
        for entry in report["rejected"]
    ]
    status = "partial" if accepted_ids and rejected else (
        "accepted" if accepted_ids else "rejected" if rejected else "empty"
    )
    attempt = {
        "at": timestamp(),
        "status": status,
        "target_symbol": context["symbol"],
        "context_sha256": hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "request_sha256": request_sha256,
        "response_format": response_format,
        "model": model,
        "accepted_issue_ids": accepted_ids,
        "rejected": rejected,
    }
    if reproduction_id is not None:
        attempt["reproduction_id"] = reproduction_id
    case["diagnoses"].append(attempt)
    return attempt


def record_preview(
    case: dict, index: RepoIndex, context: dict, request_sha256: str,
    response_format: str, model: str, line_count: int, byte_count: int,
    *, reproduction_id: str | None = None,
) -> None:
    set_target(case, index, context["symbol"])
    preview = {
        "at": timestamp(), "target_symbol": context["symbol"],
        "context_sha256": hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "request_sha256": request_sha256, "response_format": response_format,
        "model": model, "source_lines": line_count, "source_bytes": byte_count,
    }
    if reproduction_id is not None:
        preview["reproduction_id"] = reproduction_id
    case["previews"].append(preview)


def record_diagnosis_failure(
    case: dict, index: RepoIndex, context: dict, request_sha256: str,
    response_format: str, model: str, status: str, category: str,
    *, reproduction_id: str | None = None,
) -> None:
    set_target(case, index, context["symbol"])
    attempt = {
        "at": timestamp(),
        "status": status,
        "target_symbol": context["symbol"],
        "context_sha256": hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "request_sha256": request_sha256,
        "response_format": response_format,
        "model": model,
        "accepted_issue_ids": [],
        "rejected": [],
        "error_category": category,
    }
    if reproduction_id is not None:
        attempt["reproduction_id"] = reproduction_id
    case["diagnoses"].append(attempt)
