# AI Repo Doctor V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a usable Python CLI that indexes a repository, retrieves graph-guided context, estimates impact, and rejects ungrounded AI findings.

**Architecture:** A read-only scanner feeds an AST extractor; a separate graph builder resolves only local, unambiguous edges. Context, impact, and evidence validation consume the same in-memory index. The CLI rebuilds it from the current working tree for each command.

**Tech Stack:** Python 3.11+, standard library, `unittest`, Git for ignore-aware file listing, setuptools for packaging.

**Spec:** `docs/superpowers/specs/2026-09-24-repo-doctor-v1-design.md`

## Global Constraints

- Runtime is standard library only; no API key or network request.
- Source files are never executed by the scanner.
- Paths in output are repository relative; line numbers are 1-based.
- Unresolved static relations remain unresolved rather than guessed.
- Findings must cite actual scanned files and exact source text.

---

### Task 1: Git-aware file discovery

**Files:** Create `repo_doctor/scanner.py`, `repo_doctor/__init__.py`, `tests/test_scanner.py`, `.gitignore`.

**Interfaces:** Produce `discover_python_files(root: Path) -> tuple[list[str], str]`, returning sorted relative POSIX paths and scan mode `git` or `walk`.

- [x] Write tests using temporary Git and non-Git directories. A tracked Python file, untracked Python file, ignored Python file, generated-directory file, and symlink must exercise the actual scanner; assert the expected literal relative paths.
- [x] Run `python3 -m unittest tests.test_scanner -v` and verify missing behavior fails.
- [x] Implement the scanner with `git ls-files -co --exclude-standard -z` and a safe `os.walk` fallback; do not follow symlinks.
- [x] Run the focused test until green, then the whole suite.

### Task 2: AST extraction and index model

**Files:** Create `repo_doctor/model.py`, `repo_doctor/parser.py`, `repo_doctor/index.py`, `tests/test_parser.py`.

**Interfaces:** `build_index(root: Path) -> RepoIndex`; index exposes `files`, `symbols`, `imports`, `call_sites`, `parse_errors`, and stats. Symbol IDs have shape `file.py::Class.method`.

- [x] Write a failing test with class, async method, nested function, decorators, import aliases, calls, and a syntax-error file; assert exact names and line spans.
- [x] Run `python3 -m unittest tests.test_parser -v`; confirm it fails for absent extractor.
- [x] Implement dataclasses and AST traversal using `tokenize.open`, `ast.parse`, and explicit nesting; preserve parse errors without stopping the scan.
- [x] Run focused and full tests.

### Task 3: Conservative local graph resolution

**Files:** Create `repo_doctor/graph.py`, `tests/test_graph.py`; modify `repo_doctor/index.py`.

**Interfaces:** `RepoIndex.import_edges` carries source/target files plus evidence line; `RepoIndex.call_edges` carries source/target symbol IDs plus call line; `RepoIndex.import_cycles` lists deterministic cycles.

- [x] Write failing tests for `from .helpers import save`, `import pkg.helpers as h`, `self.method()`, a `src/pkg` layout, an ambiguous or shadowed name, and a two-module import cycle.
- [x] Run `python3 -m unittest tests.test_graph -v` and verify missing edges/cycle detection fail.
- [x] Implement module lookup, unique import/call resolution, local shadow exclusion, and deterministic cycle detection. Keep unresolved calls out of the edge set.
- [x] Run focused and full tests.

### Task 4: Bounded context and impact

**Files:** Create `repo_doctor/context.py`, `tests/test_context.py`.

**Interfaces:** `build_context(index, symbol_id, max_lines) -> dict`; `build_impact(index, symbol_id, depth) -> dict`.

- [x] Write failing tests that check target-first numbered snippets, direct caller/callee inclusion, test relation, truncation, unknown-symbol error, and transitive impact depth.
- [x] Run `python3 -m unittest tests.test_context -v` and observe expected failures.
- [x] Implement ordered one-hop retrieval, line-budget clipping, and reverse-edge traversal. Label every relationship in output.
- [x] Run focused and full tests.

### Task 5: Finding evidence gate

**Files:** Create `repo_doctor/evidence.py`, `tests/test_evidence.py`.

**Interfaces:** `validate_findings(index, payload: object) -> dict` with accepted and rejected entries plus reasons.

- [x] Write failing tests for one valid finding and separate false file, traversal path, out-of-range line, wrong quote, unknown symbol, and malformed confidence cases.
- [x] Run `python3 -m unittest tests.test_evidence -v` and verify failure.
- [x] Implement strict structural checks and exact quote verification against current source; return explicit rejection reasons.
- [x] Run focused and full tests.

### Task 6: Usable CLI and documentation

**Files:** Create `repo_doctor/cli.py`, `repo_doctor/__main__.py`, `tests/test_cli.py`, `pyproject.toml`, `README.md`.

**Interfaces:** `python3 -m repo_doctor` and installed `repo-doctor` provide `scan`, `context`, `impact`, `validate` with text and JSON modes.

- [x] Write CLI integration tests invoking the module against a temporary repository; assert JSON schema, text context, invalid argument exit code, and validation rejection exit code.
- [x] Run `python3 -m unittest tests.test_cli -v` and confirm expected failure.
- [x] Implement argparse dispatch, JSON serialization, concise text views, packaging, and README quick start with the manual ChatGPT workflow and limitations.
- [x] Run all tests, install in a disposable environment if available, and scan this repository as a smoke test.

## Final review

- [x] Check the spec requirements against shipped CLI behavior and tests.
- [x] Run `python3 -m unittest discover -s tests -v`, `python3 -m compileall -q repo_doctor`, command help, and representative `scan/context/validate` smoke checks.
- [x] Inspect `git diff --check` and the full change list; report remaining static-analysis limits honestly.

## Evaluation follow-up: local instance method calls

- [x] Run the CLI on a shallow clone of `psf/requests` and inspect `Session.request` relationships against source.
- [x] Add conservative resolution for local method calls when one unconditional simple assignment precedes the call, or a correctly typed context manager's `__enter__` / `__aenter__` has a directly proven `return self`, accepts the protocol call without extra required arguments, and its matching exit method exists.
- [x] Keep ambiguous, shadowed, conditionally assigned, `with`-body-assigned, nonlocal-rebound, or reassigned instance bindings unresolved; add regression coverage for each case.
- [x] Re-run the Requests scan and confirm the `requests.api.request -> Session.request` edge and its public API callers are present.
