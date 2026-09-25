# Next iteration candidates — 2026-09-25

## Evidence available

- M05's baseline-v1, challenge-v1, and challenge-v2 scans each ran five times per repository. Probe outputs, metrics, scanner stats, and scan hashes matched the prior reports with zero mismatches.
- M06 made one DeepSeek transport attempt and received only a connection error. The command used an unpinned Requests checkout by mistake; no valid model response or usage record exists. This gives no model-quality evidence and leaves billing unknown.
- M08 measured `build_index` at a median 5.2382 seconds of a 5.4590-second total prepare, with two redundant builds for repeated manifest snapshots.

## Ranked work

| Priority | Candidate | Evidence and dependency | Concrete acceptance |
| --- | --- | --- | --- |
| P0 | A fresh one-call connectivity experiment, only after a new explicit run is authorized | M06 failed with a connection error and used an unpinned checkout. The current M06 attempt is closed; do not retry it automatically. | Before sending, select the manifest-pinned checkout by reading its `checkout_id`, verify its HEAD and clean state, inspect the exact payload/hash, use `deepseek-flash` with the existing byte, token, response, and timeout limits, and make at most one request. Stop on failure. Record 0/1 attempts, response status, usage, and unknown billing accurately. |
| P1 | Reuse indexes inside one offline `prepare_cases` invocation | M08 observed two repeated `(checkout_id, commit)` snapshots and `build_index` dominated measured time. | In a separate implementation task, cache only by the verified `(checkout_id, commit)` for that invocation. Prove all 10 M05 context and request hashes, source fingerprints, evidence, and order are unchanged; run targeted and full tests; then repeat the five-run measurement. |
| P2 | Add model challenge pairs or broaden product scope | No valid model response, FP/FN, or uncertainty labels are available. | Do not select new bug/fixed pairs or adjust prompts until M07 produces manually reviewed evidence. Keep new candidates unmerged from the frozen datasets until independently sourced and reviewed. |

## P1 follow-up result

The invocation-local index cache was implemented and verified on clean analyzer commit `ad07876172ea5af6e995cd7ac1765c97110dde17`. All ten M05 plan case records and context objects remain identical; index builds fell from 10 to 8 per prepare run. The full suite passed 256 tests. The five-run timing comparison and its limits are recorded in `docs/evaluations/2026-09-25-preparation-cache.md`.

## M07 status

M07 cannot start because M06 produced no valid model response. There are no model TP/FP/FN labels to score, no model correctness or recall estimate, and no basis for prompt tuning. A future authorized M06 run must use the exact reviewed manifest checkout before M07 is reconsidered.

No Web UI, multi-provider routing, auto-fix PRs, vector store, persistent cache, or model-based automatic scoring is proposed by this evidence.
