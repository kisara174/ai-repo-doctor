# Diagnosis preparation performance — 2026-09-25

## Measurement setup

- Analyzer: clean commit `24fb68ce67297c80d0c643e6b87802b2e6b009cb`.
- Dataset: `evaluation/diagnosis/manifest-v1.json`, 10 cases across 8 unique `(checkout_id, commit)` snapshots.
- Environment: Python 3.14.5, macOS 27.0 arm64.
- Method: called `prepare_cases(..., model="deepseek-flash", max_lines=120)` five times in one Python process. `time.perf_counter()` wrappers measured `_verified_checkout`, `_source_fingerprint`, `build_index`, `build_context`, and total wall time. No files were written and no API calls were made.
- Cache state: the M05 repository scans and plan preparation had already read these source trees. The first measurement therefore was not a cold-cache run; OS file-cache state was not cleared or otherwise controlled. Runs 2–5 followed immediately in the same process.

## Results

| Run | Checkout validation (s) | Source fingerprint (s) | `build_index` (s) | Context construction (s) | Total (s) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.2058 | 0.0022 | 5.1788 | 0.0034 | 5.4300 |
| 2 | 0.1779 | 0.0021 | 5.2097 | 0.0035 | 5.4314 |
| 3 | 0.1796 | 0.0021 | 5.2387 | 0.0035 | 5.4619 |
| 4 | 0.1782 | 0.0021 | 5.2432 | 0.0034 | 5.4652 |
| 5 | 0.1776 | 0.0021 | 5.2382 | 0.0035 | 5.4590 |
| Median | 0.1782 | 0.0021 | 5.2382 | 0.0035 | 5.4590 |

Call counts per run were: 8 checkout validations, 10 source fingerprints, 10 index builds, and 10 context builds. `build_index` accounted for about 96% of median total time. The manifest has two repeated snapshots, each used by two cases:

- `click-e24db5732f30` / `e24db5732f304278e37a3d39d3546429b69f545e`: `click-1921-fixed` and `click-control-intrange-clamp`.
- `requests-6404f345e562` / `6404f345e562d962abe6700a1c357ec1e7e18232`: `requests-7432-fixed` and `requests-control-httpbasicauth`.

`prepare_cases` validates each source fingerprint but currently builds the same checkout index once per case. The two repeated snapshots therefore cause two redundant index builds. Across these measurements, two builds correspond to about 1.05 seconds of observed work, or 19% of the median total. This is an estimate of avoidable work, not a promised speedup.

## Decision

A small, single-prepare index cache is worth a separate implementation task: reuse one `build_index` result per `(checkout_id, commit)` during one `prepare_cases` call. Keep it in memory for that call only; do not add disk or cross-process caching. The change must preserve every context SHA-256 and request SHA-256 in the M05 plan, source checks, call evidence, and output ordering. Re-measure on a clean commit before reporting any speedup.

This is a performance candidate only. No implementation or cache behavior changed in this measurement.
