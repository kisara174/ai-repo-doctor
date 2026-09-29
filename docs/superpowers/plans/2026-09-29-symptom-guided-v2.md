# Symptom-Guided Diagnosis Evaluation V2 Plan

**Goal:** Compare the existing blind diagnosis prompt with the already-built
symptom-guided evaluation prompt on four new, source-reviewed Python repairs.

**Design:** [Symptom-Guided Diagnosis Evaluation V2](../specs/2026-09-29-symptom-guided-v2-design.md).
The user approved proceeding with the four-repair, 32-call cohort and waived
a separate review checkpoint. The primary agent owns source selection,
implementation, online dispatch, manual review, and acceptance.

## Constraints

- Work in the current isolated worktree on `codex/click-eval-closeout`; do not
  modify the primary checkout.
- Preserve V1's exact eight-case contract and all prior dataset request hashes.
- Add a separate exact ID, `diagnosis-symptom-guided-v2`, with exactly 16
  cases, four unique repairs, and four unique repositories unused in previous
  diagnosis datasets.
- Each repair has one blind bug/fixed pair and one symptom-guided bug/fixed
  pair. Only the symptom pair contains the identical symptom text.
- Do not modify `repo_doctor` product prompts, CLI behavior, findings schema,
  evidence validation, or the DeepSeek transport.
- Use `deepseek-flash`, JSON Schema Responses, reasoning `none`, 120 lines,
  64 KiB context, 256 KiB request, 4,096 output tokens, two repeats, and a
  maximum of 32 sequential calls. Do not retry. Stop on the first provider or
  provenance failure and retain the partial run.
- Do not send labels, case IDs, issue or PR IDs, commits, test names, ground
  truth, absolute paths, or review annotations to the model.
- Do not execute upstream code or tests and do not install target dependencies.
- Never print, store, or pass the API key as an argument. Require DeepSeek
  readiness before any request.
- Keep prepared contexts, plan, run records, review, and scorer output in the
  ignored `.local/diagnosis/` tree. Track only source code, tests, the frozen
  manifest, this plan, the design, and the final redacted report.

## Files

| Path | Responsibility |
| --- | --- |
| `tools/diagnosis_data.py` | Add V2 ID and exact 16-case/four-repair/four-repository validation while leaving V1 validation intact. |
| `tools/diagnosis_score.py` | Reuse prompt-arm/per-repair scoring for V2 and compute the registered V2 signal. |
| `tests/test_diagnosis_data.py` | Test valid V2 structure, rejected reused repositories, and malformed pair/arm counts. |
| `tests/test_diagnosis_score.py` | Test four-repair summaries, exact registered-signal pass, and a failing signal case. |
| `evaluation/diagnosis/symptom-guided-v2.json` | Freeze 16 rows, source fingerprints, upstream references, and approved symptoms. |
| `docs/evaluations/2026-09-29-symptom-guided-v2.md` | Record run provenance, findings review, signal, costs, limitations, and next decision. |
| `.local/diagnosis/symptom-guided-v2-*` | Hold detached checkouts and ignored evaluation artifacts. |

No prompt, runner, or transport edit is planned: V1 already builds the
evaluation-only symptom prompt and rebuilds its request fingerprint during
preflight. If V2 preparation proves otherwise, stop and re-plan before
changing those components.

## Task 1: Extend validation with tests first

1. Add a synthetic V2 manifest fixture with four distinct repository URLs and
   issue IDs, 16 rows, and the required pair ordering.
2. Add tests that accept the exact valid structure; reject the wrong row or
   repair count; reject reuse of a repository from any earlier dataset; and
   reject an arm that loses a symptom or has mismatched pair symptoms.
3. Run the focused new tests and confirm they fail because V2 is not yet in
   the accepted dataset contract.
4. Add the V2 ID to the allowlist. Share the established arm/pair checks
   between V1 and V2 without changing V1's exact row and repair counts. Require
   V2 to have four repairs, four distinct repositories, and no repository URL
   used by an earlier diagnosis cohort.
5. Run `python3 -m unittest tests.test_diagnosis_data -v` and confirm both
   V1 and older manifests still validate.

## Task 2: Extend scoring with tests first

1. Build synthetic successful records and review rows for all 16 V2 cases over
   two repeats. Make the signal positive only when every registered condition
   holds, including all-repair symptom coverage, a higher symptom-arm bug-hit
   count, and no fixed-case false alarms.
2. Add tests for a positive synthetic signal and at least one negative
   mutation (a fixed false alarm or no arm-level detection improvement).
3. Run the focused new scorer tests and confirm they fail because V2 currently
   has no prompt-arm or registered-signal output.
4. Reuse `_score_prompt_arms` for V2 and add a V2-only `registered_signal`
   object to the report. Keep every previous dataset's report shape unchanged.
5. Run `python3 -m unittest tests.test_diagnosis_score -v`.

## Task 3: Freeze and audit the manifest

1. Create the four clean, detached bug/fixed checkout pairs under
   `.local/diagnosis/symptom-guided-v2-checkouts` using the full immutable
   commits in the design table.
2. For each target symbol, verify unique static symbol resolution, inspect
   only the targeted code and upstream regression assertion, choose a minimal
   1-based source span, and compute its exact SHA-256. Do not run target code,
   tests, or imports.
3. Add the 16 cases in fixed order. Include issue/PR or discussion links,
   precise behavior contracts, and the same symptom on both symptom-pair
   members. Do not include any issue, test, fix, or label in symptom text.
4. Run manifest-only validation, then offline preparation with 120 lines and
   the 256 KiB request cap. Confirm all contexts fit 64 KiB, each blind and
   symptom pair shares the exact context hash, and only symptom text changes
   the request hash within each snapshot.
5. Inspect the prepared user payloads for accidental labels, test names,
   issue/PR IDs, commits, absolute paths, or ground truth. Preserve the
   resulting plan and record manifest/plan hashes.

## Task 4: Verify locally and freeze before networking

1. Run `python3 -m unittest discover -v` on the current source tree.
2. Compare prior V1 manifest bytes and any saved V1 request fingerprints;
   confirm they are unchanged.
3. Run
   `python3 -m repo_doctor doctor --deepseek --model deepseek-flash --json .`.
   If the provider is unavailable or rejects the configured key, do not send
   any request; record readiness failure and finish the offline report.
4. Review the tracked diff, `git diff --check`, and ignored artifact boundary.
   Commit the code, tests, manifest, plan, and design before online dispatch.

## Task 5: Run the approved online comparison once

Run exactly:

```sh
python3 -m tools.evaluate_diagnosis run \
  --manifest evaluation/diagnosis/symptom-guided-v2.json \
  --repos-root .local/diagnosis/symptom-guided-v2-checkouts \
  --plan-dir .local/diagnosis/symptom-guided-v2-plan \
  --out-dir .local/diagnosis/symptom-guided-v2-run \
  --repeats 2 --max-calls 32 --allow-network
```

Do not dispatch if readiness or preflight fails. On the first attempted-call
failure, stop without retrying. Confirm attempted, completed, successful,
failed, unresolved, and not-attempted counts; returned model ID; usage totals;
and request hashes from safe metadata only.

## Task 6: Review, score, and report

1. Generate an offline review template with `prepare-review`.
2. Review every parsed finding against the exact source and behavior contract.
   A true positive must identify the paired behavior and be supported by the
   submitted source. A finding on a fixed snapshot is a false alarm only when
   it falsely claims that the paired symptom remains. Preserve uncertain and
   duplicate labels where appropriate.
3. Run the scorer offline. Verify the registered signal fields against the
   case-level review rows; report failure or partial status plainly.
4. Write a redacted report with the cohort, hashes, model IDs, parsed and
   failed call counts, per-arm and per-repair findings, token use, signal
   outcome, omitted provider sampling defaults, and limitations. Do not include
   keys or raw provider bodies.
5. Re-run targeted score/report checks and `git diff --check`; inspect the
   final diff and confirm no ignored run or secret material is tracked. Commit
   the report.
