"""Tests for the reproducible baseline evaluator."""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

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

    def test_published_manifest_has_fixed_pins_and_minimum_probe_coverage(self):
        path = Path(__file__).resolve().parents[1] / "evaluation/baseline-v1.json"
        manifest = evaluate_baseline.load_manifest(path)
        evaluate_baseline.validate_baseline_pins(manifest)
        self.assertEqual([entry["id"] for entry in manifest["repositories"]],
                         ["click", "requests", "flask"])
        for entry in manifest["repositories"]:
            probes = entry["probes"]
            calls = [probe for probe in probes if probe["kind"] == "call"]
            self.assertGreaterEqual(sum("expected_target" in probe for probe in calls), 6)
            self.assertGreaterEqual(sum("unresolved_reason" in probe for probe in calls), 2)
            self.assertGreaterEqual(sum(probe["kind"] == "reexport"
                                        and "expected_target" in probe for probe in probes), 4)
            self.assertGreaterEqual(sum(probe["kind"] == "overload"
                                        and probe["expected_state"] == "resolved"
                                        for probe in probes), 3)
        registrations = [probe for probe in manifest["repositories"][0]["probes"]
                         if probe["kind"] == "command_registration"]
        self.assertGreaterEqual(sum(probe["expect_edge"] for probe in registrations), 5)
        self.assertGreaterEqual(sum(not probe["expect_edge"] for probe in registrations), 5)


class MetricTests(unittest.TestCase):
    def test_incorrect_target_counts_as_false_positive_and_false_negative(self):
        expected = {("probe-1", "call", "caller", "pkg.py::wanted")}
        predicted = {("probe-1", "call", "caller", "pkg.py::other")}

        self.assertEqual(
            evaluate_baseline._score(expected, predicted),
            {"tp": 0, "fp": 1, "fn": 1, "precision": 0.0, "recall": 0.0},
        )

    def test_perfect_match(self):
        relation = {("probe-1", "call", "caller", "pkg.py::wanted")}

        self.assertEqual(
            evaluate_baseline._score(relation, relation),
            {"tp": 1, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0},
        )

    def test_empty_sets_have_undefined_precision_and_recall(self):
        self.assertEqual(
            evaluate_baseline._score(set(), set()),
            {"tp": 0, "fp": 0, "fn": 0, "precision": None, "recall": None},
        )


class ProbeRelationsTests(unittest.TestCase):
    def test_call_probe_matches_its_unique_callsite(self):
        probe = _manifest()["repositories"][0]["probes"][0]
        scan = {
            "calls": [{
                "file": "pkg/mod.py", "caller": "pkg/mod.py::run", "expression": "helper",
                "name": "helper", "receiver": None, "line": 2,
            }],
            "call_edges": [{
                "caller": "pkg/mod.py::run", "callee": "pkg/mod.py::helper", "line": 2,
                "via_reexports": [],
            }],
            "semantic_edges": [],
            "symbols": [],
            "ambiguous_symbols": [],
        }
        relations = getattr(evaluate_baseline, "_probe_relations", None)
        self.assertTrue(callable(relations), "probe relation projection must be implemented")

        self.assertEqual(
            relations(probe, scan)["call"],
            (
                {("fixture-call-001", "call", "pkg/mod.py::run", "pkg/mod.py::helper")},
                {("fixture-call-001", "call", "pkg/mod.py::run", "pkg/mod.py::helper")},
            ),
        )

    def test_call_probe_rejects_two_expressions_on_one_line(self):
        probe = _manifest()["repositories"][0]["probes"][0]
        caller = probe["caller"]
        scan = {
            "calls": [
                {"file": "pkg/mod.py", "caller": caller, "line": 2, "expression": "helper"},
                {"file": "pkg/mod.py", "caller": caller, "line": 2, "expression": "wrapper"},
            ],
            "call_edges": [{"caller": caller, "line": 2, "callee": "pkg/mod.py::helper"}],
        }
        with self.assertRaisesRegex(evaluate_baseline.EvaluationError, "fixture-call-001"):
            evaluate_baseline._probe_relations(probe, scan)

    def test_expected_unresolved_call_counts_unexpected_edge_as_fp(self):
        probe = _manifest()["repositories"][0]["probes"][0]
        probe["expression"] = "os.getcwd"
        probe["expected_target"] = None
        probe["unresolved_reason"] = "os is an external standard-library module."
        caller = probe["caller"]
        scan = {
            "calls": [{
                "file": "pkg/mod.py", "caller": caller, "line": 2,
                "expression": "os.getcwd",
            }],
            "call_edges": [{"caller": caller, "line": 2, "callee": "pkg/mod.py::getcwd"}],
        }
        expected, predicted = evaluate_baseline._probe_relations(probe, scan)["call"]
        self.assertEqual(expected, set())
        self.assertEqual(
            evaluate_baseline._score(expected, predicted),
            {"tp": 0, "fp": 1, "fn": 0, "precision": 0.0, "recall": None},
        )

    def test_reexport_probe_selects_one_name_on_shared_import_line(self):
        file = "src/requests/__init__.py"
        probe = {
            "id": "requests-reexport-get", "kind": "reexport",
            "evidence": {"file": file, "start_line": 171, "end_line": 171, "sha256": "a" * 64},
            "rationale": "The package imports the local API function as get.",
            "exported_name": "get", "expected_target": "src/requests/api.py::get",
        }
        scan = {
            "calls": [], "call_edges": [], "symbols": [], "ambiguous_symbols": [],
            "semantic_edges": [
                {
                    "kind": "reexport", "target_symbol": "src/requests/api.py::get",
                    "evidence_file": file, "line": 171, "source_symbol": None,
                    "source_file": file, "exported_name": "get",
                },
                {
                    "kind": "reexport", "target_symbol": "src/requests/api.py::post",
                    "evidence_file": file, "line": 171, "source_symbol": None,
                    "source_file": file, "exported_name": "post",
                },
            ],
        }
        try:
            projected = evaluate_baseline._probe_relations(probe, scan)["reexport"]
        except evaluate_baseline.EvaluationError as exc:
            self.fail(f"valid re-export probe was rejected: {exc}")
        relation = (
            "requests-reexport-get", "reexport", file, "get", "src/requests/api.py::get"
        )
        self.assertEqual(projected, ({relation}, {relation}))

    def test_registration_compares_parent_and_callback_endpoints(self):
        file = "examples/repo/repo.py"
        parent = "examples/repo/repo.py::cli"
        callback = "examples/repo/repo.py::clone"
        probe = {
            "id": "click-registration-clone", "kind": "command_registration",
            "evidence": {"file": file, "start_line": 60, "end_line": 60, "sha256": "a" * 64},
            "rationale": "The cli group registers clone.",
            "parent_symbol": parent, "callback_symbol": callback, "expect_edge": True,
        }
        scan = {
            "calls": [], "call_edges": [], "symbols": [], "ambiguous_symbols": [],
            "semantic_edges": [{
                "kind": "command_registration", "target_symbol": callback,
                "evidence_file": file, "line": 60, "source_symbol": parent,
                "source_file": None, "exported_name": None,
            }],
        }
        try:
            projected = evaluate_baseline._probe_relations(probe, scan)["command_registration"]
        except evaluate_baseline.EvaluationError as exc:
            self.fail(f"valid registration probe was rejected: {exc}")
        relation = ("click-registration-clone", "command_registration", parent, callback)
        self.assertEqual(projected, ({relation}, {relation}))

    def test_non_command_decorator_does_not_register_callback(self):
        file = "examples/repo/repo.py"
        probe = {
            "id": "click-option-clone", "kind": "command_registration",
            "evidence": {"file": file, "start_line": 61, "end_line": 61, "sha256": "a" * 64},
            "rationale": "The decorator only declares an argument.",
            "parent_symbol": "examples/repo/repo.py::cli",
            "callback_symbol": "examples/repo/repo.py::clone",
            "expect_edge": False, "unresolved_reason": "@click.argument is not group registration.",
        }
        scan = {
            "semantic_edges": [{
                "kind": "command_registration", "evidence_file": file, "line": 61,
                "source_symbol": "examples/repo/repo.py::cli",
                "target_symbol": "examples/repo/repo.py::clone",
            }],
        }
        expected, predicted = evaluate_baseline._probe_relations(probe, scan)[
            "command_registration"
        ]
        self.assertEqual(expected, set())
        self.assertEqual(evaluate_baseline._score(expected, predicted)["fp"], 1)

    def test_overload_resolution_and_signatures_are_separate(self):
        symbol = "src/click/core.py::Context.invoke"
        signatures = [
            "def invoke(self, callback: t.Callable[..., V], /, *args: t.Any, **kwargs: t.Any) -> V",
            "def invoke(self, callback: Command, /, *args: t.Any, **kwargs: t.Any) -> t.Any",
        ]
        probe = {
            "id": "click-overload-invoke", "kind": "overload",
            "evidence": {
                "file": "src/click/core.py", "start_line": 875, "end_line": 883,
                "sha256": "a" * 64,
            },
            "rationale": "Two overload declarations precede one concrete implementation.",
            "symbol_id": symbol, "expected_state": "resolved",
            "expected_signatures": signatures,
        }
        scan = {
            "calls": [], "call_edges": [], "semantic_edges": [], "ambiguous_symbols": [],
            "symbols": [{
                "id": symbol, "file": "src/click/core.py", "name": "invoke",
                "qualname": "Context.invoke", "kind": "method", "start_line": 883,
                "end_line": 940, "parent": "src/click/core.py::Context",
                "decorators": [], "overloads": [
                    {"start_line": 875, "end_line": 878, "signature": signatures[0]},
                    {"start_line": 880, "end_line": 881, "signature": signatures[1]},
                ],
            }],
        }
        try:
            projected = evaluate_baseline._probe_relations(probe, scan)
        except evaluate_baseline.EvaluationError as exc:
            self.fail(f"valid overload probe was rejected: {exc}")
        self.assertEqual(
            projected["overload_resolution"],
            ({("click-overload-invoke", "overload_resolution", symbol, symbol)},
             {("click-overload-invoke", "overload_resolution", symbol, symbol)}),
        )
        expected_signatures = {
            ("click-overload-invoke", "overload_signature", symbol, signature)
            for signature in signatures
        }
        self.assertEqual(projected["overload_signature"],
                         (expected_signatures, expected_signatures))

    def test_ambiguous_overload_rejects_false_unique_implementation(self):
        symbol = "app.py::parse"
        probe = {
            "id": "ambiguous-parse", "kind": "overload",
            "evidence": {"file": "app.py", "start_line": 1, "end_line": 4,
                         "sha256": "a" * 64},
            "rationale": "There are two concrete definitions.",
            "symbol_id": symbol, "expected_state": "ambiguous", "expected_signatures": [],
        }
        scan = {
            "symbols": [{"id": symbol, "overloads": []}],
            "ambiguous_symbols": [],
        }
        relation = evaluate_baseline._probe_relations(probe, scan)["overload_resolution"]
        self.assertEqual(relation[0], set())
        self.assertEqual(evaluate_baseline._score(*relation)["fp"], 1)

    def test_overload_only_group_stays_ambiguous(self):
        symbol = "app.py::parse"
        probe = {
            "id": "overload-only-parse", "kind": "overload",
            "evidence": {"file": "app.py", "start_line": 1, "end_line": 2,
                         "sha256": "a" * 64},
            "rationale": "Only overload declarations exist.",
            "symbol_id": symbol, "expected_state": "ambiguous", "expected_signatures": [],
        }
        scan = {
            "symbols": [{"id": symbol, "overloads": [{"signature": "def parse(x: int) -> int"}]}],
            "ambiguous_symbols": [symbol],
        }
        projected = evaluate_baseline._probe_relations(probe, scan)
        self.assertEqual(projected["overload_resolution"], (set(), set()))
        self.assertEqual(projected["overload_signature"], (set(), set()))

    def test_wrong_overload_signature_is_fp_and_fn(self):
        symbol = "app.py::parse"
        probe = {
            "id": "wrong-signature-parse", "kind": "overload",
            "evidence": {"file": "app.py", "start_line": 1, "end_line": 3,
                         "sha256": "a" * 64},
            "rationale": "The declaration accepts an integer.",
            "symbol_id": symbol, "expected_state": "resolved",
            "expected_signatures": ["def parse(x: int) -> int"],
        }
        scan = {
            "symbols": [{"id": symbol, "overloads": [{"signature": "def parse(x: str) -> str"}]}],
            "ambiguous_symbols": [],
        }
        projected = evaluate_baseline._probe_relations(probe, scan)
        self.assertEqual(evaluate_baseline._score(*projected["overload_resolution"])["tp"], 1)
        self.assertEqual(
            evaluate_baseline._score(*projected["overload_signature"]),
            {"tp": 0, "fp": 1, "fn": 1, "precision": 0.0, "recall": 0.0},
        )


class SnapshotTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    def test_snapshot_requires_exact_commit_and_clean_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            self._git(root, "init", "-q")
            self._git(root, "config", "user.name", "Baseline Test")
            self._git(root, "config", "user.email", "baseline@example.invalid")
            source = root / "app.py"
            source.write_text("def run():\n    return 1\n", encoding="utf-8")
            self._git(root, "add", "app.py")
            self._git(root, "commit", "-qm", "Fixture")
            commit = self._git(root, "rev-parse", "HEAD")

            validate = getattr(evaluate_baseline, "validate_snapshot", None)
            self.assertTrue(callable(validate), "Git snapshot validation must be implemented")
            self.assertIsNone(validate(root, commit))
            with self.assertRaises(evaluate_baseline.EvaluationError):
                validate(root, "f" * 40)
            source.write_text("def run():\n    return 2\n", encoding="utf-8")
            with self.assertRaises(evaluate_baseline.EvaluationError):
                validate(root, commit)
            source.write_text("def run():\n    return 1\n", encoding="utf-8")
            (root / "new.py").write_text("value = 1\n", encoding="utf-8")
            with self.assertRaises(evaluate_baseline.EvaluationError):
                validate(root, commit)

    def test_scanner_subprocess_does_not_execute_target_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            marker = Path(directory) / "executed.txt"
            (root / "app.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed')\n"
                "def run():\n    return 1\n",
                encoding="utf-8",
            )
            scan_repository = getattr(evaluate_baseline, "scan_repository", None)
            self.assertTrue(callable(scan_repository), "CLI scanner wrapper must be implemented")

            scan, elapsed = scan_repository(Path(__file__).resolve().parents[1], root)
            self.assertEqual(scan["schema_version"], 2)
            self.assertEqual(scan["stats"]["python_files"], 1)
            self.assertGreaterEqual(elapsed, 0)
            self.assertFalse(marker.exists())

    def test_scan_digest_is_independent_of_json_key_order(self):
        digest = getattr(evaluate_baseline, "canonical_scan_digest", None)
        self.assertTrue(callable(digest), "canonical scan hashing must be implemented")
        first = {"schema_version": 2, "stats": {"python_files": 1}, "calls": []}
        reordered = {"calls": [], "stats": {"python_files": 1}, "schema_version": 2}
        changed = {"schema_version": 2, "stats": {"python_files": 2}, "calls": []}
        self.assertEqual(digest(first), digest(reordered))
        self.assertNotEqual(digest(first), digest(changed))

    def test_repeated_scans_require_identical_hashes(self):
        scan = {"schema_version": 2, "stats": {"python_files": 1}}
        changed = {"schema_version": 2, "stats": {"python_files": 2}}
        entry = {"id": "fixture", "commit": "0" * 40, "probes": []}
        with patch.object(evaluate_baseline, "scan_repository",
                          side_effect=[(scan, 0.1), (changed, 0.2)]) as scanner:
            with self.assertRaisesRegex(evaluate_baseline.EvaluationError, "unstable"):
                evaluate_baseline.evaluate_snapshot(entry, Path("/tmp/repo"),
                                                    Path("/tmp/project"), 2)
        self.assertEqual(scanner.call_count, 2)

        with patch.object(evaluate_baseline, "scan_repository",
                          side_effect=[(scan, 0.1), (deepcopy(scan), 0.2)]):
            result = evaluate_baseline.evaluate_snapshot(
                entry, Path("/tmp/repo"), Path("/tmp/project"), 2
            )
        self.assertEqual(result["scan"], scan)
        self.assertEqual(result["durations_seconds"], [0.1, 0.2])
        self.assertEqual(result["scan_hashes"],
                         [evaluate_baseline.canonical_scan_digest(scan)] * 2)

    def test_repeated_scans_reject_nonpositive_count(self):
        with patch.object(evaluate_baseline, "scan_repository") as scanner:
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.evaluate_snapshot(
                    {"id": "fixture"}, Path("/tmp/repo"), Path("/tmp/project"), 0
                )
            scanner.assert_not_called()

    def test_repeated_scans_reject_ambiguous_call_probe(self):
        entry = {"id": "fixture", "probes": [{
            "id": "call-1", "kind": "call", "caller": "app.py::run",
            "expression": "helper", "expected_target": "app.py::helper",
            "evidence": {"file": "app.py", "start_line": 2},
        }]}
        scan = {"calls": [
            {"file": "app.py", "caller": "app.py::run", "line": 2,
             "expression": "helper"},
            {"file": "app.py", "caller": "app.py::run", "line": 2,
             "expression": "other"},
        ]}
        with patch.object(evaluate_baseline, "scan_repository", return_value=(scan, 0.1)):
            with self.assertRaisesRegex(evaluate_baseline.EvaluationError, "call-1"):
                evaluate_baseline.evaluate_snapshot(entry, Path("/tmp/repo"),
                                                    Path("/tmp/project"), 1)

    def test_preflight_checks_every_repo_and_evidence_before_scanning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = []
            for repo_id in ("first", "second"):
                repo = root / repo_id
                repo.mkdir()
                self._git(repo, "init", "-q")
                self._git(repo, "config", "user.name", "Baseline Test")
                self._git(repo, "config", "user.email", "baseline@example.invalid")
                source = repo / "app.py"
                source.write_text("def run():\n    return 1\n", encoding="utf-8")
                self._git(repo, "add", "app.py")
                self._git(repo, "commit", "-qm", "Fixture")
                entries.append({
                    "id": repo_id,
                    "https_url": f"https://example.com/{repo_id}.git",
                    "commit": self._git(repo, "rev-parse", "HEAD"),
                    "probes": [{
                        "id": f"{repo_id}-call", "kind": "call",
                        "evidence": {"file": "app.py", "start_line": 1, "end_line": 2,
                                     "sha256": evaluate_baseline.source_fingerprint(source, 1, 2)},
                        "rationale": "A source anchored fixture probe.",
                        "caller": "app.py::run", "expression": "helper",
                        "expected_target": "app.py::helper",
                    }],
                })
            manifest = {"schema_version": 1, "dataset_id": "baseline-v1",
                        "repositories": entries}
            self.assertEqual(
                evaluate_baseline.preflight_repositories(manifest, root),
                {repo_id: root / repo_id for repo_id in ("first", "second")},
            )
            entries[1]["probes"][0]["evidence"]["sha256"] = "f" * 64
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.preflight_repositories(manifest, root)
            entries[1]["probes"][0]["evidence"]["sha256"] = \
                evaluate_baseline.source_fingerprint(root / "second" / "app.py", 1, 2)
            entries[1]["commit"] = "f" * 40
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.preflight_repositories(manifest, root)

    def test_scanner_rejects_nonzero_and_wrong_schema(self):
        from subprocess import CompletedProcess

        repo = Path("/tmp/target")
        project = Path("/tmp/project")
        with patch.object(evaluate_baseline.subprocess, "run",
                          return_value=CompletedProcess([], 4, "", "failure")) as run:
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.scan_repository(project, repo)
            args, kwargs = run.call_args
            self.assertEqual(args[0], [evaluate_baseline.sys.executable, "-m",
                                       "repo_doctor", "scan", str(repo), "--json"])
            self.assertFalse(kwargs["shell"])
        with patch.object(evaluate_baseline.subprocess, "run",
                          return_value=CompletedProcess([], 0, '{"schema_version": 1}', "")):
            with self.assertRaises(evaluate_baseline.EvaluationError):
                evaluate_baseline.scan_repository(project, repo)


class ReportTests(unittest.TestCase):
    def test_report_keeps_relation_families_separate(self):
        entry = {"id": "fixture", "https_url": "https://example.com/repo.git",
                 "commit": "a" * 40, "probes": [
                     {"id": "call-1", "kind": "call", "caller": "app.py::run",
                      "expression": "helper", "expected_target": "app.py::helper",
                      "rationale": "The helper call resolves locally.",
                      "evidence": {"file": "app.py", "start_line": 2}},
                     {"id": "registration-1", "kind": "command_registration",
                      "parent_symbol": "app.py::group", "callback_symbol": "app.py::run",
                      "expect_edge": False,
                      "rationale": "This decorator does not register a command.",
                      "evidence": {"file": "app.py", "start_line": 3}},
                 ]}
        scan = {"stats": {"python_files": 1, "unresolved_calls": 23},
                "calls": [{"file": "app.py", "caller": "app.py::run", "line": 2,
                           "expression": "helper"}],
                "call_edges": [{"caller": "app.py::run", "line": 2,
                                "callee": "app.py::helper"}],
                "semantic_edges": [{"kind": "command_registration", "evidence_file": "app.py",
                                    "line": 3, "source_symbol": "app.py::group",
                                    "target_symbol": "app.py::run"}],
                "symbols": [], "ambiguous_symbols": []}
        manifest = {"schema_version": 1, "dataset_id": "baseline-v1",
                    "repositories": [entry]}
        results = [{"entry": entry, "scan": scan,
                    "durations_seconds": [0.1, 0.2], "scan_hashes": ["abc", "abc"]}]
        report = evaluate_baseline.build_report(manifest, results, "b" * 40, 2)
        repository = report["repositories"][0]
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(repository["metrics"]["call"]["tp"], 1)
        self.assertEqual(repository["metrics"]["call"]["fp"], 0)
        self.assertEqual(repository["metrics"]["call"]["positive_probes"], 1)
        self.assertEqual(repository["metrics"]["command_registration"]["fp"], 1)
        self.assertEqual(repository["metrics"]["command_registration"]["negative_probes"], 1)
        self.assertEqual(repository["metrics"]["reexport"]["status"], "not_sampled")
        self.assertAlmostEqual(repository["timing"]["median_seconds"], 0.15)
        self.assertEqual(repository["probes"][1]["relations"]["command_registration"][
            "fp"], [["registration-1", "command_registration", "app.py::group",
                     "app.py::run"]])
        markdown = evaluate_baseline.render_markdown(report)
        self.assertIn("registration-1", markdown)
        self.assertIn("not_sampled", markdown)
        self.assertTrue(all(line == line.rstrip() for line in markdown.splitlines()))

    def test_cli_rejects_invalid_runs_and_preserves_outputs_on_preflight_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_out = root / "report.json"
            markdown_out = root / "report.md"
            json_out.write_text("old JSON", encoding="utf-8")
            markdown_out.write_text("old Markdown", encoding="utf-8")
            args = ["--repos-root", str(root / "missing"), "--json-out", str(json_out),
                    "--markdown-out", str(markdown_out)]
            with patch.object(evaluate_baseline, "scan_repository") as scanner:
                self.assertEqual(evaluate_baseline.main([*args, "--runs", "0"]), 2)
                self.assertEqual(evaluate_baseline.main(args), 2)
                scanner.assert_not_called()
            self.assertEqual(json_out.read_text(encoding="utf-8"), "old JSON")
            self.assertEqual(markdown_out.read_text(encoding="utf-8"), "old Markdown")
            self.assertEqual(evaluate_baseline.main([
                "--repos-root", str(root), "--json-out", str(json_out),
                "--markdown-out", str(json_out),
            ]), 2)

    def test_two_report_replacement_rolls_back_first_on_second_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "result.json"
            second = root / "result.md"
            first.write_text("old JSON", encoding="utf-8")
            second.write_text("old Markdown", encoding="utf-8")
            replace = os.replace
            count = 0

            def fail_second(source, destination):
                nonlocal count
                count += 1
                if count == 2:
                    raise OSError("simulated second-output failure")
                return replace(source, destination)

            with patch.object(evaluate_baseline.os, "replace", side_effect=fail_second):
                with self.assertRaises(OSError):
                    evaluate_baseline._write_reports([
                        (first, "new JSON"), (second, "new Markdown")
                    ])
            self.assertEqual(first.read_text(encoding="utf-8"), "old JSON")
            self.assertEqual(second.read_text(encoding="utf-8"), "old Markdown")
            self.assertEqual(sorted(path.name for path in root.iterdir()),
                             ["result.json", "result.md"])


if __name__ == "__main__":
    unittest.main()
