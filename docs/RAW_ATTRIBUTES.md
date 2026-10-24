# Raw attribute evidence

The ordinary `python -m damage_lab import --package ... --output ...` command
automatically reads a saved `sections.ServerSource.data.attrInfo` wrapper when
it has the form `["rpc.ViewPlayerAttrInfo", {"bytesHex": "..."}]`.
No screenshot or additional hand-written file is required.

This is structural evidence, not a finished stat importer. Attribute IDs, units,
runtime ownership, selected character, freshness, effective skill level and DPS
remain unknown. Numbers are not promoted to named combat stats or applied as
modifiers. The import remains partial.

## Bounded decoding

`damage_lab.rawattrs.decode_view_player_attr` accepts at most 65,536 bytes and
4,096 records. It interprets only matching wire types in three saved descriptor
shapes: `ViewPlayerAttrInfo`, `CPlayerData` and its `AttrsEntry`.
The assumed encoding is standard protobuf; compatibility with saved bytes does
not establish the game's runtime implementation or season semantics.

Its diagnostic record tree preserves original tag, length and value encodings,
including nonminimal varints. Repeated singular fields and duplicate map-entry
keys remain occurrences without a selected winner, merged message or invented
default. Floating-point bits are authoritative; no rounded decimal is emitted.
Unknown length-delimited fields remain opaque. The tree reconstructs the input
bytes as an internal consistency check.

That full diagnostic tree can contain player information and must stay private.
It is not the object stored by normal import.

## Normal import projection

`damage_lab.rawattrbundle.read` verifies the actual source bytes against the
package SHA-256, with a 64 MiB source limit. JSON duplicate members and invalid
numeric representations are refused. A missing wrapper is `absent`, an
unrecognized legacy shape is `unsupported`, and an empty recognized payload is
`decoded` with zero records. Malformed recognized payloads fail the import with
a fixed error.

JSON, SQLite and HTML receive only `tli-raw-attribute-evidence-v1`:

- Separate player and entry occurrences with structural indexes
- Matching float32/double bits and classes, uint64 decimal strings, and explicit
  int32 interpretation forms
- Value-free gap records for opaque, unknown or mismatched fields
- Recomputed counts, the enclosing source hash and explicit unknown semantics

Opaque payloads, arbitrary source strings and embedded player-information blocks
are omitted. The summary validates index order, closed subtree boundaries,
numeric forms and counts. Import snapshots and both HTML paths additionally bind
the projection to their enclosing source hash. This checks internal structure
and provenance consistency; it is not an authenticity or freshness proof.

Tests use synthetic wire bytes and temporary files, including account-data
canaries, malformed inputs and ordinary CLI round trips. Saved player exports
and generated reports stay in ignored local directories.
