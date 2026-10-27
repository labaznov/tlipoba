"""Preserve candidate modifier inputs without calculating effective character values."""

import re

from .staticcombat import summary


FORMAT = "tli-ledger-inputs-v1"
RESERVED = ("physical", "cold", "fire", "lightning", "erosion", "elemental", "damage", "all")
MAPPED = ("flat_added_damage", "increased_damage", "flat_attribute", "increased_attribute", "increased_speed")


def _tags(tags):
    if type(tags) is not list or not 1 <= len(tags) <= 32:
        raise ValueError("Ledger inputs require one to 32 explicit skill tags")
    if any(type(tag) is not str or not re.fullmatch(r"[a-z][a-z_]{0,31}", tag, re.ASCII)
           or tag in RESERVED for tag in tags) or len(set(tags)) != len(tags):
        raise ValueError("Ledger skill tags require distinct lowercase words without damage types or scopes")
    return sorted(tags)


def _gaps(ledger, excluded):
    gaps = [{"kind": kind} for kind in ("runtime_unverified", "selection_unverified", "source_patch_unknown",
                                        "activation_unverified")]
    for field, kind in (("omitted", "omitted_rows"), ("structural_gaps", "structural_gaps")):
        if ledger["accounting"][field]:
            gaps.append({"kind": kind, "count": ledger["accounting"][field]})
    if ledger["catalog"]["flags"]:
        gaps.append({"kind": "catalog_flags", "flags": list(ledger["catalog"]["flags"])})
    if ledger["source"]["section"] != "captured":
        gaps.append({"kind": "source_section_not_captured", "section": ledger["source"]["section"]})
    for row in ledger["modifiers"]:
        if row["pool"]["status"] == "unresolved":
            gaps.append({"kind": "unresolved_pool", "path": row["path"]})
    count = sum(row["reason"] == "family_not_mapped" for row in excluded)
    if count:
        gaps.append({"kind": "family_not_mapped", "count": count})
    return gaps


def inputs(ledger, *, skill_tags):
    """Revalidate a canonical ledger before projecting candidate input rows."""
    data = summary(ledger)
    tags = _tags(skill_tags)
    added = []
    increased = []
    attributes = []
    speed = []
    excluded = []
    for row in data["modifiers"]:
        for value in row["values"]:
            value["source_path"] = row["path"] + "." + value["source"]
        if row["owner"] != "player":
            row["reason"] = "owner_not_player"
            excluded.append(row)
            continue
        if row["family"] not in MAPPED:
            row["reason"] = "family_not_mapped"
            excluded.append(row)
            continue
        if row["scope"] != "any" and row["scope"] not in tags:
            row["reason"] = "scope_not_skill_tag"
            excluded.append(row)
            continue
        if row["family"] == "flat_added_damage":
            row["type"] = row["targets"][0]
            added.append(row)
        elif row["family"] == "increased_damage":
            row["damage_scope"] = row["scope"]
            if row["scope"] == "any":
                row["damage_scope"] = "all" if row["targets"] == ["damage"] else row["targets"][0]
            increased.append(row)
        elif row["family"] in ("flat_attribute", "increased_attribute"):
            row["attribute"] = row["targets"][0]
            attributes.append(row)
        elif row["family"] == "increased_speed":
            speed.append(row)
    return {
        "format": FORMAT, "status": "inventory_unverified", "arithmetic_ready": False,
        "runtime_verified": False, "identity_verified": False, "import_complete": False,
        "skill": {"tags": tags, "inferred": False},
        "ledger": {key: data[key] for key in ("format", "version", "source", "catalog", "runtime", "accounting",
                                               "omitted", "structural_gaps")},
        "added": added, "increased": increased, "attributes": attributes, "speed": speed,
        "excluded": excluded, "gaps": _gaps(data, excluded)}
