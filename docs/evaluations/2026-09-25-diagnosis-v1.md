# AI Repo Doctor diagnosis evaluation v1 — 2026-09-25

## Status

**Infrastructure complete; the first live run stopped with a provider error.** This is a partial run, not a completed model evaluation. The offline scorer produced failure accounting, but no valid model response was recorded. The review template has zero rows because there were no findings to adjudicate.

| Item | Status |
| --- | --- |
| Evaluation date | 2026-09-25; offline preparation and one live attempt |
| Analyzer commit | `5044a94b37631f19b8547ba568b235b4fa9e695f` |
| Dataset | `diagnosis-v1`; frozen manifest SHA-256 `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f` |
| Prepared plan | `.local/diagnosis/plan-v1`; canonical plan SHA-256 `9a657f2a6ca92481e6dda07212adb9b3503713956201c7006863a54a8ac36b56` |
| Requested model | `deepseek-flash` (the currently documented API ID for DeepSeek-V4.1-Flash); this is not an observed response model |
| Response model | Not available; the attempted request returned no usable response |
| Planned / attempted / successful responses | 10 / 1 / 0; 9 requests were not attempted |
| Model findings / score | 0 findings returned; quality ratios are undefined. End-to-end detection is 0/4 in this incomplete run and is not a model-quality estimate |
| Errors, uncertain findings, duplicates | 1 `provider_error` among 1 completed call; 9 requests were not attempted |
| Tokens / latency | Usage is unavailable (`null`); the failed request took 0.0346 seconds, not a model-response latency |

The initial preparation process did not have `DEEPSEEK_API_KEY`. The key is now available to a zsh login shell; its value was never displayed or written to the repository. The first live request was attempted from that shell and recorded only as `provider_error`. The client deliberately stores a generic error category, so the record does not distinguish an HTTP rejection from a connection failure. No automatic retry occurred, and the other nine requests were not sent. The user approved the original ten-request scope; any additional attempt requires fresh authorization. Billing for the failed request cannot be determined from the run record.

## Scope and reviewed request contents

The frozen manifest contains ten purposively selected contexts from public Click and Requests snapshots: four bug/fix pairs and two controls. The 10 prompts cover 783 source lines and 32,236 source-text bytes, with no case exceeding 120 lines. The actual fixed system prompt plus user prompt contents total 70,426 UTF-8 bytes; that is a byte count, not a provider token estimate.

Each request sends the fixed diagnosis instructions and one case's `symbol`, selected source `blocks`, and static `call_evidence`. It excludes manifest labels, ground truth, issue/fix metadata, local absolute paths, and credentials. I inspected all ten prepared files and their reconstructed prompts. They contain public source code only; no personal data or credential values were found. The prompt treats repository code, comments, and strings as untrusted input. The source and licenses are listed in the [dataset README](../../evaluation/diagnosis/README.md).

| Case | Snapshot | Symbol | Lines / source bytes | Context SHA-256 | Request SHA-256 |
| --- | --- | --- | ---: | --- | --- |
| `click-3084-bug` | Click `7f7bbe4569ea` | `src/click/core.py::Option.__init__` | 120 / 5,101 | `e70e24ef0c102c8eaf249c86102d05797b905073caaa0f7ca23c1c6511567564` | `63b4923935107db33d630b822026399d5bc68a890885d658abccf968f5a7ddb6` |
| `click-3084-fixed` | Click `ebcd548d5066` | `src/click/core.py::Option.__init__` | 120 / 5,132 | `24a048dedcac62b72c9e9221b6cd288538e30d07b30c2f15ec7b5ba4f63b921d` | `964163f0be72b2f29ee27ce64b63a02238619e12f9e834d458714721fa967742` |
| `click-1921-bug` | Click `76cc18d1f0bd` | `src/click/types.py::Path.convert` | 72 / 2,603 | `9a801e34952cdf05070c1e116fc2c9613647c82ea69db03a6d449a865de8645c` | `f98d15a00284880d8796fd112d269708bb83c5542d0e7d07486d96a7cf2bd983` |
| `click-1921-fixed` | Click `e24db5732f30` | `src/click/types.py::Path.convert` | 81 / 3,105 | `76f5b9f619cf4191ed5ab5c4c1f38ac499af13efd398186bf2eb1f7b5c88467d` | `02266283bb0683d830c892abb49ec605ae40816770f9c31bedce693acaa4900b` |
| `requests-6628-bug` | Requests `7a13c041dbef` | `src/requests/exceptions.py::JSONDecodeError` | 44 / 2,170 | `742c6ef12db73d6e77c725fd3b23fcec40f39d5c5d5e984a7d889d43ab50d7d2` | `1d4f44fcf85af62c9dae49bc341302a7c250059b64a1be6af13cabd5026519a1` |
| `requests-6628-fixed` | Requests `382fc2c0c6c0` | `src/requests/exceptions.py::JSONDecodeError` | 54 / 2,619 | `7605f805d5d09df09a5bf7c7cbe5618f3aa96cb21d1326e9ebadaa41dd6e5fe3` | `4589407244e02c23b8c712e9ecb0a7a0db82db5116cfd0f3d475a79402c2781d` |
| `requests-7432-bug` | Requests `0b401c76b6e8` | `src/requests/models.py::PreparedRequest.prepare_body` | 120 / 4,663 | `40d2d38ce3ad8a7a88e0958936a4ea3d2ea6790e7954ff8ea2287d45b4f3709f` | `3a4380701551891357f55c69a6fdde2559de7006c55c0c22e26e802f6dbdce75` |
| `requests-7432-fixed` | Requests `6404f345e562` | `src/requests/models.py::PreparedRequest.prepare_body` | 120 / 4,779 | `33ad6f01de9b07e105b279ed6d814016608cbbde24b741705774495ade202356` | `48fc7edd5421048cdd367c4630d5791ccae6187db30ae0aea783e72b5876b141` |
| `click-control-intrange-clamp` | Click `e24db5732f30` | `src/click/types.py::IntRange._clamp` | 7 / 183 | `885e7fe0b355c105a7ccc475e06e2963741799c2d6ccea87efe4d07014468d81` | `3240063ab2964602c67d3f76c1415050a833a72697fa3d2fff4d195b88099b71` |
| `requests-control-httpbasicauth` | Requests `6404f345e562` | `src/requests/auth.py::HTTPBasicAuth.__call__` | 45 / 1,881 | `67e4af7e6639dea2943f006ec8548a17350c062cff5ac79c9fc1adf6d5453380` | `63a71dcc9636ee976697a01df5173826fb0e4008ff4986e7513a48980afc07a5` |

The public source snapshots are identified by immutable commit IDs and licensed under BSD-3-Clause (Click) and Apache-2.0 (Requests). This report paraphrases the cases and does not reproduce source excerpts. Public issue and fix references are recorded in the manifest and dataset README.

## Model and cost scope checked

The official DeepSeek documentation checked on 2026-09-25 identifies `deepseek-flash` as DeepSeek-V4.1-Flash. The prepared requests use the API's current default thinking mode because the client does not set a `thinking` parameter; the official Chat Completions documentation lists thinking as enabled by default. This must be reconsidered if the provider changes its defaults before execution.

The client caps generated output at 4,096 tokens per request and makes no automatic retries. At the official peak output rate of $1.20 per million tokens, the theoretical output-only maximum is 40,960 tokens × $1.20 / 1,000,000 = **$0.049152 (about $0.05)**. Input tokens are billed separately: the listed peak rates are $0.30 per million input cache-miss tokens and $0.006 per million input cache-hit tokens. The exact tokenizer count and cache split are not known before a request. The run record also stores aggregate prompt/completion/total usage rather than cache-hit/miss detail. Therefore the total cost estimate is **null**, and the 10-request cap is not a hard dollar limit. The provider's billing page remains authoritative.

Official sources: [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/), [DeepSeek-V4.1-Flash release](https://api-docs.deepseek.com/news/news260910/), and [Chat Completions API parameters](https://api-docs.deepseek.com/api/create-chat-completion/).

## Representative dataset cases

These illustrate the selected test inputs only; they are not AI findings or evaluation results.

- **Click issue #3084:** a before/fixed pair around `Option.__init__` flag-value handling and whether an explicitly non-flag option still needs a value. See the [upstream issue](https://github.com/pallets/click/issues/3084) and [fix PR](https://github.com/pallets/click/pull/3152).
- **Requests issue #6628:** a before/fixed pair around `JSONDecodeError` construction and its pickle behavior. See the [upstream issue](https://github.com/psf/requests/issues/6628) and [fix PR](https://github.com/psf/requests/pull/6629).

## Limits and next step

Ten directed cases are a small exploratory sample, not a random sample of repositories. Bug/fixed pairs are correlated, controls cover only selected behavior, and public issue/fix material may have appeared in model training data. No overall product-quality or reliability claim can be made. The partial scorer reports precision, conditional recall, grounding, control false-alarm rate, uncertain rate, and duplicate rate as undefined because there were no successful responses. End-to-end detection is 0/4 under the frozen all-bug-case denominator, but this reflects that no case returned a usable response; it is not evidence of model performance. The completed-call failure rate is 1/1, and 9 requests were not attempted.

The first attempt is preserved locally in `.local/diagnosis/run-v1-r1`; its one record is `provider_error`, with no returned usage data. The local record does not reveal whether the provider rejected the request or a connection failed. The key's presence/format and the configured local proxy's TCP reachability were checked, but these checks do not establish provider authorization or account balance.

Before another run, verify the DeepSeek account/key status and review whether the failed attempt incurred any charge. A fresh run requires new approval because the original no-retry run has already attempted one request. It must use a new output directory and a clean checkout at the frozen analyzer commit `5044a94b37631f19b8547ba568b235b4fa9e695f`. Since the prepared plan is ignored by Git, pass its absolute path from the preparation checkout. After a successful run, generate the manual review template and complete that review before scoring.

**Integration status (separate from this diagnosis run).** PR #6 was merged into `codex/repo-doctor-v1` at merge commit `ec5041d3b98e07dc42532336e36ebe9ac2e82f12`, with all Python 3.11–3.13 CI jobs passing. The reviewed PR head was `3492deb7c9971c06da48477f2dff6a8836cf2226`. This code integration does not change or retry the recorded provider-error request. This report and the raw `.local` run artifacts remain local and unpublished.
