# Class header context for selected methods

Date: 2026-09-29. This change concerns source selection only. It has not
been evaluated with new model calls, and it does not establish improved
diagnostic accuracy.

## Selection rule

When the target is a uniquely indexed class method, `context` places the
enclosing class declaration after the method as an `owner_class` block. A
multiline base list remains in the declaration. The block ends before the
first class body statement, its decorators, or preceding body comments. It
does not pull in the full class or walk the class's ancestors. Module import
bindings used in the selected header remain eligible under the existing
import selection rule. All blocks share the existing 120-line and 64-KiB
diagnosis limits; a full target can leave no room for the header.

## Offline pinned-checkout comparison

The comparison rebuilt contexts from clean, pinned target checkouts using
the two unchanged manifests and compared them with the earlier frozen JSON
Schema plans. It checked source lines for each target block, context budgets,
and previously included import bindings. Target repository code, tests, and
dependencies were not executed or installed. No DeepSeek request was made.
An offline `diagnose --preview --response-format json-schema` for the Flask
#5391 bug snapshot produced parseable request JSON containing `owner_class`
and the exact class declaration; the serialized preview was 3,926 bytes.

| Set | Cases | Cases with new class header | Selected source lines, before to after | Target method and previous imports |
| --- | ---: | ---: | ---: | --- |
| Click/Requests ten-case manifest | 10 | 6 | 873 to 877 in total | Unchanged in every case |
| Flask six-case holdout | 6 | 4 | 386 to 392 in total | Unchanged in every case |

In the Flask #5391 bug snapshot, the selected source grew from seven to eight
lines. The new line is `class SeparatedPathType(click.Path):` at
`src/flask/cli.py:851`; the fixed snapshot grew from nine to ten lines in the
same way. Both #5786 snapshots gained that class's one-line header and the
newly relevant `Client` import binding. The #4170 snapshots remained at the
120-line budget without a header. Two Requests #7432 snapshots also remained
at 120 lines: a one-line header displaced one later, lower-priority source
line in each; their target methods and previous imports were unchanged.

The earlier Flask #5391 miss showed that the class declaration was absent
from its request. This edit removes that particular context omission, but
the supplied context still omits supported Python-version information and
the previously observed miss cannot establish its cause. Both manifests are
now visible to the implementer, so rerunning them would be an exploratory
check rather than fresh holdout evidence. The next quality gate needs new
unseen cases and independent review of behavioral claims.
