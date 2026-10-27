"""Project diagnostic trait candidates without selecting a rule or a damage multiplier."""

import re


FORMAT = "tli-trait-rank-candidates-v1"
STATUS = "rank_rule_unverified"
RULES = {"client_fixed": "C", "fixed_plus_enhance": "C + E"}
LEGACY_ASSUMPTION = "Legacy C = S + F labels are an unverified catalog hypothesis, not source facts"
FIELDS = {"clientFixed": ("client_fixed", "ReminiscenceFixedLevel"),
          "fromEnhance": ("from_enhance", "ReminiscenceFixedLevelFromEnhance"),
          "serverFixed": ("server_fixed", "ServerPlayerItem.ReminiscenceFixedLevel"),
          "level": ("level", "ReminiscenceLevel")}


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Trait candidates require an object with all contract fields")


def _list(value):
    if type(value) is not list:
        raise ValueError("Trait candidates require JSON lists")


def _texts(value):
    _list(value)
    if any(type(row) is not str or not row.strip() for row in value):
        raise ValueError("Trait candidate notes must contain nonempty text")
    return list(value)


def _count(value, nullable=False):
    if value is None and nullable:
        return value
    if type(value) is not int or value < 0:
        raise ValueError("Trait candidate counts must be nonnegative integers")
    return value


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError("Unknown trait candidate status")
    return value


def _memory(row, v011=False):
    _object(row, ("position", "baseId", "fields", "fixedAffixContribution", "fixedAffixSource", "consistency", "linkage"))
    position = _count(row["position"])
    path = f"sections.HeroCharacter.data.HeroJewels[{position}]._Raw_Data"
    _object(row["fields"], FIELDS)
    fields = {}
    for key, (name, suffix) in FIELDS.items():
        field = row["fields"][key]
        _object(field, ("path", "status", "value"))
        status = _enum(field["status"], ("ok", "missing", "invalid"))
        if field["path"] != f"{path}.{suffix}" or (status != "ok" and field["value"] is not None):
            raise ValueError("Trait candidate field path or status differs from its source contract")
        fields[name] = {"path": field["path"], "status": status,
                        "value": _count(field["value"]) if status == "ok" else None}
    contribution = _count(row["fixedAffixContribution"], nullable=True)
    client, server = fields["client_fixed"]["value"], fields["server_fixed"]["value"]
    if v011:
        consistency = "unchecked"
    else:
        consistency = "unchecked" if None in (client, server, contribution) else "consistent" if client == server + contribution else "conflict"
    if row["consistency"] != consistency or row["fixedAffixSource"] != f"{path}.ServerPlayerItem.BaseAffix":
        raise ValueError("Trait candidate memory consistency or affix path differs from its inputs")
    _object(row["linkage"], ("status",))
    status = _enum(row["linkage"]["status"], ("index_match", "index_mismatch", "duplicate_server_entry",
                   "not_in_server_overview", "missing_item_id", "invalid_server_index", "not_active", "unverified"))
    linkage = {"status": status}
    if status in ("index_match", "index_mismatch"):
        key = "slot" if status == "index_match" else "serverIndex"
        _object(row["linkage"], (key,))
        value = _count(row["linkage"][key])
        if (value == position + 1) != (status == "index_match"):
            raise ValueError("Trait candidate linkage index differs from its status")
        linkage["slot" if key == "slot" else "server_index"] = value
    return {"position": position, "base_id": _count(row["baseId"], nullable=True), "fields": fields,
            "fixed_affix_contribution": contribution, "fixed_affix_source": row["fixedAffixSource"],
            "consistency": consistency, "linkage": linkage}


def _candidate(row, memory):
    _object(row, ("rule", "formula", "inputs", "value", "status"))
    rule = _enum(row["rule"], RULES)
    parts = [memory["fields"]["client_fixed"]]
    if rule == "fixed_plus_enhance":
        parts.append(memory["fields"]["from_enhance"])
    inputs = _texts(row["inputs"])
    if row["formula"] != RULES[rule] or inputs != [part["path"] for part in parts]:
        raise ValueError("Trait candidate formula and inputs must match its named rule")
    statuses = {part["status"] for part in parts}
    value = None
    if "invalid" in statuses:
        status = "invalid_input"
    elif "missing" in statuses:
        status = "missing_input"
    else:
        value = sum(part["value"] for part in parts)
        status = ("input_conflict" if memory["consistency"] == "conflict"
                  else _enum(row["status"], (STATUS, "unknown_tier_table", "out_of_range")))
        if status == STATUS and value == 0:
            raise ValueError("A usable trait candidate requires a positive table rank")
    if row["status"] != status or _count(row["value"], nullable=True) != value:
        raise ValueError("Trait candidate value or status differs from its explicit inputs")
    return {"rule": rule, "formula": RULES[rule], "inputs": inputs, "value": value, "status": status}


def _trait(row, memories, indexes):
    _object(row, ("traitId", "index", "rank", "memoryPosition", "status", "candidates", "candidatesAgree"))
    identifier = row["traitId"]
    if identifier is not None and (type(identifier) is not str or not re.fullmatch("[1-9][0-9]*", identifier)):
        raise ValueError("Trait ID must be a decimal string or an explicitly invalid null")
    index = _count(row["index"], nullable=True)
    position = _count(row["memoryPosition"], nullable=True)
    _list(row["candidates"])
    if row["rank"] is not None:
        raise ValueError("Trait candidate documents cannot select a rank")
    memory = memories.get(index - 1) if index else None
    candidates = []
    agreement = None
    if identifier is None or index is None:
        status = "invalid_index"
    elif indexes.count(index) > 1:
        status = "duplicate_index"
    elif index == 0:
        status = "no_verified_source"
    elif memory is None:
        status = _enum(row["status"], ("no_memory_linked", "slot_link_conflict"))
    elif memory["linkage"]["status"] != "index_match":
        status = "slot_link_unverified"
    elif row["status"] == "slot_link_conflict":
        status = "slot_link_conflict"
    else:
        if position != memory["position"]:
            raise ValueError("Trait candidate memory position differs from its linked slot")
        candidates = [_candidate(value, memory) for value in row["candidates"]]
        if len(candidates) != 2 or {value["rule"] for value in candidates} != set(RULES):
            raise ValueError("A linked trait requires both distinct candidate rules")
        values = [value["value"] for value in candidates]
        agreement = None if None in values else values[0] == values[1]
        statuses = {value["status"] for value in candidates}
        numeric = {value["status"] for value in candidates if value["value"] is not None}
        if "unknown_tier_table" in numeric and numeric != {"unknown_tier_table"}:
            raise ValueError("Trait candidates cannot disagree about the existence of their shared tier table")
        minimum = max([1, *[value["value"] for value in candidates if value["status"] == STATUS]])
        maximum = [value["value"] - 1 for value in candidates if value["status"] == "out_of_range" and value["value"] > 0]
        if maximum and minimum > min(maximum):
            raise ValueError("Trait candidate range statuses contradict their shared tier table")
        status = "input_conflict" if "input_conflict" in statuses else STATUS if STATUS in statuses else "no_usable_candidate"
    if row["status"] != status or row["candidatesAgree"] is not agreement:
        raise ValueError("Trait status or candidate agreement differs from its explicit inputs")
    if not candidates and (position is not None or row["candidates"]):
        raise ValueError("An unlinked or invalid trait cannot expose rank candidates")
    return {"trait_id": identifier, "index": index, "rank": None, "memory_position": position,
            "status": status, "candidates_agree": agreement, "candidates": candidates}


def project(document, source_sha256):
    """Return a detached projection of the explicitly unverified candidate document."""
    _object(document, ("format", "source", "ruleStatus", "candidateRules", "traits", "memories",
                       "memoriesWithoutSelectedTrait", "gaps", "assumptions"))
    _object(document["source"], ("sha256",))
    if (type(source_sha256) is not str or not re.fullmatch("[0-9a-f]{64}", source_sha256)
            or document["source"]["sha256"] != source_sha256):
        raise ValueError("Trait candidate source hash must match the package snapshot")
    if document["format"] != FORMAT or document["ruleStatus"] != STATUS or document["candidateRules"] != RULES:
        raise ValueError("Trait candidate format and unverified rules must match the producer contract")
    if "version" not in document:
        contract_version = "legacy"
        v011 = False
    elif document["version"] == "0.1.1":
        contract_version = "0.1.1"
        v011 = True
    elif document["version"] == "0.1.0":
        contract_version = "0.1.0"
        v011 = False
    else:
        raise ValueError("Trait candidate version must be absent, 0.1.0 or 0.1.1")
    for key in ("traits", "memories", "memoriesWithoutSelectedTrait"):
        _list(document[key])
    memories = [_memory(row, v011) for row in document["memories"]]
    for row in document["traits"]:
        _object(row, ("index",))
    indexes = [_count(row["index"], nullable=True) for row in document["traits"]]
    positions = [memory["position"] for memory in memories]
    if len(set(positions)) != len(positions):
        raise ValueError("Trait candidate memory positions must be unique")
    traits = [_trait(row, dict(zip(positions, memories)), indexes) for row in document["traits"]]
    identifiers = [row["trait_id"] for row in traits if row["trait_id"] is not None]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Trait candidate IDs must be unique")
    unclaimed = [_count(value) for value in document["memoriesWithoutSelectedTrait"]]
    if unclaimed != sorted(position + 1 for position in positions if position + 1 not in indexes):
        raise ValueError("Unclaimed memory slots differ from the exported trait indexes")
    assumptions = _texts(document["assumptions"])
    if contract_version in ("legacy", "0.1.0") and LEGACY_ASSUMPTION not in assumptions:
        assumptions.append(LEGACY_ASSUMPTION)
    return {
        "format": document["format"], "contract_version": contract_version,
        "source_sha256": document["source"]["sha256"],
        "rule_status": document["ruleStatus"],
        "traits": traits,
        "memories": memories,
        "memories_without_selected_trait": unclaimed,
        "gaps": _texts(document["gaps"]), "assumptions": assumptions}
