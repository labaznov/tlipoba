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

## Ordinary journal import

The optional `--skill-catalog` argument attaches these lookups to the JSON and HTML
produced by `import-log` version `0.3.0`:

```powershell
python -m damage_lab import-log --game-log "UE_game.log" --skill-catalog "skill-catalog.json" --output local-reports/log-with-catalog
```

The input is a saved UTF-8 JSON object with `format` equal to
`tli-log-skill-catalog-input-v1`, `version` equal to `0.1.0`, and `records` and
`catalog` holding the existing cache collector's outputs. It contains catalog
facts, not manually entered character values. Acquisition of those outputs is a
separate local producer step; the command does not download or discover a catalog.

`damage_lab.logcatalogfile.read` bounds the file to 16 MiB and rejects duplicate
JSON keys, nonfinite numbers, unsupported versions and invalid catalog metadata.
The report's `skill_catalog_source` records the acquired file's SHA-256 and size.
That hash identifies the input bytes; it does not authenticate their producer or
prove that their records derive from the declared member hashes.

Each selected event gets its own `skill_catalog` result. `--event` still selects
only strict character shapes and suppresses partial projections. Without
`--skill-catalog`, the command reads no catalog file. Invalid input refuses the
whole operation before publishing its new result directory; existing outputs are
not replaced. Older reports without catalog fields remain renderable.

These additions do not select a level-specific profile or complete the character
import. Exact Carino DPS still requires further acquisition and semantic bindings.
