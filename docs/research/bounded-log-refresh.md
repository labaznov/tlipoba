# Bounded log refresh foundation

The separate Windows exporter now has a reviewed `log_tail.read` utility.
It returns at most 1 MiB of opaque bytes ending at one open-time EOF, with
absolute offsets, a hash and small fixed metadata. It excludes later appends
and refuses observed shrinkage. Path and handle checks disclose replacement;
equal observations do not prove stability or atomicity.

The bytes may begin or end within a line or UTF-8 sequence. Decoding, complete
event coverage and selected-build identity require a separate adapter. The
utility is currently unconnected to ordinary imports and Reader defaults,
and it has not been invoked against a real game log.

Independent review found a missing terminal time checkpoint. Both coordinator
and helper reproduced it before repair. Fourteen focused tests ran: thirteen
passed and one was skipped. The final Windows exporter suite ran 1,153 tests with two skips. The
two-second processing checkpoints remain soft limits; callers need an outer
deadline for blocking operations. No watcher or service was added.

A separate one-off diagnostic captured a fixed 1 MiB tail from the active log.
That window contained none of the six requested build/stat markers. This
observation says nothing about earlier log windows or protocol availability.
Its raw bytes and account-bearing path remain private.
