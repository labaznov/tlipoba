"""Validate an installed special-support candidate ledger without source reads or damage effects."""

import re
from decimal import Decimal

from .supporteffects import CONSTANTS, DECIMAL, TEMPLATES, FORMAT as RAW_EFFECT_FORMAT, _fraction


FORMAT = "tli-installed-support-effects-canonical-v1"
RAW_FORMAT = "tli-installed-support-effects-v0"
VERSION = "0.2.0"
EFFECT_FORMAT = "tli-support-effects-canonical-v1"
FLAGS = {"arithmetic_ready": False, "runtime_verified": False, "identity_verified": False,
         "import_complete": False, "activation": "unknown", "patch": "unknown", "effective_level": None}
LIMITATIONS = (
    "source sha256 binds the caller-supplied document only; no source bytes are read or verified",
    "catalog records are taken as supplied; no catalog bytes or hashes are verified",
    "installation is observed membership only; activation, effective level and panel skill are unknown",
)
PARAMETERS = {kind: parameters for kind, parameters in CONSTANTS.values()}
ELIGIBLE = ("noble_support", "magnificent_support", "activation_medium")
CATEGORIES = ELIGIBLE + ("ordinary_support", "active_skill", "passive_skill", "module", "other")
CATEGORY_NAMES = dict(zip(ELIGIBLE, ("Noble_Support", "Magnificent_Support", "Activation_Medium")))
REASONS = ("source_coordinates_invalid", "installation_identity_ambiguous", "raw_node_invalid", "native_base_invalid",
           "catalog_record_missing", "catalog_identity_mismatch", "slot_position_ambiguous", "slot_position_invalid",
           "prefix_invalid", "catalog_schema_invalid")
OMISSIONS = ("invalid_row", "no_exact_definition", "ambiguous_definition", "line_not_declared", "value_count_mismatch",
             "invalid_value", "unsupported_template", "sign_convention_unresolved", "invalid_range", "value_out_of_range", "duplicate_line")


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _select(row, fields, canonical):
    names = {_name(field) if canonical else field: _name(field) for field in fields.split()}
    if type(row) is not dict or not set(names).issubset(row):
        raise ValueError("Support inventory requires all named contract fields")
    return {target: row[source] for source, target in names.items()}


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError("Support inventory has an unsupported contract status")


def _fixed(row, expected):
    for key, value in expected.items():
        if value is False or value is None:
            if row[key] is not value:
                raise ValueError("Support inventory cannot promote unknown or false claims")
        else:
            _enum(row[key], (value,))


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value, re.ASCII):
        raise ValueError("Support inventory requires a lowercase source SHA-256")


def _list(value):
    if type(value) is not list:
        raise ValueError("Support inventory requires JSON lists")
    return value


def _integer(value, minimum, nullable=False):
    if value is None and nullable:
        return
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("Support inventory requires typed integers within the contract range")


def _pattern(value, pattern):
    if type(value) is not str or not re.fullmatch(pattern, value, re.ASCII):
        raise ValueError("Support inventory has an invalid typed identifier or coordinate")


def _metadata(row):
    _integer(row["tab_position"], 0)
    for key in ("slot", "base_id"):
        _integer(row[key], 1, True)
    _integer(row["gem_level"]["value"], 1, True)
    _fixed(row["gem_level"], {"meaning": "observed_gem_level_not_effective"})
    _enum(row["group_status"], ("ok", "ambiguous_slot", "no_primary_slot"))
    _enum(row["status"], ("effect_candidates", "excluded_category", "gap"))
    if row["category"] is not None:
        _enum(row["category"], CATEGORIES)
    if row["status"] == "gap":
        _enum(row["reason"], REASONS)
        if row["effects"] is not None:
            raise ValueError("Support inventory gaps cannot retain attributed effects")
        if row["reason"] in ("source_coordinates_invalid", "installation_identity_ambiguous", "raw_node_invalid", "native_base_invalid"):
            _fixed(row, {"base_id": None, "category": None})
        else:
            _integer(row["base_id"], 1)
        if row["reason"] == "catalog_record_missing":
            _fixed(row, {"category": None})
        if row["reason"] == "catalog_identity_mismatch" and row["category"] is not None:
            _enum(row["category"], ELIGIBLE)
        if row["reason"] in ("slot_position_ambiguous", "slot_position_invalid", "prefix_invalid", "catalog_schema_invalid"):
            _enum(row["category"], ELIGIBLE)
            if row["reason"] == "slot_position_invalid":
                _fixed(row, {"slot": None})
            else:
                _integer(row["slot"], 1)
    elif row["reason"] is not None or row["base_id"] is None:
        raise ValueError("Support inventory candidates and exclusions require exact base metadata")
    if row["status"] == "effect_candidates":
        _enum(row["category"], ELIGIBLE)
        _integer(row["slot"], 1)
        if row["effects"] is None:
            raise ValueError("Support inventory candidates require validated effects")
        identity = row["effects"]["identity"]
        for key in ("catalog_tlidb_id", "native_base_id"):
            _integer(identity[key], 1)
            if identity[key] != row["base_id"]:
                raise ValueError("Support inventory nested base identities must match their member")
        _fixed(identity, {"category": CATEGORY_NAMES[row["category"]]})
    if row["status"] == "excluded_category":
        _enum(row["category"], tuple(value for value in CATEGORIES if value not in ELIGIBLE))
        if row["effects"] is not None:
            raise ValueError("Support inventory exclusions require null effects")
    if row["reason"] == "source_coordinates_invalid":
        if row["path"] is not None or row["base_id"] is not None or row["category"] is not None:
            raise ValueError("Support inventory invalid source coordinates cannot attribute metadata")
    else:
        _pattern(row["path"], r"sections\.SkillLayout\.data\[(0|[1-9][0-9]{0,3})\]\[(0|[1-9][0-9]{0,3})\]")


def _groups(members):
    groups, position = [], -1
    for number, row in enumerate(members, 1):
        _metadata(row)
        if row["tab_position"] != position:
            if row["tab_position"] <= position:
                raise ValueError("Support inventory groups require ordered source coordinates")
            groups.append([])
            position = row["tab_position"]
        if row["alias"] != f"gem[{number}]" or row["group"] != f"group[{len(groups)}]":
            raise ValueError("Support inventory aliases must follow their observed member and group order")
        groups[-1].append(row)
    for group in groups:
        slots = [row["slot"] for row in group if row["slot"] is not None]
        status = "ambiguous_slot" if len(slots) != len(set(slots)) else "no_primary_slot" if 1 not in slots else "ok"
        offset = -1
        for row in group:
            if row["group_status"] != status:
                raise ValueError("Support inventory group status must match observed slots")
            if row["path"] is not None:
                coordinates = tuple(int(value) for value in re.findall(r"\[([0-9]+)\]", row["path"]))
                if coordinates[0] != row["tab_position"] or coordinates[1] <= offset:
                    raise ValueError("Support inventory member paths must be distinct ordered coordinates")
                offset = coordinates[1]
            if row["status"] == "effect_candidates" and slots.count(row["slot"]) > 1:
                raise ValueError("Support inventory duplicate slots cannot retain effect candidates")
            if row["reason"] == "slot_position_ambiguous" and slots.count(row["slot"]) <= 1:
                raise ValueError("Support inventory ambiguous slot gaps require a repeated slot")


def _accounting(result):
    counts = result["accounting"]
    if result["client_layer"] != "captured":
        if result["members"] is not None or any(value is not None for value in counts.values()):
            raise ValueError("Support inventory unknown client layers require null members and counts")
        return
    members = _list(result["members"])
    for key in ("members", "effect_candidates", "excluded", "gaps"):
        _integer(counts[key], 0)
    expected = {"members": len(members), "effect_candidates": sum(row["status"] == "effect_candidates" for row in members),
                "excluded": sum(row["status"] == "excluded_category" for row in members),
                "gaps": sum(row["status"] == "gap" for row in members)}
    if (counts["reconciles"] is not True or any(counts[key] != value for key, value in expected.items())
            or counts["members"] != counts["effect_candidates"] + counts["excluded"] + counts["gaps"]):
        raise ValueError("Support inventory member accounting must reconcile exactly")


def _value(row, sign):
    for value in (row["exact"], row["range"]["min"], row["range"]["max"]):
        if type(value) is not str or not DECIMAL.fullmatch(value):
            raise ValueError("Support inventory values require bounded exact decimal text")
    value, low, high = (Decimal(value) for value in (row["exact"], row["range"]["min"], row["range"]["max"]))
    if not low <= value <= high or (sign == "+" and low < 0) or row["fraction"] != _fraction(row["exact"]):
        raise ValueError("Support inventory value range, sign and fraction must match exactly")


def _roll(row):
    _fixed(row, {"origin": "native_prefix_row", "status": "native_roll_exact", "unit": "percent"})
    _pattern(row["line_id"], r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    _pattern(row["native_id"], r"[A-Za-z0-9]{1,32}")
    _integer(row["tier"], None)
    _enum(row["template"], TEMPLATES)
    role, sign = TEMPLATES[row["template"]]
    _fixed(row, {"role": role})
    if len(row["values"]) != row["template"].count("#"):
        raise ValueError("Support inventory roll values must match the exact template arity")
    for value in row["values"]:
        _value(value, sign)
    if row["native_version"] is not None:
        _fixed(row["native_version"], {"meaning": "unverified"})
        _integer(row["native_version"]["value"], None)


def _prefixpaths(result):
    positions, identities, natives = [], set(), set()
    for rows in (result["rolled_lines"], result["omissions"]):
        offsets = []
        for row in rows:
            _fixed(row, {"origin": "native_prefix_row"})
            _pattern(row["path"], r"prefix\[(0|[1-9][0-9]*)\]")
            try:
                index = int(row["path"][7:-1])
            except ValueError:
                raise ValueError("Support inventory prefix coordinates exceed the integer limit") from None
            if index >= result["prefix"]["rows"]:
                raise ValueError("Support inventory prefix coordinates exceed the supplied row count")
            offsets.append(index)
            if "reason" in row:
                _enum(row["reason"], OMISSIONS)
            else:
                _roll(row)
                if row["line_id"] in identities or row["native_id"] in natives:
                    raise ValueError("Support inventory attributed line identities must be unique")
                identities.add(row["line_id"])
                natives.add(row["native_id"])
        if offsets != sorted(offsets):
            raise ValueError("Support inventory prefix evidence must preserve source row order")
        positions.extend(offsets)
    if len(positions) != len(set(positions)):
        raise ValueError("Support inventory prefix evidence cannot reuse a source row")
    if sum(row["reason"] == "duplicate_line" for row in result["omissions"]) == 1:
        raise ValueError("Support inventory duplicate omissions require all duplicate peers")


def _catalogsources(result):
    positions = []
    for rows in (result["constants"], result["constant_issues"]):
        offsets = []
        for row in rows:
            _fixed(row["source"], {"field": "templateDescription"})
            _integer(row["source"]["line"], 0)
            offsets.append(row["source"]["line"])
            if "reason" in row:
                _enum(row["reason"], ("unknown_constant", "placeholder_without_line"))
            else:
                _fixed(row, {"origin": "catalog_literal", "status": "catalog_literal_unverified_runtime"})
                _fixed(row["parameters"], PARAMETERS[row["kind"]])
        if offsets != sorted(offsets):
            raise ValueError("Support inventory catalog evidence must preserve LF line order")
        positions.extend(offsets)
    if len(positions) != len(set(positions)):
        raise ValueError("Support inventory catalog evidence cannot reuse a text line")


def _effects(document, canonical):
    result = _select(document, "format version identity arithmeticReady activation effectiveLevel patch runtimeVerified "
                     "additionalGroupIdentity prefix catalogSchema rolledLines omissions constants constantIssues", canonical)
    _fixed(result, {"format": EFFECT_FORMAT if canonical else RAW_EFFECT_FORMAT, "version": "0.2.0",
                    "arithmetic_ready": False, "runtime_verified": False, "activation": "unknown",
                    "effective_level": "unknown", "patch": "unknown", "additional_group_identity": "unresolved",
                    "catalog_schema": "ok"})
    result["identity"] = _select(result["identity"], "status catalogTlidbId nativeBaseId category guid", canonical)
    _fixed(result["identity"], {"status": "supplied_data_exact"})
    if result["identity"]["guid"] is not None:
        _pattern(result["identity"]["guid"], r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    result["prefix"] = _select(result["prefix"], "status rows nullRows", canonical)
    if result["rolled_lines"] is not None:
        rolls = []
        for raw in _list(result["rolled_lines"]):
            row = _select(raw, "origin path lineId nativeId tier role unit template values nativeVersion status", canonical)
            values = []
            for raw in _list(row["values"]):
                value = _select(raw, "exact fraction range", canonical)
                value["range"] = _select(value["range"], "min max", canonical)
                values.append(value)
            row["values"] = values
            if row["native_version"] is not None:
                row["native_version"] = _select(row["native_version"], "value meaning", canonical)
            rolls.append(row)
        result["rolled_lines"] = rolls
        result["omissions"] = [_select(row, "origin path reason", canonical) for row in _list(result["omissions"])]
    if result["constants"] is not None:
        constants = []
        for raw in _list(result["constants"]):
            row = _select(raw, "origin source kind parameters status", canonical)
            _enum(row["kind"], PARAMETERS)
            row["source"] = _select(row["source"], "field line", canonical)
            row["parameters"] = _select(row["parameters"], " ".join(PARAMETERS[row["kind"]]), canonical)
            constants.append(row)
        result["constants"] = constants
        issues = []
        for raw in _list(result["constant_issues"]):
            row = _select(raw, "source reason", canonical)
            row["source"] = _select(row["source"], "field line", canonical)
            issues.append(row)
        result["constant_issues"] = issues
    prefix = result["prefix"]
    _enum(prefix["status"], ("absent", "supplied"))
    if prefix["status"] == "absent":
        if any(value is not None for value in (prefix["rows"], prefix["null_rows"], result["rolled_lines"], result["omissions"])):
            raise ValueError("Support inventory absent prefixes require null counts and rows")
    else:
        _integer(prefix["rows"], 0)
        _integer(prefix["null_rows"], 0)
        if len(_list(result["rolled_lines"])) + len(_list(result["omissions"])) + prefix["null_rows"] != prefix["rows"]:
            raise ValueError("Support inventory prefix rows and null padding must reconcile")
        _prefixpaths(result)
    if (result["constants"] is None) != (result["constant_issues"] is None):
        raise ValueError("Support inventory missing constant descriptions require null sections")
    if result["constants"] is not None:
        _catalogsources(result)
    result["format"] = EFFECT_FORMAT
    return result


def _members(value, canonical):
    members = []
    for raw in _list(value):
        row = _select(raw, "alias group tabPosition groupStatus slot path baseId gemLevel category status reason effects", canonical)
        row["gem_level"] = _select(row["gem_level"], "value meaning", canonical)
        if row["effects"] is not None:
            row["effects"] = _effects(row["effects"], canonical)
        members.append(row)
    return members


def _projection(document, source_sha256, canonical):
    result = _select(document, "format version inventoryVersion effectsVersion source arithmeticReady runtimeVerified "
                     "identityVerified importComplete activation patch effectiveLevel clientLayer serverLayer members "
                     "accounting limitations", canonical)
    _fixed(result, {"format": FORMAT if canonical else RAW_FORMAT, "version": VERSION, "inventory_version": "0.1.2",
                    "effects_version": "0.2.0", **FLAGS})
    result["source"] = _select(result["source"], "sha256 binding", canonical)
    _hash(source_sha256)
    _hash(result["source"]["sha256"])
    _fixed(result["source"], {"binding": "caller_supplied_document_only"})
    if result["source"]["sha256"] != source_sha256:
        raise ValueError("Support inventory source SHA-256 does not match the supplied document")
    for key in ("client_layer", "server_layer"):
        _enum(result[key], ("captured", "absent", "invalid", "not_captured"))
    result["accounting"] = _select(result["accounting"], "members effectCandidates excluded gaps reconciles", canonical)
    if type(result["limitations"]) is not list or result["limitations"] != list(LIMITATIONS):
        raise ValueError("Support inventory requires the fixed diagnostic limitations")
    result["limitations"] = list(LIMITATIONS)
    if result["members"] is not None:
        result["members"] = _members(result["members"], canonical)
        _groups(result["members"])
    _accounting(result)
    result["format"] = FORMAT
    return result


def project(document, source_sha256):
    """Return a detached canonical diagnostic projection of producer 0.2.0."""
    return _projection(document, source_sha256, False)


def summary(document):
    """Revalidate an existing canonical projection and remove unknown properties at every depth."""
    source = _select(_select(document, "source", True)["source"], "sha256", True)
    return _projection(document, source["sha256"], True)
