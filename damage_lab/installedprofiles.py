"""Look up catalog-only skill fields at observed gem levels without resolving effective levels."""

import re

from .installedskills import summary as installation_summary
from .skillprofile import DAMAGE_TYPES, FORMAT as PROFILE_FORMAT, GUID, PERCENT, RESERVED, SECONDS, _stated, profile
from .supportcatalog import summary as catalog_summary


FORMAT = "tli-installed-skill-profiles-v1"
VERSION = "0.1.0"
PROFILE_VERSION = "0.2.1"
MEANING = "observed_gem_level_not_effective"


def _select(value, fields):
    if type(value) is not dict or not set(fields.split()).issubset(value):
        raise ValueError("Installed skill profiles require all named object fields")
    return {key: value[key] for key in fields.split()}


def _pattern(value, pattern):
    if type(value) is not str or re.fullmatch(pattern, value, re.ASCII) is None:
        raise ValueError("Installed skill profiles contain an invalid public coordinate or token")


def _integer(value, minimum, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not int or minimum is not None and value < minimum:
        raise ValueError("Installed skill profiles require typed integers within the supported range")


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError("Installed skill profiles contain an unsupported status")


def _fixed(value, expected):
    for key, target in expected.items():
        if target is False or target is None:
            if value[key] is not target:
                raise ValueError("Installed skill profiles cannot promote fixed false or unknown claims")
        else:
            _enum(value[key], (target,))


def _records(records, installation, catalog):
    if installation["domains"]["client"]["status"] != "captured":
        if records is not None:
            raise ValueError("Uncaptured installed skills require an unknown catalog record map")
        return
    if type(records) is not dict:
        raise ValueError("Captured installed skills require a catalog record map")
    if sum(record is not None for record in records.values()) > catalog["skills"]:
        raise ValueError("Installed catalog records cannot outnumber declared resolved catalog skills")
    identities = {str(row["skill_id"]) for group in installation["groups"] for row in group["members"]
                  if row["skill_id"] is not None}
    for key, record in records.items():
        if type(key) is not str or re.fullmatch(r"[1-9][0-9]*", key, re.ASCII) is None or key not in identities:
            raise ValueError("Installed catalog keys must be observed canonical positive skill IDs")
        if record is not None and (type(record) is not dict or type(record.get("tlidbId")) is not int
                                   or str(record["tlidbId"]) != key):
            raise ValueError("Installed catalog records must match their exact integer skill IDs")
        if record is None:
            continue
        category = record.get("category")
        _category(category, catalog)
        if record["tlidbId"] in catalog["withheld_record_ids"]:
            raise ValueError("Installed skill profiles cannot resolve a withheld catalog identity")
        if "catalogPath" in record and record["catalogPath"] != f"skill/{category}":
            raise ValueError("Installed catalog record paths must match their declared category")
        english = record.get("english")
        if english is not None and type(english) is not dict:
            raise ValueError("Installed catalog English entries must be objects or absent")
        if english and catalog["categories"][category]["english"] != "present":
            raise ValueError("Installed catalog English payloads require a declared English member")


def _category(value, catalog):
    if (type(value) is not str or value not in catalog["categories"]
            or catalog["categories"][value]["master"] != "present"):
        raise ValueError("Installed catalog records require their declared category master")


def project(records, installation, catalog):
    """Return detached per-gem catalog lookups at the observed level only."""
    installation = installation_summary(installation)
    catalog = catalog_summary(catalog)
    _records(records, installation, catalog)
    members = []
    for group in installation["groups"]:
        for member in group["members"]:
            row = {key: member[key] for key in ("alias", "slot", "path", "skill_id", "gem_level")}
            record = records.get(str(row["skill_id"]))
            reason = ("invalid_skill_id" if row["skill_id"] is None else "invalid_gem_level"
                      if row["gem_level"] is None else "catalog_record_missing" if record is None else None)
            result = None if reason else profile(records, row["skill_id"], row["gem_level"])
            row.update(group=group["alias"], tab_position=group["tab_position"], effective_level=None,
                       lookup_level_meaning=MEANING,
                       catalog_category=record["category"] if record is not None else None,
                       status="gap" if reason else "profiled", reason=reason, profile=result)
            members.append(row)
    captured = installation["domains"]["client"]["status"] == "captured"
    return summary({"format": FORMAT, "version": VERSION, "profile_version": PROFILE_VERSION,
            "source": dict(installation["source"]), "catalog": catalog, "arithmetic_ready": False,
            "runtime_verified": False, "identity_verified": False, "import_complete": False,
            "activation": "unknown", "patch": "unknown", "effective_level": None,
            "client_layer": installation["domains"]["client"]["status"], "members": members if captured else None,
            "accounting": {"members": len(members), "profiled": sum(row["status"] == "profiled" for row in members),
                           "gaps": sum(row["status"] == "gap" for row in members), "reconciles": True}
                           if captured else {key: None for key in ("members", "profiled", "gaps", "reconciles")}})


def summary(canonical):
    """Revalidate and detach already projected catalog lookups without source I/O."""
    result = _select(canonical, "format version profile_version source catalog arithmetic_ready runtime_verified "
                     "identity_verified import_complete activation patch effective_level client_layer members accounting")
    _fixed(result, {"format": FORMAT, "version": VERSION, "profile_version": PROFILE_VERSION,
                    "arithmetic_ready": False, "runtime_verified": False, "identity_verified": False,
                    "import_complete": False, "activation": "unknown", "patch": "unknown", "effective_level": None})
    result["source"] = _select(result["source"], "sha256 binding")
    _pattern(result["source"]["sha256"], r"[0-9a-f]{64}")
    _fixed(result["source"], {"binding": "caller_supplied"})
    result["catalog"] = catalog_summary(result["catalog"])
    _enum(result["client_layer"], ("captured", "absent", "invalid", "not_captured"))
    if result["client_layer"] == "captured":
        if type(result["members"]) is not list:
            raise ValueError("Captured installed skill profiles require a member list")
        result["members"] = [_member(row, result["catalog"]) for row in result["members"]]
        _coordinates(result["members"])
        if len({row["skill_id"] for row in result["members"] if row["status"] == "profiled"}) > result["catalog"]["skills"]:
            raise ValueError("Installed profile identities cannot outnumber declared resolved catalog skills")
        expected = {"members": len(result["members"]),
                    "profiled": sum(row["status"] == "profiled" for row in result["members"]),
                    "gaps": sum(row["status"] == "gap" for row in result["members"]), "reconciles": True}
    else:
        if result["members"] is not None:
            raise ValueError("Uncaptured installed skill profiles require unknown members")
        expected = {key: None for key in ("members", "profiled", "gaps", "reconciles")}
    result["accounting"] = _select(result["accounting"], "members profiled gaps reconciles")
    if any(type(result["accounting"][key]) is not type(value) or result["accounting"][key] != value
           for key, value in expected.items()):
        raise ValueError("Installed skill profile counts must reconcile with every member disposition")
    return result


def _member(value, catalog):
    row = _select(value, "alias group tab_position slot path skill_id gem_level effective_level lookup_level_meaning "
                  "catalog_category status reason profile")
    _fixed(row, {"effective_level": None, "lookup_level_meaning": MEANING})
    _integer(row["tab_position"], 0)
    for field in ("slot", "skill_id", "gem_level"):
        _integer(row[field], 1, True)
    if row["catalog_category"] is not None:
        _category(row["catalog_category"], catalog)
    reason = ("invalid_skill_id" if row["skill_id"] is None else "invalid_gem_level"
              if row["gem_level"] is None else "catalog_record_missing" if row["profile"] is None else None)
    _fixed(row, {"status": "gap" if reason else "profiled", "reason": reason})
    if reason:
        if row["profile"] is not None or (reason != "invalid_gem_level" and row["catalog_category"] is not None):
            raise ValueError("Installed skill profile gaps cannot contain resolved catalog values")
    else:
        _category(row["catalog_category"], catalog)
        if row["skill_id"] in catalog["withheld_record_ids"]:
            raise ValueError("Installed skill profiles cannot resolve a withheld catalog identity")
        row["profile"] = _profile(row["profile"], row["skill_id"], row["gem_level"])
        if (catalog["categories"][row["catalog_category"]]["english"] != "present"
                and row["profile"]["hit"]["status"] != "no_binding"):
            raise ValueError("Installed catalog hit profiles require their declared English member")
    return row


def _profile(value, identity, level):
    result = _select(value, "format version runtimeVerified level identity tags mainStat "
                     "effectivenessOfAddedDamage castSpeedField hit")
    _fixed(result, {"format": PROFILE_FORMAT, "version": PROFILE_VERSION, "runtimeVerified": False})
    _integer(result["level"], 1)
    if result["level"] != level:
        raise ValueError("Installed catalog profile level must equal the observed gem level")
    result["identity"] = _select(result["identity"], "status tlidbId guid guidStatus")
    _fixed(result["identity"], {"status": "exact"})
    _integer(result["identity"]["tlidbId"], 1)
    if result["identity"]["tlidbId"] != identity:
        raise ValueError("Installed catalog profile identity must equal the observed skill ID")
    _enum(result["identity"]["guidStatus"], ("ok", "absent", "invalid"))
    if result["identity"]["guidStatus"] == "ok":
        _pattern(result["identity"]["guid"], GUID.pattern)
    elif result["identity"]["guid"] is not None:
        raise ValueError("Invalid or absent catalog GUIDs must remain unknown")
    result["tags"] = _tags(result["tags"])
    result["mainStat"] = _attributes(result["mainStat"])
    result["effectivenessOfAddedDamage"] = _scalar(result["effectivenessOfAddedDamage"], PERCENT, "value", 100)
    result["castSpeedField"] = _scalar(result["castSpeedField"], SECONDS, "seconds", 1)
    result["hit"] = _hit(result["hit"], level)
    return result


def _scalar(value, pattern, key, scale):
    result = _select(value, f"status text {key}")
    _enum(result["status"], ("stated", "not_stated", "invalid"))
    if result["status"] == "stated":
        _pattern(result["text"], pattern.pattern)
        if result != _stated(result["text"], pattern, key, scale):
            raise ValueError("Installed catalog numeric fields must preserve their exact stated units and value")
    elif (result[key] is not None or (result["text"] is not None
                                     and not (result["status"] == "not_stated" and result["text"] == ""))):
        raise ValueError("Unresolved catalog numeric fields cannot contain inferred values")
    return result


def _hit(value, level):
    result = _select(value, "status")
    _enum(result["status"], ("no_binding", "multiple_damage_lines", "no_spell_hit_line", "binding_count_mismatch",
                             "binding_not_range", "render_mismatch", "invalid_range", "level_not_in_table",
                             "non_integer_value", "catalog_render_consistent"))
    if result["status"] != "catalog_render_consistent":
        return result
    result = _select(value, "status type min max level binding checkedAtLevel")
    _enum(result["type"], DAMAGE_TYPES)
    for field in ("min", "max"):
        _pattern(result[field], r"0|[1-9][0-9]*")
    try:
        ordered = int(result["min"]) <= int(result["max"])
    except ValueError:
        raise ValueError("Installed catalog hit ranges exceed the integer limit") from None
    _integer(result["level"], 1)
    _integer(result["checkedAtLevel"], None)
    if not ordered or result["level"] != level:
        raise ValueError("Installed catalog hit ranges must be ordered at the observed gem level")
    result["binding"] = _select(result["binding"], "min max")
    _pattern(result["binding"]["min"], r"value[0-9]{1,2}Min")
    if result["binding"]["max"] != result["binding"]["min"][:-3] + "Max":
        raise ValueError("Installed catalog hit bindings require a matching minimum and maximum pair")
    return result


def _tags(value):
    result = _select(value, "status skill damageTypes reserved")
    _enum(result["status"], ("supplied", "absent", "invalid"))
    for field in ("skill", "damageTypes", "reserved"):
        values = result[field]
        if result["status"] != "supplied":
            if values is not None:
                raise ValueError("Unresolved catalog tags require unknown partitions")
            continue
        if type(values) is not list:
            raise ValueError("Supplied catalog tag partitions require lists")
        for value in values:
            _pattern(value, r"[a-z]+(?:_[a-z]+)*")
            if ((field == "skill" and value in DAMAGE_TYPES + RESERVED)
                    or (field == "damageTypes" and value not in DAMAGE_TYPES)
                    or (field == "reserved" and value not in RESERVED)):
                raise ValueError("Catalog damage types and path scopes cannot become skill tags")
        if values != sorted(set(values)):
            raise ValueError("Catalog tag partitions must remain sorted and distinct")
        result[field] = list(values)
    return result


def _attributes(value):
    result = _select(value, "status attributes")
    _enum(result["status"], ("supplied", "absent", "invalid"))
    if result["status"] != "supplied":
        if result["attributes"] is not None:
            raise ValueError("Unresolved catalog main attributes must remain unknown")
    else:
        if type(result["attributes"]) is not list:
            raise ValueError("Supplied catalog main attributes require a list")
        for value in result["attributes"]:
            _enum(value, ("strength", "dexterity", "intelligence"))
        if len(result["attributes"]) != len(set(result["attributes"])):
            raise ValueError("Catalog main attributes must remain distinct")
        result["attributes"] = list(result["attributes"])
    return result


def _coordinates(members):
    group, tab, offset = 0, -1, -1
    for index, row in enumerate(members, 1):
        _pattern(row["path"], r"sections\.SkillLayout\.data\[(0|[1-9][0-9]*)\]\[(0|[1-9][0-9]*)\]")
        try:
            position, value = map(int, re.findall(r"\[([0-9]+)\]", row["path"]))
        except ValueError:
            raise ValueError("Installed skill profile coordinates exceed the integer limit") from None
        if row["tab_position"] != tab:
            if row["tab_position"] <= tab:
                raise ValueError("Installed skill profile groups must preserve source order")
            group, tab, offset = group + 1, row["tab_position"], -1
        if (row["alias"] != f"gem[{index}]" or row["group"] != f"group[{group}]"
                or position != tab or value <= offset):
            raise ValueError("Installed skill profile aliases and paths must preserve distinct source coordinates")
        offset = value
