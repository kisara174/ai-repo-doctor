# Paired Explicit-Context Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task by
> task. The primary agent owns upstream interpretation, protocol, provider
> calls, behavioral review, integration, and final acceptance. A Luna executor
> may take only a separately specified mechanical packet under `AGENTS.md`.
> Steps use checkbox syntax for tracking.

**Goal:** Test whether an explicitly supplied local subclass method improves
diagnosis on two unseen Werkzeug bug/fixed pairs without new fixed-case alarms.

**Architecture:** Extend the existing optional evaluation manifest and both
offline/online context builders with `include_symbols`. Keep the current
product context builder, prompt, response parser, and scorer. Freeze eight
case/arm combinations in one manifest, then use the existing sequential
runner and manual review workflow.

**Tech Stack:** Python 3.11–3.13, `unittest`, Git, existing
`tools.evaluate_diagnosis`, optional DeepSeek Responses API.

**Spec:** [Paired explicit-context design](../specs/2026-09-29-paired-explicit-context-design.md).

## Global constraints

- Work on `codex/paired-context-eval-v0.8` in the existing managed worktree.
- Preserve all previous manifests and their prepared/run artifacts.
- Read target source and tests, but do not execute or install target code.
- Keep `deepseek-flash`, Responses `json_schema`, no thinking field, 4,096
  output tokens, and the existing source/request budgets.
- Make one provider call per case, sequentially, without retry. Stop on error.
- Keep the Key, raw provider bodies, labels, ground truth, and fix references
  out of requests and committed artifacts.
- Use source-based primary review; quotation validation alone is insufficient.
- Run focused tests during implementation and one full suite before PR.

## Files and responsibilities

| Path | Responsibility |
| --- | --- |
| `tools/diagnosis_data.py` | Validate optional extras and prepare exact context/hash. |
| `tools/diagnosis_runner.py` | Rebuild extras from the pinned checkout before transport. |
| `tests/test_diagnosis_data.py` | Red/green coverage for valid, malformed, unknown extras and unchanged default. |
| `tests/test_diagnosis_runner.py` | Red/green preflight and tamper rejection before client/output. |
| `evaluation/diagnosis/werkzeug-explicit-context-v1.json` | Frozen eight-case paired comparison. |
| `evaluation/diagnosis/README.md` | Reproduction commands, manifest hash, limitations. |
| `docs/evaluations/2026-09-29-paired-explicit-context.md` | Safe outcomes and source review. |
| `docs/execution-status.md` | Current evidence and next gate. |
| `.local/diagnosis/explicit-*` | Ignored checkouts, plan, run, review, score. |

## Task 1: Bind case-selected symbols to evaluation preparation and preflight

- [x] In `tests/test_diagnosis_data.py`, extend the committed fixture source
  with a distinct `helper` function, update fixture target line numbers and
  source hash if needed, and add a focused test whose manifest case has
  `"include_symbols": ["app.py::helper"]`. Assert the prepared context
  contains that helper with `relation == "user_selected"`, and its plan case
  records the list. The same case without the field must omit both helper and
  plan field. Run only this test and observe failure for the new behavior.
- [x] Add manifest validation tests rejecting an empty list, duplicate name,
  target name, malformed name, unknown name, and ambiguous name. The existing
  unknown target test remains separate. Run the focused tests red.
- [x] In `tools/diagnosis_data.py`, admit only dataset ID
  `diagnosis-werkzeug-explicit-context-v1`; validate optional extras as a
  nonempty list of distinct `path.py::qualified_name` strings that exclude
  the target. Use `_safe_source_path` for the path. During preparation, use
  `build_context(index, case["symbol"], max_lines,
  include_symbols=tuple(case.get("include_symbols", [])))`, and add
  `include_symbols` to the plan case only when the manifest contains it.
  Convert unknown/ambiguous extra lookup into `EvaluationDataError` before
  publishing output. Run `python3 -m unittest tests.test_diagnosis_data -q`.
- [x] In `tests/test_diagnosis_runner.py`, prepare a manifest with one extra
  symbol and assert the real preflight permits a client returning empty
  findings. Add a tamper case that removes or substitutes the prepared extra
  while keeping the old plan: `run_cases` must reject before output directory
  creation and before the client is called. Run these tests red.
- [x] In `tools/diagnosis_runner.py`, require the plan case's optional list to
  equal the manifest case list and rebuild with that tuple. Preserve old-plan
  behavior for absent lists. Run
  `python3 -m unittest tests.test_diagnosis_data tests.test_diagnosis_runner -q`
  and `git diff --check`; inspect the diff and commit only these four files.

**Acceptance:** Explicit extras change exactly the selected context/request;
old manifests prepare identically, and changed extras cannot reach transport.

## Task 2: Freeze eight source-backed cases

- [x] Confirm the four detached checkouts below have the exact HEADs, no tracked
  or untracked changes, and that each bug commit is the fixed commit's first
  parent. The existing ignored root is
  `.local/diagnosis/explicit-holdout-checkouts-20260929`:

  | Checkout suffix | Commit |
  | --- | --- |
  | `0c5cad57c237` | `0c5cad57c2370c4b916b3651adb4d82eb9fbf5ec` |
  | `625362a42926` | `625362a429263f8d713a9ed06c18f247042d7d0f` |
  | `3790dc177329` | `3790dc177329a5214bd318be6e1dfd43d680eb64` |
  | `57521600ce04` | `57521600ce04fdf4d977c36f89fc51191aa8a3c9` |

- [x] Re-read the two upstream repair diffs and regression checks. Confirm
  the source behavior and target SHA-256 table in the spec, plus the selected
  extra method on both snapshots. Reject a row if its mechanism is not
  supported by the pinned source. No target runtime execution.
- [x] Create `evaluation/diagnosis/werkzeug-explicit-context-v1.json` with
  schema version 1 and dataset ID `diagnosis-werkzeug-explicit-context-v1`.
  Use the existing case keys. For each repair use four case IDs in this order:
  `werkzeug-empty-special-bug-default`,
  `werkzeug-empty-special-bug-explicit`,
  `werkzeug-empty-special-fixed-default`,
  `werkzeug-empty-special-fixed-explicit`, then
  `werkzeug-nonstring-key-bug-default`,
  `werkzeug-nonstring-key-bug-explicit`,
  `werkzeug-nonstring-key-fixed-default`,
  `werkzeug-nonstring-key-fixed-explicit`.
  Pair IDs are `werkzeug-empty-special-default`,
  `werkzeug-empty-special-explicit`, `werkzeug-nonstring-key-default`, and
  `werkzeug-nonstring-key-explicit`. The explicit rows alone carry their
  one-element `include_symbols` list from the spec. Bug/fixed arm mates use
  the same `issue_id`, repository URL, and target symbol; snapshot mates use
  the same commit, checkout ID, target span, and target hash.
- [x] State narrow ground truth per row: empty special header values yielded
  by old `EnvironHeaders.__iter__` but skipped after repair, or non-string
  `get` key causing old `AttributeError` but returning a supplied default
  after repair. Do not call a fixed snapshot generally defect-free. Add
  upstream source/fix/test links and UTC primary approval annotations.
- [x] Check `validate_manifest`, `_verified_checkout`, `_source_fingerprint`,
  unique target and extra symbols, and source budgets. Confirm the eventual
  prompt contains no case ID, arm, ground truth, or reference. Record the
  manifest file's SHA-256 and checkout reproduction instructions in
  `evaluation/diagnosis/README.md`. Commit manifest and README.

**Acceptance:** Eight frozen, independently source-vetted rows validate
offline with exactly the intended source delta.

## Task 3: Prepare and run the frozen comparison

- [x] From a clean analyzer commit, run:

  ```sh
  python3 -m tools.evaluate_diagnosis prepare \
    --manifest evaluation/diagnosis/werkzeug-explicit-context-v1.json \
    --repos-root .local/diagnosis/explicit-holdout-checkouts-20260929 \
    --model deepseek-flash --response-format json-schema --max-lines 120 \
    --out-dir .local/diagnosis/explicit-context-plan-20260929
  ```

- [x] Inspect eight context and request hashes, source line/byte counts,
  selected extra blocks, and the exact JSON Schema serialized body. Confirm
  each default/explicit snapshot mate has the same target SHA-256 and the
  extra method appears only in the explicit arm. Keep the plan immutable.
- [x] If the Key is available, run exactly once, sequentially:

  ```sh
  python3 -m tools.evaluate_diagnosis run \
    --manifest evaluation/diagnosis/werkzeug-explicit-context-v1.json \
    --repos-root .local/diagnosis/explicit-holdout-checkouts-20260929 \
    --plan-dir .local/diagnosis/explicit-context-plan-20260929 \
    --out-dir .local/diagnosis/explicit-context-run-20260929 \
    --repeats 1 --max-calls 8 --allow-network
  ```

  A missing/rejected Key or provider failure stops the run. Preserve partial
  output and do not retry failed cases under this manifest.

**Acceptance:** Exact frozen requests sent at most once, or a documented
offline-only/partial state without invented quality findings.

## Task 4: Review, report, and integrate

- [x] For each completed response, create a review template with
  `python3 -m tools.evaluate_diagnosis prepare-review --run-dir
  .local/diagnosis/explicit-context-run-20260929 --out-file
  .local/diagnosis/explicit-context-review-20260929.json`. Inspect accepted
  findings against pinned source and upstream repair. Fill TP, FP,
  uncertain, or duplicate and concise source-backed rationales. Score only
  when the review is complete.
- [x] Use `tools.evaluate_diagnosis score` with the frozen manifest, run dir,
  review JSON, and new ignored JSON/Markdown outputs. Report completion,
  grounding, bug detection and fixed-case alarms per arm, model token usage,
  any uncertain findings, and the preregistered narrow usefulness signal.
- [x] Update `docs/evaluations/2026-09-29-paired-explicit-context.md` and
  `docs/execution-status.md`. Keep cloud diagnosis experimental and state
  same-repository, two-repair, primary-only limitations.
- [ ] Review the full diff, run
  `python3 -m unittest discover -s tests -q`,
  `python3 -m compileall -q repo_doctor tools tests`, and `git diff --check`
  once. Commit, push, open a PR against `codex/repo-doctor-v1`, attach it to
  this task, inspect Python 3.11–3.13 CI on the exact PR head, then integrate
  under the standing user authorization if review and CI are clean.

**Acceptance:** Reproducible comparison evidence and a decision that does not
upgrade a purposive result into a general accuracy claim.
