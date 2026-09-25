import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tests.test_diagnosis_data as data_fixture
from tools.diagnosis_score import make_review_template, render_report, score_records
from tools.evaluate_diagnosis import main


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ScoreInputs:
    def __init__(self):
        self.fixture = data_fixture.DiagnosisDataTests()
        self.fixture.setUp()
        base = self.fixture.manifest["cases"][0]

        def make_case(case_id, label, pair_id=None, issue_id=None):
            case = copy.deepcopy(base)
            case.update({
                "id": case_id,
                "label": label,
                "pair_id": pair_id,
                "issue_id": issue_id,
            })
            return case

        bugs = [
            make_case("bug-1", "bug", "pair-1", "issue-1"),
            make_case("bug-2", "bug", "pair-2", "issue-2"),
            make_case("bug-3", "bug", "pair-3", "issue-3"),
        ]
        fixed = [
            make_case("fixed-1", "fixed", "pair-1", "issue-1"),
            make_case("fixed-2", "fixed", "pair-2", "issue-2"),
            make_case("fixed-3", "fixed", "pair-3", "issue-3"),
        ]
        controls = [
            make_case("control-1", "control"),
            make_case("control-2", "control"),
        ]
        # The order supports a partial-run fixture: two successful bugs, two
        # successful controls, then a failed third bug that stops the runner.
        self.manifest = {
            "schema_version": 1,
            "dataset_id": "diagnosis-v1",
            "cases": [bugs[0], bugs[1], controls[0], controls[1], bugs[2], *fixed],
        }
        manifest_bytes = json.dumps(
            self.manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8") + b"\n"
        self.manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

        self.records = [
            self.make_record("bug-1", accepted=(0, 1), elapsed=1),
            self.make_record("bug-2", accepted=(0,), rejected=(1,), elapsed=2),
            self.make_record("control-1", accepted=(0,), elapsed=3),
            self.make_record("control-2", elapsed=4),
            self.make_record("bug-3", status="provider_error", elapsed=5),
        ]
        self.run = {
            "schema_version": 1,
            "dataset_id": self.manifest["dataset_id"],
            "manifest_sha256": self.manifest_sha256,
            "plan_sha256": "b" * 64,
            "analyzer_commit": "c" * 40,
            "requested_model": "test-model",
            "repeats": 1,
            "max_calls": 8,
            "planned_calls": 8,
            "attempted_calls": 5,
            "completed_calls": 5,
            "state": "partial",
            "record_files": [
                f"records/{record['case_id']}-r{record['repeat_index']}.json"
                for record in self.records
            ],
        }
        self.review = self.make_review()

    def make_record(self, case_id, *, accepted=(), rejected=(), status="success", elapsed=1):
        case = next(case for case in self.manifest["cases"] if case["id"] == case_id)
        return {
            "case_id": case_id,
            "repeat_index": 1,
            "request_sha256": _sha(f"request:{case_id}"),
            "context_sha256": _sha(f"context:{case_id}"),
            "analyzer_commit": "c" * 40,
            "target_commit": case["commit"],
            "requested_model": "test-model",
            "response_model": "test-model" if status == "success" else None,
            "started_at": "2026-09-24T00:00:00Z",
            "elapsed_seconds": float(elapsed),
            "status": status,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
            } if case_id != "control-2" else {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            },
            "accepted": [
                {"index": index, "finding": {"title": f"accepted {index}"}}
                for index in accepted
            ] if status == "success" else [],
            "rejected": [
                {"index": index, "finding": {"title": f"rejected {index}"}}
                for index in rejected
            ] if status == "success" else [],
            "error": "provider_error" if status == "provider_error" else None,
        }

    def make_review(self):
        template = make_review_template(self.records)
        template["run"] = copy.deepcopy(self.run)
        decisions = {
            ("bug-1", "accepted", 0): ("tp", "issue-1", None, None),
            ("bug-1", "accepted", 1): ("duplicate", "issue-1", "accepted", 0),
            ("bug-2", "accepted", 0): ("uncertain", "issue-2", None, None),
            ("bug-2", "rejected", 1): ("tp", "issue-2", None, None),
            ("control-1", "accepted", 0): ("fp", None, None, None),
        }
        for row in template["rows"]:
            verdict, issue_id, duplicate_bucket, duplicate_index = decisions[
                (row["case_id"], row["bucket"], row["finding_index"])
            ]
            row.update({
                "verdict": verdict,
                "matched_issue_id": issue_id,
                "rationale": f"Manual assessment for {verdict}.",
                "reviewer": "reviewer@example.invalid",
                "duplicate_of_bucket": duplicate_bucket,
                "duplicate_of_finding_index": duplicate_index,
            })
        return template

    def close(self):
        self.fixture.tearDown()


def write_run_bundle(run_dir, run, records):
    run_dir.mkdir()
    records_dir = run_dir / "records"
    records_dir.mkdir()
    (run_dir / "run.json").write_text(
        json.dumps(run, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    for relative, record in zip(run["record_files"], records, strict=True):
        (run_dir / relative).write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


class DiagnosisScoreTests(unittest.TestCase):
    def setUp(self):
        self.inputs = ScoreInputs()
        self.addCleanup(self.inputs.close)

    def test_review_template_covers_each_success_finding_and_only_those_findings(self):
        template = make_review_template(self.inputs.records)

        self.assertEqual(template["schema_version"], 1)
        self.assertEqual(len(template["rows"]), 5)
        self.assertEqual(
            [(row["case_id"], row["bucket"], row["finding_index"]) for row in template["rows"]],
            [
                ("bug-1", "accepted", 0),
                ("bug-1", "accepted", 1),
                ("bug-2", "accepted", 0),
                ("bug-2", "rejected", 1),
                ("control-1", "accepted", 0),
            ],
        )
        for row in template["rows"]:
            self.assertEqual(row["verdict"], "pending")
            self.assertIsNone(row["matched_issue_id"])
            self.assertEqual(row["rationale"], "")
            self.assertEqual(row["reviewer"], "")
            self.assertIsNone(row["duplicate_of_bucket"])
            self.assertIsNone(row["duplicate_of_finding_index"])

    def test_hand_checked_metrics_separate_accuracy_grounding_and_request_failures(self):
        report = score_records(self.inputs.manifest, self.inputs.records, self.inputs.review)

        result = report["by_repeat"][0]
        self.assertEqual(result["counts"], {
            "accepted_tp": 1,
            "accepted_fp": 1,
            "uncertain": 1,
            "duplicate": 1,
            "accepted_count": 4,
            "rejected_count": 1,
            "detected_known_bug_cases": 1,
            "successful_bug_cases": 2,
            "all_requested_bug_cases": 3,
            "successful_control_cases_with_accepted_fp": 1,
            "successful_fixed_and_control_cases": 2,
            "failed_calls": 1,
            "rejected_true_positive": 1,
        })
        self.assertEqual(result["metrics"], {
            "precision": 1 / 2,
            "recall": 1 / 2,
            "end_to_end_detection": 1 / 3,
            "grounding_rate": 4 / 5,
            "control_false_alarm_rate": 1 / 2,
            "uncertain_rate": 1 / 5,
            "duplicate_rate": 1 / 5,
        })
        self.assertEqual(result["metric_inputs"]["precision"], {"numerator": 1, "denominator": 2})
        self.assertEqual(result["samples"]["detected_bug_case_ids"], ["bug-1"])
        self.assertEqual(result["samples"]["requested_bug_case_ids"], ["bug-1", "bug-2", "bug-3"])
        self.assertEqual(result["missing_usage_records"], 1)
        self.assertEqual(result["latency_values_seconds"], [1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(result["latency_median_seconds"], 3.0)
        self.assertEqual(report["totals"]["unresolved_calls"], 0)
        self.assertEqual(report["totals"]["not_attempted_calls"], 3)
        self.assertEqual(report["totals"]["call_failure_rate"], 1 / 5)
        self.assertEqual(report["totals"]["call_failure_rate_inputs"], {
            "numerator": 1,
            "denominator": 5,
        })

    def test_optional_error_diagnostics_are_validated_and_legacy_records_still_work(self):
        legacy_report = score_records(
            self.inputs.manifest, copy.deepcopy(self.inputs.records), self.inputs.review
        )
        self.assertEqual(legacy_report["totals"]["failed_calls"], 1)

        invalid_metadata = [
            {"error_code": "private provider detail"},
            {"http_status": 429},
            {"error_code": "http", "http_status": True},
            {"error_code": "http", "http_status": 429},
            {"error_code": "invalid_response"},
        ]
        for metadata in invalid_metadata:
            with self.subTest(metadata=metadata):
                records = copy.deepcopy(self.inputs.records)
                records[0].update(metadata)
                with self.assertRaises(ValueError):
                    score_records(self.inputs.manifest, records, self.inputs.review)

    def test_scoring_accepts_http_diagnostics_on_a_failed_record(self):
        records = copy.deepcopy(self.inputs.records)
        records[-1].update(error_code="http", http_status=429)

        report = score_records(self.inputs.manifest, records, self.inputs.review)

        self.assertEqual(report["totals"]["failed_calls"], 1)

    def test_unresolved_attempts_are_excluded_from_completed_call_failure_rate(self):
        records = [self.inputs.make_record("bug-1", accepted=(0,))]
        run = copy.deepcopy(self.inputs.run)
        run.update({
            "planned_calls": 8,
            "attempted_calls": 2,
            "completed_calls": 1,
            "state": "partial",
            "record_files": ["records/bug-1-r1.json"],
        })
        review = make_review_template(records)
        review["run"] = run
        review["rows"][0].update({
            "verdict": "tp",
            "matched_issue_id": "issue-1",
            "rationale": "Matches the frozen bug root cause.",
            "reviewer": "reviewer",
        })

        report = score_records(self.inputs.manifest, records, review)

        self.assertEqual(report["totals"]["failed_calls"], 0)
        self.assertEqual(report["totals"]["unresolved_calls"], 1)
        self.assertEqual(report["totals"]["not_attempted_calls"], 6)
        self.assertEqual(report["totals"]["call_failure_rate"], 0.0)
        self.assertEqual(report["totals"]["call_failure_rate_inputs"], {
            "numerator": 0,
            "denominator": 1,
        })

    def test_uncertain_does_not_count_as_positive_and_zero_denominators_are_null(self):
        records = [self.inputs.make_record("bug-1", accepted=(0,), elapsed=1)]
        run = copy.deepcopy(self.inputs.run)
        run.update({
            "planned_calls": 8,
            "attempted_calls": 1,
            "completed_calls": 1,
            "state": "partial",
            "record_files": ["records/bug-1-r1.json"],
        })
        review = make_review_template(records)
        review["run"] = run
        review["rows"][0].update({
            "verdict": "uncertain",
            "matched_issue_id": None,
            "rationale": "Insufficient context to decide.",
            "reviewer": "reviewer",
        })

        report = score_records(self.inputs.manifest, records, review)

        metrics = report["by_repeat"][0]["metrics"]
        self.assertIsNone(metrics["precision"])
        self.assertEqual(metrics["recall"], 0.0)
        self.assertEqual(metrics["end_to_end_detection"], 0.0)
        self.assertEqual(metrics["grounding_rate"], 1.0)
        self.assertIsNone(metrics["control_false_alarm_rate"])

    def test_all_failed_calls_keep_undefined_quality_ratios_null(self):
        records = [self.inputs.make_record("bug-1", status="provider_error")]
        run = copy.deepcopy(self.inputs.run)
        run.update({
            "attempted_calls": 1,
            "completed_calls": 1,
            "record_files": ["records/bug-1-r1.json"],
        })
        review = make_review_template(records)
        review["run"] = run

        report = score_records(self.inputs.manifest, records, review)

        counts = report["by_repeat"][0]["counts"]
        metrics = report["by_repeat"][0]["metrics"]
        self.assertEqual(counts["failed_calls"], 1)
        self.assertIsNone(metrics["precision"])
        self.assertIsNone(metrics["recall"])
        self.assertEqual(metrics["end_to_end_detection"], 0.0)
        self.assertIsNone(metrics["grounding_rate"])
        self.assertIsNone(metrics["control_false_alarm_rate"])
        self.assertEqual(report["totals"]["call_failure_rate"], 1.0)

    def test_rejects_pending_missing_duplicate_unknown_or_inconsistent_review_rows(self):
        malformed = []
        pending = copy.deepcopy(self.inputs.review)
        pending["rows"][0]["verdict"] = "pending"
        malformed.append(pending)
        missing = copy.deepcopy(self.inputs.review)
        missing["rows"].pop()
        malformed.append(missing)
        duplicate = copy.deepcopy(self.inputs.review)
        duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
        malformed.append(duplicate)
        unknown = copy.deepcopy(self.inputs.review)
        unknown["rows"][0]["finding_index"] = 99
        malformed.append(unknown)
        no_rationale = copy.deepcopy(self.inputs.review)
        no_rationale["rows"][0]["rationale"] = " "
        malformed.append(no_rationale)
        wrong_issue = copy.deepcopy(self.inputs.review)
        wrong_issue["rows"][0]["matched_issue_id"] = "issue-2"
        malformed.append(wrong_issue)
        bad_duplicate_target = copy.deepcopy(self.inputs.review)
        bad_duplicate_target["rows"][1]["duplicate_of_finding_index"] = 88
        malformed.append(bad_duplicate_target)

        for review in malformed:
            with self.subTest(review=review):
                with self.assertRaises(ValueError):
                    score_records(self.inputs.manifest, self.inputs.records, review)

    def test_rejects_running_run_and_duplicate_record_identity(self):
        review = copy.deepcopy(self.inputs.review)
        review["run"]["state"] = "running"
        with self.assertRaisesRegex(ValueError, "running"):
            score_records(self.inputs.manifest, self.inputs.records, review)

        duplicated = copy.deepcopy(self.inputs.records)
        duplicated.append(copy.deepcopy(duplicated[0]))
        run = copy.deepcopy(self.inputs.run)
        run["record_files"].append(run["record_files"][0])
        run["attempted_calls"] += 1
        run["completed_calls"] += 1
        duplicate_review = copy.deepcopy(self.inputs.review)
        duplicate_review["run"] = run
        with self.assertRaises(ValueError):
            score_records(self.inputs.manifest, duplicated, duplicate_review)

    def test_rejects_a_complete_run_that_contains_a_failed_call(self):
        records = [
            self.inputs.make_record(
                case["id"],
                status="provider_error" if position == 7 else "success",
            )
            for position, case in enumerate(self.inputs.manifest["cases"])
        ]
        run = copy.deepcopy(self.inputs.run)
        run.update({
            "attempted_calls": 8,
            "completed_calls": 8,
            "state": "complete",
            "record_files": [
                f"records/{record['case_id']}-r{record['repeat_index']}.json"
                for record in records
            ],
        })
        review = make_review_template(records)
        review["run"] = run

        with self.assertRaisesRegex(ValueError, "complete run cannot contain a failed"):
            score_records(self.inputs.manifest, records, review)

    def test_reports_each_repeat_separately_without_pooling_case_counts(self):
        records = []
        for case in self.inputs.manifest["cases"]:
            accepted = (0,) if case["id"] == "bug-1" else ()
            records.append(self.inputs.make_record(case["id"], accepted=accepted))
        second_repeat = self.inputs.make_record("bug-1", accepted=(1,))
        second_repeat["repeat_index"] = 2
        records.append(second_repeat)
        run = copy.deepcopy(self.inputs.run)
        run.update({
            "repeats": 2,
            "max_calls": 16,
            "planned_calls": 16,
            "attempted_calls": 9,
            "completed_calls": 9,
            "record_files": [
                f"records/{record['case_id']}-r{record['repeat_index']}.json"
                for record in records
            ],
        })
        review = make_review_template(records)
        review["run"] = run
        first_repeat_row = next(row for row in review["rows"] if row["repeat_index"] == 1)
        first_repeat_row.update({
            "verdict": "tp",
            "matched_issue_id": "issue-1",
            "rationale": "Matches the frozen bug root cause.",
            "reviewer": "reviewer",
        })
        second_repeat_row = next(row for row in review["rows"] if row["repeat_index"] == 2)
        second_repeat_row.update({
            "verdict": "fp",
            "matched_issue_id": None,
            "rationale": "Does not match the known issue.",
            "reviewer": "reviewer",
        })

        report = score_records(self.inputs.manifest, records, review)

        self.assertEqual(len(report["by_repeat"]), 2)
        self.assertEqual(report["by_repeat"][0]["counts"]["successful_bug_cases"], 3)
        self.assertEqual(report["by_repeat"][0]["counts"]["detected_known_bug_cases"], 1)
        self.assertEqual(report["by_repeat"][0]["metrics"]["recall"], 1 / 3)
        self.assertEqual(report["by_repeat"][0]["counts"]["all_requested_bug_cases"], 3)
        self.assertEqual(report["by_repeat"][0]["metrics"]["end_to_end_detection"], 1 / 3)
        self.assertEqual(report["by_repeat"][1]["counts"]["successful_bug_cases"], 1)
        self.assertEqual(report["by_repeat"][1]["counts"]["detected_known_bug_cases"], 0)
        self.assertEqual(report["by_repeat"][1]["counts"]["all_requested_bug_cases"], 3)
        self.assertEqual(report["by_repeat"][1]["metrics"]["recall"], 0.0)
        self.assertEqual(report["by_repeat"][1]["metrics"]["end_to_end_detection"], 0.0)

    def test_markdown_report_shows_formula_denominators_and_limits(self):
        report = score_records(self.inputs.manifest, self.inputs.records, self.inputs.review)

        rendered = render_report(report)

        self.assertIn("Precision (excluding uncertain and duplicate)", rendered)
        self.assertIn("1 / 2", rendered)
        self.assertIn("1 / 3", rendered)
        self.assertIn("not a random or representative sample", rendered)
        self.assertIn("3.0", rendered)
        self.assertIn("1", rendered)
        self.assertIn("Completed-call failure rate", rendered)


class DiagnosisScoreCliTests(unittest.TestCase):
    def setUp(self):
        self.inputs = ScoreInputs()
        self.addCleanup(self.inputs.close)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / "run"
        write_run_bundle(self.run_dir, self.inputs.run, self.inputs.records)

    def test_prepare_review_uses_only_listed_records_and_copies_run_provenance(self):
        orphan = self.run_dir / "records" / "orphan-r1.json"
        orphan.write_text(json.dumps(self.inputs.records[0]), encoding="utf-8")
        output = self.root / "review.json"

        code = main(["prepare-review", "--run-dir", str(self.run_dir), "--out-file", str(output)])

        self.assertEqual(code, 0)
        review = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(review["run"], self.inputs.run)
        self.assertEqual(review["rows"], make_review_template(self.inputs.records)["rows"])
        self.assertEqual(len(review["rows"]), 5)
        self.assertEqual(main([
            "prepare-review", "--run-dir", str(self.run_dir), "--out-file", str(output),
        ]), 2)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), review)

    def test_prepare_review_rejects_record_path_traversal(self):
        run = copy.deepcopy(self.inputs.run)
        run["record_files"][0] = "records/../outside.json"
        (self.run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        output = self.root / "review.json"

        code = main(["prepare-review", "--run-dir", str(self.run_dir), "--out-file", str(output)])

        self.assertEqual(code, 2)
        self.assertFalse(output.exists())

    def test_score_cli_validates_manifest_hash_and_writes_json_and_markdown(self):
        manifest_path = self.root / "manifest.json"
        raw_manifest = json.dumps(
            self.inputs.manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8") + b"\n"
        manifest_path.write_bytes(raw_manifest)
        manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
        run = copy.deepcopy(self.inputs.run)
        run["manifest_sha256"] = manifest_hash
        (self.run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        review = copy.deepcopy(self.inputs.review)
        review["run"] = run
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        json_output = self.root / "report.json"
        markdown_output = self.root / "report.md"

        code = main([
            "score", "--manifest", str(manifest_path), "--run-dir", str(self.run_dir),
            "--review", str(review_path), "--json-out", str(json_output),
            "--markdown-out", str(markdown_output),
        ])

        self.assertEqual(code, 0)
        report = json.loads(json_output.read_text(encoding="utf-8"))
        self.assertEqual(report["manifest_sha256"], manifest_hash)
        self.assertEqual(report["by_repeat"][0]["metrics"]["precision"], 0.5)
        self.assertIn("Diagnosis evaluation report", markdown_output.read_text(encoding="utf-8"))

    def test_score_cli_rejects_pending_rows_without_creating_reports(self):
        manifest_path = self.root / "manifest.json"
        raw_manifest = json.dumps(
            self.inputs.manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8") + b"\n"
        manifest_path.write_bytes(raw_manifest)
        run = copy.deepcopy(self.inputs.run)
        run["manifest_sha256"] = hashlib.sha256(raw_manifest).hexdigest()
        (self.run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        pending = make_review_template(self.inputs.records)
        pending["run"] = run
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(pending), encoding="utf-8")
        json_output = self.root / "report.json"
        markdown_output = self.root / "report.md"

        code = main([
            "score", "--manifest", str(manifest_path), "--run-dir", str(self.run_dir),
            "--review", str(review_path), "--json-out", str(json_output),
            "--markdown-out", str(markdown_output),
        ])

        self.assertEqual(code, 2)
        self.assertFalse(json_output.exists())
        self.assertFalse(markdown_output.exists())

    def test_score_cli_never_overwrites_an_existing_report(self):
        manifest_path = self.root / "manifest.json"
        raw_manifest = json.dumps(
            self.inputs.manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8") + b"\n"
        manifest_path.write_bytes(raw_manifest)
        run = copy.deepcopy(self.inputs.run)
        run["manifest_sha256"] = hashlib.sha256(raw_manifest).hexdigest()
        (self.run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        review = copy.deepcopy(self.inputs.review)
        review["run"] = run
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        json_output = self.root / "report.json"
        markdown_output = self.root / "report.md"
        json_output.write_text("existing report", encoding="utf-8")

        code = main([
            "score", "--manifest", str(manifest_path), "--run-dir", str(self.run_dir),
            "--review", str(review_path), "--json-out", str(json_output),
            "--markdown-out", str(markdown_output),
        ])

        self.assertEqual(code, 2)
        self.assertEqual(json_output.read_text(encoding="utf-8"), "existing report")
        self.assertFalse(markdown_output.exists())

    def test_score_failure_preserves_existing_reports_and_rejects_hash_mismatch(self):
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(self.inputs.manifest), encoding="utf-8")
        review = copy.deepcopy(self.inputs.review)
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        json_output = self.root / "report.json"
        markdown_output = self.root / "report.md"
        json_output.write_text("keep json", encoding="utf-8")
        markdown_output.write_text("keep markdown", encoding="utf-8")

        code = main([
            "score", "--manifest", str(manifest_path), "--run-dir", str(self.run_dir),
            "--review", str(review_path), "--json-out", str(json_output),
            "--markdown-out", str(markdown_output),
        ])

        self.assertEqual(code, 2)
        self.assertEqual(json_output.read_text(encoding="utf-8"), "keep json")
        self.assertEqual(markdown_output.read_text(encoding="utf-8"), "keep markdown")

    def test_score_refuses_the_same_output_path(self):
        manifest_path = self.root / "manifest.json"
        raw_manifest = json.dumps(
            self.inputs.manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8") + b"\n"
        manifest_path.write_bytes(raw_manifest)
        run = copy.deepcopy(self.inputs.run)
        run["manifest_sha256"] = hashlib.sha256(raw_manifest).hexdigest()
        (self.run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        review = copy.deepcopy(self.inputs.review)
        review["run"] = run
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        output = self.root / "report.out"

        code = main([
            "score", "--manifest", str(manifest_path), "--run-dir", str(self.run_dir),
            "--review", str(review_path), "--json-out", str(output),
            "--markdown-out", str(output),
        ])

        self.assertEqual(code, 2)
        self.assertFalse(output.exists())

    def test_score_rolls_back_first_output_if_second_publish_fails(self):
        from tools import evaluate_diagnosis

        manifest_path = self.root / "manifest.json"
        raw_manifest = json.dumps(
            self.inputs.manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8") + b"\n"
        manifest_path.write_bytes(raw_manifest)
        run = copy.deepcopy(self.inputs.run)
        run["manifest_sha256"] = hashlib.sha256(raw_manifest).hexdigest()
        (self.run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        review = copy.deepcopy(self.inputs.review)
        review["run"] = run
        review_path = self.root / "review.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        json_output = self.root / "report.json"
        markdown_output = self.root / "report.md"
        real_link = evaluate_diagnosis.os.link
        link_count = 0

        def fail_second_link(source, destination):
            nonlocal link_count
            link_count += 1
            if link_count == 2:
                raise OSError("simulated publication failure")
            return real_link(source, destination)

        with patch("tools.evaluate_diagnosis.os.link", side_effect=fail_second_link):
            code = main([
                "score", "--manifest", str(manifest_path), "--run-dir", str(self.run_dir),
                "--review", str(review_path), "--json-out", str(json_output),
                "--markdown-out", str(markdown_output),
            ])

        self.assertEqual(code, 2)
        self.assertFalse(json_output.exists())
        self.assertFalse(markdown_output.exists())


if __name__ == "__main__":
    unittest.main()
