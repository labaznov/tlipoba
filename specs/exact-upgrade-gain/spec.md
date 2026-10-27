# Exact upgrade gain

1. The admitted binary value of an int or float is `Fraction(value)`, never `Fraction(str(value))`.
2. A supported combat delta is the difference of the two scenario results computed with that exact product, before the two total DPS figures are rounded independently.
3. The published DPS figures stay on the existing float pipeline, including declared topology rounding and the optional 30 Hz tick hypothesis.
4. Minimum qualification, cheapest eligible choice, ties and affordability use that exact delta. A gain of 62.5 qualifies at 60 and at 62.5, and does not qualify at 63.
5. The serialized delta is a finite float. When the exact gain is a binary float, that float is the gain. Otherwise it is the nearest finite float of the exact gain, not the difference of two rounded DPS totals. It is not a Fraction or Decimal.
6. Decimal strings in damage fields stay rejected. A modifier `exact_value` keeps its existing fraction semantics.
7. Missing or unsupported groups still block the delta. Prices stay caller-supplied.
8. A separate physical addend is lifted before it is added to the base. Base 999999999999900 and physical 0.578125 at critical factor 100 gain 57.8125, so minimum 60 selects the dear row. The single admitted base whose residual is 5/8 still gains 62.5.
9. In exact evaluation every admitted int or float becomes its binary fraction before addition, subtraction, division or multiplication. Declared topology rounding and the 30 Hz tick hypothesis stay as they are.
10. Minimum qualification, ranking and ties use that exact gain. The published delta remains a finite float, with no Fraction or Decimal in the report.
11. In exact mode an affix stack multiplies the admitted value by the integer stack count before the sum, and a multiply row adds one before the power. Value 0.1 with 3 stacks stays below 2.9999999999997004e16 when added and below 3.309999999999671e16 when multiplied. A multiply row of 2^-54 at base 1 and critical factor 1 gains 2^-54.
12. A nonzero exact gain whose nearest float is zero raises ValueError before a report is returned, for a gain and for a loss. An exact zero stays zero. A nonzero subnormal float is returned.
13. An exact product or power whose numerator and denominator together would exceed 262144 bits raises ValueError before that operation. A result of exactly 262144 bits is allowed. Zero and one skip the multiply. The float pipeline is unchanged.
