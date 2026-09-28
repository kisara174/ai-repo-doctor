# Real-repository scanner stability checkpoint

Date: 2026-09-28. Analyzer commit: `0eb8361`. This is an offline, read-only
check of two manifest-pinned public Python checkouts. Target code and tests
were not executed.

For each checkout, the recorded `HEAD` matched the frozen diagnosis manifest
and `git status --porcelain --untracked-files=all` was empty before and after.
The command `python3 -m repo_doctor scan CHECKOUT --json` ran twice from the
analyzer checkout with a 60-second timeout per run. Each pair of raw stdout
bytes matched exactly; the scan selected Git file discovery and reported no
parse errors.

| Case | Python files | Output bytes | SHA-256 of raw stdout | Wall seconds (two runs) |
| --- | ---: | ---: | --- | --- |
| `click-3084-bug` (`7f7bbe4569ea`) | 62 | 2,094,340 | `30467406d4a4a48cc21f3918a7b7bac4713511d08c6584d5d1c7cf4efc5542c0` | 0.886, 0.888 |
| `requests-6628-bug` (`7a13c041dbef`) | 35 | 1,226,938 | `e3c70a8ccc2c49b51d3f3dd5b01d4b96c9da151adf8c6da980a1bad7fd5cda75` | 0.387, 0.378 |

This supports repeatable output and read-only behavior on these two pinned
checkouts in the same environment. The output hashes include the absolute
checkout path, so they are not portable across locations. The result does not
measure semantic accuracy, other Python versions, or repositories with
different syntax and layout. No scanner change is justified by this check.
