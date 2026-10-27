# Plan

Add one helper in `damage_lab/archive.py`, called right after the current loadout is selected. It returns quietly for the legacy branch where both arrays are empty. Otherwise it builds the two `Counter` multisets from clause 4 and raises the fixed sentence on any shape problem or difference. No other module changes.

Tests go into `tests/test_damage_archive.py` as one new class that reuses `package()`. They rewrite the loadout and the guide into the producer shape and refresh `buildSha256`.

Revision 0265: the guide shape checks of clause 3 run before the multiset keys are built. The loadout selection and the check run before `extract(guide)`.
