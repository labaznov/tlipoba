# Support instance rolls

1. A support roll is stored on the guide support whose group kind, sourceTab, enabled main and slot 2..6 identify the producer gem. The catalog guid only confirms that gem.
2. Two gems with one catalog guid keep their own rolls. The same slot number in another group is a different gem. A gap in the slot list does not move a roll.
3. The order of skillGroups does not move a roll.
4. Identical rolls remain on every instance.
5. A support with no rolls does not inherit another gem's rolls. A main skill never shows support rolls.
6. A roll that is ambiguous, conflicting or outside the producer layout raises ValueError before a database or import directory is created.
7. Both empty skill arrays, and a support that really has no rolls, keep the existing labels. A main-only group that does not name a tab stays unlabeled.
8. A group that names a producer tab occupies that tab even when it has no supports. A second group with the same kind and tab is refused, in either guide order. Two enabled mains swapped between tabs at the same level are refused.

## Assumptions

The planner tests contain no accepted nonempty roll package. The only legacy shape is both skill arrays empty; its guide support has no sourceTab and no slot. That shape stays unlabeled. A nonempty roll without a producer position is refused. No guid-wide fallback is added. This is not a claim about a current player.
