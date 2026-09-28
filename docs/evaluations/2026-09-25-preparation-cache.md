# Diagnosis preparation cache follow-up — 2026-09-25

## Scope and correctness

This follow-up implements the single-invocation index reuse candidate selected from M08's measurements. On clean analyzer commit `ad07876172ea5af6e995cd7ac1765c97110dde17`, `prepare_cases` keeps an in-memory cache keyed by `(checkout_id, commit)`. It still verifies each checkout, checks each case's source fingerprint, and builds a fresh context and request hash for every case. No disk or cross-call cache was added, and no API request was made.

The optimized prepare was run against the same ten-case frozen manifest and pinned checkouts as M05. Compared with `.local/diagnosis/hardening-offline-2667ff0/diagnosis-plan`:

- All ten plan case records matched exactly, including case order, source line/byte counts, context hashes, and request hashes.
- All ten decoded context objects matched exactly.
- The instrumented preparation still ran eight checkout validations, ten source fingerprints, and ten context builds per run; index builds fell from ten to eight.
- The generated plan is retained at `.local/diagnosis/cache-validation-ad07876/diagnosis-plan/` (ignored local artifact).

The focused regression test was first run against the old implementation and failed as expected: two cases over two `prepare_cases` calls built four indexes instead of two. With the cache, it verifies two builds total, four source-fingerprint checks, and unchanged case/context ordering and symbols.

## Verification

- `python3 -m unittest tests.test_diagnosis_data -v`: 20 tests passed.
- `python3 -m unittest discover -s tests -v`: 256 tests passed.
- `python3 -m compileall -q repo_doctor tools tests`: passed.
- `python3 -m tools.evaluate_diagnosis --help` and `python3 -m repo_doctor diagnose --help`: passed.
- `git diff --check`: passed.

## Five-run timing comparison

Both measurements used Python 3.14.5 on macOS 27.0 arm64, the same ten cases and eight unique snapshots, one Python process, and `time.perf_counter()` wrappers around checkout validation, source fingerprinting, `build_index`, context construction, and total `prepare_cases` wall time. File-cache state was not cleared or controlled; these are local observations, not a cross-machine benchmark.

| Run | Index builds | Checkout validation (s) | Fingerprints (s) | `build_index` (s) | Context construction (s) | Total (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Before 1 | 10 | 0.2058 | 0.0022 | 5.1788 | 0.0034 | 5.4300 |
| Before 2 | 10 | 0.1779 | 0.0021 | 5.2097 | 0.0035 | 5.4314 |
| Before 3 | 10 | 0.1796 | 0.0021 | 5.2387 | 0.0035 | 5.4619 |
| Before 4 | 10 | 0.1782 | 0.0021 | 5.2432 | 0.0034 | 5.4652 |
| Before 5 | 10 | 0.1776 | 0.0021 | 5.2382 | 0.0035 | 5.4590 |
| After 1 | 8 | 0.1746 | 0.0023 | 4.1901 | 0.0032 | 4.4076 |
| After 2 | 8 | 0.1746 | 0.0023 | 4.2346 | 0.0033 | 4.4514 |
| After 3 | 8 | 0.1771 | 0.0024 | 4.2411 | 0.0032 | 4.4604 |
| After 4 | 8 | 0.1770 | 0.0023 | 4.2497 | 0.0032 | 4.4695 |
| After 5 | 8 | 0.1759 | 0.0024 | 4.2565 | 0.0033 | 4.4757 |
| Median before | 10 | 0.1782 | 0.0021 | 5.2382 | 0.0035 | 5.4590 |
| Median after | 8 | 0.1759 | 0.0023 | 4.2411 | 0.0032 | 4.4604 |

The observed median total fell by 0.9986 seconds (~18.3%); median index-building time fell by 0.9971 seconds (~19.0%). The build count dropped by the two repeated snapshots identified in M08. Timing variation, filesystem caching, and this single machine limit the conclusion; the stable context/request hashes establish behavior preservation, while these timings do not promise the same speedup elsewhere.

## Reproduction command

From a clean checkout at `ad07876172ea5af6e995cd7ac1765c97110dde17`:

```sh
python3 -m tools.evaluate_diagnosis prepare \
  --manifest evaluation/diagnosis/manifest-v1.json \
  --repos-root /tmp/ai-repo-doctor-diagnosis-checkouts \
  --model deepseek-flash \
  --max-lines 120 \
  --out-dir .local/diagnosis/cache-validation-ad07876/diagnosis-plan
```

The before timings are recorded in `docs/evaluations/2026-09-25-preparation-performance.md`; this report adds the after run and the hash-equivalence check.
