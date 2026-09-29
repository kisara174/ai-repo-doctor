# Click Explicit-Context Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task by
> task. The primary agent owns upstream interpretation, labels, provider
> dispatch, review, and integration. A Luna executor may take only a separate
> mechanical packet under `AGENTS.md`. Steps use checkbox syntax for tracking.

**Goal:** Compare default and explicitly supplemented diagnosis context on two
fresh Click bug/fixed pairs, then record a source-reviewed quality result.

**Architecture:** Reuse the existing optional `include_symbols` evaluator
contract. Add one exact dataset ID, freeze eight manifest rows, prepare
request hashes under a clean commit, run at most eight sequential calls, and
manually review every model finding before scoring.

**Tech Stack:** Python 3.11–3.13, `unittest`, Git, existing
`tools.evaluate_diagnosis`, optional DeepSeek Responses API.

**Spec:** [Click explicit-context design](../specs/2026-09-29-click-explicit-context-design.md).

## Global constraints

- Work on `codex/click-explicit-holdout-v0.9` in the existing managed worktree.
- Preserve earlier manifests and ignored plan/run records; never relabel them.
- Read pinned Click source and tests without executing target code or installing
  its dependencies.
- Use `deepseek-flash`, Responses `json_schema`, no thinking field, 120 selected
  lines, 64 KiB selected source, 256 KiB request, and 4,096 output tokens.
- Verify `doctor --deepseek` returns `ready` immediately before dispatch.
- Send one call per case sequentially, no retries, stop on the first error.
- Never send labels, ground truth, issues, or fix links to the model; never
  commit the Key, raw provider bodies, or ignored run artifacts.
- Review behavior from source; a quotation match alone is not a TP.

## Files and responsibilities

| Path | Responsibility |
| --- | --- |
| `tools/diagnosis_data.py` | Admit exact Click dataset ID. |
| `tests/test_diagnosis_data.py` | Red/green allowlist coverage. |
| `evaluation/diagnosis/click-explicit-context-v1.json` | Eight frozen rows. |
| `evaluation/diagnosis/README.md` | Provenance, hash, reproduction, limit. |
| `docs/evaluations/2026-09-29-click-explicit-context.md` | Run and manual-review decision. |
| `docs/execution-status.md` | Current project checkpoint. |
| `.local/diagnosis/click-explicit-*` | Ignored checkouts, plan, run, review, score. |

## Task 1: Admit the exact dataset ID

- [ ] Add a focused test in `tests/test_diagnosis_data.py`: copy
  `self.manifest`, set `dataset_id` to
  `diagnosis-click-explicit-context-v1`, and assert `validate_manifest`
  accepts it. Set the ID to `diagnosis-click-explicit-context-v2` and assert
  `EvaluationDataError` rejects it. Use this exact test and run only it first
  to observe the new v1 case fail:

  ```python
  def test_click_explicit_dataset_id_is_exact(self):
      manifest = copy.deepcopy(self.manifest)
      manifest["dataset_id"] = "diagnosis-click-explicit-context-v1"
      validate_manifest(manifest)
      manifest["dataset_id"] = "diagnosis-click-explicit-context-v2"
      with self.assertRaises(EvaluationDataError):
          validate_manifest(manifest)
  ```

- [ ] Add the v1 ID to the set and error message in
  `tools/diagnosis_data.py::validate_manifest`; do not broaden matching or
  modify the runner, product CLI, prompt, parser, or scorer. The set addition
  is exactly `"diagnosis-click-explicit-context-v1",`.
- [ ] Run `python3 -m unittest tests.test_diagnosis_data -q` and
  `git diff --check`. Inspect and commit only the two files.

**Acceptance:** The new exact ID is accepted; an unlisted variant is rejected;
old manifests and optional extras retain their existing behavior.

## Task 2: Freeze eight source-backed cases

- [ ] Recheck the four detached checkout HEADs and clean status under
  `.local/diagnosis/click-explicit-candidates-20260929`:
  `acc91bc4f47e38f43277fcdfd8ca855734c4fbbc`,
  `5eb46cba463ff3e3894b58f6649c5a13f02a70b1`,
  `02046e7a19480f85fff7e4577486518abe47e401`,
  `1a4d8c1bb1e8f8e214ede7223bd2c05dc2ce006a`.
  Check both fixed commits' first parents match their bug snapshots.
- [ ] Re-read the two official PRs, exact fix diffs, and upstream regression
  tests. Confirm trigger, old behavior, repaired behavior, and narrow fixed
  contract. The primary agent approves ground truth before freezing the file.
- [ ] Create `evaluation/diagnosis/click-explicit-context-v1.json` with
  `schema_version: 1`, dataset ID from Task 1, and eight cases ordered
  completion bug/default, bug/explicit, fixed/default, fixed/explicit, then
  metavar in the same order. Use distinct pair IDs for default and explicit
  arms; each pair contains one `bug` and one `fixed` row. The target symbols,
  full commits, and exact source span/hash are in the spec. Default rows omit
  `include_symbols`; explicit rows contain the matching single `Choice`
  method. Use `https://github.com/pallets/click`, checkout names
  `click-<first 12 SHA>`, primary references to PR, issue, commit, source,
  and upstream test, and approved primary-agent annotations. State the two
  narrow trigger/outcome contracts in `ground_truth`; do not assert that a
  repaired snapshot is defect-free.
- [ ] Check `validate_manifest`, `_verified_checkout`, source fingerprints,
  unique target and extra symbol resolution, and default/explicit context
  selection offline. Confirm no block is truncated and all selected source
  fits 120 lines and 64 KiB. Compute the manifest's exact byte SHA-256 and
  add provenance and clean-checkout recreation instructions to
  `evaluation/diagnosis/README.md`. Commit the manifest and README before
  preparing requests.

**Acceptance:** Eight source-backed rows reproduce from four clean checkouts;
the model payload contains none of the labels or ground truth.

## Task 3: Prepare and dispatch once

- [ ] From the clean committed analyzer, run:

  ```sh
  python3 -m tools.evaluate_diagnosis prepare \
    --manifest evaluation/diagnosis/click-explicit-context-v1.json \
    --repos-root .local/diagnosis/click-explicit-candidates-20260929 \
    --model deepseek-flash --max-lines 120 --response-format json-schema \
    --out-dir .local/diagnosis/click-explicit-plan-20260929
  ```

- [ ] Inspect all eight contexts and exact serialized request hashes.
  Independently rebuild each hash from the prepared context and existing
  serializer. Verify default bug/fixed request hashes are equal within each
  pair, explicit bug/fixed hashes differ, all targets remain unchanged, and
  prompts contain no labels, case IDs, issues, or ground truth. Record plan
  SHA-256 and analyzer commit before any upload. Stop on any mismatch.
- [ ] Run `python3 -m repo_doctor doctor --deepseek --model deepseek-flash
  --json .` and require `deepseek.status == "ready"`. Its model-list request
  contains no source. If not ready, stop before consuming the cohort.
- [ ] Run exactly once, sequentially:

  ```sh
  python3 -m tools.evaluate_diagnosis run \
    --manifest evaluation/diagnosis/click-explicit-context-v1.json \
    --repos-root .local/diagnosis/click-explicit-candidates-20260929 \
    --plan-dir .local/diagnosis/click-explicit-plan-20260929 \
    --out-dir .local/diagnosis/click-explicit-run-20260929 \
    --repeats 1 --max-calls 8 --allow-network
  ```

- [ ] Inspect the safe run summary. If it stops early, preserve the partial
  run, make no retry, and report completion plus unknown quality. Do not
  reuse this cohort as unseen data after any request is attempted.

**Acceptance:** Prepared source/request hashes match an independent rebuild;
at most eight calls occur, and any failure stops further dispatch.

## Task 4: Review, report, and integrate

- [ ] Create the review template with `python3 -m tools.evaluate_diagnosis
  prepare-review --run-dir .local/diagnosis/click-explicit-run-20260929
  --out-file .local/diagnosis/click-explicit-review-20260929.json`. For each
  completed response, inspect every accepted finding against the pinned
  source and repair; mark TP, FP, uncertain, or duplicate with concise
  source-backed rationale. Preserve rejected findings separately.
- [ ] Run `tools.evaluate_diagnosis score` with the frozen manifest, run dir,
  completed review file, and new ignored JSON/Markdown outputs. Report
  completed calls, parse and grounding status, bug matches, fixed alarms,
  uncertainty, and provider usage per arm. Apply the spec's narrow usefulness
  rule without treating a partial run or historical sample as an accuracy
  estimate.
- [ ] Write `docs/evaluations/2026-09-29-click-explicit-context.md`, update
  `evaluation/diagnosis/README.md` and `docs/execution-status.md`. State the
  one-library, two-repair, one-sample, primary-review limitations.
- [ ] Run the focused data tests, one full `python3 -m unittest discover -s
  tests -q`, `python3 -m compileall -q repo_doctor tools tests`, and
  `git diff --check`. Review the diff; commit, push, open a PR against
  `codex/repo-doctor-v1`, attach it to this task, check Python 3.11–3.13 CI
  on the exact head, and integrate under standing user authorization if clean.

**Acceptance:** Reproducible paired evidence and a decision bounded by its
actual responses, with no product-default change absent the preregistered
signal.
