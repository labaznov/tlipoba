# Unverified catalog relation in hero-memory candidates

## Problem

The current producer treats `C = S + F` as a consistency requirement, where C
and S are captured client/server level observations and F is a catalog-derived
fixed-affix contribution. A mismatch can suppress both rank candidates as
`input_conflict`. The relation between the captured observations and the catalog
contribution has not been established. A saved item-update path uses a separate
item field instead; that does not establish a universal replacement invariant.

## Requirements

1. The producer emits version `0.1.1` of the existing
   `tli-trait-rank-candidates-v1` format. It preserves C, S, enhancement level,
   memory level, catalog contribution and their paths as observations. It reports
   memory `consistency=unchecked` regardless of C/S/F equality. `input_conflict`
   is not an allowed candidate or trait status in this version.
2. Candidate formulas remain C and C + E. Their missing/invalid inputs, linkage,
   tier-table and range rules remain enforced. Every selected rank stays null;
   agreement never verifies a rule. No A value, zero default or new level formula
   is synthesized.
3. The consumer accepts legacy documents with version absent or `0.1.0`, using
   the existing arithmetic/status validation. It preserves the legacy claims
   in the projection only, while appending exactly this assumption once:
   `Legacy C = S + F labels are an unverified catalog hypothesis, not source facts`.
   This qualification applies to absent-version and 0.1.0 documents, not 0.1.1.
   The projection exposes `contract_version`: `legacy` for an absent version,
   or the explicit supported version. Snapshot, JSON, SQLite and HTML preserve
   this marker; HTML displays `Контракт: <contract_version>`. Older canonical
   records without the marker remain readable as `legacy` (version unavailable
   at that boundary), with legacy relation labels explicitly unverified.
4. For `0.1.1`, the consumer requires `consistency=unchecked`, validates the
   unchanged captured fields and candidate arithmetic, and accepts numerical
   C/S/F disagreement without creating an input conflict. A claimed consistency
   or conflict based on that relation is rejected for this version, as are
   `input_conflict` claims at candidate and trait levels. Canonical snapshot
   validation enforces the same 0.1.1 restrictions.
5. Explicit null, non-string or unsupported producer versions are rejected.
   Source hashes, field paths, counts, linkage, privacy projection and rejection
   of selected ranks retain their existing checks.
6. Ordinary import supports both contracts. Existing historical packages remain
   readable; a separately labeled regenerated archive fixture exercises `0.1.1`
   through the ordinary importer. It is produced by running the actual 0.1.1
   producer on the same saved source SHA, using recorded local catalog inputs;
   hand-editing an old document's version is not this proof. The original
   package is hash-checked as unchanged. No runtime,
   identity, freshness, complete-build or exact-DPS claim becomes true.
7. Documentation and producer assumptions describe the unsupported catalog
   relation accurately. No catalog contribution is added to C, no comparison is
   presented as a proved game invariant, and this feature changes no damage
   formula or rank selection. It must not assert C = S + A or another replacement
   invariant; the one inspected item-update path is not established as the
   binding for exported `_Raw_Data`.

## Assumptions

- The current task remains on the existing planner branch 1 / draft PR2.
- The exporter has no remote; its focused producer change is prepared on a local
  task branch, preserving unrelated working-tree changes.
- The real legacy producer emits 0.1.0. An absent raw-document version is known
  from the synthetic consumer fixture only; it does not prove that a historical
  real producer omitted its version. Missing canonical metadata means that the
  version is unavailable at that boundary, not an inferred source version.
- Compatibility means preserving and qualifying historical artifact claims,
  not retroactively treating them as proved mechanics.
- A regenerated archived fixture is a compatibility test, not a new game export.

## Verification

New tests cite their requirement numbers. Every new test has a recorded RED run
or a mutation probe. Baseline failures block implementation unless explicitly
waived by the human. Focused tests precede the smallest code change; all local
tests and configured linters run on the final integration candidate before any
commit. A reviewer from another vendor reruns the applicable proofs and checks
clause coverage. Source artifacts, user data and logs remain ignored.
