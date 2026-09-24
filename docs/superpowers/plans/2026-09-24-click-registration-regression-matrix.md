# Click Explicit Registration Regression Matrix Plan

**Goal:** Protect conservative `add_command` inference with behavior tests and an expanded source-backed challenge set.

**Scope:** Continue on `codex/explicit-add-command-registration`. Keep `challenge-v1` and all `baseline-v1` files unchanged. Do not import or execute target repositories or install their dependencies.

## Task 1: Add semantic behavior tests before production changes

**File:** `tests/test_semantics.py`

- [x] Add a failing regression for a method that rebinds `self` before calling `self.add_command(...)`; expect no registration edge.
- [x] Cover positive same-module source forms: aliased Click module, imported `Group` alias with a multi-hop local base chain, and an explicit registration target already proven by a Click decorator edge.
- [x] Cover negative near misses: a non-Click class, unknown/attribute receiver, callback or receiver rebinding, and dynamic/keyword/expanded callback arguments.
- [x] Run the focused failing test and verify it fails specifically because the invalid edge was emitted.

## Task 2: Fix only confirmed inference gaps

**Files:** `repo_doctor/model.py`, `repo_doctor/parser.py`, `repo_doctor/semantics.py`

- [x] Preserve enough internal source metadata to distinguish the method's `self` parameter from a later assignment or deletion of `self`.
- [x] Reject explicit registration when that receiver parameter is rebound in the containing method.
- [x] Run the relevant semantic tests after each minimal fix; keep public JSON unchanged.

## Task 3: Support versioned negative registration probes

**Files:** `tools/evaluate_baseline.py`, `tests/test_evaluation.py`

- [x] Add manifest validation for `challenge-v2` pinned to the same three immutable source snapshots.
- [x] Allow negative `command_registration` probes to omit invented parent/callback IDs; still require an evidence line and an unresolved reason.
- [x] Add evaluator tests proving such negatives validate and false positives at the evidence line count against them.

## Task 4: Publish a separate challenge-v2 snapshot

**Files:** `evaluation/challenge-v2.json`, `evaluation/README.md`

- [x] Copy the reviewed challenge-v1 probes without changing challenge-v1.
- [x] Add source-fingerprinted positives or negatives for the additional explicit-registration boundaries identified in Click and Flask source.
- [x] Run five scans per repository into `evaluation/results/challenge-v2.json` and `.md`.
- [x] Confirm all hashes are stable and inspect every TP, FP, and FN.

## Task 5: Final regression review

- [x] Run the full `unittest` suite.
- [x] Run challenge-v1 and challenge-v2 five-run evaluations; write baseline-v1 comparison output only under `/tmp`.
- [x] Confirm frozen baseline hashes and challenge-v1 report hashes remain unchanged.
- [x] Review the complete diff and update this plan.
- [x] Push the updated PR branch.
