# Explicit supplementary context: offline coverage check

Date: 2026-09-29. Analyzer commit:
`56ffb6c102a3faa8ff921ac0e953ce6a4359f997`. This checks source selection
and request bytes only. It makes no claim about model defect detection.

## Change and safety boundary

`context` and `diagnose` now accept repeatable `--include-symbol` values. The
target and its enclosing class declaration are selected first, followed by
user-selected symbols, then existing graph neighbors and import bindings.
Every block shares the original physical-line budget. Selecting an already
abbreviated owner class expands it to its full source. Unknown or ambiguous
symbols are rejected by the existing index lookup. The user must inspect the
selected source and exact `diagnose --preview` request before upload; the
existing source-byte and wire-byte limits and expected SHA-256 guard remain.
`user_selected` labels the block's origin, not a proven relationship.

## Default-path invariance

Using the unchanged six-case
[Werkzeug manifest](../../evaluation/diagnosis/werkzeug-holdout-v1.json)
(SHA-256 `09c42643a0e21f5468882c562c7326c2f731c9f0d3c3e9b00cec9bf3fe0d7bda`),
offline preparation at this commit completed 6/6 clean pinned checkouts. Each
new case record and selected context file was byte-identical to the frozen
`werkzeug-plan-20260929` plan. The metadata also matched except for the new
analyzer commit. Consequently all six default context and serialized request
SHA-256 values are unchanged. The new ignored plan is
`.local/diagnosis/explicit-context-default-20260929/plan.json` (file SHA-256
`abac1a0096dae631d458385d9e77035f4cd3dac2d484b251ed1fed602efa160a`).

## Visible-case coverage probe

The [prior holdout](2026-09-29-werkzeug-holdout.md) missed
[Werkzeug #2985](https://github.com/pallets/werkzeug/issues/2985): the
selected `Headers.__str__` context omitted the `EnvironHeaders` subclass
that exposes headers from a WSGI environment. An offline `diagnose --preview`
with `--response-format json-schema` and explicit
`--include-symbol src/werkzeug/datastructures/headers.py::EnvironHeaders`
gave these results, with no API request:

| Snapshot | Default source lines | Explicit source lines | Explicit request bytes | Explicit request SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `werkzeug-2985-bug` | 9 | 66 | 9,059 | `c2cee25e97cc9f041558844b1ce1df25670bc0577044b74cfa11780ff6621374` |
| `werkzeug-2985-fixed` | 15 | 72 | 9,935 | `5b85730326de7706a7e9c81c6e159f8de5e93da85045a89fcd18161750f5ea6f` |

Both previews included the complete subclass span at
`headers.py:599-652`, including `EnvironHeaders.__iter__`, with no truncated
block. The extra source stayed within all upload limits. This case was
already visible before the change, so an online rerun would be development
feedback rather than unseen quality evidence. No model call was made.

## Verification and next gate

The five new behavior tests were run red then green; an existing source-change
test was updated to forward the new optional keyword through its test double.
The full offline suite passed 326 tests, followed by `compileall` and staged
diff checks. The next quality gate is a separately preregistered, source-vetted
bug/fixed cohort that has not been sent to the model. Compare default and
explicit-context arms on identical snapshots, review claims against source,
and report false alarms as well as known-defect detection. A second reviewer
is still needed before any broader accuracy claim.
