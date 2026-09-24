"""Tests for the reproducible baseline evaluator."""

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from tools import evaluate_baseline


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "dataset_id": "baseline-v1",
        "repositories": [
            {
                "id": "fixture",
                "https_url": "https://example.com/fixture.git",
                "commit": "0" * 40,
                "probes": [
                    {
                        "id": "fixture-call-001",
                        "kind": "call",
                        "evidence": {
                            "file": "pkg/mod.py",
                            "start_line": 2,
                            "end_line": 3,
                            "sha256": "a" * 64,
                        },
                        "rationale": "The local helper is called directly.",
                        "caller": "pkg/mod.py::run",
                        "expression": "helper",
                        "expected_target": "pkg/mod.py::helper",
                    }
                ],
            }
        ],
    }


class ManifestTests(unittest.TestCase):
    def test_source_fingerprint_normalizes_selected_lines(self):
        source = "first\r\nselected one\r\nselected two\r\nlast\r\n"
        expected = hashlib.sha256(b"selected one\nselected two").hexdigest()
        fingerprint = getattr(evaluate_baseline, "source_fingerprint", None)
        self.assertTrue(callable(fingerprint), "source_fingerprint must be implemented")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text(source, encoding="utf-8", newline="")
            self.assertEqual(fingerprint(path, 2, 3), expected)

    def test_valid_call_manifest_passes_contract_validation(self):
        validate = getattr(evaluate_baseline, "validate_manifest_data", None)
        self.assertTrue(callable(validate), "validate_manifest_data must be implemented")

        self.assertIsNone(validate(_manifest()))

    def test_rejects_invalid_optional_expectation_fields(self):
        cases = {
            "invalid target type": {"expected_target": 17, "unresolved_reason": "dynamic"},
            "empty reason alongside target": {"expected_target": "pkg/mod.py::helper", "unresolved_reason": ""},
        }
        for name, updates in cases.items():
            with self.subTest(name=name):
                manifest = _manifest()
                probe = manifest["repositories"][0]["probes"][0]
                probe.update(updates)
                with self.assertRaises(evaluate_baseline.EvaluationError):
                    evaluate_baseline.validate_manifest_data(manifest)

    def test_rejects_unhashable_kind_and_state_as_input_errors(self):
        manifest = _manifest()
        probe = manifest["repositories"][0]["probes"][0]
        probe["kind"] = []
        with self.assertRaises(evaluate_baseline.EvaluationError):
            evaluate_baseline.validate_manifest_data(manifest)

        probe.update(
            kind="overload",
            symbol_id="pkg/mod.py::parse",
            expected_state=[],
            expected_signatures=["def parse(value: int) -> int"],
        )
        with self.assertRaises(evaluate_baseline.EvaluationError):
            evaluate_baseline.validate_manifest_data(manifest)

    def test_positive_registration_rejects_unresolved_reason(self):
        manifest = _manifest()
        probe = manifest["repositories"][0]["probes"][0]
        probe.update(
            kind="command_registration",
            parent_symbol="pkg/mod.py::cli",
            callback_symbol="pkg/mod.py::run",
            expect_edge=True,
            unresolved_reason="should be absent",
        )
        with self.assertRaises(evaluate_baseline.EvaluationError):
            evaluate_baseline.validate_manifest_data(manifest)

    def test_rejects_invalid_manifest_shapes_and_selectors(self):
        def duplicate_probe(manifest):
            manifest["repositories"][0]["probes"].append(
                deepcopy(manifest["repositories"][0]["probes"][0])
            )

        changes = {
            "wrong schema": lambda m: m.update(schema_version=2),
            "duplicate ID": duplicate_probe,
            "path traversal": lambda m: m["repositories"][0]["probes"][0]["evidence"].update(
                file="../../outside.py"
            ),
            "reversed range": lambda m: m["repositories"][0]["probes"][0]["evidence"].update(
                start_line=4, end_line=2
            ),
            "missing expression": lambda m: m["repositories"][0]["probes"][0].pop(
                "expression"
            ),
            "conflicting expectation": lambda m: m["repositories"][0]["probes"][0].update(
                unresolved_reason="dynamic"
            ),
            "missing expectation": lambda m: m["repositories"][0]["probes"][0].pop(
                "expected_target"
            ),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                manifest = _manifest()
                change(manifest)
                with self.assertRaises(evaluate_baseline.EvaluationError):
                    evaluate_baseline.validate_manifest_data(manifest)

    def test_evidence_validation_rejects_changed_content_and_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            source = root / "pkg" / "mod.py"
            source.parent.mkdir(parents=True)
            source.write_text("first\nsecond\n", encoding="utf-8")
            probe = _manifest()["repositories"][0]["probes"][0]
            probe["evidence"]["start_line"] = 2
            probe["evidence"]["end_line"] = 2
            probe["evidence"]["sha256"] = hashlib.sha256(b"second").hexdigest()

            self.assertIsNone(evaluate_baseline.validate_evidence(root, probe))
            source.write_text("first\nchanged\n", encoding="utf-8")
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.validate_evidence(root, probe)

            source.unlink()
            source.symlink_to(Path(directory) / "outside.py")
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.validate_evidence(root, probe)

    def test_load_manifest_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(_manifest()), encoding="utf-8")
            self.assertEqual(evaluate_baseline.load_manifest(path)["dataset_id"], "baseline-v1")
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.load_manifest(path)


if __name__ == "__main__":
    unittest.main()
