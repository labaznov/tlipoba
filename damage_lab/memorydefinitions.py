"""Validate source-bound hero-memory definitions without resolving their combat roles."""

from decimal import Decimal
import math
import re


FORMAT = "tli-memory-definition-ledger-v1"
VERSION = "0.1.1"
ERROR = "Memory definitions contain an invalid source-bound diagnostic contract"
JEWELS = "sections.HeroCharacter.data.HeroJewels"
LISTS = ("BaseAttrInfoList", "BAffixInfoList", "SuffixInfoList", "PrefixInfoList", "EnchantAffixList", "ChipAffixList", "FixedBaseAffix")
MAPPED = LISTS[:4]
GROUPS = ("baseStats", "fixedAffixes", "randomAffixes", "revivedAffixes", "specialRandomAffixes")
TYPES = ("Origin", "Discipline", "Progress", "Any")
DISPOSITIONS = ("native_id_invalid", "no_exact_catalog_modifier", "ambiguous_catalog_modifier", "definition_invalid",
                "english_template_missing", "english_template_invalid", "memory_type_conflict", "own_value_invalid")
FLAGS = "arithmeticReady runtimeVerified identityVerified importComplete"
INDEX = r"(0|[1-9][0-9]{0,3})"
ROW = re.escape(JEWELS) + r"\[" + INDEX + r"\]\._Raw_Data\.AffixList\.(" + "|".join(LISTS) + r")\[" + INDEX + r"\]"


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _preflight(value):
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
            _require(-10 ** 20 < node < 10 ** 20)
        elif type(node) is float:
            _require(math.isfinite(node))
        else:
            _require(node is None or type(node) is bool)


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower().lstrip("_")


def _select(value, fields, canonical):
    names = {_name(field) if canonical else field: _name(field) for field in fields.split()}
    _require(type(value) is dict and set(names).issubset(value))
    return {target: value[source] for source, target in names.items()}


def _pattern(value, pattern):
    _require(type(value) is str)
    match = re.fullmatch(pattern, value, re.ASCII)
    _require(match is not None)
    return match


def _enum(value, choices):
    _require(type(value) is str and value in choices)


def _integer(value, minimum=0, maximum=10 ** 18):
    _require(type(value) is int and minimum <= value < maximum)


def _list(value):
    _require(type(value) is list)
    return value


def _decimal(value):
    _pattern(value, r"-?[0-9]{1,12}(?:\.[0-9]{1,9})?")
    return Decimal(value)


def _row(value, canonical, jewels):
    result = _select(value, "alias path nativeId disposition", canonical)
    match = _pattern(result["path"], ROW)
    jewel, name, index = int(match[1]), match[2], int(match[3])
    _require(jewel < jewels and index < 4096 and result["alias"] == f"heroMemory[{jewel}].{name}[{index}]")
    return result, (jewel, name, index)


def _tier(value, canonical):
    result = _select(value, "tier level literal range sign unit", canonical)
    _integer(result["tier"])
    if result["level"] is not None:
        _integer(result["level"])
    _require(result["sign"] is None or type(result["sign"]) is str and result["sign"] in ("+", "-"))
    _require(result["unit"] is None or result["unit"] == "%")
    _require((result["literal"] is None) != (result["range"] is None))
    if result["literal"] is not None:
        _decimal(result["literal"])
    else:
        result["range"] = _select(result["range"], "min max", canonical)
        _require(_decimal(result["range"]["min"]) <= _decimal(result["range"]["max"]))
    return result


def _mirror(value, canonical, name):
    result = _select(value, "status issue", canonical)
    if name not in MAPPED:
        _require(result == {"status": "unknown", "issue": "mirror_list_unmapped"})
        return result
    _enum(result["status"], ("same", "different", "unknown", "absent"))
    if result["status"] in ("same", "absent"):
        _require(result["issue"] is None)
    elif result["status"] == "different":
        _require(result["issue"] is None or result["issue"] == "length_mismatch")
    else:
        _enum(result["issue"], ("mirror_value_invalid", "mirror_ambiguous", "mirror_container_invalid", "mirror_row_invalid"))
    return result


def _type(value, canonical, catalog):
    result = _select(value, "catalog helper status basis", canonical)
    _require(result["catalog"] == catalog and result["basis"] == "helper_TYPES_convention")
    if result["helper"] is not None:
        _enum(result["helper"], TYPES[:3])
    status = "catalog_any" if catalog == "Any" else "unknown" if result["helper"] is None else "consistent"
    _require(result["status"] == status and (catalog == "Any" or result["helper"] is None or result["helper"] == catalog))
    return result


def _candidate(value, canonical, jewels):
    result, coordinates = _row(value, canonical, jewels)
    _integer(result["native_id"], 1, 10 ** 20)
    _require(result["disposition"] == "exact_definition")
    details = _select(value, "definition template catalogTier ownValues serverMirror nativeConditions memoryType "
                      "operator activation rankScaling lineRoles runtimePoolIdentity", canonical)
    definition = _select(details["definition"], "logicalPath group id modifierId memoryType", canonical)
    _require(definition["logical_path"] == "hero-memory/master" and definition["modifier_id"] == str(result["native_id"]))
    _enum(definition["group"], GROUPS)
    _pattern(definition["id"], r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    _enum(definition["memory_type"], TYPES)
    template = _select(details["template"], "text source", canonical)
    _require(template["source"] == "hero-memory/i18n/en")
    _pattern(template["text"], r"[^\x00-\x09\x0b-\x1f\x7f]{1,1024}")
    rows = []
    for index, value in enumerate(_list(details["own_values"])):
        row = _select(value, "index exact source", canonical)
        _require(type(row["index"]) is int and row["index"] == index and row["source"] == f"DynArgs[{index}]")
        _decimal(row["exact"])
        rows.append(row)
    conditions = _select(details["native_conditions"], "Condition Filter Behavior", canonical)
    for state in conditions.values():
        _enum(state, ("empty", "present", "missing", "invalid"))
    for key, expected in (("operator", "unresolved"), ("activation", "unknown"), ("rank_scaling", "unknown"),
                          ("line_roles", "unresolved"), ("runtime_pool_identity", "unresolved")):
        _require(details[key] == expected)
    details.update(definition=definition, template=template, catalog_tier=_tier(details["catalog_tier"], canonical),
                   own_values=rows, native_conditions=conditions,
                   server_mirror=_mirror(details["server_mirror"], canonical, coordinates[1]),
                   memory_type=_type(details["memory_type"], canonical, definition["memory_type"]))
    result.update(details)
    return result, coordinates


def _omission(value, canonical, jewels):
    result, coordinates = _row(value, canonical, jewels)
    _enum(result["disposition"], DISPOSITIONS)
    if result["disposition"] == "native_id_invalid":
        _require(result["native_id"] is None)
    else:
        _integer(result["native_id"], 1, 10 ** 20)
    return result, coordinates


def _gap(value, canonical, jewels):
    result = _select(value, "path reason", canonical)
    _enum(result["reason"], ("jewel_invalid", "affix_list_invalid", "affix_container_invalid", "row_invalid"))
    pattern = re.escape(JEWELS) + r"\[" + INDEX + r"\]"
    if result["reason"] != "jewel_invalid":
        pattern += r"\._Raw_Data\.AffixList"
    if result["reason"] in ("affix_container_invalid", "row_invalid"):
        pattern += r"\.(" + "|".join(LISTS) + r")"
    if result["reason"] == "row_invalid":
        pattern += r"\[" + INDEX + r"\]"
    match = _pattern(result["path"], pattern)
    coordinates = tuple(int(part) if index != 1 else part for index, part in enumerate(match.groups()))
    _require(coordinates[0] < jewels and (len(coordinates) < 3 or coordinates[2] < 4096))
    return result, coordinates


def _captured(result, canonical):
    counts = result["accounting"]
    for key, value in counts.items():
        if key != "reconciles":
            _integer(value)
    _require(counts["jewels"] <= 4096 and counts["reconciles"] is True)
    if counts["jewels"] == 0:
        _require(all(value == 0 for key, value in counts.items() if key != "reconciles"))
    scopes = []
    for field, projector in (("candidates", _candidate), ("omitted", _omission), ("structural_gaps", _gap)):
        rows = []
        for value in _list(result[field]):
            row, scope = projector(value, canonical, counts["jewels"])
            _require(all(scope != previous[:len(scope)] and previous != scope[:len(previous)] for previous in scopes))
            scopes.append(scope)
            rows.append(row)
        result[field] = rows
        _require(counts[field] == len(rows))
    _require(counts["rows"] == counts["candidates"] + counts["omitted"])
    definitions = {}
    for row in result["candidates"]:
        facts = {key: row[key] for key in ("definition", "template", "catalog_tier")}
        _require(definitions.setdefault(row["native_id"], facts) == facts)
    candidates = {row["native_id"] for row in result["candidates"]}
    rejected = {row["native_id"] for row in result["omitted"] if row["disposition"] not in ("native_id_invalid", "memory_type_conflict", "own_value_invalid")}
    _require(not candidates.intersection(rejected))
    ambiguous = {row["native_id"] for row in result["omitted"] if row["disposition"] == "ambiguous_catalog_modifier"}
    known = candidates | {row["native_id"] for row in result["omitted"] if row["disposition"] not in ("native_id_invalid", "no_exact_catalog_modifier")}
    _require(len(ambiguous) <= result["catalog"]["collisions"] and len(known) <= result["catalog"]["modifier_ids"])
    _require(all(row["definition"]["group"] not in result["catalog"]["invalid_groups"] for row in result["candidates"]))


def _project(value, source_sha256, canonical):
    _preflight(value)
    _pattern(source_sha256, r"[0-9a-f]{64}")
    result = _select(value, "format version source " + FLAGS + " catalog domain candidates omitted structuralGaps accounting", canonical)
    _require(result["format"] == FORMAT and result["version"] == VERSION)
    for flag in FLAGS.split():
        _require(result[_name(flag)] is False)
    source = _select(result["source"], "sha256 binding", canonical)
    _require(source["sha256"] == source_sha256 and source["binding"] == "caller_supplied")
    catalog = _select(result["catalog"], "logicalPaths modifierIds collisions invalidEntries invalidGroups", canonical)
    _require(type(catalog["logical_paths"]) is list and catalog["logical_paths"] == ["hero-memory/master", "hero-memory/i18n/en"])
    for key in ("modifier_ids", "collisions", "invalid_entries"):
        _integer(catalog[key])
    _require(catalog["collisions"] <= catalog["modifier_ids"])
    for group in _list(catalog["invalid_groups"]):
        _enum(group, GROUPS)
    _require(len(catalog["invalid_groups"]) == len(set(catalog["invalid_groups"])))
    catalog.update(logical_paths=list(catalog["logical_paths"]), invalid_groups=list(catalog["invalid_groups"]))
    domain = _select(result["domain"], "status path", canonical)
    _require(domain["path"] == JEWELS)
    _enum(domain["status"], ("captured", "absent", "not_captured", "invalid"))
    accounting = _select(result["accounting"], "jewels rows emptySlots candidates omitted structuralGaps reconciles", canonical)
    result.update(source=source, catalog=catalog, domain=domain, accounting=accounting)
    if domain["status"] == "captured":
        _captured(result, canonical)
    else:
        _require(all(result[field] is None for field in ("candidates", "omitted", "structural_gaps"))
                 and all(number is None for number in accounting.values()))
    return result


def project(raw, source_sha256):
    """Project the pinned compiler DTO and compare its declared source with the caller's hash."""
    return _project(raw, source_sha256, False)


def summary(canonical):
    """Revalidate a detached canonical ledger without authenticating source or catalog bytes."""
    _require(type(canonical) is dict and type(canonical.get("source")) is dict)
    return _project(canonical, canonical["source"].get("sha256"), True)
