# AI Repo Doctor V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the static Python repository index to resolve explicit re-exports, distinguish overload declarations from their implementation, and expose bounded Click command-registration relationships.

**Architecture:** Keep ordinary call/import edges separate from typed semantic relationships. The parser records decorator and overload syntax; index construction canonicalizes overload groups; graph resolution follows only explicit, unique local re-export bindings; a Click semantic pass recognizes statically proven group registrations; CLI context and impact expose those relationships without treating them as runtime calls.

**Tech Stack:** Python 3.11+, standard library only, `unittest`, AST parsing, Git-backed test fixtures.

**Spec:** `docs/superpowers/specs/2026-09-24-repo-doctor-v2-design.md`

## Global Constraints

- Runtime requires Python 3.11+ and uses only the standard library.
- The scanner remains read-only: it does not execute or import target code.
- The Repo Doctor runtime does not access the network or send source code anywhere.
- Unresolved or ambiguous static relationships stay unresolved; do not guess.
- `call_edges` continue to mean source-level calls; semantic relationships remain separately typed.
- JSON output uses `schema_version: 2`; existing V1 field names and meanings remain unchanged.
- Click-specific semantic edges are limited to statically confirmed `click.group`, `click.command`, `.command(...)`, and `.group(...)` registration forms.
- General dynamic dispatch, reflection, arbitrary decorators, plugins, dynamic `__getattr__`, wildcard expansion, and target-code execution remain out of scope.
- The primary agent owns architecture, task packets, debugging choices, diff review, and acceptance. Delegate only bounded tasks that meet the repository's Luna/DeepSeek routing policy; never run more than one Luna executor at once.
- Before a delegated task, read fresh weekly Codex usage. At strictly less than 10% remaining, use DeepSeek Harness only if the task is eligible under its policy; otherwise use Luna for Luna-eligible work. At 10% or above, or when weekly usage is unavailable, use Luna only if eligible; keep all other work with the primary agent.
- A Luna task packet lists Objective, Allowed changes, Forbidden changes, Exact steps, Validation, Expected result, and Stop conditions. The primary agent independently reviews the diff and reruns validation before accepting it.

---

## Files and Responsibilities

- Modify `repo_doctor/model.py`: immutable records for decorators, overload signatures, re-export hops, and semantic edges; V2 fields on symbols, imports, call edges, and index.
- Modify `repo_doctor/parser.py`: capture decorator syntax and mark only direct, unconditional module imports as eligible static bindings.
- Modify `repo_doctor/index.py`: collect same-ID definitions before deciding whether they form a valid overload group or remain ambiguous.
- Modify `repo_doctor/graph.py`: resolve explicit local re-export chains and attach their evidence to canonical call edges.
- Create `repo_doctor/semantics.py`: recognize bounded Click decorator identities and group-to-callback registration edges.
- Modify `repo_doctor/context.py`: show registration neighbors and separately labeled semantic impact results while retaining the source-line budget.
- Modify `repo_doctor/cli.py`: serialize V2 metadata/edges and update text views and every JSON schema version.
- Modify `README.md`: describe V2 relationships, JSON schema change, and static-analysis limits.
- Modify `tests/test_parser.py`, `tests/test_graph.py`, `tests/test_context.py`, and `tests/test_cli.py`; create `tests/test_semantics.py` for Click adapter fixtures.

### Task 1: Preserve decorator syntax and import scope

**Files:**

- Modify: `repo_doctor/model.py`
- Modify: `repo_doctor/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**

- Add frozen `DecoratorRef(expression: str, line: int, recognized: str | None = None)`.
- Add frozen `OverloadSignature(start_line: int, end_line: int, signature: str)`.
- Add `Symbol.decorators: tuple[DecoratorRef, ...]`, `Symbol.is_overload: bool`, `Symbol.overload_signature: OverloadSignature | None`, and `Symbol.overloads: tuple[OverloadSignature, ...]` with defaults that preserve existing constructors. A parsed overload definition has `overload_signature`; the canonical implementation has the grouped `overloads` tuple.
- Add `ImportRef.is_unconditional_module_level: bool = False`; it is true only for an `Import` or `ImportFrom` node directly in `ast.Module.body`.
- `parse_python_file(root, relative_path, ...)` continues returning `ParsedFile`; each function/method now carries decorators in source order and line positions.
- `_overload_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> OverloadSignature` formats the signature as `def NAME(ARGUMENTS)` or `async def NAME(ARGUMENTS)`, followed by ` -> RETURN` when an annotation exists; its line range is the decorator-inclusive definition range.

- [ ] **Step 1: Add a parser test for decorators, recognized overload aliases, and conditional imports**

```python
source = """import typing as t
from typing_extensions import overload as ov
if TYPE_CHECKING:
    from click import group as conditional_group

@t.overload
def fetch(key: int) -> int: ...

@ov
def fetch(key: str) -> str: ...

@custom
def fetch(key):
    return key
"""
```

Assert the first two `fetch` records have `is_overload is True`, the implementation has `is_overload is False`, decorator lines are 6, 9, and 12, and the conditional import has `is_unconditional_module_level is False`. Assert the custom decorator is preserved with `recognized is None`.

- [ ] **Step 2: Run the focused test and confirm the new assertions fail**

Run: `python3 -m unittest tests.test_parser.ParserTests.test_records_decorators_and_overload_aliases -v`

Expected: FAIL because current `Symbol` and `ImportRef` do not expose the new metadata.

- [ ] **Step 3: Add the model records and parser extraction**

Use `ast.unparse()` only to preserve a deterministic decorator/signature expression; never evaluate it. Build the set of direct module-body import node identities from `tree.body`, and set `is_unconditional_module_level` from membership in that set. Resolve overload decorator aliases only from direct imports of `typing` or `typing_extensions`; treat a name as shadowed if the module also binds or defines that name. Store `_overload_signature(node)` on each recognized overload declaration so index construction can preserve it without re-reading source.

```python
@dataclass(frozen=True, slots=True)
class DecoratorRef:
    expression: str
    line: int
    recognized: str | None = None
```

- [ ] **Step 4: Run parser tests and full current suite**

Run: `python3 -m unittest tests.test_parser -v`

Run: `python3 -m unittest discover -s tests -v`

Expected: all parser tests and all V1 tests pass; pre-existing duplicate-definition behavior is unchanged in this task.

- [ ] **Step 5: Commit the parser metadata slice**

```bash
git add repo_doctor/model.py repo_doctor/parser.py tests/test_parser.py
git commit -m "Record decorator and overload syntax"
```

### Task 2: Canonicalize overload declarations

**Files:**

- Modify: `repo_doctor/index.py`
- Modify: `repo_doctor/model.py` if the final overload signature record needs a field adjustment
- Test: `tests/test_graph.py`

**Interfaces:**

- `build_index(root: Path) -> RepoIndex` remains unchanged.
- `RepoIndex.symbols[id]` holds the unique concrete implementation when and only when the same-ID group contains exactly one non-overload definition and one or more recognized overload declarations.
- The implementation's `Symbol.overloads` holds source-ordered `OverloadSignature` records; overload declarations are not separate executable symbols.
- Multiple concrete definitions and overload-only groups stay in `RepoIndex.ambiguous_symbols`. If a repeated same-ID group contains an unrecognized decorator definition, it is treated as concrete and therefore remains ambiguous rather than being selected as an overload.

- [ ] **Step 1: Add tests for one implementation, overload-only, and multiple implementations**

```python
source = """from typing import overload
@overload
def parse(value: int) -> int: ...
@overload
def parse(value: str) -> str: ...
def parse(value):
    return value
def run():
    return parse(1)
"""
```

Assert `app.py::parse` is not ambiguous, the canonical symbol has two overload signatures, and the `run` call resolves to that implementation. Add a second fixture with overload declarations and no implementation, and retain the existing duplicate concrete-definition fixture; both must remain ambiguous.

- [ ] **Step 2: Run the focused overload tests and confirm failure**

Run: `python3 -m unittest tests.test_graph.GraphTests.test_overload_declarations_resolve_to_single_implementation -v`

Expected: FAIL because `build_index` currently marks the repeated qualified name ambiguous before examining decorators.

- [ ] **Step 3: Group parsed definitions before inserting symbols**

Collect parsed symbol candidates by ID, then apply the overload rule before the existing ambiguous-parent cleanup. Preserve the current ambiguity behavior for every group that does not match exactly one concrete implementation plus one or more recognized overloads.

```python
concrete = [symbol for symbol in candidates if not symbol.is_overload]
overloads = [symbol for symbol in candidates if symbol.is_overload]
if len(concrete) == 1 and overloads and all(item.overload_signature for item in overloads):
    canonical = replace(concrete[0], overloads=tuple(item.overload_signature for item in overloads))
```

- [ ] **Step 4: Run graph tests and the complete suite**

Run: `python3 -m unittest tests.test_graph -v`

Run: `python3 -m unittest discover -s tests -v`

Expected: overload implementation calls resolve; overload-only and multiple concrete definitions remain ambiguous; all V1 graph behavior passes.

- [ ] **Step 5: Commit overload grouping**

```bash
git add repo_doctor/index.py repo_doctor/model.py tests/test_graph.py
git commit -m "Resolve overload groups to concrete implementations"
```

### Task 3: Resolve explicit re-export chains

**Files:**

- Modify: `repo_doctor/model.py`
- Modify: `repo_doctor/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**

- Add frozen `ExportHop(file: str, name: str, line: int)` and `SemanticEdge(kind: str, target_symbol: str, evidence_file: str, line: int, source_symbol: str | None = None, source_file: str | None = None, exported_name: str | None = None)` records. A re-export uses `source_file` and `exported_name`; a registration uses `source_symbol` and `target_symbol`.
- Add `CallEdge.via_reexports: tuple[ExportHop, ...] = ()` and `RepoIndex.semantic_edges: list[SemanticEdge]`.
- `resolve_graph(index: RepoIndex) -> None` preserves V1 ordinary import/call resolution rules. Only the new re-export table uses unique, unconditional, module-level local import bindings; a call resolved through that table targets the canonical implementation and carries the ordered evidence chain.
- `_resolve_export(index: RepoIndex, file: str, name: str, active: set[tuple[str, str]]) -> tuple[str, tuple[ExportHop, ...]] | None` resolves one public module binding to a canonical symbol and ordered hop evidence; `_resolve_export` returns `None` for cycles or multiple targets.
- Each recognized re-export creates a `kind == "reexport"` semantic edge. A cycle, conflicting target, conditional import, wildcard import, dynamic export, or external target creates no resolved export edge.

- [ ] **Step 1: Add a fixture covering a two-hop package re-export and both call forms**

Create `pkg/__init__.py` with `from .api import public as public`, `pkg/api.py` with `from .impl import internal as public`, and `pkg/impl.py` with `def internal(): return 1`. In `caller.py`, test both `import pkg as p; p.public()` and `from pkg import public; public()`.

Assert both calls target `pkg/impl.py::internal`, each has the correct ordered `via_reexports`, and the index contains two `reexport` edges with exact source lines.

- [ ] **Step 2: Run the new re-export test and confirm it fails**

Run: `python3 -m unittest tests.test_graph.GraphTests.test_resolves_calls_through_explicit_reexport_chain -v`

Expected: FAIL because attribute lookup currently stops at the package `__init__.py` symbol table.

- [ ] **Step 3: Build a cycle-safe export table and resolve calls through it**

Resolve each explicit module-level `ImportFrom` binding against a direct local symbol, a unique local submodule, or another export-table entry. Use a visited `(module_file, exported_name)` set per traversal; encountering a repeated pair returns unresolved. Do not expand `*` imports or inspect assignments as aliases.

```python
def _resolve_export(index, file: str, name: str, active: set[tuple[str, str]]):
    key = (file, name)
    if key in active:
        return None
    active.add(key)
    try:
        return resolve_direct_symbol_or_explicit_import(index, file, name, active)
    finally:
        active.remove(key)
```

`resolve_direct_symbol_or_explicit_import(index, file, name, active)` is a private helper in `repo_doctor/graph.py` with signature `tuple[str, tuple[ExportHop, ...]] | None`; it gathers direct-symbol, submodule, and supported import-binding candidates, returning a result only when exactly one binding candidate remains. A direct symbol that conflicts with an explicit import is unresolved. The helper never imports the target module.

- [ ] **Step 4: Add negative tests for cycles, conflicts, and unsupported forms**

Assert that a two-module re-export cycle, two imports binding the same public name to different targets, a conditional import, `from module import *`, and a package exposing a name only through `__getattr__` produce no call edge to a guessed target. Re-run the existing local import, alias, and cycle tests.

- [ ] **Step 5: Run focused and full graph suites**

Run: `python3 -m unittest tests.test_graph -v`

Run: `python3 -m unittest discover -s tests -v`

Expected: all positive chains resolve to one canonical symbol; every negative fixture remains unresolved; existing imports and calls are unchanged.

- [ ] **Step 6: Commit re-export resolution**

```bash
git add repo_doctor/model.py repo_doctor/graph.py tests/test_graph.py
git commit -m "Resolve calls through explicit local reexports"
```

### Task 4: Add bounded Click registration semantics

**Files:**

- Create: `repo_doctor/semantics.py`
- Modify: `repo_doctor/index.py`
- Test: `tests/test_semantics.py`

**Interfaces:**

- Add `resolve_semantic_edges(index: RepoIndex) -> None` in `repo_doctor/semantics.py`; call it after `resolve_graph(index)` during index construction.
- Add private helpers `_click_api_aliases(index: RepoIndex) -> dict[tuple[str, str], str]`, `_group_callbacks(index: RepoIndex, aliases: dict[tuple[str, str], str]) -> set[str]`, and `_registration_edges(index: RepoIndex, aliases: dict[tuple[str, str], str], groups: set[str]) -> list[SemanticEdge]`.
- Recognize Click decorators only from unshadowed explicit import paths `click`, `from click import group`, and `from click import command`, including their import aliases and `import click as c` module aliases.
- `@click.group()` identifies the decorated function's symbol ID as a group callback. `@group.command(...)` and `@group.group(...)` create `command_registration` semantic edges from that callback symbol to the uniquely named child callback symbol.
- A module-level assignment/rebind, ambiguous callback ID, unsupported decorator expression, or unknown decorator identity produces no registration edge.

- [ ] **Step 1: Add tests for direct imports, module aliases, and subgroups**

```python
source = """import click as c
@c.group()
def cli():
    pass
@cli.command()
def leaf():
    pass
@cli.group()
def nested():
    pass
"""
```

Assert the index contains two `command_registration` edges from `app.py::cli` to `app.py::leaf` and `app.py::nested`, with evidence lines equal to the two decorator lines. Add a separate fixture using `from click import group as make_group` and `from click import command as make_command`; assert the group alias is recognized and a standalone `@make_command()` is identified as a command decorator without creating a parent registration edge.

- [ ] **Step 2: Run the focused test and confirm there are no registration edges yet**

Run: `python3 -m unittest tests.test_semantics -v`

Expected: FAIL because no semantic pass currently exists.

- [ ] **Step 3: Implement import identity and group-registration resolution**

Use unconditional module-level import records and alias/shadow checks. For a locally scanned `click` package, require the public `group` or `command` binding to resolve uniquely; do not treat an unrelated same-name local module as Click solely because of its filename.

```python
def resolve_semantic_edges(index: RepoIndex) -> None:
    aliases = _click_api_aliases(index)
    groups = _group_callbacks(index, aliases)
    index.semantic_edges.extend(_registration_edges(index, aliases, groups))
```

- [ ] **Step 4: Add false-positive tests**

Assert no registration edge is produced for `@custom.decorator`, an unknown `@cli.command` receiver, a re-bound `cli` name, an ambiguous same-ID callback, or a conditional Click import. Assert generic decorator metadata remains available for unknown decorators.

- [ ] **Step 5: Run semantic and full test suites**

Run: `python3 -m unittest tests.test_semantics -v`

Run: `python3 -m unittest discover -s tests -v`

Expected: only known Click forms create typed registration edges; all tests pass.

- [ ] **Step 6: Commit Click relationship recognition**

```bash
git add repo_doctor/semantics.py repo_doctor/index.py tests/test_semantics.py
git commit -m "Index statically proven Click command registrations"
```

### Task 5: Expose V2 relationships in CLI, context, impact, and documentation

**Files:**

- Modify: `repo_doctor/cli.py`
- Modify: `repo_doctor/context.py`
- Modify: `repo_doctor/evidence.py`
- Modify: `README.md`
- Test: `tests/test_context.py`, `tests/test_cli.py`

**Interfaces:**

- `_scan_data(index)` returns `schema_version: 2`, existing V1 keys with their original meanings, `semantic_edges`, `symbols[].decorators`, `symbols[].overloads`, and `call_edges[].via_reexports`.
- `imports[]` retains its V1 fields and adds `is_unconditional_module_level` so users can audit which imports were eligible as export bindings.
- `build_context(index, symbol_id, max_lines=120)` returns `schema_version: 2`; it adds `registered_command` blocks for a group target and `registered_by` blocks for a registered callback, under the existing source-line budget. Its `semantic_evidence` lists relevant re-export and registration edges for the target, and call evidence includes `via_reexports`.
- `build_impact(index, symbol_id, depth=2)` returns `schema_version: 2`; existing `affected_symbols` remains call-edge-only and `module_importers` retains its V1 meaning. Add a separate `semantic_relations` list for touching re-export and registration edges, with direction and source evidence.
- `validate_findings(...)` keeps acceptance/rejection semantics and changes only the result schema marker to 2.
- `stats.resolved_calls` and `stats.unresolved_calls` continue to count only ordinary call sites/edges; semantic edges never change these counts.
- `semantic_evidence` and `semantic_relations` serialize the `SemanticEdge` fields; `direction` is `outgoing` when the requested symbol ID equals `source_symbol` and `incoming` when it equals `target_symbol` (for re-export edges the canonical implementation is `target_symbol`).

- [ ] **Step 1: Add CLI/context tests for separate semantic outputs and schema 2**

Build temporary fixtures from Task 3 and Task 4. Assert scan JSON reports version 2 and the direct re-export and `command_registration` edges; context for the canonical re-exported symbol includes re-export evidence and `via_reexports` call evidence; context for `cli` includes `leaf` with relation `registered_command`; context for `leaf` includes `cli` with relation `registered_by`; impact exposes re-export and registration results separately from `affected_symbols`. Add a low-budget context assertion proving semantic neighbor blocks obey `max_lines` and set `budget_exhausted` when omitted.

Update the existing call-edge JSON assertion to include `"via_reexports": []` for direct calls, and assert `scan`, `context`, `impact`, and `validate` JSON results all report version 2.

- [ ] **Step 2: Run the focused tests and confirm schema/relationship assertions fail**

Run: `python3 -m unittest tests.test_context tests.test_cli -v`

Expected: FAIL on version and missing semantic fields before the implementation changes.

- [ ] **Step 3: Serialize typed records and add labeled context/impact data**

Serialize dataclass records with stable field order and sorted edge order. Add semantic neighbors after ordinary call neighbors in deterministic file/line/symbol order; deduct their source lines from the same `max_lines` budget. Build `semantic_evidence` from edges touching the target and `semantic_relations` from edges touching the impact target. Compute `budget_exhausted` from truncation or omitted context candidates and `omitted_symbols` from the difference between candidates and emitted blocks. Keep registration results out of call depth and ordinary `affected_symbols`.

```python
return {
    "schema_version": 2,
    "symbol": symbol_id,
    "max_lines": max_lines,
    "blocks": blocks,
    "call_evidence": direct_edges,
    "semantic_evidence": semantic_evidence,
    "budget_exhausted": budget_exhausted,
    "omitted_symbols": omitted_symbols,
}
```

- [ ] **Step 4: Update human-readable CLI text and README**

Print `Static call edges` separately from `Semantic relationships`; label re-export and command-registration evidence, and retain the statement that static links do not prove runtime use or test coverage. Document schema 2 and the three supported V2 improvements in the README's capabilities/limits section.

- [ ] **Step 5: Run context, CLI, and all tests**

Run: `python3 -m unittest tests.test_context tests.test_cli -v`

Run: `python3 -m unittest discover -s tests -v`

Expected: schema and relation tests pass; existing evidence validation behavior and V1 field meanings remain intact.

- [ ] **Step 6: Commit V2 output and docs**

```bash
git add repo_doctor/cli.py repo_doctor/context.py repo_doctor/evidence.py README.md tests/test_context.py tests/test_cli.py
git commit -m "Expose V2 semantic relationships in CLI"
```

### Task 6: Verify the pinned Click evaluation and full V2 behavior

**Files:**

- Modify only if a failing acceptance check reveals a V2 defect: files owned by Tasks 1–5.
- No new network-dependent unit tests.

**Interfaces:** The fixed checkout at `/tmp/ai-repo-doctor-v2-click` is evaluation input only; the final report must include the checkout commit and observed relations. The Requests smoke uses `/tmp/ai-repo-doctor-v2-requests` and reports its checked-out commit.

- [ ] **Step 1: Confirm the evaluation checkout is the pinned Click commit**

Run: `git -C /tmp/ai-repo-doctor-v2-click rev-parse HEAD`

Expected: `06b2a678741131fd577ce170e23e5ca0aeba0309`.

- [ ] **Step 2: Scan Click and assert the representative relationships**

Run: `python3 -m repo_doctor scan /tmp/ai-repo-doctor-v2-click --json`

Run this assertion against that JSON output:

```bash
python3 - <<'PY'
import json
import subprocess

root = "/tmp/ai-repo-doctor-v2-click"
report = json.loads(subprocess.check_output(["python3", "-m", "repo_doctor", "scan", root, "--json"], text=True))
target = "src/click/utils.py::echo"
echo_calls = {(call["caller"], call["line"]) for call in report["calls"] if call["expression"] == "click.echo"}
echo_edges = {(edge["caller"], edge["line"]) for edge in report["call_edges"] if edge["callee"] == target}
assert report["schema_version"] == 2
assert echo_calls & echo_edges
assert any(edge["kind"] == "reexport" and edge["source_file"] == "src/click/__init__.py" and edge["target_symbol"] == target for edge in report["semantic_edges"])
for symbol in (
    "src/click/core.py::Context.invoke",
    "src/click/core.py::Group.command",
    "src/click/core.py::Group.command.decorator",
    "src/click/core.py::Group.group",
    "src/click/core.py::Group.group.decorator",
):
    assert symbol not in report["ambiguous_symbols"], symbol
PY
```

Run: `python3 -m repo_doctor context /tmp/ai-repo-doctor-v2-click examples/repo/repo.py::cli --max-lines 300 --json`

Assert the context has five `registered_command` blocks for `clone`, `delete`, `setuser`, `commit`, and `copy`, and five matching `command_registration` evidence edges with decorator lines. In `src/click/core.py`, confirm the concrete implementations of `Context.invoke`, `Group.command`, `Group.command.decorator`, `Group.group`, and `Group.group.decorator` are not marked ambiguous due only to overload declarations.

- [ ] **Step 3: Verify the known dynamic-dispatch boundary stays unresolved**

Inspect `src/click/core.py::Group.invoke` call sites. For each call record whose caller is `src/click/core.py::Group.invoke` and expression is `sub_ctx.command.invoke`, assert there is no call edge with the same caller and line. Confirm the expression remains in `calls` while absent from `call_edges`, so it contributes to the unresolved-call count.

- [ ] **Step 4: Rerun the Requests regression smoke**

Run `git clone --depth=1 https://github.com/psf/requests.git /tmp/ai-repo-doctor-v2-requests` and record the checkout revision with `git -C /tmp/ai-repo-doctor-v2-requests rev-parse HEAD`.

Run the exact edge assertion against the checkout at `/tmp/ai-repo-doctor-v2-requests`:

```bash
python3 - <<'PY'
import json
import subprocess

root = "/tmp/ai-repo-doctor-v2-requests"
report = json.loads(subprocess.check_output(["python3", "-m", "repo_doctor", "scan", root, "--json"], text=True))
assert any(
    edge["caller"].endswith("requests/api.py::request")
    and edge["callee"].endswith("requests/sessions.py::Session.request")
    for edge in report["call_edges"]
)
PY
```

This is a manual regression command, not a network-dependent unit test.

- [ ] **Step 5: Run final repository checks**

Run: `python3 -m unittest discover -s tests -v`

Run: `python3 -m compileall -q repo_doctor`

Run: `python3 -m repo_doctor --help`

Run: `git diff --check`

Run: `git diff origin/codex/repo-doctor-v2-design...HEAD --check`

Run: `git status --short --branch`

Expected: all unit tests pass, compileall and help exit 0, the committed implementation diff has no whitespace errors, and the working tree is clean. Report unresolved calls honestly; do not present their total as an accuracy score.

- [ ] **Step 6: Review the final V2 diff and commit any narrowly scoped evaluation correction**

Run: `git diff origin/codex/repo-doctor-v2-design...HEAD --stat`.

If a correction is required, add a regression test for the exact false or missing relation, rerun its focused test and the full suite, then commit the correction with a message naming that behavior. Do not expand into dynamic dispatch, arbitrary decorators, or unrelated refactoring.

- [ ] **Step 7: Push the reviewed V2 branch**

```bash
git push -u origin codex/repo-doctor-v2
```

Expected: the public remote branch points to the same final commit as local `HEAD`.

## Self-Review Checklist

- [ ] Re-export resolution has explicit positive and negative tests, including cycles and conflicts.
- [ ] Overload handling selects only one concrete implementation and preserves ambiguity otherwise.
- [ ] Click registration edges use decorator line evidence and never count as call edges.
- [ ] Context source budgets apply to semantic neighbors; impact keeps semantic relationships outside call depth.
- [ ] All command JSON outputs use schema version 2 and V1 field meanings remain stable.
- [ ] Click evaluation checks the pinned commit, five callbacks, `click.echo`, overload cases, and the unresolved dynamic-dispatch boundary.

## Spec Coverage

- Explicit re-export aliases, chains, conflicts, cycles, and unresolved cases: Tasks 3, 5, and 6.
- Overload aliases, implementation selection, retained signatures, and ambiguity: Tasks 1, 2, and 6.
- Decorator metadata, bounded Click registration, exact line evidence, and false-positive limits: Tasks 1, 4, 5, and 6.
- V2 schema, context/impact relationship labeling, text output, and documentation: Task 5.
- Read-only behavior, standard-library runtime, Requests regression, pinned Click evaluation, and unresolved dynamic dispatch: Tasks 1–6.

The scope is one plan because all three analysis improvements share `RepoIndex`, edge provenance, and the V2 JSON/context/impact contract; each capability has its own tests before the combined evaluation.
