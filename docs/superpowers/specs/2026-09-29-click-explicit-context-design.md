# Click explicit-context paired evaluation design

Date: 2026-09-29. This is a fresh, source-backed comparison of the opt-in
`include_symbols` workflow after the Werkzeug paired attempt stopped at a
local transport error. It tests whether supplying a dynamically dispatched
`Choice` method helps diagnosis of two known Click behaviors while avoiding
new alarms on the matching repairs. It does not estimate general accuracy.

## Cohort and source evidence

Use two previously unsent Click repairs from the official repository. Each
bug snapshot is the repair commit's first parent. The public target method
is byte-identical within its pair; the repair changes the short `Choice`
method reached through `self.type`. Four detached checkouts have been inspected
at their exact HEADs and are clean. Only static source and upstream tests were
read; no target code, tests, or dependencies were executed.

| Repair | Bug commit | Fixed commit | Target | Explicit extra |
| --- | --- | --- | --- | --- |
| [Case-insensitive completion, PR #1693](https://github.com/pallets/click/pull/1693) | `acc91bc4f47e38f43277fcdfd8ca855734c4fbbc` | `5eb46cba463ff3e3894b58f6649c5a13f02a70b1` | `src/click/core.py::Parameter.shell_complete` | `src/click/types.py::Choice.shell_complete` |
| [Choice metavar, PR #2365](https://github.com/pallets/click/pull/2365) | `02046e7a19480f85fff7e4577486518abe47e401` | `1a4d8c1bb1e8f8e214ede7223bd2c05dc2ce006a` | `src/click/core.py::Parameter.make_metavar` | `src/click/types.py::Choice.get_metavar` |

For PR #1693, `Choice(["Au", "al", "Bc"], case_sensitive=False)` completing
`"a"` should offer both `"Au"` and `"al"`; the old `startswith` check offered
only `"al"`. The repair respects `case_sensitive`, while `True` still matches
only `"al"`. For PR #2365, an option with `Choice(["foo", "bar"])` and
`show_choices=False` should display a type metavar such as `[TEXT]` rather
than expose `[foo|bar]`. The repair changes `Choice.get_metavar`; the target
`Parameter.make_metavar` remains unchanged. Fixed snapshots are negative only
for these narrow contracts.

The target source fingerprints are stable within each pair:

| Target | Span in both snapshots | SHA-256 |
| --- | --- | --- |
| `Parameter.shell_complete` | `src/click/core.py:2110-2131` | `c3937a7463013df7ab8b6b7fcc5c3fb590eb9f23926f0e1cfa0a3c220380bb39` |
| `Parameter.make_metavar` | `src/click/core.py:2127-2139` | `26e38d9433092fed60b56c64e96368058e634389aff7cab69dba19abfa4a4947` |

An offline selection probe with 120 lines found no changed `Choice` method in
the default arm. The explicit arm included each method in full, without
truncation. The largest selected context was 43 lines. The default context
for each bug/fixed pair should have identical request bytes, because its
target and selected source are unchanged; the explicit arm should expose the
repair difference. Confirm these exact request hashes during preparation.

## Evaluator contract and protocol

Add only the dataset ID `diagnosis-click-explicit-context-v1` to the existing
manifest allowlist. Reuse the current optional `include_symbols` manifest field,
offline preparation, runner preflight, JSON Schema Responses request, manual
review template, and scorer. Do not change product context selection, prompts,
response parsing, scoring, or the prior frozen datasets.

Freeze eight cases in this order for each repair: bug/default, bug/explicit,
fixed/default, fixed/explicit. Default rows omit `include_symbols`; explicit
rows contain exactly the corresponding method above. Use a separate pair ID
for each arm, with one bug and one fixed case. Record exact commit, checkout
name, target span/hash, narrow ground truth, primary source references, and
review annotation. The model receives only selected context: no case ID, arm,
label, issue, ground truth, or fix reference. The extra block's
`user_selected` relation states selection, not defect status.

Use `deepseek-flash`, Responses `json_schema`, no thinking field, 120 selected
source lines, 64 KiB selected source, 256 KiB request body, and 4,096 output
tokens. Require a fresh source-free `doctor --deepseek --model deepseek-flash`
status of `ready` before dispatch. Prepare the manifest and all eight exact
request hashes under one clean analyzer commit; independently rebuild hashes
and verify four clean pinned checkouts. Make one request per case, sequentially,
with `--repeats 1 --max-calls 8 --allow-network`; do not retry. Stop on any
provider or provenance error and retain partial records. Do not store the Key
or raw provider response bodies.

Review every accepted finding against the pinned source and upstream repair.
Mark TP, FP, uncertain, or duplicate; quotation grounding alone is not a
behavioral judgment. The preregistered narrow usefulness signal requires all
eight parseable calls, at least one bug identified only in its explicit arm,
and no additional explicit-arm false alarm on either fixed snapshot. If this
fails, report why without tuning on the now-visible cohort or changing the
product default. Even a positive result remains exploratory: two purposive,
historical repairs from one library, one model sample per arm, and primary
review only.
