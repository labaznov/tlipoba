"""Corroborate one offline panel state without asserting player identity."""

from decimal import Decimal
from datetime import datetime
import math
import operator
import re


_BINDINGS = {
    "10103": ("Spell DPS", (("spell_dps", "damage/s", 1),)),
    "11800": ("Total Spell Damage", (("hit_min", "damage", 1), ("hit_max", "damage", 1))),
    "21000": ("Spells cast per second", (("cast_rate", "casts/s", 1),)),
    "21212": ("Spell Critical Strike Chance", (("crit_chance", "fraction", 100),)),
    "21400": ("Spell Critical Strike Damage", (("crit_multiplier", "multiplier", 100),)),
    "21714": ("Max Tangle Quantity", (("max_tangles", "count", 1),)),
    "21715": ("Additional Tangle Attach Quantity", (("extra_attachments", "count", 1),)),
    "11000": ("Cold Penetration", (("cold_penetration", "fraction", 100),)),
}


def _integer(value, name):
    try:
        if value is True or value is False or operator.index(value) < 0:
            raise ValueError(f"Panel log {name} must be a nonnegative integer")
    except TypeError as error:
        raise ValueError(f"Panel log {name} must be a nonnegative integer") from error


def _fields(value, fields):
    try:
        if not set(fields).issubset(dict.keys(value)):
            raise ValueError("Panel log object is missing required fields")
    except TypeError as error:
        raise ValueError("Panel log requires typed JSON objects") from error


def _list(value):
    try:
        list.__len__(value)
    except TypeError as error:
        raise ValueError("Panel log requires typed JSON lists") from error


def _text(value):
    try:
        if not str.strip(value):
            raise ValueError("Panel log text must be nonempty")
    except TypeError as error:
        raise ValueError("Panel log requires text fields") from error


def _issues(value):
    _list(value)
    for issue in value:
        _text(issue)


def _cohort(cohort):
    _fields(cohort, ("timestamp", "frame", "attributes", "issues", "status"))
    _integer(cohort["frame"], "frame")
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z", cohort["timestamp"]) is None:
            raise ValueError("Panel log timestamp must be UTC with millisecond precision")
        datetime.strptime(cohort["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ")
    except TypeError as error:
        raise ValueError("Panel log timestamp must be UTC text") from error
    if cohort["status"] not in ("resolved", "partial"):
        raise ValueError("Panel log cohort status must be resolved or partial")
    _issues(cohort["issues"])
    _list(cohort["attributes"])


def _attribute(attribute):
    _fields(attribute, ("id", "name", "values", "raw_values", "line_numbers", "status"))
    if attribute["status"] != "resolved":
        raise ValueError("Panel log resolved cohort cannot contain unresolved attributes")
    for field in ("values", "raw_values", "line_numbers"):
        _list(attribute[field])
    for line in attribute["line_numbers"]:
        _integer(line, "line number")
    if len(attribute["line_numbers"]) != 2 or not 0 < attribute["line_numbers"][0] < attribute["line_numbers"][1]:
        raise ValueError("Panel log resolved attribute requires ordered header and value lines")
    try:
        if re.fullmatch(r"[1-9][0-9]*", attribute["id"]) is None:
            raise ValueError("Panel log attribute ID must be a decimal string")
    except TypeError as error:
        raise ValueError("Panel log attribute ID must be a decimal string") from error
    try:
        if not str.strip(attribute["name"]):
            raise ValueError("Panel log attribute name must be nonempty text")
    except TypeError as error:
        raise ValueError("Panel log attribute name must be nonempty text") from error
    if len(attribute["values"]) != len(attribute["raw_values"]) or not attribute["values"]:
        raise ValueError("Panel log numeric values and raw tokens require matching nonempty lists")
    for value, token in zip(attribute["values"], attribute["raw_values"]):
        try:
            if (value is True or value is False or not math.isfinite(value)
                    or re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", token) is None
                    or float(Decimal(token)) != value or (value == 0 and Decimal(token) != 0)):
                raise ValueError("Panel log raw numeric token must match its finite number")
        except (TypeError, OverflowError) as error:
            raise ValueError("Panel log raw numeric token must match its finite number") from error
    if attribute["id"] in _BINDINGS:
        name, bindings = _BINDINGS[attribute["id"]]
        cardinality = len(attribute["values"]) == len(bindings)
        if attribute["id"] == "21212" and len(attribute["values"]) == 2:
            cardinality = Decimal(attribute["raw_values"][0]) == Decimal(attribute["raw_values"][1])
            if not cardinality:
                raise ValueError("Panel log has unknown dual crit chance semantics")
        if attribute["name"] != name or not cardinality:
            raise ValueError("Panel log known attribute requires its exact label and cardinality")
        for token, (key, unit, divisor) in zip(attribute["raw_values"], bindings):
            value = Decimal(token) / divisor
            if value != 0 and float(value) == 0:
                raise ValueError("Panel log unit conversion cannot underflow to zero")
            if value < 0 or (unit == "count" and value != value.to_integral_value()):
                raise ValueError("Panel log known values must be nonnegative with integral counts")
            if key == "crit_chance" and value > 1:
                raise ValueError("Panel log critical chance must be between zero and one")
        if attribute["id"] == "11800" and Decimal(attribute["raw_values"][0]) > Decimal(attribute["raw_values"][1]):
            raise ValueError("Panel log damage range minimum cannot exceed maximum")


def select(document, expected_spell_dps):
    """Return exact-token rows for an explicitly native-anchored panel cohort.

    A numeric anchor corroborates one state, never player identity or mechanics.
    No damage coefficient, benchmark or unsupported attribute is inferred.
    """
    _integer(expected_spell_dps, "native Spell DPS anchor")
    _fields(document, ("format", "source", "cohorts", "gaps"))
    _fields(document["source"], ("sha256",))
    try:
        if (document["format"] != "tli-panel-log-v1"
                or re.fullmatch(r"[0-9a-fA-F]{64}", document["source"]["sha256"]) is None):
            raise ValueError("Panel log format and source SHA256 must match the contract")
    except TypeError as error:
        raise ValueError("Panel log source SHA256 must be hexadecimal text") from error
    _issues(document["gaps"])
    _list(document["cohorts"])
    resolved = []
    issues = document["gaps"][:]
    for cohort in document["cohorts"]:
        _cohort(cohort)
        issues.extend(cohort["issues"])
        if cohort["status"] != "resolved":
            issues.append("Partial panel cohort omitted")
            continue
        identities = set()
        for attribute in cohort["attributes"]:
            _attribute(attribute)
            if attribute["id"] in identities:
                raise ValueError("Duplicate panel log attribute ID in resolved cohort")
            identities.add(attribute["id"])
        resolved.append(cohort)
    matches = [cohort for cohort in resolved
               if any(attribute["id"] == "10103"
                      and abs(Decimal(attribute["raw_values"][0]) - expected_spell_dps) <= Decimal(".5")
                      for attribute in cohort["attributes"])]
    if not matches:
        raise ValueError("Panel log has no cohort matching the native Spell DPS")
    if any(not _BINDINGS.keys() <= {attribute["id"] for attribute in cohort["attributes"]}
           for cohort in matches):
        raise ValueError("Panel log matching cohort is missing required observations")
    signatures = {tuple(sorted((attribute["id"], attribute["name"],
                                tuple(Decimal(token) for token in attribute["raw_values"]))
                               for attribute in cohort["attributes"])) for cohort in matches}
    if len(signatures) != 1:
        raise ValueError("Panel log matching cohorts are ambiguous")
    cohort = max(matches, key=lambda row: (row["timestamp"], row["frame"]))
    rows = []
    for attribute in cohort["attributes"]:
        if attribute["id"] not in _BINDINGS:
            continue
        label, bindings = _BINDINGS[attribute["id"]]
        for index, (key, unit, divisor) in enumerate(bindings):
            token = attribute["raw_values"][index]
            value = float(Decimal(token) / divisor)
            display = format((Decimal(str(value)) * divisor).normalize(), "f")
            rows.append({"key": key, "label": label,
                         "value": value,
                         "display": display + ("%" if divisor == 100 else " /s" if unit == "casts/s" else ""),
                         "unit": unit,
                         "precision": "log full precision; corroborated; identity_verified=false",
                         "source": {"attr_id": attribute["id"], "index": index + 1,
                                    "raw_value": token, "raw_values": attribute["raw_values"][:],
                                    "timestamp": cohort["timestamp"],
                                    "frame": cohort["frame"], "line_numbers": attribute["line_numbers"][:]}})
    return {"rows": rows, "summary": {"format": document["format"], "status": "corroborated",
                                      "known": len(rows), "unknown_attributes": sum(
                                          attribute["id"] not in _BINDINGS for attribute in cohort["attributes"]),
                                      "cohort": {"timestamp": cohort["timestamp"], "frame": cohort["frame"]},
                                      "identity_verified": False, "source_sha256": document["source"]["sha256"]},
            "issues": issues}
