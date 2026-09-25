"""Validate frozen diagnosis data and prepare bounded offline contexts."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from repo_doctor.context import build_context
from repo_doctor.diagnosis import (
    MAX_CONTEXT_LINES,
    build_diagnosis_prompts,
    validate_context_budget,
)
from repo_doctor.deepseek import MAX_REQUEST_BYTES, _serialize_request_body
from repo_doctor.index import build_index
from repo_doctor.source import read_source


class EvaluationDataError(ValueError):
    """Frozen evaluation input cannot be safely or reproducibly prepared."""


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise EvaluationDataError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationDataError(f"{label} must be nonempty text")
    return value


def _safe_source_path(value: object, label: str) -> str:
    name = _text(value, label)
    path = PurePosixPath(name)
    parts = name.split("/")
    if (
        "\\" in name
        or "\x00" in name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or path.as_posix() != name
    ):
        raise EvaluationDataError(f"{label} must be a safe repository-relative POSIX path")
    return name


def _validate_url(value: object, label: str, *, repository: bool = False) -> str:
    url = _text(value, label)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise EvaluationDataError(f"{label} must be a valid public HTTPS URL") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or (repository and parsed.hostname != "github.com")
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or not parsed.path.strip("/")
        or (repository and (len(parsed.path.strip("/").split("/")) != 2 or parsed.query or parsed.fragment))
    ):
        raise EvaluationDataError(f"{label} must be a public HTTPS URL")
    return url


def validate_manifest(data: dict) -> None:
    """Validate manifest structure and all values that do not require a checkout."""
    root = _object(data, "manifest")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        raise EvaluationDataError("manifest.schema_version must be 1")
    if root.get("dataset_id") != "diagnosis-v1":
        raise EvaluationDataError('manifest.dataset_id must be "diagnosis-v1"')
    cases = root.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvaluationDataError("manifest.cases must be a nonempty list")

    case_ids: set[str] = set()
    pairs: dict[str, list[dict]] = {}
    for item in cases:
        case = _object(item, "case")
        case_id = _text(case.get("id"), "case.id")
        if re.fullmatch(r"[A-Za-z0-9_-]+", case_id, flags=re.ASCII) is None:
            raise EvaluationDataError("case.id must contain only ASCII letters, digits, '_' or '-'")
        if case_id in case_ids:
            raise EvaluationDataError(f"duplicate case ID: {case_id}")
        case_ids.add(case_id)

        pair_id = case.get("pair_id")
        label = case.get("label")
        if not isinstance(label, str) or label not in ("bug", "fixed", "control"):
            raise EvaluationDataError(f"{case_id}.label must be bug, fixed, or control")
        issue_id = case.get("issue_id")
        if label == "control":
            if pair_id is not None or issue_id is not None:
                raise EvaluationDataError(f"{case_id}: controls must not have a pair or issue ID")
        else:
            _text(pair_id, f"{case_id}.pair_id")
            _text(issue_id, f"{case_id}.issue_id")
            pairs.setdefault(pair_id, []).append(case)

        _validate_url(case.get("repository_url"), f"{case_id}.repository_url", repository=True)
        checkout_id = _text(case.get("checkout_id"), f"{case_id}.checkout_id")
        if re.fullmatch(r"[A-Za-z0-9_-]+", checkout_id, flags=re.ASCII) is None:
            raise EvaluationDataError(f"{case_id}.checkout_id must be a safe directory name")
        commit = case.get("commit")
        if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise EvaluationDataError(f"{case_id}.commit must be a full lowercase Git SHA")

        source = _object(case.get("source"), f"{case_id}.source")
        file = _safe_source_path(source.get("file"), f"{case_id}.source.file")
        if not file.endswith(".py"):
            raise EvaluationDataError(f"{case_id}.source.file must name a Python source file")
        start = source.get("start_line")
        end = source.get("end_line")
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            raise EvaluationDataError(f"{case_id}.source needs a valid 1-based line range")
        digest = source.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise EvaluationDataError(f"{case_id}.source.sha256 must be 64 lowercase hex characters")

        symbol = _text(case.get("symbol"), f"{case_id}.symbol")
        if not symbol.startswith(file + "::") or not symbol[len(file) + 2:]:
            raise EvaluationDataError(f"{case_id}.symbol must identify a qualified symbol in {file}")
        _text(case.get("ground_truth"), f"{case_id}.ground_truth")

        references = case.get("references")
        if not isinstance(references, list) or not references:
            raise EvaluationDataError(f"{case_id}.references must be a nonempty list")
        for number, reference in enumerate(references):
            _validate_url(reference, f"{case_id}.references[{number}]")

        annotation = _object(case.get("annotation"), f"{case_id}.annotation")
        _text(annotation.get("reviewer"), f"{case_id}.annotation.reviewer")
        reviewed_at = _text(annotation.get("reviewed_at"), f"{case_id}.annotation.reviewed_at")
        try:
            parsed_date = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EvaluationDataError(f"{case_id}.annotation.reviewed_at must be ISO 8601") from exc
        if parsed_date.tzinfo is None:
            raise EvaluationDataError(f"{case_id}.annotation.reviewed_at must include a timezone")
        if annotation.get("status") != "approved":
            raise EvaluationDataError(f"{case_id}.annotation.status must be approved")

    for pair_id, members in pairs.items():
        if len(members) != 2 or {member["label"] for member in members} != {"bug", "fixed"}:
            raise EvaluationDataError(f"pair {pair_id} must have exactly one bug and one fixed case")
        bug = next(member for member in members if member["label"] == "bug")
        fixed = next(member for member in members if member["label"] == "fixed")
        if (
            bug["issue_id"] != fixed["issue_id"]
            or bug["repository_url"] != fixed["repository_url"]
        ):
            raise EvaluationDataError(f"pair {pair_id} must share repository and issue ID")


def _analyzer_commit() -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvaluationDataError("cannot determine analyzer Git commit") from exc
    commit = completed.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise EvaluationDataError("analyzer Git commit is not a full SHA")
    return commit


def _git(checkout: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(checkout), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvaluationDataError("target checkout failed a read-only Git check") from exc
    return completed.stdout.strip()


def _verified_checkout(case: dict, repos_root: Path) -> Path:
    checkout_id = case["checkout_id"]
    base = Path(repos_root).resolve(strict=True)
    candidate = base / checkout_id
    if candidate.is_symlink() or not candidate.is_dir():
        raise EvaluationDataError(f"{case['id']}: checkout is absent or is a symlink")
    try:
        checkout = candidate.resolve(strict=True)
        checkout.relative_to(base)
    except (OSError, ValueError) as exc:
        raise EvaluationDataError(f"{case['id']}: checkout escapes --repos-root") from exc
    top_level = Path(_git(checkout, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if top_level != checkout:
        raise EvaluationDataError(f"{case['id']}: checkout directory is not the Git root")
    commit = _git(checkout, "rev-parse", "--verify", "HEAD")
    if commit != case["commit"]:
        raise EvaluationDataError(f"{case['id']}: checkout commit does not match manifest")
    if _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        raise EvaluationDataError(f"{case['id']}: target checkout must be clean")
    return checkout


def _source_fingerprint(checkout: Path, case: dict) -> str:
    source = case["source"]
    try:
        text = read_source(checkout, source["file"])
    except (OSError, ValueError) as exc:
        raise EvaluationDataError(f"{case['id']}: cannot safely read source file") from exc
    lines = text.splitlines()
    start, end = source["start_line"], source["end_line"]
    if end > len(lines):
        raise EvaluationDataError(f"{case['id']}: source fingerprint line range is outside the file")
    selected = "\n".join(lines[start - 1:end])
    actual = hashlib.sha256(selected.encode("utf-8")).hexdigest()
    if actual != source["sha256"]:
        raise EvaluationDataError(f"{case['id']}: source fingerprint does not match checkout")
    return actual


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_cases(
    manifest: dict,
    repos_root: Path,
    model: str,
    max_lines: int,
    *,
    manifest_sha256: str | None = None,
) -> dict:
    """Build request-safe context and a reproducible plan without writing or networking."""
    validate_manifest(manifest)
    if not isinstance(model, str) or not model.strip():
        raise EvaluationDataError("model must be nonempty text")
    if type(max_lines) is not int or not 1 <= max_lines <= MAX_CONTEXT_LINES:
        raise EvaluationDataError(f"max_lines must be between 1 and {MAX_CONTEXT_LINES}")
    if manifest_sha256 is None:
        manifest_sha256 = _canonical_hash(manifest)
    if not isinstance(manifest_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None:
        raise EvaluationDataError("manifest_sha256 must be 64 lowercase hex characters")

    analyzer_commit = _analyzer_commit()
    contexts: dict[str, dict] = {}
    prepared_cases = []
    checkout_cache: dict[str, tuple[str, Path]] = {}

    for case in manifest["cases"]:
        checkout_id = case["checkout_id"]
        previous = checkout_cache.get(checkout_id)
        if previous is not None and previous[0] != case["commit"]:
            raise EvaluationDataError(f"{case['id']}: checkout ID is reused for another commit")
        if previous is None:
            checkout = _verified_checkout(case, repos_root)
            checkout_cache[checkout_id] = (case["commit"], checkout)
        else:
            checkout = previous[1]

        _source_fingerprint(checkout, case)
        try:
            index = build_index(checkout)
            if case["symbol"] in index.ambiguous_symbols:
                raise EvaluationDataError(f"{case['id']}: Ambiguous symbol: {case['symbol']}")
            if case["symbol"] not in index.symbols:
                raise EvaluationDataError(f"{case['id']}: Unknown symbol: {case['symbol']}")
            detailed_context = build_context(index, case["symbol"], max_lines)
            source_lines, source_bytes = validate_context_budget(detailed_context)
            system_prompt, user_prompt = build_diagnosis_prompts(detailed_context)
            context = json.loads(user_prompt)
        except EvaluationDataError:
            raise
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EvaluationDataError(f"{case['id']}: cannot build bounded context") from exc

        if set(context) != {"symbol", "blocks", "call_evidence"}:
            raise EvaluationDataError(f"{case['id']}: prompt context contains unexpected fields")
        if len(_serialize_request_body(system_prompt, user_prompt, model)) > MAX_REQUEST_BYTES:
            raise EvaluationDataError(f"{case['id']}: serialized request exceeds 256 KiB limit")
        context_hash = _canonical_hash(context)
        request_shape = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "requested_model": model,
            "max_tokens": 4096,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        prepared_cases.append({
            "id": case["id"],
            "repository_url": case["repository_url"],
            "commit": case["commit"],
            "symbol": case["symbol"],
            "context_file": f"{case['id']}.json",
            "context_sha256": context_hash,
            "request_sha256": _canonical_hash(request_shape),
            "source_lines": source_lines,
            "source_bytes": source_bytes,
        })
        contexts[case["id"]] = context

    plan = {
        "schema_version": 1,
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": manifest_sha256,
        "analyzer_commit": analyzer_commit,
        "python_version": platform.python_version(),
        "requested_model": model,
        "max_lines": max_lines,
        "cases": prepared_cases,
    }
    return {"plan": plan, "contexts": contexts}
