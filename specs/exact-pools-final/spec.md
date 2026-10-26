# Exact pools final

1. `exact_value` is optional and only on additive `spell.damage.more` rows. The other shape is the old six fields. Any other extra name is refused, including on casting rows, target `more_taken` and multiply rows.
2. The string is derived from the ledger percent divided by 100, normalized with no exponent, no `-0` and no trailing zero, and it matches `-?(0|[1-9][0-9]{0,6})(\.[0-9]{0,10}[1-9])?`.
3. `value == float(exact_value)` exactly. `-1 <= Fraction(exact_value) <= 10**6`.
4. Validation and `engine.cold` both use the exact-substituted rows. An additive pool cannot mix exact and plain rows.
5. P0 and P1 return DPS 0. P5 is `1e-9` within `1e-15` relative. P6 and P7 are refused. Four fraction spellings of one percent share one `exact_value`.
6. Old plain rows still give 120, 140, 100 and unknown. Duplicate sources and other-pool multiplication stay. JSON replay and the priced compare use the ordinary evaluators. No spell-format bump.
7. A saved calculation whose applied rows omit `exact_value` is not the regenerated calculation. `render` still accepts the empty-applied legacy report. `conditionalreport.py` is unchanged.

## Assumptions

53055 is not involved. No live character, roll or DPS is claimed. Old nonempty applied-row reports are regenerated from source and context; they are not rewritten in place.

## 0235 correction, before implementation

8. Direct cold() malformed modifiers retain explicit ValueError before exact substitution, including missing affix, missing value with exact_value, and a non-dict row. A one-shot iterable of valid rows remains supported without a second traversal.
9. Canonical strings reject trailing zeros, negative zero, omitted integer digits, exponent/plus spellings and more than eleven decimals; exact endpoints -1 and 1000000 remain accepted. Integer digits are retained when normalizing percent/100.
10. Report regression uses the real build/render/reconstruction boundary, with a clearly synthetic test-only assembler supplying the complete unit spell. Actual automatic raw groups remain unavailable. A fresh nonempty applied report and its serialized replay render; stripping exact_value fails canonical reconstruction; the unchanged empty legacy fixture renders. This seam demonstrates compatibility, never real source readiness.

The earlier clause7 dictionary-only comparison was insufficient evidence: root0229 and independent0231/0232 require actual renderer behavior. The preexisting canonical comparison and conditionalreport.py remain unchanged. Dead unreachable Fraction-result conversion in cold is removed only while relevant checks are green; no formula change.
