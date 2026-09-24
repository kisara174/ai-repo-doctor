# 可复现基础评估 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AI Repo Doctor V2 建立一套固定源码快照、人工标注探针、可复跑指标和 CLI 耗时报告。

**Architecture:** 新增仅依赖 Python 标准库的开发工具 `tools/evaluate_baseline.py`。它校验固定 Git 快照和证据指纹，调用现有 `python -m repo_doctor scan ... --json`，只在人工标注 probe 集上计算关系指标，并输出 JSON 与 Markdown 报告；它不会导入或运行目标仓库代码。

**Tech Stack:** Python 3.11+, 标准库 `argparse`、`json`、`hashlib`、`subprocess`、`time`、`platform`、`unittest`；Git 固定快照；Repo Doctor JSON schema 2。

**Spec:** `docs/superpowers/specs/2026-09-24-baseline-evaluation-design.md`

## Global Constraints

- Python runtime floor remains 3.11+; no third-party dependency is added.
- Runner must not clone/fetch, access the network, import or execute target repository code, write target checkouts, or install target dependencies.
- The three target repositories and commits remain Click `06b2a678741131fd577ce170e23e5ca0aeba0309`, Requests `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`, and Flask `d73fa1cdcbd8b1465c151db8924ba58b1dd14e35`.
- Runner accepts only clean target checkouts at those exact commits and Repo Doctor scan output with `schema_version == 2`.
- Metrics describe only curated probes; all unannotated graph relations are excluded.
- Calls, re-exports, command registrations, overload resolution, and overload signatures remain separately scored relation types.
- A zero precision or recall denominator is serialized as JSON `null`.
- Default scan repetitions are 5; the report records all durations, their median/minimum/maximum, and environment metadata.
- A validation, scan, determinism, or rendering error must not leave a partial successful report.
- Do not add this evaluation runner to regular CI or compare against V1 in this baseline.
- The primary agent owns source annotation choices, task decomposition, debugging, review, and acceptance. Delegate only a separately bounded mechanical change that meets the repository Luna routing policy.

---

## Files and Responsibilities

- Create `tools/__init__.py`: make the source-only `tools` directory importable by unit tests; it is excluded from the distributable `repo_doctor*` package.
- Create `tools/evaluate_baseline.py`: manifest validation, source fingerprint checks, scanner output normalization, relation scoring, fixed-snapshot preflight, repeated CLI scans, and JSON/Markdown output.
- Create `tests/test_evaluation.py`: standard-library tests for manifest validation, source fingerprints, relation projection, metrics, Git preflight, deterministic summaries, subprocess boundaries, and report failure handling.
- Create `evaluation/baseline-v1.json`: pinned repository metadata and manually reviewed source probes with evidence hashes.
- Create `evaluation/README.md`: commands to obtain the pinned snapshots and run the evaluator; clone/fetch is a developer setup step outside the runner.
- Create `evaluation/results/v2-baseline.json` and `evaluation/results/v2-baseline.md`: first successful five-run report.
- Do not modify `repo_doctor/`, `pyproject.toml`, or the existing public CLI schema for this evaluation tool.

### Task 1: Add manifest and evidence validation

**Files:**

- Create: `tools/__init__.py`
- Create: `tools/evaluate_baseline.py`
- Create: `tests/test_evaluation.py`

**Interfaces:**

- `load_manifest(path: Path) -> dict[str, object]` loads UTF-8 JSON and requires top-level `schema_version == 1`, `dataset_id == "baseline-v1"`, and a `repositories` list.
- Each repository entry has `id`, official `https_url`, 40-hex `commit`, and `probes` list. Repository IDs are unique.
- Every probe has globally unique `id`, `kind`, `evidence`, and nonempty `rationale`. `evidence` has a safe repository-relative POSIX `file`, 1-based inclusive `start_line` and `end_line`, and 64-hex `sha256`.
- Allowed `kind` values are `call`, `reexport`, `command_registration`, and `overload`. A `call` requires `caller`, `expression`, and either a nonempty `expected_target` or a nonempty `unresolved_reason`, but not both. A `reexport` requires `exported_name` and the same target/reason rule. A `command_registration` requires `parent_symbol`, `callback_symbol`, and Boolean `expect_edge`; a negative probe requires `unresolved_reason`. An `overload` requires `symbol_id`, `expected_state` (`resolved` or `ambiguous`), and `expected_signatures`; resolved probes require a nonempty list, while ambiguous probes require an empty list.
- `validate_manifest_data(manifest: dict[str, object]) -> None` checks structure, required fields, unique repository/probe IDs, unique relation selectors, valid hashes/line ranges, and expectation rules without needing repository checkouts. Selector keys are `(repo_id, kind, file, caller, line)` for calls, `(repo_id, kind, file, line, exported_name)` for re-exports, `(repo_id, kind, file, line)` for registrations, and `(repo_id, kind, symbol_id)` for overloads.
- `source_fingerprint(path: Path, start_line: int, end_line: int) -> str` decodes UTF-8, selects the inclusive lines from `splitlines()`, rejoins them with one `\n`, and returns the SHA-256 hex digest.
- `validate_evidence(repo_root: Path, probe: dict[str, object]) -> None` resolves the probe's repository-relative file under `repo_root`, rejects symlinks resolving outside the checkout, and raises `EvaluationError` when the selected source hash differs.
- Raise `EvaluationError` with the repository/probe ID and failed field when an input is malformed, a path escapes the checkout, or a fingerprint differs.

- [x] **Step 1: Add a passing test for a valid in-memory manifest and line fingerprint**

```python
source = "first\r\nselected one\r\nselected two\r\nlast\r\n"
expected_text = "selected one\nselected two"
expected_hash = hashlib.sha256(expected_text.encode("utf-8")).hexdigest()
```

Write `source` to a temporary file, assert `source_fingerprint(path, 2, 3) == expected_hash`, and assert a valid manifest with one resolved call probe passes `validate_manifest_data()`.

- [x] **Step 2: Run the focused tests and verify the new imports fail**

Run: `python3 -m unittest tests.test_evaluation.ManifestTests -v`

Expected: FAIL because `tools.evaluate_baseline` and its validation functions do not exist yet.

- [x] **Step 3: Add the evaluator module, error type, JSON loader, schema checks, and fingerprint function**

Implement a safe-path check with `PurePosixPath`: reject absolute paths, empty components, and any `..` component. Require `1 <= start_line <= end_line <= len(lines)` before hashing. Normalize only selected source line endings as specified; do not hash surrounding source.

```python
text = "\n".join(lines[start_line - 1 : end_line])
return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [x] **Step 4: Add rejection tests for malformed schema, duplicate IDs, path traversal, and stale hashes**

Test `schema_version == 2`, duplicate probe IDs, `../../outside.py`, reversed line ranges, a missing required call selector, both `expected_target` and `unresolved_reason` set, neither set, and a source edit after hashing. Each case must raise `EvaluationError` with a message containing the probe ID or field name.

- [x] **Step 5: Run manifest tests and commit**

Run: `python3 -m unittest tests.test_evaluation.ManifestTests -v`

Expected: all valid manifest and fingerprint tests pass; every invalid case is rejected before scanning.

```bash
git add tools/__init__.py tools/evaluate_baseline.py tests/test_evaluation.py
git commit -m "Add baseline evaluation input validation"
```

### Task 2: Normalize probes and calculate sampled metrics

**Files:**

- Modify: `tools/evaluate_baseline.py`
- Modify: `tests/test_evaluation.py`

**Interfaces:**

- `_probe_relations(probe: dict[str, object], scan: dict[str, object]) -> dict[str, tuple[set[tuple[str, ...]], set[tuple[str, ...]]]]` returns, per relation type, the expected and predicted normalized relation sets, with every tuple already prefixed by the probe ID.
- `_score(expected: set[tuple[str, ...]], predicted: set[tuple[str, ...]]) -> dict[str, int | float | None]` returns `tp`, `fp`, `fn`, `precision`, and `recall` using set operations.
- Call selectors use `(evidence.file, caller, evidence.start_line)`. Exactly one `calls[]` record must match that site and its `expression` must equal the manifest selector; zero or multiple matches fail. Any same-site `call_edges[]` entries produce predicted callee relations.
- Re-export selectors use `kind == "reexport"`, `evidence_file == evidence.file`, `line == evidence.start_line`, and `exported_name`; the normalized relation includes both `source_file` and `target_symbol`, so a wrong endpoint produces FP and FN.
- Registration selectors use `kind == "command_registration"`, `evidence_file == evidence.file`, and `line == evidence.start_line`; compare the full `(source_symbol, target_symbol)` endpoint pair with the expected pair or empty set.
- Overload resolution predicts `(symbol_id, symbol_id)` only when the ID appears in `symbols[]` and not in `ambiguous_symbols`. Signature relations are `(symbol_id, signature_text)` from that symbol's ordered `overloads` list.
- Keep the probe ID in each relation tuple through scoring and serialization so two probes cannot double count one another.

- [x] **Step 1: Add a unit test proving an incorrect target is both FP and FN**

```python
expected = {("probe-1", "call", "caller", "pkg.py::wanted")}
predicted = {("probe-1", "call", "caller", "pkg.py::other")}
result = _score(expected, predicted)
```

Assert `tp == 0`, `fp == 1`, `fn == 1`, `precision == 0.0`, and `recall == 0.0`.

- [x] **Step 2: Run the focused metric test and confirm it fails**

Run: `python3 -m unittest tests.test_evaluation.MetricTests.test_wrong_target_is_false_positive_and_false_negative -v`

Expected: FAIL because `_score` does not exist.

- [x] **Step 3: Implement set scoring and call/re-export/registration relation projection**

Use `expected & predicted`, `predicted - expected`, and `expected - predicted` for TP, FP, and FN. Compute each ratio only when its denominator is nonzero; otherwise return `None`. Keep each relation family under its own metric key.

```python
precision = tp / (tp + fp) if tp + fp else None
recall = tp / (tp + fn) if tp + fn else None
```

- [x] **Step 4: Add overload projection and same-line call ambiguity tests**

Test a resolved symbol with two signatures, an ambiguous symbol with no canonical implementation, and a wrong signature. Build two `calls[]` records with the same caller and line but different expressions and assert `_probe_relations()` rejects the probe even when the manifest expression matches one of them.

- [x] **Step 5: Test empty denominators and negative probes**

Assert `_score(set(), set())` serializes both metrics as `None`; an expected-empty registration probe with one predicted endpoint has `fp == 1`; a correct unresolved call with no predicted edge has no FP or FN.

- [x] **Step 6: Run focused tests and commit**

Run: `python3 -m unittest tests.test_evaluation.MetricTests -v`

Expected: wrong targets produce FP+FN, negative probes detect unexpected edges, same-line calls are rejected, and overload resolution/signatures score independently.

```bash
git add tools/evaluate_baseline.py tests/test_evaluation.py
git commit -m "Score annotated repository probes"
```

### Task 3: Validate snapshots and run deterministic repeated scans

**Files:**

- Modify: `tools/evaluate_baseline.py`
- Modify: `tests/test_evaluation.py`

**Interfaces:**

- `validate_snapshot(repo: Path, expected_commit: str) -> None` uses read-only Git subprocesses to require exact `HEAD` and empty `git status --porcelain --untracked-files=all`.
- `scan_repository(project_root: Path, repo: Path) -> tuple[dict[str, object], float]` invokes `[sys.executable, "-m", "repo_doctor", "scan", str(repo), "--json"]` with `cwd=project_root`, `shell=False`, captured text output, and `time.perf_counter()` timing. It rejects nonzero exit, invalid JSON, and schema versions other than 2.
- `canonical_scan_digest(scan: dict[str, object]) -> str` hashes UTF-8 JSON encoded with sorted keys and compact separators.
- `evaluate_snapshot(repo_entry: dict[str, object], repo: Path, project_root: Path, runs: int) -> dict[str, object]` runs all scans, requires one repeated digest, and returns all durations and the digest list.
- Before the first scanner subprocess, preflight all three repository SHAs/clean states, evidence paths/fingerprints, and manifest-level selector uniqueness. After each scan, verify that every call probe selects exactly one `calls[]` record and that its expression matches before scoring that repository. No report paths are opened during preflight or scanning.

- [x] **Step 1: Add temporary-Git-repository tests for exact commit and cleanliness**

Create a temporary Git repo with `git init`, configure a local test author, commit one file, and record `HEAD`. Assert that exact SHA passes; a different SHA, a modified tracked file, and an untracked file each raise `EvaluationError`.

- [x] **Step 2: Run the snapshot tests and confirm they fail**

Run: `python3 -m unittest tests.test_evaluation.SnapshotTests -v`

Expected: FAIL because `validate_snapshot()` does not exist.

- [x] **Step 3: Add read-only snapshot preflight and the safe CLI subprocess wrapper**

Pass subprocess arguments as lists and set `shell=False`. Do not call `git clone`, `git fetch`, pip, `importlib`, `runpy`, or any command inside a target checkout. Resolve every evidence path under `repo.resolve()` and reject a resolved path outside that directory.

```python
command = [sys.executable, "-m", "repo_doctor", "scan", str(repo), "--json"]
completed = subprocess.run(command, cwd=project_root, capture_output=True, text=True, check=False)
```

- [x] **Step 4: Add timing, canonical scan hashes, and repeated-run checks**

Reject `runs < 1`. For each target, retain every elapsed duration and every scan digest; raise before report rendering if any digest differs. Include the scan JSON `stats` for repository size context, but do not use unresolved-call totals or unannotated graph edges in precision/recall.

- [x] **Step 5: Add tests for schema mismatch, nonzero CLI exit, unstable hashes, and target code non-execution**

Use a target file whose top-level code would create a marker file if executed. Run the real Repo Doctor CLI wrapper against the temporary target and assert the marker does not exist and the checkout remains clean. Inject a fake subprocess result in the nonzero-exit and changing-hash tests; verify the invocation uses an argument list and does not set `shell=True`.

- [x] **Step 6: Run snapshot and evaluator tests and commit**

Run: `python3 -m unittest tests.test_evaluation.SnapshotTests -v`

Expected: exact clean snapshots pass; wrong SHA, dirty state, target execution attempt, schema mismatch, nonzero exit, and unstable output all fail before report generation.

```bash
git add tools/evaluate_baseline.py tests/test_evaluation.py
git commit -m "Run baseline scans on pinned clean snapshots"
```

### Task 4: Build the report model, CLI, and output renderers

**Files:**

- Modify: `tools/evaluate_baseline.py`
- Modify: `tests/test_evaluation.py`

**Interfaces:**

- `build_report(manifest: dict[str, object], results: list[dict[str, object]], repo_doctor_commit: str, runs: int) -> dict[str, object]` returns report schema 1 with UTC generation time, dataset ID, Python version, platform/architecture, analyzer commit, repository ID/URL/pinned SHA/stats, all run durations, median/minimum/maximum, all scan hashes, per-relation metrics and positive/negative probe counts, and every probe's expected/predicted/TP/FP/FN sets. A relation type with no probes is `not_sampled`.
- `render_markdown(report: dict[str, object]) -> str` creates repository sections, relation tables, probe mismatch IDs, timing summaries, and the sampled-metrics limitation.
- CLI: `python3 tools/evaluate_baseline.py --repos-root PATH [--manifest PATH] [--runs N] --json-out PATH --markdown-out PATH`; default manifest is `evaluation/baseline-v1.json`, default runs is 5, and `N` must be positive.
- Report JSON and Markdown are fully rendered in memory after all preflight/scans pass. Write both to temporary sibling paths, close them successfully, and only then replace destination files. Reject identical output paths. On earlier failure, existing outputs are unchanged.
- `main(argv: list[str] | None = None) -> int` returns 0 on complete success and 2 on evaluation/input/output failure with a concise stderr message.

- [x] **Step 1: Add a report aggregation test with two probes and separate relation metrics**

Build one call probe with one TP and one registration negative probe with one FP. Assert report categories remain separate and each has its own `tp`, `fp`, `fn`, precision, recall, positive/negative probe counts, and full per-probe details.

- [x] **Step 2: Run the focused report test and confirm it fails**

Run: `python3 -m unittest tests.test_evaluation.ReportTests.test_report_keeps_relation_families_separate -v`

Expected: FAIL because `build_report()` does not exist.

- [x] **Step 3: Implement stable report aggregation and Markdown rendering**

Serialize relation tuples as JSON arrays in deterministic sorted order. Render missing ratios as `—`, escape table delimiters in free text, and list only probe IDs with FP or FN in the Markdown mismatch summary. Keep complete probe detail in JSON.

- [x] **Step 4: Add CLI parsing and failure-preserving output writes**

Test default manifest and run count, rejection of `--runs 0`, identical output paths, and pre-existing report files remaining byte-for-byte unchanged when preflight fails. Stage rendered content in memory and write both temporary siblings before replacing destinations. If either replacement fails, remove any newly installed destination and restore every previous file from its backup before returning an error.

- [x] **Step 5: Run evaluator tests and commit**

Run: `python3 -m unittest tests.test_evaluation.ReportTests -v`

Expected: JSON has schema 1 and complete probe outcomes; Markdown has one section per repository and distinct relation rows; invalid runs and failed evaluation preserve prior outputs.

```bash
git add tools/evaluate_baseline.py tests/test_evaluation.py
git commit -m "Render reproducible baseline reports"
```

### Task 5: Curate pinned probes and document reproduction

**Files:**

- Create: `evaluation/baseline-v1.json`
- Create: `evaluation/README.md`
- Test: `tests/test_evaluation.py`

**Interfaces:**

- The manifest has dataset ID `baseline-v1`, schema version 1, and exactly three entries: `click`, `requests`, and `flask`, each with the URL and SHA in the approved design.
- Every probe has its own rationale and source fingerprint; source text is not copied into the manifest.
- Each repository has at least 6 positive ordinary call probes and 2 expected-unresolved ordinary call probes; at least 4 positive re-export probes; and at least 3 positive overload probes.
- Click includes the five verified registrations under `examples/repo/repo.py::cli` and at least five source-backed expected-no-registration candidates.
- Include a source-backed ambiguous overload negative where a snapshot supports one; otherwise exercise that negative only in the synthetic unit fixture and do not label the real repository as having such a sample.
- README acquisition commands use ordinary `git clone` followed by `git checkout --detach <pinned SHA>`; these network operations are explicitly setup-only and are never called by the evaluator.

- [x] **Step 1: Inventory scan candidates from the existing pinned scan JSON and source files**

For each snapshot, list resolved `calls[]`/`call_edges[]` pairs, `reexport` semantic edges, and symbols with nonempty `overloads`. Inspect the exact source lines in the checkout before selecting a probe. For unresolved calls, inspect the call expression and its local scope to ensure the expected-unresolved label is supported by visible source evidence. The existing fixed checkouts are `/tmp/ai-repo-doctor-v2-click`, `/tmp/ai-repo-doctor-v2-requests`, and `/tmp/ai-repo-doctor-baseline-flask`.

Run: `python3 -m unittest tests.test_evaluation.ManifestTests -v`

Expected: existing manifest contract tests pass before adding the real dataset.

- [x] **Step 2: Write the real manifest with evidence hashes and minimum category coverage**

Use unique descriptive IDs such as `click-call-001`, `requests-reexport-001`, and `flask-overload-001`. For each probe, hash only its inclusive evidence lines with `source_fingerprint()`. Use one call probe per unique `(file, caller, line)`; if multiple `calls[]` records share that site, choose another site rather than guessing an expression-to-edge association.

- [x] **Step 3: Add manifest structure and coverage tests**

Assert repository IDs and commit SHAs match the approved list, probe IDs and selectors are unique, all four kinds appear, each per-repository minimum is met, and Click has five positive and five negative command-registration probes. These structural unit tests load only the manifest. Source fingerprints are checked by the evaluator against the supplied clean snapshots during Task 6, so ordinary unit tests do not require network access or clones.

- [x] **Step 4: Write reproduction instructions**

Document the checkout directory layout `click/`, `requests/`, `flask/`; the pinned URLs and SHAs; these concrete setup commands; the evaluator invocation; the five-run default; output paths; and the limits of sampled precision/recall and timing comparisons.

```bash
BASELINE_CHECKOUTS=/tmp/ai-repo-doctor-checkouts
mkdir -p "$BASELINE_CHECKOUTS"
git clone https://github.com/pallets/click.git "$BASELINE_CHECKOUTS/click"
git -C "$BASELINE_CHECKOUTS/click" checkout --detach 06b2a678741131fd577ce170e23e5ca0aeba0309
git clone https://github.com/psf/requests.git "$BASELINE_CHECKOUTS/requests"
git -C "$BASELINE_CHECKOUTS/requests" checkout --detach 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
git clone https://github.com/pallets/flask.git "$BASELINE_CHECKOUTS/flask"
git -C "$BASELINE_CHECKOUTS/flask" checkout --detach d73fa1cdcbd8b1465c151db8924ba58b1dd14e35
```

```bash
python3 tools/evaluate_baseline.py \
  --repos-root /path/to/pinned-checkouts \
  --runs 5 \
  --json-out evaluation/results/v2-baseline.json \
  --markdown-out evaluation/results/v2-baseline.md
```

- [x] **Step 5: Run contract tests, inspect every probe against source, and commit data/docs**

Run: `python3 -m unittest tests.test_evaluation.ManifestTests -v`

Expected: all pinned metadata, category counts, and unique selectors pass. Manually re-open every annotated source range and verify the rationale describes that exact relationship; the actual run in Task 6 rechecks every evidence hash against the corresponding checkout.

```bash
git add evaluation/baseline-v1.json evaluation/README.md tests/test_evaluation.py
git commit -m "Add pinned baseline evaluation probes"
```

### Task 6: Generate and verify the first baseline report

**Files:**

- Create: `evaluation/results/v2-baseline.json`
- Create: `evaluation/results/v2-baseline.md`
- Test: full `tests/` suite and the real evaluator invocation

**Interfaces:**

- Checkout layout under `--repos-root`: `click/`, `requests/`, `flask/`.
- Output paths are the two checked-in `evaluation/results/` files.
- Initial report contains exactly 5 durations and 5 identical scan summary hashes per repository; every category has either sampled metrics or an explicit `not_sampled` marker.

- [x] **Step 1: Confirm all target checkouts match the pins and are clean**

Run `git -C <repo> rev-parse HEAD` and `git -C <repo> status --porcelain --untracked-files=all` for each checkout. Expected SHAs are Click `06b2a678741131fd577ce170e23e5ca0aeba0309`, Requests `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`, and Flask `d73fa1cdcbd8b1465c151db8924ba58b1dd14e35`; each status output is empty.

- [x] **Step 2: Run the complete standard-library unit suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: all existing Repo Doctor tests and evaluation unit tests pass without network access or external package installation.

- [x] **Step 3: Run the actual five-scan-per-repository baseline**

Run the README command from the Repo Doctor checkout using the three clean snapshots. Expected: exit 0, one JSON report and one Markdown report, 15 total scan durations, five equal hashes per repository, and no target checkout changes.

- [x] **Step 4: Review the report against every annotation**

For each repository and relation type, compare JSON TP/FP/FN with the corresponding probe details. Confirm unresolved-call totals and unannotated edges appear only as context, null metrics appear where denominators are zero, and every Markdown mismatch ID has a matching JSON probe record.

- [x] **Step 5: Commit the generated baseline artifacts**

```bash
git add evaluation/results/v2-baseline.json evaluation/results/v2-baseline.md
git commit -m "Record reproducible V2 baseline evaluation"
```

## Plan Self-Review

- **Spec coverage:** fixed repos/SHAs and clean-tree checks are Tasks 3, 5, and 6; evidence fingerprints and probe contracts are Tasks 1 and 5; sampled metrics and all relation categories are Task 2; determinism and five-run timing are Task 3; JSON/Markdown output and no-partial-report behavior are Task 4; no-network reproduction docs and real snapshot run are Tasks 5 and 6; unit and integration validation are Tasks 1–6.
- **Scope:** this is one offline evaluation subsystem with separable, testable contracts; it does not change analyzer behavior or runtime dependencies.
- **Placeholder scan:** no task relies on deferred design decisions or unspecified follow-up work.
- **Type consistency:** relation projection returns expected/predicted sets per metric family; report aggregation consumes those sets; CLI orchestration validates inputs before scans and passes complete results to report rendering.
