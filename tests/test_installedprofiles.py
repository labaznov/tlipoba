import copy
import json
import unittest
from decimal import Decimal

from damage_lab.installedprofiles import project
from damage_lab.installedskills import project as installation_project
from damage_lab.supportcatalog import project as catalog_project
from test_installedskills import document as installation_document
from test_skillprofile import catalog as skill_catalog
from test_supportcatalog import document as catalog_document


def records():
    """One synthetic exact master record with its supplied English entry."""
    return {key: {**value, "category": "Active", "catalogPath": "skill/Active"}
            for key, value in skill_catalog().items()}


def installation():
    """Canonical fictional observed gems, without an effective level."""
    return installation_project(installation_document(), "a" * 64)


def catalog():
    """Canonical declared local master and English byte coordinates."""
    return catalog_project(catalog_document())


def ordinary(*, raw_catalog=False):
    """Bind fictional support values to a public skill definition and synthetic installation."""
    template = ("Supports skills that hit enemies.\n"
                "+#% additional damage for the supported skill when it lands a Critical Strike")
    data = {"7420": {"tlidbId": 7420, "id": "synthetic-critical-support", "category": "Support",
        "catalogPath": "skill/Support", "tags": ["Support"],
        "descriptionBindings": {"template": "templateDescription", "level": 1, "bindings": ["value7"]},
        "levelProgression": [{"level": 1, "value7": Decimal("13.5")}, {"level": 7, "value7": Decimal("9.25")}],
        "english": {"templateDescription": template, "description": template.replace("#", "13.5")}}}
    observed = installation()
    observed["groups"][0]["members"][0]["skill_id"] = 7420
    metadata = catalog_document()
    metadata["categories"]["Support"] = {"master": "present", "english": "present"}
    for role, span in (("master", [401, 491]), ("english", [501, 609])):
        row = copy.deepcopy(metadata["documents"][0])
        path = "skill/Support/" + ("master" if role == "master" else "i18n/en")
        row.update(role=role, category="Support", logicalPath=path, address="/data/SS14/" + path + ".json",
                   member=path, byteRange=span)
        metadata["documents"].append(row)
    return data, observed, metadata if raw_catalog else catalog_project(metadata)


class InstalledProfileTests(unittest.TestCase):
    """Keep catalog lookups at observed gem levels separate from effective skill values."""

    def test_an_ordinary_critical_support_retains_its_separate_catalog_hit_candidate(self):
        data, observed, metadata = ordinary()
        member = project(data, observed, metadata)["members"][0]
        effect = member["ordinary_support"]
        self.assertEqual((effect["status"], effect["identity"]["catalog_id"], effect["lookup"]["level"],
                          effect["candidate"]["kind"], effect["candidate"]["value"]["fraction"],
                          effect["effective_level"], effect["arithmetic_ready"]),
                         ("candidate", 7420, 7, "critical_hit_additional_damage",
                          {"numerator": 37, "denominator": 400}, None, False))

    def test_legacy_profiles_do_not_invent_or_accept_new_ordinary_support_observations(self):
        from damage_lab.installedprofiles import summary

        data = project(records(), installation(), catalog())
        data["version"] = "0.1.0"
        for member in data["members"]:
            member.pop("ordinary_support")
        self.assertEqual(summary(data), data)

    def test_ordinary_support_context_cannot_drift_from_its_installed_catalog_member(self):
        from damage_lab.installedprofiles import summary

        for field, value in (("catalog_id", 7421), ("guid", "different-public-support"), ("level", 11)):
            with self.subTest(field=field):
                data = project(*ordinary())
                leaf = data["members"][0]["ordinary_support"]
                leaf["lookup" if field == "level" else "identity"][field] = value
                with self.assertRaises(ValueError):
                    summary(data)

    def test_new_profiles_require_the_ordinary_observation_field_even_when_it_is_unknown(self):
        from damage_lab.installedprofiles import summary

        data = project(records(), installation(), catalog())
        data["members"][0].pop("ordinary_support")
        with self.assertRaises(ValueError):
            summary(data)

    def test_two_ordinary_support_installs_keep_their_own_lookup_levels_and_coordinates(self):
        data, observed, metadata = ordinary()
        data["7420"]["levelProgression"].append({"level": 19, "value7": Decimal("12.75")})
        observed["groups"][1]["members"][0]["skill_id"] = 7420
        members = project(data, observed, metadata)["members"]
        self.assertEqual([(row["alias"], row["ordinary_support"]["lookup"]["level"],
                           row["ordinary_support"]["candidate"]["value"]["fraction"])
                          for row in members if row["ordinary_support"] is not None],
                         [("gem[1]", 7, {"numerator": 37, "denominator": 400}),
                          ("gem[3]", 19, {"numerator": 51, "denominator": 400})])

    def test_installed_gems_receive_catalog_lookups_and_explicit_gaps_without_effective_levels(self):
        result = project(records(), installation(), catalog())
        member = result["members"][0]
        self.assertEqual((result["format"], result["version"], result["profile_version"], result["accounting"],
                          result["arithmetic_ready"], result["runtime_verified"], result["identity_verified"],
                          result["import_complete"], result["activation"], result["patch"], result["effective_level"],
                          member["alias"], member["group"], member["path"], member["gem_level"],
                          member["effective_level"], member["lookup_level_meaning"], member["profile"]["hit"]),
                         ("tli-installed-skill-profiles-v1", "0.1.1", "0.2.1",
                          {"members": 4, "profiled": 1, "gaps": 3, "reconciles": True},
                          False, False, False, False, "unknown", "unknown", None,
                          "gem[1]", "group[1]", "sections.SkillLayout.data[0][0]", 7, None,
                          "observed_gem_level_not_effective", {"status": "catalog_render_consistent", "type": "cold",
                          "min": "11", "max": "19", "level": 7, "binding": {"min": "value1Min", "max": "value1Max"},
                          "checkedAtLevel": 20}))

    def test_uncaptured_client_keeps_members_and_accounting_unknown(self):
        from test_installedskills import absent

        for status in ("absent", "invalid", "not_captured"):
            with self.subTest(status=status):
                data = installation_project(absent("client", status), "a" * 64)
                result = project(None, data, catalog())
                self.assertEqual((result["client_layer"], result["members"], result["accounting"]),
                                 (status, None, {"members": None, "profiled": None, "gaps": None, "reconciles": None}))

    def test_captured_client_requires_a_record_map_with_only_observed_canonical_ids(self):
        for data in (None, [], {90017: records()["90017"]}, {"090017": None}, {"0": None},
                     {"99991": None}, {"90017": []}, {"90017": {**records()["90017"], "tlidbId": True}},
                     {"90017": {**records()["90017"], "tlidbId": 90029}},
                     {"90017": {**records()["90017"], "tlidbId": "90017"}}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                project(data, installation(), catalog())

    def test_an_empty_record_map_is_missing_catalog_evidence_instead_of_zero_skill_values(self):
        result = project({}, installation(), catalog())
        self.assertEqual((result["accounting"], [(row["reason"], row["profile"]) for row in result["members"]]),
                         ({"members": 4, "profiled": 0, "gaps": 4, "reconciles": True},
                          [("catalog_record_missing", None)] * 3 + [("invalid_gem_level", None)]))

    def test_catalog_records_require_loaded_category_masters_and_declared_english_payloads(self):
        for change in ("category", "master", "english", "path", "withheld", "malformed_english"):
            with self.subTest(change=change):
                data, metadata = records(), catalog()
                if change == "category":
                    data["90017"]["category"] = "Unknown"
                elif change == "master":
                    data["90017"].update(category="Ignored_English", catalogPath="skill/Ignored_English")
                elif change == "english":
                    data["90017"].update(category="Noble_Support", catalogPath="skill/Noble_Support")
                elif change == "path":
                    data["90017"]["catalogPath"] = "skill/Noble_Support"
                elif change == "withheld":
                    metadata["withheld_record_ids"].append(90017)
                else:
                    data["90017"]["english"] = "not a catalog entry"
                with self.assertRaises(ValueError):
                    project(data, installation(), metadata)

    def test_absent_english_preserves_master_fields_with_an_explicit_unbound_hit(self):
        data = records()
        data["90017"].update(category="Noble_Support", catalogPath="skill/Noble_Support", english=None)
        result = project(data, installation(), catalog())["members"][0]["profile"]
        self.assertEqual((result["hit"], result["tags"]["skill"], result["effectivenessOfAddedDamage"]),
                         ({"status": "no_binding"}, ["activation_medium", "projectile", "spell"],
                          {"status": "stated", "text": "117.5%", "value": "1.175"}))

    def test_installation_and_catalog_are_revalidated_before_any_profile_lookup(self):
        for target in ("source", "installation_runtime", "catalog_runtime"):
            with self.subTest(target=target):
                installed, metadata = installation(), catalog()
                if target == "source":
                    installed["source"]["sha256"] = "wrong"
                elif target == "installation_runtime":
                    installed["runtime"]["verified"] = True
                else:
                    metadata["network_bytes_verified"] = True
                with self.assertRaises(ValueError):
                    project(records(), installed, metadata)

    def test_canonical_summaries_preserve_profile_gaps_and_detach_nested_values(self):
        from damage_lab.installedprofiles import summary

        canonical = project(records(), installation(), catalog())
        result = summary(canonical)
        self.assertEqual(result, canonical)
        result["members"][0]["profile"]["tags"]["skill"].clear()
        result["catalog"]["documents"][0]["byte_range"][0] = 0
        self.assertEqual((canonical["members"][0]["profile"]["tags"]["skill"],
                          canonical["catalog"]["documents"][0]["byte_range"]),
                         (["activation_medium", "projectile", "spell"], [19, 87]))

    def test_canonical_metadata_and_counts_cannot_promote_or_contradict_the_diagnostic(self):
        from damage_lab.installedprofiles import summary

        changes = [(("format",), "other"), (("version",), "0.2.0"), (("profile_version",), "0.2.0"),
                   (("source", "sha256"), "A" * 64), (("source", "binding"), "bytes_verified"),
                   (("arithmetic_ready",), True), (("runtime_verified",), 0), (("identity_verified",), True),
                   (("import_complete",), True), (("activation",), "active"), (("patch",), "verified"),
                   (("effective_level",), 7), (("client_layer",), "absent"), (("members",), None),
                   (("accounting", "members"), True), (("accounting", "members"), 3),
                   (("accounting", "profiled"), 2), (("accounting", "gaps"), -1),
                   (("accounting", "reconciles"), 1), (("catalog", "network_bytes_verified"), True)]
        for path, value in changes:
            with self.subTest(path=path):
                data = project(records(), installation(), catalog())
                node = data
                for name in path[:-1]:
                    node = node[name]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    summary(data)

    def test_canonical_members_require_consistent_source_coordinates_and_gap_reasons(self):
        from damage_lab.installedprofiles import summary

        for field, value in (("alias", "gem[2]"), ("group", "group[2]"), ("tab_position", True),
                              ("tab_position", 2), ("path", "sections.SkillLayout.data[0][2]"),
                              ("path", "sections.Other.data[0][0]"), ("slot", 0), ("skill_id", True),
                              ("gem_level", 0), ("effective_level", 7), ("lookup_level_meaning", "effective"),
                              ("status", "complete"), ("status", "gap"), ("reason", "invalid_gem_level"),
                              ("profile", None), ("catalog_category", None)):
            with self.subTest(field=field):
                data = project(records(), installation(), catalog())
                data["members"][0][field] = value
                with self.assertRaises(ValueError):
                    summary(data)

    def test_profile_identity_levels_and_tag_partitions_cannot_be_forged(self):
        from damage_lab.installedprofiles import summary

        changes = [(("format",), "other"), (("version",), "0.2.0"), (("runtimeVerified",), 0),
                   (("level",), 13), (("identity", "status"), "verified"),
                   (("identity", "tlidbId"), True), (("identity", "tlidbId"), 90029),
                   (("identity", "guid"), "x" * 65), (("identity", "guidStatus"), "absent"),
                   (("tags", "status"), "unknown"), (("tags", "skill"), ["cold"]),
                   (("tags", "skill"), ["spell", "spell"]), (("tags", "skill"), ["Spell"]),
                   (("tags", "damageTypes"), ["spell"]), (("tags", "reserved"), ["cold"]),
                   (("mainStat", "attributes"), ["wisdom"]), (("mainStat", "attributes"), ["strength", "strength"]),
                   (("mainStat", "status"), "invalid")]
        for path, value in changes:
            with self.subTest(path=path):
                data = project(records(), installation(), catalog())
                node = data["members"][0]["profile"]
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    summary(data)

    def test_summary_drops_extra_identity_tag_and_attribute_properties(self):
        from damage_lab.installedprofiles import summary

        data = project(records(), installation(), catalog())
        value = data["members"][0]["profile"]
        for node in (data, data["source"], data["catalog"], data["catalog"]["documents"][0],
                     data["members"][0], value, value["identity"], value["tags"], value["mainStat"]):
            node["opaque"] = {"accountId": "PRIVATE-PROFILE-CANARY"}
        value["tags"]["catalog"] = ["PRIVATE-PROFILE-CANARY"]
        self.assertNotIn("PRIVATE-PROFILE-CANARY", json.dumps(summary(data)))

    def test_typed_profile_fields_require_exact_units_binding_ranges_and_statuses(self):
        from damage_lab.installedprofiles import summary

        changes = [(("effectivenessOfAddedDamage", "value"), "1.17"),
                   (("effectivenessOfAddedDamage", "text"), "117.5 seconds"),
                   (("castSpeedField", "seconds"), .73), (("castSpeedField", "text"), "0.73/s"),
                   (("castSpeedField", "status"), "not_stated"), (("hit", "status"), "complete"),
                   (("hit", "type"), "all"), (("hit", "min"), "-1"), (("hit", "max"), "10"),
                   (("hit", "min"), 11), (("hit", "level"), 13), (("hit", "checkedAtLevel"), True),
                   (("hit", "binding", "min"), "value1"), (("hit", "binding", "max"), "value2Max")]
        for path, value in changes:
            with self.subTest(path=path):
                data = project(records(), installation(), catalog())
                node = data["members"][0]["profile"]
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    summary(data)

    def test_profile_field_gaps_remain_explicit_and_cannot_smuggle_unknown_payloads(self):
        from damage_lab.installedprofiles import summary

        data = project(records(), installation(), catalog())
        value = data["members"][0]["profile"]
        for node in (value["effectivenessOfAddedDamage"], value["castSpeedField"], value["hit"], value["hit"]["binding"]):
            node["opaque"] = "PRIVATE-NESTED-PROFILE-CANARY"
        self.assertNotIn("PRIVATE-NESTED-PROFILE-CANARY", json.dumps(summary(data)))
        for status in ("no_binding", "multiple_damage_lines", "no_spell_hit_line", "binding_count_mismatch",
                       "binding_not_range", "render_mismatch", "invalid_range", "level_not_in_table", "non_integer_value"):
            with self.subTest(status=status):
                value["hit"] = {"status": status, "opaque": "PRIVATE-NESTED-PROFILE-CANARY"}
                self.assertEqual(summary(data)["members"][0]["profile"]["hit"], {"status": status})

    def test_the_same_skill_on_two_gems_is_looked_up_at_each_observed_level(self):
        data = installation()
        data["groups"][0]["members"][1].update(skill_id=90017, gem_level=20)
        result = project(records(), data, catalog())
        self.assertEqual([(row["gem_level"], row["profile"]["hit"]["min"], row["effective_level"])
                          for row in result["members"][:2]], [(7, "11", None), (20, "437", None)])

    def test_an_invalid_observed_identity_is_a_gap_without_a_guid_or_name_bridge(self):
        data = installation()
        data["groups"][0]["members"][1]["skill_id"] = None
        data["issues"].append({"path": "sections.SkillLayout.data[0][2]", "reason": "invalid_skill_id"})
        data["relationships"] = [row for row in data["relationships"] if row["secondary"] != "gem[2]"]
        result = project(records(), data, catalog())["members"][1]
        self.assertEqual((result["skill_id"], result["catalog_category"], result["reason"], result["profile"]),
                         (None, None, "invalid_skill_id", None))

    def test_a_known_record_does_not_supply_an_unknown_observed_gem_level(self):
        data = records()
        data["90053"] = {**data["90017"], "tlidbId": 90053}
        result = project(data, installation(), catalog())["members"][3]
        self.assertEqual((result["gem_level"], result["catalog_category"], result["reason"], result["profile"]),
                         (None, "Active", "invalid_gem_level", None))

    def test_a_captured_empty_client_has_zero_counts_without_claiming_complete_import(self):
        data = installation()
        data["domains"]["client"] = {"status": "captured", "tabs": 0, "null_tabs": 0, "rows": 0, "null_rows": 0}
        data["domains"]["server"] = {key: "absent" if key == "status" else None for key in data["domains"]["server"]}
        data.update(groups=[], relationships=[], unmatched_server_slots=[], issues=[])
        result = project({}, data, catalog())
        self.assertEqual((result["members"], result["accounting"], result["import_complete"]),
                         ([], {"members": 0, "profiled": 0, "gaps": 0, "reconciles": True}, False))

    def test_catalog_field_statuses_preserve_absent_invalid_and_explicit_empty_values(self):
        from damage_lab.installedprofiles import summary

        for tags, status, values in ((None, "absent", None), (17, "invalid", None), ([], "supplied", [])):
            with self.subTest(status=status):
                data = records()
                data["90017"].update(tags=tags, mainStat=tags, castSpeed="", effectivenessOfAddedDamage="bad")
                result = summary(project(data, installation(), catalog()))["members"][0]["profile"]
                self.assertEqual((result["tags"], result["mainStat"], result["castSpeedField"],
                                  result["effectivenessOfAddedDamage"]),
                                 ({"status": status, "skill": values, "damageTypes": values, "reserved": values},
                                  {"status": status, "attributes": values},
                                  {"status": "not_stated", "text": "", "seconds": None},
                                  {"status": "invalid", "text": None, "value": None}))

    def test_project_keeps_inputs_unchanged_and_drops_raw_english_catalog_tags_and_instance_data(self):
        data, installed, metadata = records(), installation(), catalog()
        data["90017"]["english"]["description"] += "\nPRIVATE-RAW-PROFILE-CANARY"
        data["90017"].update(id={"instanceId": "PRIVATE-RAW-PROFILE-CANARY"},
                             opaque={"accountId": "PRIVATE-RAW-PROFILE-CANARY"})
        original = copy.deepcopy((data, installed, metadata))
        result = project(data, installed, metadata)
        text = json.dumps(result)
        result["members"][0]["profile"]["tags"]["skill"].clear()
        result["catalog"]["documents"][0]["byte_range"].clear()
        self.assertEqual(((data, installed, metadata) == original, "PRIVATE-RAW-PROFILE-CANARY" in text,
                          "Activation Medium" in text, result["members"][0]["profile"]["identity"]["guid"],
                          result["members"][0]["profile"]["hit"]),
                         (True, False, False, None, {"status": "render_mismatch"}))

    def test_missing_canonical_fields_and_invalid_containers_fail_with_controlled_errors(self):
        from damage_lab.installedprofiles import summary

        for path in ((), ("source",), ("catalog",), ("members", 0), ("members", 0, "profile"),
                     ("members", 0, "profile", "tags"), ("members", 0, "profile", "hit")):
            with self.subTest(path=path):
                data = project(records(), installation(), catalog())
                node = data
                for field in path:
                    node = node[field]
                node.pop(next(iter(node)))
                with self.assertRaises(ValueError):
                    summary(data)
        for value in (None, [], False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                summary(value)

    def test_resolved_skill_ids_cannot_outnumber_the_declared_catalog_records(self):
        from damage_lab.installedprofiles import summary

        metadata = catalog()
        metadata.update(skills=0, records=metadata["invalid_records"] + metadata["withheld_records"])
        result = project(records(), installation(), catalog())
        result["catalog"] = metadata
        for operation in (lambda: project(records(), installation(), metadata), lambda: summary(result)):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()

    def test_repeated_gem_lookups_count_one_distinct_catalog_skill(self):
        from damage_lab.installedprofiles import summary

        installed, metadata = installation(), catalog()
        installed["groups"][0]["members"][1].update(skill_id=90017, gem_level=20)
        metadata.update(skills=1, records=1 + metadata["invalid_records"] + metadata["withheld_records"])
        result = summary(project(records(), installed, metadata))
        self.assertEqual((result["accounting"]["profiled"], result["catalog"]["skills"]), (2, 1))
