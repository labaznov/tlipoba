"""Compare caller-priced complete cold combat scenarios under one declared target and uptime."""

import copy
import datetime
import math
import re
from fractions import Fraction

from .rawcombat import evaluate as assemble


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError("Combat upgrade object has missing or unsupported fields")


def _text(value):
    if type(value) is not str or not value or value != value.strip() or len(value) > 1024:
        raise ValueError("Combat upgrade labels require bounded nonempty trimmed text")


# Gregorian date, uppercase T, seconds, 1..6 fraction digits and uppercase Z or a signed HH:MM offset
_STAMP = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]{1,6})?"
                    r"(?:Z|[+-]([0-9]{2}):([0-9]{2}))", re.ASCII)


def _evidence(value):
    """Caller price evidence: an unverified source label and an admitted lexical timestamp, each possibly unknown."""
    _object(value, "source observed_at")
    if value["source"] is not None:
        _text(value["source"])
    stamp = value["observed_at"]
    if stamp is not None:
        match = _STAMP.fullmatch(stamp) if type(stamp) is str else None
        if match is None:
            raise ValueError("Candidate price time requires an offset timestamp")
        year, month, day, hour, minute, second, *offset = (None if part is None else int(part)
                                                           for part in match.groups())
        try:
            datetime.date(year, month, day)
        except ValueError:
            raise ValueError("Candidate price time requires a valid date") from None
        if hour > 23 or minute > 59 or second > 59 or (offset[0] is not None and (offset[0] > 23 or offset[1] > 59)):
            raise ValueError("Candidate price time requires a valid time and offset")
    return {"source": value["source"], "observed_at": stamp}


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
    if baseline["format"] != target["format"]:
        raise ValueError("Combat upgrade variants must share the combat contract version")
    if baseline["spell"]["format"] != target["spell"]["format"]:
        raise ValueError("Combat upgrade variants must share the spell model version")
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


def _plain(value):
    if type(value) is not Fraction:
        raise ValueError("Exact upgrade gain must be a fraction of the admitted operands")
    if value == 0:
        return 0.0
    number = float(value)
    if number == 0:
        raise ValueError("Combat damage delta cannot underflow to zero")
    if not math.isfinite(number):
        raise ValueError("Combat damage delta must be finite")
    return number


def _rank_key(candidate):
    exact, cost = candidate["exact"], candidate["cost"]
    if exact is None or cost in (None, 0):
        ratio = 0
    else:
        ratio = exact / Fraction(cost)
    return (cost != 0, -ratio, cost, candidate["id"])


def _status(delta, cost):
    if delta is None:
        return "blocked"
    if delta <= 0:
        return "not_upgrade"
    return "unpriced" if cost is None else "free" if cost == 0 else "upgrade"


def evaluate(document):
    """Return conditional combat deltas from complete replacements and caller-supplied prices."""
    report, _gains = _measured(document)
    return report


def exact_deltas(document):
    """Private exact gains for qualification and ties. They are not report fields."""
    _report, gains = _measured(document)
    return gains


def _measured(document):
    _object(document, "format baseline currency candidates")
    if document["format"] not in ("tli-combat-upgrade-scenario-v1", "tli-combat-upgrade-scenario-v2"):
        raise ValueError("Unsupported combat upgrade scenario format")
    evidenced = document["format"] == "tli-combat-upgrade-scenario-v2"
    _text(document["currency"])
    _list(document["candidates"])
    identities = set()
    for candidate in document["candidates"]:
        _object(candidate, "id name scenario cost missing" + (" price_evidence" if evidenced else ""))
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
        if evidenced:
            _evidence(candidate["price_evidence"])
    baseline = assemble(document["baseline"])
    baseline_exact = None if baseline["gaps"] else assemble(document["baseline"], exact=True)["dps"]
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
        if gaps:
            exact = None
            delta = None
        else:
            exact = assemble(target, exact=True)["dps"] - baseline_exact
            delta = _plain(exact)
        positive = exact is not None and exact > 0
        cost = candidate["cost"]
        candidates.append({"id": candidate["id"], "name": candidate["name"], "cost": cost,
                           "dps": result["dps"], "delta": delta,
                           "relative": _quotient(delta, baseline["dps"], "Relative gain"),
                           "per_cost": _quotient(delta, cost, "Gain per cost"), "status": _status(delta, cost),
                           "eligible_for_ranking": positive, "eligible_for_cost_ranking": positive and cost is not None,
                           "gaps": gaps, "result": result, "exact": exact})
        if evidenced:
            candidates[-1]["price_evidence"] = _evidence(candidate["price_evidence"])
    ranking = sorted((candidate for candidate in candidates if candidate["eligible_for_cost_ranking"]),
                     key=_rank_key)
    exact_gains = {candidate["id"]: candidate.pop("exact") for candidate in candidates}
    return {"format": "tli-combat-upgrade-report-v2" if evidenced else "tli-combat-upgrade-report-v1",
            "status": baseline["status"], "baseline": baseline,
            "currency": document["currency"], "price_source": "caller", "quantity_scope": "conditional_combat_dps",
            "gaps": list(baseline["gaps"]), "candidates": candidates,
            "ranking": [candidate["id"] for candidate in ranking], "scenario": copy.deepcopy(document)}, exact_gains
