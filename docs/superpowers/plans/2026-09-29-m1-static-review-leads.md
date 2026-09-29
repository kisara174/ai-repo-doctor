# M1 Static Review Leads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The repository AGENTS.md policy keeps design and review with the primary agent; no Luna task here needs delegation.

**Goal:** Make a newly created case show a deterministic, evidence-linked order of concrete places to inspect, without presenting call popularity or graph gaps as proven bugs.

**Architecture:** Add one pure `build_review_leads(index, static_issues)` pass. It reuses the existing parse-error and import-cycle issues, then identifies at most five production function/method symbols with at least three distinct production callers from at least two other files, connected by resolved direct call edges. Persist its output under the existing case `scan` object and render it before the issue details; old schema-v1 cases without this optional field still render.

**Tech Stack:** Python standard library, `unittest`, the existing `RepoIndex`, `case.json` v1, and Markdown report renderer.

**Spec:** `docs/PRODUCT_GUIDE.md`, M1 item “增加可确定性解释的静态分析项与优先级规则”.

## Global Constraints

- Static observations must never be labeled verified behavior defects. Keep issue IDs, source and human status, and schema version 1 compatible.
- No target repository code execution, network call, new dependency, API key exposure, or change to DeepSeek requests.
- Priority means order of investigation: parse failures first because they block coverage, import cycles second for explicit import review, shared call targets third for change-impact exploration. It is not severity or bug probability.
- Every shared target must have at least three **distinct** direct, resolved, non-test callers from at least two other files. Count each caller once, use its earliest matching call line as evidence, sort ties by symbol ID, show at most ten source edges per target and no more than five targets. Do not count same-file, test-origin, or ambiguous symbols.

---

### Task 1: Build deterministic leads from the existing index

**Files:**
- Create: `repo_doctor/leads.py`
- Modify: `repo_doctor/case.py`
- Test: `tests/test_product_case.py`

**Interfaces:**
- Consumes: `RepoIndex`, the list returned by `_static_issues(index)`.
- Produces: `build_review_leads(index: RepoIndex, static_issues: list[dict]) -> list[dict]`, stored as optional `case["scan"]["review_leads"]`.

- [x] **Step 1: Write the failing test.** Add a `test_review_leads_have_stable_order_and_source_edges` in `tests/test_product_case.py`. Create `broken.py` with `def broken(:`, an `a.py`/`b.py` import cycle, `core.py` with `shared` and a same-file caller, and three production caller functions in separate files that invoke `shared`; add a test-file caller that also invokes it. Assert the lead kinds are `parse_error`, `import_cycle`, `shared_call_target`; the shared lead names `core.py::shared`, counts exactly the three cross-file callers, references each production caller's call line and no test file. Create the same index twice and assert equivalent lead content. Add a second case with three callers in only one other file and assert no shared target lead.
- [x] **Step 2: Verify red.** Run `python3 -m unittest tests.test_product_case.ProductCaseTests.test_review_leads_have_stable_order_and_source_edges -v`; expect failure because `review_leads` is absent.
- [x] **Step 3: Implement `build_review_leads`.** Convert existing static issues to order-1/order-2 leads with their stable issue ID and source evidence. Build a `callee -> caller -> earliest line` map from `index.call_edges`, excluding test files, ambiguous symbols, and non-function/method targets. Emit sorted, capped order-3 shared-target leads with `subject`, `caller_count`, `evidence`, `reason`, and `next_step`. Keep this module free of file I/O.
- [x] **Step 4: Persist and validate.** In `create_case`, compute `static_issues` once, store them under `issues`, and store leads under `scan`. In `load_case`, accept missing `review_leads` for old v1 cases and reject it when present with a non-list value.
- [x] **Step 5: Verify green.** Run the focused test and `python3 -m unittest tests.test_product_case -v`; expect both exit 0.
- [x] **Step 6: Commit.** Commit only `repo_doctor/leads.py`, `repo_doctor/case.py`, and `tests/test_product_case.py` with message `feat: add deterministic static review leads`.

### Task 2: Render user actions and prove installed behavior

**Files:**
- Modify: `repo_doctor/report.py`
- Modify: `README.md`
- Modify: `docs/execution-status.md`
- Modify: `docs/PRODUCT_GUIDE.md`
- Test: `tests/test_product_case.py`

**Interfaces:**
- Consumes: optional `case["scan"]["review_leads"]` from Task 1.
- Produces: a “建议先检查” report section containing the ordered lead, exact file/line or copyable symbol ID, and the reason and next step. Existing issue rendering remains intact.

- [x] **Step 1: Extend the focused test to require report entries.** Assert that the rendered report shows the order-1 parse location, order-2 import edge location, order-3 `core.py::shared` and all three call evidence locations, plus the sentence that review order is not bug severity. Confirm an old schema-v1 case with the optional field removed still reopens and renders.
- [x] **Step 2: Verify red.** Run `python3 -m unittest tests.test_product_case.ProductCaseTests.test_review_leads_have_stable_order_and_source_edges -v`; expect the new report assertions to fail.
- [x] **Step 3: Render leads.** Add a report section after repository overview. Escape untrusted strings through existing `_inline` and `_code` helpers. Show issue ID for parse/cycle leads, symbol ID and distinct caller count for shared targets, and exact source-edge file/line evidence. Explain the three review-order rules and that a shared target is an impact entry, not a bug.
- [x] **Step 4: Update user documentation.** Explain the new report section in `README.md` and mark the M1 static-priority item complete in `docs/PRODUCT_GUIDE.md` only after the installed CLI smoke succeeds. Record the branch status in `docs/execution-status.md`.
- [x] **Step 5: Verify.** Run `python3 -m unittest tests.test_product_case -v`, then `python3 -m unittest discover -s tests -q`, `python3 -m compileall -q repo_doctor tests`, and `git diff --check`. Build the wheel and install it into a clean temporary virtual environment; run its `repo-doctor report create` and `report show` on a small local fixture, checking that the report includes the new section and no target code runs.
- [x] **Step 6: Commit.** Commit the report, docs, and test changes with message `feat: surface ranked static review entries`.

## Self-review

The plan covers the M1 static-priority requirement with source-backed review entries and a concrete CLI report. It deliberately leaves the separate M1 architecture summary and the invalid M1 model-quality gate open. The output contract and names are consistent across both tasks; no placeholder implementation step remains.

## Execution record

Completed in `codex/m1-quality-gate` on 2026-09-29. The final focused module passed 6 tests; the full offline suite passed 372. The branch wheel built and installed in a clean Python 3.14 environment outside the source tree, and its CLI created and reopened a report for the 56-file project. The next M1 architecture summary and the incomplete diagnosis-quality gate remain separate work.
