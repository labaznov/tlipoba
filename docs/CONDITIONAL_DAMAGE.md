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

## Command using an automatic import

```powershell
python -m damage_lab conditional-combat --import local-reports/import/import.json --skill "gem[1]" --context examples/conditional-context.json --output local-reports/conditional
```

Use the selected gem alias from the automatic import. The command reads the
imported record and its static ledger, then calls the existing input assembler.
Damage pools, critical parameters, casting parameters and effective level are
never taken from the context file or replaced with defaults. Missing groups stay
null and keep the result blocked. If the selected skill has no supported raw
context or the import has no static ledger, the command refuses the operation.

The context contains only explicit combat choices and evidence: `format`,
`topology`, `target`, `uptime`, `gates`, `missing`, `notes`, `condition` and
`coverage`. Version `tli-conditional-combat-context-v1` has no `topology.base`
and publishes report `0.1.0`. Version `tli-conditional-combat-context-v2` adds
`topology.base` and publishes report `0.1.1` in the same container. Extra fields
such as `spell`, `ledger` or damage rolls are rejected. The examples are
illustrative; their unknown gates and unknown Cursed state are deliberate, not
confirmations.

The import file is limited to 4 MiB and the context to 1 MiB. Duplicate keys,
nonfinite numbers, underflow, malformed JSON and invalid contracts are refused.
Each input gets its own acquired SHA-256 and byte count. These hashes identify
the bytes, not the current actor or freshness.

A fresh output directory receives `conditional-combat.json` and an escaped
`index.html`. The report distinguishes detected conditional inventory from rows
actually applied by the calculation, and shows all blocking gaps. Existing output
paths are not replaced. This command does not read the game, obtain market prices,
infer an active curse or require manually entered character statistics.

## Tangle base

`topology.base` is absent from context v1. HTML labels that case as an unverified
legacy assumption of one Tangle. The JSON report stays version `0.1.0` and its
raw scenario stays `tli-raw-cold-combat-v1`.

Context v2 requires `topology.base` to be an integer from 0 through 1000, or
null. The assembler builds `tli-raw-cold-combat-v2` and report version `0.1.1`.
Null keeps the existing `topology.base: unavailable` gap and is rejected when
`hit_topology` is confirmed. A known integer is stored on the context and on
`calculation.scenario.topology.base`. It is a scenario assertion, not an imported
fact and not a confirmation of Carino geometry.

Automatic imports still leave damage, critical, casting and double-damage groups
null. Every automatic report stays spell-blocked, so DPS, result topology and
factors stay null for base null, 0 and 2. No rank is added.
`examples/conditional-context-v2.json` uses `base: null` and an unknown hit
topology.
