import copy
import hashlib
import json
import subprocess
import tempfile
import tokenize
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_doctor.diagnosis import build_diagnosis_prompts
from repo_doctor.deepseek import _serialize_schema_request_body
from repo_doctor.index import build_index
from tools.diagnosis_data import (
    EvaluationDataError,
    _source_fingerprint,
    prepare_cases,
    validate_manifest,
)


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
        self.analyzer_commit = "a" * 40
        self._analyzer_patcher = patch(
            "tools.diagnosis_data._analyzer_commit", return_value=self.analyzer_commit
        )
        self._analyzer_patcher.start()
        self.repos_root = self.root / "repos"
        self.repo = self.repos_root / "fixture"
        self.repo.mkdir(parents=True)
        self.source = self.repo / "app.py"
        self.source.write_text(
            "def unrelated():\n"
            "    return 42\n\n"
            "def broken():\n"
            "    return 1 / 0\n\n"
            "def supplement():\n"
            "    return 99\n",
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
        self._analyzer_patcher.stop()
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
        self.assertEqual(prepared["plan"]["analyzer_commit"], self.analyzer_commit)
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
        self.assertNotIn("thinking_mode", prepared["plan"])
        open_request.assert_not_called()

    def test_prepare_includes_only_manifest_selected_supplement_and_records_it(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["dataset_id"] = "diagnosis-werkzeug-explicit-context-v1"
        manifest["cases"][0]["include_symbols"] = ["app.py::supplement"]

        prepared = prepare_cases(manifest, self.repos_root, "test-model", 120)
        selected = prepared["contexts"]["bug-01"]["blocks"]
        self.assertEqual(
            [(block["symbol"], block["relation"]) for block in selected],
            [("app.py::broken", "target"), ("app.py::supplement", "user_selected")],
        )
        self.assertEqual(
            prepared["plan"]["cases"][0]["include_symbols"],
            ["app.py::supplement"],
        )
        self.assertEqual(prepared["plan"]["dataset_id"], manifest["dataset_id"])

        default = prepare_cases(self.manifest, self.repos_root, "test-model", 120)
        self.assertNotIn("include_symbols", default["plan"]["cases"][0])
        self.assertEqual(
            [block["symbol"] for block in default["contexts"]["bug-01"]["blocks"]],
            ["app.py::broken"],
        )

    def test_click_explicit_dataset_id_is_exact(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["dataset_id"] = "diagnosis-click-explicit-context-v1"
        validate_manifest(manifest)
        manifest["dataset_id"] = "diagnosis-click-explicit-context-v2"
        with self.assertRaises(EvaluationDataError):
            validate_manifest(manifest)

    def test_manifest_rejects_invalid_include_symbols(self):
        for extras in (
            [], ["app.py::supplement", "app.py::supplement"],
            ["app.py::broken"], ["../outside.py::x"], ["app.py"],
        ):
            with self.subTest(extras=extras):
                manifest = copy.deepcopy(self.manifest)
                manifest["cases"][0]["include_symbols"] = extras
                with self.assertRaisesRegex(EvaluationDataError, "include_symbols"):
                    validate_manifest(manifest)

    def test_prepare_rejects_unknown_include_symbol(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["cases"][0]["include_symbols"] = ["app.py::missing"]
        with self.assertRaisesRegex(EvaluationDataError, "Unknown symbol"):
            prepare_cases(manifest, self.repos_root, "test-model", 120)

    def test_prepare_rejects_ambiguous_include_symbol(self):
        self.source.write_text(
            "def unrelated():\n    return 42\n\n"
            "def broken():\n    return 1 / 0\n\n"
            "def supplement():\n    return 99\n\n"
            "def supplement():\n    return 100\n",
            encoding="utf-8",
        )
        git(self.repo, "add", "app.py")
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "-qm", "Ambiguous supplement"],
            check=True,
        )
        manifest = copy.deepcopy(self.manifest)
        manifest["cases"][0]["commit"] = git(self.repo, "rev-parse", "HEAD")
        manifest["cases"][0]["include_symbols"] = ["app.py::supplement"]

        with self.assertRaisesRegex(EvaluationDataError, "Ambiguous symbol"):
            prepare_cases(manifest, self.repos_root, "test-model", 120)

    def test_schema_prepare_fingerprints_exact_responses_body_offline(self):
        with patch("urllib.request.OpenerDirector.open") as open_request:
            prepared = prepare_cases(
                self.manifest, self.repos_root, "test-model", 120,
                response_format="json-schema",
            )

        plan = prepared["plan"]
        self.assertEqual(plan["schema_version"], 2)
        self.assertEqual(plan["response_format"], "json-schema")
        self.assertNotIn("thinking_mode", plan)
        prompts = build_diagnosis_prompts(prepared["contexts"]["bug-01"])
        wire = _serialize_schema_request_body(*prompts, "test-model")
        self.assertEqual(json.loads(wire)["text"]["format"]["type"], "json_schema")
        self.assertEqual(
            plan["cases"][0]["request_sha256"], hashlib.sha256(wire).hexdigest()
        )
        open_request.assert_not_called()

    def test_schema_prepare_rejects_incompatible_thinking_and_unknown_format(self):
        with self.assertRaises(EvaluationDataError):
            prepare_cases(
                self.manifest, self.repos_root, "test-model", 120,
                response_format="json-schema", thinking_mode="disabled",
            )
        with self.assertRaises(EvaluationDataError):
            prepare_cases(
                self.manifest, self.repos_root, "test-model", 120,
                response_format="unknown",
            )

    def test_prepare_explicit_thinking_mode_is_fingerprinted_in_plan(self):
        prepared = prepare_cases(
            self.manifest,
            self.repos_root,
            "test-model",
            120,
            thinking_mode="disabled",
        )

        self.assertEqual(prepared["plan"]["thinking_mode"], "disabled")
        system_prompt, user_prompt = build_diagnosis_prompts(prepared["contexts"]["bug-01"])
        request = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "requested_model": "test-model",
            "max_tokens": 4096,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }
        expected_hash = hashlib.sha256(
            json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(prepared["plan"]["cases"][0]["request_sha256"], expected_hash)

    def test_prepare_rejects_unsupported_thinking_mode(self):
        with self.assertRaises(EvaluationDataError):
            prepare_cases(
                self.manifest,
                self.repos_root,
                "test-model",
                120,
                thinking_mode="balanced",
            )

    def test_prepare_reuses_index_for_duplicate_snapshot_within_each_call(self):
        manifest = self.make_manifest()
        second_case = dict(manifest["cases"][0])
        second_case.update({
            "id": "control-02",
            "symbol": "app.py::unrelated",
            "source": {
                "file": "app.py",
                "start_line": 1,
                "end_line": 2,
                "sha256": source_hash(self.source, 1, 2),
            },
        })
        manifest["cases"].append(second_case)

        with (
            patch("tools.diagnosis_data.build_index", wraps=build_index) as index_builder,
            patch(
                "tools.diagnosis_data._source_fingerprint",
                wraps=_source_fingerprint,
            ) as source_fingerprint,
        ):
            first = prepare_cases(manifest, self.repos_root, "test-model", 120)
            second = prepare_cases(manifest, self.repos_root, "test-model", 120)

        self.assertEqual(index_builder.call_count, 2)
        self.assertEqual(source_fingerprint.call_count, 4)
        for prepared in (first, second):
            self.assertEqual(
                [case["id"] for case in prepared["plan"]["cases"]],
                ["bug-01", "control-02"],
            )
            self.assertEqual(
                list(prepared["contexts"]),
                ["bug-01", "control-02"],
            )
            self.assertEqual(
                [prepared["contexts"][case_id]["symbol"] for case_id in prepared["contexts"]],
                ["app.py::broken", "app.py::unrelated"],
            )

    def test_prepare_rejects_analyzer_head_change_after_generation(self):
        with patch(
            "tools.diagnosis_data._analyzer_commit",
            side_effect=[
                self.analyzer_commit,
                EvaluationDataError("analyzer commit changed during evaluation"),
            ],
        ) as analyzer_commit:
            with self.assertRaisesRegex(EvaluationDataError, "changed"):
                prepare_cases(self.manifest, self.repos_root, "test-model", 120)

        self.assertEqual(analyzer_commit.call_count, 2)

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

    def make_symptom_guided_manifest(self):
        pytest_symptom = (
            "When I ask pytest to collect a specific test file together with its "
            "containing directory, it collects only the file's test and misses "
            "other tests in that directory. Which code in the supplied context "
            "could explain this behavior?"
        )
        rich_symptom = (
            "In the terminal, `⬇️` and `⬆️` visually occupy two columns, but Rich "
            "lays out following text as though each occupies one; lines wrap or "
            "align incorrectly. Which code in the supplied context could explain "
            "this behavior?"
        )
        base = self.make_manifest()["cases"][0]

        def make_case(case_id, label, pair_id, repair, symptom=None):
            row = copy.deepcopy(base)
            row.update({
                "id": case_id,
                "pair_id": pair_id,
                "repository_url": "https://github.com/pytest-dev/pytest"
                if repair == "pytest-12083"
                else "https://github.com/Textualize/rich",
                "checkout_id": repair,
                "label": label,
                "issue_id": "12083" if repair == "pytest-12083" else "3897",
            })
            if symptom is not None:
                row["symptom"] = symptom
            return row

        return {
            "schema_version": 1,
            "dataset_id": "diagnosis-symptom-guided-v1",
            "cases": [
                make_case(
                    "pytest-blind-bug", "bug", "pytest-12083-blind", "pytest-12083"
                ),
                make_case(
                    "pytest-blind-fixed", "fixed", "pytest-12083-blind", "pytest-12083"
                ),
                make_case(
                    "pytest-symptom-bug", "bug", "pytest-12083-symptom", "pytest-12083",
                    symptom=pytest_symptom,
                ),
                make_case(
                    "pytest-symptom-fixed", "fixed", "pytest-12083-symptom", "pytest-12083",
                    symptom=pytest_symptom,
                ),
                make_case("rich-blind-bug", "bug", "rich-3897-blind", "rich-3897"),
                make_case("rich-blind-fixed", "fixed", "rich-3897-blind", "rich-3897"),
                make_case(
                    "rich-symptom-bug", "bug", "rich-3897-symptom", "rich-3897",
                    symptom=rich_symptom,
                ),
                make_case(
                    "rich-symptom-fixed", "fixed", "rich-3897-symptom", "rich-3897",
                    symptom=rich_symptom,
                ),
            ],
        }

    def make_symptom_guided_v2_manifest(self):
        previous = self.make_symptom_guided_manifest()
        previous_cases = previous["cases"]
        repairs = [
            (
                "pydantic",
                "https://github.com/pydantic/pydantic",
                "pydantic/pydantic#13520",
                "A generic model's defaults and type variables change behavior after an integration inspects annotations.",
            ),
            (
                "jinja",
                "https://github.com/pallets/jinja",
                "pallets/jinja#1921",
                "A very large scientific-notation string passed through the int filter raises OverflowError instead of returning the fallback.",
            ),
            (
                "black",
                "https://github.com/psf/black",
                "psf/black#4640",
                "Formatting a lambda with a standalone comment in a tuple default raises LookupError instead of returning formatted output.",
            ),
            (
                "typer",
                "https://github.com/fastapi/typer",
                "fastapi/typer discussion#1068",
                "With Rich installed, fish-shell completion descriptions contain escaped spaces and are malformed.",
            ),
        ]
        cases = []
        for repair, repository_url, issue_id, symptom in repairs:
            for previous_case, arm, label in zip(
                previous_cases[:4],
                ("blind", "blind", "symptom", "symptom"),
                ("bug", "fixed", "bug", "fixed"),
            ):
                case = copy.deepcopy(previous_case)
                case.update({
                    "id": f"{repair}-{arm}-{label}",
                    "pair_id": f"{repair}-{arm}",
                    "repository_url": repository_url,
                    "checkout_id": repair,
                    "issue_id": issue_id,
                })
                if arm == "symptom":
                    case["symptom"] = symptom
                cases.append(case)
        return {
            "schema_version": 1,
            "dataset_id": "diagnosis-symptom-guided-v2",
            "cases": cases,
        }

    def test_symptom_guided_v2_dataset_contract(self):
        validate_manifest(self.make_symptom_guided_v2_manifest())

    def test_symptom_guided_v2_rejects_wrong_shape_and_repository_reuse(self):
        mutations = [
            (
                "missing case",
                lambda manifest: manifest["cases"].pop(),
                "exactly 16 cases",
            ),
            (
                "extra case",
                lambda manifest: manifest["cases"].append(
                    copy.deepcopy(manifest["cases"][0])
                ),
                "exactly 16 cases",
            ),
            (
                "reuse one candidate repository",
                lambda manifest: [
                    case.update(repository_url="https://github.com/pydantic/pydantic")
                    for case in manifest["cases"]
                    if case["id"].startswith("jinja-")
                ],
                "exactly 4 distinct repositories",
            ),
            (
                "reuse a repository from an earlier cohort",
                lambda manifest: [
                    case.update(repository_url="https://github.com/pallets/click")
                    for case in manifest["cases"]
                    if case["id"].startswith("pydantic-")
                ],
                "repository was already used by an earlier diagnosis dataset",
            ),
            (
                "remove one repair's symptom arm",
                lambda manifest: [
                    case.pop("symptom", None)
                    for case in manifest["cases"]
                    if case["id"].startswith("jinja-symptom-")
                ],
                "one blind and one symptom-guided pair",
            ),
            (
                "mismatch symptom pair members",
                lambda manifest: next(
                    case for case in manifest["cases"]
                    if case["id"] == "typer-symptom-fixed"
                ).update(symptom="A different symptom"),
                "both members must have the same symptom",
            ),
        ]
        for label, mutate, expected in mutations:
            with self.subTest(label=label):
                manifest = self.make_symptom_guided_v2_manifest()
                mutate(manifest)
                with self.assertRaisesRegex(EvaluationDataError, expected):
                    validate_manifest(manifest)

    def test_symptom_guided_dataset_contract(self):
        validate_manifest(self.make_symptom_guided_manifest())

    def test_symptom_guided_dataset_rejects_malformed_shape_and_symptoms(self):
        def remove_symptom(manifest, case_ids):
            for case in manifest["cases"]:
                if case["id"] in case_ids:
                    case.pop("symptom", None)

        def set_pair_symptom(manifest, value):
            for case in manifest["cases"]:
                if case["id"] in {"pytest-symptom-bug", "pytest-symptom-fixed"}:
                    case["symptom"] = value

        def add_legacy_symptom(manifest):
            manifest["dataset_id"] = "diagnosis-v1"
            manifest["cases"][0]["symptom"] = "symptom"

        valid = self.make_symptom_guided_manifest()
        cases = [
            ("missing case", lambda m: m["cases"].pop(), "exactly 8"),
            (
                "extra case",
                lambda m: m["cases"].append(copy.deepcopy(m["cases"][0])),
                "exactly 8",
            ),
            (
                "repeated pair",
                lambda m: m["cases"][4].update(pair_id="pytest-12083-blind"),
                "pair .* exactly one bug and one fixed",
            ),
            (
                "pair with two bugs",
                lambda m: m["cases"][1].update(label="bug"),
                "pair .* exactly one bug and one fixed",
            ),
            (
                "repair missing an arm",
                lambda m: remove_symptom(m, {"pytest-symptom-bug", "pytest-symptom-fixed"}),
                "one blind and one symptom-guided pair",
            ),
            (
                "two repair groups share one issue ID",
                lambda m: [
                    case.update(issue_id="12083")
                    for case in m["cases"]
                    if case["id"].startswith("rich-")
                ],
                "exactly 2 repairs",
            ),
            (
                "one pair member missing symptom",
                lambda m: m["cases"][3].pop("symptom"),
                "both members must have the same symptom",
            ),
            (
                "pair with mismatched symptoms",
                lambda m: m["cases"][3].update(symptom="Different symptom"),
                "both members must have the same symptom",
            ),
            (
                "symptom on a legacy dataset",
                add_legacy_symptom,
                "only supported in diagnosis-symptom-guided-v1",
            ),
            (
                "whitespace-only symptom",
                lambda m: set_pair_symptom(m, "  "),
                "symptom must be trimmed nonempty text",
            ),
            (
                "multiline symptom",
                lambda m: set_pair_symptom(m, "line one\nline two"),
                "symptom must be single-line text",
            ),
            (
                "control character in symptom",
                lambda m: set_pair_symptom(m, "bad\x01text"),
                "symptom must not contain control characters",
            ),
            (
                "oversized symptom",
                lambda m: set_pair_symptom(m, "x" * 2001),
                "symptom must contain at most 2,000 characters",
            ),
        ]
        for label, mutate, expected in cases:
            with self.subTest(label=label):
                manifest = copy.deepcopy(valid)
                mutate(manifest)
                with self.assertRaisesRegex(EvaluationDataError, expected):
                    validate_manifest(manifest)

    def test_prepare_symptom_arm_keeps_context_and_changes_request_hash(self):
        manifest = self.make_symptom_guided_manifest()
        for case in manifest["cases"]:
            case["checkout_id"] = "fixture"
            case["commit"] = self.commit

        prepared = prepare_cases(
            manifest, self.repos_root, "test-model", 120, response_format="json-schema"
        )
        plan_cases = {case["id"]: case for case in prepared["plan"]["cases"]}
        for repair in ("pytest-12083", "rich-3897"):
            blind = next(
                case for case in manifest["cases"]
                if case["pair_id"] == f"{repair}-blind" and case["label"] == "bug"
            )
            symptom = next(
                case for case in manifest["cases"]
                if case["pair_id"] == f"{repair}-symptom" and case["label"] == "bug"
            )
            self.assertEqual(
                plan_cases[blind["id"]]["context_sha256"],
                plan_cases[symptom["id"]]["context_sha256"],
            )
            self.assertNotEqual(
                plan_cases[blind["id"]]["request_sha256"],
                plan_cases[symptom["id"]]["request_sha256"],
            )
            self.assertEqual(
                prepared["contexts"][blind["id"]], prepared["contexts"][symptom["id"]]
            )
            self.assertNotIn(
                "reported_symptom",
                json.dumps(prepared["contexts"][symptom["id"]], ensure_ascii=False),
            )

        legacy = prepare_cases(
            self.manifest, self.repos_root, "test-model", 120,
            response_format="json-schema",
        )
        baseline_prompts = build_diagnosis_prompts(legacy["contexts"]["bug-01"])
        baseline_hash = hashlib.sha256(
            _serialize_schema_request_body(
                baseline_prompts[0], baseline_prompts[1], "test-model"
            )
        ).hexdigest()
        self.assertEqual(
            legacy["plan"]["cases"][0]["request_sha256"], baseline_hash
        )

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

    def test_flask_holdout_dataset_id_is_supported(self):
        manifest = self.make_manifest()
        manifest["dataset_id"] = "diagnosis-flask-holdout-v1"
        validate_manifest(manifest)
        prepared = prepare_cases(manifest, self.repos_root, "test-model", 120)
        self.assertEqual(prepared["plan"]["dataset_id"], manifest["dataset_id"])

        manifest["dataset_id"] = "diagnosis-unreviewed-v1"
        with self.assertRaisesRegex(EvaluationDataError, "dataset_id"):
            validate_manifest(manifest)

    def test_werkzeug_holdout_dataset_id_is_supported(self):
        manifest = self.make_manifest()
        manifest["dataset_id"] = "diagnosis-werkzeug-holdout-v1"
        validate_manifest(manifest)
        prepared = prepare_cases(manifest, self.repos_root, "test-model", 120)
        self.assertEqual(prepared["plan"]["dataset_id"], manifest["dataset_id"])

        manifest["dataset_id"] = "diagnosis-unreviewed-v1"
        with self.assertRaisesRegex(EvaluationDataError, "dataset_id"):
            validate_manifest(manifest)

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

    def test_prepare_rejects_oversized_serialized_wire_request(self):
        with self.assertRaisesRegex(EvaluationDataError, "256 KiB"):
            prepare_cases(self.manifest, self.repos_root, "m" * (300 * 1024), 120)


if __name__ == "__main__":
    unittest.main()
