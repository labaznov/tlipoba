"""Apply explicit combat changes to an already calculated damage anchor."""

import copy
import math

from damage_lab import formulas
from .carino import heat


def _fields(value, names, label, optional=()):
    try:
        keys = set(value.keys())
        valid = set(names) <= keys <= set(names + optional)
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


def _rows(value, label):
    rows = _array(value, label)
    for row in rows:
        _fields(row, ("id", "affix", "value", "stacks", "mode"), f"{label} modifier")
    return rows


def _factor(value, label):
    return formulas.additional(_rows(value, label))


def _ratio(context, layer):
    reference = _factor(context["reference"][layer], f"Reference {layer}")
    if reference <= 0:
        raise ValueError(f"Reference {layer} factor must be positive")
    return _factor(context["target"][layer], f"Target {layer}") / reference


def apply(panel, anchor, context):
    """Return the anchor after applying reference-relative combat conditions."""
    fields = ("armor_penetration", "armor_effectiveness", "armor_penetration_order")
    _fields(context, ("reference", "target", "tick_frequency", "armor", "nonphysical",
                      "missing", "notes"), "Combat context", ("carino",) + fields)
    selected = {field for field in fields if field in context}
    if selected and len(selected) != len(fields):
        raise ValueError("Combat context requires exactly all three armor penetration fields together")
    if selected and any(context[field] is None for field in fields):
        raise ValueError("Combat armor parameters require explicit values and an order")
    _fields(context["reference"], ("damage", "cast", "taken"), "Reference context")
    _fields(context["target"], ("damage", "cast", "taken"), "Target context")
    missing = _texts(context["missing"], "Missing coverage")
    notes = _texts(context["notes"], "Combat notes")
    if selected:
        missing.append("Порядок применения пробивания и эффективности брони не подтверждён")
        notes.append(f"Порядок брони выбран как гипотеза сценария: {context['armor_penetration_order']}")
    if "carino" in context:
        context = copy.deepcopy(context)
        hero = context["carino"]
        _fields(hero, ("rank", "eternal", "reference", "target"), "Carino context")
        for state in ("reference", "target"):
            _fields(hero[state], ("heat", "effect"), f"Carino {state}")
            for layer in ("damage", "cast", "taken"):
                for row in _rows(context[state][layer], f"{state} {layer}"):
                    if (row["id"] in ("carino-heat-damage", "carino-heat-cast")
                            or row["affix"] in ("carino-incinerated-glory", "carino-eternal-flames")):
                        raise ValueError("Carino modifiers cannot be supplied manually with compiled Heat states")
            rows = heat(hero[state]["heat"], hero["rank"], hero[state]["effect"], hero["eternal"])
            for layer in ("damage", "cast"):
                context[state][layer] = _array(context[state][layer], f"{state} {layer}") + rows[layer]
        missing.append("Наследование Heat модификаторов Tangle не подтверждено")
        notes.append("Heat, ранг свойства и итоговая эффективность заданы явно; Burning Red и цикл перезарядки не выводились")
    result = copy.deepcopy(anchor)
    if selected:
        limitation = "Броня учитывается только при явном боевом контексте; пробивание брони не реализовано"
        result["assumptions"] = [
            "Броня учитывается при явном боевом контексте" if entry == limitation else entry
            for entry in result["assumptions"] if entry != "Пробивание брони не моделируется"
        ]
    ratios = {layer: _ratio(context, layer) for layer in ("damage", "cast", "taken")}
    rate = formulas.tangle_rate(panel["cast_rate"])
    if rate == 0 and anchor["dps"] != 0:
        raise ValueError("Zero cast rate requires zero anchor DPS")
    actual = formulas.tangle_rate(panel["cast_rate"] * ratios["cast"],
                                 frequency=context["tick_frequency"])
    armor = ({"effectiveness": context["armor_effectiveness"],
              "penetration": context["armor_penetration"], "order": context["armor_penetration_order"]}
             if selected else {})
    if selected and "armor_penetration" in panel:
        observed = panel["armor_penetration"]
        try:
            if observed is True or observed is False or not math.isfinite(observed) or not 0 <= observed <= 1:
                raise ValueError("Panel armor penetration must be a finite fraction between zero and one")
        except (TypeError, OverflowError) as error:
            raise ValueError("Panel armor penetration must be a finite fraction between zero and one") from error
    if selected and armor["penetration"] == "panel":
        if "armor_penetration" not in panel:
            raise ValueError("Panel armor penetration is missing")
        armor["penetration"] = panel["armor_penetration"]
    if selected and "armor_penetration" in panel and armor["penetration"] != panel["armor_penetration"]:
        raise ValueError("Combat armor penetration must match the imported panel value")
    mitigation = formulas.armor(context["armor"], context["nonphysical"], **armor)
    ratios["cast"] = actual / rate if rate else 1.0
    result["status"] = "conditional"
    result["dps"] *= ratios["damage"] * ratios["cast"] * ratios["taken"] * (1 - mitigation)
    if not math.isfinite(result["dps"]):
        raise ValueError("Combat DPS must be finite")
    if selected:
        result["trace"].append({"label": ("Пробивание редукции брони из панели" if "armor_penetration" in panel
                                          else "Пробивание редукции брони задано сценарием"),
                                "value": armor["penetration"], "unit": "fraction"})
    result["trace"].extend([
        {"label": "Дополнительный урон: отношение боевого состояния к исходному", "factor": ratios["damage"]},
        {"label": "Частота сотворения: отношение боевого состояния к исходной панели", "factor": ratios["cast"]},
        {"label": "Получаемый урон: отношение боевого состояния к исходному", "factor": ratios["taken"]},
        {"label": ("Броня цели с явной гипотезой пробивания: оставшаяся доля урона" if selected
                   else "Броня цели до пробивания: оставшаяся доля урона"), "factor": 1 - mitigation},
    ])
    result["assumptions"].extend(notes + [f"Не учтено: {entry}" for entry in missing]
                                 + ([] if selected else ["Пробивание брони не моделируется"]))
    result["combat"] = {
        "damage_ratio": ratios["damage"], "cast_ratio": ratios["cast"],
        "taken_ratio": ratios["taken"], "actual_cast_rate": actual,
        "armor_mitigation": mitigation, "missing": missing,
    }
    if selected:
        result["combat"].update(armor_effectiveness=armor["effectiveness"],
                                armor_penetration=armor["penetration"], armor_penetration_order=armor["order"],
                                armor_penetration_source="panel" if "armor_penetration" in panel else "scenario")
    return result
