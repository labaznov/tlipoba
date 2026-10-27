# Frostbite: unresolved source version

Checked 2026-10-24. These mirror pages do not establish which Frostbite rule the
installed SS14 client uses. No Frostbite multiplier was added to the damage model.

| Source | What it states | What remains unproved |
|---|---|---|
| [Frostbite](https://tlidb.com/en/Frostbite) | Its introduction assigns one percent additional Cold damage taken per rating point | Client version, applicability, actual target rating and uptime |
| [Frostbite and Freeze Help](https://tlidb.com/en/Frostbite_and_Freeze) | Ten default rating, a default cap of 120, and rating-related Cold damage wording | A numerical damage coefficient; even the freeze boundary differs between the summary and detail |
| [Character Build](https://tlidb.com/en/Character_Build) | The Frostbite section derives rating from Cold hit damage relative to target Life and Energy Shield, then scales control effect and duration | Which version supersedes this description and whether the other page's damage coefficient applies |

The saved Help body fetched on 2026-10-21 agrees with the dedicated Help page's
two cards, not with all the stronger numerical statements from the other pages.
Its HTML SHA-256 is
`55d1ec159c40676a05b481f72add4d67e3c7f515565715ffc4f364cc2b410c9c`;
the extracted text SHA-256 is
`6e0e6ec5c12721b86f3587932fa7840e1177624ea6b6b943eca108c95c89d7dd`.
These identify saved mirror representations, not installed game data.

The three URLs are presentations from one unofficial mirror, not independent
confirmations. A fetch date does not establish an effective game version.
The existing [Help registry](../../damage_lab/data/help-index-ss14.json) already
records the dedicated Help page's missing coefficient and freeze-boundary conflict.

A character's maximum rating is a cap, not a measurement of an enemy's current
rating. Frostbite Effect likewise cannot become a Cold damage multiplier without
its scaling rule. Required next evidence is a version-bound client rule and a
source-bound target state, or an equivalent controlled observation. Picking the
description that best matches a benchmark would not resolve this conflict.
