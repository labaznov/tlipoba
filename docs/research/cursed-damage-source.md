# Conditional damage against Cursed enemies

Checked 2026-10-24. This identifies a concrete next compiler rule; no conditional
damage implementation or current-character activation is claimed by this note.

An exact saved SS14 catalog member contains the normal legendary modifier
`51423041`, with template `+#% additional damage against Cursed enemies`.
The definition has one positive percent specification, fixed at 20% for the
verified normal variant. This does not validate a corroded 30% variant. It is separate from the
adjacent defensive modifier `51423051`; damage dealt and damage taken must not be
interchanged.

The item definition is `b4aa6245-131d-57ba-88cf-64f2d452a8d4`, with catalog
`tlidbId` stored as the string `112230`. The normal modifier is read through
`descriptionTemplate` and `normalValues`, not a corroded description.
Its source coordinate is `legendaries/helmet/int_helmet/master`, under the
item's `mods` list. The exact UTF-8 member is 21,350 bytes with SHA-256
`2f46ff4211bbedbb5a9073fb68ea298ca3b23c236d6cd89c7c0700985b6cd270`.
The coordinator independently verified that member and the unique matching
definition. See the [catalog provenance contract](../SUPPORT_CATALOG.md).

These are saved community catalog facts. They do not verify the current patch,
the character's own roll, native application or curse uptime. The compiler's
existing exact-definition, own-value range, variant, unit and native-condition
guards still have to pass for any real row.

The implementation must retain a target-Cursed condition separately from skill
scope. Explicit true can enable the source-bound additional-damage row; false
must disable it; unknown must block a numeric result that depends on it. A printed
curse skill or an empty native condition array does not establish an active curse.
The row must pass through existing additional-damage pooling once, including
duplicate-source protection, rather than multiplying an already inclusive panel DPS.

Acceptance must reach calculation and upgrade comparison, not stop at displaying
another candidate. Synthetic checks should distinguish a baseline of 100 with a
20% modifier: 120 when the declared condition is true, 100 when false, and blocked
when unknown. Comparing 20% with 30% under the same confirmed condition should
give a delta of 10. These are test oracles, not character measurements.
