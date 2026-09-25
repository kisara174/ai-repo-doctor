"""Offline review templates and auditable scoring for diagnosis runs."""

from __future__ import annotations

import math
import re
from statistics import median

from repo_doctor.deepseek import DEEPSEEK_ERROR_CODES
from .diagnosis_data import EvaluationDataError, validate_manifest
from .diagnosis_score_math import calculate_repeat_metrics


_REVIEW_ROW_KEYS = {
    "case_id",
    "repeat_index",
    "bucket",
    "finding_index",
    "verdict",
    "matched_issue_id",
    "rationale",
    "reviewer",
    "duplicate_of_bucket",
    "duplicate_of_finding_index",
}
_RUN_KEYS = {
    "schema_version",
    "dataset_id",
    "manifest_sha256",
    "plan_sha256",
    "analyzer_commit",
    "requested_model",
    "repeats",
    "max_calls",
    "planned_calls",
    "attempted_calls",
    "completed_calls",
    "state",
    "record_files",
}
_USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")
_COUNT_ZEROES = {
    "accepted_tp": 0,
    "accepted_fp": 0,
    "uncertain": 0,
    "duplicate": 0,
    "accepted_count": 0,
    "rejected_count": 0,
    "detected_known_bug_cases": 0,
    "successful_bug_cases": 0,
    "all_requested_bug_cases": 0,
    "successful_control_cases_with_accepted_fp": 0,
    "successful_fixed_and_control_cases": 0,
    "failed_calls": 0,
    "rejected_true_positive": 0,
}


def _fail(message: str) -> None:
    raise EvaluationDataError(message)


def _is_sha(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _case_repeat(record: dict) -> tuple[str, int]:
    case_id = record.get("case_id")
    repeat_index = record.get("repeat_index")
    if not isinstance(case_id, str) or re.fullmatch(r"[A-Za-z0-9_-]+", case_id) is None:
        _fail("record case_id is invalid")
    if type(repeat_index) is not int or repeat_index < 1:
        _fail(f"{case_id}: repeat_index must be a positive integer")
    return case_id, repeat_index


def _finding_entries(record: dict) -> list[tuple[str, int]]:
    case_id, repeat_index = _case_repeat(record)
    status = record.get("status")
    if status not in ("success", "provider_error", "invalid_response"):
        _fail(f"{case_id}: unknown record status")
    accepted = record.get("accepted")
    rejected = record.get("rejected")
    if not isinstance(accepted, list) or not isinstance(rejected, list):
        _fail(f"{case_id}: accepted and rejected must be lists")
    if status != "success" and (accepted or rejected):
        _fail(f"{case_id}: failed calls cannot contain findings")

    entries: list[tuple[str, int]] = []
    indices: set[int] = set()
    for bucket, findings in (("accepted", accepted), ("rejected", rejected)):
        for entry in findings:
            if not isinstance(entry, dict):
                _fail(f"{case_id}: finding entry must be an object")
            index = entry.get("index")
            if type(index) is not int or index < 0:
                _fail(f"{case_id}: finding index must be a nonnegative integer")
            if index in indices:
                _fail(f"{case_id}: duplicate model finding index")
            if not isinstance(entry.get("finding"), dict):
                _fail(f"{case_id}: finding payload must be an object")
            indices.add(index)
            entries.append((bucket, index))
    entries.sort(key=lambda item: item[1])
    return entries


def make_review_template(records: list[dict]) -> dict:
    """Create a pending review row for each finding in each successful record."""
    if not isinstance(records, list):
        _fail("records must be a list")
    seen_calls: set[tuple[str, int]] = set()
    rows = []
    for record in records:
        if not isinstance(record, dict):
            _fail("record must be an object")
        identity = _case_repeat(record)
        if identity in seen_calls:
            _fail("records contain a duplicate case/repeat")
        seen_calls.add(identity)
        for bucket, index in _finding_entries(record):
            case_id, repeat_index = identity
            rows.append({
                "case_id": case_id,
                "repeat_index": repeat_index,
                "bucket": bucket,
                "finding_index": index,
                "verdict": "pending",
                "matched_issue_id": None,
                "rationale": "",
                "reviewer": "",
                "duplicate_of_bucket": None,
                "duplicate_of_finding_index": None,
            })
    return {"schema_version": 1, "rows": rows}


def _validate_run_and_records(manifest: dict, records: list[dict], run: dict) -> dict[str, dict]:
    validate_manifest(manifest)
    if not isinstance(run, dict) or set(run) != _RUN_KEYS:
        _fail("review run metadata does not match the run schema")
    if type(run["schema_version"]) is not int or run["schema_version"] != 1:
        _fail("run schema_version must be 1")
    if run["dataset_id"] != manifest["dataset_id"]:
        _fail("run dataset does not match manifest")
    if not _is_sha(run["manifest_sha256"], 64) or not _is_sha(run["plan_sha256"], 64):
        _fail("run hashes must be SHA-256 values")
    if not _is_sha(run["analyzer_commit"], 40):
        _fail("run analyzer_commit must be a full Git SHA")
    if not isinstance(run["requested_model"], str) or not run["requested_model"].strip():
        _fail("run requested_model must be nonempty")
    repeats = run["repeats"]
    max_calls = run["max_calls"]
    planned = run["planned_calls"]
    attempted = run["attempted_calls"]
    completed = run["completed_calls"]
    if type(repeats) is not int or not 1 <= repeats <= 3:
        _fail("run repeats must be between 1 and 3")
    if type(max_calls) is not int or max_calls < 1:
        _fail("run max_calls must be a positive integer")
    expected_planned = len(manifest["cases"]) * repeats
    if type(planned) is not int or planned != expected_planned or planned > max_calls:
        _fail("run planned_calls does not match manifest and repeats")
    if type(attempted) is not int or not 0 <= attempted <= planned:
        _fail("run attempted_calls is invalid")
    if type(completed) is not int or completed != len(records):
        _fail("run completed_calls does not match the supplied records")
    if attempted < completed or attempted - completed > 1:
        _fail("run attempted/completed calls violate sequential execution")
    if run["state"] not in ("running", "complete", "partial"):
        _fail("run state is invalid")
    if run["state"] == "running":
        _fail("cannot score a running experiment")
    if run["state"] == "complete" and (attempted != planned or completed != planned):
        _fail("a complete run must contain every planned call")

    record_files = run["record_files"]
    if not isinstance(record_files, list) or len(record_files) != completed:
        _fail("run record_files does not match completed_calls")
    case_by_id = {case["id"]: case for case in manifest["cases"]}
    planned_keys = [
        (case["id"], repeat_index)
        for repeat_index in range(1, repeats + 1)
        for case in manifest["cases"]
    ]
    if completed > len(planned_keys) or attempted > len(planned_keys):
        _fail("run exceeds the planned call sequence")

    seen_calls: set[tuple[str, int]] = set()
    failure_seen = False
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            _fail("record must be an object")
        identity = _case_repeat(record)
        if identity != planned_keys[position]:
            _fail("records must be a prefix of manifest/repeat execution order")
        if identity in seen_calls:
            _fail("records contain a duplicate case/repeat")
        seen_calls.add(identity)
        case_id, repeat_index = identity
        case = case_by_id[case_id]
        expected_file = f"records/{case_id}-r{repeat_index}.json"
        if record_files[position] != expected_file:
            _fail("run record_files must name the listed records in execution order")
        if not isinstance(record_files[position], str) or ".." in record_files[position].split("/"):
            _fail("run record_files contains an unsafe path")
        if record.get("target_commit") != case["commit"]:
            _fail(f"{case_id}: target commit does not match manifest")
        if record.get("analyzer_commit") != run["analyzer_commit"]:
            _fail(f"{case_id}: analyzer commit does not match run")
        if record.get("requested_model") != run["requested_model"]:
            _fail(f"{case_id}: requested model does not match run")
        if not _is_sha(record.get("request_sha256"), 64) or not _is_sha(record.get("context_sha256"), 64):
            _fail(f"{case_id}: record fingerprints must be SHA-256 values")
        if record.get("status") not in ("success", "provider_error", "invalid_response"):
            _fail(f"{case_id}: unknown record status")
        error_code = record.get("error_code")
        if error_code is not None and (
            not isinstance(error_code, str) or error_code not in DEEPSEEK_ERROR_CODES
        ):
            _fail(f"{case_id}: error_code is not an allowed diagnostic code")
        http_status = record.get("http_status")
        if http_status is not None and (
            type(http_status) is not int or not 100 <= http_status <= 599
        ):
            _fail(f"{case_id}: http_status must be an HTTP status code or null")
        if record["status"] == "success":
            if error_code is not None or http_status is not None:
                _fail(f"{case_id}: successful record cannot contain error diagnostics")
        else:
            if record["status"] == "invalid_response" and error_code not in (None, "invalid_response"):
                _fail(f"{case_id}: invalid_response status has inconsistent error_code")
            if error_code == "invalid_response" and record["status"] != "invalid_response":
                _fail(f"{case_id}: invalid_response error_code has inconsistent status")
            if error_code == "http" and http_status is None:
                _fail(f"{case_id}: HTTP error is missing http_status")
            if error_code != "http" and http_status is not None:
                _fail(f"{case_id}: http_status requires an HTTP error code")
        if failure_seen:
            _fail("records continue after a failed provider response")
        if record["status"] != "success":
            failure_seen = True
        response_model = record.get("response_model")
        if record["status"] == "success":
            if not isinstance(response_model, str) or not response_model.strip():
                _fail(f"{case_id}: successful record is missing response_model")
            if record.get("error") is not None:
                _fail(f"{case_id}: successful record cannot have an error")
        elif response_model is not None or record.get("error") != record["status"]:
            _fail(f"{case_id}: failed record status/error is inconsistent")
        elapsed = record.get("elapsed_seconds")
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            _fail(f"{case_id}: elapsed_seconds must be a nonnegative finite number")
        usage = record.get("usage")
        if not isinstance(usage, dict) or set(usage) != set(_USAGE_KEYS):
            _fail(f"{case_id}: usage must contain only the three token fields")
        for token_name, value in usage.items():
            if value is not None and (type(value) is not int or value < 0):
                _fail(f"{case_id}: {token_name} must be a nonnegative integer or null")
        _finding_entries(record)

    if failure_seen and attempted > completed:
        _fail("a failed response cannot be followed by an unresolved request")
    if record_files != [
        f"records/{record['case_id']}-r{record['repeat_index']}.json" for record in records
    ]:
        _fail("run record_files do not match the supplied record sequence")
    if run["state"] == "complete" and failure_seen:
        _fail("a complete run cannot contain a failed request")
    return case_by_id


def _review_rows(records: list[dict], review: dict, case_by_id: dict[str, dict]) -> dict:
    if not isinstance(review, dict) or set(review) != {"schema_version", "run", "rows"}:
        _fail("review must contain schema_version, run, and rows")
    if type(review["schema_version"]) is not int or review["schema_version"] != 1:
        _fail("review schema_version must be 1")
    rows = review["rows"]
    if not isinstance(rows, list):
        _fail("review rows must be a list")

    expected = {}
    for record in records:
        case_id, repeat_index = _case_repeat(record)
        for bucket, index in _finding_entries(record):
            key = (case_id, repeat_index, bucket, index)
            expected[key] = None

    actual: dict[tuple[str, int, str, int], dict] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != _REVIEW_ROW_KEYS:
            _fail("review row does not match the required schema")
        case_id = row["case_id"]
        repeat_index = row["repeat_index"]
        bucket = row["bucket"]
        finding_index = row["finding_index"]
        if not isinstance(case_id, str) or type(repeat_index) is not int or type(finding_index) is not int:
            _fail("review row identity has invalid types")
        if repeat_index < 1 or finding_index < 0 or bucket not in ("accepted", "rejected"):
            _fail("review row identity is invalid")
        key = (case_id, repeat_index, bucket, finding_index)
        if key in actual:
            _fail("review contains a duplicate row")
        if key not in expected:
            _fail("review contains an unknown finding")
        actual[key] = row
    if set(actual) != set(expected):
        _fail("review is missing finding rows")

    for key, row in actual.items():
        case_id, repeat_index, bucket, finding_index = key
        case = case_by_id[case_id]
        verdict = row["verdict"]
        if verdict not in ("tp", "fp", "uncertain", "duplicate"):
            _fail(f"{case_id}: verdict must be tp, fp, uncertain, or duplicate")
        for field in ("rationale", "reviewer"):
            if not isinstance(row[field], str) or not row[field].strip():
                _fail(f"{case_id}: {field} must be nonempty text")
        issue_id = row["matched_issue_id"]
        if issue_id is not None and (not isinstance(issue_id, str) or not issue_id.strip()):
            _fail(f"{case_id}: matched_issue_id must be null or nonempty text")
        if issue_id is not None and issue_id != case["issue_id"]:
            _fail(f"{case_id}: matched_issue_id does not match the frozen issue")

        duplicate_bucket = row["duplicate_of_bucket"]
        duplicate_index = row["duplicate_of_finding_index"]
        if verdict == "tp":
            if case["label"] != "bug" or issue_id != case["issue_id"]:
                _fail(f"{case_id}: tp must match the known issue in a bug case")
            if duplicate_bucket is not None or duplicate_index is not None:
                _fail(f"{case_id}: tp cannot reference a duplicate target")
        elif verdict == "fp":
            if issue_id is not None:
                _fail(f"{case_id}: fp cannot match a frozen issue")
            if duplicate_bucket is not None or duplicate_index is not None:
                _fail(f"{case_id}: fp cannot reference a duplicate target")
        elif verdict == "uncertain":
            if duplicate_bucket is not None or duplicate_index is not None:
                _fail(f"{case_id}: uncertain cannot reference a duplicate target")
        else:
            if case["label"] != "bug" or issue_id != case["issue_id"]:
                _fail(f"{case_id}: duplicate must match a frozen bug issue")
            if duplicate_bucket not in ("accepted", "rejected") or type(duplicate_index) is not int or duplicate_index < 0:
                _fail(f"{case_id}: duplicate must identify its canonical finding")

    true_positives: dict[tuple[str, int, str], tuple[str, int]] = {}
    for key, row in actual.items():
        case_id, repeat_index, bucket, finding_index = key
        if row["verdict"] == "tp":
            group = (case_id, repeat_index, row["matched_issue_id"])
            if group in true_positives:
                _fail(f"{case_id}: additional finding for the same issue must be marked duplicate")
            true_positives[group] = (bucket, finding_index)
        elif row["verdict"] == "duplicate":
            canonical_key = (
                case_id,
                repeat_index,
                row["duplicate_of_bucket"],
                row["duplicate_of_finding_index"],
            )
            canonical = actual.get(canonical_key)
            if (
                canonical is None
                or canonical["verdict"] != "tp"
                or canonical["matched_issue_id"] != row["matched_issue_id"]
                or canonical_key == key
            ):
                _fail(f"{case_id}: duplicate must point to a canonical nonduplicate tp")
    return actual


def _metric_inputs(counts: dict) -> dict:
    total_findings = counts["accepted_count"] + counts["rejected_count"]
    return {
        "precision": {"numerator": counts["accepted_tp"], "denominator": counts["accepted_tp"] + counts["accepted_fp"]},
        "recall": {"numerator": counts["detected_known_bug_cases"], "denominator": counts["successful_bug_cases"]},
        "end_to_end_detection": {"numerator": counts["detected_known_bug_cases"], "denominator": counts["all_requested_bug_cases"]},
        "grounding_rate": {"numerator": counts["accepted_count"], "denominator": total_findings},
        "control_false_alarm_rate": {
            "numerator": counts["successful_control_cases_with_accepted_fp"],
            "denominator": counts["successful_fixed_and_control_cases"],
        },
        "uncertain_rate": {"numerator": counts["uncertain"], "denominator": total_findings},
        "duplicate_rate": {"numerator": counts["duplicate"], "denominator": total_findings},
    }


def _usage_details(records: list[dict]) -> tuple[dict[str, int], dict[str, int], int]:
    observed_totals = {name: 0 for name in _USAGE_KEYS}
    observed_records = {name: 0 for name in _USAGE_KEYS}
    missing_records = 0
    for record in records:
        usage = record["usage"]
        if any(usage[name] is None for name in _USAGE_KEYS):
            missing_records += 1
        for name in _USAGE_KEYS:
            if usage[name] is not None:
                observed_totals[name] += usage[name]
                observed_records[name] += 1
    return observed_totals, observed_records, missing_records


def score_records(manifest: dict, records: list[dict], review: dict) -> dict:
    """Score manually reviewed records without I/O, networking, or source execution."""
    if not isinstance(records, list):
        _fail("records must be a list")
    run = review.get("run") if isinstance(review, dict) else None
    case_by_id = _validate_run_and_records(manifest, records, run)
    reviewed = _review_rows(records, review, case_by_id)
    repeats = run["repeats"]
    manifest_cases = manifest["cases"]
    cases_by_repeat = {
        repeat_index: [
            record for record in records if record["repeat_index"] == repeat_index
        ]
        for repeat_index in range(1, repeats + 1)
    }
    rows_by_repeat = {
        repeat_index: [
            (key, row) for key, row in reviewed.items() if key[1] == repeat_index
        ]
        for repeat_index in range(1, repeats + 1)
    }

    by_repeat = []
    for repeat_index in range(1, repeats + 1):
        repeat_records = cases_by_repeat[repeat_index]
        repeat_rows = rows_by_repeat[repeat_index]
        counts = dict(_COUNT_ZEROES)
        requested_bug_cases = [case for case in manifest_cases if case["label"] == "bug"]
        counts["all_requested_bug_cases"] = len(requested_bug_cases)
        successful_bug_records = []
        successful_fixed_control_records = []
        successful_control_records = []
        failed_case_ids = []
        for record in repeat_records:
            case = case_by_id[record["case_id"]]
            if record["status"] == "success":
                if case["label"] == "bug":
                    counts["successful_bug_cases"] += 1
                    successful_bug_records.append(record)
                if case["label"] in ("fixed", "control"):
                    counts["successful_fixed_and_control_cases"] += 1
                    successful_fixed_control_records.append(record)
                if case["label"] == "control":
                    successful_control_records.append(record)
            else:
                counts["failed_calls"] += 1
                failed_case_ids.append(case["id"])

        detected_bug_case_ids = []
        for record in successful_bug_records:
            case_id = record["case_id"]
            has_accepted_tp = any(
                key[0] == case_id
                and key[1] == repeat_index
                and key[2] == "accepted"
                and row["verdict"] == "tp"
                for key, row in repeat_rows
            )
            if has_accepted_tp:
                detected_bug_case_ids.append(case_id)
        counts["detected_known_bug_cases"] = len(detected_bug_case_ids)

        for record in repeat_records:
            if record["status"] != "success":
                continue
            counts["accepted_count"] += len(record["accepted"])
            counts["rejected_count"] += len(record["rejected"])
        for key, row in repeat_rows:
            _, _, bucket, _ = key
            verdict = row["verdict"]
            if verdict == "uncertain":
                counts["uncertain"] += 1
            elif verdict == "duplicate":
                counts["duplicate"] += 1
            elif verdict == "tp":
                if bucket == "accepted":
                    counts["accepted_tp"] += 1
                else:
                    counts["rejected_true_positive"] += 1
            elif verdict == "fp" and bucket == "accepted":
                counts["accepted_fp"] += 1

        control_fp_ids = []
        for record in successful_control_records:
            case_id = record["case_id"]
            if any(
                key[0] == case_id
                and key[1] == repeat_index
                and key[2] == "accepted"
                and row["verdict"] == "fp"
                for key, row in repeat_rows
            ):
                control_fp_ids.append(case_id)
        counts["successful_control_cases_with_accepted_fp"] = len(control_fp_ids)

        scored = calculate_repeat_metrics(counts)
        repeat_latencies = [record["elapsed_seconds"] for record in repeat_records]
        repeat_usage_totals, repeat_usage_records, missing_usage_records = _usage_details(repeat_records)
        by_repeat.append({
            "repeat_index": repeat_index,
            "counts": scored["counts"],
            "metrics": scored["metrics"],
            "metric_inputs": _metric_inputs(counts),
            "samples": {
                "requested_bug_case_ids": [case["id"] for case in requested_bug_cases],
                "successful_bug_case_ids": [record["case_id"] for record in successful_bug_records],
                "detected_bug_case_ids": detected_bug_case_ids,
                "failed_case_ids": failed_case_ids,
                "successful_fixed_and_control_case_ids": [
                    record["case_id"] for record in successful_fixed_control_records
                ],
                "successful_control_cases_with_accepted_fp": control_fp_ids,
            },
            "request_details": [
                {
                    "case_id": record["case_id"],
                    "label": case_by_id[record["case_id"]]["label"],
                    "status": record["status"],
                    "elapsed_seconds": record["elapsed_seconds"],
                    "usage": dict(record["usage"]),
                }
                for record in repeat_records
            ],
            "missing_usage_records": missing_usage_records,
            "observed_token_totals": repeat_usage_totals,
            "observed_token_records": repeat_usage_records,
            "latency_values_seconds": repeat_latencies,
            "latency_median_seconds": median(repeat_latencies) if repeat_latencies else None,
        })

    observed_totals, observed_records, missing_usage_records = _usage_details(records)
    latencies = [record["elapsed_seconds"] for record in records]
    failed_calls = sum(record["status"] != "success" for record in records)
    unresolved_calls = run["attempted_calls"] - run["completed_calls"]
    totals = {
        "planned_calls": run["planned_calls"],
        "attempted_calls": run["attempted_calls"],
        "completed_calls": run["completed_calls"],
        "failed_calls": failed_calls,
        "unresolved_calls": unresolved_calls,
        "not_attempted_calls": run["planned_calls"] - run["attempted_calls"],
        "call_failure_rate": failed_calls / run["completed_calls"] if run["completed_calls"] else None,
        "call_failure_rate_inputs": {"numerator": failed_calls, "denominator": run["completed_calls"]},
        "missing_usage_records": missing_usage_records,
        "observed_token_totals": observed_totals,
        "observed_token_records": observed_records,
        "latency_values_seconds": [
            {
                "case_id": record["case_id"],
                "repeat_index": record["repeat_index"],
                "elapsed_seconds": record["elapsed_seconds"],
            }
            for record in records
        ],
        "latency_median_seconds": median(latencies) if latencies else None,
    }
    response_models = sorted({
        record["response_model"] for record in records if record["response_model"] is not None
    })
    return {
        "schema_version": 1,
        "dataset_id": run["dataset_id"],
        "case_count": len(manifest_cases),
        "case_ids": [case["id"] for case in manifest_cases],
        "manifest_sha256": run["manifest_sha256"],
        "plan_sha256": run["plan_sha256"],
        "analyzer_commit": run["analyzer_commit"],
        "requested_model": run["requested_model"],
        "response_models": response_models,
        "repeats": repeats,
        "run_state": run["state"],
        "by_repeat": by_repeat,
        "totals": totals,
        "limitations": [
            "The purposively selected cases are not a random or representative sample.",
            "Public issue discussions and fixes may be present in model training data.",
            "Paired bug/fixed snapshots are correlated, and repeated calls are not new independent cases.",
            "This exploratory result does not establish general product quality or reliability.",
            "End-to-end detection uses all planned bug cases; unattempted calls are shown separately.",
            "Precision excludes uncertain and duplicate findings; rejected true positives are diagnostic evidence only.",
        ],
    }


def _markdown(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ")


def _format_ratio(value: object) -> str:
    return "—" if value is None else f"{value:.4f}"


def render_report(report: dict) -> str:
    """Render a deterministic human-readable report from the scored JSON object."""
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        _fail("report must have schema_version 1")
    lines = [
        "# Diagnosis evaluation report",
        "",
        f"- Dataset: `{_markdown(report['dataset_id'])}`",
        f"- Manifest SHA-256: `{_markdown(report['manifest_sha256'])}`",
        f"- Plan SHA-256: `{_markdown(report['plan_sha256'])}`",
        f"- Analyzer commit: `{_markdown(report['analyzer_commit'])}`",
        f"- Requested model: `{_markdown(report['requested_model'])}`",
        f"- Response models: `{_markdown(', '.join(report['response_models']) or 'none')}`",
        f"- Samples: {report['case_count']}; case IDs: `{_markdown(', '.join(report['case_ids']))}`",
        f"- Repeats: {report['repeats']}; run state: `{_markdown(report['run_state'])}`",
        "",
        "Precision excludes uncertain and duplicate findings. Null means the denominator is zero.",
        "",
    ]
    summary = report['totals']
    if summary['completed_calls'] - summary['failed_calls'] == 0:
        lines.extend([
            'No successful model response was recorded; quality conclusions are unavailable.',
            '',
        ])
    elif report['run_state'] != 'complete':
        lines.extend([
            'This run is partial; unattempted requests are reported separately.',
            '',
        ])
    labels = {
        "precision": "Precision (excluding uncertain and duplicate)",
        "recall": "Conditional recall",
        "end_to_end_detection": "End-to-end detection",
        "grounding_rate": "Grounding rate",
        "control_false_alarm_rate": "Control false alarm rate",
        "uncertain_rate": "Uncertain rate",
        "duplicate_rate": "Duplicate rate",
    }
    for repeat in report["by_repeat"]:
        lines.extend([
            f"## Repeat {repeat['repeat_index']}",
            "",
            "| Metric | Value | Numerator / denominator |",
            "| --- | ---: | ---: |",
        ])
        for key, label in labels.items():
            inputs = repeat["metric_inputs"][key]
            lines.append(
                f"| {label} | {_format_ratio(repeat['metrics'][key])} | "
                f"{inputs['numerator']} / {inputs['denominator']} |"
            )
        counts = repeat["counts"]
        lines.extend([
            "",
            f"Findings: {counts['accepted_count']} accepted, {counts['rejected_count']} rejected; "
            f"uncertain {counts['uncertain']}, duplicate {counts['duplicate']}, "
            f"rejected true positives {counts['rejected_true_positive']}, "
            f"failed calls {counts['failed_calls']}.",
            "",
            f"Requested bug cases: {_markdown(', '.join(repeat['samples']['requested_bug_case_ids']) or 'none')}",
            f"Detected bug cases: {_markdown(', '.join(repeat['samples']['detected_bug_case_ids']) or 'none')}",
            f"Request elapsed median (including failed calls): {_format_ratio(repeat['latency_median_seconds'])} seconds; "
            f"raw seconds: {_markdown(', '.join(map(str, repeat['latency_values_seconds'])) or 'none')}.",
            f"Token usage missing in {repeat['missing_usage_records']} completed records; "
            f"observed token totals: {_markdown(repeat['observed_token_totals'])}.",
            "",
            "| Case | Label | Status | Seconds | Prompt tokens | Completion tokens | Total tokens |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ])
        for detail in repeat["request_details"]:
            usage = detail["usage"]
            values = ["—" if usage[name] is None else str(usage[name]) for name in _USAGE_KEYS]
            lines.append(
                f"| {_markdown(detail['case_id'])} | {_markdown(detail['label'])} | "
                f"{_markdown(detail['status'])} | {detail['elapsed_seconds']} | "
                f"{values[0]} | {values[1]} | {values[2]} |"
            )
        lines.append("")

    totals = report["totals"]
    lines.extend([
        "## Request and resource totals",
        "",
        f"Planned {totals['planned_calls']}; attempted {totals['attempted_calls']}; "
        f"completed {totals['completed_calls']}; failed {totals['failed_calls']}; "
        f"unresolved {totals['unresolved_calls']}; not attempted {totals['not_attempted_calls']}.",
        f"Completed-call failure rate: {_format_ratio(totals['call_failure_rate'])} "
        f"({totals['call_failure_rate_inputs']['numerator']} / "
        f"{totals['call_failure_rate_inputs']['denominator']}).",
        f"Missing usage: {totals['missing_usage_records']} records; "
        f"observed totals: {_markdown(totals['observed_token_totals'])}.",
        f"Request elapsed median (including failed calls): {_format_ratio(totals['latency_median_seconds'])} seconds.",
        "",
        "## Limitations",
        "",
    ])
    lines.extend(f"- {_markdown(item)}" for item in report["limitations"])
    return "\n".join(lines) + "\n"
