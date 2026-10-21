"""Compose a declared raw Cold spell with explicit topology and target conditions."""

import copy
import math

from . import rawspell
from .engine import topology
from .formulas import additional, armor, product


def _object(value, fields, label):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError(f"{label} has missing or unsupported fields")
    return value


def _text(value, label):
    if type(value) is not str or not value or value != value.strip() or len(value) > 1024:
        raise ValueError(f"{label} requires nonempty bounded text without edge whitespace")
    return value


def _texts(value, label):
    if type(value) is not list or len(value) > 1000:
        raise ValueError(f"{label} requires a bounded list of text")
    return [_text(row, label) for row in value]


def _number(value, minimum, maximum, label):
    if type(value) in (int, float):
        try:
            if math.isfinite(value) and minimum <= value <= maximum:
                return value
        except OverflowError:
            pass
    raise ValueError(f"{label} requires a finite number within the supported range")


def _topology(value):
    _object(value, "maximum extra active hits retention", "Combat topology")
    for field, maximum in (("maximum", 4), ("extra", 1000), ("active", 1000), ("hits", 1000)):
        if type(value[field]) is not int or not 0 <= value[field] <= maximum:
            raise ValueError("Combat topology requires bounded nonnegative integers")
    _number(value["retention"], 0, 1, "Shotgun retained fraction")
    return topology(**value)


def _target(value):
    _object(value, "cold_resistance cold_penetration armor armor_effectiveness armor_penetration "
            "armor_penetration_order increased_taken more_taken", "Combat target")
    for field, minimum, maximum in (("cold_resistance", -10, 1), ("cold_penetration", 0, 10),
                                    ("armor", 0, math.inf), ("armor_effectiveness", 0, 1),
                                    ("armor_penetration", 0, 1), ("increased_taken", -1, 100)):
        _number(value[field], minimum, maximum, "Combat target value")
    if value["armor_penetration_order"] not in ("after_effectiveness", "before_effectiveness"):
        raise ValueError("Combat armor requires an explicit supported penetration order")
    return value


def _more(value):
    if type(value) is not list or len(value) > 1000:
        raise ValueError("Target additional modifiers require a bounded list")
    for row in value:
        _object(row, "id affix value stacks mode", "Target additional modifier")
        _text(row["id"], "Target modifier identity")
        _text(row["affix"], "Target affix identity")
        _number(row["value"], -1, 1e6, "Target additional modifier")
        if type(row["stacks"]) is not int or not 0 <= row["stacks"] <= 1000:
            raise ValueError("Target modifier stacks require a bounded nonnegative integer")
        if row["mode"] not in ("add", "multiply"):
            raise ValueError("Target modifier mode must be add or multiply")
    return additional(value)


def _gates(value):
    _object(value, "inheritance hit_topology target_state", "Combat gates")
    gaps = []
    for name, gate in value.items():
        _object(gate, "status evidence", "Combat gate")
        if gate["status"] not in ("confirmed", "unknown", "conflict"):
            raise ValueError("Combat gate status must be confirmed unknown or conflict")
        evidence = _texts(gate["evidence"], "Combat gate evidence")
        if gate["status"] == "confirmed" and not evidence:
            raise ValueError("A confirmed combat gate requires evidence references")
        if gate["status"] != "confirmed":
            gaps.append(f"{name}: {gate['status']}")
    return gaps


def evaluate(document):
    """Return conditional combat damage without applying panel or reference-state pools."""
    _object(document, "format spell topology target uptime gates missing notes", "Raw combat scenario")
    if document["format"] != "tli-raw-cold-combat-v1":
        raise ValueError("Unsupported raw combat format")
    spell = rawspell.evaluate(document["spell"])
    gaps = (_gates(document["gates"]) + ["spell: " + gap for gap in spell["gaps"]]
            + _texts(document["missing"], "Missing combat effects"))
    _texts(document["notes"], "Combat notes")
    geometry = _topology(document["topology"])
    target = _target(document["target"])
    _number(document["uptime"], 0, 1, "Combat uptime")
    mitigation = armor(target["armor"], True, effectiveness=target["armor_effectiveness"],
                       penetration=target["armor_penetration"], order=target["armor_penetration_order"])
    factors = {"topology": geometry["factor"],
               "cold_defence": max(0, 1 - target["cold_resistance"] + target["cold_penetration"]),
               "armor": 1 - mitigation, "increased_taken": 1 + target["increased_taken"],
               "more_taken": _more(target["more_taken"]), "uptime": document["uptime"]}
    result = {"format": "tli-raw-cold-combat-report-v1", "status": "blocked" if gaps else "conditional", "dps": None,
            "spell": spell, "topology": None, "factors": None, "armor_mitigation": None,
            "scenario": copy.deepcopy(document), "trace": [], "gaps": gaps,
            "ownership": {
                "spell": ["base and complete damage pools", "ordinary full Physical to Cold conversion",
                          "critical expectation", "cast speed", "per-caster cap and selected tick hypothesis"],
                "combat": ["Tangle attachment and hit topology", "Cold resistance and penetration",
                           "explicit nonphysical armor policy", "complete target damage-taken pools", "uptime"],
                "not_applied": ["panel anchors", "reference-state ratios", "Heat or inferred buffs",
                                "repeated critical or casting factors", "global multi-caster cast cap"]},
            "assumptions": [
                "Gate confirmations are caller assertions, not verified runtime identity or freshness",
                "Tangle inheritance and accepted hits are explicit scenario assertions, not projectile-count inference",
                "The selected armor penetration order is a conditional hypothesis",
                "Target damage-taken rows are complete explicit pools and are applied once",
                "Several casters retain their individual cast caps without a second global cap",
            ]}
    if gaps:
        return result
    value, trace = spell["pre_defence_dps"], []
    for stage, factor in factors.items():
        amount = product([value, factor], name="Combat stage product")
        trace.append({"stage": stage, "input": value, "factor": factor, "output": amount})
        value = amount
    result.update(dps=value, topology=geometry, factors=factors, armor_mitigation=mitigation, trace=trace)
    return result
