# Installed support-selection boundary

Checked 2026-10-24 against two exact installed-file scripts selected from the
previously verified saved directory index: `AttributeMgr` and `SkillEquipMgr`.
The bounded acquisition read 46,816 bytes including entry headers and the
footer; both complete payload SHA-1 values matched their own headers. The
46,483 payload bytes parsed at unchanged defaults into 51 functions and 2,873
instructions. No game instructions, process-memory reads, UI input or server
requests were executed. Raw scripts and diagnostics remain private.

These are static facts under the inspected Lua operand conventions. Equal
file metadata observations do not prove atomicity, current runtime binding,
selected character or SS14 applicability.

## Support candidates and selection

`SkillEquipMgr.CheckSupportListByTabIndex` takes an active skill instance ID,
tab index and slot ID. It first asks `SkillMgr.GetSkillItemData` for that
instance. Its nil branch traces the missing item and returns an empty table;
that result alone cannot diagnose missing printed data or an empty live group.

The normal path iterates `SkillMgr.SkillSlotDataList[TabIndex]` with `pairs`.
Each candidate must have a non-empty `ItemId`, truthy `SkillData.SpecialInfo`
and a result equal to literal `true` from
`CheckETriggerPassiveSkillAndEPassiveSkill(SkillType)`. The source does not
read `IsActive` in this selection body. Neither the function name nor these
conditions independently establish gameplay activation.

For each accepted candidate it appends `SpecialInfo.SkillId` and the original
slot object to parallel arrays. It calculates a position with `CalSkillPos`
and calls the external native-named method `CheckSupportStoneList` with:

1. The active item's `SpecialInfo.SkillId`
2. A new empty table
3. The calculated position
4. The candidate `SpecialInfo.SkillId` array

The caller retains one return value. It queries `table.keyof` on that value
for each candidate's `SpecialInfo.SkillId`. A nil result permits insertion of
the original slot object into the returned dictionary under its `ItemId`;
a non-nil result skips that insertion. The local name suggests a failure list,
but the external method's behavior remains a prerequisite of that interpretation.

Two previously saved helper bodies narrow the Lua side. The inspected
`table.keyof` iterates `pairs`, returns the first key whose value equals its
second argument, and otherwise returns nil. The skill-type predicate compares
its input with three `ESkillType` fields: `ETriggerPassiveSkill`, `EPassiveSkill`
and `ESpecialLevelUpPassiveSkill`, returning a literal boolean. Their numeric
enum values and actual runtime binding remain unverified. These helper bodies
make the shown filter a conditional exclusion by equal returned values; they
do not supply the external check's rules or result.

This dictionary is distinct from `CheckSupportList`, whose similar native
call and nil-membership filter produce an array of skill IDs. Instance IDs,
`SpecialInfo.SkillId` and printed `BaseId` are separate bindings. Duplicate
instance IDs overwrite dictionary entries in traversal order; the printed
list does not establish that order. No first or last visible winner is adopted.

## Import and calculation consequence

Visible slot positions and item references provide candidates for investigation.
They do not reproduce the external support check. The current
[within-event observation layer](../LOG_BUILD.md) therefore keeps installation,
activation and effective level unknown and does not construct an active support
graph from token equality.

Before applying a support effect, the importer still needs verified bindings
from the imported tree to the slot constructor's arguments, the relevant slot
configuration, the item-type binding and the external check's rules or observed
results. The [coordinate helpers](ordinary-layout-source.md) alone do not
resolve these requirements. No new DPS multiplier follows from this trace.

## Check locations

Function paths and zero-based PCs refer to the saved `SkillEquipMgr` listing.

| Fact | Location |
|---|---|
| Method binding to child 11 | main PC 35–37, constant 13 |
| Active-instance lookup and nil return | `main.11` PC 0–10 |
| Same-tab candidate traversal and gates | `main.11` PC 13–33 |
| Parallel skill-ID and slot-object arrays | `main.11` PC 34–45 |
| Coordinate calculation and external call arguments | `main.11` PC 48–60 |
| Nil-membership filter and dictionary result | `main.11` PC 62–79 |
| Separate array-returning helper | `main.12` PC 0–26 |

For the last filter, `EQ` at PC 73 compares the lookup result with nil and
has A=0. Under the inspected skip convention, equality skips the following
jump and reaches insertion. Otherwise PC 74 has sBx=2 and reaches PC 77,
skipping insertion. This arithmetic is a conditional source interpretation,
not verification of the game's custom VM or native API contract.

The two additional helper listings have separate function-tree coordinates:

| Helper | Binding and body |
|---|---|
| `Table` extension `keyof` | main PC 27–29 binds child 9; `main.9` PC 0–10 |
| `SkillConstantMgr` type predicate | main PC 69–71 binds child 21; `main.21` PC 0–15 |
