"""Choose the cheapest supported conditional-combat gain at caller prices."""

import math

from fractions import Fraction

from .combatupgrades import evaluate as compare, exact_deltas

GOAL_FORMAT = "tli-combat-upgrade-goal-v1"
REASONS = ("blocked", "unpriced", "not_upgrade", "below_minimum", "over_budget", "ineligible")


def _canonical(value, label):
    """An exact int, or a nonintegral finite float; integral floats (and -0.0) become their exact int."""
    if type(value) is int:
        try:
            float(value)
        except OverflowError:
            raise ValueError(f"Upgrade goal {label} requires a finite number") from None
        return value
    if type(value) is float and math.isfinite(value):
        return int(value) if value.is_integer() else value
    raise ValueError(f"Upgrade goal {label} requires a finite number")


def _parameters(minimum, budget):
    """Validate the goal before any comparison; equivalent values (100, 100.0, 1e2) persist identically."""
    minimum, budget = _canonical(minimum, "minimum"), _canonical(budget, "budget")
    if minimum <= 0:
        raise ValueError("Upgrade goal minimum must be positive")
    if budget < 0:
        raise ValueError("Upgrade goal budget must be nonnegative")
    return minimum, budget


def _known(value, label):
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Upgrade goal report row has a malformed {label}")
    return value


def _selection(report, *, minimum, budget, exact):
    """Return the goal object for a fresh combatupgrades report: the cheapest supported rows meeting the goal."""
    for value in (minimum, budget):
        if type(value) not in (int, float) or type(value) is bool:
            raise ValueError("Upgrade goal parameters must be canonical")
    try:
        canonical = _parameters(minimum, budget)
    except ValueError:
        raise ValueError("Upgrade goal parameters must be canonical") from None
    if canonical != (minimum, budget) or tuple(map(type, canonical)) != (type(minimum), type(budget)):
        raise ValueError("Upgrade goal parameters must be canonical")
    if (type(report) is not dict or report.get("format") != "tli-combat-upgrade-report-v1"
            or report.get("quantity_scope") != "conditional_combat_dps" or type(report.get("candidates")) is not list):
        raise ValueError("Upgrade goal requires a conditional combat upgrade report")
    blocked = report.get("status") == "blocked"
    qualified, excluded = [], []
    for row in report["candidates"]:
        delta, cost = _known(row["delta"], "delta"), _known(row["cost"], "cost")
        gain = exact[row["id"]]
        if cost is not None and cost < 0:
            raise ValueError("Upgrade goal report row has a malformed cost")
        if type(row["eligible_for_cost_ranking"]) is not bool:
            raise ValueError("Upgrade goal report row has a malformed eligibility flag")
        reasons = set()
        if blocked or gain is None or row["gaps"]:
            reasons.add("blocked")
        if cost is None:
            reasons.add("unpriced")
        if gain is not None and gain <= 0:
            reasons.add("not_upgrade")
        elif gain is not None and gain < Fraction(minimum):
            reasons.add("below_minimum")
        if cost is not None and cost > budget:
            reasons.add("over_budget")
        if not reasons and not row["eligible_for_cost_ranking"]:
            reasons.add("ineligible")
        if reasons:
            excluded.append({"id": row["id"], "reasons": [reason for reason in REASONS if reason in reasons]})
        else:
            qualified.append(row)
    qualified.sort(key=lambda row: (row["cost"], -exact[row["id"]], row["id"]))
    ranking = [row["id"] for row in qualified]
    return {"format": GOAL_FORMAT, "minimum_gain": minimum, "budget": budget, "currency": report["currency"],
            "quantity_scope": report["quantity_scope"], "ranking": ranking, "selected": ranking[0] if ranking else None,
            "status": "blocked" if blocked else "selected" if ranking else "no_supported_affordable_candidate",
            "excluded": excluded}


def evaluate(document, *, minimum, budget):
    """Preserve efficiency ranking and add an explicit minimum-gain budget query."""
    minimum, budget = _parameters(minimum, budget)
    report = compare(document)
    report["goal"] = _selection(report, minimum=minimum, budget=budget, exact=exact_deltas(document))
    return report
