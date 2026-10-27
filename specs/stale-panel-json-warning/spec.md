# Stale panel JSON warning

Machine-facing calculation outputs must carry the structured newer-conflicting-panel state.

1. `logstats.select` exposes, exactly when it appends the "Newer panel states do not match"
   issue, the structured summary fields `newer_state_conflict` (boolean) and
   `stale_selection_warning` (the fixed module constant, otherwise null). No input-derived
   text is copied.
2. `archive.logged` propagates both fields into the stored panel summary;
   `importer.logsummary` projects them into machine outputs, validating the flag as a
   boolean or explicit unknown and the warning as exactly the matching fixed constant,
   refusing anything else. A stored summary without the fields stays compatible with the
   fields absent (unknown), never reading as no conflict (clause 6).
3. In the stale conflicting case the conditional `calculation.json` contains
   `panel_log.newer_state_conflict == true` and the fixed warning; the ordinary older-only,
   equal-twin and no-panel cases carry `false` and null.
4. Default success semantics stay unchanged: numeric conditional DPS, status
   "conditional", `identity_verified=false`, no scenario suppression, no character or skill
   attribution invented.
5. The warning is a fixed privacy-safe string; no raw log text, private values or source
   paths leak through the new fields.

## Legacy and consistency contract (0585)

6. A stored panel summary without the conflict fields is legacy: `logsummary` preserves the
   absence and never converts it to `false`/null claims of no conflict; the legacy artifact
   is still accepted.
7. When the fields are present the pair must be consistent: `newer_state_conflict=true`
   requires `stale_selection_warning` exactly equal to the fixed constant; `false` requires
   the warning to be null. Partial or contradictory pairs are refused with a safe
   ValueError; a known warning is never silently dropped or invented.
8. New summaries written by `logstats.select` always carry the checked pair, so new
   no-conflict records explicitly assert `false` only because the newer-state check ran.

## Partial-cohort unknown contract (0604)

9. `newer_state_conflict` is tri-state: true (a newer resolved 10103 state provably differs
   from the anchor), false (complete comparison coverage found no such state), and null
   (unknown: comparison coverage is insufficient, as detailed in clauses 12–19).
10. The unknown state carries the fixed privacy-safe constant UNKNOWN_WARNING ("Newer
    partial panel states were omitted; the current-state comparison is unknown") in
    `stale_selection_warning`; true keeps CONFLICT_WARNING and false keeps null. No actor,
    skill, atomicity or actual-conflict inference is made from a partial state.
11. `logsummary` validates the tri-state pairs exactly: true↔CONFLICT_WARNING,
    false↔null, null↔UNKNOWN_WARNING; every other combination, type or text is refused.
    The unknown warning reaches calculation.json like the conflict warning does, and prior
    true/false/legacy behaviors are unchanged.

## Incomplete coverage contract (0620)

12. `false` is reported only with evidenced complete coverage: the document carries no
    gap beyond the three fixed identity sentences (an unterminated snapshot boundary can
    hide an unseen later record) AND no partial cohort sits at or after the selected
    state. A partial cohort at or after the selected state blocks the comparison even
    without a 10103 attribute, because a partial cohort's attribute list is not proven
    complete. Rationale: absence of a proved contradiction must not become no-conflict
    certainty (0619); ties (equal timestamp and frame) cannot be ordered, so a tied
    partial also blocks — this supersedes the earlier strict-greater note recorded in the
    0619 review, reason: no proven temporal order means the comparison is not provable.
13. Strictly older partial cohorts do not block; the fixed identity gaps alone do not
    block. Unknown keeps the fixed UNKNOWN_WARNING and flows to JSON/SQLite/HTML exactly
    like the 0604 unknown; no conflict, actor, skill or atomicity is inferred from a gap.

## Complete coverage evidence contract (0639)

14. Any rejected panel line in the parsed document blocks complete coverage: unrecognized
    panel content could have affected state selection, so the comparison stays unknown
    with the general warning; no reason for the rejection is invented.
15. A resolved cohort sharing the selected cohort's (timestamp, frame) whose 10103 value
    differs beyond the anchor tolerance cannot be ordered against the selected state, so
    the comparison is unknown (not conflict); a tie with the same value or without a 10103
    attribute does not block. Proved newer conflicts remain true.
16. The unknown warning is the fixed general sentence "Panel comparison coverage is
    incomplete; the current-state comparison is unknown"; it never asserts that partial
    states exist. It flows to import/calculation JSON, the SQLite panel summary and the
    HTML report, which renders the comparison result (true/false/unknown) explicitly.

## Legacy rejected-field contract (0654)

17. Rejection coverage semantics: a `rejected` list with entries keeps the unknown of
    clause 14; an explicit empty list is the parser's assertion that nothing was rejected
    and counts as complete; a missing field or any non-list value cannot establish
    coverage, so the comparison reports unknown with the general warning while the input
    stays accepted — no private error text, no invented rejection. Intentional decision:
    the 0604-form warning text existed only inside an unmerged candidate chain and is not
    a published or user legacy artifact (verified against planner history), so
    `logsummary` deliberately validates only the current fixed constants and refuses the
    old candidate text; no compatibility obligation is invented.

## Tied anchor comparison (0663)

18. Every tied candidate state is compared against the native expected Spell DPS anchor
    under the documented 0.5 tolerance — never against the selected observation with a
    chained pairwise tolerance. A tied resolved 10103 state outside the anchor tolerance
    is unordered ambiguity: unknown with the general warning. A tied state inside the
    anchor tolerance does not block. Clause 19 supersedes the earlier non-blocking
    reading for a resolved cohort without 10103: it is not evidence of target coverage.


## Missing target coverage (0680)

19. A resolved cohort at or after the selected cohort lacking 10103 makes the comparison
    unknown unless the source contract supplies explicit evidence that target coverage
    is complete; current tli-panel-log-v1 has no such proof. A strictly older missing-target
    cohort does not block. A proved newer differing 10103 remains true even if another
    cohort has missing coverage. Unknown uses the existing fixed warning in JSON, SQLite
    and HTML and must not invent a conflict, actor, skill, currentness or cause.
    Rationale: parser `resolved` describes only parsing of observed rows, not an exhaustive
    panel. This supersedes the earlier clause 18 non-blocking interpretation (review 0671).
