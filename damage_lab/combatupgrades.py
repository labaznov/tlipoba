"""Compare caller-priced complete cold combat scenarios under one declared target and uptime."""

import copy
import math

from .rawcombat import evaluate as assemble


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError("Combat upgrade object has missing or unsupported fields")


def _text(value):
    if type(value) is not str or not value or value != value.strip() or len(value) > 1024:
        raise ValueError("Combat upgrade labels require bounded nonempty trimmed text")


def _list(value):
    if type(value) is not list or len(value) > 1000:
        raise ValueError("Combat upgrades require bounded JSON lists")


def _finite(value, label):
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite number")
    try:
        if math.isfinite(value):
            return value
    except OverflowError:
        pass
    raise ValueError(f"{label} must be a finite number")


def _common(baseline, target):
    if baseline["target"] != target["target"] or baseline["uptime"] != target["uptime"]:
        raise ValueError("Combat upgrade variants must share the complete target and uptime")
    for section, field in (("context", "skill_id"), ("context", "catalog_sha256"),
                           ("damage", "roll_model"), ("casting", "frequency")):
        # Shared unknown groups block deltas without asserting a roll or tick policy
        if baseline["spell"][section] is None and target["spell"][section] is None:
            continue
        if (baseline["spell"][section] is None or target["spell"][section] is None
                or baseline["spell"][section][field] != target["spell"][section][field]):
            raise ValueError("Combat upgrade variants must share skill, catalog, roll model and tick hypothesis")


def _quotient(numerator, denominator, label):
    if numerator is None or denominator is None or denominator == 0:
        return None
    value = _finite(numerator / denominator, label)
    if numerator != 0 and value == 0:
        raise ValueError(f"{label} cannot underflow to zero")
    return value


def _status(delta, cost):
    if delta is None:
        return "blocked"
    if delta <= 0:
        return "not_upgrade"
    return "unpriced" if cost is None else "free" if cost == 0 else "upgrade"


def evaluate(document):
    """Return conditional combat deltas from complete replacements and caller-supplied prices."""
    _object(document, "format baseline currency candidates")
    if document["format"] != "tli-combat-upgrade-scenario-v1":
        raise ValueError("Unsupported combat upgrade scenario format")
    _text(document["currency"])
    _list(document["candidates"])
    identities = set()
    for candidate in document["candidates"]:
        _object(candidate, "id name scenario cost missing")
        _text(candidate["id"])
        _text(candidate["name"])
        if candidate["id"] in identities:
            raise ValueError("Duplicate combat upgrade candidate identity")
        identities.add(candidate["id"])
        _list(candidate["missing"])
        for gap in candidate["missing"]:
            _text(gap)
        if candidate["cost"] is not None and _finite(candidate["cost"], "Candidate cost") < 0:
            raise ValueError("Candidate cost must be nonnegative")
    baseline = assemble(document["baseline"])
    candidates = []
    for candidate in document["candidates"]:
        target = copy.deepcopy(candidate["scenario"])
        if type(target) is not dict or "missing" not in target:
            raise ValueError("A combat upgrade candidate requires a complete raw combat scenario")
        _list(target["missing"])
        target["missing"] += candidate["missing"]
        result = assemble(target)
        _common(baseline["scenario"], result["scenario"])
        gaps = list(dict.fromkeys(baseline["gaps"] + result["gaps"]))
        delta = _finite(result["dps"] - baseline["dps"], "Combat damage delta") if not gaps else None
        positive = delta is not None and delta > 0
        cost = candidate["cost"]
        candidates.append({"id": candidate["id"], "name": candidate["name"], "cost": cost,
                           "dps": result["dps"], "delta": delta,
                           "relative": _quotient(delta, baseline["dps"], "Relative gain"),
                           "per_cost": _quotient(delta, cost, "Gain per cost"), "status": _status(delta, cost),
                           "eligible_for_ranking": positive, "eligible_for_cost_ranking": positive and cost is not None,
                           "gaps": gaps, "result": result})
    ranking = sorted((candidate for candidate in candidates if candidate["eligible_for_cost_ranking"]),
                     key=lambda candidate: (candidate["cost"] != 0,
                                            -candidate["per_cost"] if candidate["per_cost"] is not None else 0,
                                            candidate["cost"], candidate["id"]))
    return {"format": "tli-combat-upgrade-report-v1", "status": baseline["status"], "baseline": baseline,
            "currency": document["currency"], "price_source": "caller", "quantity_scope": "conditional_combat_dps",
            "gaps": list(baseline["gaps"]), "candidates": candidates,
            "ranking": [candidate["id"] for candidate in ranking], "scenario": copy.deepcopy(document)}
