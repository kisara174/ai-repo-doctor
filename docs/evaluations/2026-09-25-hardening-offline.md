# Offline hardening evaluation — 2026-09-25

## Scope and provenance

This records the offline M05 regression run after M02–M04. The analyzer was clean at commit `2667ff0b6765edba57c958510754b21dcb0851a2`. PR #7's actual head at that point passed all six push and pull_request CI jobs across Python 3.11, 3.12, and 3.13. The local run used Python 3.14.5 on macOS 27.0 arm64.

All generated reports and the diagnosis plan are under the ignored directory `.local/diagnosis/hardening-offline-2667ff0/`. The previous run in `.local/diagnosis/post-review-pr6-3492deb/` was read for comparison and left unchanged. No provider API request was made.

## Commands

Each fixed repository checkout was verified clean at the manifest SHA before scanning. Each dataset was evaluated five times per repository:

```sh
python3 tools/evaluate_baseline.py --repos-root /tmp/ai-repo-doctor-checkouts --manifest evaluation/baseline-v1.json --runs 5 --json-out .local/diagnosis/hardening-offline-2667ff0/baseline-v1.json --markdown-out .local/diagnosis/hardening-offline-2667ff0/baseline-v1.md
python3 tools/evaluate_baseline.py --repos-root /tmp/ai-repo-doctor-checkouts --manifest evaluation/challenge-v1.json --runs 5 --json-out .local/diagnosis/hardening-offline-2667ff0/challenge-v1.json --markdown-out .local/diagnosis/hardening-offline-2667ff0/challenge-v1.md
python3 tools/evaluate_baseline.py --repos-root /tmp/ai-repo-doctor-checkouts --manifest evaluation/challenge-v2.json --runs 5 --json-out .local/diagnosis/hardening-offline-2667ff0/challenge-v2.json --markdown-out .local/diagnosis/hardening-offline-2667ff0/challenge-v2.md
python3 -m tools.evaluate_diagnosis prepare --manifest evaluation/diagnosis/manifest-v1.json --repos-root /tmp/ai-repo-doctor-diagnosis-checkouts --model deepseek-flash --max-lines 120 --out-dir .local/diagnosis/hardening-offline-2667ff0/diagnosis-plan
```

`deepseek-flash` matches the model recorded in the previously frozen diagnosis plan. It is only part of the offline request fingerprint here; it was not contacted.

## Baseline and challenge results

All three datasets matched the previous `post-review-pr6-3492deb` results for repository IDs, scanner statistics, every relation metric, every probe's expected/predicted/TP/FP/FN sets, and per-run scan hashes. Each repository's five hashes were stable and identical to its previous report. There were zero mismatched probes in all three reports. Report timestamps, analyzer commit metadata, and timings naturally differ and were not used as semantic equality checks.

| Dataset | Click median (s) | Flask median (s) | Requests median (s) | Probe mismatches | Stable hashes |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline-v1 | 1.4665 | 0.7334 | 0.4259 | 0 | 5/5 per repository |
| challenge-v1 | 1.4764 | 0.7371 | 0.4318 | 0 | 5/5 per repository |
| challenge-v2 | 1.4840 | 0.7387 | 0.4310 | 0 | 5/5 per repository |

The timing values are per-scan medians from this machine. Filesystem cache state was not controlled, so these are not a performance claim or a cross-machine benchmark.

| Dataset | JSON SHA-256 | Markdown SHA-256 |
| --- | --- | --- |
| baseline-v1 | `34bf330443713254937141eff2e4eeeb3bc7575ee0822ca4213b60510dc67925` | `e41c96ebf3cf4b18d33893ab56b29556f9a13f207551764bded7ee3a4496b753` |
| challenge-v1 | `dfc0dc030534d4d35aaed3e119010db0c442f751dfff4f19e0c5cec805e742e4` | `486208b2cc0df1f81da72f38fe25e75e5edfa23ee7815d91c6c4e979cf2b9d72` |
| challenge-v2 | `4a2f10c1256552ee7d83e89fb64cdfcf34cea86575c86dea11510dd1998ac91e` | `b3f86a794f03c6b4c3ace2b868c166f3030d57a3641b317d48119b60af9f77bc` |

## Diagnosis plan and context review

The new plan records analyzer SHA `2667ff0b6765edba57c958510754b21dcb0851a2`, manifest SHA-256 `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`, and contains 10 cases. The plan file SHA-256 is `cc08799a902159454b9d0e0393819f4ff3adea24b271cc0fc87f36723141f705`.

Every context was checked against the manifest and plan: only `symbol`, `blocks`, and `call_evidence` are present; paths are repository-relative; all 10 context and request hashes independently recompute; no ground-truth field or label appears. The four bug/fixed pairs and two controls were reviewed, including the changed source blocks and call evidence. The contexts cover Click issues 3084 and 1921, Requests issues 6628 and 7432, plus the IntRange and HTTPBasicAuth controls. The Option constructor and one `super_len` neighbor are marked truncated at the configured context limit; the relevant changed lines and evidence are present.

| Case | Context SHA-256 | Request SHA-256 |
| --- | --- | --- |
| click-3084-bug | `e70e24ef0c102c8eaf249c86102d05797b905073caaa0f7ca23c1c6511567564` | `63b4923935107db33d630b822026399d5bc68a890885d658abccf968f5a7ddb6` |
| click-3084-fixed | `24a048dedcac62b72c9e9221b6cd288538e30d07b30c2f15ec7b5ba4f63b921d` | `964163f0be72b2f29ee27ce64b63a02238619e12f9e834d458714721fa967742` |
| click-1921-bug | `9a801e34952cdf05070c1e116fc2c9613647c82ea69db03a6d449a865de8645c` | `f98d15a00284880d8796fd112d269708bb83c5542d0e7d07486d96a7cf2bd983` |
| click-1921-fixed | `76f5b9f619cf4191ed5ab5c4c1f38ac499af13efd398186bf2eb1f7b5c88467d` | `02266283bb0683d830c892abb49ec605ae40816770f9c31bedce693acaa4900b` |
| requests-6628-bug | `742c6ef12db73d6e77c725fd3b23fcec40f39d5c5d5e984a7d889d43ab50d7d2` | `1d4f44fcf85af62c9dae49bc341302a7c250059b64a1be6af13cabd5026519a1` |
| requests-6628-fixed | `7605f805d5d09df09a5bf7c7cbe5618f3aa96cb21d1326e9ebadaa41dd6e5fe3` | `4589407244e02c23b8c712e9ecb0a7a0db82db5116cfd0f3d475a79402c2781d` |
| requests-7432-bug | `40d2d38ce3ad8a7a88e0958936a4ea3d2ea6790e7954ff8ea2287d45b4f3709f` | `3a4380701551891357f55c69a6fdde2559de7006c55c0c22e26e802f6dbdce75` |
| requests-7432-fixed | `33ad6f01de9b07e105b279ed6d814016608cbbde24b741705774495ade202356` | `48fc7edd5421048cdd367c4630d5791ccae6187db30ae0aea783e72b5876b141` |
| click-control-intrange-clamp | `885e7fe0b355c105a7ccc475e06e2963741799c2d6ccea87efe4d07014468d81` | `3240063ab2964602c67d3f76c1415050a833a72697fa3d2fff4d195b88099b71` |
| requests-control-httpbasicauth | `67e4af7e6639dea2943f006ec8548a17350c062cff5ac79c9fc1adf6d5453380` | `63a71dcc9636ee976697a01df5173826fb0e4008ff4986e7513a48980afc07a5` |

## Limits and next gate

This is an offline static-scanner regression, not a DeepSeek quality evaluation. It establishes no model correctness or recall claim. The subsequent M06 live smoke made one request from an incorrect Requests checkout and returned a connection error with no valid response or usage data; billing is unknown and no retry was made. M07 remains blocked. See the [live smoke record](2026-09-25-live-smoke.md) for the full request audit and future gate.
