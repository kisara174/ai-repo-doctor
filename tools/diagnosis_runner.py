"""Run explicitly authorized, sequential diagnosis requests against frozen contexts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from repo_doctor.deepseek import DEEPSEEK_ERROR_CODES, DeepSeekError, DeepSeekResult
from repo_doctor.context import build_context
from repo_doctor.diagnosis import (
    build_diagnosis_prompts,
    validate_context_budget,
    validate_diagnosis_payload,
)
from repo_doctor.index import build_index
from .diagnosis_data import (
    EvaluationDataError,
    _canonical_hash,
    _source_fingerprint,
    _verified_checkout,
    validate_manifest,
)


def _analyzer_snapshot() -> tuple[str, bool]:
    root = Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.strip())
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvaluationDataError("cannot verify analyzer Git state") from exc
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise EvaluationDataError("analyzer Git commit is not a full SHA")
    return commit, dirty


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_usage(value: object) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {key: None for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    result = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        token_value = value.get(key)
        result[key] = token_value if type(token_value) is int and token_value >= 0 else None
    return result


def _client_error_details(error: Exception) -> tuple[str, str, int | None]:
    code = "unknown"
    http_status = None
    if isinstance(error, DeepSeekError):
        candidate_code = getattr(error, "code", None)
        if isinstance(candidate_code, str) and candidate_code in DEEPSEEK_ERROR_CODES:
            code = candidate_code
        candidate_status = getattr(error, "http_status", None)
        if code == "http" and type(candidate_status) is int and 100 <= candidate_status <= 599:
            http_status = candidate_status
        elif code == "http":
            code = "unknown"
    status = "invalid_response" if code == "invalid_response" else "provider_error"
    return status, code, http_status


def _write_json_atomic(path: Path, value: dict) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.tmp-",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        raise EvaluationDataError("cannot atomically write run record") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _validate_plan_and_contexts(
    plan: dict,
    contexts: dict[str, dict],
    manifest: dict,
    repos_root: Path,
    manifest_sha256: str,
) -> tuple[list[tuple[dict, dict, object, str, str]], str]:
    validate_manifest(manifest)
    if not isinstance(plan, dict) or type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
        raise EvaluationDataError("plan.schema_version must be 1")
    if plan.get("dataset_id") != manifest["dataset_id"]:
        raise EvaluationDataError("plan dataset does not match manifest")
    if plan.get("manifest_sha256") != manifest_sha256:
        raise EvaluationDataError("plan manifest SHA-256 does not match manifest bytes")
    if not isinstance(manifest_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None:
        raise EvaluationDataError("manifest SHA-256 is invalid")
    model = plan.get("requested_model")
    if not isinstance(model, str) or not model.strip():
        raise EvaluationDataError("plan requested_model must be nonempty")
    max_lines = plan.get("max_lines")
    if type(max_lines) is not int or not 1 <= max_lines <= 120:
        raise EvaluationDataError("plan max_lines is outside the supported limit")

    manifest_cases = manifest["cases"]
    plan_cases = plan.get("cases")
    if not isinstance(plan_cases, list) or len(plan_cases) != len(manifest_cases):
        raise EvaluationDataError("plan case list does not match manifest")
    case_ids = {case["id"] for case in manifest_cases}
    if not isinstance(contexts, dict) or set(contexts) != case_ids:
        raise EvaluationDataError("prepared contexts do not match manifest case IDs")

    analyzer_commit, dirty = _analyzer_snapshot()
    if dirty or plan.get("analyzer_commit") != analyzer_commit:
        raise EvaluationDataError("analyzer must be clean at the prepared commit")

    case_state: list[tuple[dict, dict, object, str, str]] = []
    index_cache: dict[str, tuple[str, Path, object]] = {}
    for manifest_case, plan_case_value in zip(manifest_cases, plan_cases, strict=True):
        case_id = manifest_case["id"]
        if not isinstance(plan_case_value, dict) or plan_case_value.get("id") != case_id:
            raise EvaluationDataError("plan cases must preserve manifest order and IDs")
        plan_case = plan_case_value
        for field, expected in (
            ("repository_url", manifest_case["repository_url"]),
            ("commit", manifest_case["commit"]),
            ("symbol", manifest_case["symbol"]),
            ("context_file", f"{case_id}.json"),
        ):
            if plan_case.get(field) != expected:
                raise EvaluationDataError(f"{case_id}: prepared plan {field} changed")

        context = contexts[case_id]
        if not isinstance(context, dict) or set(context) != {"symbol", "blocks", "call_evidence"}:
            raise EvaluationDataError(f"{case_id}: context has fields outside the request allowlist")
        if context["symbol"] != manifest_case["symbol"]:
            raise EvaluationDataError(f"{case_id}: context symbol differs from manifest")
        line_count, byte_count = validate_context_budget(context)
        if type(plan_case.get("source_lines")) is not int or plan_case["source_lines"] != line_count:
            raise EvaluationDataError(f"{case_id}: context line count changed")
        if type(plan_case.get("source_bytes")) is not int or plan_case["source_bytes"] != byte_count:
            raise EvaluationDataError(f"{case_id}: context byte count changed")
        context_hash = _canonical_hash(context)
        if plan_case.get("context_sha256") != context_hash:
            raise EvaluationDataError(f"{case_id}: context SHA-256 changed")

        checkout_id = manifest_case["checkout_id"]
        cached = index_cache.get(checkout_id)
        if cached is not None:
            if cached[0] != manifest_case["commit"]:
                raise EvaluationDataError(f"{case_id}: checkout ID is reused for another commit")
            checkout, index = cached[1], cached[2]
        else:
            checkout = _verified_checkout(manifest_case, repos_root)
            _source_fingerprint(checkout, manifest_case)
            try:
                index = build_index(checkout)
            except (OSError, ValueError) as exc:
                raise EvaluationDataError(f"{case_id}: cannot index pinned target checkout") from exc
            index_cache[checkout_id] = (manifest_case["commit"], checkout, index)

        symbol = manifest_case["symbol"]
        if symbol in index.ambiguous_symbols or symbol not in index.symbols:
            raise EvaluationDataError(f"{case_id}: target symbol is unknown or ambiguous")
        try:
            rebuilt_context = build_context(index, symbol, max_lines)
            validate_context_budget(rebuilt_context)
            system_prompt, user_prompt = build_diagnosis_prompts(rebuilt_context)
            expected_context = json.loads(user_prompt)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EvaluationDataError(f"{case_id}: cannot rebuild prepared context") from exc
        if context != expected_context:
            raise EvaluationDataError(f"{case_id}: prepared context differs from pinned checkout")

        request = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "requested_model": model,
            "max_tokens": 4096,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        request_hash = _canonical_hash(request)
        if plan_case.get("request_sha256") != request_hash:
            raise EvaluationDataError(f"{case_id}: request fingerprint changed")
        case_state.append((manifest_case, plan_case, index, system_prompt, user_prompt))

    return case_state, model


def run_cases(
    plan: dict,
    contexts: dict[str, dict],
    repos_root: Path,
    *,
    repeats: int,
    max_calls: int,
    api_key: str,
    client: Callable,
    output_dir: Path,
    manifest: dict | None = None,
    manifest_sha256: str | None = None,
) -> dict:
    """Preflight a complete run, then call the provider sequentially without retries."""
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise EvaluationDataError("repeats must be an integer from 1 to 3")
    if type(max_calls) is not int or max_calls < 1:
        raise EvaluationDataError("max_calls must be a positive integer")
    if not isinstance(api_key, str) or not api_key.strip():
        raise EvaluationDataError("API key is required")
    if not callable(client):
        raise EvaluationDataError("client must be callable")
    if manifest is None:
        raise EvaluationDataError("manifest data is required")
    if manifest_sha256 is None:
        manifest_sha256 = _canonical_hash(manifest)

    output = Path(output_dir).absolute()
    if os.path.lexists(output):
        raise EvaluationDataError("output directory already exists")

    prepared, model = _validate_plan_and_contexts(
        plan, contexts, manifest, repos_root, manifest_sha256
    )
    if any(api_key in system_prompt or api_key in user_prompt
           for _, _, _, system_prompt, user_prompt in prepared):
        raise EvaluationDataError("API key appears in prepared request context")
    planned_calls = len(prepared) * repeats
    if planned_calls > max_calls:
        raise EvaluationDataError("planned calls exceed max_calls")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        records_dir = output / "records"
        records_dir.mkdir()
        inflight_dir = output / ".inflight"
        inflight_dir.mkdir()
    except OSError as exc:
        raise EvaluationDataError("cannot create a new experiment directory") from exc

    summary = {
        "schema_version": 1,
        "dataset_id": plan["dataset_id"],
        "manifest_sha256": manifest_sha256,
        "plan_sha256": _canonical_hash(plan),
        "analyzer_commit": plan["analyzer_commit"],
        "requested_model": model,
        "repeats": repeats,
        "max_calls": max_calls,
        "planned_calls": planned_calls,
        "attempted_calls": 0,
        "completed_calls": 0,
        "state": "running",
        "record_files": [],
    }
    summary_path = output / "run.json"
    _write_json_atomic(summary_path, summary)

    active_marker_path: Path | None = None
    active_record_path: Path | None = None
    active_record_payload: dict | None = None
    active_relative_record: str | None = None
    try:
        should_stop = False
        for repeat_index in range(1, repeats + 1):
            for manifest_case, plan_case, index, system_prompt, user_prompt in prepared:
                case_id = manifest_case["id"]
                stem = f"{case_id}-r{repeat_index}"
                marker_path = inflight_dir / f"{stem}.json"
                record_path = records_dir / f"{stem}.json"
                active_marker_path = marker_path
                active_record_path = record_path
                active_record_payload = None
                active_relative_record = record_path.relative_to(output).as_posix()
                started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                _write_json_atomic(marker_path, {
                    "case_id": case_id,
                    "repeat_index": repeat_index,
                    "request_sha256": plan_case["request_sha256"],
                    "started_at": started_at,
                })
                summary["attempted_calls"] += 1
                _write_json_atomic(summary_path, summary)

                started = time.perf_counter()
                response: DeepSeekResult | None = None
                status = "success"
                error = None
                error_code = None
                http_status = None
                validated: dict = {"accepted": [], "rejected": []}
                try:
                    response = client(
                        system_prompt,
                        user_prompt,
                        api_key=api_key,
                        model=model,
                    )
                except Exception as exc:
                    status, error_code, http_status = _client_error_details(exc)
                    error = status
                elapsed = time.perf_counter() - started

                if status == "success":
                    try:
                        if (
                            not isinstance(response, DeepSeekResult)
                            or not isinstance(response.model, str)
                            or not response.model.strip()
                            or not isinstance(response.payload, dict)
                        ):
                            raise ValueError("invalid provider response")
                        serialized_payload = _canonical_json(response.payload)
                        if len(api_key) >= 8 and api_key in serialized_payload:
                            raise ValueError("provider response contains a credential")
                        validated = validate_diagnosis_payload(
                            index, response.payload, contexts[case_id]
                        )
                    except (OSError, ValueError, TypeError, KeyError):
                        status = "invalid_response"
                        error = "invalid_response"
                        error_code = "invalid_response"

                response_model = response.model if status == "success" and response else None
                usage = _safe_usage(response.usage if response else None)
                record = {
                    "case_id": case_id,
                    "repeat_index": repeat_index,
                    "request_sha256": plan_case["request_sha256"],
                    "context_sha256": plan_case["context_sha256"],
                    "analyzer_commit": plan["analyzer_commit"],
                    "target_commit": manifest_case["commit"],
                    "requested_model": model,
                    "response_model": response_model,
                    "started_at": started_at,
                    "elapsed_seconds": elapsed,
                    "status": status,
                    "usage": usage,
                    "accepted": validated["accepted"] if status == "success" else [],
                    "rejected": validated["rejected"] if status == "success" else [],
                    "error": error,
                    "error_code": error_code,
                    "http_status": http_status,
                }
                serialized_record = _canonical_json(record)
                if len(api_key) >= 8 and api_key in serialized_record:
                    record.update({
                        "response_model": None,
                        "usage": None,
                        "accepted": [],
                        "rejected": [],
                        "status": "invalid_response",
                        "error": "invalid_response",
                        "error_code": "invalid_response",
                        "http_status": None,
                    })

                active_record_payload = record
                _write_json_atomic(record_path, record)
                summary["record_files"].append(active_relative_record)
                summary["completed_calls"] = len(summary["record_files"])
                if status != "success" or record["status"] != "success":
                    summary["state"] = "partial"
                    should_stop = True
                _write_json_atomic(summary_path, summary)
                marker_path.unlink(missing_ok=True)
                if should_stop:
                    break
            if should_stop:
                break

        if not should_stop:
            summary["state"] = "complete"
            _write_json_atomic(summary_path, summary)
    except BaseException:
        # A request may already have reached the provider. Reconcile a fully published
        # record before marking partial; otherwise keep its inflight marker for review.
        summary["state"] = "partial"
        record_reconciled = False
        if active_record_path is not None and active_record_payload is not None:
            try:
                persisted_record = json.loads(active_record_path.read_text(encoding="utf-8"))
                if persisted_record == active_record_payload:
                    if active_relative_record not in summary["record_files"]:
                        summary["record_files"].append(active_relative_record)
                    summary["completed_calls"] = len(summary["record_files"])
                    record_reconciled = True
            except BaseException:
                pass
        try:
            _write_json_atomic(summary_path, summary)
        except BaseException:
            pass
        else:
            if record_reconciled and active_marker_path is not None:
                try:
                    active_marker_path.unlink(missing_ok=True)
                except BaseException:
                    pass
        raise
    return summary
