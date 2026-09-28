# Flask Holdout Diagnosis Comparison Implementation Plan

> **For agentic workers:** Execute this plan task by task in an isolated
> worktree. The primary agent owns case selection, defect judgments, provider
> calls, review, and acceptance. A bounded executor may only take a fully
> specified mechanical packet under `AGENTS.md`.

**Goal:** Freeze six new Flask bug/fixed snapshots, measure the current
diagnosis path, and test one preregistered prompt edit on the same snapshots.

**Architecture:** Reuse the existing manifest, preparation, runner, review,
and scorer protocols. Extend only the manifest ID allowlist and, after a clean
baseline, one system-prompt sentence group. Each arm gets a separate committed
analyzer SHA and ignored plan/run directories.

**Tech Stack:** Python 3.11–3.13, `unittest`, the existing
`tools.evaluate_diagnosis` CLI, Git, and optional DeepSeek Responses API.

**Spec:** [Flask holdout design](../specs/2026-09-28-flask-holdout-design.md).

## Global constraints

- Work on `codex/diagnosis-holdout-v0.3` in the existing managed worktree.
- Preserve `evaluation/diagnosis/manifest-v1.json` byte for byte; its SHA-256
  is `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
- Do not execute Flask code, tests, or dependencies. Read source and Git
  metadata only. Do not record the API key or raw provider responses.
- Use six cases in the spec's order, one response per case per arm, no retries.
  Keep the request budgets and model settings in the spec fixed.
- The prompt variant is preregistered in the spec. Do not adapt its wording
  after reading baseline model outputs.
- Run verification for a named risk or required integration gate; do not
  repeatedly sweep the suite without a changed source state or failure.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `tools/diagnosis_data.py` | Accept the two named diagnosis dataset IDs. |
| `tests/test_diagnosis_data.py` | Prove the new ID works and arbitrary IDs fail. |
| `evaluation/diagnosis/flask-holdout-v1.json` | Frozen six-case provenance and ground truth. |
| `evaluation/diagnosis/README.md` | Reproduction steps and interpretation limits. |
| `repo_doctor/diagnosis.py` | Exactly one preregistered system-prompt edit after baseline. |
| `docs/evaluations/2026-09-28-flask-holdout.md` | Safe hashes, outcomes, human review summary, and decision. |
| `docs/execution-status.md` | Current stage, commit IDs, and checks. |
| `.local/diagnosis/holdout-*` | Ignored checkouts, plans, records, and reviews. |

## Task 1: Allow an independently named manifest

- [ ] In `tests/test_diagnosis_data.py`, add a test using
  `manifest = self.make_manifest()` and set
  `manifest["dataset_id"] = "diagnosis-flask-holdout-v1"`. Call
  `validate_manifest(manifest)`, then
  `prepare_cases(manifest, self.repos_root, "test-model", 120)` and assert its
  plan retains that ID. Set the ID to `diagnosis-unreviewed-v1` and assert
  `validate_manifest` raises `EvaluationDataError` mentioning `dataset_id`.
- [ ] Run
  `python3 -m unittest tests.test_diagnosis_data.DiagnosisDataTests.test_flask_holdout_dataset_id_is_supported -v`.
  It must fail on the existing exact-ID check.
- [ ] In `tools/diagnosis_data.py`, replace the single ID equality with the
  exact set `{"diagnosis-v1", "diagnosis-flask-holdout-v1"}`. Update the
  error message to list those two values. Change no other manifest rule.
- [ ] Re-run the focused test, then
  `python3 -m unittest tests.test_diagnosis_data -q` and `git diff --check`.
  Inspect the diff and commit the two files.

**Acceptance:** The new ID survives preparation, arbitrary IDs still fail,
and legacy manifests remain valid.

## Task 2: Freeze six source-backed cases

- [ ] Read the spec's three upstream issues and fix PRs. Confirm each fixed
  SHA is the merge commit and each bug SHA is its first parent. The six local
  detached checkouts are under
  `.local/diagnosis/holdout-checkouts-20260928/`; verify every HEAD and clean
  status. On another machine, clone `https://github.com/pallets/flask.git`
  once as a bare repo, then use `git --git-dir=<bare> worktree add --detach
  <checkout-id> <full-sha>` for each row below.
- [ ] Create `evaluation/diagnosis/flask-holdout-v1.json` with
  `schema_version: 1`, `dataset_id: "diagnosis-flask-holdout-v1"`, six case
  objects in the table's order, and the exact field structure of
  `manifest-v1.json`. Use `repository_url:
  "https://github.com/pallets/flask"`, `label: "bug"` or `"fixed"`, shared
  `pair_id` per issue, `issue_id: "pallets/flask#<number>"`, a full source
  fingerprint, a trigger/outcome-specific `ground_truth`, public issue/PR/
  commit/blob `references`, and a primary-agent approval annotation with an
  ISO-8601 timestamp. Do not copy the old ten cases or their labels.

  | Case ID | Checkout ID / full commit | Symbol suffix | Source span / SHA-256 |
  | --- | --- | --- | --- |
  | `flask-4170-bug` | `flask-c3f923d0e0ab` / `c3f923d0e0aba3ed5b6013c5d022021e4ae059cf` | `call_factory` | `src/flask/cli.py:89-119` / `d447f6ee712f5eacf74b29b063430393d380434e8a41285505e1d0300f4da7e0` |
  | `flask-4170-fixed` | `flask-ef3a82a28200` / `ef3a82a2820082f7d9f2ca963c9dff7eb1ea9687` | `call_factory` | `src/flask/cli.py:89-122` / `62dd30fd819d88e6ce54f77399a977799382c9941dc4d9d0537dfc1e5ff27ecf` |
  | `flask-5391-bug` | `flask-3435d2ff1589` / `3435d2ff1589eb0c1a85cc294a20985910a1a606` | `SeparatedPathType.convert` | `src/flask/cli.py:851-861` / `2f5433429fc2279c131d3a0e02a7621c228342292209527e2c6ad59703d73582` |
  | `flask-5391-fixed` | `flask-d7209a957004` / `d7209a957004d4758f32fd8b2f89da11f5fe5718` | `SeparatedPathType.convert` | `src/flask/cli.py:851-863` / `4e7c63eca412e2011eb711ff409e2fd4fe283745f8dab01fd8475913b13cfe7c` |
  | `flask-5786-bug` | `flask-5addaf833b2e` / `5addaf833b2e8c7a616f89dd8ad5a44b07d7c000` | `FlaskClient.open` | `src/flask/testing.py:204-247` / `92bfe86f26e0d4df42a236919305ddaae0f5477b15470fcbf807122475923f4f` |
  | `flask-5786-fixed` | `flask-24824ff666e0` / `24824ff666e096c4c07d0b75a889088571afe4a6` | `FlaskClient.open` | `src/flask/testing.py:204-247` / `8e98d535a52474242bf50a64ddd15a0ff84439be148f88891b114fbe8ce3229d` |

- [ ] For #4170, accept only the erroneous positional `script_info` for a
  sole `**kwargs` factory. For #5391, require the Python <3.12 list-
  comprehension `super()` trigger and the option conversion failure. For
  #5786, require reverse context restoration and the prior request session
  obscuring the final redirect target's session. State the corresponding
  repaired behavior narrowly in fixed rows.
- [ ] Read every source span and upstream regression test. Run
  `validate_manifest`, `_source_fingerprint`, and `build_index`/`build_context`
  read-only for each case. Assert six clean pinned checkouts, unique symbols,
  the listed hashes, and at most 120 source lines / 64 KiB. Record the final
  manifest's byte SHA-256 in `evaluation/diagnosis/README.md` and the report.
- [ ] `git diff --check`, review the manifest for any leaked ground truth in
  prompt fields, and commit manifest plus README. Recheck the old manifest
  SHA-256 after the commit.

**Acceptance:** Six source-backed cases are immutable and independently
identifiable; no target code was executed.

## Task 3: Current-prompt baseline

- [ ] With a clean analyzer commit, prepare a new schema plan:

  ```sh
  python3 -m tools.evaluate_diagnosis prepare \
    --manifest evaluation/diagnosis/flask-holdout-v1.json \
    --repos-root .local/diagnosis/holdout-checkouts-20260928 \
    --model deepseek-flash --response-format json-schema --max-lines 120 \
    --out-dir .local/diagnosis/holdout-plan-baseline-20260928
  ```

- [ ] Inspect `plan.json` and its SHA-256, each context/request SHA-256, six
  line/byte counts, and clean target states. Rebuild all six production wire
  bodies offline and confirm their SHA-256 equals the plan values. Confirm
  ground truth and issue IDs are absent from prompt contexts.
- [ ] If the key is loaded and transport is ready, make exactly six calls:

  ```sh
  python3 -m tools.evaluate_diagnosis run \
    --plan-dir .local/diagnosis/holdout-plan-baseline-20260928 \
    --manifest evaluation/diagnosis/flask-holdout-v1.json \
    --repos-root .local/diagnosis/holdout-checkouts-20260928 \
    --out-dir .local/diagnosis/holdout-run-baseline-20260928 \
    --repeats 1 --max-calls 6 --allow-network
  ```

  No retry. If the key or provider fails, retain safe records and stop the
  paired online experiment with an explicit partial status.
- [ ] If all six complete, run `prepare-review` to a new JSON path, adjudicate
  **every** accepted and rejected finding from pinned source and upstream
  repair, and run `score` to separate JSON/Markdown paths. Label the review
  primary-only. Record counts and token usage in the report.

**Acceptance:** A pinned six-case baseline and truthful review/score, or an
explicit partial run without invented metrics.

## Task 4: Preregistered prompt variant

- [ ] Only after the baseline, edit `build_diagnosis_prompts` in
  `repo_doctor/diagnosis.py`. Immediately after the current instruction
  “Report only issues supported by exact source lines in the supplied
  context.” add the exact two sentences from the spec. Change no context or
  evidence code. Run the focused prompt tests, full offline suite, `compileall`,
  and `git diff --check`. Review and commit the change before preparing.
- [ ] Prepare a new schema plan under that clean commit in
  `.local/diagnosis/holdout-plan-variant-20260928`. Compare all six context
  hashes with the baseline (must be equal) and request hashes (must differ),
  and verify the exact serialized wire bodies offline.
- [ ] If the baseline was complete and the provider is available, run the
  variant in `.local/diagnosis/holdout-run-variant-20260928`, again six calls
  maximum and no retry. Independently adjudicate all findings and score only
  a complete, reviewed run. Stop on provider or input drift.

**Acceptance:** The only changed provider input is the system prompt and both
arms have separately traceable commits, plans, records, and reviews.

## Task 5: Decision and integration

- [ ] Complete `docs/evaluations/2026-09-28-flask-holdout.md` with the
  source/manifest/plan hashes, case-level verdicts, separate arm scores,
  paired comparison, primary-review limits, and the spec's decision rule.
  Do not claim a default-prompt improvement from one six-case run.
- [ ] Update `docs/execution-status.md` with the actual state. Verify the
  final diff, full offline suite, `compileall`, and `git diff --check` once on
  the final head. Push, create and attach a PR against the confirmed default
  branch, and check current-head Python 3.11/3.12/3.13 CI. Merge under the
  standing project authorization only if review and CI pass.

**Acceptance:** The report supports a concrete keep/change recommendation;
the integrated code and documentation have current-head verification.

## Execution checkpoint — 2026-09-28

Tasks 1–3 completed. Task 4's prompt variant was prepared under clean commit
`c206da6`, with all six context hashes identical to the baseline and each
request hash changed only by the preregistered prompt text. Its first online
call returned `invalid_response/invalid_content_json`, so the runner stopped
at 1/6 attempts and Task 4's complete paired comparison was not possible.
The prompt was reverted at `d66ec4c`. Do not resume the five unattempted
calls or retry this arm as if they belonged to the original one-pass plan.
Task 5's report and integration checks remain the next actions. The
[holdout report](../../evaluations/2026-09-28-flask-holdout.md) is the
source for actual outcome counts.
