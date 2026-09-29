# Click explicit-context paired evaluation

Date: 2026-09-29. The [preregistered design](../superpowers/specs/2026-09-29-click-explicit-context-design.md)
compared the current default context with one explicitly selected `Choice`
method on two fresh historical Click repairs. The full run completed, but its
narrow usefulness signal failed. This is exploratory evidence from one model
sample per case, not a general accuracy estimate.

## Frozen inputs and dispatch

- Dataset: `diagnosis-click-explicit-context-v1`; eight cases from
  [Click #1692](https://github.com/pallets/click/issues/1692) / [PR #1693](https://github.com/pallets/click/pull/1693)
  and [Click #2356](https://github.com/pallets/click/issues/2356) / [PR #2365](https://github.com/pallets/click/pull/2365).
  Exact commits, target fingerprints, behavioral contracts, and source links
  are in [the frozen manifest](../../evaluation/diagnosis/click-explicit-context-v1.json).
- Manifest byte SHA-256:
  `a3b5341bd219f734730cf7272939c890e8ecf3c458ac5cd42096b07ecfe48bd1`.
  Analyzer commit: `1f2db12d4ba038c858bea5adbc8c793574711700`.
  Canonical prepared-plan SHA-256:
  `0e0e3452bd7378bdd1266771fd2db1466866691bf8917c22de7a6b854db80f75`.
- Four detached Click checkouts matched the pinned commits and were clean;
  each fixed commit's first parent was the corresponding bug snapshot. All
  eight source fingerprints and serialized request hashes were independently
  checked. No context block was truncated. The largest context was 43 source
  lines; the largest serialized request was 6,255 bytes.
- Within each repair, default bug/fixed requests had identical bytes because
  their public `Parameter` target stayed unchanged and the repaired `Choice`
  method was omitted. Explicit requests contained that method in full and
  differed across the repair. Prompts contained no case IDs, labels, issue
  IDs, ground truth, or fix links.
- A source-free `doctor --deepseek --model deepseek-flash` check returned
  `ready` immediately before dispatch. The sequential runner used Responses
  `json_schema`, `reasoning.effort=none`, a 4,096 output-token limit, and one
  call per case without retry. All 8/8 calls succeeded and yielded parseable
  output. No target code, tests, or dependencies were executed or installed;
  the Key and raw provider bodies were not saved in evaluation artifacts.

## Primary source review

The local evidence gate accepted four findings and rejected none. Each quote
matched selected source, but quotation matching did not establish a defect.
The review template, four source-backed adjudications, safe run records, and
score remain in ignored `.local/diagnosis/click-explicit-*` files.

| Repair and snapshot | Default arm | Explicit arm | Primary review |
| --- | --- | --- | --- |
| Completion bug | No finding | One accepted FP | The model discussed mixed or generator returns from a custom completion callback. The pinned [Click completion documentation](https://github.com/pallets/click/blob/acc91bc4f47e38f43277fcdfd8ca855734c4fbbc/docs/shell-completion.rst#L149-L162) requires a list of `CompletionItem` objects or a list of strings; an empty list is valid. It did not identify the old `Choice.shell_complete` case-sensitive prefix check. |
| Completion fixed | One accepted FP | One accepted FP | Both findings again concerned mixed custom-callback return types outside that documented contract. The [repair](https://github.com/pallets/click/commit/5eb46cba463ff3e3894b58f6649c5a13f02a70b1) addresses `Choice` case sensitivity, which neither finding challenged. |
| Metavar bug | No finding | One accepted FP | The model proposed removing square brackets. The old code deliberately uses them, and the [upstream regression test](https://github.com/pallets/click/blob/1a4d8c1bb1e8f8e214ede7223bd2c05dc2ce006a/tests/test_options.py#L931-L964) expects `[TEXT]` when `show_choices=False`. It missed the actual choice-value leak. |
| Metavar fixed | No finding | No finding | No fixed-case alarm on this repair. |

The same default completion request bytes produced no finding for the bug row
and a false positive for the fixed row. This observed response difference
limits any causal reading of one-sample arm differences.

| Measure | Result | Scope |
| --- | ---: | --- |
| Completed, parseable calls | 8/8 | Four bug-arm and four fixed-arm cases. |
| Known bug matches | 0/4 | Neither of the two distinct repairs was identified in either arm. |
| Adjudicated accepted precision | 0/4 | Four accepted findings, all FP; no uncertain or duplicate rows. |
| Citation grounding | 4/4 | Exact local source quotation only. |
| Fixed-case false alarms | 2/4 | One default and one explicit alarm on the same completion repair. |
| Additional explicit fixed-case alarms | 0/2 pairs | The explicit arm did not add an alarm beyond its paired default arm. |

Provider-reported usage was 9,937 input and 1,059 output tokens, 10,996 total.
The four default calls used 4,494 total tokens; the four explicit calls used
6,502. These are observed usage counts, not a billing estimate. The median
request duration was 1.372 seconds.

## Decision and limits

The preregistered signal required eight parseable calls, at least one known
bug detected only in an explicit arm, and no additional explicit fixed alarm.
The first and third conditions held; the required bug detection did not.
Explicitly adding the `Choice` method did not demonstrate useful diagnosis in
this run. Keep cloud findings labeled as quotation-checked claims requiring
human review; do not change the product's default context selection or tune
against these now-visible cases.

Both repairs came purposively from one library, are historical public fixes
that may be in training data, and share bug/fixed context within each arm.
There was one model sample per case and one primary reviewer. These results
do not estimate general accuracy, reliability, or performance on unseen
repositories. The next useful work is to define and validate a stronger
behavioral evaluation or review method on a new frozen cohort before changing
the diagnosis workflow.
