# Strict metadata census before content acquisition

Checked 2026-10-24. The external Windows exporter has an offline-tested,
op-only `strict_census` diagnostic. It measures the map and potential packing
cost without reading game contents or starting the finder. No live result is
claimed here.

The platform provider observes `GetNativeSystemInfo`, admitting the declared
64-bit Windows / AMD64 / 4096-byte-page profile. It uses the 48-byte
`SYSTEM_INFO` layout and validates the application bounds before addition.
The maximum comes from the system observation, rather than a guessed numeral.
[SYSTEM_INFO](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-system_info)
defines that field, and
[GetNativeSystemInfo](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getnativesysteminfo)
describes the platform observation.

The strict walk uses the existing single-region `query` method. Every row
must have exact primitive fields, continue at the requested address and fit
inside the observed endpoint. Operand bounds precede arithmetic. Only
reaching that endpoint ends the walk; no query is made there. An earlier
error 87 is inconclusive. The
[VirtualQueryEx contract](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualqueryex)
says that querying above a process's highest accessible address causes that
error; the error alone does not establish the end.

One fresh budget covers the provider, walk, planning and reply preparation:
65535 yielded rows, at most one extra probe query, and a 30-second soft
deadline. Post-call checks include failed calls. The deadline cannot cancel
an in-flight native operation. An incomplete or refused walk has no accepted
plan and makes no complete-domain claim.

The finite JSON reply is at most 4096 bytes and contains counts, platform
status and lower-bound packing costs. It contains no row or endpoint address.
Provider/query attempts are counted separately from the one logical census
charge and zero content reads. With the inspected real provider and query
path, each attempt entails at most one corresponding native call; fake
providers are not native measurements. Backend image checks and transport
authentication lie outside that narrowly named counter model.

Every returned outcome, including budget refusals and the fixed output
fallback, passes bounded finalization. There are at most two passes and,
conservatively, four finite encodings. A changed refusal is itself checked;
the returned payload is the last encoded payload. Finalization performs no
new provider, query or content operation and never resets the budget.

Independent tests first reproduced two failures from one finalization gap.
After repair, all 14 independent coordinator checks passed. The final external
Windows suite ran 1391 tests with two existing skips; 97 focused tests passed.
Separate independent Spec review is functionally clean, and coordinator
Standards review has no blocking finding with maintenance debt recorded.
The author review is separate.

A complete result covers only the observed system application interval for
this sequential walk. It does not establish the target's architecture, an
atomic snapshot, stable topology, the current player or all process memory.
Some concurrent changes may remain undetected. Packing fit remains a lower
bound without reserved validation cost or a runtime guarantee.

The new operation requires a normal fresh ReaderSession after review; the
existing `info` reply contains no module-version proof. Ordinary build import,
new character values and exact Carino DPS are not established by these tests.
