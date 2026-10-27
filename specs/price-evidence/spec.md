# Candidate price evidence

## Problem and authority

docs/VISION.md requires currency, source and acquisition time for a price. DONE0345
verified that the current v1 comparison stores currency and a global caller marker,
but has no candidate-specific source or timestamp. This is a coverage gap, not a
claim that existing arithmetic is defective. This specification implements that
existing requirement without acquiring prices or claiming current market value.

## User stories

1. As a player, I want the source and time attached to each supplied price so I can assess its relevance
2. As a player, I want missing price evidence shown as unknown so absence does not become a market fact
3. As an existing caller, I want saved v1 scenarios and reports to replay unchanged
4. As a player, I want blocked damage candidates and price evidence kept separate so provenance cannot unlock a recommendation

## Requirements

1. Existing tli-combat-upgrade-scenario-v1 and report-v1 behavior, accepted fields,
   returned JSON shape, HTML and goal behavior remain unchanged. Do not add fields
   to legacy output or silently reinterpret a legacy document as v2.
2. Add tli-combat-upgrade-scenario-v2 with the same document fields and candidate
   fields as v1, plus required candidate price_evidence. Its object contains exactly
   source and observed_at. Each is null or a string; null means unknown. All other
   unknown fields and malformed shapes are refused through a safe ValueError.
3. A supplied source is a bounded nonempty trimmed text label, using the existing
   1024-character text policy. It is caller evidence, never independently verified.
4. A supplied observed_at is a valid Gregorian timestamp with four-digit year,
   date, uppercase T, hours/minutes/seconds, optional 1..6 decimal fractional digits,
   and uppercase Z or explicit signed HH:MM offset. Reject naive timestamps, invalid
   dates/times/offsets, bools and nonstrings. Preserve the admitted lexical timestamp
   verbatim for deterministic replay; do not read a clock or invent a collection time.
5. The evaluated tli-combat-upgrade-report-v2 retains the candidate's own complete
   price_evidence and its full original scenario. The existing global price_source
   stays caller. Evidence must survive JSON round-trip without aliasing caller data.
6. HTML for v2 displays source and observed_at alongside the corresponding price,
   escaping all text and explicitly displaying unknown for each null field. Equal
   costs, reordered candidates and blocked/unpriced/free candidates cannot exchange
   evidence. Supplied labels/timestamps do not confirm a market observation.
7. Evidence is diagnostic only: it changes no cost, exact DPS delta, ranking,
   qualification, cheapest-goal choice, exclusions or blocked status. Retain current
   exact arithmetic and its operational budget. Missing evidence does not invent a
   price and does not modify the existing eligibility policy for an explicit cost.
8. Ordinary combat-upgrades CLI supports v2 both plain and with minimum-gain/budget;
   existing atomic new-directory publication and safe error behavior remain intact.
   HTML replay recomputes v2 reports just as v1, refusing modified report evidence,
   costs, ranking or blocked status. It is integrity checking, not authentication:
   callers remain free to author a genuinely different source scenario.

## Decisions and non-goals

A versioned v2 keeps v1 callers byte-compatible. Currency remains the existing
document-wide field; no mixed-currency ranking or conversions. No price fetching,
market API, game/Reader access, external timestamp verification or automatic price
freshness classification. No change to simple panel upgrades or raw combat schemas.
No current-player, selected-skill, market validity or full-DPS claim.

## Assumptions

The existing explicit caller price policy remains accepted. Null evidence is a
truthful intermediate state while source acquisition is unavailable. The new schema
is an engineering extension of the existing price-provenance requirement; any review
finding that changes product acceptance must return to the leader before code.

## Verification and boundaries

Public seams: combatupgrades.evaluate, upgradegoal.evaluate, combatupgradereport.render
and the ordinary combat-upgrades CLI. Every behavioral requirement needs a real
assertion RED or meaningful compiled killed mutant, not an ImportError. Cover v1
unchanged output/HTML, v2 known/null evidence, invalid timestamps/shapes, independent
candidate attribution and copy isolation, exact same rankings/goals, blocked rows,
tamper refusal, escaping, replay and no publication for invalid input. Map tests to
clause numbers. Independent final Spec and Standards reviews, followed by the full
actual-main Windows suite and linters/checks on immutable pins, gate integration.
