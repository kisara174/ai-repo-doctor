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

The offline plan was prepared from clean analyzer commit
`65a3e1cd93d212b61b6be4577c94979da8aa6099`. Its canonical plan SHA-256
was `49152b340a52aa0ea3cb07557e43892e3563b1f8bc4dee5464d056811c1daa7e`.
All six selected context files matched the earlier Flash plan byte for byte.
The model-specific request hashes were frozen before dispatch:

| Case | Context SHA-256 | Pro request SHA-256 | Verifier output |
| --- | --- | --- | --- |
| tomlkit bug | `51663e048b37ba82e52090bf88c2813b362483cbd8160aad6d73ea850592abd9` | `3000ddeec34f6f441af56600c0441c12c9198838776e35f37b2b863ac2987b91` | 0 accepted, 2 rejected |
| tomlkit fixed | `86cc3f58fa7472b61dec2c15da60acdc8ae318778af3b5278ee944f0602cab7d` | `bd2dbeb824d55fddc3c7b69a8220e72d388b269ba098d5fe65c308ed0e03a908` | 1 accepted, 1 rejected |
| attrs bug | `ac429d8c0fc1bd16c600e172790eb529ab0cbebd42700cefc18c92dcd6e35c60` | `fdc63e96030a44d4b7d42e4c8f28038ce4051c16663f52ddbf6b2ddddcda141d` | 1 accepted, 0 rejected |
| attrs fixed | `2c444bf68919774091e74992267496d60deb55f4c12a25030e07dc3907044253` | `453089858fee145b7110f6a3c06b99a9d76fd35792cff3b3c8c7c606ae2b7c68` | 0 accepted, 0 rejected |
| AnyIO bug | `30fc2ae58ed9b7db3e54e813b8b50cad3f6e9d212e0eb791a75416b7a9cf6591` | `ea7d66e305e3507f8556dbb7a502aced64798af3fe4c1d56049bf1bcb98ea1de` | 1 accepted, 0 rejected |
| AnyIO fixed | `f5708c265aa5da9679def081cf1ac425eaa9a7ccdd125ae47d055f9d006523f8` | `0678f1bf81e50d27049aab1b51e500255494481b8bf104484fe0862c265b772a` | 0 accepted, 2 rejected |

The single authorized run attempted and completed **6/6** calls with no retries.
Every response identified `deepseek-v4-pro` and was parseable. The verifier
accepted three findings and rejected five on quotation or symbol checks. The
primary agent reviewed all eight findings against the pinned source and repair:

| Case and bucket/index | Review | Source-based reason |
| --- | --- | --- |
| tomlkit bug rejected 0 | FP | The entry checks the delimiter, and `Source.inc()` installs a NUL EOF sentinel; `ord(_current)` is not an empty-string index error. The registered internal CRLF hang is absent. |
| tomlkit bug rejected 1 | FP | `original += close[:-3]` preserves extra closing-delimiter characters in the source spelling; no failing string or internal CRLF hang is identified. |
| tomlkit fixed rejected 0 | FP | EOF after three closing delimiters is valid; fewer delimiters do not return a completed string. The loop's plain `inc()` is intentional. |
| tomlkit fixed accepted 1 | FP | EOF immediately after a proper closing delimiter is valid, while the ordinary-character path still requires more input. No incomplete-string failure or recurrence of the repaired CRLF hang is shown. |
| attrs bug accepted 0 | FP | `_OBJ_SETATTR` is `object.__setattr__`, so the asserted recursion does not follow. The one-shot transformer output lost by later loops is not described. |
| AnyIO bug accepted 0 | FP | The claim concerns normal insertion after waking. It omits cancellation after a signaled waiter is removed from the queue, which is the registered lost-wakeup trigger. |
| AnyIO fixed rejected 0 | FP | The repaired cancellation branch notifies the next waiter when the cancelled waiter's event was set; no token was acquired by the cancelled borrower. |
| AnyIO fixed rejected 1 | FP | The capacity check and borrower mutation in `acquire_on_behalf_of_nowait` are synchronous, with no task-switching `await` between them. |

The registered screen **failed**. Source review found **0/3** accepted known
defects, **1/3** repaired snapshots with an accepted false alarm, and **6/6**
parseable responses. Accepted-finding precision was 0/3; conditional recall
and end-to-end detection were 0/3. The six requests used 22,551 prompt and
2,067 completion tokens. At the registered all-cache-miss peak rates, the
estimated cost ceiling is **$0.03795264** (not a billing statement); cost per
accepted true positive is undefined. Median provider request time was 3.92
seconds. The raw run, review, and score files are in the ignored local
`.local/diagnosis/m1-pro-screen-*` directory; this document retains the
reproducible plan identifiers and review outcome.

Compared with the same-context Flash run, Pro removed the one invalid JSON
response but did not improve known-defect detection or the repaired-snapshot
false-alarm count. This reused cohort cannot establish general reliability.
Keep the released `deepseek-flash` default, keep symptom guidance
evaluation-only, and do not spend a fresh independent cohort on this Pro
candidate under the registered gate.
