"""Resolve explicit critical-stat pools without hit expectation, imports or game verification."""

import copy
import math
import re

from .formulas import additional, product


FORMAT = "tli-critical-stat-scenario-v1"
GATES = ("version", "base", "scope", "activation", "completeness", "operator")


def _object(value, fields, label):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError(f"{label} has missing or unsupported fields")
    return value


def _number(value, label, *, minimum=0, maximum=None):
    if type(value) in (int, float):
        try:
            if math.isfinite(value) and value >= minimum and (maximum is None or value <= maximum):
                return value
        except OverflowError:
            pass
    raise ValueError(f"{label} must be a finite number within the supported range")


def _text(value, label):
    if (type(value) is not str or not value or value != value.strip() or len(value) > 1024
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ValueError(f"{label} must be bounded nonempty text without edge whitespace or control characters")
    return value


def _evidence(value):
    if type(value) is not list or len(value) > 1000:
        raise ValueError("Gate evidence must be a bounded list of references")
    for entry in value:
        _text(entry, "Evidence reference")
    return value


def _sum(value, label, *, increased=False):
    if value is None:
        return None
    if type(value) is not list or len(value) > 1000:
        raise ValueError(f"{label} must be a bounded numeric list or null")
    for entry in value:
        _number(entry, label, minimum=-1 if increased else 0, maximum=1e6 if increased else None)
    try:
        result = math.fsum(value)
    except OverflowError:
        raise ValueError(f"{label} sum must be finite") from None
    if not math.isfinite(result):
        raise ValueError(f"{label} sum must be finite")
    return result


def _more(value):
    if value is None:
        return None
    if type(value) is not list or len(value) > 1000:
        raise ValueError("Critical-stat more modifiers must be a bounded list or null")
    for row in value:
        _object(row, "id affix value stacks mode", "Critical-stat more modifier")
        _text(row["id"], "Modifier identity")
        _text(row["affix"], "Affix identity")
        _number(row["value"], "Critical-stat more fraction", minimum=-1, maximum=1e6)
        if type(row["stacks"]) is not int or not 0 <= row["stacks"] <= 1000:
            raise ValueError("Modifier stacks must be an integer within the supported range")
        if row["mode"] not in ("add", "multiply"):
            raise ValueError("Modifier mode must be add or multiply")
    return additional(value)


def _quotient(value, divisor):
    try:
        result = value / divisor
    except (OverflowError, ZeroDivisionError):
        raise ValueError("Critical chance quotient must be finite") from None
    _number(result, "Critical chance quotient")
    if value > 0 and result == 0:
        raise ValueError("Critical chance quotient cannot underflow to zero")
    return result


def evaluate(document):
    """Return conditional full critical stats or blocked nulls under explicit caller evidence gates."""
    _object(document, "format context gates rating damage", "Critical-stat scenario")
    if document["format"] != FORMAT:
        raise ValueError("Unsupported critical-stat format")
    context = _object(document["context"], "source_sha256 skill_alias", "Critical-stat context")
    if type(context["source_sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", context["source_sha256"]):
        raise ValueError("Critical-stat context requires a lowercase source SHA256 hash")
    if type(context["skill_alias"]) is not str or not re.fullmatch(r"gem\[[1-9][0-9]{0,8}\]", context["skill_alias"], re.ASCII):
        raise ValueError("Critical-stat context requires an explicit positive gem alias up to nine digits")
    gates = document["gates"]
    if type(gates) is not dict or not set(gates).issubset(GATES):
        raise ValueError("Critical-stat gates contain unsupported fields")
    gaps = []
    for name in GATES:
        if name not in gates:
            gaps.append(name + ": missing")
            continue
        gate = _object(gates[name], "status evidence", "Evidence gate")
        if gate["status"] not in ("confirmed", "unknown", "conflict"):
            raise ValueError("Evidence gate status must be confirmed, unknown or conflict")
        if not _evidence(gate["evidence"]) and gate["status"] == "confirmed":
            raise ValueError("A confirmed gate requires evidence references")
        if gate["status"] != "confirmed":
            gaps.append(name + ": " + gate["status"])
    rating = _object(document["rating"], "base increased more divisor cap", "Critical rating")
    damage = _object(document["damage"], "base increased policy more", "Critical damage")
    for name, pool in (("rating", rating), ("damage", damage)):
        gaps.extend(name + "." + field + ": unknown" for field in pool if pool[field] is None)
    base = _sum(rating["base"], "Base critical rating")
    increased = _sum(rating["increased"], "Ordinary critical rating", increased=True)
    factor = None if increased is None else _number(1 + increased, "Ordinary critical rating factor")
    more = _more(rating["more"])
    divisor = None if rating["divisor"] is None else _number(rating["divisor"], "Rating divisor")
    if divisor == 0:
        raise ValueError("Rating divisor must be positive")
    cap = None if rating["cap"] is None else _number(rating["cap"], "Critical chance cap", maximum=1)
    multiplier = None if damage["base"] is None else _number(damage["base"], "Base full critical multiplier")
    bonuses = _sum(damage["increased"], "Ordinary critical damage", increased=True)
    scaling = _more(damage["more"])
    policy = damage["policy"]
    if policy is not None and policy not in ("percentage_points", "relative_to_base"):
        raise ValueError("Critical damage policy must be percentage_points or relative_to_base")
    adjusted = None
    if policy == "percentage_points" and multiplier is not None and bonuses is not None:
        adjusted = _number(multiplier + bonuses, "Adjusted full critical multiplier")
    elif policy == "relative_to_base" and bonuses is not None:
        ordinary = _number(1 + bonuses, "Ordinary critical damage factor")
        if multiplier is not None:
            adjusted = product((multiplier, ordinary), name="Adjusted full critical multiplier")
    rated = None if any(value is None for value in (base, factor, more)) else product((base, factor, more), name="Critical rating")
    uncapped = None if rated is None or divisor is None else _quotient(rated, divisor)
    chance = None if uncapped is None or cap is None else min(cap, uncapped)
    full = None if adjusted is None or scaling is None else product((adjusted, scaling), name="Full critical multiplier")
    result = {"format": "tli-critical-stat-report-v1", "status": "blocked" if gaps else "conditional",
              "rating": None, "chance": None, "multiplier": None, "trace": [], "gaps": gaps,
              "scenario": copy.deepcopy(document), "assumptions": [
                  "Source hashes and evidence gates are caller assertions; runtime identity and freshness are not verified",
                  "Rating divisor and chance cap are explicit scenario choices, not inferred game constants",
                  "Ordinary critical damage uses only the explicit policy; the current game operator is not established",
                  "More rows modify the full critical stat, not damage of a critical hit",
                  "Lucky critical chance, Lucky damage and critical-only hit more remain outside these pools",
                  "No native effect, support 7420, panel, benchmark, hit expectation or DPS is mapped or applied",
              ]}
    if gaps:
        return result
    result.update(rating=rated, chance=chance, multiplier=full, trace=[
        {"label": "Base critical rating", "value": base, "unit": "rating"},
        {"label": "Ordinary critical rating factor", "value": factor, "unit": "multiplier"},
        {"label": "Grouped critical rating more", "value": more, "unit": "multiplier"},
        {"label": "Critical rating", "value": rated, "unit": "rating"},
        {"label": "Explicit rating divisor", "value": divisor, "unit": "rating_per_probability"},
        {"label": "Uncapped critical chance", "value": uncapped, "unit": "fraction"},
        {"label": "Explicit critical chance cap", "value": cap, "unit": "fraction"},
        {"label": "Critical chance", "value": chance, "unit": "fraction"},
        {"label": "Base full critical multiplier", "value": multiplier, "unit": "multiplier"},
        {"label": "Ordinary critical damage bonuses", "value": bonuses, "unit": "fraction"},
        {"label": "Ordinary critical damage policy", "policy": policy},
        {"label": "Critical multiplier before more", "value": adjusted, "unit": "multiplier"},
        {"label": "Grouped critical damage stat more", "value": scaling, "unit": "multiplier"},
        {"label": "Full critical multiplier", "value": full, "unit": "multiplier"},
    ])
    return result
