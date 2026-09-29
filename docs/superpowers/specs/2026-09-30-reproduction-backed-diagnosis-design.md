# Reproduction-backed diagnosis design

Date: 2026-09-30. Approved for autonomous execution by the user's instruction
to design, implement, repair, and verify the next product gap while keeping the
project lean.

## Problem and evidence

`verify` currently needs an issue ID, so a user cannot record a failing check
before asking the model to investigate. The blind M1 and same-context Pro
screens each found 0/3 known defects and accepted a false alarm on repaired
code. An earlier symptom-guided study found all four known defects in its one
complete repeat but also accepted false alarms on fixed snapshots. A free-text
symptom flag would not address the mismatch between an old observation and
the current source.

## Choice

Add one explicit, case-level reproduction command and one opt-in diagnosis
selector. Reuse the existing bounded `run_verification` subprocess runner.
This is smaller than a general test-management subsystem and gives the user a
concrete failing observation before any AI issue exists. A free-text symptom
field and automatic test execution are outside this change. No model-quality
claim follows from completing this workflow.

## User flow and stored data

```text
report create REPO --out CASE
reproduce CASE -- python -m pytest -q tests/test_specific.py
diagnose REPO SYMBOL --case CASE --reproduction R-001 --preview
diagnose REPO SYMBOL --case CASE --reproduction R-001 --expect-request-sha256 HASH
issue CASE A-001                  # if the model proposes a finding
verify CASE A-001 --phase after -- SAME_COMMAND
```

`reproduce` runs only the argv after `--` in the case repository, with the
existing minimal environment, 1–300 second timeout, 16-KiB captured output,
and no shell. It never runs during `report`, `context`, or `diagnose`. It saves
`R-001`, then `R-002`, etc. in an optional `reproductions` array on the current
case schema v1. Each record has the verifier result plus source fingerprints
before and after the command. Return 0 for a passing command, 1 for a failed
or timed-out command, and 2 for invalid input. Even a passing run is saved, so
it can supersede an older failure. Existing case files without this array
remain readable.

`diagnose --reproduction ID` requires `--case`. The selected run must be the
latest for its exact argv, have status `failed`, have unchanged Python source
during execution, and match the current Python source fingerprint. A timeout,
command error, pass, stale run, or missing ID stops before any provider call.
The diagnosis path performs the same fingerprint check after a provider
response before accepting findings. Changes outside scanned Python files are
not detected; the report states this limit.

Without `--reproduction`, prompt bytes, request hashes, records, and behavior
remain unchanged even if the case has saved reproductions. With it, the user
payload includes the run ID, timestamp, argv, exit code, captured output, and
truncation flag. The system prompt labels these as an untrusted observation,
asks for a source-backed connection, and permits an empty result. The normal
256-KiB request limit still applies. The exact preview shows the additional
output and gets its own SHA-256. Live reproduction-backed diagnosis requires
`--expect-request-sha256` from that preview. No Key or raw provider response
is saved. The command output is stored locally and may contain secrets, so
CLI help and README instruct the user to inspect preview before upload.

Previews, diagnosis attempts, and AI issues save an optional
`reproduction_id`. When an AI issue is created from that run, its verification
history also gets a compact `before` record referencing the same reproduction
ID, argv, status, timestamps, and source fingerprints; it does not duplicate
the captured output. The existing explicit `verify ... --phase after --
SAME_COMMAND` and human `--related-test` confirmation can then complete the
same-command repair check. The report labels the run as an observed command
outcome and each AI finding as an unverified hypothesis. This linkage is
provenance, not a claim that the failing command proves a particular issue.

## Acceptance

- A controlled Python fixture can record failure before an issue exists,
  preview the exact opt-in request, send it through a test transport, and keep
  reproduction → diagnosis → issue linkage after reopening the case. After a
  source fix, the same explicit regression command and human confirmation
  produce the existing repair-evidence state.
- A later passing run of the same argv, source edit, in-run source mutation,
  timeout, and missing preview hash all prevent upload.
- The pre-change blind request fixture keeps SHA-256
  `2d1d7ca4b298c17d511d01dc6e70e8bad41d7120cbec1844540959862bf3fd12`.
- Focused tests, full project suite, clean wheel install, controlled CLI demo,
  and supported-Python CI pass. No external target repository code is run for
  this feature's acceptance.

This proves the workflow and safety gates, not model precision or recall. A
fresh paired bug/fixed evaluation would be needed before claiming diagnostic
quality improvement.
