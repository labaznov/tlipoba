# Printed skill layout and item references

Checked 2026-10-24 against the saved installed `ViewPlayerMgr` listing and
the partial descriptor projection described in [build-protocol-schema](build-protocol-schema.md).
These are static source facts under the inspected Lua operand conventions,
not a current character, selected build, active support group or SS14 runtime proof.
No game instructions or server requests were executed for this check.
Raw listings and descriptors remain private.

## Reference path

The descriptor declares `ViewFeaturesInfo.skillLayout` as `SkillSlotDTO`.
Its repeated `slots` contains `SlotsEntry`: int32 `key` and `SkillStatus`
`value`. The latter declares string `skillId` and an enum `status`.
`PlayerItem.Id` is also a declared string. Map-entry options and enum
semantics remain unresolved; names and compatible types alone do not prove a join.

The saved source supplies the reference:

1. `CreateSkills` constructs each item and assigns it to a dictionary keyed
   by that input `PlayerItem.Id`
2. `CreateViewPlayerData` passes the resulting dictionary as the second
   argument to `CreateSkillLayout`
3. That helper reads a slot's `value.skillId`; its lookup path reads
   `Skills[skillId]` and assigns the result to a struct's `SkillData`

Thus the inspected lookup uses an item-instance reference. It is separate
from `BaseId`, which identifies a catalog definition. The ordinary lexical
projection deliberately omits both instance fields. A future within-event
comparison can emit coordinate aliases without exporting their raw tokens.
Such an observed token match must preserve missing and elided peers and
duplicate ambiguity; it cannot establish the selected installed item or a
complete support group. The printer's lexical classes are not original wire types.

The code also compares the reference with the string `"0"`. At PC 29–32,
the listing has `EQ`, `JMP` with signed offset 2, the dictionary lookup and
then the `SkillData` assignment. With ordinary `pc + 1 + offset` semantics,
the jump at PC 30 reaches PC 33, skipping both lookup and assignment. This
function then makes no such assignment on the string-sentinel path. The
initialization helper or struct defaults may already supply a value, and the
data inspector alone does not verify the game's custom control-flow semantics.
An empty or unequipped slot is therefore not established by the literal sentinel.

## Position and alias gaps

`CreateSkillLayout` passes the printed `key` unchanged into
`SkillConstantMgr:CalSkillTabIndex`. The two returned values index the
output dictionary. Its body was not inspected here: quotient/remainder,
slot roles and UI grouping must not be invented from observed key ranges.

The helper stores the return of `SkillMgr.InitSkillSlotItemData(struct, entry)`
before assigning `struct.SkillData`. Whether that returned object is the same
struct remains unverified. The lookup itself is visible; its presence on the
stored layout record requires this additional alias binding.

The source iterates with `pairs`. Duplicate item IDs and duplicate output
coordinates overwrite in traversal order, which a printed list does not
establish. A conservative importer must preserve ambiguity rather than select
the first or last visible record. An absent lookup yields nil under ordinary
table semantics; this is not permission to treat a missing printed item as absent.
Global lookup, helper implementations, metatables, rebinding and current
runtime selection remain prerequisites of the static interpretation.

## Check locations

Function paths and zero-based PCs refer to the saved diagnostic listing.

| Binding | Location |
|---|---|
| `CreateSkills` and `CreateSkillLayout` method assignments | main PC 36–40 |
| Constructor calls and dictionary argument flow | `main.5` PC 33–43 |
| Item dictionary key from `PlayerItem.Id` | `main.11` PC 26–27 |
| Key passed to external coordinate helper | `main.12` PC 8–11 |
| Initialized object stored at returned coordinates | `main.12` PC 20–26 |
| String sentinel and dictionary lookup | `main.12` PC 27–32 |

The next source bindings are the two external helper bodies. Effective skill
level, activation and the unresolved [raw damage calculation](attribute-calculation-source.md)
remain separate requirements; this trace supplies no numeric DPS.
