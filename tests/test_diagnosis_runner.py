import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tools.diagnosis_runner as diagnosis_runner_module
from repo_doctor.deepseek import MAX_REQUEST_BYTES, DeepSeekError, DeepSeekResult
import tests.test_diagnosis_data as data_fixture
from tools.diagnosis_data import prepare_cases
from tools.diagnosis_runner import run_cases


ANALYZER_COMMIT = "a" * 40
API_KEY = "TEST_SECRET_SENTINEL"


class DiagnosisRunnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = data_fixture.DiagnosisDataTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output_root = Path(self.temporary.name)

        self.manifest = copy.deepcopy(self.fixture.manifest)
        second_case = copy.deepcopy(self.manifest["cases"][0])
        second_case["id"] = "bug-02"
        self.manifest["cases"].append(second_case)
        self.manifest_bytes = json.dumps(self.manifest, ensure_ascii=False).encode("utf-8")
        self.manifest_sha256 = hashlib.sha256(self.manifest_bytes).hexdigest()
        with patch("tools.diagnosis_data._analyzer_commit", return_value=ANALYZER_COMMIT):
            bundle = prepare_cases(
                self.manifest,
                self.fixture.repos_root,
                "test-model",
                120,
                manifest_sha256=self.manifest_sha256,
            )
        self.plan = bundle["plan"]
        self.contexts = bundle["contexts"]

    def run_with(self, *, client, output_name="run", **changes):
        plan = copy.deepcopy(changes.pop("plan", self.plan))
        contexts = copy.deepcopy(changes.pop("contexts", self.contexts))
        repos_root = changes.pop("repos_root", self.fixture.repos_root)
        output_dir = self.output_root / output_name
        options = {
            "repeats": 1,
            "max_calls": 2,
            "api_key": API_KEY,
            "client": client,
            "output_dir": output_dir,
            "manifest": self.manifest,
            "manifest_sha256": self.manifest_sha256,
        }
        options.update(changes)
        with patch("tools.diagnosis_runner._analyzer_snapshot", return_value=(ANALYZER_COMMIT, False)):
            summary = run_cases(
                plan, contexts, repos_root,
                repeats=options.pop("repeats"),
                max_calls=options.pop("max_calls"),
                api_key=options.pop("api_key"),
                client=options.pop("client"),
                output_dir=options.pop("output_dir"),
                manifest=options.pop("manifest"),
                manifest_sha256=options.pop("manifest_sha256"),
                **options,
            )
        return summary, output_dir

    def assert_rejected_before_client(self, client, output_name="rejected", **changes):
        output_dir = self.output_root / output_name
        with patch("tools.diagnosis_runner._analyzer_snapshot", return_value=(ANALYZER_COMMIT, False)):
            with self.assertRaises(ValueError):
                run_cases(
                    changes.pop("plan", copy.deepcopy(self.plan)),
                    changes.pop("contexts", copy.deepcopy(self.contexts)),
                    changes.pop("repos_root", self.fixture.repos_root),
                    repeats=changes.pop("repeats", 1),
                    max_calls=changes.pop("max_calls", 2),
                    api_key=changes.pop("api_key", API_KEY),
                    client=client,
                    output_dir=output_dir,
                    manifest=changes.pop("manifest", copy.deepcopy(self.manifest)),
                    manifest_sha256=changes.pop("manifest_sha256", self.manifest_sha256),
                    **changes,
                )
        client.assert_not_called()
        return output_dir

    def test_two_valid_cases_make_exactly_two_requests_and_write_safe_records(self):
        client = Mock(return_value=DeepSeekResult(
            "test-model",
            {"findings": []},
            {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        ))

        summary, output_dir = self.run_with(client=client)

        self.assertEqual(client.call_count, 2)
        self.assertEqual(summary["state"], "complete")
        self.assertEqual(summary["planned_calls"], 2)
        self.assertEqual(summary["attempted_calls"], 2)
        self.assertEqual(summary["completed_calls"], 2)
        self.assertEqual(len(summary["record_files"]), 2)
        self.assertEqual(json.loads((output_dir / "run.json").read_text()), summary)
        records = [json.loads((output_dir / name).read_text()) for name in summary["record_files"]]
        self.assertEqual([record["status"] for record in records], ["success", "success"])
        self.assertEqual(records[0]["usage"], {
            "prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12,
        })
        for path in output_dir.rglob("*"):
            if path.is_file():
                self.assertNotIn(API_KEY, path.read_text(encoding="utf-8"))
        user_payload = json.loads(client.call_args_list[0].args[1])
        self.assertEqual(set(user_payload), {"symbol", "blocks", "call_evidence"})
        self.assertNotIn("GROUND_TRUTH_SENTINEL", json.dumps(user_payload))

    def test_insufficient_call_budget_rejects_the_entire_run_before_client(self):
        client = Mock()
        output = self.assert_rejected_before_client(client, max_calls=1)
        self.assertFalse(output.exists())

    def test_oversized_wire_request_rejects_before_creating_run_or_calling_client(self):
        client = Mock(return_value=DeepSeekResult("test-model", {"findings": []}))
        with patch.object(
            diagnosis_runner_module,
            "_serialize_request_body",
            return_value=b"x" * (MAX_REQUEST_BYTES + 1),
            create=True,
        ):
            output = self.assert_rejected_before_client(client)

        self.assertFalse(output.exists())

    def test_changed_context_hash_rejects_the_run_before_client(self):
        client = Mock()
        plan = copy.deepcopy(self.plan)
        plan["cases"][0]["context_sha256"] = "0" * 64
        output = self.assert_rejected_before_client(client, plan=plan)
        self.assertFalse(output.exists())

    def test_changed_request_hash_rejects_the_run_before_client(self):
        client = Mock()
        plan = copy.deepcopy(self.plan)
        plan["cases"][0]["request_sha256"] = "0" * 64
        output = self.assert_rejected_before_client(client, plan=plan)
        self.assertFalse(output.exists())

    def test_changed_manifest_hash_rejects_the_run_before_client(self):
        client = Mock()
        output = self.assert_rejected_before_client(client, manifest_sha256="0" * 64)
        self.assertFalse(output.exists())

    def test_changed_analyzer_commit_or_dirty_analyzer_rejects_before_client(self):
        for actual in (("b" * 40, False), (ANALYZER_COMMIT, True)):
            with self.subTest(actual=actual):
                client = Mock()
                output = self.output_root / ("analyzer-" + str(actual[1]))
                with patch("tools.diagnosis_runner._analyzer_snapshot", return_value=actual):
                    with self.assertRaisesRegex(ValueError, "analyzer"):
                        run_cases(
                            self.plan, self.contexts, self.fixture.repos_root,
                            repeats=1, max_calls=2, api_key=API_KEY,
                            client=client, output_dir=output,
                            manifest=self.manifest,
                            manifest_sha256=self.manifest_sha256,
                        )
                client.assert_not_called()
                self.assertFalse(output.exists())

    def test_missing_api_key_rejects_before_client(self):
        client = Mock()
        output = self.assert_rejected_before_client(client, api_key=" ")
        self.assertFalse(output.exists())

    def test_api_key_present_in_prompt_rejects_before_client(self):
        client = Mock(return_value=DeepSeekResult("test-model", {"findings": []}))
        output = self.assert_rejected_before_client(client, api_key="broken")
        self.assertFalse(output.exists())

    def test_missing_usage_is_recorded_as_null_token_fields(self):
        client = Mock(return_value=DeepSeekResult("test-model", {"findings": []}))

        summary, output_dir = self.run_with(client=client)

        record = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(record["usage"], {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        })

    def test_dirty_target_checkout_rejects_before_client(self):
        (self.fixture.repo / "untracked.py").write_text("value = 1\n", encoding="utf-8")
        client = Mock()
        output = self.assert_rejected_before_client(client)
        self.assertFalse(output.exists())

    def test_target_head_mismatch_rejects_before_client(self):
        subprocess.run(
            ["git", "-C", str(self.fixture.repo), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "Moved HEAD"],
            check=True,
        )
        client = Mock()
        output = self.assert_rejected_before_client(client)
        self.assertFalse(output.exists())

    def test_existing_output_directory_rejects_before_client(self):
        output = self.output_root / "rejected"
        output.mkdir()
        (output / "keep.txt").write_text("keep", encoding="utf-8")
        client = Mock()
        self.assert_rejected_before_client(client)
        self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_provider_error_is_recorded_without_raw_error_and_stops_after_one_call(self):
        client = Mock(side_effect=DeepSeekError(API_KEY))

        summary, output_dir = self.run_with(client=client)

        self.assertEqual(client.call_count, 1)
        self.assertEqual(summary["state"], "partial")
        self.assertEqual(summary["attempted_calls"], 1)
        self.assertEqual(summary["completed_calls"], 1)
        record = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(record["status"], "provider_error")
        self.assertNotIn(API_KEY, json.dumps(record))
        self.assertEqual(record["error"], "provider_error")
        self.assertEqual(record.get("error_code"), "unknown")
        self.assertIsNone(record.get("http_status"))

    def test_invalid_response_is_recorded_and_stops_after_one_call(self):
        client = Mock(return_value=DeepSeekResult("test-model", {"bad": []}))

        summary, output_dir = self.run_with(client=client)

        self.assertEqual(client.call_count, 1)
        self.assertEqual(summary["state"], "partial")
        record = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(record["status"], "invalid_response")
        self.assertEqual(record["error"], "invalid_response")

    def test_client_protocol_error_is_classified_as_invalid_response(self):
        error = DeepSeekError("DeepSeek response content was not valid JSON")
        error.code = "invalid_response"
        client = Mock(side_effect=error)

        summary, output_dir = self.run_with(client=client)

        self.assertEqual(client.call_count, 1)
        self.assertEqual(summary["state"], "partial")
        record = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(record["status"], "invalid_response")
        self.assertEqual(record["error"], "invalid_response")
        self.assertEqual(record.get("error_code"), "invalid_response")
        self.assertIsNone(record.get("http_status"))

    def test_error_message_does_not_determine_the_failure_category(self):
        client = Mock(side_effect=DeepSeekError("DeepSeek response content was not valid JSON"))

        summary, output_dir = self.run_with(client=client)

        record = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(record["status"], "provider_error")
        self.assertEqual(record.get("error_code"), "unknown")

    def test_http_error_record_contains_only_safe_code_and_status(self):
        error = DeepSeekError(f"private body {API_KEY}")
        error.code = "http"
        error.http_status = 429
        client = Mock(side_effect=error)

        summary, output_dir = self.run_with(client=client)

        record = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(record["status"], "provider_error")
        self.assertEqual(record["error"], "provider_error")
        self.assertEqual(record.get("error_code"), "http")
        self.assertEqual(record.get("http_status"), 429)
        self.assertNotIn(API_KEY, json.dumps(record))
        self.assertNotIn("private body", json.dumps(record))

    def test_custom_exception_uses_unknown_code_without_persisting_message(self):
        client = Mock(side_effect=RuntimeError(API_KEY))

        summary, output_dir = self.run_with(client=client)

        record = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(record["status"], "provider_error")
        self.assertEqual(record.get("error_code"), "unknown")
        self.assertIsNone(record.get("http_status"))
        self.assertNotIn(API_KEY, json.dumps(record))

    def test_keyboard_interrupt_marks_run_partial_and_preserves_inflight_marker(self):
        client = Mock(side_effect=KeyboardInterrupt)
        output_dir = self.output_root / "interrupted"

        with patch("tools.diagnosis_runner._analyzer_snapshot", return_value=(ANALYZER_COMMIT, False)):
            with self.assertRaises(KeyboardInterrupt):
                run_cases(
                    self.plan, self.contexts, self.fixture.repos_root,
                    repeats=1, max_calls=2, api_key=API_KEY,
                    client=client, output_dir=output_dir,
                    manifest=self.manifest,
                    manifest_sha256=self.manifest_sha256,
                )

        client.assert_called_once()
        summary = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["state"], "partial")
        self.assertEqual(summary["attempted_calls"], 1)
        self.assertEqual(summary["completed_calls"], 0)
        self.assertEqual(summary["record_files"], [])
        self.assertEqual(len(list((output_dir / ".inflight").glob("*.json"))), 1)

    def test_interrupt_after_record_publish_reconciles_summary_before_exit(self):
        from tools import diagnosis_runner

        client = Mock(return_value=DeepSeekResult("test-model", {"findings": []}))
        output_dir = self.output_root / "record-published"
        write_json_atomic = diagnosis_runner._write_json_atomic

        def interrupt_after_record(path, value):
            write_json_atomic(path, value)
            if path.parent.name == "records":
                raise KeyboardInterrupt

        with patch("tools.diagnosis_runner._analyzer_snapshot", return_value=(ANALYZER_COMMIT, False)):
            with patch("tools.diagnosis_runner._write_json_atomic", side_effect=interrupt_after_record):
                with self.assertRaises(KeyboardInterrupt):
                    run_cases(
                        self.plan, self.contexts, self.fixture.repos_root,
                        repeats=1, max_calls=2, api_key=API_KEY,
                        client=client, output_dir=output_dir,
                        manifest=self.manifest,
                        manifest_sha256=self.manifest_sha256,
                    )

        client.assert_called_once()
        summary = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["state"], "partial")
        self.assertEqual(summary["attempted_calls"], 1)
        self.assertEqual(summary["completed_calls"], 1)
        self.assertEqual(summary["record_files"], ["records/bug-01-r1.json"])
        self.assertTrue((output_dir / summary["record_files"][0]).is_file())
        self.assertEqual(list((output_dir / ".inflight").glob("*.json")), [])

    def test_rejected_findings_are_valid_results_and_do_not_stop_next_case(self):
        client = Mock(side_effect=[
            DeepSeekResult("test-model", {"findings": [{}]}),
            DeepSeekResult("test-model", {"findings": []}),
        ])

        summary, output_dir = self.run_with(client=client)

        self.assertEqual(client.call_count, 2)
        self.assertEqual(summary["state"], "complete")
        first = json.loads((output_dir / summary["record_files"][0]).read_text())
        self.assertEqual(first["status"], "success")
        self.assertEqual(len(first["rejected"]), 1)


if __name__ == "__main__":
    unittest.main()
