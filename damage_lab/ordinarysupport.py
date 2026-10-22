"""Bind ordinary support scalars at observed catalog levels without applying them."""

from decimal import Decimal
from fractions import Fraction
import math
import re


FORMAT = "tli-ordinary-support-effect-v1"
VERSION = "0.1.1"
VERSIONS = ("0.1.0", VERSION)
TEMPLATE = "Supports skills that hit enemies.\n+#% additional damage for the supported skill when it lands a Critical Strike"
PROJECTILE = ("Supports Projectile Skills.\nProjectile Quantity of the supported skill\n+2\n"
              "#% additional damage for the supported skill")
ERROR = "Ordinary support contains an invalid catalog candidate contract"
REASONS = ("unsupported_catalog_id", "catalog_identity_unbound", "category_unbound", "description_binding_unavailable",
           "template_unbound", "binding_arity_unresolved", "binding_field_unresolved", "binding_level_invalid",
           "level_table_invalid", "reference_level_missing", "reference_level_ambiguous", "reference_cell_invalid",
           "reference_cell_requires_exact_number", "reference_render_unresolved", "observed_level_missing",
           "observed_level_ambiguous", "observed_cell_invalid", "observed_cell_requires_exact_number", "observed_level_invalid")
UNKNOWN = {"arithmetic_ready": False, "runtime_verified": False, "identity_verified": False, "import_complete": False,
           "effective_level": None, "activation": "unknown", "eligibility": "unverified",
           "additional_group_identity": "unresolved", "patch": "unknown"}


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _pattern(value, expression):
    return type(value) is str and re.fullmatch(expression, value, re.ASCII) is not None


def _integer(value, maximum):
    return type(value) is int and 1 <= value <= maximum


def _preflight(value, *, integer_limit=10 ** 20):
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
            _require(-integer_limit < node < integer_limit)
        elif type(node) is float:
            _require(math.isfinite(node))
        elif type(node) is Decimal:
            _require(node.is_finite())
        else:
            _require(node is None or type(node) is bool)


def _select(value, fields):
    _require(type(value) is dict and set(fields.split()).issubset(value))
    return {field: value[field] for field in fields.split()}


def _cell(value, *, signed=False):
    if type(value) is int:
        if not (-10 ** 12 < value < 10 ** 12 if signed else 0 <= value < 10 ** 12):
            return None
        text = str(value)
    elif type(value) is Decimal:
        if not value.is_finite():
            return None
        parts = value.as_tuple()
        if len(parts.digits) > 21 or not -9 <= parts.exponent <= 11 or not signed and value < 0:
            return None
        text = format(value, "f")
    elif type(value) is str:
        text = value
    else:
        return None
    if not _pattern(text, (r"-?" if signed else "") + r"(?:[0-9]{1,12}(?:\.[0-9]{1,9})?|[0-9]{1,12}/[1-9][0-9]{0,11})"):
        return None
    kind = "rational" if "/" in text else "decimal" if "." in text else "integer"
    return {"text": text, "kind": kind}


def _ratio(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def _decimal(value):
    sign = "-" if value < 0 else ""
    whole, remainder = divmod(abs(value.numerator), value.denominator)
    if not remainder:
        return sign + str(whole)
    digits = []
    for _ in range(64):
        number, remainder = divmod(remainder * 10, value.denominator)
        digits.append(str(number))
        if not remainder:
            return sign + str(whole) + "." + "".join(digits)
    return None


def _envelope(catalog_id, level, record):
    exact = type(record.get("tlidbId")) is int and record["tlidbId"] == catalog_id
    return {"format": FORMAT, "version": VERSION, "status": "unresolved", "reason": None, "gaps": [],
            "identity": {"catalog_id": catalog_id,
                         "guid": record.get("id") if exact and _pattern(record.get("id"), r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}") else None,
                         "category": "Support" if exact and record.get("category") == "Support" else None},
            "lookup": {"level": level, "meaning": "observed_gem_level_not_effective"}, "candidate": None, **UNKNOWN}


def _gap(result, reason):
    result.update(reason=reason, gaps=[reason])
    return result


def effect(record, *, catalog_id, level):
    """Return a scalar catalog candidate or a fixed unresolved reason, never a ready pool."""
    _require(type(record) is dict and _integer(catalog_id, 10 ** 20 - 1) and _integer(level, 1000))
    _preflight(record)
    result = _envelope(catalog_id, level, record)
    if catalog_id not in (7401, 7420):
        return _gap(result, "unsupported_catalog_id")
    maximum = 40 if catalog_id == 7401 else 1000
    template = PROJECTILE if catalog_id == 7401 else TEMPLATE
    if level > maximum:
        return _gap(result, "observed_level_invalid")
    if result["identity"]["guid"] is None or record.get("catalogPath", "skill/Support") != "skill/Support":
        return _gap(result, "catalog_identity_unbound")
    if result["identity"]["category"] is None:
        return _gap(result, "category_unbound")
    binding, english = record.get("descriptionBindings"), record.get("english")
    if (type(binding) is not dict or type(english) is not dict
            or binding.get("template") != "templateDescription"):
        return _gap(result, "description_binding_unavailable")
    if english.get("templateDescription") != template:
        return _gap(result, "template_unbound")
    fields = binding.get("bindings")
    if type(fields) is not list or len(fields) != 1:
        return _gap(result, "binding_arity_unresolved")
    field = fields[0]
    if not _pattern(field, r"value[0-9]{1,2}"):
        return _gap(result, "binding_field_unresolved")
    reference = binding.get("level")
    if not _integer(reference, maximum):
        return _gap(result, "binding_level_invalid")
    rows = record.get("levelProgression")
    if (type(rows) is not list or len(rows) > maximum
            or any(type(row) is not dict or not _integer(row.get("level"), maximum) for row in rows)):
        return _gap(result, "level_table_invalid")
    cells = {}
    for name, requested in (("reference", reference), ("observed", level)):
        matches = [row for row in rows if row["level"] == requested]
        if len(matches) != 1:
            return _gap(result, name + ("_level_missing" if not matches else "_level_ambiguous"))
        raw = matches[0].get(field)
        if type(raw) is float:
            return _gap(result, name + "_cell_requires_exact_number")
        cells[name] = _cell(raw, signed=catalog_id == 7401)
        if cells[name] is None:
            return _gap(result, name + "_cell_invalid")
    reference_text = _decimal(Fraction(cells["reference"]["text"]))
    if reference_text is None or english.get("description") != template.replace("#", reference_text):
        return _gap(result, "reference_render_unresolved")
    percent = Fraction(cells["observed"]["text"])
    result.update(status="candidate", candidate={
        "kind": "additional_damage" if catalog_id == 7401 else "critical_hit_additional_damage",
        "origin": "catalog_level_table", "owner": "supported_skill",
        "target": "supported_skill" if catalog_id == 7401 else "supported_skill_critical_hit", "unit": "percent",
        "value": {"cell": cells["observed"], "percent": _ratio(percent), "fraction": _ratio(percent / 100)},
        "binding": {"template": template, "template_field": "templateDescription", "line": 3 if catalog_id == 7401 else 1, "token_index": 0,
                    "field": field, "reference_level": reference, "reference_cell": cells["reference"],
                    "reference_description": template.replace("#", reference_text), "status": "whole_reference_render_consistent"}})
    if catalog_id == 7401:
        result["candidate"].update(scope="projectile", projectile_quantity={
            "origin": "catalog_literal", "lines": [1, 2], "text": "+2", "value": 2,
            "bound": False, "hit_semantics": "unknown"})
    return result


def summary(canonical):
    """Revalidate a detached proof capsule without claiming to reopen catalog or source bytes."""
    _preflight(canonical, integer_limit=10 ** 21)
    result = _select(canonical, "format version status reason gaps identity lookup candidate " + " ".join(UNKNOWN))
    _require(result["format"] == FORMAT and result["version"] in VERSIONS)
    for key, value in UNKNOWN.items():
        _require(result[key] is value if value is None or value is False else result[key] == value)
    identity = _select(result["identity"], "catalog_id guid category")
    lookup = _select(result["lookup"], "level meaning")
    _require(_integer(identity["catalog_id"], 10 ** 20 - 1) and _integer(lookup["level"], 1000)
             and lookup["meaning"] == "observed_gem_level_not_effective")
    _require(identity["guid"] is None or _pattern(identity["guid"], r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"))
    _require(identity["category"] in (None, "Support"))
    result.update(identity=identity, lookup=lookup)
    if result["candidate"] is None:
        _require(result["status"] == "unresolved" and type(result["reason"]) is str
                 and result["reason"] in REASONS and type(result["gaps"]) is list and result["gaps"] == [result["reason"]])
        result["gaps"] = list(result["gaps"])
        return result
    _require(result["version"] == VERSION or identity["catalog_id"] == 7420)
    candidate = _select(result["candidate"], "kind origin owner target unit value binding"
                        + (" scope projectile_quantity" if identity["catalog_id"] == 7401 else ""))
    if identity["catalog_id"] == 7401:
        quantity = _select(candidate["projectile_quantity"], "origin lines text value bound hit_semantics")
        _require(type(quantity["value"]) is int and type(quantity["lines"]) is list
                 and all(type(line) is int for line in quantity["lines"]) and quantity["bound"] is False)
        quantity["lines"] = list(quantity["lines"])
        candidate["projectile_quantity"] = quantity
    value = _select(candidate["value"], "cell percent fraction")
    value["cell"] = _select(value["cell"], "text kind")
    for key in ("percent", "fraction"):
        value[key] = _select(value[key], "numerator denominator")
        _require(type(value[key]["numerator"]) is int and type(value[key]["denominator"]) is int)
    binding = _select(candidate["binding"], "template template_field line token_index field reference_level reference_cell reference_description status")
    binding["reference_cell"] = _select(binding["reference_cell"], "text kind")
    _require(type(binding["line"]) is int and type(binding["token_index"]) is int
             and _integer(binding["reference_level"], 1000) and _pattern(binding["field"], r"value[0-9]{1,2}"))
    candidate.update(value=value, binding=binding)
    result["candidate"] = candidate
    if lookup["level"] == binding["reference_level"]:
        _require(value["cell"] == binding["reference_cell"])
    rows = [{"level": binding["reference_level"], binding["field"]: binding["reference_cell"]["text"]}]
    if lookup["level"] != binding["reference_level"]:
        rows.append({"level": lookup["level"], binding["field"]: value["cell"]["text"]})
    expected = effect({"tlidbId": identity["catalog_id"], "id": identity["guid"], "category": identity["category"],
        "descriptionBindings": {"template": binding["template_field"], "level": binding["reference_level"], "bindings": [binding["field"]]},
        "english": {"templateDescription": binding["template"], "description": binding["reference_description"]},
        "levelProgression": rows}, catalog_id=identity["catalog_id"], level=lookup["level"])
    expected["version"] = result["version"]
    _require(result == expected and expected["status"] == "candidate")
    return expected
