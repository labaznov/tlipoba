# Skill slot identity and reader boundaries

Checked 2026-10-24 against retained installed-script listings. These are
static source facts under the inspected operand conventions and bindings;
struct defaults, metatables and current runtime selection remain unknown.
Raw listings and player inputs remain private. No gameplay or DPS gate changes.

## Instance identity and sentinels

`ViewPlayerMgr.CreateSkillLayout` passes the newly created slot object and
the input entry to `SkillMgr.InitSkillSlotItemData`. The initializer copies
`entry.value.skillId` unchanged into `ItemId` and returns that same object
on its successful path. The constructor subsequently uses the same input
reference as the key for `Skills[reference]`.

The two string sentinels have different source paths:

| Reference | Initializer | Constructor | List reader |
|---|---|---|---|
| Empty string | Returns before the unlock-state write | Attempts the dictionary lookup | Skips the slot |
| `"0"` | Writes the filled unlock state | Skips the dictionary lookup | Passes the non-empty test |

The latter path leaves `SkillData` at its unknown struct default. A missing
dictionary entry can also leave no usable skill object. Neither path proves
an empty, equipped or active skill; a later reader may fail when indexing it.

## View-player readers

`GetSkillDataList` inspects slot 1 for tabs at or below literal 5. For tabs
above 5 it inspects every slot and additionally requires the skill's type
to equal the bound aura enum. Both paths require `ItemId` to differ from the
empty string; the lower-tab path also skips a falsy slot 1. List order follows
the unestablished `pairs` order. The returned `SkillItemId` comes from that instance reference;
`BaseId` comes separately from `SkillData.ConfigBaseId`.

`GetMainSkillData` reads `SkillLayout[1][1].SkillData`. With a usable
`SkillLayout`, it returns nil when tab 1, slot 1 or `SkillData` is absent
or falsy; a nil `SkillLayout` itself raises. This identifies what the
accessor returns, not the selected statistics page or active DPS skill.
Keys 1 and 100 both map to that coordinate under the captured arithmetic;
their collision winner remains unknown.

## Separate local-player configuration

In the configuration loop of `SkillMgr.InitSkillData`, values returned by
`USkillSlotsInfoMgr.GetAllInfos` supply six explicitly read properties:

| Property | Source use |
|---|---|
| `SkillId` | Tab index and running tab maximum |
| `SlotId` | Slot index, running slot maximum and cost-initializer argument |
| `UnlockLevel` | Unlock struct field, message and player-level comparison |
| `Type` | Copied unchanged into `SlotType` |
| `UnlockCost` | Cost field and cost-initializer argument |
| `Energy` | Energy field |

This is a Lua consumer contract, not the complete native schema or its
serialized field order, types and defaults. In particular, the source uses
`SkillId` as a tab coordinate; its name does not make it an item-instance
or catalog identity. The view-player initializer does not perform this
configuration loop. Its coordinates alone therefore do not establish
`SlotType` or installed support membership.

## Check locations and provenance

Function paths and PCs are zero-based in the saved diagnostic listings.

| Listing | Location |
|---|---|
| `ViewPlayerMgr` | `main.12` PC 21–32: initializer call and reference lookup |
| `ViewPlayerMgr` | `main.13`: list reader; `main.22`: literal `[1][1]` accessor |
| `SkillMgr` | `main.14` PC 4–38: reference copy, distinct sentinels and return |
| `SkillMgr` | `main.5` PC 40–150: native-info iteration and property reads |

The parsed diagnostic JSON SHA-256 values are:

- `ViewPlayerMgr`: `6727bd46e28e02e7e216a72e9b931c43c1e224397672806d7d1a8c88d7e0a0be`
- `SkillMgr`: `6287618b91886f8945b18d7c6f2b32f9d37bb54e89de170b1bdaa403ccb899a4`

The [ordinary import graph](ordinary-layout-source.md) keeps candidate
coordinates and unresolved collisions. The [support-selection trace](support-selection-source.md)
describes the separate selection boundary. Currentness, activation, effective
level and raw damage, critical and casting pools still require their own evidence.
