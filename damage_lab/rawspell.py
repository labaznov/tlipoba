"""Assemble an explicit Physical-to-Cold spell before target defence and Tangle topology."""

import copy
import math
import re
from fractions import Fraction

from .engine import cold, critical
from .formulas import additional, product, tangle_rate


def _object(value, fields, label):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError(f"{label} has missing or unsupported fields")
    return value


def _number(value, minimum, maximum, label):
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite number within the supported range")
    try:
        if math.isfinite(value) and minimum <= value <= maximum:
            return value
    except OverflowError:
        pass
    raise ValueError(f"{label} must be a finite number within the supported range")


def _text(value, label):
    if type(value) is not str or not value or value != value.strip() or len(value) > 1024:
        raise ValueError(f"{label} must be nonempty text without edge whitespace")
    return value


def _texts(value, label):
    if type(value) is not list or len(value) > 1000:
        raise ValueError(f"{label} must be a bounded list of text")
    return [_text(entry, label) for entry in value]


def _range(value):
    _object(value, "min max", "Damage range")
    _number(value["min"], 0, 1e15, "Minimum damage")
    _number(value["max"], value["min"], 1e15, "Maximum damage")


def _rows(value, damage):
    if type(value) is not list or len(value) > 1000:
        raise ValueError("Additional modifiers must be a bounded list")
    for row in value:
        _object(row, "id affix value stacks mode scope" if damage else "id affix value stacks mode",
                "Additional modifier")
        _text(row["id"], "Modifier identity")
        _text(row["affix"], "Affix identity")
        _number(row["value"], -1, 1e6, "Additional modifier")
        if type(row["stacks"]) is not int or not 0 <= row["stacks"] <= 1000:
            raise ValueError("Modifier stacks must be an integer within the supported range")
        if row["mode"] not in ("add", "multiply"):
            raise ValueError("Modifier mode must be add or multiply")
        if damage and row["scope"] not in ("all", "physical", "cold"):
            raise ValueError("Damage modifier scope must be all, physical or cold")
    additional(value)


def _context(value):
    _object(value, "source_sha256 catalog_sha256 skill_id effective_level gates", "Skill context")
    for field in ("source_sha256", "catalog_sha256"):
        if type(value[field]) is not str or not re.fullmatch(r"[0-9a-f]{64}", value[field]):
            raise ValueError("Skill context requires exact source and catalog SHA256 hashes")
    _text(value["skill_id"], "Skill identity")
    _object(value["gates"], "version level base conversion", "Evidence gates")
    gaps = []
    for name, gate in value["gates"].items():
        _object(gate, "status evidence", "Evidence gate")
        if gate["status"] not in ("confirmed", "unknown", "conflict"):
            raise ValueError("Evidence gate status must be confirmed, unknown or conflict")
        evidence = _texts(gate["evidence"], "Gate evidence")
        if gate["status"] == "confirmed" and not evidence:
            raise ValueError("A confirmed gate requires evidence references")
        if gate["status"] != "confirmed":
            gaps.append(f"{name}: {gate['status']}")
    if value["effective_level"] is not None or value["gates"]["level"]["status"] == "confirmed":
        if type(value["effective_level"]) is not int or not 1 <= value["effective_level"] <= 1000:
            raise ValueError("Effective skill level must be an integer within the supported range")
    return gaps


def _damage(value):
    _object(value, "base physical cold effectiveness increased more roll_model", "Damage")
    for field in ("base", "physical", "cold"):
        _range(value[field])
    _number(value["effectiveness"], 0, 1e6, "Added effectiveness")
    _object(value["increased"], "all physical cold", "Increased damage")
    for number in value["increased"].values():
        _number(number, -1, 1e6, "Increased damage")
    if value["roll_model"] != "midpoint":
        raise ValueError("Only the explicit midpoint damage roll model is supported")
    _rows(value["more"], True)


def _critical(value):
    _object(value, "chance multiplier lucky more", "Critical expectation")
    _number(value["chance"], 0, 1, "Critical chance")
    _number(value["multiplier"], 0, 100, "Critical multiplier")
    _number(value["more"], -1, 100, "Critical-only more")
    if type(value["lucky"]) is not bool:
        raise ValueError("Lucky critical chance must be a boolean")


def _casting(value):
    _object(value, "interval increased more frequency", "Casting")
    _number(value["interval"], 0, 1e6, "Base cast interval")
    if value["interval"] == 0:
        raise ValueError("Base cast interval must be positive")
    _number(value["increased"], -1, 1e6, "Increased cast speed")
    _rows(value["more"], False)
    if value["frequency"] is not None and (type(value["frequency"]) is not int or value["frequency"] != 30):
        raise ValueError("Tick frequency must be 30 or None")


def _double(value):
    if value is None:
        return ["double_damage: unavailable"]
    _object(value, "noncritical critical mean_model gate", "Double Damage")
    for field in ("noncritical", "critical"):
        _number(value[field], 0, 1, "Conditional Double Damage probability")
    if value["mean_model"] != "shared_midpoint":
        raise ValueError("Double Damage requires the explicit shared midpoint model")
    gate = _object(value["gate"], "status evidence", "Double Damage gate")
    if gate["status"] not in ("confirmed", "unknown", "conflict"):
        raise ValueError("Double Damage gate status must be confirmed unknown or conflict")
    evidence = _texts(gate["evidence"], "Double Damage evidence")
    if gate["status"] == "confirmed" and not evidence:
        raise ValueError("A confirmed Double Damage gate requires evidence references")
    return [] if gate["status"] == "confirmed" else ["double_damage: " + gate["status"]]


def evaluate(document):
    """Return a conditional raw expectation or a blocked result with explicit evidence gaps.

    Gate confirmations are assertions of the caller, not a game/API verification.
    A null effective level is retained only behind an unknown or conflicting level gate.
    Entire null damage, critical or casting groups remain unavailable and block arithmetic.
    Every supplied non-null group is fully validated before returning a blocked result.
    Base damage must be Physical and conversion must be ordinary complete conversion
    to Cold; native added Cold retains its separate modifier path.
    Opt-in v2 requires an explicit Double Damage group and shared branch midpoint.
    Probabilities are already effective conditional probabilities, not inferred marginals.
    """
    version = document.get("format") if type(document) is dict else None
    if version not in ("tli-raw-cold-spell-v1", "tli-raw-cold-spell-v2"):
        raise ValueError("Unsupported raw spell format")
    modern = version == "tli-raw-cold-spell-v2"
    _object(document, "format context damage critical casting missing notes" +
            (" double_damage" if modern else ""), "Raw spell scenario")
    gaps = _context(document["context"]) + _texts(document["missing"], "Missing effects")
    if modern:
        gaps += _double(document["double_damage"])
    _texts(document["notes"], "Scenario notes")
    for name, validator in (("damage", _damage), ("critical", _critical), ("casting", _casting)):
        if document[name] is None:
            gaps.append(name + ": unavailable")
        else:
            validator(document[name])
    damage, crit, casting = (document[name] for name in ("damage", "critical", "casting"))
    result = {"format": "tli-raw-cold-spell-report-v2" if modern else "tli-raw-cold-spell-report-v1", "status": "blocked" if gaps else "conditional",
              "pre_defence_dps": None, "gaps": gaps, "scenario": copy.deepcopy(document), "trace": [],
              "assumptions": [
                  "Evidence gates are caller assertions; runtime identity and freshness are not verified",
                  "Base Physical damage uses ordinary complete conversion to Cold",
                  "Each damage component has the stated midpoint mean; Lucky applies only to critical chance",
                  "All supplied pools are complete for this scenario and applied once without a panel",
                  "The result is one caster before enemy defence, damage taken, Tangle topology and uptime",
                  "Tick rounding, when selected, is a separate unverified 30 Hz hypothesis",
              ]}
    result["assumptions"].append(
        "Double Damage uses caller-asserted conditional probabilities and the same midpoint in every crit/DD branch"
        if modern else "Legacy v1 excludes Double Damage; its absence is not verified game zero")
    if gaps:
        return result
    increased = damage["increased"]
    components = {}
    for label, base, physical, native in (("converted", damage["base"], damage["physical"], {"min": 0, "max": 0}),
                                        ("native", {"min": 0, "max": 0}, {"min": 0, "max": 0}, damage["cold"])):
        components[label] = {edge: cold(base[edge], physical[edge], native[edge], damage["effectiveness"],
                                        increased["all"], increased["physical"], increased["cold"], damage["more"])
                             for edge in ("min", "max")}
    minimum = components["converted"]["min"] + components["native"]["min"]
    maximum = components["converted"]["max"] + components["native"]["max"]
    mean = minimum + product((maximum - minimum, .5), name="Midpoint spread")
    factor = critical(crit["chance"], crit["multiplier"], lucky=crit["lucky"], more=crit["more"])
    joint = None
    if modern:
        chance = Fraction(crit["chance"])
        probability = chance * (2 - chance) if crit["lucky"] else chance
        double = document["double_damage"]
        joint = ((1 - probability) * (1 + Fraction(double["noncritical"])) +
                 probability * Fraction(crit["multiplier"]) * (1 + Fraction(crit["more"])) *
                 (1 + Fraction(double["critical"])))
    expected = product((mean, joint if modern else factor), name="Expected hit")
    speed = additional(casting["more"])
    rate = product(((1 + casting["increased"]) / casting["interval"], speed), name="Raw cast rate")
    _number(rate, 0, 1e300, "Raw cast rate")
    effective = tangle_rate(rate, casting["frequency"])
    dps = product((expected, effective), name="Pre-defence DPS")
    _number(dps, 0, 1e300, "Pre-defence DPS")
    result.update(noncritical={"min": minimum, "max": maximum, "mean": mean, "components": components},
                  critical_factor=factor, expected_hit=expected,
                  rate={"smooth": rate, "capped": min(rate, 30), "effective": effective,
                        "frequency": casting["frequency"]}, pre_defence_dps=dps,
                  trace=[{"label": "Converted Physical range", **components["converted"]},
                         {"label": "Native Cold range", **components["native"]},
                         {"label": "Midpoint noncritical hit", "value": mean},
                         {"label": "Critical expectation", "factor": factor},
                         {"label": "Expected hit", "value": expected},
                         {"label": "Base cast interval", "value": casting["interval"]},
                         {"label": "Increased cast speed factor", "factor": 1 + casting["increased"]},
                         {"label": "Additional cast speed factor", "factor": speed},
                         {"label": "Uncapped cast rate", "value": rate},
                         {"label": "Effective cast rate per caster", "value": effective},
                         {"label": "Pre-defence DPS", "value": dps}])
    if modern:
        result["joint_factor"] = float(joint)
        result["trace"][3]["label"] = "Critical-only expectation reference (not multiplied again)"
        result["trace"].insert(4, {"label": "Joint critical and Double Damage expectation",
            "effective_critical_probability": float(probability), "noncritical": double["noncritical"],
            "critical": double["critical"], "mean_model": double["mean_model"],
            "shared_midpoint": mean, "factor": float(joint)})
    return result
