# Skill item level source trace

Verified 2026-10-23 against three hash-verified saved installed scripts:
`ItemMgr`, `SkillStateMgr` and the `Table` library. The
[data-only inspector](../CLIENT_LUA.md) parsed their 114,028 payload bytes as
221 functions and 6,973 instructions at unchanged default limits. No game
instructions were executed. Raw files and generated listings remain private.
This is a static source trace; runtime selection and SS14 applicability still
require evidence.

## Constructor and proxy

The [build constructor](build-protocol-schema.md#build-and-stat-paths) passes
each complete `PlayerItem` through `ItemMgr.CreateItem`.
Its body creates an item structure, calls `_UpdateItemData`, then wraps the
result with `table.readonly`.

`_UpdateItemData` assigns `ServerPlayerItem` directly from the wrapper's `Item`
and assigns `ItemData.Level = wrapper.Item.Level or 1`. Under the inspected
Lua conventions, `or` falls back for nil or false; numeric zero is truthy.
This is a constructor fallback, not a rule for accepting unknown player levels
as level one.

The inspected `table.readonly` creates a proxy whose `_Raw_Data` points to its
input table. It does not copy that table. Nested tables are wrapped on access
and cached by reference; non-table values are returned directly. This narrows
the exporter's `_Raw_Data.Level` provenance, but does not make the source
immutable or establish an atomic snapshot. The direct `ServerPlayerItem`
assignment also retains an alias rather than a demonstrated deep copy.

## Experience and upgrade state

For the skill branch, `CreateSkillSpecialInfo` receives the assigned item
level. It looks up `USkillExperienceInfoMgr.GetInfoEx(Type3 * 100 + Level)`
and stores the returned `Experience` as `SkillLimitExp`. This path supplies
an experience requirement, not damage at that level.

The subsequent `SkillStateMgr.GetSkillUpState` receives the original
`PlayerItem.Level or 1`, experience and the mutable item structure. Its
inspected body reads `ItemData.Exp1` for a special upgrade check; it does not
directly write the supplied item. The external special-upgrade helper and
other called services were not inspected here. The body therefore cannot
prove that every dependency is free of side effects.

## Import and calculation consequences

The ordinary exporter reads `SkillData._Raw_Data.Level`; the consumer records
that positive integer as observed `gemLevel`. It still keeps effective level
unknown. The source trace supports retaining that distinction rather than
automatically adding bonuses or selecting a damage row.

The descriptor declares a separate `PlayerItem.SkillItemLevel` field.
Neither its effective-level meaning nor its combination with `Level` follows
from these constructor, proxy and upgrade-state bodies. Absence of a literal
field read does not rule out indirect use elsewhere.

Next evidence is the calculation path that binds level bonuses and a specific
damage-table row, or a source-bound runtime observation of that path. Current
import completeness, active pools and exact Carino DPS are unchanged.

## Static check locations

Paths below are function-tree locations in the private diagnostic listings;
PCs are zero-based, using the pinned inspector's operand conventions.

| Script | Function | Checked operations |
|---|---|---|
| `ItemMgr` | `main.8`, `CreateItem` | PC 6–15: update followed by proxy wrapping |
| `ItemMgr` | `main.11`, `_UpdateItemData` | PC 26–27: source alias; PC 66–71: level assignment; PC 377–416: skill and upgrade-state calls |
| `ItemMgr` | `main.18`, `CreateSkillSpecialInfo` | PC 12–21: experience lookup and assignment |
| `SkillStateMgr` | `main.26`, `GetSkillUpState` | PC 10–15: special upgrade check with `Exp1`; full 123-word body checked for direct item writes |
| `Table` | `main.27`, `readonly` | PC 12–35: proxy creation and raw-data reference |
| `Table` | `main.27.0`, `__index` | PC 0–32: raw lookup, nested proxy cache and scalar return |
