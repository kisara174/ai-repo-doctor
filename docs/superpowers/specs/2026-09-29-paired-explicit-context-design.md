# Paired explicit-context evaluation design

Date: 2026-09-29. This experiment asks whether explicitly adding an omitted
local subclass method helps optional cloud diagnosis identify a known behavior
without creating a new false alarm on the paired repair. It tests this narrow
workflow, not general defect detection or automatic subclass discovery.

## Cohort and intervention

Use two previously unsent public Werkzeug repairs. The bug snapshot is each
fix commit's first parent. The target method is unchanged across each pair;
the repair changes the supplementary subclass method. Read upstream source and
regression tests, but do not execute target repository code or dependencies.

| Repair | Bug commit | Fixed commit | Target | Explicit extra |
| --- | --- | --- | --- | --- |
| [Skip empty content length and type](https://github.com/pallets/werkzeug/commit/625362a429263f8d713a9ed06c18f247042d7d0f) | `0c5cad57c2370c4b916b3651adb4d82eb9fbf5ec` | `625362a429263f8d713a9ed06c18f247042d7d0f` | `werkzeug/datastructures.py::Headers.__iter__` | `werkzeug/datastructures.py::EnvironHeaders.__iter__` |
| [PR #1005](https://github.com/pallets/werkzeug/pull/1005) | `3790dc177329a5214bd318be6e1dfd43d680eb64` | `57521600ce04fdf4d977c36f89fc51191aa8a3c9` | `werkzeug/datastructures.py::Headers.get` | `werkzeug/datastructures.py::EnvironHeaders.__getitem__` |

For the first repair, an empty `CONTENT_TYPE` or `CONTENT_LENGTH` in the WSGI
environment was yielded as a header. The repair skips empty special values;
its regression check distinguishes an empty value from the string `"0"`.
For PR #1005, `EnvironHeaders.get` delegates to its overridden `__getitem__`.
Passing a non-string key raised `AttributeError` at `key.upper()` instead of
returning the supplied default via `KeyError`; the repair adds a type check.
The upstream discussion records `42 in headers` as a motivating case. Treat
the repaired snapshot as negative only for this narrow contract.

An offline source-selection probe found that the default context omitted each
changed subclass method. The explicit context included the complete method
and remained below 120 selected lines and 64 KiB of selected source. A third
candidate, `HTTPException.get_headers`, was rejected because the current
default call graph already selects its changed subclass caller.

Freeze one manifest with dataset ID `diagnosis-werkzeug-explicit-context-v1`.
For each repair, include four cases in this order: bug/default, bug/explicit,
fixed/default, fixed/explicit. The default rows omit `include_symbols`; the
explicit rows contain a one-element list naming the extra above. Use distinct
pair IDs for each arm, with one bug and one fixed case in each pair. Each row
records the same pinned commit, target span and target SHA-256 as its
counterpart in the other arm, plus its own narrow ground truth and source
references. The four target fingerprints are:

| Repair | Target span | Target SHA-256 in both snapshots |
| --- | --- | --- |
| Empty special values | `werkzeug/datastructures.py:1139-1141` | `ae82648bb2996c49eb0897bd5b566d4f2cd688dc1a0b76908d9c10e38926902e` |
| Non-string key | `werkzeug/datastructures.py:979-1016` | `4f51fb2cc0526f8929cf7b0ad31d3a6a4306a99f1aa28239d61bbe62cc78ad6f` |

The model receives only the existing selected context payload. It never
receives arm name, case ID, issue ID, label, ground truth, or fix link. The
`user_selected` relation is visible for the extra block and makes the arms
recognizable by source coverage; it is not a statement that the extra is
defective.

## Evaluator contract

Add optional `include_symbols` to each manifest case. If present, it is a
nonempty JSON list of unique qualified repository symbols, excluding the
target. Validate its shape and resolve every entry against the pinned clean
checkout. Pass the tuple to `build_context` during both offline preparation
and run preflight. Record the list in that case's prepared plan only when
present; old manifest files and default case records remain unchanged, apart
from the prepared plan's analyzer-commit metadata. Bind every context and
serialized request to existing hashes and budgets. Rebuild from pinned source
before any provider call; tampered extras, context, plan, or checkout must
fail before output creation or transport. Do not change the product prompt,
source-selection default, parser, scorer, or response protocol.

## Frozen run and decision

Use `deepseek-flash`, Responses `json_schema`, no thinking field, 120 selected
source lines, 64 KiB selected source, 256 KiB serialized body, and 4,096
output tokens. Prepare and inspect all eight exact wire request hashes under
a clean committed analyzer before dispatch. Run one call per case in manifest
order, sequentially, with `--repeats 1 --max-calls 8 --allow-network` and no
retry. A missing or rejected Key, transport error, malformed response, or
source drift ends the run; retain partial records and mark later cases
unattempted. Never save the Key or raw provider bodies.

Review each accepted finding against the pinned source and repair, labeling
TP, FP, uncertain, or duplicate. A quotation match is not a behavioral
verdict. Compare bug detection and fixed-case false alarms between the two
arms for each repair. The narrow usefulness signal is at least one defect
detected only in the explicit arm with no additional explicit-arm false alarm
on either fixed case, all eight calls parseable, and no response or provenance
failure. Anything less is inconclusive or negative for this workflow. Even
meeting that signal does not justify an accuracy claim, a changed default, or
an automatic subclass heuristic: these are two purposive, same-repository,
historical repairs, one model sample per arm, with primary review only.
