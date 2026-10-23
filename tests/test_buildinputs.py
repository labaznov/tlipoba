import copy
import json
import unittest

from damage_lab.buildinputs import assemble


def record():
    """Create a fictional source-bound record with skill, gear and co-member evidence."""
    from damage_lab.installedprofiles import project
    from damage_lab.staticcombat import project as static
    from test_importer import supported
    from test_installedprofiles import records, installation, catalog
    from test_staticcombat import document

    data = supported()
    observed = installation()
    data["installed_skills"] = observed
    definitions = records()
    definitions["90017"]["tags"] = ["Physical" if tag == "Cold" else tag for tag in definitions["90017"]["tags"]]
    definitions["90017"]["english"] = {key: value.replace("Cold", "Physical")
                                         for key, value in definitions["90017"]["english"].items()}
    data["installed_skill_profiles"] = project(definitions, observed, catalog())
    data["static_combat"] = static(document(), data["source_sha256"])
    support = data["installed_support_effects"]
    effect = copy.deepcopy(support["members"][1]["effects"])
    effect["identity"].update(catalog_tlidb_id=90029, native_base_id=90029)
    support["members"] = []
    for group in observed["groups"]:
        for gem in group["members"]:
            eligible = gem["alias"] == "gem[2]"
            support["members"].append({"alias": gem["alias"], "group": group["alias"],
                "tab_position": group["tab_position"], "group_status": group["status"], "slot": gem["slot"],
                "path": gem["path"], "base_id": gem["skill_id"],
                "gem_level": {"value": gem["gem_level"], "meaning": "observed_gem_level_not_effective"},
                "category": "noble_support" if eligible else "active_skill", "status": "effect_candidates"
                if eligible else "excluded_category", "reason": None, "effects": effect if eligible else None})
    support["accounting"] = {"members": 4, "effect_candidates": 1, "excluded": 3, "gaps": 0, "reconciles": True}
    support["server_layer"] = "captured"
    return data


def mediumrecord():
    """Connect a fictional medium to its observed co-member and declared catalog slices."""
    import tempfile
    from pathlib import Path
    from damage_lab.installedprofiles import project
    from damage_lab.supportbundle import read
    from test_supportbundle import medium
    from test_installedprofiles import records, catalog

    data = record()
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        _, descriptor, source = medium(directory)
        inventory, metadata, _ = read(directory, descriptor, source)
    data["installed_support_catalog"] = metadata
    support = data["installed_support_effects"]
    support["effects_version"] = "0.3.0"
    candidate = support["members"][1]
    candidate.update(base_id=8030, category="activation_medium", effects=inventory["members"][1]["effects"])
    observed = data["installed_skills"]
    observed["groups"][0]["members"][1]["skill_id"] = 8030
    definitions = records()
    definitions["90017"]["tags"] = ["Physical" if tag == "Cold" else tag for tag in definitions["90017"]["tags"]]
    definitions["90017"]["english"] = {key: value.replace("Cold", "Physical")
                                         for key, value in definitions["90017"]["english"].items()}
    data["installed_skill_profiles"] = project(definitions, observed, catalog())
    return data


class BuildInputsTests(unittest.TestCase):
    """Connect automatic observations without fabricating complete raw damage inputs."""

    def test_medium_creation_metadata_does_not_fill_any_damage_pool(self):
        baseline = assemble(record(), skill_alias="gem[1]")
        result = assemble(mediumrecord(), skill_alias="gem[1]")
        self.assertEqual((result["raw_spell"], result["raw_result"], result["gaps"],
                          result["installation"]["members"][1]["effects"]["medium_trigger"]["line"]["slots"][1]["exact"]),
                         (baseline["raw_spell"], baseline["raw_result"], baseline["gaps"], "0.4"))

    def test_observed_spell_burst_count_cannot_resolve_missing_raw_inputs(self):
        baseline = assemble(record(), skill_alias="gem[1]")
        for count in (0, 3):
            data = record()
            data["stats"]["max_spell_burst"] = count
            report = assemble(data, skill_alias="gem[1]")
            with self.subTest(count=count):
                self.assertEqual((report["record"]["stats"].get("max_spell_burst"),
                                  report["raw_spell"], report["raw_result"], report["status"],
                                  report["arithmetic_ready"], report["runtime_verified"]),
                                 (count, baseline["raw_spell"], baseline["raw_result"], "blocked", False, False))

    def test_the_observed_spell_context_reaches_the_real_evaluator_with_unavailable_groups(self):
        from damage_lab.rawspell import evaluate

        report = assemble(record(), skill_alias="gem[1]")
        self.assertEqual((report["raw_spell"]["format"], report["raw_result"]),
                         ("tli-raw-cold-spell-v1", evaluate(report["raw_spell"])))

    def test_an_invalid_catalog_guid_does_not_create_a_guessed_raw_spell_identity(self):
        data = record()
        data["installed_skill_profiles"]["members"][0]["profile"]["identity"].update(guid=None, guidStatus="absent")
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["raw_spell"], report["raw_result"], "raw_spell_context_unavailable" in report["gaps"]),
                         (None, None, True))

    def test_an_explicit_gem_selects_its_profile_and_scoped_modifier_candidates_without_dps(self):
        report = assemble(record(), skill_alias="gem[1]")
        self.assertEqual((report["format"], report["selection"], report["skill"]["skill_id"],
                          report["skill"]["effective_level"], len(report["modifiers"]["added"]),
                          report["modifiers"]["skill"]["inferred"], report["raw_result"]["status"], report["arithmetic_ready"]),
                         ("tli-build-input-report-v1", {"alias": "gem[1]", "basis": "explicit_alias", "status": "observed"},
                          90017, None, 1, False, "blocked", False))

    def test_group_members_remain_observed_installation_instead_of_enabled_effects(self):
        report = assemble(record(), skill_alias="gem[1]")
        self.assertEqual((report["installation"]["status"], [row["alias"] for row in report["installation"]["members"]],
                          report["installation"]["members"][1]["effects"]["arithmetic_ready"]),
                         ("observed_group_only", ["gem[1]", "gem[2]"], False))

    def test_known_lookup_fields_never_fill_effective_level_critical_or_cast_pools(self):
        report = assemble(record(), skill_alias="gem[1]")
        self.assertTrue(report["status"] == "blocked" and all(report["raw_spell"][field] is None for field in ("damage", "critical", "casting"))
                        and {"effective_level_unknown", "current_patch_unverified", "base_damage_unverified",
                             "main_attributes_unresolved", "critical_pools_unresolved", "cast_pools_unresolved",
                             "conversion_unverified", "support_activation_unverified", "combat_context_unresolved"}
                        .issubset(report["gaps"]))

    def test_raw_context_uses_the_exact_selected_master_member_hash_and_catalog_guid(self):
        data = record()
        documents = data["installed_skill_profiles"]["catalog"]["documents"]
        documents[0]["member_sha256"] = "7" * 64
        documents.reverse()
        report = assemble(data, skill_alias="gem[1]")
        context = report["raw_spell"]["context"]
        self.assertEqual((context["source_sha256"], context["catalog_sha256"], context["skill_id"], context["effective_level"],
                          {name: gate["status"] for name, gate in context["gates"].items()}),
                         (data["source_sha256"], "7" * 64, "synthetic-guid", None,
                          {name: "unknown" for name in ("version", "level", "base", "conversion")}))

    def test_raw_missing_excludes_combat_context_and_gate_duplicates_but_keeps_source_pool_gaps(self):
        report = assemble(record(), skill_alias="gem[1]")
        missing = report["raw_spell"]["missing"]
        self.assertTrue({"main_attributes_unresolved", "critical_pools_unresolved", "cast_pools_unresolved",
                         "support_activation_unverified", "modifiers:omitted_rows"}.issubset(missing)
                        and not {"effective_level_unknown", "current_patch_unverified", "base_damage_unverified",
                                 "conversion_unverified", "combat_context_unresolved"}.intersection(missing)
                        and report["raw_result"]["pre_defence_dps"] is None and report["raw_result"]["trace"] == [])

    def test_unsupported_or_unbound_hit_paths_do_not_create_a_raw_model(self):
        for change in ("cold", "missing_hit", "not_spell", "invalid_tags"):
            with self.subTest(change=change):
                data = record()
                profile = data["installed_skill_profiles"]["members"][0]["profile"]
                if change == "cold":
                    profile["hit"]["type"] = "cold"
                elif change == "missing_hit":
                    profile["hit"] = {"status": "level_not_in_table"}
                elif change == "not_spell":
                    profile["tags"]["skill"].remove("spell")
                else:
                    profile["tags"] = {"status": "invalid", "skill": None, "damageTypes": None, "reserved": None}
                report = assemble(data, skill_alias="gem[1]")
                self.assertEqual((report["raw_spell"], report["raw_result"], "raw_spell_path_unsupported" in report["gaps"]),
                                 (None, None, True))

    def test_missing_profile_alias_and_valid_guid_gaps_never_borrow_another_context(self):
        for change in ("profile", "alias", "guid"):
            with self.subTest(change=change):
                data = record()
                if change == "profile":
                    data.pop("installed_skill_profiles")
                elif change == "guid":
                    data["installed_skill_profiles"]["members"][0]["profile"]["identity"].update(guid=None, guidStatus="invalid")
                report = assemble(data, skill_alias="gem[999]" if change == "alias" else "gem[1]")
                self.assertEqual((report["raw_spell"], report["raw_result"], "raw_spell_context_unavailable" in report["gaps"]),
                                 (None, None, True))

    def test_raw_document_and_evaluator_scenarios_are_independently_detached(self):
        data = record()
        original = copy.deepcopy(data)
        report = assemble(data, skill_alias="gem[1]")
        report["raw_spell"]["context"]["gates"]["level"]["evidence"].append("changed")
        report["raw_result"]["scenario"]["notes"].append("changed")
        self.assertEqual((data, "changed" in report["raw_result"]["scenario"]["context"]["gates"]["level"]["evidence"]),
                         (original, False))

    def test_missing_profile_evidence_is_an_unavailable_selection_without_inferred_tags(self):
        data = record()
        data.pop("installed_skill_profiles")
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["selection"]["status"], report["skill"], report["modifiers"],
                          "profile_catalog_unavailable" in report["gaps"]), ("unavailable", None, None, True))

    def test_an_unobserved_alias_is_not_replaced_by_the_first_or_primary_gem(self):
        report = assemble(record(), skill_alias="gem[17]")
        self.assertEqual((report["selection"]["status"], report["skill"], report["modifiers"],
                          "skill_not_observed" in report["gaps"]), ("not_observed", None, None, True))

    def test_a_missing_catalog_record_preserves_the_gem_gap_without_borrowing_another_profile(self):
        report = assemble(record(), skill_alias="gem[3]")
        self.assertEqual((report["selection"]["status"], report["skill"]["reason"], report["modifiers"],
                          "skill_profile_gap" in report["gaps"]), ("observed", "catalog_record_missing", None, True))

    def test_missing_static_or_installation_evidence_is_not_an_empty_complete_pool(self):
        data = record()
        for key in ("static_combat", "installed_support_effects", "installed_support_catalog"):
            data.pop(key)
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["modifiers"], report["installation"],
                          {"static_ledger_unavailable", "support_inventory_unavailable"}.issubset(report["gaps"])),
                         (None, {"status": "unavailable", "members": None}, True))

    def test_incompatible_group_coordinates_cannot_attribute_neighboring_support_effects(self):
        data = record()
        data["installed_support_effects"]["members"][1]["base_id"] = 90031
        data["installed_support_effects"]["members"][1]["effects"]["identity"].update(catalog_tlidb_id=90031, native_base_id=90031)
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["installation"], "installation_context_conflict" in report["gaps"]),
                         ({"status": "unavailable", "members": None}, True))

    def test_sources_and_fixed_claims_are_revalidated_before_any_projection(self):
        for field, value in (("source_sha256", "b" * 64), ("import_status", "complete")):
            with self.subTest(field=field):
                data = record()
                data[field] = value
                with self.assertRaises(ValueError):
                    assemble(data, skill_alias="gem[1]")

    def test_profiles_cannot_contradict_the_installed_group_for_the_same_source(self):
        for field, value in (("skill_id", 90037), ("gem_level", 17)):
            with self.subTest(field=field):
                data = record()
                data["installed_skills"]["groups"][0]["members"][0][field] = value
                with self.assertRaisesRegex(ValueError, "profile group contradicts"):
                    assemble(data, skill_alias="gem[1]")

    def test_missing_skill_inventory_cannot_confirm_a_profile_selection(self):
        data = record()
        data.pop("installed_skills")
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["selection"]["status"], report["skill"], report["modifiers"],
                          report["installation"]["members"], "skill_inventory_unavailable" in report["gaps"]),
                         ("unavailable", None, None, None, True))

    def test_unknown_fields_are_removed_and_all_results_are_detached(self):
        data = record()
        data["raw"] = "PRIVATE-INPUT-CANARY"
        data["installed_skill_profiles"]["members"][0]["raw"] = "PRIVATE-INPUT-CANARY"
        original = copy.deepcopy(data)
        report = assemble(data, skill_alias="gem[1]")
        report["skill"]["profile"]["tags"]["skill"].append("changed")
        self.assertEqual((data, "PRIVATE-INPUT-CANARY" in json.dumps(report),
                          "changed" in report["record"]["installed_skill_profiles"]["members"][0]["profile"]["tags"]["skill"]),
                         (original, False, False))

    def test_a_selection_requires_an_explicit_safe_positive_gem_alias(self):
        for alias in (None, True, 1, "", "gem[0]", "gem[01]", "gem[1] ", "PRIVATE-INPUT-CANARY"):
            with self.subTest(alias=alias), self.assertRaises(ValueError):
                assemble(record(), skill_alias=alias)

    def test_attack_only_flat_damage_is_excluded_from_a_spell_selection(self):
        from damage_lab.staticcombat import project
        from test_staticcombat import document

        data = record()
        raw = document()
        raw["modifiers"][0].update(scope="attack", appliesToPlayerSpell=False)
        data["static_combat"] = project(raw, data["source_sha256"])
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["modifiers"]["added"], report["modifiers"]["excluded"][0]["reason"]),
                         ([], "scope_not_skill_tag"))

    def test_an_unknown_tag_partition_does_not_fall_back_to_the_skill_name_or_other_gems(self):
        data = record()
        data["installed_skill_profiles"]["members"][0]["profile"]["tags"] = {
            "status": "invalid", "skill": None, "damageTypes": None, "reserved": None}
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["modifiers"], "skill_tags_unavailable" in report["gaps"]), (None, True))

    def test_an_unknown_client_layer_does_not_infer_an_empty_or_primary_selection(self):
        data = record()
        profiles = data["installed_skill_profiles"]
        profiles.update(client_layer="not_captured", members=None)
        profiles["accounting"] = {field: None for field in profiles["accounting"]}
        report = assemble(data, skill_alias="gem[1]")
        self.assertEqual((report["selection"]["status"], report["skill"], report["modifiers"],
                          "skill_layer_unavailable" in report["gaps"]), ("unavailable", None, None, True))

    def test_panel_or_benchmark_changes_cannot_supply_missing_raw_character_inputs(self):
        data = record()
        before = assemble(data, skill_alias="gem[1]")
        data["stats"].update(spell_dps=127831, crit_multiplier=7.31, cast_rate=11.3)
        data["benchmark"]["average_dps"] = 77131827
        after = assemble(data, skill_alias="gem[1]")
        fields = ("skill", "modifiers", "installation", "gaps", "raw_spell", "raw_result")
        self.assertEqual({field: before[field] for field in fields}, {field: after[field] for field in fields})
