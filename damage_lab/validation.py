"""Compare independent measurements without fitting the damage model.

Matching figures do not establish that a model covers every damage mechanic.
"""

import math


def _number(value, label):
    try:
        if value is True or value is False or not math.isfinite(value) or value < 0:
            raise ValueError(f"{label} must be a finite nonnegative number")
    except (TypeError, OverflowError) as error:
        raise ValueError(f"{label} must be a finite nonnegative number") from error


def compare(predicted, measured):
    """Return signed discrepancies while preserving both original values."""
    _number(predicted, "Predicted DPS")
    _number(measured, "Measured DPS")
    difference = predicted - measured
    result = {
        "predicted": predicted, "measured": measured, "difference": difference,
        "relative_error": difference / measured if measured > 0 else None,
        "measured_to_predicted": measured / predicted if predicted > 0 else None,
    }
    for name, value in result.items():
        if value is not None and not math.isfinite(value):
            raise ValueError(f"Comparison {name} must be finite")
    return result
