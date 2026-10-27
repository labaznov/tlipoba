# Plan

1. Spec clauses 6-8 above; tasks tracked here.
2. RED on the 0546 probe cases: legacy absence turned into false/null, true-without-warning
   accepted, false-with-warning accepted.
3. logsummary: preserve absence; validate present pairs for consistency; keep the fixed
   constant check.
4. Mutants: legacy-default-false, partial-pair-accepted, contradiction-accepted,
   constant-check-dropped. Full suite under host-heavy.

## 0680 plan

Use parser and CLI synthetic cases to prove later and tied missing target are unknown without assigning conflict; retain prior true priority and old/matching cases, then run scoped and full checks under host-heavy.
