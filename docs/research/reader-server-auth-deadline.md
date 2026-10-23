# Reader server authentication receive deadline

Local Windows producer observation, 2026-10-23. This concerns the companion
exporter's named-pipe transport, not a game API or a DPS formula.

A controlled test reproduced a silent authentication peer preventing the
single-threaded server from serving a normal peer. The silent peer drained
the server's challenge and left its connection open without answering.
The normal client's existing receive deadline expired while the server
remained occupied.

The producer now shares its existing authentication receive wrapper between
client and server. The server gives both authentication phases one deadline,
preserves their order and HMAC checks, and closes the original connection
when authentication fails. Successful acceptance returns the original
connection. Message-length limits, pipe access controls and operation
allowlists are unchanged.

The behavioral test failed before this change and passed afterward: the
silent peer timed out, its connection closed, and the next authenticated
peer received its expected reply while the silent client's local handle
was still open. Independent static review found the production change
consistent with this contract. The producer suite ran 1,137 tests with one
skip on Windows; all recorded owned processes ended. A later test-only
strengthening also requires the owned child's exit code to be zero; its
focused rerun passed without another full-suite run.

This bounds receive waits during authentication. It is not a hard wall-clock
bound for accept, connect, sends, cancellation drain or completion after a
successful poll. The test uses an outer owned-child timeout for containment.

No real Reader session or game was used for this test. A new selected-source
manifest has been frozen from the reviewed bytes; older manifests containing
the changed modules remain invalid. This is not transitive runtime attestation.
A new manual Reader process is required before live use;
the completed test does not prove live import or exact Carino DPS.
