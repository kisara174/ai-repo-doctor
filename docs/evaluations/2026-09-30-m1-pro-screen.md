# M1 Pro model screen on the frozen non-thinking cohort

Registered 2026-09-30 before any `deepseek-v4-pro` response for this cohort was
read. This is a **candidate screen**, not a new holdout or a population-level
quality estimate. The existing [M1 v2 evaluation](2026-09-29-m1-holdout-v2.md)
called `deepseek-flash` on these exact repairs and found no accepted known
defect among three buggy snapshots, one accepted false alarm on a repaired
snapshot, and one invalid JSON response. Those results and their review rubric
are frozen; they will not be rescored.

## Input and variable under test

Reuse the exact six-case `evaluation/diagnosis/m1-holdout-v2.json` manifest,
SHA-256 `98a051c5ca478ae4f33e155a6b4f24e72041138df018bc3f51f0de55d82446d4`.
Its tomlkit, attrs, and AnyIO bug/fixed checkouts stay pinned and source-only.
The target repositories, their tests, and their dependencies are not executed
or installed. The prompt, selected source context, 120-line/64-KiB source
budget, 256-KiB wire cap, `chat-json` format, explicit disabled thinking, and
4,096 output-token limit are unchanged. Only the requested model changes to
`deepseek-v4-pro`. Offline preparation must confirm the six context hashes
match the earlier Flash plan; model-specific request hashes must be frozen
before dispatch.

The current API Key passed the product's read-only `doctor --deepseek --model
deepseek-v4-pro` readiness check before this registration. The
[official model and pricing table](https://api-docs.deepseek.com/quick_start/pricing/)
lists Pro as available and, when checked on 2026-09-30, gives peak all-cache-miss
input and output prices of $1.32 and $3.96 per million tokens. These are
estimation rates, not a billing statement.

## Call, review, and stop rules

- Prepare from a clean committed analyzer checkout and six clean pinned target
  checkouts. Save the analyzer commit, canonical plan hash, six context hashes,
  and six model-specific request hashes.
- Send one call per case, in manifest order, **six calls maximum**, using only
  the evaluator's explicit network path. No retries, prompt changes, extra
  symbols, model fallback, or sample substitution after dispatch. Preserve
  attempted, failed, and unattempted records if the run stops early.
- Source-review every accepted and rejected finding against the pinned source,
  repair diff, and upstream regression. A TP must identify the registered
  trigger and wrong outcome on the buggy snapshot. Exact quotations prove
  source provenance only. Mark TP, FP, uncertain, or duplicate with a source
  rationale before scoring.
- Report the response model, parseability, known-bug accepted TP count,
  repaired-snapshot accepted FP count, provider usage, elapsed time, and an
  all-cache-miss peak-cost estimate. If no accepted TP exists, cost per useful
  issue is undefined.

## Decision rule

Pro is worth a **fresh independent paired holdout** only if all six responses
are parseable, at least two of three known defects yield an accepted TP, and
no repaired snapshot has an accepted false alarm. If this screen fails, keep
the released `deepseek-flash` default and keep symptom guidance
evaluation-only. If it passes, do not yet change the product default or add a
symptom flag: the same known cohort cannot establish independent quality, and
the previous symptom-guided study had repaired-snapshot false alarms. A new
preregistered cohort would be required before any product adoption decision.

## Result

Pending the single registered run and primary source review.
