"""Compute an explicit baseline main-stat bonus without applying it to damage."""

import copy
import math
import re

from .formulas import product


FORMAT = "tli-main-stat-scenario-v1"
ATTRIBUTES = ("strength", "dexterity", "intelligence")


def _object(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f"{label} has missing or unsupported fields")
    return value


def _number(value, label):
    if type(value) in (int, float):
        try:
            if math.isfinite(value) and value >= 0:
                return value
        except OverflowError:
            pass
    raise ValueError(f"{label} must be a finite nonnegative number")


def _text(value, label):
    if type(value) is not str or not value or value != value.strip() or len(value) > 1024:
        raise ValueError(f"{label} must be bounded nonempty text without edge whitespace")
    return value


def _texts(value):
    if type(value) is not list or len(value) > 1000:
        raise ValueError("Evidence must be a bounded list of references")
    for entry in value:
        _text(entry, "Evidence reference")
    return value


def evaluate(document):
    """Sum eligible final attribute totals once using the caller's explicit point rate."""
    _object(document, ("format", "context", "attributes", "eligible", "per_point", "ratio", "gates"),
            "Main-stat scenario")
    if document["format"] != FORMAT:
        raise ValueError("Unsupported main-stat format")
    _object(document["context"], ("source_sha256", "catalog_sha256", "skill_id"), "Main-stat context")
    for field in ("source_sha256", "catalog_sha256"):
        if type(document["context"][field]) is not str or not re.fullmatch(r"[0-9a-f]{64}", document["context"][field]):
            raise ValueError("Main-stat context requires exact source and catalog SHA256 hashes")
    _text(document["context"]["skill_id"], "Skill identity")
    _object(document["attributes"], ATTRIBUTES, "Final attributes")
    for value in document["attributes"].values():
        if value is not None:
            _number(value, "Final attribute")
    _number(document["per_point"], "Main-stat point rate")
    eligible = document["eligible"]
    if (type(eligible) is not list or len(eligible) > len(ATTRIBUTES)
            or any(type(name) is not str or name not in ATTRIBUTES for name in eligible)
            or len(set(eligible)) != len(eligible)):
        raise ValueError("Eligible main attributes must be a distinct list of supported names")
    _object(document["ratio"], ("selection", "evidence"), "Main-stat ratio")
    if document["ratio"]["selection"] not in ("none", "unknown"):
        raise ValueError("Main-stat ratio selection must be none or unknown")
    if not _texts(document["ratio"]["evidence"]) and document["ratio"]["selection"] == "none":
        raise ValueError("No-ratio selection requires evidence references")
    _object(document["gates"], ("patch", "main_stat_binding", "activation"), "Evidence gates")
    for gate in document["gates"].values():
        _object(gate, ("status", "evidence"), "Evidence gate")
        if gate["status"] not in ("confirmed", "unknown", "conflict"):
            raise ValueError("Evidence gate status must be confirmed, unknown or conflict")
        if not _texts(gate["evidence"]) and gate["status"] == "confirmed":
            raise ValueError("A confirmed gate requires evidence references")
    gaps = [f"{name}: {gate['status']}" for name, gate in document["gates"].items()
            if gate["status"] != "confirmed"]
    if document["ratio"]["selection"] == "unknown":
        gaps.append("ratio: unknown")
    gaps.extend(f"{name}: final total unknown" for name in document["eligible"]
                if document["attributes"][name] is None)
    result = {"format": "tli-main-stat-report-v1", "status": "blocked" if gaps else "conditional",
              "bonus": None, "factor": None, "gaps": gaps, "scenario": copy.deepcopy(document),
              "assumptions": [
                  "Evidence gates are caller assertions; runtime identity and freshness are not verified",
                  "Attributes are complete final totals; static flat or increased rows are not totals",
                  "Eligibility is an explicit main-stat binding, separate from skill and damage tags",
                  "The explicit point rate and no-ratio assertion apply only to this baseline scenario",
                  "The result is not applied to a panel, raw spell or DPS",
              ],
              "trace": [{"label": "Main attribute contribution", "attribute": name,
                         "selected": name in eligible, "value": document["attributes"][name],
                         "contribution": None} for name in ATTRIBUTES]}
    if gaps:
        return result
    for row in result["trace"]:
        if row["selected"]:
            row["contribution"] = product((row["value"], document["per_point"]), name="Main-stat contribution")
    try:
        bonus = math.fsum(row["contribution"] for row in result["trace"] if row["selected"])
    except OverflowError:
        raise ValueError("Main-stat bonus must be finite") from None
    _number(bonus, "Main-stat bonus")
    _number(1 + bonus, "Main-stat factor")
    result.update(bonus=bonus, factor=1 + bonus)
    result["trace"].extend([{"label": "Main-stat bonus", "value": bonus, "unit": "fraction"},
                            {"label": "Main-stat factor", "factor": 1 + bonus}])
    return result
