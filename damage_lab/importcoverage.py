"""Project importer composition evidence without claiming verified combat effects."""

import re
from datetime import datetime


DOMAINS = ("equipment", "skillLayout", "heroTraits", "talents", "slates", "pactspirits",
           "nativeStats", "panelSkillIdentity", "supportActivation")
COUNTS = {
    "equipment": ("items", "invalidRecords", "affixes", "affixesWithRolls", "affixesWithoutRolls", "invalidAffixes"),
    "skillLayout": ("groups", "mainSkills", "supports", "integerLevels", "invalidLevels", "invalidRecords", "emptySlots"),
    "heroTraits": ("selectedTraits", "memories", "invalidRecords"),
    "talents": ("trees", "nodesWithPoints", "invalidRecords"),
    "slates": ("slates", "emptySlots", "invalidRecords"),
    "pactspirits": ("pactspirits", "emptySlots", "invalidRecords"),
    "nativeStats": ("named", "unnamedStatPairs", "otherUnnamedFields"),
    "panelSkillIdentity": (), "supportActivation": ("installedSupports",)}
EXTRAS = {
    "skillLayout": ("guideSupportLevelValues",),
    "heroTraits": ("rankStatus", "baseTraitRank", "rankSource"),
    "nativeStats": ("semantics", "protocolVerified"),
    "panelSkillIdentity": ("identity",), "supportActivation": ("activation", "reason")}
LEVELS = ("resolved", "missing_level", "duplicate_level", "invalid_value", "unverified_flat_tail",
          "not_level_scaled", "absent", "unknown_status", "invalid")
PATHS = {
    "equipment": ["sections.WearItems.data[].sourceData.AffixList"],
    "skillLayout": ["sections.SkillLayout.data[tab][].SkillData._Raw_Data"],
    "heroTraits": ["sections.HeroCharacter.data.HeroCharacters", "sections.HeroCharacter.data.HeroJewels"],
    "talents": ["sections.GeniusInfos.data.entries[].value.GeniusList"],
    "slates": ["sections.ServerSource.data.featuresInfo.talentBlock.dressingTalentBlocks"],
    "pactspirits": ["sections.PetDatas.data"], "nativeStats": ["sections.ServerSource.data.attrInfo"],
    "panelSkillIdentity": ["(no snapshot path; panel-log RoleAttrMgr lines name no skill)"],
    "supportActivation": ["sections.SkillLayout.data[tab][SlotId 2-6]",
                          "sections.ServerSource.data.featuresInfo.skillLayout.slots"]}
RULES = [
    "composition=observed means at least one shape-valid record exists; it says nothing about combat effect.",
    "effective is never verified in this version: unverified = valid named records exist but their combat application is not established; unknown = no valid record or no saved source.",
    "Presence is not activation; equal numbers are not identity; trait rank candidates C and C+E stay unverified.",
    "importComplete is always false until every domain has an established effective state.",
    "The guide is hashed separately; its binding to the source snapshot is not verified."]
GAPS = {
    "equipment": ("affix-to-modifier mapping and conditional effects are not established",
                  "map affix modifier ids to engine families with catalog provenance"),
    "skillLayout": ("effective support level and gem-to-skill effects are not established",
                    "source-bound effective-level rule from catalog plus named level bonuses"),
    "heroTraits": ("rank rule C vs C+E unverified; base trait memory source unverified",
                   "first-party source linking Trait Level to the memory fields"),
    "talents": ("talent node effects are not mapped to the modifier engine", "catalog node effect mapping with provenance"),
    "slates": ("slate effects need catalog-bound decoding and area rules", "catalog-bound slate effect decoding"),
    "pactspirits": ("pactspirit effects and slot roles are not mapped", "catalog-bound pactspirit effect mapping"),
    "nativeStats": ("only corroborated named fields; unnamed stat ids are unmapped",
                    "first-party schema naming the unnamed attrInfo ids"),
    "panelSkillIdentity": ("no saved source names the skill shown by the panel", "a logged line that names the displayed skill"),
    "supportActivation": ("installed supports have no varying enabled/disabled field",
                          "a varying named activation field or its first-party definition")}


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Import coverage requires all named contract fields")


def _hash(value):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Import coverage requires lowercase SHA-256 hashes")


def _source(row):
    status = row["capturedAtStatus"]
    stamp = row["capturedAt"]
    if status not in ("valid", "invalid", "absent"):
        raise ValueError("Import coverage timestamp status must be known")
    if status == "valid":
        if type(stamp) is not str or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{6})?[+-]\d\d:\d\d", stamp):
            raise ValueError("Import coverage timestamp must be a normalized zoned ISO date")
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError:
            raise ValueError("Import coverage timestamp must be a valid ISO date") from None
        if parsed.isoformat() != stamp:
            raise ValueError("Import coverage timestamp must retain its normalized form")
    elif stamp is not None:
        raise ValueError("Unknown import coverage timestamps must be null")
    return {"sha256": row["sha256"], "captured_at": stamp, "captured_at_status": status}


def _counts(value, keys):
    _object(value, ())
    if not any(key in value for key in keys):
        return {}
    _object(value, keys)
    if any(type(value[key]) is not int or value[key] < 0 for key in keys):
        raise ValueError("Import coverage counts must be nonnegative integers")
    return {_name(key): value[key] for key in keys}


def _domain(name, row):
    _object(row, ("composition", "effective", "paths", "counts"))
    if type(row["paths"]) is not list or row["paths"] != PATHS[name]:
        raise ValueError("Import coverage paths must match the fixed domain contract")
    composition = row["composition"]
    if type(composition) is not str or composition not in ("observed", "empty", "absent", "invalid"):
        raise ValueError("Import coverage has an unknown composition status")
    effective = "unverified" if composition == "observed" and name not in ("heroTraits", "supportActivation") else "unknown"
    if row["effective"] != effective:
        raise ValueError("Import coverage effective status contradicts its domain and composition")
    counts = _counts(row["counts"], COUNTS[name])
    if ((composition in ("observed", "empty") and name != "panelSkillIdentity" and not counts)
            or (composition == "absent" and counts)
            or (name == "panelSkillIdentity" and (composition != "absent" or counts))
            or (name == "nativeStats" and (composition == "empty" or (composition != "observed" and counts)))
            or (name == "supportActivation" and composition == "invalid" and counts)):
        raise ValueError("Import coverage counts contradict its composition status")
    if counts and name != "nativeStats":
        primary = counts[_name(COUNTS[name][0])]
        if (primary > 0) != (composition == "observed") or (composition == "empty" and counts.get("invalid_records", 0)):
            raise ValueError("Import coverage record count contradicts its composition status")
    return {"composition": composition, "effective": effective, "paths": list(row["paths"]), "counts": counts}


def _extras(name, row, result, supplied):
    _object(row, tuple(key for key in EXTRAS.get(name, ()) if key != "protocolVerified"))
    fixed = {}
    if name == "heroTraits":
        counts = result["counts"]
        fixed = {"rankStatus": "rank_rule_unverified" if counts.get("selected_traits") and counts.get("memories") else "unknown",
                 "baseTraitRank": "no_verified_source", "rankSource": "trait_ranks.candidates (trait-ranks.json)"}
    elif name == "nativeStats":
        fixed = {"semantics": "named_fields_corroborated_only; unnamed_ids_unmapped"
                 if result["composition"] == "observed" else "unreadable"}
        if result["composition"] == "observed":
            if row.get("protocolVerified") is not False:
                raise ValueError("Import coverage native protocol must remain unverified")
            result["protocol_verified"] = False
        elif "protocolVerified" in row:
            raise ValueError("Unreadable native coverage cannot claim protocol evidence")
    elif name == "panelSkillIdentity":
        fixed = {"identity": "chosen_skill_unverified"}
    elif name == "supportActivation":
        fixed = {"activation": "unknown", "reason": "client layout flags never vary; no disabled state observed"}
    if any(row[key] != value for key, value in fixed.items()):
        raise ValueError("Import coverage metadata must retain the fixed unverified contract")
    result.update({_name(key): value for key, value in fixed.items()})
    if name == "skillLayout":
        value = row["guideSupportLevelValues"]
        if supplied:
            _object(value, LEVELS)
            result["guide_support_level_values"] = _counts(value, LEVELS)
        elif value is not None:
            raise ValueError("Import coverage guide counts require a supplied guide")
        else:
            result["guide_support_level_values"] = None


def _relations(domains):
    equipment = domains["equipment"]["counts"]
    if equipment and equipment["affixes"] != equipment["affixes_with_rolls"] + equipment["affixes_without_rolls"]:
        raise ValueError("Import coverage affix counts must reconcile")
    layout = domains["skill_layout"]
    counts = layout["counts"]
    activation = domains["support_activation"]
    composition = layout["composition"]
    if counts:
        rows = counts["main_skills"] + counts["supports"]
        if (rows != counts["integer_levels"] + counts["invalid_levels"] or counts["groups"] > rows
                or bool(rows) != bool(counts["groups"])):
            raise ValueError("Import coverage skill counts must reconcile")
        if composition == "observed" and not counts["supports"]:
            composition = "empty"
    if (activation["composition"] != composition
            or activation["counts"] != ({"installed_supports": counts.get("supports", 0)}
                                         if composition in ("observed", "empty") else {})):
        raise ValueError("Import coverage installed support counts must agree with the skill layout")


def _gaps(rows, domains):
    if type(rows) is not list or len(rows) != len(DOMAINS):
        raise ValueError("Import coverage requires one gap for each of its nine domains")
    result = {}
    for row in rows:
        _object(row, ("domain", "composition", "gap", "next"))
        name = row["domain"]
        if type(name) is not str or name not in DOMAINS or name in result:
            raise ValueError("Import coverage gaps must name distinct known domains")
        if ((row["gap"], row["next"]) != GAPS[name]
                or row["composition"] != domains[_name(name)]["composition"]):
            raise ValueError("Import coverage gap text and status must match its domain contract")
        result[name] = {"domain": _name(name), "composition": row["composition"], "gap": row["gap"], "next": row["next"]}
    return [result[name] for name in DOMAINS]


def project(document, source_sha256, guide_sha256):
    """Return detached, named composition evidence for a source-bound audit."""
    _object(document, ("format", "version", "tool", "source", "guide", "importComplete", "domains", "gaps", "rules"))
    _object(document["source"], ("sha256", "capturedAt", "capturedAtStatus"))
    _object(document["guide"], ("supplied", "sha256", "binding"))
    if (document["format"] != "tli-import-coverage-v1" or document["version"] != "0.2.0"
            or document["tool"] != "tli-build-exporter/import_coverage" or document["importComplete"] is not False):
        raise ValueError("Import coverage requires the supported producer contract and incomplete status")
    if type(document["rules"]) is not list or document["rules"] != RULES:
        raise ValueError("Import coverage rules must match its fixed unverified contract")
    _hash(source_sha256)
    if document["source"]["sha256"] != source_sha256:
        raise ValueError("Import coverage source hash must match the package snapshot")
    supplied = guide_sha256 is not None
    if supplied:
        _hash(guide_sha256)
    if (document["guide"]["supplied"] is not supplied or document["guide"]["sha256"] != guide_sha256
            or document["guide"]["binding"] != ("unverified" if supplied else "not_supplied")):
        raise ValueError("Import coverage guide hash and supplied status must match its declared input")
    _object(document["domains"], DOMAINS)
    domains = {}
    for name in DOMAINS:
        row = document["domains"][name]
        domains[_name(name)] = _domain(name, row)
        _extras(name, row, domains[_name(name)], supplied)
    _relations(domains)
    return {"format": document["format"], "version": document["version"], "tool": document["tool"],
            "source": _source(document["source"]),
            "guide": {key: document["guide"][key] for key in ("supplied", "sha256", "binding")},
            "import_complete": False, "domains": domains,
            "gaps": _gaps(document["gaps"], domains), "rules": list(document["rules"])}


def summary(data):
    """Revalidate an already bound projection through the same producer contract."""
    _object(data, ("format", "version", "tool", "source", "guide", "import_complete", "domains", "gaps", "rules"))
    _object(data["source"], ("sha256", "captured_at", "captured_at_status"))
    _object(data["guide"], ("supplied", "sha256", "binding"))
    _object(data["domains"], tuple(_name(name) for name in DOMAINS))
    domains = {}
    for name in DOMAINS:
        row = data["domains"][_name(name)]
        _object(row, ("composition", "effective", "paths", "counts"))
        _object(row["counts"], ())
        domains[name] = {key: row[key] for key in ("composition", "effective", "paths")}
        domains[name]["counts"] = {key: row["counts"][_name(key)] for key in COUNTS[name] if _name(key) in row["counts"]}
        domains[name].update({key: row[_name(key)] for key in EXTRAS.get(name, ()) if _name(key) in row})
    if type(data["gaps"]) is not list:
        raise ValueError("Import coverage gaps must be a JSON list")
    gaps = []
    names = {_name(name): name for name in DOMAINS}
    for row in data["gaps"]:
        _object(row, ("domain", "composition", "gap", "next"))
        if type(row["domain"]) is not str or row["domain"] not in names:
            raise ValueError("Import coverage gaps must name known projected domains")
        gaps.append({"domain": names[row["domain"]], **{key: row[key] for key in ("composition", "gap", "next")}})
    document = {key: data[key] for key in ("format", "version", "tool", "guide", "rules")}
    document.update(source={"sha256": data["source"]["sha256"], "capturedAt": data["source"]["captured_at"],
                            "capturedAtStatus": data["source"]["captured_at_status"]},
                    importComplete=data["import_complete"], domains=domains, gaps=gaps)
    return project(document, data["source"]["sha256"], data["guide"]["sha256"])
