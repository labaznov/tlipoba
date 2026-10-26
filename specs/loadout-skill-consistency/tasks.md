# Tasks

1. Baseline: run `test_damage_archive`, `test_importer` and `test_buildinputcli` on the unchanged copy.
2. RED tests:
   - clause 4: foreign guid, missing guide skill, level, active against passive, duplicate multiplicity;
   - clause 5: all-disabled bypass;
   - clause 2/3: malformed slots and groups;
   - clause 6: no output from the CLI and no database from `archive()`.
3. Positive tests, each proven by a compiled semantic mutant:
   - matching producer slots (clause 8);
   - the same guid at two levels;
   - the legacy branch (clause 7).
4. GREEN with the minimal helper, then rerun the scoped modules.
5. Revision 0265: RED for the five 0264 guide shapes, plus the missing kind and a non-list container, through `archive()` and the CLI. Then GREEN, then mutants for every method.
