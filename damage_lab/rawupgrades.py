"""Compare complete raw spell scenarios before target defence or Tangle topology."""

import copy
import math

from .rawspell import evaluate as assemble


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError("Raw upgrade object has missing or unsupported fields")


def _text(value):
    if type(value) is not str or not value or value != value.strip() or len(value) > 1024:
        raise ValueError("Raw upgrade labels require bounded nonempty trimmed text")


def _list(value):
    if type(value) is not list or len(value) > 1000:
        raise ValueError("Raw upgrades require bounded JSON lists")


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
    if baseline["format"] != target["format"]:
        raise ValueError("Raw upgrade variants must share the spell model version")
    for section, field in (("context", "skill_id"), ("context", "catalog_sha256"),
                           ("damage", "roll_model"), ("casting", "frequency")):
        # Shared unknown groups block deltas without asserting a roll or tick policy
        if baseline[section] is None and target[section] is None:
            continue
        if baseline[section] is None or target[section] is None or baseline[section][field] != target[section][field]:
            raise ValueError("Raw upgrade variants must share skill, catalog, roll model and tick hypothesis")


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
    """Return caller-priced, conditional single-caster comparisons from complete replacements."""
    _object(document, "format baseline currency candidates")
    if document["format"] != "tli-raw-upgrade-scenario-v1":
        raise ValueError("Unsupported raw upgrade scenario format")
    _text(document["currency"])
    _list(document["candidates"])
    identities = set()
    for candidate in document["candidates"]:
        _object(candidate, "id name scenario cost missing")
        _text(candidate["id"])
        _text(candidate["name"])
        if candidate["id"] in identities:
            raise ValueError("Duplicate raw upgrade candidate identity")
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
            raise ValueError("A raw upgrade candidate requires a complete raw spell scenario")
        _list(target["missing"])
        target["missing"] += candidate["missing"]
        result = assemble(target)
        _common(baseline["scenario"], result["scenario"])
        gaps = list(dict.fromkeys(baseline["gaps"] + result["gaps"]))
        delta = _finite(result["pre_defence_dps"] - baseline["pre_defence_dps"], "Raw damage delta") if not gaps else None
        positive = delta is not None and delta > 0
        cost = candidate["cost"]
        candidates.append({"id": candidate["id"], "name": candidate["name"], "cost": cost,
                           "pre_defence_dps": result["pre_defence_dps"],
                           "delta": delta, "relative": _quotient(delta, baseline["pre_defence_dps"], "Relative gain"),
                           "per_cost": _quotient(delta, cost, "Gain per cost"), "status": _status(delta, cost),
                           "eligible_for_ranking": positive, "eligible_for_cost_ranking": positive and cost is not None,
                           "gaps": gaps, "result": result})
    ranking = sorted((candidate for candidate in candidates if candidate["eligible_for_cost_ranking"]),
                     key=lambda candidate: (candidate["cost"] != 0,
                                            -candidate["per_cost"] if candidate["per_cost"] is not None else 0,
                                            candidate["cost"], candidate["id"]))
    return {"format": "tli-raw-upgrade-report-v1", "status": baseline["status"], "baseline": baseline,
            "currency": document["currency"], "price_source": "caller", "quantity_scope": "pre_defence_single_caster",
            "gaps": list(baseline["gaps"]), "candidates": candidates,
            "ranking": [candidate["id"] for candidate in ranking], "scenario": copy.deepcopy(document)}
