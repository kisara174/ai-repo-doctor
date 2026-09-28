# First ten-case Responses JSON Schema diagnosis baseline

Date: 2026-09-28. This is an exploratory, primary-agent-reviewed baseline,
not an independently reviewed estimate of general model quality.

## Fixed input and execution

- Frozen manifest SHA-256:
  `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
  Eight clean, pinned checkouts supplied ten bug, repaired, and control cases.
- Analyzer commit: `091dc2de6ccbaec85abe9f6073f4ecbcb89ad172`.
  Prepared plan SHA-256:
  `227daef6a18915071e74f9d14e59b9a68a939febc260e690d82a6c21d94c9da0`.
  All ten context hashes matched the earlier frozen Chat plan. The new schema
  plan independently matched each production Responses wire-body hash; its
  largest request was 12,981 bytes, with at most 120 selected source lines and
  5,132 source bytes.
- Model: `deepseek-flash`; protocol: Responses `json_schema` with
  `reasoning.effort=none`, `stream=false`, `store=false`, and 4,096 output
  tokens. The prompt, target contexts, and local evidence gate were unchanged
  from the earlier format comparison. The `requests-6628-bug` request body was
  10,947 bytes with SHA-256
  `77ad9764b601ab4d3885bd0f8f33a48b890367e042fb798be82190573140b32a`,
  matching that comparison's Responses body.
- One gated `requests-6628-bug` smoke completed: one locally accepted finding,
  zero rejected, 2,927 prompt and 285 completion tokens. Primary review found
  its arbitrary-keyword-argument concern unrelated to the frozen pickle
  defect. This smoke is separate from the scored dataset run.
- The full run completed 10/10 requests with no provider failure or retry.
  All ten records report usage: 27,675 prompt and 3,323 completion tokens
  (30,998 observed total). Token counts are not a billing estimate. No target
  repository code, tests, or dependencies were executed.

## Primary source review

The tool accepted 14 citations and rejected one. Citation acceptance only
checks that the quoted lines occur in the submitted source. The primary agent
reviewed all 15 findings against pinned source and the documented fix/control
contract. `uncertain` marks a plausible separate issue whose correctness or
relevance cannot be established from this dataset; it is excluded from
precision. This review has no independent second reviewer.

| Case | Finding verdicts | Basis |
| --- | --- | --- |
| `click-3084-bug` | No findings | Missed the known option flag-value defect. |
| `click-3084-fixed` | Rejected 0: FP | Complained that context ended mid-branch; quote and symbol failed local evidence checks and no fixed-contract violation was shown. |
| `click-1921-bug` | Accepted 0: FP; accepted 1: TP | Access-check concern missed the cause. Finding 1 cited `readlink` then `realpath` and proposed anchoring a relative target to the link directory, matching the upstream repair despite its imprecise title. |
| `click-1921-fixed` | Accepted 0: FP; accepted 1: uncertain | Showing the original user path in an error is consistent with the method. A possible noncanonical result for chained links is a separate, unverified concern; the repaired relative-target anchor is present. |
| `requests-6628-bug` | Accepted 0: FP | Speculated about double initialization and did not identify the missing JSON-parent `__reduce__` dispatch or pickle failure. |
| `requests-6628-fixed` | Accepted 0: FP; accepted 1–2: uncertain | Positional JSON decoder arguments and RequestException kwargs are intentional here; `__reduce__` is present. A real grammar typo and a possible missing response attribute are separate from the frozen serialization defect. |
| `requests-7432-bug` | Accepted 0: FP; accepted 1: uncertain; accepted 2: FP | None identified the `Iterable` gate that misses an attribute-proxy file wrapper and loses rewind position. Zero-length framing is a separate unresolved concern; Python retains implicit exception context for the chaining claim. |
| `requests-7432-fixed` | Accepted 0–1: uncertain | Both concern zero-length framing rather than the repaired `Iterable or hasattr(__iter__)` stream gate. |
| `click-control-intrange-clamp` | No findings | No observed false alarm. |
| `requests-control-httpbasicauth` | Accepted 0: FP | Warns with password type rather than the secret value; this does not violate the selected Basic Auth handler contract. |

The exact per-finding decisions and rationales are retained in the ignored
local review artifact at
`.local/diagnosis/schema-ten-cases-20260928/review-primary.json`. Run records
and scored outputs remain in that same local directory; no API key or raw
provider response was saved in tracked files.

## Corrected score and limits

Scorer commit `420495b` corrected a pre-existing numerator/denominator
inconsistency: the fixed/control false-alarm denominator included both
negative case types, but the numerator previously counted only control cases.
The legacy JSON count field
`successful_control_cases_with_accepted_fp` now counts fixed **and** control
cases for compatibility; the Markdown label says “Fixed/control false alarm
rate.” The first local report showed the incorrect 1/6 and is preserved; use
`report-corrected-420495b.json` or `.md` for this run.

| Measure | This run | Meaning |
| --- | ---: | --- |
| Known bug detection | 1/4 (25%) | One of four successful bug cases produced an accepted, primary-reviewed match. |
| Precision | 1/8 (12.5%) | One TP and seven FP among adjudicated accepted findings; six accepted findings remain uncertain. |
| Citation grounding | 14/15 (93.3%) | Exact source checks, not behavioral correctness. |
| Fixed/control false alarms | 3/6 (50%) | Three of six successful negative cases had at least one accepted FP. |
| Uncertain findings | 6/15 (40%) | Including findings about separate possible issues. |

These ten cases were selected for known public defects and include correlated
bug/fixed pairs. One call per case cannot establish model reliability, and
the primary review may need independent correction. The format path produced
parseable outputs for every request in this run, but that does not establish a
future completion rate. The large gap between citation grounding and actual
known-defect detection is the main observed product problem.

## Decision

Keep JSON Schema opt-in and do not switch the default yet. A prompt or context
change must be evaluated against new independently selected holdout cases;
re-running these same ten cases as the sole acceptance gate would tune to
visible answers. The next testable target is fewer unsupported claims while
preserving detection of concrete bug triggers and outcomes. The earlier
[format comparison](2026-09-28-structured-output.md) remains a separate
single-case experiment and must not be pooled with this baseline.
