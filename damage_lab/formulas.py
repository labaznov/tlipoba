"""Explicit combat formulas independent of panels, catalogs and game access."""

import math
import operator


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


def additional(rows):
    """Pool supplied additional fractions by explicit affix identity."""
    pools = {}
    identities = set()
    modes = {}
    product = 1.0
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
            try:
                product *= _factor(1 + row["value"]) ** row["stacks"]
            except OverflowError as error:
                raise ValueError("Additional product must be finite") from error
        else:
            pools[row["affix"]] = pools.get(row["affix"], 0) + row["value"] * row["stacks"]
    return _finite(product * math.prod(_factor(1 + value) for value in pools.values()), "Additional product")


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


def armor(value, nonphysical):
    """Return monster armor mitigation before armor-penetration ordering."""
    if nonphysical is not True and nonphysical is not False:
        raise ValueError("Nonphysical must be a boolean")
    _finite(value, "Armor")
    if value < 0:
        raise ValueError("Armor cannot be negative")
    return min(0.8, value / (0.9 * value + 30000)) * (0.6 if nonphysical else 1)
