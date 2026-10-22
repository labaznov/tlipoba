"""Assemble source-bound candidate inputs without filling unknown character damage parameters."""

import copy
import json
import re

from .importer import snapshot
from .ledgerinputs import inputs


FORMAT = "tli-build-input-report-v1"
GAPS = ("effective_level_unknown", "current_patch_unverified", "base_damage_unverified",
        "main_attributes_unresolved", "critical_pools_unresolved", "cast_pools_unresolved",
        "conversion_unverified", "support_activation_unverified", "combat_context_unresolved")
ASSUMPTIONS = (
    "Selection names an observed gem alias and does not verify the panel skill",
    "Catalog values belong to the observed gem level and not the effective level",
    "Projected modifier rows are candidates and not complete character pools",
    "Group co-membership does not confirm enabled support effects",
    "No panel value or benchmark fills missing raw damage inputs",
)


def _binding(record, selected, profiles, gaps):
    inventory = record.get("installed_skills")
    if inventory is None or inventory["domains"]["client"]["status"] != "captured":
        gaps.append("skill_inventory_unavailable")
        return False
    expected = {}
    for group in inventory["groups"]:
        if group["alias"] != selected["group"]:
            continue
        for member in group["members"]:
            expected[member["alias"]] = {key: member[key] for key in
                ("slot", "path", "skill_id", "gem_level")}
            expected[member["alias"]].update(group=group["alias"], tab_position=group["tab_position"])
    observed = {row["alias"]: {key: row[key] for key in
        ("group", "tab_position", "slot", "path", "skill_id", "gem_level")}
        for row in profiles["members"] if row["group"] == selected["group"]}
    if expected != observed:
        raise ValueError("Installed profile group contradicts the source-bound skill inventory")
    return True


def _installation(record, selected, profiles, gaps):
    result = {"status": "unavailable", "members": None}
    inventory = record.get("installed_support_effects")
    if inventory is None or inventory["members"] is None:
        gaps.append("support_inventory_unavailable")
        return result
    if selected is None:
        return result
    members = [row for row in inventory["members"] if row["group"] == selected["group"]]
    expected = {row["alias"]: row for row in profiles["members"] if row["group"] == selected["group"]}
    conflict = {row["alias"] for row in members} != set(expected)
    for row in members:
        observed = expected.get(row["alias"])
        if observed is None:
            continue
        conflict |= any(row[field] != observed[field] for field in ("group", "tab_position", "slot", "path"))
        conflict |= (row["base_id"] is not None and observed["skill_id"] is not None
                     and row["base_id"] != observed["skill_id"])
        conflict |= (row["gem_level"]["value"] is not None and observed["gem_level"] is not None
                     and row["gem_level"]["value"] != observed["gem_level"])
    if conflict:
        gaps.append("installation_context_conflict")
        return result
    return {"status": "observed_group_only", "members": copy.deepcopy(members)}


def assemble(record, *, skill_alias):
    """Select a gem and project applicable observed rows, leaving complete raw spell inputs unavailable."""
    if type(skill_alias) is not str or re.fullmatch(r"gem\[[1-9][0-9]{0,8}\]", skill_alias, re.ASCII) is None:
        raise ValueError("Build inputs require an explicit positive gem alias")
    canonical = snapshot(record)
    source = canonical.get("source_sha256")
    if type(source) is not str or re.fullmatch(r"[0-9a-f]{64}", source, re.ASCII) is None:
        raise ValueError("Build inputs require a source-bound imported record")
    json.dumps(canonical, allow_nan=False)
    gaps = list(GAPS)
    selected = None
    profiles = canonical.get("installed_skill_profiles")
    status = "unavailable"
    if profiles is None:
        gaps.append("profile_catalog_unavailable")
    elif profiles["members"] is None:
        gaps.append("skill_layer_unavailable")
    else:
        selected = next((row for row in profiles["members"] if row["alias"] == skill_alias), None)
        status = "not_observed" if selected is None else "observed"
        if selected is None:
            gaps.append("skill_not_observed")
        elif selected["profile"] is None:
            gaps.append("skill_profile_gap")
    if selected is not None and not _binding(canonical, selected, profiles, gaps):
        selected, status = None, "unavailable"
    modifiers = None
    ledger = canonical.get("static_combat")
    if ledger is None:
        gaps.append("static_ledger_unavailable")
    if selected is not None and selected["profile"] is not None:
        tags = selected["profile"]["tags"]
        if tags["status"] != "supplied" or not tags["skill"]:
            gaps.append("skill_tags_unavailable")
        elif ledger is not None:
            modifiers = inputs(ledger, skill_tags=tags["skill"])
            gaps.extend("modifiers:" + row["kind"] for row in modifiers["gaps"])
    installation = _installation(canonical, selected, profiles, gaps)
    return {"format": FORMAT, "status": "blocked", "arithmetic_ready": False, "runtime_verified": False,
            "identity_verified": False, "import_complete": False, "source_sha256": source,
            "selection": {"alias": skill_alias, "basis": "explicit_alias", "status": status},
            "skill": copy.deepcopy(selected), "modifiers": modifiers, "installation": installation,
            "gaps": list(dict.fromkeys(gaps)), "raw_spell": None, "record": canonical,
            "assumptions": list(ASSUMPTIONS)}
