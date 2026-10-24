# Catalog candidates from printed skill rows

`damage_lab.logcatalog.project(snapshot, event_index, source_sha256, records, catalog, partial=False)`
compares one explicit saved-log event with an independently acquired SS14 skill catalog.
Use `partial=True` for the separately validated bag-elided character shape.
The `records` mapping and raw `catalog` provenance have the existing offline
`support_effect_inventory_bundle.collect` contract. This pure function opens no files.

The result retains each visible skill row separately, including its source alias,
paths, and distinct lexical `BaseId`, `Level` and `SkillItemLevel` observations.
Only a canonical positive integer catalog token can match an exact record key.
The record's numeric identity and declared category must agree with its catalog
provenance. Withheld identities remain unresolved; there are no identity bridges,
nearest matches or level defaults.

The caller supplies the record map and provenance. Validation checks their declared
identities, categories and accounting; it does not rederive records from the hashed
member bytes. Acquisition must establish that relationship separately, using the
existing bounded cache collector or an equivalently verified producer.

A match is a catalog candidate, not a verified installed skill. The result keeps
the catalog's exact saved-member hashes separate from the ordinary-log prefix
hash. Neither hash proves current patch compatibility or the identity of the
displayed character. An elided skill collection stays incomplete even when every
visible row matches.

Both printed level fields remain observations. No level-specific profile is
selected, and derived gem level, effective level and profile remain null.
Activation, installation, runtime and identity remain unknown; arithmetic readiness
and import completeness remain false. The function does not manufacture a native
`installed_skills` inventory or supply missing damage inputs.

This is an intermediate importer API. The ordinary `import-log` command does not
yet attach catalog candidates automatically. Complete character import and exact
Carino DPS still require further acquisition and semantic bindings.
