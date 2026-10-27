# Explicit Tangle attachment base

## Requirements

1. Keep `tli-raw-cold-combat-v1` input and serialized JSON report behavior
   compatible, including its assumptions list. Saved pre-change v1 upgrade and
   goal reports remain renderable under the existing exact recomputation check.
   Expose the unverified base-one assumption in HTML and documentation only;
   do not add a v1 JSON assumption that breaks canonical equality.
2. Accept `tli-raw-cold-combat-v2` with the existing fields and exactly one
   additional topology field, `base`. A known base is an integer from 0 through
   1000; booleans, floats, negatives and larger values are rejected. The existing
   limits on maximum, extra, active, hits and retention remain unchanged.
3. For a known base, attached count is `min(maximum, active, base + extra)`.
   Existing hit retention is unchanged. With 100 single-caster DPS, maximum4,
   active4, extra1, hits1 and retention1, base1 yields200 DPS and base2 yields300
   DPS under otherwise neutral, complete conditions. Base0 is an explicit zero
   base, not a missing value; additional capacity still applies. The shared
   `engine.topology` adds keyword-only `base=1`, preserves positional callers and
   its exact `{attached, shotgun, factor}` result shape. Raw combat v2 adds the
   selected base to its successful topology result; v1 topology shape is unchanged.
4. In v2, `base: null` with unknown/conflicting `hit_topology` blocks combat DPS
   and adds `topology.base: unavailable`. No number substitutes for null.
   A confirmed `hit_topology` with null base is inconsistent and rejected.
   Missing base and unsupported topology fields are rejected. Invalid supplied
   sibling values, including `active > maximum`, are still rejected before
   returning a blocked report, without inventing a base to compute geometry.
5. Preserve the selected base in the v2 scenario and successful topology result.
   Existing report containers remain supported; no runtime identity, import
   completeness or game verification follows from a caller's gate assertion.
6. Existing conditional-combat, upgrade and minimum-gain/budget goal queries
   accept complete v2
   scenarios without a second global caster cap. Upgrade variants must share the
   combat contract version as well as the existing common target/context rules;
   mixed v1/v2 comparisons are rejected. Explicit topology replacements within
   v2 remain possible. Unknown base cannot receive a numerical upgrade ranking.
7. Reports preserve their existing validation/recomputation and escaping rules.
   The topology HTML table shows a base row: the supplied integer for v2, unknown
   for v2 null, and one with an explicit unverified legacy-assumption label for
   v1. Never access a missing v1 `base` key or substitute one for v2 null.
   Existing commands publish supported v2 comparisons and goal results without
   a new command. Document the schema and uncertainty boundary.
8. Do not change the game's fact table, inferred formula status, automatic build
   import, spell arithmetic, resistance, armor, uptime or real Carino parameters.
   No actual SS14 base count or exceptional hero override is inferred.

## Sources

- `damage_lab/data/combat-ss14.json`, fact `tangle.single_target_count`: the
  general attachment rule is inferred and its numerical base remains unknown
- `damage_lab/engine.py`, `topology`: the existing base-one scenario
- `damage_lab/rawcombat.py`, `evaluate`: existing validation and gate boundary
- Private bounded audit: `local-reports/next-dps-block-20261025-2157.md`

## Assumptions

- Work remains on issue1 / branch1 / draft PR2
- The 0..1000 base bound is an engineering scenario limit matching the existing
  attachment-count bounds; it is not a documented game limit
- Base0 permits explicit abstract scenarios and never claims a real game state
- Report format stays v1: its existing scenario field carries the input version;
  consumers retain their established strict recomputation rather than trusting
  caller-supplied output
- The legacy panel/hit calculator keeps its documented base-one scenario; the
  new explicit parameter is introduced through the raw combat model

## Verification

Capture synthetic v1 upgrade and goal reports from the pinned pre-change
implementation before production edits. The regression tests render those
pre-change reports, rather than generating expected reports with the new SUT.
Record their source revision and generation commands. All other new cases need
an observed RED or a targeted mutation proving that the case can fail.
