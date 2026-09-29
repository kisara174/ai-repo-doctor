# Werkzeug diagnosis holdout design

## Purpose and decision

Measure the merged method-context build against six previously unused public
Werkzeug snapshots. The three upstream bug/fixed pairs test whether the current
DeepSeek JSON Schema path produces actionable, source-supported findings while
remaining quiet on repaired code. This is a new repository and a small,
purposively selected cohort. It is not an unbiased estimate of accuracy, and
it does not isolate the effect of the one-line class header from all other
input differences. The old Click/Requests and Flask manifests remain frozen.

There is one current-product arm and no prompt edit. Changing the prompt after
seeing the outputs would consume this holdout as tuning data; any subsequent
comparison needs new cases.

## Frozen inputs

Add `evaluation/diagnosis/werkzeug-holdout-v1.json` with schema version 1 and
the exact dataset ID `diagnosis-werkzeug-holdout-v1`. Each row records its
commit, clean checkout ID, source span and SHA-256, upstream references,
trigger/outcome ground truth, and primary-agent approval. The model receives
only selected context, never the issue ID, label, ground truth, or fix links.

| Upstream issue / fix | Bug commit | Fixed commit | Target symbol |
| --- | --- | --- | --- |
| [#2842](https://github.com/pallets/werkzeug/issues/2842) / [PR #2843](https://github.com/pallets/werkzeug/pull/2843) | `4c09d1b3b08deb939803a4beb53483cbc54dfb8d` | `f516c4005c7c4510b61ae07969450771b929809d` | `src/werkzeug/datastructures/structures.py::TypeConversionDict.get` |
| [#2985](https://github.com/pallets/werkzeug/issues/2985) / [PR #2986](https://github.com/pallets/werkzeug/pull/2986) | `d1f60d68ac9788aec05712aca29867abd00d5cc3` | `64d27f79eb84880b33f4451e078dab0b49c4c2c2` | `src/werkzeug/datastructures/headers.py::Headers.__str__` |
| [#2994](https://github.com/pallets/werkzeug/issues/2994) / [PR #2995](https://github.com/pallets/werkzeug/pull/2995) | `1a1728ed88939ca68928dade168e1989be062c6f` | `ea93b549a93f65b216070e72a26cf0cc31d1e9ad` | `src/werkzeug/datastructures/structures.py::MultiDict.__init__` |

The bug snapshot is the fixed commit's first parent in every row. #2843 was
committed directly; #2986 and #2995 were merged. All six checked-out target
symbols are unique, parse without errors, and fit the diagnosis source budget.
The target source spans and hashes are fixed before model use:

| Case | Source lines | SHA-256 |
| --- | --- | --- |
| `werkzeug-2843-bug` | `structures.py:55-85` | `49a2e7b78e6816bfa9e37767622aae2c0e0196cc602fa6c5019157b108f2c05d` |
| `werkzeug-2843-fixed` | `structures.py:55-89` | `37268a2b4d145b30ee22d187fa33b789f8d50c03986933bb3c2f5c2da1417534` |
| `werkzeug-2985-bug` | `headers.py:568-574` | `2d47f839a2d8f6546400d0a0104b48c4bdfc52caffca29c12d53d07550288b58` |
| `werkzeug-2985-fixed` | `headers.py:568-574` | `7f640552c9cc12b1e5eebc1e03cd034a7d8e949efabd911357950ac272a9021f` |
| `werkzeug-2994-bug` | `structures.py:181-210` | `509c2d83cf82c57d891032f1ea9763134795364eed56e57d41210a5a1481c671` |
| `werkzeug-2994-fixed` | `structures.py:181-210` | `6eb95ab3086d14d44304b3163b7eb7bdfd1fcf38288e45b4dde718d34adbed33` |

For #2842, a `None` value converted with `int` raises `TypeError` rather
than returning the requested default. The repair catches `TypeError` like
`ValueError`. For #2985, an `EnvironHeaders` instance inherits
`Headers.__str__`; iterating its private `_list` yields an empty formatted
header block despite available WSGI environment headers. The repair uses its
public `to_wsgi_list()` view. For #2994, initializing `MultiDict` from a
mapping with a bytes value treats that bytes object as a collection of integer
elements. The repair recognizes only list, tuple, and set as multi-value
containers. Fixed cases are negatives for their paired contracts only; they
are not certified defect-free.

## Execution and review

Prepare under a clean committed analyzer with `deepseek-flash`, Responses
`json_schema`, `reasoning.effort=none`, 120 selected source lines, 64 KiB
selected source, 256 KiB serialized request body, and 4,096 output tokens.
Inspect all six context and request hashes before dispatch. Run one call per
case in the table's order, without retry. A missing or rejected Key, malformed
response, transport error, or checkout drift stops the run; retain the partial
record and mark remaining cases unattempted. Do not run Werkzeug code, tests,
or dependencies, and do not persist the Key or raw provider responses.

The primary agent reviews every accepted finding against the pinned source
and upstream fix, labeling TP, FP, uncertain, or duplicate. Local quotation
validation is distinct from correctness. Score only complete review rows;
report completed and unattempted calls separately, as well as provider usage
without inferring billing. Report bug detection, false alarms on fixed cases,
adjudicated precision, and grounding for this cohort alone. No independent
second review is available yet.

Treat at least two correctly detected bug cases, at most one fixed-case false
alarm, six completed parseable responses, and later independent adjudication
as a gate for considering a broader product-quality claim. Meeting it in six
purposive cases would still require a larger independent evaluation. If the
gate fails, keep cloud diagnosis explicitly experimental and classify misses
as missing context, unsupported reasoning, or response noncompliance before
choosing one new change. Do not tune against these cases and call them unseen
again.
