# Bounded log refresh foundation

The separate Windows exporter now has a reviewed `log_tail.read` utility.
It returns at most 1 MiB of opaque bytes ending at one open-time EOF, with
absolute offsets, a hash and small fixed metadata. It excludes later appends
and refuses observed shrinkage. Path and handle checks disclose replacement;
equal observations do not prove stability or atomicity.

The bytes may begin or end within a line or UTF-8 sequence. Decoding, complete
event coverage and selected-build identity require a separate adapter. The
utility was initially unconnected to ordinary imports and Reader defaults,
and the initial tests did not invoke it against a real game log.

Independent review found a missing terminal time checkpoint. Both coordinator
and helper reproduced it before repair. Fourteen focused tests ran: thirteen
passed and one was skipped. The final Windows exporter suite ran 1,153 tests with two skips. The
two-second processing checkpoints remain soft limits; callers need an outer
deadline for blocking operations. No watcher or service was added.

A separate one-off diagnostic captured a fixed 1 MiB tail from the active log.
That window contained none of the six requested build/stat markers. This
observation says nothing about earlier log windows or protocol availability.
Its raw bytes and account-bearing path remain private.

## Fresh panel and composition check

A Windows development check on 24 October 2026 acquired one fixed 1 MiB
ordinary-log window after the user opened the skill statistics panel. The normal
[`panellog`](../../damage_lab/panellog.py) parser retained one resolved cohort
with 193 unique attributes, no duplicate IDs and no rejected records. No
screenshots, manually entered values, process-memory access or UI automation
were used for that acquisition.

The normal `import-log --context` command parsed six trees in the same window.
They were market search messages; none matched the supported composition
structure. A separate, fixed 4,969,008-byte omitted interval contained no
supported tree headers or composition candidates. No parser limits were relaxed,
and the two acquisitions were not merged into an atomic snapshot. The interval
edges can cut physical lines or events.

The existing native-anchor selector refused to join the fresh panel to an older
native export with a different Spell DPS. The panel also lacked the internal
getter inputs required by the traced damage equation. Observed panel aggregates
do not replace those inputs.

This verifies a screenshot-free development path for observed statistics, not a
complete automatic build import or exact combat DPS. Selected-instance identity,
actor binding, effective levels and complete composition remain unresolved.
Real windows and reports stay private; production code and defaults were
unchanged by this check.

## Two existing parsers on one saved window

`import-log` parses printed composition trees only. Zero such events does not
establish that `RoleAttrMgr` panel data is absent from the same bytes. The
existing [`panellog`](../../damage_lab/panellog.py) parser reads the panel
header/value pairs; no new parser, command or API is required.

Bounded window acquisition is a separate, already verified step. It keeps the
window bytes and window metadata (offsets, discarded leading bytes and origin)
privately, so both parsers can run offline on identical bytes without another
game read. [LOG_IMPORT](../LOG_IMPORT.md) shows both commands. On a synthetic
saved window they reported zero composition events, one resolved panel cohort
and the same snapshot SHA256.

That hash covers only the saved window. It is not the original whole-log hash
and proves neither actor, currentness nor atomicity. No cohort is current
because it is first, latest or equal to another. A native-anchored
`logstats.select` still needs an independent native Spell DPS reading: the
window's own `10103` value cannot anchor itself, and an older native export
does not establish a fresh actor. This note grants no new acquisition
permission and describes no retry.
