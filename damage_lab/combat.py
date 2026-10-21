"""Apply explicit combat changes to an already calculated damage anchor."""

import copy
import math

from damage_lab import formulas


def _fields(value, names, label):
    try:
        valid = set(value.keys()) == set(names)
    except AttributeError as error:
        raise ValueError(f"{label} must be an object") from error
    if not valid:
        raise ValueError(f"{label} requires exactly {', '.join(names)}")


def _array(value, label):
    try:
        return value + []
    except TypeError as error:
        raise ValueError(f"{label} must be an array") from error


def _texts(value, label):
    entries = _array(value, label)
    try:
        for entry in entries:
            str.strip(entry)
    except TypeError as error:
        raise ValueError(f"{label} must contain text") from error
    return entries


def _factor(value, label):
    rows = _array(value, label)
    for row in rows:
        _fields(row, ("id", "affix", "value", "stacks", "mode"), f"{label} modifier")
    return formulas.additional(rows)


def _ratio(context, layer):
    reference = _factor(context["reference"][layer], f"Reference {layer}")
    if reference <= 0:
        raise ValueError(f"Reference {layer} factor must be positive")
    return _factor(context["target"][layer], f"Target {layer}") / reference


def apply(panel, anchor, context):
    """Return the anchor after applying reference-relative combat conditions."""
    _fields(context, ("reference", "target", "tick_frequency", "armor", "nonphysical",
                      "missing", "notes"), "Combat context")
    _fields(context["reference"], ("damage", "cast", "taken"), "Reference context")
    _fields(context["target"], ("damage", "cast", "taken"), "Target context")
    missing = _texts(context["missing"], "Missing coverage")
    notes = _texts(context["notes"], "Combat notes")
    result = copy.deepcopy(anchor)
    ratios = {layer: _ratio(context, layer) for layer in ("damage", "cast", "taken")}
    rate = formulas.tangle_rate(panel["cast_rate"])
    if rate == 0 and anchor["dps"] != 0:
        raise ValueError("Zero cast rate requires zero anchor DPS")
    actual = formulas.tangle_rate(panel["cast_rate"] * ratios["cast"],
                                 frequency=context["tick_frequency"])
    mitigation = formulas.armor(context["armor"], context["nonphysical"])
    ratios["cast"] = actual / rate if rate else 1.0
    result["status"] = "conditional"
    result["dps"] *= ratios["damage"] * ratios["cast"] * ratios["taken"] * (1 - mitigation)
    if not math.isfinite(result["dps"]):
        raise ValueError("Combat DPS must be finite")
    result["trace"].extend([
        {"label": "Дополнительный урон: отношение боевого состояния к исходному", "factor": ratios["damage"]},
        {"label": "Частота сотворения: отношение боевого состояния к исходной панели", "factor": ratios["cast"]},
        {"label": "Получаемый урон: отношение боевого состояния к исходному", "factor": ratios["taken"]},
        {"label": "Броня цели до пробивания: оставшаяся доля урона", "factor": 1 - mitigation},
    ])
    result["assumptions"].extend(notes + [f"Не учтено: {entry}" for entry in missing]
                                 + ["Пробивание брони не моделируется"])
    result["combat"] = {
        "damage_ratio": ratios["damage"], "cast_ratio": ratios["cast"],
        "taken_ratio": ratios["taken"], "actual_cast_rate": actual,
        "armor_mitigation": mitigation, "missing": missing,
    }
    return result
