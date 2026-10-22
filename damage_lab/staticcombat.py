"""Validate a source-bound static modifier ledger without applying combat effects."""

import re
from decimal import Context, Decimal, localcontext

from .fixedimplicit import ENGLISH, MASTER


FORMAT = "tli-static-combat-modifiers-v1"
VERSIONS = ("0.3.2", "0.4.0", "0.4.1", "0.4.2")
CRITICAL = {"critical_rating_increased": "rating_increase", "critical_damage_modifier": "unresolved"}
EVIDENCE_ISSUES = ("evidence_definition_shape", "evidence_spec_invalid", "evidence_value_invalid")
AFFIXES = ("BaseAttrInfoList", "BAffixInfoList", "PrefixInfoList", "SuffixInfoList", "EnchantAffixList",
           "ChipAffixList", "FixedBaseAffix")
REASONS = ("item_unresolved", "invalid_record", "no_exact_definition", "ambiguous_exact_definition",
           "list_group_mismatch", "variant_template_unverified", "unsupported_family", "scope_unverified",
           "unknown_unit", "unknown_condition", "value_count_mismatch", "invalid_numeric", "value_out_of_range",
           "value_range_inverted")
IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
TIER = r"[0-9]{1,3}\+?"
ELEMENTS = ("physical", "cold", "fire", "lightning", "erosion")
ATTRIBUTES = ("strength", "dexterity", "intelligence")
COMBINATIONS = {
    "flat_added_damage": {((element,), scope, "player") for element in ELEMENTS for scope in ("spell", "attack")},
    "increased_damage": ({((target,), "any", "player") for target in ELEMENTS + ("damage", "elemental")}
                         | {(("damage",), scope, "player") for scope in ("spell", "attack", "projectile", "melee", "deterioration")}
                         | {(("damage",), "any", "minion")}),
    "flat_attribute": {((attribute,), "any", "player") for attribute in ATTRIBUTES},
    "increased_attribute": {((attribute,), "any", "player") for attribute in ATTRIBUTES},
    "increased_speed": {(("cast_speed",), "any", "player"), (("attack_speed", "cast_speed"), "any", "player"),
                        (("attack_speed", "cast_speed"), "any", "minion")},
    "critical_rating_increased": {(("critical_rating",), "any", "player")},
    "critical_damage_modifier": {(("critical_damage",), scope, "player") for scope in ("any", "spell")}}


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Static combat requires all named contract fields")


def _select(row, fields, canonical, optional=()):
    names = {_name(field) if canonical else field: _name(field) for field in fields + optional}
    _object(row, tuple(_name(field) if canonical else field for field in fields))
    return {target: row[source] for source, target in names.items() if source in row}


def _list(value):
    if type(value) is not list:
        raise ValueError("Static combat requires JSON lists")
    return value


def _pattern(value, pattern):
    if type(value) is not str or not re.fullmatch(pattern, value, re.ASCII):
        raise ValueError("Static combat has an invalid typed contract value")


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError("Static combat has an unknown contract status")


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Static combat counts require nonnegative integers")


def _catalog(catalog, version):
    for path, row in catalog["documents"].items():
        _pattern(path, r"(?:gear|legendaries)/[A-Za-z0-9_./-]+")
        if len(path) > 256:
            raise ValueError("Static combat logical catalog paths exceed the producer limit")
        _pattern(row["sha256"], "[0-9a-f]{64}")
        if "role" in row or path.endswith("/i18n/en"):
            if version != "0.4.2" or path != ENGLISH or row.get("role") != "english":
                raise ValueError("Static combat English roles require the supported paired wand member and compiler version")
        _enum(row["status"], ("ok", "invalid"))
        if row["status"] == "ok":
            if row["issue"] is not None:
                raise ValueError("Static combat valid catalog documents cannot have an issue")
        else:
            _enum(row["issue"], ("not_json_object", "duplicate_key", "parse_limit", "container_shape", "identity_leaf"))
        if row["season_id"] is not None:
            _pattern(row["season_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}")
        if row["schema_version"] is not None:
            _count(row["schema_version"])
            if row["schema_version"] >= 1000000:
                raise ValueError("Static combat catalog schema version exceeds the producer limit")
    expected = []
    if any(row["status"] == "invalid" for row in catalog["documents"].values()):
        expected.append("catalog_document_invalid")
    if len({row["season_id"] for row in catalog["documents"].values()
            if row["status"] == "ok" and "role" not in row}) > 1:
        expected.append("catalog_season_mixed")
    if catalog["flags"] != expected:
        raise ValueError("Static combat catalog flags must agree with its documents")


def _accounting(result):
    counts = result["accounting"]
    for key in ("items", "empty_rows", "observed", "compiled", "omitted", "structural_gaps"):
        _count(counts[key])
    if (counts["reconciles"] is not True or counts["observed"] != counts["compiled"] + counts["omitted"]
            or any(counts[key] != len(result[key]) for key in ("items", "omitted", "structural_gaps"))
            or counts["compiled"] != len(result["modifiers"])):
        raise ValueError("Static combat counts must reconcile with the ledger rows")
    if counts["scope"] != ("known_rows_only" if result["structural_gaps"] else "all_rows"):
        raise ValueError("Static combat accounting scope must disclose structural gaps")
    captured = result["source"]["section"] == "captured"
    if captured != bool(result["items"]) or (not captured and any(counts[key] for key in
            ("items", "empty_rows", "observed", "compiled", "omitted", "structural_gaps"))):
        raise ValueError("Static combat source state must agree with its captured inventory")


def _identity(row, canonical):
    return _select(row, ("status",), canonical, ("kind", "catalog", "definition", "tlidbId"))


def _items(result):
    for index, row in enumerate(result["items"]):
        if row["alias"] != f"gear[{index}]" or row["path"] != f"sections.WearItems.data[{index}]":
            raise ValueError("Static combat item aliases and paths must retain their source coordinates")
        identity = row["identity"]
        _enum(identity["status"], ("exact", "invalid_record", "unsupported_item_kind", "no_exact_item", "ambiguous_item"))
        fields = {"status"}
        if identity["status"] == "exact":
            fields.update(("kind", "catalog", "definition", "tlidb_id"))
            _object(identity, fields)
            _pattern(identity["definition"], IDENTIFIER)
            _pattern(identity["tlidb_id"], r"[1-9][0-9]{0,19}")
            path = identity["catalog"]
            if (type(path) is not str or path not in result["catalog"]["documents"]
                    or result["catalog"]["documents"][path]["status"] != "ok"
                    or "role" in result["catalog"]["documents"][path]):
                raise ValueError("Static combat exact item identity requires a valid supplied catalog")
            prefix = "gear/" if identity["kind"] == "base" else "legendaries/"
            if not path.startswith(prefix):
                raise ValueError("Static combat item kind must agree with its catalog category")
        elif identity["status"] == "ambiguous_item" or (identity["status"] == "no_exact_item" and "kind" in identity):
            fields.add("kind")
        if set(identity) != fields:
            raise ValueError("Static combat unresolved items cannot retain exact identity claims")
        if "kind" in identity:
            _enum(identity["kind"], ("base", "legendary"))


def _modifier(row, canonical, version):
    result = _select(row, ("item", "path", "list", "nativeId", "family", "targets", "scope", "owner",
                           "appliesToPlayerSpell", "unit", "values", "definition", "pool", "templateSign", "status"), canonical)
    result["targets"] = list(_list(result["targets"]))
    result["values"] = [_select(value, ("exact", "source"), canonical, ("fraction",)) for value in _list(result["values"])]
    fixed = "fixed_implicit" if canonical else "fixedImplicit"
    result["definition"] = _select(result["definition"], ("catalog", "id"), canonical,
                                   ("templateSource", "tier", "tierId", "variant", "implicit"))
    result["pool"] = _select(result["pool"], ("id", "status", "basis"), canonical)
    _enum(result["family"], tuple(COMBINATIONS))
    if result["family"] in CRITICAL:
        if version not in ("0.4.0", "0.4.1", "0.4.2"):
            raise ValueError("Static critical inventory requires a supported critical compiler version")
        if result["template_sign"] != "+":
            raise ValueError("Static critical inventory requires an exact positive template sign")
        _object(row, ("semantics",))
        result["semantics"] = _select(row["semantics"], ("operation", "valueRole", "arithmeticReady"), canonical)
        semantics = result["semantics"]
        if (semantics["operation"] != CRITICAL[result["family"]] or semantics["value_role"] != "non_additional_percent"
                or semantics["arithmetic_ready"] is not False):
            raise ValueError("Static critical inventory cannot choose an operator or enable arithmetic")
    elif "semantics" in row:
        raise ValueError("Static critical semantics cannot be attached to another modifier family")
    if fixed in row:
        if version != "0.4.2":
            raise ValueError("Static fixed implicit proofs require compiler version 0.4.2")
        from .fixedimplicit import project, summary

        result["fixed_implicit"] = summary(row[fixed]) if canonical else project(row[fixed])
    _vocabulary(result)
    return result


def _native(value, compiled=False):
    if value is None and not compiled:
        return
    if type(value) is not int or not -10 ** 100 < value < 10 ** 100 or (compiled and not 0 < value < 10 ** 20):
        raise ValueError("Static combat native identifiers require bounded integers")


def _vocabulary(row):
    _native(row["native_id"], True)
    _enum(row["scope"], ("any", "spell", "attack", "projectile", "melee", "deterioration"))
    _enum(row["owner"], ("player", "minion"))
    _enum(row["status"], ("compiled_unverified_runtime",))
    if row["template_sign"] is not None:
        _enum(row["template_sign"], ("+", "-"))
    targets = row["targets"]
    for value in targets:
        _enum(value, ("physical", "cold", "fire", "lightning", "erosion", "damage", "elemental",
                      "strength", "dexterity", "intelligence", "attack_speed", "cast_speed", "critical_rating", "critical_damage"))
    if not targets or len(set(targets)) != len(targets):
        raise ValueError("Static combat targets must be distinct known names")
    if (tuple(targets), row["scope"], row["owner"]) not in COMBINATIONS[row["family"]]:
        raise ValueError("Static combat family, targets, scope and owner must match a supported producer combination")
    expected = False if row["scope"] == "attack" or row["owner"] != "player" else True if row["scope"] in ("spell", "any") else None
    if row["applies_to_player_spell"] is not expected:
        raise ValueError("Static combat player-spell applicability must agree with scope and owner")
    unit = "flat" if row["family"] in ("flat_added_damage", "flat_attribute") else "percent"
    if row["unit"] != unit or len(row["values"]) != (2 if row["family"] == "flat_added_damage" else 1):
        raise ValueError("Static combat units and value counts must match the declared family")
    for index, value in enumerate(row["values"]):
        _pattern(value["exact"], r"-?[0-9]{1,12}(?:\.[0-9]{1,9})?")
        if value["source"] != f"DynArgs[{index}]" or ("fraction" in value) != (unit == "percent"):
            raise ValueError("Static combat values require exact indexed sources and matching fractional units")
        if unit == "percent":
            _pattern(value["fraction"], r"-?[0-9]{1,24}(?:\.[0-9]{1,24})?(?:E[+-]?[0-9]{1,2})?")
            with localcontext(Context(prec=32)):
                if Decimal(value["fraction"]) != Decimal(value["exact"]) / 100:
                    raise ValueError("Static combat fractions must equal their exact percent values divided by 100")
    if row["family"] == "flat_added_damage" and Decimal(row["values"][0]["exact"]) > Decimal(row["values"][1]["exact"]):
        raise ValueError("Static combat flat damage intervals cannot be inverted")


def _definition(row, identity):
    definition, pool = row["definition"], row["pool"]
    _pattern(definition["id"], IDENTIFIER)
    if definition["catalog"] != identity["catalog"]:
        raise ValueError("Static combat modifier definitions must use their source item's catalog")
    if "fixed_implicit" in row:
        if (set(definition) != {"catalog", "id", "implicit"} or definition["implicit"] is not True
                or pool != {"id": None, "status": "unresolved", "basis": "fixed_implicit_identity_unresolved"}):
            raise ValueError("Static fixed implicit definitions require an implicit identity and an unresolved pool")
        return
    if identity["kind"] == "base":
        if set(definition) != {"catalog", "id", "tier", "tier_id", "template_source"}:
            raise ValueError("Static combat base definitions require their exact tier metadata")
        _pattern(definition["tier_id"], IDENTIFIER)
        if definition["tier"] is not None:
            _pattern(definition["tier"], TIER)
        if definition["template_source"] != "descriptionTemplate":
            raise ValueError("Static combat base definitions require their own description template")
        basis = "gear_entry"
    else:
        if set(definition) != {"catalog", "id", "variant", "template_source"}:
            raise ValueError("Static combat legendary definitions require their exact variant metadata")
        _enum(definition["variant"], ("normal", "corroded"))
        expected = "corrodedDescriptionTemplate" if definition["variant"] == "corroded" else "descriptionTemplate"
        if definition["template_source"] != expected:
            raise ValueError("Static combat legendary variants require their own description template")
        basis = "legendary_mod" if definition["variant"] == "normal" else "legendary_mod_same_template"
    if identity["kind"] == "legendary" and definition["variant"] == "corroded" and pool["status"] == "unresolved":
        if pool != {"id": None, "status": "unresolved", "basis": "variant_template_differs"}:
            raise ValueError("Static combat unresolved variant pools must retain their explicit null identity")
    elif pool != {"id": definition["id"], "status": "exact", "basis": basis}:
        raise ValueError("Static combat exact pools must agree with their public definition identity")


def _omission(row, canonical, version):
    result = _select(row, ("item", "path", "list", "nativeId", "reason"), canonical)
    if ("fixed_implicit" if canonical else "fixedImplicit") in row:
        raise ValueError("Static fixed implicit proofs cannot be attached to omitted rows")
    issue = "evidence_issue" if canonical else "evidenceIssue"
    if "evidence" in row or issue in row:
        if version not in ("0.4.1", "0.4.2"):
            raise ValueError("Static cast evidence requires a supported cast compiler version")
        if "evidence" in row and issue in row:
            raise ValueError("Static cast evidence cannot also contain an evidence issue")
    if "evidence" in row:
        from .castevidence import project, summary

        result["evidence"] = summary(row["evidence"]) if canonical else project(row["evidence"])
    if issue in row:
        _enum(row[issue], EVIDENCE_ISSUES)
        result["evidence_issue"] = row[issue]
    return result


def _fixed(row, item, catalog):
    identity, proof = item["identity"], row["fixed_implicit"]
    if (row["native_id"] != 520020 or row["list"] != "FixedBaseAffix" or len(row["path"]) > 256
            or (row["family"], row["targets"], row["scope"], row["owner"], row["unit"], row["template_sign"])
            != ("increased_damage", ["damage"], "spell", "player", "percent", "+")
            or identity["kind"] != "base" or identity["catalog"] != MASTER
            or row["definition"]["id"] != identity["definition"]):
        raise ValueError("Static fixed implicit proofs require the exact wand spell-damage row and item")
    if (proof["master"]["catalog"] != identity["catalog"]
            or proof["master"]["item_guid"] != identity["definition"]
            or proof["master"]["tlidb_id"] != identity["tlidb_id"]
            or proof["own_value"] != {"exact": row["values"][0]["exact"], "source": row["values"][0]["source"]}):
        raise ValueError("Static fixed implicit proof identities and own values must agree with their source row")
    for entry in (proof["master"], proof["english"]):
        document = catalog["documents"].get(entry["catalog"])
        if (document is None or document["status"] != "ok" or document["sha256"] != entry["sha256"]
                or (entry["catalog"] == ENGLISH and document.get("role") != "english")):
            raise ValueError("Static fixed implicit proofs require their valid catalog member hashes")


def _rows(result):
    items = {row["alias"]: row for row in result["items"]}
    seen = set()
    for key in ("modifiers", "omitted", "structural_gaps"):
        for row in result[key]:
            if type(row["item"]) is not str or row["item"] not in items:
                raise ValueError("Static combat rows must reference a known item alias")
            item = items[row["item"]]
            if key == "structural_gaps":
                _enum(row["reason"], ("invalid_record", "invalid_affix_list", "invalid_affix_container"))
                base = item["path"]
                paths = {base} if row["reason"] == "invalid_record" else (
                    {base + ".sourceData", base + ".sourceData.AffixList"} if row["reason"] == "invalid_affix_list" else
                    {base + ".sourceData.AffixList." + name for name in AFFIXES})
                if type(row["path"]) is not str or row["path"] not in paths:
                    raise ValueError("Static combat structural gaps require fixed source-container paths")
                if row["reason"] != "invalid_affix_container" and item["identity"]["status"] != "invalid_record":
                    raise ValueError("Static combat malformed item containers require invalid-record identity")
            else:
                _enum(row["list"], AFFIXES)
                _pattern(row["path"], re.escape(item["path"] + ".sourceData.AffixList." + row["list"]) + r"\[(?:0|[1-9][0-9]*)\]")
                if key == "modifiers":
                    if item["identity"]["status"] != "exact":
                        raise ValueError("Static combat compiled modifiers require an exact item identity")
                    _definition(row, item["identity"])
                    if "fixed_implicit" in row:
                        _fixed(row, item, result["catalog"])
                else:
                    _native(row["native_id"])
                    _enum(row["reason"], REASONS)
                    if "evidence" in row:
                        _native(row["native_id"], True)
                        identity = item["identity"]
                        if (row["reason"] != "unsupported_family" or identity["status"] != "exact"
                                or identity["kind"] != "base"
                                or row["evidence"]["definition"]["catalog"] != identity["catalog"]):
                            raise ValueError("Static cast evidence requires its exact omitted base-item binding")
                    elif "evidence_issue" in row:
                        _native(row["native_id"], True)
                        if row["reason"] != "unsupported_family" or item["identity"]["status"] != "exact":
                            raise ValueError("Static cast evidence issues require an exactly identified omitted item")
                        if (item["identity"]["kind"] != "base"
                                and row["evidence_issue"] != "evidence_definition_shape"):
                            raise ValueError("Static cast numeric evidence issues require a base-item definition")
            if row["path"] in seen:
                raise ValueError("Static combat ledger rows require distinct source paths")
            seen.add(row["path"])
    for gap in result["structural_gaps"]:
        if any(path == gap["path"] or path.startswith(gap["path"] + ".") or path.startswith(gap["path"] + "[")
               for path in seen if path != gap["path"]):
            raise ValueError("Static combat invalid source containers cannot also contain observed rows")


def _project(document, source_sha256, canonical):
    result = _select(document, ("format", "version", "source", "catalog", "runtime", "items", "modifiers", "omitted",
                               "structuralGaps", "accounting"), canonical)
    result["source"] = _select(result["source"], ("sha256", "section"), canonical)
    _pattern(source_sha256, "[0-9a-f]{64}")
    if (result["format"] != FORMAT or result["version"] not in VERSIONS or result["source"]["sha256"] != source_sha256):
        raise ValueError("Static combat format, version and source hash must match the package contract")
    _enum(result["source"]["section"], ("captured", "absent", "invalid", "empty"))
    catalog = _select(result["catalog"], ("documents", "flags"), canonical)
    _object(catalog["documents"], ())
    result["catalog"] = {
        "documents": {path: _select(row, ("sha256", "status", "issue", "seasonId", "schemaVersion"), canonical, ("role",))
                      for path, row in catalog["documents"].items()}, "flags": list(_list(catalog["flags"]))}
    _catalog(result["catalog"], result["version"])
    result["runtime"] = _select(result["runtime"], ("verified", "selectionVerified", "sourcePatch", "activation"), canonical)
    runtime = result["runtime"]
    if (runtime["verified"] is not False or runtime["selection_verified"] is not False
            or runtime["source_patch"] != "unknown" or runtime["activation"] != "unverified"):
        raise ValueError("Static combat cannot verify runtime, selection, patch or activation")
    result["items"] = [_select(row, ("alias", "path", "identity"), canonical) for row in _list(result["items"])]
    for row in result["items"]:
        row["identity"] = _identity(row["identity"], canonical)
    _items(result)
    result["modifiers"] = [_modifier(row, canonical, result["version"]) for row in _list(result["modifiers"])]
    result["omitted"] = [_omission(row, canonical, result["version"])
                         for row in _list(result["omitted"])]
    result["structural_gaps"] = [_select(row, ("item", "path", "reason"), canonical)
                                 for row in _list(result["structural_gaps"])]
    _rows(result)
    result["accounting"] = _select(result["accounting"], ("items", "emptyRows", "observed", "compiled", "omitted",
                                                        "structuralGaps", "reconciles", "scope"), canonical)
    _accounting(result)
    return result


def project(document, source_sha256):
    """Return detached, source-bound inventory evidence with no runtime verification."""
    return _project(document, source_sha256, False)


def summary(data):
    """Revalidate a canonical ledger through the same safe projection contract."""
    _object(data, ("source",))
    _object(data["source"], ("sha256",))
    return _project(data, data["source"]["sha256"], True)
