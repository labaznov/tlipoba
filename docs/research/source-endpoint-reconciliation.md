# Conditional reconciliation of historical Spell DPS

Checked 2026-10-23 from hash-verified saved installed source and two saved
panel-log projections. No new game-memory read, UI input or game-code execution
was performed. The private comparison examined all 37 cohorts: 33 met the stated
cold-only numeric preconditions and four lacked required resolved fields.
The 33 retained rows contain four distinct numeric input tuples and four
distinct observed/predicted pairs;
repeated rows are not independent experiments.

## Source dependency that changes the comparison

The [attribute source trace](attribute-calculation-source.md) identifies the
five internal component queries used by display getter `10103`. Its input is
not explicitly the arithmetic mean of displayed range getter `11800`.

Getter `11800` separately sums elements one and two of `11900`–`12300`.
For each of the four nonphysical endpoint getters `12000`–`12300`, the
inspected source includes these outer factors, with `t = g(11201) / 100`:

```text
first endpoint:  0.7 + t
second endpoint: 1 + 0.01 * (1 - t) * (-30) = 0.7 + 0.3 * t
```

The asymmetry is literal: the first branch has no `0.3` multiplier on t.
It must not be silently normalized to the second branch. This observation does
not establish a runtime bug. Getter `11900` has a different literal factor.
The remaining endpoint and scalar paths also contain different tag queries,
label branches and further modifiers; matching names do not prove equality.

One internal base query, `104000`, computes a weighted expression:

```text
((1 + a) * L + (1 + b) * H) / (2 + a + b)
a = g(82005)
b = g(82000)
```

Its L/H terms share the corresponding inspected `114000`/`124000` base-query
structure. These are internal endpoints, not automatically the final displayed
range. With a=b=0 this particular expression reduces algebraically to a mean;
actual label values and the rest of the conversion/modifier graph remain open.

## Fixed hypothesis tested against saved observations

The comparison preselected a zero-weight, cold-only branch and additionally
hypothesized equality of B with the inverted endpoint mean below. Zero weights
alone do not imply that equality. The outer `U(0) * (1 + g(12400)/100)` factor,
empty-tag versus spell-tag attribute coefficients and label branches must be
neutral or accounted identically in both paths; this has not been established.
It did not search for weights, choose a fitted multiplier or use a dummy result.
For observed cold range `[lo, hi]` it used:

```text
L = lo / (0.7 + t)
H = hi / (0.7 + 0.3 * t)
B = (L + H) / 2
prediction = B * rate * (1 + chance * (critical_multiplier - 1))
```

All inputs came automatically from the same saved cohort's numeric tokens:
`12100`, `11201`, `21000`, the first `21212` value and `21400`. The comparison
required observed zero endpoints for `11900`, `12000`, `12200`, `12300`, an
identical total/cold range, and a chance below 100%. Under the inspected
`21212` branch, a first value below 100 agrees with `21210`; it does not prove
the historical runtime used this installed source.

The maximum observed absolute difference was below one tenth in reported DPS
units; the maximum absolute relative difference was below five parts per billion.
That is a numerical observation, not a declared rounding tolerance: the game
printer's precision remains unknown. Exact rational arithmetic over printed
tokens does not reproduce every binary64 operation in the client.

For a synthetic arithmetic control, take t=1/5, internal endpoints L=200 and
H=500. The displayed endpoints are then 180 and 380. Their direct mean is280;
inverting the two different factors recovers the internal mean350. At rate7/3,
chance1/4 and critical multiplier9/5, the stated conditional prediction is980.
These numbers are synthetic, not a character fixture.

## What this settles and what it leaves open

The source-derived conditional expression reconciles the saved panel numbers
without a fitted residual. It gives a concrete reason to stop treating the
displayed midpoint as an already verified input to getter `10103`.

It does not establish current-player or selected-skill identity, recomputation,
historical-version equivalence, actual zero endpoint weights, equality of the
different scoped queries or all conversion paths. Numeric agreement alone
cannot settle those assumptions. The caller must not convert this diagnostic
into an automatically confirmed combat formula or apply its correction on top
of an already computed Spell DPS.

Next evidence is the lower-level endpoint/scalar binding and its runtime
context. Full raw-spell aggregation, effective level, Tangle/hit topology,
target defenses and finite-window combat DPS remain separate work. No imported
value, raw-calculation gate or engine formula changes with this source note.

## Conditional propagation through conversion terms

A further static check compared the scalar `104xxx`, minimum `114xxx` and
maximum `124xxx` families. For the inspected suffixes, instruction words match
exactly, and tagged constants match after renaming only each family's memo key
and its family-specific callees. Shared coefficient queries are unchanged.
This is a source-template comparison, not evidence of equal runtime values.

Write `R(s)` for the first returned value of family `104`, `114` or `124` with
suffix s. The checked recurrences are:

```text
R(050) = R(000) * g(21810) / 100
R(120) = R(020) * g(21880) / 100
R(130) = R(020) * g(21890) / 100
R(330) = (R(020) - R(120) - R(130)) * C_c
R(370) = (R(060) - R(180) - R(190)) * C_pc
```

Here X(i) and E(i) mean the checked `_GetAttrValue` queries for attribute i,
with mine tags `{6001100}`, empty other tags, mode X or E, empty filter and
literal flag A:

```text
C_c  = (X(5109) + X(5719) + X(5727) - 2)
       * E(5109) * E(5719) * E(5727)
C_pc = (X(5002) + X(5109) + X(5719) + X(5727) - 3)
       * E(5002) * E(5109) * E(5719) * E(5727)
```

If the coefficients have the same numeric values in all three contexts, an
existing scalar-equals-endpoint-mean identity propagates through these linear
operations. For example, the identity for base `020` suffices for `120`, `130`
and `330`; their mean identities are not independent assumptions. This is real
algebra, without a bound on floating-point differences. The inspected bodies
do not establish coefficient ranges, active effects or native pool semantics.

The `370` branch still needs lower identities for `060`, `180` and `190`.
The full cold sum also contains `400`, `460`, `630` and `690`, outside this
check. Moreover, equal native query arguments do not prove equal results across
outer `GetValue(10103)` and `GetValue(11800)` calls: calculation flags, helper,
stone, frame and cache context can differ. The historical equality of B with
the inverted mean remains an explicit hypothesis.

## Static check locations

| Script | Function | Checked source |
|---|---|---|
| `ExportAttrShow` | `main.52`, `11800` | PC 6–24 and 25–43: separate endpoint sums |
| `ExportAttrShow` | `main.54`–`main.57`, `12000`–`12300` | PC 18–23 and 63–71: different outer endpoint factors |
| `ExportAttrShow` | `main.501`, `104000` | PC 6–73: weighted base expression |
| `ExportAttrShow` | `main.732`, `114000`; `main.963`, `124000` | Base query min/max, effect query and skill-damage query |
| `ExportAttrShow` | `main.506`, `main.737`, `main.968` | `050` conversion-family recurrence |
| `ExportAttrShow` | `main.513`–`main.514`, `main.744`–`main.745`, `main.975`–`main.976` | `120` and `130` conversion-family recurrences |
| `ExportAttrShow` | `main.534`, `main.765`, `main.996` | `330` family and coefficient queries |
| `ExportAttrShow` | `main.538`, `main.769`, `main.1000` | `370` family and coefficient queries |

The function bodies were projected from an already validated complete outline.
Selected child-free bodies were additionally framed as standalone diagnostic
inputs for inspection at unchanged decoder limits; this did not execute them
or establish whole-client runtime semantics.
