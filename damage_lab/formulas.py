"""Explicit combat formulas independent of panels, catalogs and game access."""

import math
import operator
from fractions import Fraction


def _finite(value, name):
    try:
        if value is True or value is False or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
    except (TypeError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    return value


def _factor(value):
    _finite(value, "Additional factor")
    if value < 0:
        raise ValueError("Additional factor cannot be negative")
    return value


def product(values, *, name="Product"):
    """Multiply finite nonnegative factors without silently losing positive values to zero."""
    result = 1.0
    for value in values:
        _finite(value, f"{name} factor")
        if value < 0:
            raise ValueError(f"{name} factor cannot be negative")
        try:
            current = _finite(result * value, name)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"{name} must be finite") from None
        if current == 0 and result > 0 and value > 0:
            raise ValueError(f"{name} cannot underflow to zero")
        result = current
    return result


def additional(rows):
    """Pool additional fractions by affix, retaining exact additive sums until multiplication."""
    pools = {}
    identities = set()
    modes = {}
    result = 1.0
    for row in rows:
        if not all(field in row for field in ("id", "affix", "value", "stacks", "mode")):
            raise ValueError("Additional row requires id, affix, value, stacks and mode")
        for field in ("id", "affix"):
            try:
                if not str.strip(row[field]):
                    raise ValueError(f"Additional {field} must be nonempty text")
            except TypeError as error:
                raise ValueError(f"Additional {field} must be nonempty text") from error
        if row["mode"] not in ("add", "multiply"):
            raise ValueError("Additional mode must be add or multiply")
        _finite(row["value"], "Additional value")
        _finite(row["stacks"], "Stack count")
        try:
            operator.index(row["stacks"])
        except TypeError as error:
            raise ValueError("Stack count must be a nonnegative integer") from error
        if row["stacks"] < 0:
            raise ValueError("Stack count must be a nonnegative integer")
        if row["id"] in identities:
            raise ValueError("Duplicate modifier instance")
        identities.add(row["id"])
        if row["affix"] in modes and modes[row["affix"]] != row["mode"]:
            raise ValueError("Affix stack mode must be consistent")
        modes[row["affix"]] = row["mode"]
        if row["mode"] == "multiply":
            factor = _factor(1 + row["value"])
            try:
                power = factor ** row["stacks"]
            except OverflowError as error:
                raise ValueError("Additional product must be finite") from error
            if factor > 0 and power == 0:
                raise ValueError("Additional power cannot underflow to zero")
            result = product((result, power), name="Additional product")
        else:
            pools.setdefault(row["affix"], []).append(row["value"] * row["stacks"])
    try:
        return product((result, *(_factor(sum(map(Fraction, (1, *terms)))) for terms in pools.values())),
                       name="Additional product")
    except OverflowError:
        raise ValueError("Additional product must be finite") from None


def tangle_rate(rate, frequency=None):
    """Select continuous casting or an explicit TLIBuilder 30 Hz hypothesis.

    Tick rounding is a scenario option, not an established global SS14 rule.
    The documented 30 casts/s limit is applied per caster.
    """
    _finite(rate, "Cast rate")
    if rate < 0:
        raise ValueError("Cast rate cannot be negative")
    if frequency is not None:
        _finite(frequency, "Tick frequency")
        if frequency != 30:
            raise ValueError("Tick frequency must be 30 or None")
    if rate == 0:
        return 0.0
    if frequency is None:
        return min(rate, 30)
    numerator, denominator = rate.as_integer_ratio()
    ticks = max(1, (30 * denominator + numerator - 1) // numerator)
    return 30 / ticks


def armor(value, nonphysical, *, effectiveness=None, penetration=None, order=None):
    """Return monster mitigation with an optional explicit ordering hypothesis.

    Explicit effectiveness is the final applicable fraction, not a bonus on top
    of the legacy nonphysical default; penetration ordering is not verified.
    """
    if nonphysical is not True and nonphysical is not False:
        raise ValueError("Nonphysical must be a boolean")
    _finite(value, "Armor")
    if value < 0:
        raise ValueError("Armor cannot be negative")
    mitigation = min(0.8, value / (0.9 * value + 30000))
    if effectiveness is None and penetration is None and order is None:
        return mitigation * (0.6 if nonphysical else 1)
    if effectiveness is None or penetration is None or order not in ("after_effectiveness", "before_effectiveness"):
        raise ValueError("Explicit armor requires effectiveness, penetration and a known order")
    for label, fraction in (("Armor effectiveness", effectiveness), ("Armor penetration", penetration)):
        _finite(fraction, label)
        if not 0 <= fraction <= 1:
            raise ValueError(f"{label} must be between zero and one")
    if order == "before_effectiveness":
        return (mitigation - penetration) * effectiveness
    return mitigation * effectiveness - penetration
