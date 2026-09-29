# Symptom-Guided Diagnosis Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task by
> task. The primary agent owns cohort interpretation, online dispatch, manual
> review, and acceptance. Steps use checkbox syntax for tracking.

**Goal:** Add an evaluation-only symptom prompt arm, freeze two new paired
Python repairs, and produce a source-reviewed comparison against the existing
blind prompt.

**Architecture:** Keep the product diagnosis prompt and CLI unchanged. Add a
small evaluator-only prompt builder, validate the exact eight-row manifest,
rebuild symptom prompts during run preflight, and report per-arm metrics only
for this dataset. Freeze and prepare the public source snapshots before any
provider request.

**Tech Stack:** Python 3.11+, standard-library `unittest`, Git worktrees,
existing `tools.evaluate_diagnosis`, DeepSeek Responses API `json_schema`.

**Spec:** [Symptom-Guided Diagnosis Evaluation Design](../specs/2026-09-29-symptom-guided-evaluation-design.md).

## Global Constraints

- Use the current isolated worktree on `codex/click-eval-closeout`.
- Do not edit the primary checkout or change `repo_doctor` product prompts,
  CLI behavior, response schema, or transport.
- Preserve all previous manifests, request hashes, and score-report shapes.
- Dataset ID is `diagnosis-symptom-guided-v1`; it contains exactly eight
  cases, four bug/fixed pairs, two repairs, and two prompt arms.
- A present `symptom` is trimmed, single-line text of 1–2,000 Unicode
  characters with no control characters; only symptom-arm rows contain it.
- Use `deepseek-flash`, Responses API `json_schema`, reasoning effort `none`,
  at most 120 source lines and 64 KiB, at most 256 KiB serialized request, and
  4,096 output tokens.
- The current Responses request omits temperature, top-p, and seed; provider
  defaults apply. Record the returned model ID and do not claim deterministic
  replay.
- Run two repeats, at most 16 sequential requests, no automatic retry, and
  stop after the first provider or provenance failure.
- Require `doctor --deepseek --model deepseek-flash` to report `ready` before
  dispatch. Do not show, store, or pass the API key as a command argument.
- Do not send case IDs, labels, issue IDs, commits, tests, fix references,
  ground truth, absolute checkout/worktree paths, or review annotations to the
  model. Bounded source context naturally includes repository-relative source
  filenames for evidence grounding.
- Do not execute upstream source, tests, or install upstream dependencies.
- Store prepared plans, contexts, run records, and review JSON only under the
  ignored `.local/diagnosis/` directory. Track the manifest, this implementation
  plan, and final redacted report as project artifacts.

## Files and responsibilities

| Path | Responsibility |
| --- | --- |
| `tools/diagnosis_prompt.py` | Build evaluation prompts while preserving the exact existing baseline prompt. |
| `tools/diagnosis_data.py` | Validate the new dataset/symptom contract and fingerprint the evaluation prompts. |
| `tools/diagnosis_runner.py` | Independently rebuild symptom-aware prompts and request hashes before transport. |
| `tools/diagnosis_score.py` | Add new-dataset-only prompt-arm summaries and render them. |
| `tests/test_diagnosis_prompt.py` | Verify baseline byte stability and symptom payload/instructions. |
| `tests/test_diagnosis_data.py` | Verify dataset shape, symptom validation, and request/context hashes. |
| `tests/test_diagnosis_runner.py` | Verify run preflight rebuilds symptom requests from the manifest. |
| `tests/test_diagnosis_score.py` | Verify arm-by-repeat scoring and unchanged legacy reports. |
| `evaluation/diagnosis/symptom-guided-v1.json` | Freeze eight source-reviewed cases and provenance. |
| `docs/evaluations/2026-09-29-symptom-guided-evaluation.md` | Record run status, manual decisions, signal, and limits. |
| `.local/diagnosis/symptom-guided-v1-*` | Hold clean checkouts and ignored plan/run/review/report artifacts. |

## Task 1: Validate the exact dataset and symptom field

**Files:** `tests/test_diagnosis_data.py`, `tools/diagnosis_data.py`.

**Interfaces:** `validate_manifest(manifest: dict) -> None` continues to validate
all older datasets. The new exact dataset additionally requires eight rows,
two repairs, one blind and one symptom pair per repair, matching bug/fixed
symptom values within each pair, and a shared `issue_id`/repository within a
repair. A symptom field on any older dataset is rejected.

- [ ] **Step 1: Add a valid eight-row test fixture.** Build each row from the
  existing local fixture case; use pair IDs `pytest-12083-blind`,
  `pytest-12083-symptom`, `rich-3897-blind`, and `rich-3897-symptom`. Each pair
  contains one bug and one fixed case. Put the same approved symptom on both
  symptom-pair rows and omit the key from blind rows. Use this complete setup
  inside `test_symptom_guided_dataset_contract`:

  ```python
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
          "repository_url": (
              "https://github.com/pytest-dev/pytest"
              if repair == "pytest-12083"
              else "https://github.com/Textualize/rich"
          ),
          "checkout_id": repair,
          "label": label,
          "issue_id": "12083" if repair == "pytest-12083" else "3897",
      })
      if symptom is not None:
          row["symptom"] = symptom
      else:
          row.pop("symptom", None)
      return row

  manifest = {
      "schema_version": 1,
      "dataset_id": "diagnosis-symptom-guided-v1",
      "cases": [
          make_case("pytest-blind-bug", "bug", "pytest-12083-blind", "pytest-12083"),
          make_case("pytest-blind-fixed", "fixed", "pytest-12083-blind", "pytest-12083"),
          make_case("pytest-symptom-bug", "bug", "pytest-12083-symptom", "pytest-12083", symptom=pytest_symptom),
          make_case("pytest-symptom-fixed", "fixed", "pytest-12083-symptom", "pytest-12083", symptom=pytest_symptom),
          make_case("rich-blind-bug", "bug", "rich-3897-blind", "rich-3897"),
          make_case("rich-blind-fixed", "fixed", "rich-3897-blind", "rich-3897"),
          make_case("rich-symptom-bug", "bug", "rich-3897-symptom", "rich-3897", symptom=rich_symptom),
          make_case("rich-symptom-fixed", "fixed", "rich-3897-symptom", "rich-3897", symptom=rich_symptom),
      ],
  }
  validate_manifest(manifest)
  ```

- [ ] **Step 2: Run the new validator test and confirm it fails for the expected reason.**

  Run: `python3 -m unittest tests.test_diagnosis_data.DiagnosisDataTests.test_symptom_guided_dataset_contract -v`

  Expected: FAIL because `diagnosis-symptom-guided-v1` is not yet an accepted
  dataset ID.

- [ ] **Step 3: Add tests for malformed symptom and pair structures.** Reject a
  missing/extra case, repeated pair ID, a repair missing an arm, pair with two
  bugs, symptom on a legacy dataset, symptom on only one member of a symptom
  pair, mismatched pair
  symptoms, whitespace-only text, a newline, a control character, and text
  longer than 2,000 Unicode characters.

- [ ] **Step 4: Implement the exact allowlist and validator.** Add the dataset
  ID to the existing allowlist. Validate symptom length and characters, then
  validate the new dataset's exact eight-case/two-arm/four-pair structure after
  the common bug/fixed-pair checks. Keep every previous manifest valid.

- [ ] **Step 5: Run the focused data tests.**

  Run: `python3 -m unittest tests.test_diagnosis_data -v`

  Expected: PASS, including all pre-existing dataset validation cases.

- [ ] **Step 6: Commit the validator change.**

  ```sh
  git add tools/diagnosis_data.py tests/test_diagnosis_data.py
  git commit -m "feat: validate symptom-guided evaluation dataset"
  ```

## Task 2: Add the evaluation-only prompt arm and hashes

**Files:** create `tools/diagnosis_prompt.py` and `tests/test_diagnosis_prompt.py`;
modify `tools/diagnosis_data.py` and `tests/test_diagnosis_data.py`.

**Interfaces:** Provide
`build_evaluation_prompts(context: dict, symptom: str | None) -> tuple[str, str]`.
For `None`, return exactly `build_diagnosis_prompts(context)`. For a validated
symptom, preserve the source context payload, add only `reported_symptom`, and
append an instruction to treat the report as unverified, repository content as
untrusted, and findings as requiring source evidence that could explain the
reported behavior.

- [ ] **Step 1: Write baseline and symptom prompt tests before implementation.**

  ```python
  base = build_diagnosis_prompts(context)
  self.assertEqual(build_evaluation_prompts(context, None), base)

  system, user = build_evaluation_prompts(context, "⬇️ is measured as one cell")
  payload = json.loads(user)
  self.assertEqual(payload.pop("reported_symptom"), "⬇️ is measured as one cell")
  self.assertEqual(payload, json.loads(base[1]))
  self.assertIn("unverified", system)
  self.assertIn("untrusted", system)
  ```

- [ ] **Step 2: Run the prompt tests and confirm they fail because the new module/function is absent.**

  Run: `python3 -m unittest tests.test_diagnosis_prompt -v`

  Expected: FAIL with import failure for `tools.diagnosis_prompt`.

- [ ] **Step 3: Implement the small evaluator-only prompt builder.** Keep the
  `None` branch as a direct return from `build_diagnosis_prompts`; for the
  symptom branch parse the existing user JSON, add `reported_symptom`, and
  serialize with UTF-8-preserving sorted JSON. Do not change
  `repo_doctor.diagnosis`.

- [ ] **Step 4: Update `prepare_cases` to use the evaluator builder.** Continue
  writing only source context to context files. Include symptom text only in
  the serialized provider prompt so the existing request SHA-256 fingerprints
  the exact symptom.

- [ ] **Step 5: Add preparation assertions.** For one blind and one symptom
  case over the same fixture checkout, assert equal context hashes, different
  request hashes when symptoms differ, and no `reported_symptom` in saved
  context JSON. Confirm a legacy fixture retains its old request hash.

- [ ] **Step 6: Run prompt and data tests, then commit.**

  Run: `python3 -m unittest tests.test_diagnosis_prompt tests.test_diagnosis_data -v`

  ```sh
  git add tools/diagnosis_prompt.py tools/diagnosis_data.py tests/test_diagnosis_prompt.py tests/test_diagnosis_data.py
  git commit -m "feat: add evaluation-only symptom prompt arm"
  ```

## Task 3: Rebuild symptom prompts during run preflight

**Files:** `tools/diagnosis_runner.py`, `tests/test_diagnosis_runner.py`.

**Interfaces:** `_validate_plan_and_contexts` obtains `symptom` from the
validated manifest row and uses `build_evaluation_prompts`. It still rebuilds
context from the pinned checkout, compares the saved context object and hash,
and hashes the exact Responses `json_schema` request before any client call.

- [ ] **Step 1: Write a fake-client run test for all eight fixture cases.**
  Prepare the valid eight-case local manifest with `response_format="json-schema"`;
  invoke `run_cases` with `repeats=1`, `max_calls=8`, and a client that returns
  `DeepSeekResult("test-model", {"findings": []})`. Assert the four symptom
  user prompts include `reported_symptom`, the four blind prompts do not, and
  all eight records preserve their prepared request/context hashes.

- [ ] **Step 2: Run that test and confirm it fails before transport.**

  Run: `python3 -m unittest tests.test_diagnosis_runner.DiagnosisRunnerTests.test_symptom_prompt_is_rebuilt_from_manifest -v`

  Expected: FAIL because preflight rebuilds only the blind core prompt and
  rejects the prepared symptom request hash.

- [ ] **Step 3: Change runner preflight to use the shared evaluation builder.**
  Pass `manifest_case.get("symptom")`; do not persist the symptom separately
  in plan or run records, because the manifest hash already binds it.

- [ ] **Step 4: Run runner tests, including existing stop-on-provider-error coverage.**

  Run: `python3 -m unittest tests.test_diagnosis_runner -v`

  Expected: PASS; provider failure still records one safe failure and prevents
  the next transport call.

- [ ] **Step 5: Commit the preflight change.**

  ```sh
  git add tools/diagnosis_runner.py tests/test_diagnosis_runner.py
  git commit -m "fix: rebuild symptom evaluation requests before dispatch"
  ```

## Task 4: Report new-dataset metrics by prompt arm

**Files:** `tools/diagnosis_score.py`, `tests/test_diagnosis_score.py`.

**Interfaces:** For this dataset only, add `report["by_prompt_arm"]` with
`blind` and `symptom-guided` entries. Each arm contains one result per repeat,
with existing counts/metrics, successful and failed call counts, detected bug
case IDs, fixed-case accepted false-alarm IDs, and per-repair bug/fixed
decisions. Keep existing whole-dataset totals. Do not add this key to reports
for earlier dataset IDs.

- [ ] **Step 1: Build a score fixture with eight manifest rows and 16 records.**
  Use manifest case `symptom` presence as the arm. For each repeat, include a
  true positive on one symptom bug row, a true positive on one blind bug row,
  and one accepted false positive on a fixed row; complete the remaining calls
  with successful empty findings. Create manual review rows using the existing
  `make_review_template` contract.

- [ ] **Step 2: Write failing score assertions.** Assert each arm has two
  repeats, each has two requested bug cases per repeat, detections and fixed
  alarms appear under the correct arm/repair, and the rendered Markdown names
  both arms. Also assert an existing `diagnosis-v1` report has no
  `by_prompt_arm` key.

- [ ] **Step 3: Run the new scoring test and confirm it fails because arm results are absent.**

  Run: `python3 -m unittest tests.test_diagnosis_score.DiagnosisScoreTests.test_symptom_dataset_reports_arm_and_repair_metrics -v`

  Expected: FAIL with missing `by_prompt_arm` output.

- [ ] **Step 4: Implement per-arm/per-repeat aggregation from reviewed records.**
  Reuse the existing review verdicts and `calculate_repeat_metrics`; do not
  infer verdicts from model text. Define each repair result from its two
  `pair_id` rows and report the bug detection and fixed false alarm separately.

- [ ] **Step 5: Render an arm comparison section only when the report contains the new key.**
  Include case IDs and counts so the registered signal can be checked from the
  report without losing the existing global repeat tables.

- [ ] **Step 6: Run score tests and commit.**

  Run: `python3 -m unittest tests.test_diagnosis_score -v`

  ```sh
  git add tools/diagnosis_score.py tests/test_diagnosis_score.py
  git commit -m "feat: score symptom evaluation by prompt arm"
  ```

## Task 5: Freeze and prepare the two-repair manifest

**Files:** create `evaluation/diagnosis/symptom-guided-v1.json`.

**Interfaces:** Eight rows use these exact source snapshots:

- pytest bug `7cfe8aa2758c154c9355ca61e3de32a50ec78663`, fixed
  `d036b12bb6fa09f9a8a3b690cc7336113c93fa44`, target
  `src/_pytest/main.py::Session.perform_collect`; include
  `src/_pytest/main.py::normalize_collection_arguments` only on the fixed row.
- Rich bug `53757bc234cf18977cade41a5b64f3abaccb0b85`, fixed
  `f000c3149166cc2091b801b63b0a55e806c5d49b`, target
  `rich/cells.py::cell_len`; include `rich/cells.py::cached_cell_len` only on
  the bug row. The fixed row's context graph includes `rich/cells.py::_cell_len`.

- [ ] **Step 1: Create ignored bare repositories and detached source checkouts.**

  ```sh
  SYMPTOM_ROOT=.local/diagnosis/symptom-guided-v1-checkouts
  mkdir -p "$SYMPTOM_ROOT/.bare"
  git clone --bare https://github.com/pytest-dev/pytest.git "$SYMPTOM_ROOT/.bare/pytest.git"
  git clone --bare https://github.com/Textualize/rich.git "$SYMPTOM_ROOT/.bare/rich.git"
  git --git-dir="$SYMPTOM_ROOT/.bare/pytest.git" worktree add --detach "$SYMPTOM_ROOT/pytest-7cfe8aa2758c" 7cfe8aa2758c154c9355ca61e3de32a50ec78663
  git --git-dir="$SYMPTOM_ROOT/.bare/pytest.git" worktree add --detach "$SYMPTOM_ROOT/pytest-d036b12bb6fa" d036b12bb6fa09f9a8a3b690cc7336113c93fa44
  git --git-dir="$SYMPTOM_ROOT/.bare/rich.git" worktree add --detach "$SYMPTOM_ROOT/rich-53757bc234cf" 53757bc234cf18977cade41a5b64f3abaccb0b85
  git --git-dir="$SYMPTOM_ROOT/.bare/rich.git" worktree add --detach "$SYMPTOM_ROOT/rich-f000c3149166" f000c3149166cc2091b801b63b0a55e806c5d49b
  ```

- [ ] **Step 2: Verify provenance and source spans without running upstream code.**
  Check clean status, exact HEADs, merge first parents, target/supplement symbol
  uniqueness, and source line ranges. Use inclusive `splitlines()`
  spans joined with LF and UTF-8 SHA-256, matching `_source_fingerprint`.

- [ ] **Step 3: Create the eight manifest rows.** Use `schema_version: 1`, the
  exact dataset ID, the four pair IDs, two issue IDs, target paths/lines/hashes,
  source-only `include_symbols`, issue/PR/source-test references, approved
  annotations, and narrow ground truth. Reuse the exact symptom strings in
  bug and fixed rows of the symptom arm. Keep all metadata out of the prompt.

- [ ] **Step 4: Validate the manifest offline and commit it before preparation.**

  Run this exact standalone validator command from the repository root:

  ```sh
  python3 -c 'import json; from pathlib import Path; from tools.diagnosis_data import validate_manifest; validate_manifest(json.loads(Path("evaluation/diagnosis/symptom-guided-v1.json").read_text(encoding="utf-8"))); print("manifest valid")'
  ```

  Expected: `manifest valid`, with no network access.

  ```sh
  git add evaluation/diagnosis/symptom-guided-v1.json
  git commit -m "data: freeze symptom-guided diagnosis cohort"
  ```

- [ ] **Step 5: Prepare the committed manifest offline.**

  ```sh
  python3 -m tools.evaluate_diagnosis prepare \
    --manifest evaluation/diagnosis/symptom-guided-v1.json \
    --repos-root .local/diagnosis/symptom-guided-v1-checkouts \
    --model deepseek-flash --max-lines 120 --response-format json-schema \
    --out-dir .local/diagnosis/symptom-guided-v1-plan
  ```

- [ ] **Step 6: Audit prepared contexts and hashes.** Confirm 8 contexts, each
  under 120 lines/64 KiB, with no `reported_symptom` saved in a context file.
  For each source snapshot, assert blind and symptom context SHA-256 values are
  equal and request hashes differ. Independently rebuild the request body with
  `build_evaluation_prompts` and `_serialize_schema_request_body`, then compare
  all eight hashes. Confirm no case IDs, labels, issue IDs, commits, test names,
  fix references, absolute checkout paths, review annotations, or ground truth
  occur in any serialized prompt. Repository-relative source filenames inside
  the source context are expected.

- [ ] **Step 7: Run focused and full tests before any provider request.**

  Run: `python3 -m unittest tests.test_diagnosis_prompt tests.test_diagnosis_data tests.test_diagnosis_runner tests.test_diagnosis_score -v`

  Run: `python3 -m unittest discover -v`

## Task 6: Run the bounded online experiment

**Files:** ignored `.local/diagnosis/symptom-guided-v1-*` records only.

- [ ] **Step 1: Require a clean committed analyzer and ready DeepSeek preflight.**

  Run: `python3 -m repo_doctor doctor --deepseek --model deepseek-flash --json .`

  Expected: `deepseek.status` is `ready`. If the key is missing/rejected or
  preflight is not ready, send no evaluation requests and record the reason
  without exposing key material.

- [ ] **Step 2: Dispatch the exact 16 sequential requests once.**

  ```sh
  python3 -m tools.evaluate_diagnosis run \
    --manifest evaluation/diagnosis/symptom-guided-v1.json \
    --repos-root .local/diagnosis/symptom-guided-v1-checkouts \
    --plan-dir .local/diagnosis/symptom-guided-v1-plan \
    --out-dir .local/diagnosis/symptom-guided-v1-run \
    --repeats 2 --max-calls 16 --allow-network
  ```

- [ ] **Step 3: Inspect only the safe run summary and parsed records.** Verify
  attempted/completed counts, no retry, returned model ID, provider usage, and
  request hashes. On any call error, preserve the partial run and stop; do not
  resend a case.

## Task 7: Review, score, and report

**Files:** ignored review/scoring artifacts; create
`docs/evaluations/2026-09-29-symptom-guided-evaluation.md`.

- [ ] **Step 1: Generate an offline review template.**

  ```sh
  python3 -m tools.evaluate_diagnosis prepare-review \
    --run-dir .local/diagnosis/symptom-guided-v1-run \
    --out-file .local/diagnosis/symptom-guided-v1-review.json
  ```

- [ ] **Step 2: Review each parsed finding against pinned source and the approved behavior contract.**
  Mark `tp` only when the finding identifies the paired defect and explains
  the symptom; mark unrelated claims `fp`, preserve `uncertain`, and mark
  duplicates explicitly. On fixed snapshots, mark `fp` only when an accepted
  finding falsely attributes the paired symptom to the fixed source. Keep
  rationale specific and note the exact supporting/contradicting source lines.

- [ ] **Step 3: Score offline and inspect the arm-by-repair-by-repeat report.**

  ```sh
  python3 -m tools.evaluate_diagnosis score \
    --manifest evaluation/diagnosis/symptom-guided-v1.json \
    --run-dir .local/diagnosis/symptom-guided-v1-run \
    --review .local/diagnosis/symptom-guided-v1-review.json \
    --json-out .local/diagnosis/symptom-guided-v1-report.json \
    --markdown-out .local/diagnosis/symptom-guided-v1-report.md
  ```

- [ ] **Step 4: Check the preregistered signal exactly.** Require 16 parseable
  calls; at least one symptom-relevant bug TP per repair across two repeats;
  zero symptom-arm fixed false alarms; and at least one additional bug-case
  detection result in symptom-guided versus blind across eight bug repeats,
  with no increase in fixed false alarms. Report a failed or partial result as
  such.

- [ ] **Step 5: Write the final redacted report.** State provenance, run and
  manifest hashes, returned model IDs, token usage, case-level verdicts,
  repeat variation, signal outcome, the omitted provider sampling defaults,
  exploratory limitations, and the next decision. Do not include the key or
  raw provider response bodies.

- [ ] **Step 6: Review final diff and commit the report.**
  Confirm previous manifests and their prepared request hashes are unchanged;
  confirm ignored `.local` records and API key material are absent from Git.

  ```sh
  git status --short
  git diff --check
  git add docs/evaluations/2026-09-29-symptom-guided-evaluation.md
  git commit -m "docs: report symptom-guided diagnosis evaluation"
  ```
