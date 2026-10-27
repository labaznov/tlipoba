# Loadout skill consistency

`damage_lab.archive.archive()` shows skills from `guide-data.json` `skillGroups`. The exporter writes the current loadout in `build.json` from the same groups (`planner_transfer.py`):
- an `active` group goes into `activeSkills`;
- an `aura` group goes into `passiveSkills`;
- each filled slot is `{skillGuid, enabled: true, level, supports}`;
- the remaining slots are `enabled: false` with `skillGuid` set to null.

The import never compared the two, so a package whose loadout disagreed with its guide published the guide as the current composition.

## Requirements

1. **When the check runs.** After the unique current loadout is selected, and before any database or public output, `archive()` compares the loadout skill slots with the guide groups.
2. **Canonical slots.** When `activeSkills` or `passiveSkills` is non-empty, the loadout is canonical.
   - Each array must be a list of objects with a boolean `enabled`.
   - A slot with `enabled: false` is ignored.
   - A slot with `enabled: true` needs a non-empty string `skillGuid` and an integer `level` that is not a bool.
3. **Guide groups.** In the canonical case:
   - `skillGroups` must be a list;
   - every entry must be an object with `kind` equal to `active` or `aura`;
   - its `main` must be an object with a non-empty string `guid` and an integer `level` that is not a bool.

   These types are checked before any value becomes a multiset key and before any guide-derived extraction. An unhashable or missing value therefore reaches the clause 6 sentence instead of a TypeError, AttributeError or KeyError.
4. **The comparison.** Two multisets are compared:
   - the enabled slots as `(array, skillGuid, level)`;
   - the guide mains as `(activeSkills if kind is active else passiveSkills, guid, level)`.

   Duplicates are kept. An active group never matches a passive slot. Names are never compared.
5. **No bypass.** A loadout whose non-empty arrays contain only disabled slots is still compared, so it cannot hide non-empty guide groups.
6. **Error text.** Any malformed slot, malformed group or unequal multiset raises `ValueError("Current loadout skills differ between build.json and guide-data.json")`. The message names no skill, guid or level. Direct `archive()` leaves no database. The ordinary `import` command exits 1 and leaves no output directory.
7. **Legacy fixture.** When both arrays are empty lists, the check is skipped and behavior is unchanged.
   - This keeps the existing synthetic fixtures (`tests/test_damage_archive.py` `package()`, `examples/make_fixture.py`), whose guide mains carry no guid.
   - It is a compatibility branch only. It proves no current composition, and nothing in the output calls it verified.
8. **Unchanged for matching packages:** guide labels and rendering, support `lineRolls`, the SQLite `systems` `build_only` skills row, and the other inventory, stats and readiness fields. Two instances of the same guid at different levels each match their own slot.

## Out of scope

- Support consistency, and any claim that the supports are complete.
- Source tabs and slot positions, which the multiset does not check.
- Which UI skill is selected, atomicity of the capture, and the current main skill.

## Evidence for the boundary

There are 10 local exporter packages (`captures/20261026-0259-loadout-consistency/real-packages.log`, counts only). In all of them:
- the arrays hold 5 active and 4 passive slots;
- every slot has exactly the keys `enabled`, `level`, `skillGuid` and `supports`;
- `enabled` is a bool and enabled levels are integers;
- the guide kinds are `active` and `aura`;
- the clause 4 multisets are equal.

The planner tests contain no loadout shape that has only support `lineRolls`. The only legacy shape is the one with both arrays empty.

## Revision 0265

Root 0264 showed that the 0259 candidate let malformed guide groups escape clause 6:
- a list or object `guid` escaped as TypeError at the multiset key;
- a null `main`, a null group, a missing `main` or a non-list `skillGroups` escaped from the earlier `skillvalues.extract` call.

The guide shape is now checked explicitly in `consistent()`. Current-loadout selection and `consistent()` now run right after `guide-data.json` is loaded and before `extract`.

As a result, an unknown or duplicate current loadout is now reported before native-stats and skill-value errors, which used to come first. Acceptance is not weakened, and every 0259 behavior is unchanged.
