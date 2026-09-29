# M1 Architecture and Impact Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The repository AGENTS.md policy keeps requirement interpretation, design, and review with the primary agent.

**Goal:** Make a case report explain which local Python modules have many known dependents and show exact source edges for a selected symbol's direct and indirect impact.

**Architecture:** A pure architecture pass summarizes resolved production-to-production local import and cross-file call edges, ranks up to five modules by the number of distinct dependent files, and persists the supporting file/line evidence in `scan.architecture`. The existing reverse-impact traversal gains the earliest resolved call edge for each hop, then the report renders those edges alongside the existing impact path. Both additions are optional when reopening older schema-v1 cases.

**Tech Stack:** Python 3.11+ standard library, existing `RepoIndex`, case schema v1, Markdown renderer, and `unittest`.

**Spec:** `docs/PRODUCT_GUIDE.md`, M1 architecture/change-impact item.

## Global Constraints

- A “focus module” is a navigation hint, not a quality, centrality, risk, or defect score. Count only distinct other non-test Python files with a statically resolved local import or call edge into the module. Require at least two dependents; sort by descending count then path; show at most five modules and ten evidence edges per module.
- Preserve existing `build_impact` keys and case-v1 loading. Append `call_path_evidence` to each affected symbol without changing its `symbol`, `distance`, or `path` semantics. Choose the earliest source line for duplicate caller/callee edges.
- Do not execute target repository code, connect to a model, install target dependencies, or infer dynamic imports/runtime dispatch. Escape file and symbol text in Markdown.

---

### Task 1: Source-backed module summary

**Files:**
- Create: `repo_doctor/architecture.py`
- Modify: `repo_doctor/case.py`
- Test: `tests/test_product_case.py`

**Interfaces:**
- Consumes: `RepoIndex.files`, `.import_edges`, `.call_edges`, and `.symbols`.
- Produces: `build_architecture_summary(index: RepoIndex) -> dict`, stored at `case["scan"]["architecture"]`, with `production_modules`, `local_import_edges`, `cross_file_call_edges`, and `focus_modules`. Each focus module has `file`, `dependent_file_count`, `importer_count`, `caller_file_count`, `evidence`, and `evidence_omitted`.

- [x] **Step 1: Write red test.** Create a repository with `core.py::save`, `service_one.py` and `service_two.py` that both import and call `save`, `api.py` that calls `service_one`, and a `test_core.py` import/call control. In `tests/test_product_case.py`, create a case and assert `core.py` has exactly two production dependents; evidence includes `service_one.py:1` (import) and `service_one.py:4` (call) plus the second service, excludes the test file, and is identical after a fresh index/recreate. Assert no focus module appears for a one-dependent repository.
- [x] **Step 2: Verify red.** Run `python3 -m unittest tests.test_product_case.ProductCaseTests.test_architecture_summary_uses_resolved_production_edges -v`; expect missing `architecture`.
- [x] **Step 3: Implement pure pass.** Use the production file set from `FileRecord.is_test`. For each eligible import edge, add its source to the target module's dependent set and save `{"kind":"import","file":source,"line":line,"target":target}`. For each eligible cross-file call edge, use caller/callee symbol files and save `{"kind":"call","file":caller.file,"line":edge.line,"caller":edge.caller,"callee":edge.callee}`. Rank and cap as specified; sort evidence by file, line, kind, and target/callee so the output is stable.
- [x] **Step 4: Persist and load.** Add the result to `create_case` without changing schema version. `load_case` accepts an absent `architecture` for old cases and rejects a present non-dict value.
- [x] **Step 5: Verify green and commit.** Run the focused test and `python3 -m unittest tests.test_product_case -q`, inspect the diff, then commit only `repo_doctor/architecture.py`, `repo_doctor/case.py`, and the test with `feat: summarize resolved module dependencies`.

### Task 2: Cite each impact hop and render the user report

**Files:**
- Modify: `repo_doctor/context.py`
- Modify: `repo_doctor/cli.py`
- Modify: `repo_doctor/report.py`
- Modify: `README.md`
- Modify: `docs/PRODUCT_GUIDE.md`
- Modify: `docs/execution-status.md`
- Test: `tests/test_context.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_product_case.py`

**Interfaces:**
- Consumes: the Task 1 architecture dict and existing `build_impact(index, symbol_id, depth=2)` output.
- Produces: each affected item gains `call_path_evidence`, an array ordered from target outward, with `caller`, `callee`, `file`, `line`, and `via_reexports`. The report shows direct/indirect groups and line-backed hops, plus the architecture section. Old cases without architecture or path evidence still render.

- [x] **Step 1: Write red impact test.** Extend `test_impact_follows_reverse_calls_to_requested_depth` in `tests/test_context.py`: `service.py::process` has one hop from `service.py:4` to `helpers.py::save`; `api.py::route` has two ordered hops, `service.py:4` then `api.py:4`. Add a second call from the same caller to the same callee on a later line and assert the earliest line wins.
- [x] **Step 2: Verify red.** Run `python3 -m unittest tests.test_context.ContextTests.test_impact_follows_reverse_calls_to_requested_depth -v`; expect missing `call_path_evidence`.
- [x] **Step 3: Implement hop evidence.** Build a `(caller,callee) -> earliest CallEdge` map before traversal. When constructing each affected item from `caller_path`, add evidence for each adjacent pair from target outward, including re-export hops as dictionaries. Preserve existing sort order and source keys. Make `_print_impact` display each edge's file and line under the affected symbol.
- [x] **Step 4: Write red report test.** In the architecture case test, call `set_target` with `core.py::save`, save, and assert the report has “静态架构摘要”, the two supporting import/call lines, “直接影响”, “间接影响”, and `service_one.py:4` plus the `api.py` hop. Delete the optional architecture field from another saved v1 case and assert `load_case` and `render_report` still work. The installed CLI smoke must also run `report show`.
- [x] **Step 5: Render and document.** Add architecture before the review-entry section, state the resolved-edge boundary, and include exact evidence lines. Split selected-symbol impact by `distance == 1` and `distance > 1`; display each hop's file/line and target/caller ID, and show existing module import evidence. Update README and mark the M1 architecture item in `docs/PRODUCT_GUIDE.md` only after installed CLI verification.
- [x] **Step 6: Verify and commit.** Run focused tests, full `python3 -m unittest discover -s tests -q`, `python3 -m compileall -q repo_doctor tests`, and `git diff --check`. Build a wheel with standard isolated build; if PyPI is unavailable, use a preinstalled Python runtime with setuptools at least 77, `pip wheel --no-index --no-deps --no-build-isolation`, and record that fallback. Install the wheel in a clean temporary venv; from outside the source tree, create/reopen a report with `--symbol` on the project and confirm that the saved and rendered reports match. Commit Task 2 files, docs, and this plan with `feat: cite architecture and impact edges in reports`.

## Self-review

The plan covers the third M1 product item without changing AI requests or the existing issue workflow. It does not claim an M1 model-quality pass; a new evaluation under the revised transport remains separate. The optional schema fields preserve old cases, and the test fixtures check that displayed edges originate in production source lines.

## Execution record

Completed on `codex/m1-architecture` on 2026-09-29. Focused product, context, and CLI tests passed; the full offline suite passed 373 tests, with `compileall` and diff checks clean. Ordinary isolated build failed twice while downloading setuptools because PyPI TLS connections ended unexpectedly. The bundled Python 3.12 runtime supplied setuptools 84 for an offline, non-isolated wheel build; that wheel installed in a clean Python 3.14 venv. Installed `report create --symbol` and `report show` produced byte-identical reports from outside the source tree, with 30 production modules and 6 direct plus 17 indirect source-backed impact paths.
