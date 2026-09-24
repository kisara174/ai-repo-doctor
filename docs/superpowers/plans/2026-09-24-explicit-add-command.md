# Explicit Click add_command Registration Implementation Plan

> **For agentic workers:** Execute inline task-by-task. Preserve the existing `baseline-v1` manifest and report.

**Goal:** Recognize source-provable explicit Click `add_command` registrations as `command_registration` semantic edges.

**Architecture:** Capture the minimal internal AST data needed to identify simple `add_command` calls and class base expressions during the existing parse pass. Resolve edges in the Click semantic pass only when the receiver and callback both resolve to known local Click group/command symbols; do not change public JSON fields or execute target code.

**Tech Stack:** Python 3.11+ standard library, AST, existing source-fingerprint evaluator.

**Spec:** `docs/superpowers/specs/2026-09-24-repo-doctor-v2-design.md` — “装饰器与 Click 注册关系”.

## Global Constraints

- Analyze source statically; do not import or execute target repositories.
- Keep `command_registration` in `semantic_edges`; do not alter the public JSON schema.
- Emit only edges with a proven Click group receiver and a proven local Click command or group callback.
- Preserve the frozen `baseline-v1` manifest and report files.
- Validate against the source-backed `challenge-v1` evaluator and separately regenerate baseline output under `/tmp` for regression comparison.
- Do not add or run unit tests in this task; use the requested fixed-snapshot evaluations as validation.

---

### Task 1: Preserve explicit registration syntax in internal parse metadata

**Files:**
- Modify: `repo_doctor/model.py`
- Modify: `repo_doctor/parser.py`
- Modify: `repo_doctor/index.py`

**Produces:** `RepoIndex.registration_calls` records with source file, line, receiver name, callback name, lexical caller, and enclosing class (when present). Class `Symbol` records retain base-expression strings internally. Neither field is serialized by `repo_doctor/cli.py`.

- [ ] Add a frozen internal `CommandRegistrationCall` record. Add a trailing `base_expressions` field to `Symbol`, a defaulted `registration_calls` field to `ParsedFile`, and `registration_calls` to `RepoIndex`.
- [ ] In `_Extractor._add_symbol`, save `ast.unparse(base)` for `ClassDef` bases.
- [ ] In `_Extractor.visit_Call`, record only calls shaped as `name.add_command(callback_name)` with exactly one positional `ast.Name` argument, no keyword arguments, and an `ast.Name` receiver. Record these at module scope and inside direct class methods; preserve the enclosing method and nearest class IDs when available. Continue generic traversal so normal call extraction remains unchanged.
- [ ] Return the metadata from `parse_python_file` and aggregate it in `build_index`.
- [ ] Confirm with a focused source inspection that `_symbol_data` remains explicit and does not serialize `base_expressions` or registration-call internals.

### Task 2: Resolve only source-provable Click registrations

**Files:**
- Modify: `repo_doctor/semantics.py`

**Consumes:** Existing recognized decorator identities, import references, module bindings, class symbols and Task 1 metadata.

**Produces:** Additional `SemanticEdge(kind="command_registration", ...)` records whose source is a known group callback or a class proven to inherit Click `Group`, and whose target is a known same-module Click command/group callback.

- [ ] Identify command callbacks as top-level functions with a confirmed `click.command` or `click.group` decorator; retain the existing group callback set for parent checks.
- [ ] Resolve a name receiver only when it uniquely identifies a known group callback and is not locally shadowed or module-rebound.
- [ ] Resolve `self` only inside a direct class method when the enclosing class’s same-module base chain reaches `click.Group` or a statically imported alias of `Group`. Stop on cycles, ambiguous symbols, shadowed aliases, or unknown bases.
- [ ] Resolve the sole callback argument only when it names a same-module top-level function with a confirmed Click command/group decorator and no binding conflict.
- [ ] Emit the call line as `evidence_file` / `line`; preserve existing decorator registration behavior and deterministic edge sorting.

### Task 3: Verify challenge acceptance and baseline preservation

**Files:**
- Update: `docs/superpowers/specs/2026-09-24-repo-doctor-v2-design.md`
- Update: `evaluation/README.md`
- Regenerate: `evaluation/results/challenge-v1.json`
- Regenerate: `evaluation/results/challenge-v1.md`

- [ ] Run the five-run challenge evaluation from the repository root:

```bash
python3 tools/evaluate_baseline.py \
  --manifest evaluation/challenge-v1.json \
  --repos-root /tmp/ai-repo-doctor-checkouts \
  --runs 5 \
  --json-out evaluation/results/challenge-v1.json \
  --markdown-out evaluation/results/challenge-v1.md
```

- [ ] Confirm `click-registration-003` and `flask-registration-001` are true positives, all five hashes are stable within each repository, and no new false positives appear.
- [ ] Run the five-run baseline evaluation to temporary output paths so the published baseline report remains unchanged:

```bash
python3 tools/evaluate_baseline.py \
  --manifest evaluation/baseline-v1.json \
  --repos-root /tmp/ai-repo-doctor-checkouts \
  --runs 5 \
  --json-out /tmp/ai-repo-doctor-baseline-after-add-command.json \
  --markdown-out /tmp/ai-repo-doctor-baseline-after-add-command.md
```

- [ ] Compare baseline relation metrics and mismatch IDs with `evaluation/results/v2-baseline.json`; preserve the checked-in baseline manifest/report hashes.
- [ ] Update the README’s challenge-result note to describe the regenerated report, run `git diff --check`, inspect the full diff, then commit the implementation and reports.
