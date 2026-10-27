"""Compile explicit Carino Heat states into additional-modifier rows."""

import math
import operator


def _integer(value, label):
    try:
        operator.index(value)
    except TypeError as error:
        raise ValueError(f"{label} must be a nonnegative integer") from error
    if value is True or value is False or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")


def heat(heat: int, rank: int, effect: float, eternal: bool) -> dict:
    """Describe a fixed Heat state with an explicitly supplied effect multiplier.

    The caller supplies the Incinerated Glory rank and final Heat effectiveness.
    Coefficients follow the two Carino Heat rules in data/combat-ss14.json, SS14.
    This function does not infer Burning Red, maximum Heat, ammo, rotation or
    uptime, and does not establish that Tangle inherits these modifiers.
    """
    _integer(heat, "Heat count")
    _integer(rank, "Incinerated Glory rank")
    if not 1 <= rank <= 5:
        raise ValueError("Incinerated Glory rank must be from one through five")
    try:
        if effect is True or effect is False or not math.isfinite(effect) or effect < 0:
            raise ValueError("Heat effect must be a finite nonnegative number")
    except (TypeError, OverflowError) as error:
        raise ValueError("Heat effect must be a finite nonnegative number") from error
    if eternal is not True and eternal is not False:
        raise ValueError("Eternal Flames must be a boolean")
    result = {
        "damage": [{"id": "carino-heat-damage", "affix": "carino-incinerated-glory",
                    "value": (0.016, 0.02, 0.023, 0.026, 0.03)[rank - 1] * effect,
                    "stacks": heat, "mode": "add"}],
        "cast": ([{"id": "carino-heat-cast", "affix": "carino-eternal-flames",
                   "value": 0.004 * effect, "stacks": heat, "mode": "add"}]
                 if eternal else []),
    }
    try:
        for rows in result.values():
            for row in rows:
                if not math.isfinite(1 + row["value"] * row["stacks"]):
                    raise ValueError("Heat contribution must be finite")
    except OverflowError as error:
        raise ValueError("Heat contribution must be finite") from error
    return result
