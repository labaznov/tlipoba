# Installed attribute calculation boundaries

Checked 2026-10-23 using hash-verified saved installed scripts and data-only
inspectors. `AttrUtils` parsed to strict EOF at unchanged defaults: 32,250 bytes,
62 functions and 2,140 instructions. Selected methods in the separately indexed
`ExportAttrShow` were inspected under the pinned operand conventions. No game
instructions were executed. Raw sources and diagnostic listings remain private.
This is static evidence, with current runtime selection and SS14 applicability
still unverified.

## Player and skill context

`AttrUtils.Init` obtains its field named `RealAttrHelper` specifically from
`UWoodStakeMgr.AttrHelper`. It creates a separate virtual helper with
`UVirtualWorldMgr:CreateAttrHelper(false, 0)` and initially selects that helper.
The field name alone therefore cannot establish current-player identity.
On normal continuation, `SetPlayerId` recreates and selects the virtual helper
using its two supplied arguments. External helper implementations remain outside
this trace.

`_SetCalcType` reads the requested display record's flags for skill binding,
less-tag queries and source queries. `SetStoneItemId` preserves the supplied
item ID when binding is enabled; nil, `-1`, empty text or disabled binding resets
it to `-1`.
This setter neither resolves a catalog skill ID nor calculates effective level.
The normal closing call `_SetCalcType(nil)` does not itself reset the stone ID.

`_BeginCache` chooses the real or virtual bank and compares the active helper's
reported frame with the bank's stored frame. A differing frame replaces that
bank. `_EndCache` only resets counters; it does not clear cached values.
`ClearContextCache` is a separate explicit reset. The inspected bank keys include
stone ID, query type, attribute ID and tag/flag/minion context, without an explicit
player-ID or helper-pointer dimension. This does not establish a cache defect:
actual helper ownership, frame behavior and call ordering remain unknown.
Equal observed values would not prove an atomic snapshot.

## Numeric query boundary

`_GetAttrValue` delegates to external helper methods. Its value branch selects
X, Y or absolute X according to the requested filter. Its base branch uses Base
or Base + Floating. Its increase branch returns `(ModIncr + 100) / 100`; its
more branch multiplies `(entry + 100) / 100` over the returned collection.
These literal operations do not establish which modifier belongs to a given
pool or which critical operator applies to an imported item.

The later [enum binding check](client-enum-query-modes.md) ties the literal
modes to `EBase=B`, `EIncrease=X`, `EMore=E` and `EValue=V` under the inspected
constructor/environment bindings. Its no-filter declaration is integer zero;
an empty-string argument must not be substituted for it by name alone.

`_GetSkillDamageValue` and `_GetSkillMultiplierValue` select `result[Id]`,
then X, Y or absolute X and `tonumber`. An absent entry falls back to zero in
this source path; that fallback is not permission to fill missing imported
character data with zero. The latter method calls a helper named
`GetSkillDamageValueAsHit`; its name alone does not establish units.

## Native helper context: 25 October 2026

Separately bounded saved-file analysis found a context supplying the literal
`UAttrHelper` under a `game` operand and the method names `GetAttrData`,
`GetSkillDamageValue`, `GetCurrentFrame` and `GetAttributeSources`.
An exact address operand shared with the result-wrapper candidate for
`CreateAttrHelper` connects these source observations conditionally.
The literal bytes and selected instruction sequences were independently checked;
opaque binder calls still prevent treating this as verified runtime class or
player identity. A failed RTTI representation did not establish type absence.

The candidate cache lookup and a member-result load are now localized in saved
code. A subsequently inspected callee preserves that result on its direct-return
path; its external tail paths remain unknown. These findings guide the next
bounded acquisition design. They do not establish a live root, scalar encoding,
attribute units, complete pools or an atomic snapshot, and supply no numerical
correction to DPS.

For the explicitly constructed `CppWFloat` payload path, the transport word is
stored with tag `0x13` (decimal 19), retrieved unchanged on the matching-tag
branch, then used as binary64 by the `__tonumber` handler. No scale factor or
special-value filter appears on this path. Other extraction branches delegate
to uninspected code. The raw decoder requires an established payload binding;
character identity, field roles and units remain separate evidence requirements.
Its numeric conversion preserves signed zero, subnormals, infinities and NaNs;
combat validation must still reject nonfinite inputs where required.

The named `FAttrData` registration supplies offsets 8, 16 and 24 for
`Base`, `Floating` and `ModIncr`. Each follows the same candidate scalar
getter and `CppWFloat` pusher. These offsets are relative to the record pointer
returned by an opaque receiver operation, not an arbitrary userdata address.
`AttrType` follows a separate DWORD getter, which zero-extends the stored bits
before integer transport; its semantic identifier namespace remains unknown.

The collection property is named `ModIncrExt`. Its candidate copier reads a
pointer at offset zero and a DWORD count at offset eight, copying eight bytes
per element. Its ordinary push path calls the scalar `CppWFloat` pusher for
each element, then supplies successive index operands starting at one to an
opaque operation. A separate path
retains a collection pointer behind an opaque wrapper; it has not been reduced
to the same iteration contract. Container type, capacity, accepted counts and
pointer lifetime are not established by these observations.

The checked Lua consumer initializes the `EMore` result to one and iterates
`pairs(ModIncrExt)`, updating it as `result * (value + 100) / 100` for each
entry. With ordinary Lua `pairs` behavior, an empty collection leaves one;
a missing collection is not an empty collection. Environment overrides and
custom iteration behavior have not been verified. `EIncrease` instead uses
`(ModIncr + 100) / 100`. The base branches
select `Base + Floating`, `Base`, or `abs(Base)` according to their selector,
and the consumer finally calls `tonumber`. This connects the source field names
to arithmetic, without obtaining current values, proving actor ownership or
authorizing substitution of displayed aggregates for these inputs.

## Display DPS callback arithmetic

The constructor's six checked numeric callback entries delegate to their
matching `_Get...` methods. The selected configuration contains IDs `10100`,
`10103`, `140000`, `150000`, `150001` and `150002`. The earlier
[selector trace](../CLIENT_LUA.md#findings-for-further-calculation-work) chooses
the first matching configuration record; this does not prove which record is
selected for the current Carino skill.

For getter `10103`, define `g(id)` as the first value returned by `_Get{id}`,
without substituting a similarly named panel value. Its inspected arithmetic is:

```text
B = g(105000) + g(105010) + g(105020) + g(105030) + g(105040)
p = g(21210) / 100
m = g(21400) / 100
result = B * g(21000) * (1 + p + p * (m - 2))
       = B * g(21000) * (1 + p * (m - 1))
```

The second expression is an algebraic identity, not a promise of bit-identical
results after rewriting the client's floating-point operation order.

This identifies a concrete static dependency graph. It does not prove that B
equals the average of displayed Total Spell Damage (`11800`), or that the
critical input `21210` can always be replaced by displayed `21212`. Those
substitutions were hypotheses in the historical
[panel comparison](panel-formula-evidence.md), not source bindings. The five
damage getters contain further label-dependent branches and other queries.

The checked `21212` body returns two values: its second is `g(21210)`, while
its first becomes 100 when that value is at least 100, or when it is below 100
and label query `3001120` equals one. Otherwise the first is unchanged.
Getter `21210` itself has label-dependent power branches. This establishes a
real distinction between the queries without proving that it explains the
historical discrepancy or assigning game-mechanic names to those labels.

Getter `21000` calls `_GetUserdefine(7)`, whose body delegates to
`AttrHelper:GetAtkSpeed(SkillStoneId, 0)`. Getter `21400` requests attribute
`4803` with tag `6001100` through `_GetAttrValue`. Their native implementations
and modifier aggregation remain unresolved.

The three `150000`–`150002` getters delegate to user-defined operations
15–17. Their inspected bodies invoke further tag-dependent calculation paths;
they are not interchangeable with `10103`. Getter `140000` has another
component sum and multiplier. Neither their numeric IDs nor their names justify
adding them to every spell's DPS.

## Check locations and next evidence

PCs below are zero-based private listing locations, not game addresses.

| Script | Function | Checked operation |
|---|---|---|
| `AttrUtils` | `main.2`, `main.8` | Helper construction and player-context selection |
| `AttrUtils` | `main.18`, `main.26` | Stone ID and display-query flags |
| `AttrUtils` | `main.22`, `main.27`–`main.31` | Cache reset, frame checks and dimensions |
| `AttrUtils` | `main.32`, PC 151–241 | Value/base/increase/more branches |
| `AttrUtils` | `main.36`, `main.37` | External damage-query results and filtering |
| `ExportAttrShow` | `main.0.26`, PC 0–4 | Callback for `10103` delegates to `_Get10103` |
| `ExportAttrShow` | `main.31`, PC 6–45 | Component sum, rate and critical arithmetic |
| `ExportAttrShow` | `main.112`, `main.121` | Rate operation and critical-value query |

Next, trace the five damage components and critical branches to their source
queries, then compare a source-bound observation of the same skill/context.
The subsequent [endpoint reconciliation](source-endpoint-reconciliation.md)
documents concrete differences in those range queries and a conditional
historical check; it does not confirm equality of the underlying query pools.
Keep panel prediction separate from combat topology, target defenses and
finite-window DPS. Complete automatic acquisition, effective level and exact
Carino combat DPS remain open; this note changes no imported value or formula.
