"""Evaluate post-20 additional skill damage for caller-selected rate fractions."""

import math


class GrowthError(ValueError):
    """A growth input or result outside the supported numeric contract."""


def _rate(value):
    if type(value) not in (int, float):
        raise GrowthError("Rates must be finite nonnegative representable numbers")
    try:
        result = float(value)
    except OverflowError:
        raise GrowthError("Rates must be finite nonnegative representable numbers") from None
    if not math.isfinite(result) or result < 0:
        raise GrowthError("Rates must be finite nonnegative representable numbers")
    return result


def multiplier(level, *, first_rate, later_rate):
    """Return the selected 21–30 and 31+ growth factors without choosing a game profile.

    This is only a mathematical operator, not an effective-level resolver or a
    verified current-season rule, and must not be applied again to a panel.
    """
    if type(level) is not int or level < 1:
        raise GrowthError("Level must be a positive integer")
    first, later = _rate(first_rate), _rate(later_rate)
    if level <= 20:
        return 1.0
    try:
        exponent = 0.0
        for rate, count in ((first, min(level, 30) - 20), (later, max(level - 30, 0))):
            if rate and count:
                numerator, denominator = math.log1p(rate).as_integer_ratio()
                exponent += count * numerator / denominator
        result = math.exp(exponent)
    except OverflowError:
        raise GrowthError("Growth exceeds the finite numeric range") from None
    if not math.isfinite(result):
        raise GrowthError("Growth exceeds the finite numeric range")
    return result
