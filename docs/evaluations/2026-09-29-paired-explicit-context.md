# Paired explicit-context evaluation: partial run

Date: 2026-09-29. This report records the preregistered attempt from the
[design](../superpowers/specs/2026-09-29-paired-explicit-context-design.md).
The cohort and request plans were frozen before dispatch. This attempt does
not provide model-quality evidence.

## Frozen inputs and offline checks

- Dataset: `diagnosis-werkzeug-explicit-context-v1`, eight cases across two
  bug/fixed pairs and default/explicit context arms.
- Manifest SHA-256:
  `a199434e0531b25ea6527df34696d5c66b0784dd16db2a15cfea26d0d9a2791f`.
- Analyzer commit: `eab470863aaf865d175ee5de675063f2bcdc21de`.
- Plan SHA-256:
  `1b6c2ef152818ba39255c8e5ff424b796d6489ba3adbb5d24bcbfde0f513d9ab`.
- All four detached source checkouts matched their pinned HEADs and were
  clean. The two bug snapshots were their repairs' first parents. All eight
  source fingerprints, selected contexts, and serialized JSON Schema request
  hashes were rechecked before dispatch. Prompts contained no case IDs, labels,
  issue references, or ground truth.
- The largest selected context was 70 lines and 2,960 source bytes; the
  largest serialized request was 9,320 bytes. No target code, tests, or
  dependencies were executed or installed.
- After the code change, the prior six-case Werkzeug default plan was
  prepared again at commit `69415f7`. All six case records, context files,
  and request hashes matched the earlier frozen plan; only analyzer-commit
  metadata changed.

## Dispatch outcome

The sequential runner attempted the first case,
`werkzeug-empty-special-bug-default`, and stopped after a `provider_error` with
safe error code `connection`. The record had no HTTP status and no provider
usage fields. No successful model response or finding was recorded. The
remaining seven cases were not attempted. The run, partial record, and empty
review template remain under ignored `.local/diagnosis/explicit-context-*`
artifacts.

| Measure | Result |
| --- | ---: |
| Planned cases | 8 |
| Requests attempted | 1 |
| Successful model responses | 0 |
| Connection failures | 1 |
| Not attempted | 7 |
| Reviewable findings | 0 |
| Provider token usage | unavailable |

The safe scorer output reports zero end-to-end detections because there were
no successful responses and seven planned calls were not attempted. This is a
run failure, not evidence that the model missed the known defect. With no
usage metadata, no billing conclusion can be made.

## Decision

The preregistered paired comparison did not complete. Its usefulness signal,
bug detection, fixed-case false alarms, and grounding are unavailable. No
accuracy claim or product-default change follows. Mark this cohort consumed
for holdout purposes because one request was attempted; do not present it as
unseen evidence in a later run. The next comparison needs a fresh frozen
cohort and an operational provider connection before dispatch.
