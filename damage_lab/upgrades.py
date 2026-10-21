"""Compare explicit modifier replacements inside one conditional damage model."""

import copy
import math
import operator

from .combat import apply
from .engine import calculate


def _fields(value, required, label, optional=()):
    try:
        valid = set(required) <= set(value.keys()) <= set(required + optional)
    except AttributeError as error:
        raise ValueError(f"{label} must be an object") from error
    if not valid:
        raise ValueError(f"{label} requires its documented fields without overrides")


def _number(value, minimum, maximum, label, integer=False):
    try:
        if value is True or value is False or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"{label} must be a finite number in its supported range")
        if integer:
            operator.index(value)
    except (TypeError, OverflowError) as error:
        raise ValueError(f"{label} must be a supported number with integer counts") from error


def _text(value, label):
    try:
        if not str.strip(value) or value != str.strip(value):
            raise ValueError(f"{label} must be nonempty trimmed text")
    except TypeError as error:
        raise ValueError(f"{label} must be nonempty trimmed text") from error


def _array(value, label):
    try:
        return value + []
    except TypeError as error:
        raise ValueError(f"{label} must be an array") from error


def _quotient(numerator, denominator, label):
    if not denominator:
        return None
    result = numerator / denominator
    if not math.isfinite(result) or (numerator != 0 and result == 0):
        raise ValueError(f"{label} cannot overflow or underflow")
    return result


def evaluate(document):
    """Evaluate supported candidate deltas without changing shared conditions."""
    _fields(document, ("format", "panel", "condition", "combat", "currency", "candidates"), "Upgrade scenario")
    if document["format"] != "tli-upgrade-scenario-v1":
        raise ValueError("Upgrade scenario format must be tli-upgrade-scenario-v1")
    _text(document["currency"], "Upgrade currency")
    _fields(document["condition"], ("basis", "active", "hits", "retention", "lucky", "critical_more",
                                    "resistance", "taken", "uptime"), "Upgrade conditions")
    if document["condition"]["basis"] not in ("panel", "hit"):
        raise ValueError("Upgrade basis must be panel or hit")
    required = (("spell_dps",) if document["condition"]["basis"] == "panel"
                else ("hit_min", "hit_max", "crit_chance", "crit_multiplier"))
    _fields(document["panel"], ("cast_rate", "max_tangles", "extra_attachments", "cold_penetration") + required,
            "Upgrade panel", ("spell_dps", "hit_min", "hit_max", "crit_chance", "crit_multiplier", "armor_penetration"))
    bounds = {"cast_rate": (0, 1e6), "max_tangles": (0, 4), "extra_attachments": (0, 1000),
              "cold_penetration": (0, 10), "spell_dps": (0, 1e18), "hit_min": (0, 1e18),
              "hit_max": (0, 1e18), "crit_chance": (0, 1), "crit_multiplier": (0, 100),
              "armor_penetration": (0, 1)}
    for field, value in document["panel"].items():
        _number(value, *bounds[field], f"Panel {field}", integer=field in ("max_tangles", "extra_attachments"))
    if ("hit_min" in document["panel"] and "hit_max" in document["panel"]
            and document["panel"]["hit_min"] > document["panel"]["hit_max"]):
        raise ValueError("Hit range must be ordered from minimum to maximum")
    for field, minimum, maximum in (("active", 0, 1000), ("hits", 0, 1000), ("retention", 0, 1),
                                    ("critical_more", -1, 100), ("resistance", -10, 1),
                                    ("taken", -1, 100), ("uptime", 0, 1)):
        _number(document["condition"][field], minimum, maximum, f"Condition {field}",
                integer=field in ("active", "hits"))
    if document["condition"]["lucky"] is not True and document["condition"]["lucky"] is not False:
        raise ValueError("Condition lucky must be a boolean")
    identities = set()
    for candidate in _array(document["candidates"], "Upgrade candidates"):
        _fields(candidate, ("id", "name", "target", "cost", "missing"), "Upgrade candidate")
        _text(candidate["id"], "Candidate id")
        _text(candidate["name"], "Candidate name")
        if candidate["id"] in identities:
            raise ValueError("Duplicate candidate identity")
        identities.add(candidate["id"])
        for gap in _array(candidate["missing"], "Candidate missing effects"):
            _text(gap, "Candidate missing effect")
        if candidate["cost"] is not None:
            _number(candidate["cost"], 0, math.inf, "Candidate cost")
    anchor = calculate(document["panel"], document["condition"])
    baseline = apply(document["panel"], anchor, document["combat"])
    candidates = []
    for candidate in document["candidates"]:
        context = copy.deepcopy(document["combat"])
        context["target"] = copy.deepcopy(candidate["target"])
        context["missing"] = list(dict.fromkeys(context["missing"] + candidate["missing"]))
        result = apply(document["panel"], anchor, context)
        delta = result["dps"] - baseline["dps"]
        cost = candidate["cost"]
        gaps = list(dict.fromkeys(baseline["combat"]["missing"] + result["combat"]["missing"]))
        candidates.append({"id": candidate["id"], "name": candidate["name"],
                           "dps": result["dps"], "delta": delta,
                           "relative": _quotient(delta, baseline["dps"], "Relative gain"),
                           "cost": cost, "per_cost": _quotient(delta, cost, "Gain per cost"),
                           "status": ("incomplete" if gaps else "not_upgrade" if delta <= 0 else "unpriced" if cost is None
                                      else "free" if cost == 0 else "upgrade"),
                           "gaps": gaps, "eligible_for_ranking": not gaps and delta > 0,
                           "eligible_for_cost_ranking": not gaps and delta > 0 and cost is not None,
                           "result": result})
    ranking = sorted((candidate for candidate in candidates if candidate["eligible_for_cost_ranking"]),
                     key=lambda candidate: (candidate["cost"] != 0,
                                            -candidate["per_cost"] if candidate["per_cost"] is not None else 0,
                                            candidate["cost"], candidate["id"]))
    return {"format": "tli-upgrade-report-v1", "status": "conditional", "baseline": baseline,
            "currency": document["currency"], "candidates": candidates,
            "scenario": copy.deepcopy(document), "price_source": "caller",
            "gaps": copy.deepcopy(baseline["combat"]["missing"]),
            "ranking": [candidate["id"] for candidate in ranking]}
