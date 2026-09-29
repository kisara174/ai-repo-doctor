# Werkzeug Holdout Implementation Plan

> **For agentic workers:** Use `executing-plans` task by task. The primary
> agent owns upstream interpretation, experiment setup, provider calls,
> behavioral review, release decisions, and final acceptance. Any Luna work
> needs a separate bounded packet under `AGENTS.md`.

**Goal:** Freeze a third-repository six-case diagnosis cohort and measure the
current product path without changing its prompt or evidence gate.

**Architecture:** Reuse the manifest validator, offline preparation, sequential
runner, review template, and scorer. Extend one explicit dataset ID allowlist,
commit six public source-backed cases, then prepare and run once under a clean
analyzer commit. Keep all run artifacts ignored and publish only safe metrics.

**Tech Stack:** Python 3.11–3.13, `unittest`, Git, existing
`tools.evaluate_diagnosis`, optional DeepSeek Responses API.

**Spec:** [Werkzeug holdout design](../specs/2026-09-29-werkzeug-holdout-design.md).

## Global constraints

- Work on `codex/werkzeug-holdout-v0.5` in the existing managed worktree.
- Preserve the original ten-case and Flask six-case manifests byte for byte.
- Read target Werkzeug code and Git metadata only; do not execute its code,
  tests, or dependencies.
- Keep `deepseek-flash`, Responses `json_schema`, disabled thinking, current
  prompt, 4,096 output tokens, and source/request budgets fixed.
- One provider call per case; stop on the first failure and do not retry.
- Do not display or save the Key, raw provider response, or private source.
- Do not infer behavioral truth from a local quote match. Label all review as
  primary-only until an independent reviewer checks it.
- Run focused checks for changed code and one full suite at integration, not
  repeated optional sweeps.

## Files and responsibilities

| Path | Responsibility |
| --- | --- |
| `tools/diagnosis_data.py` | Accept the exact third dataset ID. |
| `tests/test_diagnosis_data.py` | Reject arbitrary IDs and accept the new one. |
| `evaluation/diagnosis/werkzeug-holdout-v1.json` | Frozen six cases. |
| `evaluation/diagnosis/README.md` | Reproduction command and manifest hash. |
| `docs/evaluations/2026-09-29-werkzeug-holdout.md` | Safe run outcome and decision. |
| `docs/execution-status.md` | Current branch, evidence, CI, and next gate. |
| `.local/diagnosis/werkzeug-*` | Ignored checkouts, plan, run, review, score. |

## Task 1: Admit only the reviewed cohort ID

- [ ] Add one focused test in `tests/test_diagnosis_data.py`: a fixture with
  `dataset_id = "diagnosis-werkzeug-holdout-v1"` must pass
  `validate_manifest` and preserve its ID in `prepare_cases`; an arbitrary
  ID must still raise `EvaluationDataError` for `dataset_id`.
- [ ] Run that test and observe the expected ID rejection before editing code.
- [ ] Add the exact ID to the allowlist and error message in
  `tools/diagnosis_data.py`; change no other validation rule.
- [ ] Run the focused test, `python3 -m unittest tests.test_diagnosis_data -q`,
  and `git diff --check`; inspect the patch and commit these two files.

**Acceptance:** The new named cohort prepares; unknown IDs remain rejected.

## Task 2: Freeze six source-backed rows

- [ ] Confirm the six HEADs and clean states in
  `.local/diagnosis/werkzeug-checkouts-20260929/`, using the spec table.
  Confirm each bug commit is the fixed commit's first parent.
- [ ] Recheck upstream issue/PR behavior and repair diffs read-only. Reject a
  candidate if the selected symbol does not contain the relevant bug and fix.
- [ ] Create `evaluation/diagnosis/werkzeug-holdout-v1.json` with six cases in
  spec order, each bug immediately followed by fixed. Use the existing
  manifest shape, exact `checkout_id`, full commit, symbol, source file/span/
  SHA-256, `pair_id`, issue ID, narrow trigger/outcome ground truth, public
  references, and UTC primary approval annotation.
- [ ] Check `validate_manifest`, every `_verified_checkout` and
  `_source_fingerprint`, unique symbols, and `build_context` source budgets.
  Confirm labels, issue IDs, and ground truth are absent from prompt contexts.
- [ ] Record the manifest's byte SHA-256 and reproduction commands in
  `evaluation/diagnosis/README.md`; check previous manifest hashes and commit
  the new manifest and README.

**Acceptance:** All six pinned cases validate without running target code.

## Task 3: Run the frozen current-product arm

- [ ] With a clean analyzer commit, prepare to a new ignored directory:

  ```sh
  python3 -m tools.evaluate_diagnosis prepare \
    --manifest evaluation/diagnosis/werkzeug-holdout-v1.json \
    --repos-root .local/diagnosis/werkzeug-checkouts-20260929 \
    --model deepseek-flash --response-format json-schema --max-lines 120 \
    --out-dir .local/diagnosis/werkzeug-plan-20260929
  ```

- [ ] Inspect all context and request hashes, line/byte counts, analyzer
  commit, and request settings. Reconstruct the exact serialized wire hashes
  offline. Ensure ground truth is absent from all six payloads.
- [ ] If the Key is present and the provider can be called, use one sequential
  run with `--repeats 1 --max-calls 6 --allow-network`, the same manifest/
  checkouts/plan, and a fresh `.local/diagnosis/werkzeug-run-20260929`
  output directory. Stop on any failure; no retry.
- [ ] For completed responses, prepare review rows, adjudicate every accepted
  and rejected finding against pinned code and upstream repair, then score
  only after filling required verdicts and rationales. Preserve partial
  records even when scoring a complete cohort is impossible.

**Acceptance:** An honest complete or partial outcome with safe provenance.

## Task 4: Report and integrate

- [ ] Write `docs/evaluations/2026-09-29-werkzeug-holdout.md` with exact
  completion count, reviewed TP/FP/uncertain/duplicate totals, fixed alarms,
  grounding, provider usage, and limits. Compare with the preregistered gate
  in the spec; do not pool cohorts or infer billed cost.
- [ ] Update `docs/execution-status.md` and the evaluation README. Review the
  entire diff, run the full offline suite once, `compileall`, and diff checks.
- [ ] Commit, push, open a PR against the verified default branch, attach it
  to this task, check Python 3.11–3.13 CI on the exact PR head, then integrate
  under the standing user authorization if the review and CI are clean.

**Acceptance:** Reviewable, reproducible evaluation evidence; a default-branch
decision that keeps cloud diagnosis experimental unless the stated gate is
met and independently reviewed.
