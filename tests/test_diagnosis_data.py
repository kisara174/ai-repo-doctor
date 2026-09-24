import hashlib
import json
import subprocess
import tempfile
import tokenize
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_doctor.diagnosis import build_diagnosis_prompts
from tools.diagnosis_data import EvaluationDataError, prepare_cases, validate_manifest


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def source_hash(path, start, end):
    with tokenize.open(path) as stream:
        lines = stream.read().splitlines()
    return hashlib.sha256("\n".join(lines[start - 1:end]).encode("utf-8")).hexdigest()


class DiagnosisDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repos_root = self.root / "repos"
        self.repo = self.repos_root / "fixture"
        self.repo.mkdir(parents=True)
        self.source = self.repo / "app.py"
        self.source.write_text(
            "def unrelated():\n"
            "    return 42\n\n"
            "def broken():\n"
            "    return 1 / 0\n",
            encoding="utf-8",
        )
        git(self.repo, "init", "-q")
        git(self.repo, "add", "app.py")
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "-qm", "Fixture"],
            check=True,
        )
        self.commit = git(self.repo, "rev-parse", "HEAD")
        self.manifest = self.make_manifest()

    def tearDown(self):
        self.temporary.cleanup()

    def make_manifest(self, *, file="app.py", symbol="app.py::broken", commit=None, digest=None):
        return {
            "schema_version": 1,
            "dataset_id": "diagnosis-v1",
            "cases": [{
                "id": "bug-01",
                "pair_id": None,
                "repository_url": "https://github.com/example/fixture",
                "checkout_id": "fixture",
                "commit": commit or self.commit,
                "symbol": symbol,
                "label": "control",
                "issue_id": None,
                "source": {
                    "file": file,
                    "start_line": 4,
                    "end_line": 5,
                    "sha256": digest or source_hash(self.source, 4, 5),
                },
                "ground_truth": "GROUND_TRUTH_SENTINEL: fixture diagnosis only",
                "references": ["https://github.com/example/fixture/issues/1"],
                "annotation": {
                    "reviewer": "fixture reviewer",
                    "reviewed_at": "2026-09-24T00:00:00Z",
                    "status": "approved",
                },
            }],
        }

    def test_prepare_builds_context_without_labels_or_network(self):
        with patch("urllib.request.OpenerDirector.open") as open_request:
            prepared = prepare_cases(self.manifest, self.repos_root, "test-model", 120)

        context = prepared["contexts"]["bug-01"]
        serialized = json.dumps(context, ensure_ascii=False)
        self.assertEqual(set(context), {"symbol", "blocks", "call_evidence"})
        self.assertEqual(context["symbol"], "app.py::broken")
        self.assertIn("return 1 / 0", serialized)
        self.assertNotIn("unrelated", serialized)
        self.assertNotIn("GROUND_TRUTH_SENTINEL", serialized)
        self.assertNotIn("ground_truth", serialized)
        self.assertEqual(prepared["plan"]["cases"][0]["source_lines"], 2)
        self.assertEqual(prepared["plan"]["cases"][0]["context_sha256"], hashlib.sha256(
            json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest())
        system_prompt, user_prompt = build_diagnosis_prompts(context)
        request = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "requested_model": "test-model",
            "max_tokens": 4096,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        expected_request_hash = hashlib.sha256(
            json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(prepared["plan"]["cases"][0]["request_sha256"], expected_request_hash)
        open_request.assert_not_called()

    def test_manifest_accepts_a_valid_local_fixture(self):
        validate_manifest(self.manifest)

    def test_manifest_accepts_github_source_permalink_fragments(self):
        manifest = self.make_manifest()
        manifest["cases"][0]["references"] = [
            "https://github.com/example/fixture/blob/" + self.commit + "/app.py#L4-L5"
        ]
        validate_manifest(manifest)

    def test_manifest_rejects_a_bug_without_its_fixed_pair(self):
        manifest = self.make_manifest()
        manifest["cases"][0]["label"] = "bug"
        manifest["cases"][0]["pair_id"] = "fixture-pair"
        manifest["cases"][0]["issue_id"] = "example#1"
        with self.assertRaisesRegex(EvaluationDataError, "pair"):
            validate_manifest(manifest)

    def test_manifest_accepts_one_bug_and_one_fixed_case_per_pair(self):
        manifest = self.make_manifest()
        bug = dict(manifest["cases"][0])
        fixed = dict(bug)
        bug.update({"label": "bug", "pair_id": "fixture-pair", "issue_id": "example#1"})
        fixed.update({
            "id": "fixed-01", "label": "fixed",
            "pair_id": "fixture-pair", "issue_id": "example#1",
        })
        manifest["cases"] = [bug, fixed]
        validate_manifest(manifest)

    def test_manifest_reports_malformed_url_as_a_validation_error(self):
        manifest = self.make_manifest()
        manifest["cases"][0]["repository_url"] = "https://["
        with self.assertRaisesRegex(EvaluationDataError, "URL"):
            validate_manifest(manifest)

    def test_prepare_rejects_a_checkout_at_the_wrong_head(self):
        manifest = self.make_manifest(commit="0" * 40)
        with self.assertRaisesRegex(EvaluationDataError, "commit"):
            prepare_cases(manifest, self.repos_root, "test-model", 120)

    def test_prepare_rejects_a_dirty_checkout(self):
        (self.repo / "app.py").write_text(self.source.read_text() + "# dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(EvaluationDataError, "clean"):
            prepare_cases(self.manifest, self.repos_root, "test-model", 120)

    def test_prepare_rejects_an_untracked_file(self):
        (self.repo / "untracked.py").write_text("value = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(EvaluationDataError, "clean"):
            prepare_cases(self.manifest, self.repos_root, "test-model", 120)

    def test_prepare_rejects_a_wrong_source_fingerprint(self):
        manifest = self.make_manifest(digest="0" * 64)
        with self.assertRaisesRegex(EvaluationDataError, "fingerprint"):
            prepare_cases(manifest, self.repos_root, "test-model", 120)

    def test_manifest_rejects_duplicate_case_ids(self):
        manifest = self.make_manifest()
        manifest["cases"].append(dict(manifest["cases"][0]))
        with self.assertRaisesRegex(EvaluationDataError, "duplicate"):
            validate_manifest(manifest)

    def test_manifest_rejects_parent_traversal_and_absolute_source_paths(self):
        for filename in ("../outside.py", str(self.source)):
            with self.subTest(filename=filename):
                manifest = self.make_manifest(file=filename)
                with self.assertRaisesRegex(EvaluationDataError, "path"):
                    validate_manifest(manifest)

    def test_prepare_rejects_a_tracked_symlink_escaping_the_checkout(self):
        outside = self.root / "outside.py"
        outside.write_text("def broken():\n    return 1 / 0\n", encoding="utf-8")
        (self.repo / "escaped.py").symlink_to(outside)
        git(self.repo, "add", "escaped.py")
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "-qm", "Symlink"],
            check=True,
        )
        manifest = self.make_manifest(
            file="escaped.py", symbol="escaped.py::broken",
            commit=git(self.repo, "rev-parse", "HEAD"),
            digest=source_hash(outside, 1, 2),
        )
        with self.assertRaisesRegex(EvaluationDataError, "source|symlink|Unsafe"):
            prepare_cases(manifest, self.repos_root, "test-model", 120)

    def test_prepare_rejects_unknown_symbols(self):
        manifest = self.make_manifest(symbol="app.py::missing")
        with self.assertRaisesRegex(EvaluationDataError, "Unknown symbol"):
            prepare_cases(manifest, self.repos_root, "test-model", 120)

    def test_prepare_rejects_ambiguous_symbols(self):
        self.source.write_text(
            "def broken():\n    return 1\n\ndef broken():\n    return 2\n",
            encoding="utf-8",
        )
        git(self.repo, "add", "app.py")
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "-qm", "Ambiguous"],
            check=True,
        )
        manifest = self.make_manifest(
            commit=git(self.repo, "rev-parse", "HEAD"),
            digest=source_hash(self.source, 4, 5),
        )
        with self.assertRaisesRegex(EvaluationDataError, "Ambiguous symbol"):
            prepare_cases(manifest, self.repos_root, "test-model", 120)

    def test_prepare_rejects_a_line_budget_above_the_fixed_limit(self):
        with self.assertRaisesRegex(EvaluationDataError, "120"):
            prepare_cases(self.manifest, self.repos_root, "test-model", 121)

    def test_prepare_rejects_an_empty_model(self):
        with self.assertRaisesRegex(EvaluationDataError, "model"):
            prepare_cases(self.manifest, self.repos_root, "", 120)


if __name__ == "__main__":
    unittest.main()
