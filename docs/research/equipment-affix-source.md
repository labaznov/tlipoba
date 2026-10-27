# Equipment arguments, definitions and preload data

Checked 2026-10-24 against pinned saved client modules. These are conditional
static facts under the inspected Lua operand convention. The inspection did not
run game instructions, read process memory, use Reader/UI input or send server
requests. A previously pinned isolated third-party codec decompressed one saved
data entry; it was not installed globally. Runtime bindings, season and current
character applicability remain unverified.

## Actual arguments and requested ranges are different paths

`AffixLinkerMgr.GetAffixItemData` reads each row's `Id` and lowercase `source`.
With a Lua-truthy `bWithRange`, it requests
`middle:GetDefaultDynmcParam(Id, EMTT_Equip)` and labels the selected arguments
`F_tableParam`. Otherwise it uses the row's `DynArgs` and labels them
`F_serverParam`. There is no local nil-to-default fallback or merge of those
two sources. The helper name alone does not establish its implementation or
the meaning of its values.

The same body makes a new keyed argument table with values multiplied by
minus one only when all three conditions hold: `bNightmareReversed` is truthy,
the looked-up definition's `ModifierType` equals `DreamBad`, and `bWithRange`
is falsy. It does not assign that table back to the source row. Numeric types,
metamethods and the meaning of the reversal are not validated here.

It forwards the selected value to `middle:Equip_GetAffixItemData`, including the
source label. All returned values feed `table.insert`; exactly one appended
row is not established without the callee's return contract. This is an
item-data path, not proof of effect execution or a general DPS transformation.
The [lexical importer](../LOG_BUILD.md) therefore keeps printed values and
their paths without replacing rolls by defaults or applying this negation.

## A modifier ID, a server-affix key and a type are distinct

`ProcessServerAffixInfoByAffixData` queries `UModifierInfoMgr.GetInfo` with the
row's `Id`, then reads that result's `ServerAffix`. It calls the custom
`string.split` helper with delimiter `{`, converts the first returned segment
with `tonumber`, and queries `UServerAffixInfoMgr.GetInfo` with that result.
If the split result's first element is nil, it returns before either operation.
A missing second record causes a trace call and return. There is no guard
before reading the first result's field or passing a nil numeric conversion
to the second lookup.

For a non-nil second record it makes a plain callback call with three
arguments: that record's `Type`, the original row's `DynArgs`, and the record
itself. Callback results are discarded. The callback identity and custom split
semantics remain unknown. No equality between the two lookup keys, `Type`,
the caller's `AffixType` or imported native attribute IDs is established.
External calls are not assumed pure.

## The preload manager is another source, not a proven native definition table

The separately acquired module assigns the environment's `wolf` to its existing
truthy value or a new table, then publishes the manager binding as
`wolf.UModifierInfoPreLoadMgr`. It does not assign `wolf.UModifierInfoMgr` in
the inspected root. Its `Load` calls
`require('Config.LuaPreLoadTable.DataCfg.config_preload_modifier')` and then
calls the returned value. A callable is required; it need not be a plain
function. The result is checked for nil/table shape, but if `LUA_ERROR` returns,
the invalid value is still assigned to `Infos`. The old table is cleared first.
`GetInfo` indexes `Infos` with the original key and normalizes falsy values to nil.
This does not show that native-named `UModifierInfoMgr` uses the same data.

The manager acquisition read 1,705 installed-file bytes, including a
1,426-byte payload. The exact required data module then used a separate
327,553-byte read: 327,238 compressed bytes, a 90-byte header and a fresh
225-byte footer. Both complete stored payload hashes matched their own headers;
equal file metadata is not atomicity. The two data blocks decompressed to
342,920 bytes. One independently reviewed call admitted that exact byte length
and a 32,768 per-list / aggregate-instruction limit within the existing parser hard ceilings; defaults stayed
unchanged. It parsed three functions and 20,706 instructions to strict EOF.

The inspected constructor windows contain string keys and integer lists. The
root's tail calls the environment's `setmetatable`, then returns a closure whose
descriptor captures root register zero. Neither the constructor nor the closure
was executed or materialized into a verified runtime configuration. This does
not establish modifier fields, group-key meanings, attribute identities, units
or the link to the native manager. Parser success is not a DPS input contract.
Post-generation output limits and soft processing deadlines are not hard
peak-memory bounds.

## Primary check points and next requirement

| Parsed module SHA-256 | Function / zero-based PCs | Observed boundary |
|---|---|---|
| `a6e2f63ba0fdc1a1ef8e55f7d5d8ab4939c3f16c60d889028066783a1624b941` | Root 29–31; child 10 7–22, 23–46, 47–63 | Item arguments, range branch, conditional reversal and output |
| Same module | Root 293–295; child 98 0–35 | Modifier definition to separate server-affix record and callback |
| `7d8df737c2b60d5bbf942bcbab905033a0a551a5c2093fbc64379268be9f6ef9` | Root 0–18; children 0–3 | Separate preload manager, require/call and lookup |
| `a9e14f759b460d65ccc14ff1bcff09c0d8d2ea81606ed49678b305fe1d9c1a93` | Root 0–17, 20675–20698; children 0–1 | Limited constructor/closure windows, not a full semantic table projection |

The [command conversion](affix-command-source.md) remains a separate path.
Before equipment observations enter the damage model, a resolver still needs
positive bindings from the relevant definition and argument positions to
attribute identity, numeric units, operator, scope and activation. Neither a
matching field name nor a range/default representation supplies those bindings.
Missing raw damage, crit, casting and effective level keep exact Carino DPS
unverified.
