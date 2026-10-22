"""Bind an exact Ice Focus catalog scalar while leaving all application and skill damage unresolved."""

from decimal import Decimal
from fractions import Fraction
import math
import re


FORMAT = "tli-passive-effect-v1"
VERSION = "0.1.0"
ERROR = "Passive effects contain an invalid catalog candidate contract"
TEMPLATE = ("Activates Focus and gains a buff:\n#% additional Cold Damage\n"
    "Gains 30 Focus Pts when dealing damage to Frostbitten enemies. Interval: 0.4 s.\n"
    "Upon reaching 100 Focus Pts, creates an Ice Storm that follows the character. When there are enemies inside the storm, consumes 45 Focus Pts every 0.5 s to generate Glacial Spikes that deal Spell Cold Damage to the enemies\n"
    "For every 1% Focus Speed, +1% Focus Pts gained, up to\n"
    "+200%. The Ice Storm ends when Focus Pts drop to 0.\n"
    "+4% additional damage for this skill\nGlacial Spike:\nDeals #-# Spell Cold Damage.")
UNKNOWN = {"arithmetic_ready": False, "runtime_verified": False, "identity_verified": False, "import_complete": False,
           "effective_level": None, "activation": "unknown", "eligibility": "unverified",
           "additional_group_identity": "unresolved", "patch": "unknown"}
UNMODELLED = ("focus_resource_and_ice_storm_mechanics", "self_skill_additional_damage_literal_4_percent", "glacial_spike_damage")
REASONS = ("unsupported_catalog_id", "catalog_identity_unbound", "category_unbound", "description_binding_unavailable",
           "template_unbound", "binding_arity_unresolved", "binding_field_unresolved", "binding_level_invalid",
           "level_table_invalid", "reference_level_missing", "reference_level_ambiguous", "reference_cell_invalid",
           "reference_cell_requires_exact_number", "reference_range_invalid", "reference_render_unresolved",
           "observed_level_missing", "observed_level_ambiguous", "observed_cell_invalid",
           "observed_cell_requires_exact_number", "observed_range_invalid")


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _preflight(value, digits):
    stack, seen, count = [(value, 0)], set(), 0
    while stack:
        node, depth = stack.pop()
        count += 1
        _require(count <= 20_000 and depth <= 32)
        if type(node) in (dict, list):
            _require(id(node) not in seen and len(node) <= 4096)
            seen.add(id(node))
            if type(node) is dict:
                _require(all(type(key) is str for key in node))
                stack.extend((key, depth + 1) for key in node)
            stack.extend((child, depth + 1) for child in (node.values() if type(node) is dict else node))
        elif type(node) is str:
            _require(len(node) <= 4096)
            try:
                node.encode("utf-8")
            except UnicodeError:
                raise ValueError(ERROR) from None
        elif type(node) is int:
            _require(-10 ** digits < node < 10 ** digits)
        elif type(node) is float:
            _require(math.isfinite(node))
        elif type(node) is Decimal:
            _require(node.is_finite())
        else:
            _require(node is None or type(node) is bool)


def _pattern(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value, re.ASCII) is not None


def _integer(value, maximum):
    return type(value) is int and 1 <= value <= maximum


def _select(value, fields):
    _require(type(value) is dict and set(fields.split()).issubset(value))
    return {field: value[field] for field in fields.split()}


def _cell(value):
    if type(value) is int:
        if not -10 ** 12 < value < 10 ** 12:
            return None
        text = str(value)
    elif type(value) is Decimal:
        if not value.is_finite():
            return None
        parts = value.as_tuple()
        if len(parts.digits) > 21 or not -9 <= parts.exponent <= 11:
            return None
        text = format(value, "f")
    elif type(value) is str:
        text = value
    else:
        return None
    if not _pattern(text, r"-?[0-9]{1,12}(?:\.[0-9]{1,9})?|-?[0-9]{1,12}/[1-9][0-9]{0,11}"):
        return None
    return {"text": text, "kind": "rational" if "/" in text else "decimal" if "." in text else "integer"}


def _decimal(value):
    whole, remainder = divmod(abs(value.numerator), value.denominator)
    sign = "-" if value < 0 else ""
    if not remainder:
        return sign + str(whole)
    digits = []
    for _ in range(64):
        number, remainder = divmod(remainder * 10, value.denominator)
        digits.append(str(number))
        if not remainder:
            return sign + str(whole) + "." + "".join(digits)
    return None


def _range(row, minimum, maximum):
    low, high = row.get(minimum), row.get(maximum)
    if type(low) is not int or type(high) is not int or not 0 <= low <= high < 10 ** 12:
        return None
    return {"min": {"text": str(low), "kind": "integer"}, "max": {"text": str(high), "kind": "integer"}}


def _ratio(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def _envelope(record, catalog_id, level):
    exact = type(record.get("tlidbId")) is int and record["tlidbId"] == catalog_id
    return {"format": FORMAT, "version": VERSION, "status": "unresolved", "reason": None, "gaps": [],
            "identity": {"catalog_id": catalog_id,
                         "guid": record.get("id") if exact and _pattern(record.get("id"), r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}") else None,
                         "category": "Passive" if exact and record.get("category") == "Passive" else None},
            "lookup": {"level": level, "meaning": "observed_gem_level_not_effective"}, "candidate": None, **UNKNOWN}


def _gap(result, reason):
    result.update(reason=reason, gaps=[reason])
    return result


def effect(record, *, catalog_id, level):
    """Return the exact observed-level buff scalar or a fixed gap, never an effective damage pool."""
    _require(type(record) is dict and _integer(catalog_id, 10 ** 20 - 1) and _integer(level, 40))
    _preflight(record, 20)
    result = _envelope(record, catalog_id, level)
    if catalog_id != 8318:
        return _gap(result, "unsupported_catalog_id")
    if result["identity"]["guid"] is None or record.get("catalogPath", "skill/Passive") != "skill/Passive":
        return _gap(result, "catalog_identity_unbound")
    if result["identity"]["category"] is None:
        return _gap(result, "category_unbound")
    binding, english = record.get("descriptionBindings"), record.get("english")
    if type(binding) is not dict or type(english) is not dict or binding.get("template") != "templateDescription":
        return _gap(result, "description_binding_unavailable")
    if english.get("templateDescription") != TEMPLATE:
        return _gap(result, "template_unbound")
    fields = binding.get("bindings")
    if type(fields) is not list or len(fields) != 2:
        return _gap(result, "binding_arity_unresolved")
    field, minimum = fields
    if not _pattern(field, r"value[0-9]{1,2}") or not _pattern(minimum, r"value[0-9]{1,2}Min"):
        return _gap(result, "binding_field_unresolved")
    maximum = minimum[:-3] + "Max"
    reference = binding.get("level")
    if not _integer(reference, 40):
        return _gap(result, "binding_level_invalid")
    rows = record.get("levelProgression")
    if (type(rows) is not list or len(rows) > 40
            or any(type(row) is not dict or not _integer(row.get("level"), 40) for row in rows)):
        return _gap(result, "level_table_invalid")
    cells, ranges = {}, {}
    for name, requested in (("reference", reference), ("observed", level)):
        matches = [row for row in rows if row["level"] == requested]
        if len(matches) != 1:
            return _gap(result, name + ("_level_missing" if not matches else "_level_ambiguous"))
        raw = matches[0].get(field)
        if type(raw) is float:
            return _gap(result, name + "_cell_requires_exact_number")
        cells[name] = _cell(raw)
        if cells[name] is None:
            return _gap(result, name + "_cell_invalid")
        ranges[name] = _range(matches[0], minimum, maximum)
        if ranges[name] is None:
            return _gap(result, name + "_range_invalid")
    rendered = _decimal(Fraction(cells["reference"]["text"]))
    if rendered is None:
        return _gap(result, "reference_render_unresolved")
    description = TEMPLATE.replace("#-#", ranges["reference"]["min"]["text"] + "-" + ranges["reference"]["max"]["text"]).replace("#", rendered)
    if english.get("description") != description:
        return _gap(result, "reference_render_unresolved")
    percent = Fraction(cells["observed"]["text"])
    result.update(status="candidate", candidate={
        "kind": "additional_damage", "owner": "player", "target": "cold_damage", "scope": "focus_buff", "unit": "percent",
        "value": {"cell": cells["observed"], "percent": _ratio(percent), "fraction": _ratio(percent / 100)},
        "unmodelled_effects": list(UNMODELLED),
        "binding": {"template": TEMPLATE, "template_field": "templateDescription", "line": 1, "token_index": 0,
                    "field": field, "range": {"min_field": minimum, "max_field": maximum, "line": 8, "token_index": 1},
                    "reference_level": reference, "reference_scalar_cell": cells["reference"],
                    "reference_range_cells": ranges["reference"], "observed_range_cells": ranges["observed"],
                    "reference_description": description, "status": "whole_reference_render_consistent"}})
    return result


def _rangeproof(value):
    result = _select(value, "min max")
    for key in ("min", "max"):
        result[key] = _select(result[key], "text kind")
        _require(result[key]["kind"] == "integer" and _pattern(result[key]["text"], r"0|[1-9][0-9]{0,11}"))
    _require(int(result["min"]["text"]) <= int(result["max"]["text"]))
    return result


def summary(canonical):
    """Reconstruct the known proof cells and revalidate without authenticating source or catalog bytes."""
    _preflight(canonical, 21)
    result = _select(canonical, "format version status reason gaps identity lookup candidate " + " ".join(UNKNOWN))
    _require(result["format"] == FORMAT and result["version"] == VERSION)
    for key, expected in UNKNOWN.items():
        _require(result[key] is expected if expected is None or expected is False else result[key] == expected)
    identity = _select(result["identity"], "catalog_id guid category")
    lookup = _select(result["lookup"], "level meaning")
    _require(_integer(identity["catalog_id"], 10 ** 20 - 1) and _integer(lookup["level"], 40)
             and lookup["meaning"] == "observed_gem_level_not_effective")
    _require(identity["guid"] is None or _pattern(identity["guid"], r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"))
    _require(identity["category"] in (None, "Passive"))
    result.update(identity=identity, lookup=lookup)
    if result["candidate"] is None:
        _require(result["status"] == "unresolved" and type(result["reason"]) is str and result["reason"] in REASONS
                 and type(result["gaps"]) is list and result["gaps"] == [result["reason"]])
        result["gaps"] = list(result["gaps"])
        return result
    candidate = _select(result["candidate"], "kind owner target scope unit value unmodelled_effects binding")
    value = _select(candidate["value"], "cell percent fraction")
    value["cell"] = _select(value["cell"], "text kind")
    for key in ("percent", "fraction"):
        value[key] = _select(value[key], "numerator denominator")
        _require(type(value[key]["numerator"]) is int and type(value[key]["denominator"]) is int)
    binding = _select(candidate["binding"], "template template_field line token_index field range reference_level "
                      "reference_scalar_cell reference_range_cells observed_range_cells reference_description status")
    binding["reference_scalar_cell"] = _select(binding["reference_scalar_cell"], "text kind")
    binding["range"] = _select(binding["range"], "min_field max_field line token_index")
    coordinates = binding["range"]
    _require(type(binding["line"]) is int and type(binding["token_index"]) is int
             and type(coordinates["line"]) is int and type(coordinates["token_index"]) is int
             and _integer(binding["reference_level"], 40) and _pattern(binding["field"], r"value[0-9]{1,2}")
             and _pattern(coordinates["min_field"], r"value[0-9]{1,2}Min")
             and coordinates["max_field"] == coordinates["min_field"][:-3] + "Max")
    binding["reference_range_cells"] = _rangeproof(binding["reference_range_cells"])
    binding["observed_range_cells"] = _rangeproof(binding["observed_range_cells"])
    candidate.update(value=value, binding=binding)
    result["candidate"] = candidate
    if lookup["level"] == binding["reference_level"]:
        _require(value["cell"] == binding["reference_scalar_cell"]
                 and binding["observed_range_cells"] == binding["reference_range_cells"])
    rows = [{"level": binding["reference_level"], binding["field"]: binding["reference_scalar_cell"]["text"],
             coordinates["min_field"]: int(binding["reference_range_cells"]["min"]["text"]),
             coordinates["max_field"]: int(binding["reference_range_cells"]["max"]["text"])}]
    if lookup["level"] != binding["reference_level"]:
        rows.append({"level": lookup["level"], binding["field"]: value["cell"]["text"],
                     coordinates["min_field"]: int(binding["observed_range_cells"]["min"]["text"]),
                     coordinates["max_field"]: int(binding["observed_range_cells"]["max"]["text"])})
    expected = effect({"tlidbId": identity["catalog_id"], "id": identity["guid"], "category": identity["category"],
        "descriptionBindings": {"template": binding["template_field"], "level": binding["reference_level"],
                                "bindings": [binding["field"], coordinates["min_field"]]},
        "english": {"templateDescription": binding["template"], "description": binding["reference_description"]},
        "levelProgression": rows}, catalog_id=identity["catalog_id"], level=lookup["level"])
    _require(result == expected and expected["status"] == "candidate")
    return expected
