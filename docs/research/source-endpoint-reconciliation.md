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
suffix s. The checked recurrences describe the calculation branch or coherent
memo contents, not an arbitrary stale cached result:

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

Further exact template comparisons close the remaining cold-tail recurrences.
Set `p10=g(21810)/100`, `p20=g(21820)/100`, `p50=g(21850)/100`,
`p80=g(21880)/100`, `p90=g(21890)/100`. In real algebra:

```text
R(060) = R(000)*p20
R(180) = R(000)*p20*p80
R(190) = R(000)*p20*p90
R(090) = R(010)*p50
R(150) = R(000)*p10*p50
R(210) = R(010)*p50*p80
R(220) = R(010)*p50*p90
R(250) = R(000)*p10*p50*p80
R(260) = R(000)*p10*p50*p90
```

These bodies call their base directly, rather than necessarily evaluating the
intermediate recurrence. Source multiplication/division order is retained in
the private inspection; these factored expressions do not guarantee identical
floating-point rounding. With V using the same query arguments above but mode V:

```text
C_gc  = (X(5108)+X(5109)+X(5719)+X(5727)-3)
        * E(5108)*E(5109)*E(5719)*E(5727)
C_pgc = (X(5002)+X(5108)+X(5109)+X(5719)+X(5727)-4)
        * E(5002)*E(5108)*E(5109)*E(5719)*E(5727)
d = 1-p80-p90
v31 = V(5131)/100
v15 = V(5415)/100

R(330) = R(020)*d*C_c
R(370) = R(000)*p20*d*C_pc
R(400) = R(010)*p50*d*C_gc
R(460) = R(000)*p10*p50*d*C_pgc
R(630) = R(000)*v31*C_pc
R(690) = R(010)*v15*C_gc
```

For family f, let T_f be the source sum of those six terms and define
`delta(s)=R_104(s)-(R_114(s)+R_124(s))/2`. Shared numeric coefficients and
coherent calculation state then give:

```text
a0 = (p20*d+v31)*C_pc + p10*p50*d*C_pgc
a1 = (p50*d+v15)*C_gc
a2 = d*C_c
T_f = a0*R_f(000) + a1*R_f(010) + a2*R_f(020)
delta(T) = a0*delta(000) + a1*delta(010) + a2*delta(020)
```

Thus three base mean identities are sufficient for the internal cold-sum
identity. They are not necessary individually: defects could cancel or a
coefficient could vanish. No such cancellation, zero, coefficient range or
actual native value is established here.

## The scalar cold wrapper has an additional condition

Getter `105020` first queries label `3001160` with mine tags `{6001100}`,
empty other tags and mode L. If the value equals 1 it returns zero, without
evaluating the later factor or six terms. Otherwise it computes
`alpha=1+0.01*(V(5106)-30)` and multiplies the scalar cold sum by it.
The corresponding endpoint getters `115020` and `125020` multiply their
six-term sums by literal 1, without that label query or factor.

Let J be zero for the suppressed branch and one otherwise. For finite, defined
comparison quantities, the compact real-algebra notation is:

```text
g(105020) = J*alpha*T_104
g(115020) = T_114
g(125020) = T_124
M = (T_114+T_124)/2
g(105020)-M = J*alpha*delta(T) + (J*alpha-1)*M
```

This product notation does not mean the suppressed source branch evaluates
alpha or T. Even with the internal mean identity and nonzero M, equality needs
J*alpha=1. Actual label and V values remain unknown. No branch selection is
inferred solely from a historical observed zero or nonzero.

Equal native query arguments also do not prove equal results across outer
`GetValue(10103)` and `GetValue(11800)` calls: calculation flags, helper,
stone, frame and cache context can differ. The endpoint wrappers, U(0), 12400
and scoped-query obligations above remain open. The historical equality of B
with the inverted mean remains an explicit hypothesis; no raw DPS gate changes.

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
| `ExportAttrShow` | `main.507`, `main.738`, `main.969`; `main.519`–`main.520`, `main.750`–`main.751`, `main.981`–`main.982` | `060`, `180`, `190` scaled base terms |
| `ExportAttrShow` | `main.510`, `main.741`, `main.972`; `main.516`, `main.747`, `main.978` | `090` and `150` scaled base terms |
| `ExportAttrShow` | `main.522`–`main.523`, `main.753`–`main.754`, `main.984`–`main.985`; `main.526`–`main.527`, `main.757`–`main.758`, `main.988`–`main.989` | `210`, `220`, `250`, `260` scaled base terms |
| `ExportAttrShow` | `main.541`, `main.772`, `main.1003`; `main.547`, `main.778`, `main.1009` | `400` and `460` coefficient branches |
| `ExportAttrShow` | `main.564`, `main.795`, `main.1026`; `main.570`, `main.801`, `main.1032` | `630` and `690` V-query branches |
| `ExportAttrShow` | `main.575`, `main.806`, `main.1037` | `105020` PC 6–57 label/factor/sum; endpoint sums PC 6–29 |

The function bodies were projected from an already validated complete outline.
Selected child-free bodies were additionally framed as standalone diagnostic
inputs for inspection at unchanged decoder limits; this did not execute them
or establish whole-client runtime semantics.
