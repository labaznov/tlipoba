# Conditional damage against a Cursed target

The source-backed normal modifier `51423041` is a separate
`conditional_damage_more` family in compiler `0.4.4` / static bundle `0.1.4`.
It preserves `condition: {kind: target_cursed, state: unknown}`. Scope applicability
to player spells does not mean that the target is Cursed. Normal item, definition,
template, unit, own value range and native-container guards still apply; corroded
and defensive lookalikes are not admitted by this rule. See the
[verified source](research/cursed-damage-source.md).

`conditionalcombat.evaluate(combat, ledger, condition=..., coverage=...)` adds only
these conditional rows to an explicit raw combat scenario. The ledger's source
hash must match the spell context. Other ledger families are not reapplied.

The condition is `{cursed: true|false|null, evidence: [...]}`. A declared true or
false requires evidence references. Coverage is a separate
`{status: confirmed|unknown|conflict, evidence: [...]}` gate: confirmation asserts
that the supplied raw pools exclude these conditional sources. It does not prove
runtime state or the completeness of the imported character.

| Target state | Confirmed pool coverage | Result for a complete baseline of 100 and a 20% row |
|---|---|---|
| true | yes | 120 |
| false | yes | 100 |
| unknown | yes | blocked |
| either | unknown or conflicting | blocked |

Enabled rows enter outgoing `spell.damage.more`, with one stack and the existing
additional-pool operation. They are not target damage-taken rows. Source identities
are distinct from shared catalog pool identities: two 20% contributions in one
pool give a factor of 1.4, not 1.44. An already present source or pool is refused
instead of applying the effect twice. Missing raw damage remains missing.

`conditionalcombat.compare(document)` prepares each variant with the same explicit
condition and coverage gate, then uses the existing combat upgrade comparison.
Its `tli-conditional-combat-upgrades-v1` document contains `currency`, `condition`,
`coverage`, a `baseline` with `combat` and `ledger`, and `candidates` with `id`,
`name`, `combat`, `ledger`, `cost` and `missing`. Prices remain caller supplied.
An unknown condition prevents numeric deltas and rankings when a compared variant
contains these conditional rows; unrelated comparisons do not depend on this state.

The normal catalog definition is fixed at 20%. A synthetic 20%→30% arithmetic
check does not authorize the real corroded variant. Gate confirmations are caller
assertions; the adapter does not detect a curse, infer uptime, read the game or
turn an inclusive panel DPS into a raw baseline. Exact Carino DPS remains blocked
while its material raw inputs and applicability evidence are unavailable.
