import copy
import json
import unittest

from damage_lab.importcoverage import project, summary


def document(guide=False):
    """Synthetic producer document with all nine domains, without a supplied guide."""
    domains = {
        "equipment": {"composition": "observed", "effective": "unverified",
                      "paths": ["sections.WearItems.data[].sourceData.AffixList"],
                      "counts": {"items": 3, "invalidRecords": 1, "affixes": 5,
                                 "affixesWithRolls": 2, "affixesWithoutRolls": 3, "invalidAffixes": 1}},
        "skillLayout": {"composition": "observed", "effective": "unverified",
                        "paths": ["sections.SkillLayout.data[tab][].SkillData._Raw_Data"],
                        "counts": {"groups": 1, "mainSkills": 1, "supports": 2,
                                   "integerLevels": 2, "invalidLevels": 1, "invalidRecords": 0, "emptySlots": 3},
                        "guideSupportLevelValues": None},
        "heroTraits": {"composition": "observed", "effective": "unknown",
                       "paths": ["sections.HeroCharacter.data.HeroCharacters", "sections.HeroCharacter.data.HeroJewels"],
                       "counts": {"selectedTraits": 4, "memories": 2, "invalidRecords": 0},
                       "rankStatus": "rank_rule_unverified", "baseTraitRank": "no_verified_source",
                       "rankSource": "trait_ranks.candidates (trait-ranks.json)"},
        "talents": {"composition": "observed", "effective": "unverified",
                    "paths": ["sections.GeniusInfos.data.entries[].value.GeniusList"],
                    "counts": {"trees": 2, "nodesWithPoints": 7, "invalidRecords": 0}},
        "slates": {"composition": "observed", "effective": "unverified",
                   "paths": ["sections.ServerSource.data.featuresInfo.talentBlock.dressingTalentBlocks"],
                   "counts": {"slates": 2, "emptySlots": 1, "invalidRecords": 0}},
        "pactspirits": {"composition": "observed", "effective": "unverified",
                       "paths": ["sections.PetDatas.data"],
                       "counts": {"pactspirits": 1, "emptySlots": 2, "invalidRecords": 0}},
        "nativeStats": {"composition": "observed", "effective": "unverified",
                        "paths": ["sections.ServerSource.data.attrInfo"],
                        "counts": {"named": 1, "unnamedStatPairs": 9, "otherUnnamedFields": 2},
                        "semantics": "named_fields_corroborated_only; unnamed_ids_unmapped", "protocolVerified": False},
        "panelSkillIdentity": {"composition": "absent", "effective": "unknown",
                               "paths": ["(no snapshot path; panel-log RoleAttrMgr lines name no skill)"],
                               "counts": {}, "identity": "chosen_skill_unverified"},
        "supportActivation": {"composition": "observed", "effective": "unknown",
                              "paths": ["sections.SkillLayout.data[tab][SlotId 2-6]",
                                        "sections.ServerSource.data.featuresInfo.skillLayout.slots"],
                              "counts": {"installedSupports": 2}, "activation": "unknown",
                              "reason": "client layout flags never vary; no disabled state observed"}}
    gaps = [
        ("equipment", "affix-to-modifier mapping and conditional effects are not established",
         "map affix modifier ids to engine families with catalog provenance"),
        ("skillLayout", "effective support level and gem-to-skill effects are not established",
         "source-bound effective-level rule from catalog plus named level bonuses"),
        ("heroTraits", "rank rule C vs C+E unverified; base trait memory source unverified",
         "first-party source linking Trait Level to the memory fields"),
        ("talents", "talent node effects are not mapped to the modifier engine", "catalog node effect mapping with provenance"),
        ("slates", "slate effects need catalog-bound decoding and area rules", "catalog-bound slate effect decoding"),
        ("pactspirits", "pactspirit effects and slot roles are not mapped", "catalog-bound pactspirit effect mapping"),
        ("nativeStats", "only corroborated named fields; unnamed stat ids are unmapped",
         "first-party schema naming the unnamed attrInfo ids"),
        ("panelSkillIdentity", "no saved source names the skill shown by the panel", "a logged line that names the displayed skill"),
        ("supportActivation", "installed supports have no varying enabled/disabled field",
         "a varying named activation field or its first-party definition")]
    if guide:
        domains["skillLayout"]["guideSupportLevelValues"] = {
            "resolved": 2, "missing_level": 0, "duplicate_level": 0, "invalid_value": 0,
            "unverified_flat_tail": 0, "not_level_scaled": 0, "absent": 0, "unknown_status": 0, "invalid": 0}
    return {"format": "tli-import-coverage-v1", "version": "0.2.0", "tool": "tli-build-exporter/import_coverage",
            "source": {"sha256": "a" * 64, "capturedAt": "2026-02-17T03:19:41+00:00", "capturedAtStatus": "valid"},
            "guide": {"supplied": guide, "sha256": "b" * 64 if guide else None,
                      "binding": "unverified" if guide else "not_supplied"}, "importComplete": False,
            "domains": domains,
            "gaps": [{"domain": name, "composition": domains[name]["composition"], "gap": gap, "next": step}
                     for name, gap, step in gaps],
            "rules": [
                "composition=observed means at least one shape-valid record exists; it says nothing about combat effect.",
                "effective is never verified in this version: unverified = valid named records exist but their combat application is not established; unknown = no valid record or no saved source.",
                "Presence is not activation; equal numbers are not identity; trait rank candidates C and C+E stay unverified.",
                "importComplete is always false until every domain has an established effective state.",
                "The guide is hashed separately; its binding to the source snapshot is not verified."]}


class ImportCoverageTest(unittest.TestCase):
    """Coverage observations never claim verified combat effects or complete import."""

    def test_observed_composition_remains_an_incomplete_import(self):
        self.assertEqual((project(document(), "a" * 64, None)["import_complete"],
                          project(document(), "a" * 64, None)["domains"]["hero_traits"]["effective"]), (False, "unknown"))

    def test_source_and_guide_hashes_must_match_the_exact_input_files(self):
        for source, guide in (("c" * 64, None), ("A" * 64, None), (True, None), ("a" * 64, "b" * 64)):
            with self.subTest(source=source, guide=guide), self.assertRaises(ValueError):
                project(document(), source, guide)

    def test_unknown_properties_are_removed_at_every_depth(self):
        data = document(guide=True)
        for row in (data, data["source"], data["guide"], data["domains"],
                    data["domains"]["equipment"], data["domains"]["equipment"]["counts"],
                    data["domains"]["skillLayout"]["guideSupportLevelValues"], data["gaps"][0]):
            row["account"] = {"rawItemId": "SYNTHETIC-PRIVATE-CANARY"}
        self.assertNotIn("SYNTHETIC-PRIVATE-CANARY", json.dumps(project(data, "a" * 64, "b" * 64)))

    def test_format_version_and_incomplete_status_are_explicit(self):
        for key, value in (("format", "other"), ("version", "0.1.0"), ("tool", "private-canary"),
                           ("importComplete", True), ("importComplete", 0)):
            data = document()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64, None)

    def test_counts_reject_boolean_float_negative_and_partial_values(self):
        for value in (True, 3.0, -1, "3", {}, None):
            data = document()
            data["domains"]["equipment"]["counts"]["items"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                project(data, "a" * 64, None)
        data = document()
        del data["domains"]["equipment"]["counts"]["affixes"]
        with self.assertRaises(ValueError):
            project(data, "a" * 64, None)

    def test_domain_status_and_count_contradictions_are_rejected(self):
        for domain, field, value in (("equipment", "composition", "verified"), ("equipment", "effective", "verified"),
                                      ("equipment", "composition", "empty"), ("equipment", "counts", {}),
                                      ("heroTraits", "effective", "unverified"),
                                      ("panelSkillIdentity", "composition", "observed")):
            data = document()
            data["domains"][domain][field] = value
            with self.subTest(domain=domain, field=field), self.assertRaises(ValueError):
                project(data, "a" * 64, None)

    def test_cross_counts_cannot_overstate_acquired_records(self):
        for domain, field, value in (("equipment", "affixes", 13), ("skillLayout", "integerLevels", 0),
                                      ("skillLayout", "groups", 7), ("supportActivation", "installedSupports", 8)):
            data = document()
            data["domains"][domain]["counts"][field] = value
            with self.subTest(domain=domain, field=field), self.assertRaises(ValueError):
                project(data, "a" * 64, None)

    def test_fixed_paths_and_metadata_cannot_carry_private_values(self):
        for domain, field, value in (("equipment", "paths", ["sections.Account.private-canary"]),
                                      ("heroTraits", "rankStatus", "verified"),
                                      ("heroTraits", "baseTraitRank", 3), ("heroTraits", "rankSource", "private-canary"),
                                      ("nativeStats", "semantics", "private-canary"), ("nativeStats", "protocolVerified", 0),
                                      ("panelSkillIdentity", "identity", "private-canary"),
                                      ("supportActivation", "activation", "verified"), ("supportActivation", "reason", {})):
            data = document()
            data["domains"][domain][field] = value
            with self.subTest(domain=domain, field=field), self.assertRaises(ValueError):
                project(data, "a" * 64, None)

    def test_guide_counts_require_a_supplied_hashed_guide(self):
        for value in (None, {}, {"resolved": True}, "private-canary"):
            data = document(guide=True)
            data["domains"]["skillLayout"]["guideSupportLevelValues"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                project(data, "a" * 64, "b" * 64)
        data = document()
        data["domains"]["skillLayout"]["guideSupportLevelValues"] = document(guide=True)["domains"]["skillLayout"]["guideSupportLevelValues"]
        with self.assertRaises(ValueError):
            project(data, "a" * 64, None)

    def test_timestamps_cannot_carry_arbitrary_source_text(self):
        for value, status in (("private-canary", "valid"), ("2026-02-30T00:00:00+00:00", "valid"),
                              ("2026-02-17", "valid"), (None, "valid"),
                              ("private-canary", "invalid"), (None, "private-canary")):
            data = document()
            data["source"].update(capturedAt=value, capturedAtStatus=status)
            with self.subTest(value=value, status=status), self.assertRaises(ValueError):
                project(data, "a" * 64, None)

    def test_rules_and_gap_explanations_must_match_the_known_contract(self):
        for target, key, value in (("top", "rules", ["private-canary"]), ("gap", "gap", "private-canary"),
                                   ("gap", "next", {}), ("gap", "composition", "empty"),
                                   ("gap", "domain", "account")):
            data = document()
            (data if target == "top" else data["gaps"][0])[key] = value
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64, None)

    def test_projection_rejects_malformed_required_containers(self):
        for target, key, value in (("top", "domains", []), ("top", "gaps", [False]),
                                   ("top", "source", None), ("top", "guide", False),
                                   ("domains", "equipment", []), ("equipment", "counts", []),
                                   ("equipment", "paths", "private-canary")):
            data = document()
            row = data if target == "top" else data["domains"] if target == "domains" else data["domains"][target]
            row[key] = value
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64, None)

    def test_summary_reuses_validation_and_removes_unknown_properties(self):
        data = project(document(guide=True), "a" * 64, "b" * 64)
        for row in (data, data["source"], data["guide"], data["domains"],
                    data["domains"]["equipment"], data["domains"]["equipment"]["counts"],
                    data["domains"]["skill_layout"]["guide_support_level_values"], data["gaps"][0]):
            row["account"] = {"private": "SYNTHETIC-PRIVATE-CANARY"}
        self.assertEqual(summary(data), project(document(guide=True), "a" * 64, "b" * 64))

    def test_summary_rejects_resolved_effects_and_complete_import_claims(self):
        for target, key, value in (("top", "import_complete", True), ("top", "import_complete", 0),
                                   ("equipment", "effective", "verified"), ("counts", "items", True)):
            data = project(document(), "a" * 64, None)
            row = data if target == "top" else data["domains"]["equipment"]["counts"] if target == "counts" else data["domains"][target]
            row[key] = value
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                summary(data)

    def test_projection_and_summary_do_not_mutate_or_share_nested_inputs(self):
        data = document(guide=True)
        before = copy.deepcopy(data)
        result = project(data, "a" * 64, "b" * 64)
        copied = summary(result)
        copied["domains"]["skill_layout"]["guide_support_level_values"]["resolved"] = 79
        copied["domains"]["equipment"]["paths"].append("synthetic")
        copied["rules"].clear()
        self.assertEqual((data, result), (before, project(before, "a" * 64, "b" * 64)))

    def test_absent_or_invalid_timestamps_remain_explicit_nulls(self):
        for status in ("absent", "invalid"):
            data = document()
            data["source"].update(capturedAt=None, capturedAtStatus=status)
            with self.subTest(status=status):
                self.assertEqual(project(data, "a" * 64, None)["source"]["captured_at"], None)

    def test_a_null_guide_cannot_disguise_a_supplied_file_hash(self):
        data = document()
        data["guide"]["sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            project(data, "a" * 64, None)

    def test_unreadable_native_stats_cannot_retain_observed_counts(self):
        data = document()
        data["domains"]["nativeStats"].update(composition="invalid", effective="unknown", semantics="unreadable")
        del data["domains"]["nativeStats"]["protocolVerified"]
        data["gaps"][6]["composition"] = "invalid"
        with self.assertRaises(ValueError):
            project(data, "a" * 64, None)

    def test_zero_skill_groups_cannot_retain_observed_rows(self):
        data = document()
        data["domains"]["skillLayout"].update(composition="empty", effective="unknown")
        data["domains"]["skillLayout"]["counts"].update(groups=0, supports=0, integerLevels=1, invalidLevels=0)
        data["domains"]["supportActivation"].update(composition="empty")
        data["domains"]["supportActivation"]["counts"]["installedSupports"] = 0
        data["gaps"][1]["composition"] = data["gaps"][8]["composition"] = "empty"
        with self.assertRaises(ValueError):
            project(data, "a" * 64, None)

    def test_absent_domains_remain_unknown_with_no_invented_counts(self):
        data = document()
        for name, row in data["domains"].items():
            row.update(composition="absent", effective="unknown", counts={})
            if name == "heroTraits":
                row["rankStatus"] = "unknown"
            elif name == "nativeStats":
                row["semantics"] = "unreadable"
                del row["protocolVerified"]
        for row in data["gaps"]:
            row["composition"] = "absent"
        self.assertEqual([row["counts"] for row in summary(project(data, "a" * 64, None))["domains"].values()], [{}] * 9)

    def test_invalid_container_and_empty_skill_records_remain_unresolved(self):
        data = document()
        data["domains"]["skillLayout"].update(composition="invalid", effective="unknown")
        data["domains"]["skillLayout"]["counts"] = {key: 0 for key in data["domains"]["skillLayout"]["counts"]}
        data["domains"]["supportActivation"].update(composition="invalid", counts={})
        data["gaps"][1]["composition"] = data["gaps"][8]["composition"] = "invalid"
        self.assertEqual(project(data, "a" * 64, None)["domains"]["skill_layout"]["effective"], "unknown")

    def test_each_gap_and_required_metadata_must_be_present(self):
        for target, field in (("top", "format"), ("source", "capturedAtStatus"),
                              ("heroTraits", "rankSource"), ("skillLayout", "guideSupportLevelValues"),
                              ("equipment", "paths")):
            data = document()
            row = data if target == "top" else data["source"] if target == "source" else data["domains"][target]
            del row[field]
            with self.subTest(target=target, field=field), self.assertRaises(ValueError):
                project(data, "a" * 64, None)
        data = document()
        data["gaps"][1] = data["gaps"][0]
        with self.assertRaises(ValueError):
            project(data, "a" * 64, None)


if __name__ == "__main__":
    unittest.main()
