# Execution Status

Updated 2026-09-30. The current public product is
[v0.3.0](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.3.0),
merged in [PR #23](https://github.com/kisara174/ai-repo-doctor/pull/23) at
`479c616`. It retains the v0.2.0 persistent Python repository case, symbol
search, bounded optional DeepSeek diagnosis, source-grounded issues, human
review, and explicit before/after regression records. It adds source-backed
static review leads, architecture and impact summaries, and explicit disabled
thinking in the default `chat-json` request. The final merge commit passed
Python 3.11–3.13 CI; 373 local tests passed on the release branch. The wheel
was rebuilt from the merge commit, installed in a clean environment, and
downloaded again from the public release with matching SHA-256
`91025e1462828e280f10aa71924f869fc435761ad1ddfe2be88abdabd6e7f22b`.
The [product guide](PRODUCT_GUIDE.md) tracks the completed P0 workflow and
the remaining diagnosis-quality gap. The older dated reports below preserve
evaluation history.

The v0.4.0 release candidate adds an opt-in, case-level `reproduce` command
before AI issues exist. Only a latest failed command with complete captured
output and matching Python source fingerprint may enter a previewed diagnosis
request; the ordinary blind request bytes are unchanged. A resulting AI issue
links that failure as its compact before-check, so the existing explicit same
command after-check and human confirmation can complete a repair record. This
is a workflow improvement, not evidence that model precision improved.
Before publication, 383 offline tests and `compileall` passed. A `0.4.0`
wheel installed outside the source tree and completed a controlled case:
`R-002` recorded a failed assertion, one explicit preview-locked Flash request
(SHA-256 `dafbc91387fcfe1703ad4bd787d61937a3227754b89fa70994ed9db7dbe8898e`)
returned one quote-backed issue, the same command passed after a source edit,
and human test-link confirmation made the report show repair evidence. A
separate offline check rejected that reproduction after the source changed.
The wheel built for this pre-merge check had SHA-256
`e3fb41b3d296cfec0e6bdde102117b00bb58974acf37760ee23bda4109e5e106`;
the final release wheel must be rebuilt from the merge commit. This one
controlled call checks integration, not general diagnosis quality.

PR [#20](https://github.com/kisara174/ai-repo-doctor/pull/20) merged the first
M1 changes into the default branch at `2ab4e15`; no new release tag was made.
It added a fresh six-case M1 repair cohort, made the CLI `chat-json` request
explicitly disable thinking, and gave newly created reports ordered
source-backed review entries for parse failures, import cycles, and cross-file
shared call targets.
The frozen cohort stopped after its first call returned a truncated response;
five cases were not attempted, so M1 diagnosis quality has not passed. A
separate small, preview-locked CLI call completed and saved one
quotation-verified issue. See the
[M1 holdout record](evaluations/2026-09-29-m1-holdout.md).
The new static entries passed 372 local offline tests, `compileall`, and diff
checks. A wheel built from the branch installed in a clean Python 3.14 virtual
environment outside the source tree. Its CLI created and reopened a report for
this 56-file repository; the five cross-file entries pointed to concrete
callers of source reading, diagnosis prompts, request serialization, context
budgeting, and indexing. The target repository was not executed. The wheel
still carries project version `0.2.0`; this branch is not the public tag.
All Python 3.11–3.13 push and pull-request CI jobs for PR #20 passed.

PR [#21](https://github.com/kisara174/ai-repo-doctor/pull/21) merged the M1
static architecture summary into the default branch at `5a327cb`.
It uses resolved local production-code import/call edges, excludes detected
test files from module ranking, and shows source-line evidence for each direct
or indirect impact hop. The branch passed 373 offline tests, `compileall`,
diff checks, and Python 3.11–3.13 pull-request CI. PyPI TLS
errors interrupted the ordinary isolated wheel build twice, so a bundled
Python 3.12 runtime with setuptools 84 built the wheel offline without
installing or changing project dependencies. The wheel installed in a clean
Python 3.14 virtual environment outside the source tree. The installed CLI
`report create --symbol` and `report show` produced byte-identical saved and
reopened reports for this repository: 30 production modules, five focus
modules, and 6 direct plus 17 indirect static paths for `read_source`, each
with one source edge per hop. The target repository was not executed.

**Earlier integrated evaluation checkpoint:** `codex/repo-doctor-v1` at `70047c3`
([PR #16](https://github.com/kisara174/ai-repo-doctor/pull/16)).
The stability branch was merged in
[PR #8](https://github.com/kisara174/ai-repo-doctor/pull/8) at `5d72890`,
and the separate Flask holdout was merged in
[PR #9](https://github.com/kisara174/ai-repo-doctor/pull/9) at `dbd8a1c`.
The method-owner context change was merged in
[PR #10](https://github.com/kisara174/ai-repo-doctor/pull/10) at `74da767`.
The Werkzeug holdout was merged in
[PR #11](https://github.com/kisara174/ai-repo-doctor/pull/11) at `2f7cc48`.
The quotation-only finding label was merged in
[PR #12](https://github.com/kisara174/ai-repo-doctor/pull/12) at `8d591bf`.
The explicit supplementary context change was merged in
[PR #13](https://github.com/kisara174/ai-repo-doctor/pull/13) at `94a886a`.
The paired explicit-context evaluation was merged in
[PR #14](https://github.com/kisara174/ai-repo-doctor/pull/14) at `9e1f996`.
The provider-readiness documentation was merged in
[PR #15](https://github.com/kisara174/ai-repo-doctor/pull/15) at `56535f0`.
The Click explicit-context comparison was merged in
[PR #16](https://github.com/kisara174/ai-repo-doctor/pull/16) at `70047c3`.
The experimental prompt was reverted before PR #9 merged. PR #14 added
manifest-declared explicit source selection to offline evaluation preparation
and run preflight, and recorded a partial paired attempt. The
[offline coverage check](evaluations/2026-09-29-explicit-context-coverage.md)
preserves default request bytes; the
[paired evaluation report](evaluations/2026-09-29-paired-explicit-context.md)
records one connection failure and seven unattempted cases without a quality
claim. A later local transport check found the Python 3.14 CA bundle missing;
the standard Python certificate installation restored `doctor --deepseek`
readiness without weakening TLS verification.
A fresh Click explicit-context comparison then completed all eight calls; its
[source-reviewed result](evaluations/2026-09-29-click-explicit-context.md)
did not meet the preregistered usefulness signal.
The prior evaluation branch
was integrated at `86d1022`; its context implementation commit was
`6791483f9045487285e72aebad2eee7134ce4424`. Focused context
coverage was committed at `0ad91c8a456941dda8e7c0f6ebba351d038b6e61`.
Wheel installation instructions and CI acceptance were committed at
`05b5bc94af2d5fd999740892db8021f19dbb4248`. Those changes were reviewed
in [PR #7](https://github.com/kisara174/ai-repo-doctor/pull/7). The original `codex/repo-doctor-v2-design`
checkout has separate untracked V3 documents and was left untouched.

## Delivered capabilities

| Stage | Available now | Evidence and limit |
| --- | --- | --- |
| V1 | Read-only Python repository scan; symbol, import, and static call index; bounded `context`; reverse `impact`; evidence `validate`. | Static relationships are conservative and do not execute target code. |
| V2 | Decorator and overload metadata, explicit local reexports, bounded Click command-registration relationships, and richer static call resolution. | `call_edges` and `semantic_edges` remain distinct. Dynamic dispatch is outside the current precision claim. |
| V3 | Optional, explicit `diagnose` call to DeepSeek with bounded selected source; local finding evidence checks and safe error handling. | Source quotations can be validated without proving the model's behavioral conclusion. No automatic patching. |
| V0.2 product loop | Persistent `case.json` and `report.md`, symbol search, stable static and AI issue IDs, optional case-linked preview and diagnosis, human review, explicit bounded regression verification, and a bundled offline demo. | A repair-evidence claim requires the same command failing before and passing after a Python source change, stable source during each run, and human confirmation. `verify` is not an OS sandbox. |
| Evaluation | Frozen ten-case diagnosis manifest, separate Flask and Werkzeug holdouts, a fresh Click explicit-context comparison, offline preparation, one-case and full-plan runners, manifest-bound supplementary symbols, manual-review template, scoring, reproducible hashes, and offline CI workflow. | The Werkzeug paired attempt stopped at a connection failure. The Click comparison completed 8/8 calls but matched no known bug and produced four false positives on primary review. |
| Latest context change | Local class ancestor definitions and used module import bindings may join the selected source blocks within the same line budget. | Focused fixture covers ancestry order, relevant imports, and the shared budget; PR #8 passed the full offline suite and CI. |
| Method-owner context | A method target can include its enclosing class declaration as a separate bounded block. | Pinned offline comparisons preserve target lines and existing imports; PR #10 passed local and CI gates. |
| Finding presentation | Text output calls citation-checked findings `QUOTE-VERIFIED`; the JSON `accepted` key remains stable. | Exact source quotation matching does not establish a true bug; manual review remains required. |
| Explicit context | `context` and `diagnose` can add user-selected symbols inside the same source budget. | Opt-in selection can expose omitted local code; it does not infer a relationship or prove a model diagnosis. |
| Distribution | The public `0.2.0` tag and attached wheel install `repo-doctor` in a clean virtual environment. | Installed demo creation, task report, request preview, explicit before/after verification, and final report were checked outside the source tree. The evaluation-only `tools` package remains outside the wheel. |

The original post-V3 plan's T0–T6 implementation and T7 offline preparation
were completed. T7's first ten-case online run stopped after one
`provider_error`; nine calls were unattempted. T8 accurately reported that
partial run. Its frozen manifest SHA-256 remains
`f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
The [original report](evaluations/2026-09-25-diagnosis-v1.md) remains the
record of that run.

## Model-quality evidence so far

- The old-context, disabled-thinking `requests-6628-bug` request returned two
  locally accepted findings. Primary source review marked one uncertain and
  one false positive; neither identified the known missing `__reduce__`
  dispatch. See [single-case report](evaluations/2026-09-27-thinking-disabled-smoke.md).
- The paired old-context fixed and HTTP Basic Auth control requests returned
  three accepted findings in total, all false positives on primary review.
  The control's `basestring` claim appeared when its import binding was
  missing from the supplied context.
  See [paired report](evaluations/2026-09-27-paired-control.md).
- Under expanded context at `6791483`, the bug request returned
  `invalid_content_json` with no usable finding; the fixed request returned
  two false positives on primary review; the control returned zero findings.
  The import line was present in the control context. See
  [expanded-context report](evaluations/2026-09-28-context-expansion.md).
- A new plan under `05b5bc9` reproduced the three audited payloads exactly.
  Its one permitted bug call stopped with `provider_error/connection` before
  model content arrived. The full ten-case run was not started. See
  [quality-gate report](evaluations/2026-09-28-quality-gate.md).
- At analyzer commit `091dc2d`, the opt-in Responses JSON Schema evaluator
  completed a frozen ten-case run. Primary review found one match among four
  known bug cases, seven accepted false positives, six uncertain findings,
  and one rejected false positive. The corrected fixed/control false-alarm
  count is 3/6. See the
  [ten-case baseline](evaluations/2026-09-28-schema-ten-case-baseline.md).
- At analyzer commit `14da7b4`, a new pinned Flask six-case baseline completed
  6/6 calls. Primary review found no match among three known bug cases, six
  accepted false positives, two uncertain findings, and false alarms on all
  three fixed cases. A preregistered prompt variant at `c206da6` stopped
  after its first call returned `invalid_content_json`; five calls were not
  attempted. The prompt was reverted at `d66ec4c`. See the
  [Flask holdout report](evaluations/2026-09-28-flask-holdout.md).
- At analyzer commit `a9155de`, the pinned Werkzeug six-case baseline
  completed 6/6 calls. Primary review found one match among three known bug
  cases, four accepted false positives, three uncertain findings, and fixed
  case false alarms in two of three repaired snapshots. All eight findings
  passed quotation grounding. The preregistered quality gate failed; see the
  [Werkzeug holdout report](evaluations/2026-09-29-werkzeug-holdout.md).
- The paired explicit-context cohort froze eight cases and exact request
  hashes at analyzer commit `eab4708`. One request ended with a safe
  `connection` error; seven were not attempted. No model response arrived,
  so the run provides no quality comparison. See the
  [partial run report](evaluations/2026-09-29-paired-explicit-context.md).
- At analyzer commit `1f2db12`, a fresh Click explicit-context cohort
  completed all 8/8 calls. Primary review matched neither of two known
  repairs in either arm. All four citation-checked findings were false
  positives; two were on fixed-arm cases. The preregistered signal failed.
  See the [Click comparison](evaluations/2026-09-29-click-explicit-context.md).

The earlier exploratory calls used one selected case at a time and cannot be
scored as dataset coverage. The original Chat ten-case run remains partial
and unchanged; the new JSON Schema ten-case run is complete and has a primary
review, but no independent second review. The Flask and Werkzeug baselines
also have only primary review and are too small to estimate general model
quality. The completed Click comparison remains too small and correlated to
estimate general model quality. Model token usage is recorded where available;
actual billing is not inferred.

## Current next gate

Keep the v0.3.0 human-reviewed workflow stable. The separately registered
[M1 v2 evaluation](evaluations/2026-09-29-m1-holdout-v2.md) sent six pinned
requests with thinking explicitly disabled: five responses were parseable,
one was invalid JSON, source review found **0/3** known repairs, and one
parseable fixed snapshot had an accepted false alarm. The usefulness gate
failed, so the blind model path has no unattended-use quality claim. The
next product-quality task is a user-supplied symptom or reproduction entry
that keeps source quotation, human review, and a paired repaired-snapshot
false-alarm gate. Earlier symptom-guided experiments improved hit counts but
also had false alarms; no prompt change is promoted from those results alone.
The same-context [Pro candidate screen](evaluations/2026-09-30-m1-pro-screen.md)
returned 6/6 parseable responses but still found **0/3** known defects and
accepted one false alarm on a repaired snapshot. Its registered gate failed;
keep Flash as the released default and symptom guidance evaluation-only.
The opt-in reproduction-backed path does not change that quality judgment; a
fresh paired evaluation would be needed for an accuracy claim.

## Verification scope

- The context test module passed 12 tests at `0ad91c8`. The full offline suite
  passed 276 tests after that change; `compileall` and `git diff --check`
  passed. These checks ran before the documentation/CI-only `05b5bc9` commit.
- At `05b5bc9`, a wheel built successfully and installed with `pip --no-index`
  into a clean Python 3.14 virtual environment outside the source tree.
  Installed CLI help plus offline scan, context, impact, and validation passed.
- PR #7 head `05b5bc94af2d5fd999740892db8021f19dbb4248` passed all Python
  3.11, 3.12, and 3.13 jobs in both push and pull-request CI runs. Each job
  built and smoke-tested the installed wheel. See PR #7 for the CI result on
  its final integration head.
- PR #8 head `2ffd9fe093f1057631ed1d314307e88a5710b441` passed all Python
  3.11, 3.12, and 3.13 jobs in push and pull-request CI. Its local suite
  passed 313 tests; reviewer-found source-encoding mutation was fixed before
  integration.
- PR #9 head `d902aefa54c00c6325477363660783819140a946` passed all Python
  3.11, 3.12, and 3.13 jobs in push and pull-request CI. Its local suite
  passed 314 tests. The prompt variant stopped after one malformed-content
  response and was reverted before integration.
- The method-owner context branch passed 318 local offline tests, `compileall`,
  and `git diff --check` on 2026-09-29. Its two pinned offline sets retained
  all target-method lines and previously selected import bindings; see the
  [comparison](evaluations/2026-09-29-method-owner-context.md).
- PR #10 head `5d7fd59c61805e81323829bceb51a18010bcdf67` passed Python
  3.11, 3.12, and 3.13 in both push and pull-request CI before merging.
- The Werkzeug dataset-ID focused test and all 26 diagnosis-data tests passed
  after the exact allowlist extension. Six clean target checkouts, source
  fingerprints, context budgets, and serialized request hashes were checked
  before the online run. The Werkzeug branch passed 319 local offline tests
  and `compileall` on 2026-09-29.
- PR #11 head `88ef9ec75be2645b4e767c456c1a4c6a65211ce3` passed Python
  3.11, 3.12, and 3.13 in both push and pull-request CI before merging.
- The text-label branch first failed then passed its two focused CLI
  output tests. Its JSON compatibility is covered by the existing CLI test.
  All 321 local offline tests, `compileall`, and `git diff --check` passed on
  2026-09-29.
- PR #12 head `6758416e446b6e05b85685ec1860ce5360a2a7c8` passed Python
  3.11, 3.12, and 3.13 in push and pull-request CI before merging.
- The explicit-context branch passed 326 local offline tests, `compileall`,
  and staged diff checks. Its six default Werkzeug case records and context
  files matched the prior frozen plan byte for byte. The source-selection
  comparison and its limits are in the
  [offline coverage check](evaluations/2026-09-29-explicit-context-coverage.md).
- Manifest-declared `include_symbols` support passed the full 332-test
  offline suite, `compileall`, and diff checks. The eight case contexts and
  serialized request hashes were rebuilt before dispatch. Re-preparing the
  prior six-case Werkzeug default plan produced byte-identical context files
  and unchanged request hashes; only analyzer-commit metadata changed.
  Target checkouts remained clean; no target code or tests were run.
- PR #14 head `257f050ff07223247062b506dd73742005d3290e` passed Python
  3.11, 3.12, and 3.13 in pull-request CI before merging. Local 332-test,
  `compileall`, and diff checks passed on the final code tree.
- The Click cohort's four pinned checkouts, eight source fingerprints, context
  selections, and serialized request hashes were checked before dispatch.
  The exact dataset-ID data module passed 31 tests; the full offline suite
  passed 333 tests after the report, along with `compileall` and diff checks.
  The provider run completed 8/8 calls and all four findings received primary
  source review. No Click target code or tests were run.
- PR #16 head `5028353428b0d3f0d37471bc002a3eb4a335b13e` passed Python
  3.11, 3.12, and 3.13 in push and pull-request CI before merging.
- Pinned target repository code, tests, and dependencies were not executed or
  installed during these diagnosis experiments. The API key and raw provider
  response bodies were not saved in the evaluation artifacts.

## Earlier stability gates

The stability sequence completed these P0 and P1 gates:

- `doctor` now checks local readiness by default and optional DeepSeek model
  access only when requested (`7239c4c`, `3900bac`).
- An opt-in Responses JSON Schema diagnosis path was added after a controlled
  single-case comparison (`a11d526`, `b70e446`). See the
  [structured-output report](evaluations/2026-09-28-structured-output.md).
- `diagnose --preview` produces the exact request body without network or Key;
  `--expect-request-sha256` locks a later upload to those bytes. Selected
  source lines are checked before and after the provider call (`0eb8361`).
  The 303-test suite, `compileall`, CLI help, and diff check passed at that
  source state. A subsequent reviewer found the source-encoding edge case
  described above; no other actionable issue was reported.
- Two pinned real repositories produced byte-identical repeat scans with zero
  parse errors and clean worktrees. See the
  [scanner checkpoint](evaluations/2026-09-28-scanner-stability.md).
- The wheel built in an isolated environment and the installed CLI scanned
  and previewed outside the source tree. See the
  [installed CLI checkpoint](evaluations/2026-09-28-wheel-smoke.md).
- JSON Schema preparation, run dispatch, and scoring are implemented at
  `24736c0`, `9bcc18b`, and `091dc2d`. The scorer correction at `420495b`
  has a red/green regression test. The source-encoding regression also failed
  before its fix and passed after it; the full offline suite passed 313 tests,
  along with `compileall` and `git diff --check`. The
  ten-case provider run is pinned to the earlier clean analyzer commit
  `091dc2d`; the corrected score is a later offline derivation from unchanged
  run records and completed primary review.

The provider parser already separates incomplete, missing-content, and
invalid-JSON responses with safe error categories. The Werkzeug holdout
missed two known bugs and failed its preregistered usefulness gate. Explicit
selection supplies omitted local methods, but the fresh Click comparison
matched no known defect and added no demonstrated diagnostic benefit. The
local `doctor --deepseek` check reports `ready` after installing Python's
missing CA bundle. Keep cloud diagnosis experimental. The next quality change
needs a specific failure hypothesis and a new frozen, source-reviewed cohort;
do not reuse visible cases as unseen evidence or switch the default protocol.
Preserve all manifests and run records.

The earlier [post-V3 execution plan](superpowers/plans/2026-09-24-post-v3-execution.md),
[handoff audit](evaluations/2026-09-25-handoff-audit.md), and
[hardening report](evaluations/2026-09-25-hardening-offline.md) preserve the
implementation and offline evaluation history. Future agents should not
re-run completed T0–T8 steps to recreate this state.
