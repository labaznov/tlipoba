# Explicit Tangle base in automatic conditional reports

## Requirements

1. Keep context `tli-conditional-combat-context-v1` and its automatic report version
   `0.1.0` JSON compatible. Capture a genuine pre-change synthetic report and
   preserve its exact reconstruction/render support. Do not add v1 JSON fields
   or change its raw-combat-v1 scenario or assumptions.
2. Accept `tli-conditional-combat-context-v2` with the same top-level fields and
   exactly one added topology field `base`, using the strict raw-combat-v2
   contract. Build raw-combat-v2 and automatic report version `0.1.1` for this
   context only; the report container format stays v1. Base must be int0..1000
   or null. Reject bool, float, missing/extra fields and unsupported formats.
3. Preserve base null. Unknown/conflicting hit_topology must retain the existing
   topology.base gap; confirmed plus null is rejected, and all supplied sibling
   values still validate. For known0/2, preserve that exact integer in context
   and calculation.scenario.topology.base without adding the null-base gap.
   The current assembler always leaves material raw-spell groups unavailable:
   every automatic report remains spell-blocked, with DPS and downstream
   geometry/factors null regardless of base. Do not inject complete synthetic
   spell groups to manufacture an automatic numeric result. Known-base numeric
   geometry is already tested in rawcombat. No ranking exists in this report.
   Known base is a scenario assertion, never an imported fact or confirmation
   of actual Carino geometry. Raw spell groups remain exactly as assembled.
4. Render both versions with exact source-bound recomputation and escaping.
   Accept exactly (context v1, report0.1.0) and (context v2, report0.1.1), rejecting
   other pairs before reconstruction. Compare canonical JSON using sorted keys
   and allow_nan=False rather than Python equality, which equates True/1 and
   2/2.0. Reject those type substitutions in reconstructed nested fields of both
   versions, as well as tampered base, result, raw format or verification flags.
   Immediately after the status paragraph, show v2 base as its integer or unknown;
   label v1 base1 as an unverified legacy assumption in HTML only. Valid v1 JSON
   stays unchanged; its HTML gains this label. Keep inputs unchanged.
5. The existing conditional-combat command publishes v2 through the same JSON/HTML
   output files with exact acquired file hashes and bounded reads. Keep duplicate
   flag/key, numeric validation, generic errors and no-overwrite behavior. Do not
   introduce a new command, manual character-stat file or game access.
6. Document v1/v2 mapping and uncertainty in the existing conditional documentation;
   add a synthetic v2 context example with base:null and unknown hit_topology.
   Tests exercise actual automatic synthetic import -> assembler -> conditional
   evaluator -> ordinary CLI -> JSON reconstruction/HTML, including null/known0/2
   scenario preservation with spell-blocked results,
   invalid sibling/null and source/hash/tamper/escaping cases.
7. Do not change rawcombat, rawspell, engine arithmetic, source mappings, fact tables,
   ranks, effective levels, activation, market prices or automatic import record
   contracts. No real base count, wire body, complete import or full Carino DPS
   is inferred. Preserve all existing provenance and false verification flags.

## Assumptions

- Continue existing issue1 / branch1 / draftPR2
- The battle context is a separate explicit scenario choice, not imported character
  damage/crit/casting. Existing automatic records stay unchanged
- The existing report container can distinguish compatibility by version0.1.0/0.1.1
  and context format; no database migration is required for generated CLI reports
- All work is offline Windows with synthetic fixtures and saved public source

## Verification

Each clause maps to paired tests with observed RED or a meaningful isolated mutation.
Freeze a v1 synthetic report before production edits and record generation command,
source SHA and exact bytes. Preserve every old assertion; full scripts/test.py after
final changes and independent Spec/Standards review precede integration.
