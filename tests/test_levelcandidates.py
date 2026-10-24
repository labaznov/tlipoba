"""Synthetic level-grant ledgers preserve evidence without choosing an effective level."""

import copy
import json
import unittest

from damage_lab.levelcandidates import CANONICAL_FORMAT, project, summary


def document():
    def domain(status="absent", observed=None, bound=None, candidates=None, coverage="unknown_section_absent", **extra):
        return {"status": status, "observed": observed, "bound": bound, "boundLevelCandidates": candidates,
                "candidateCoverage": coverage, **extra}

    def candidate(kind, path, template, binding, amount, **extra):
        scope = template.removeprefix("+# ").removeprefix("to ").removesuffix(" Skill Level")
        return {"domain": kind, "path": path, "template": template, "binding": binding, "amount": amount,
                "eligibility": {"scope": scope, "scopeTokens": scope.split(), "allTokensInSkillTags": scope == "Spell",
                                "skillCategory": "Active", "status": "unverified"}, **extra}

    tree = "sections.GeniusInfos.data.entries[3].value"
    rows = [candidate("gear", "sections.WearItems.data[2].sourceData.AffixList.PrefixInfoList[4]",
                      "+# Physical Skill Level", {"status": "exact", "kind": "native_id_in_item_document",
                      "catalog": "gear/one_handed/wand/master", "definition": "synthetic-level", "tier": "3+",
                      "tierId": "synthetic-tier", "tierBounds": {"min": "1.0", "max": "4"}},
                      {"exact": "2.70", "origin": "native_roll", "source": "DynArgs[0]"}, nativeId=17932841, slot=7),
            candidate("talent", tree + ".GeniusList.entries[5]", "+# Spell Skill Level",
                      {"status": "computed", "kind": "computed_position_tier_id",
                       "catalog": "talent-tree/synthetic_tree/master", "node": "node-s", "nodeType": "legendary"},
                      {"exact": "3.0", "origin": "catalog_literal", "source": "node.mods[2].value"},
                      rank={"rank": 1, "maxPoints": 1, "serverPoint": 7, "semantics": "single_point_node"}),
            candidate("talent", tree + ".GeniusList.entries[8]", "+# Spell Skill Level",
                      {"status": "computed", "kind": "computed_position_tier_id",
                       "catalog": "talent-tree/synthetic_tree/master", "node": None, "nodeType": "micro"}, None,
                      rank={"rank": 2, "maxPoints": 3, "serverPoint": None, "semantics": "per_point_or_total_unknown"}),
            candidate("talent", tree + ".BonusTalents", "+# Spell Skill Level",
                      {"status": "exact", "kind": "notable_tlidb_id_in_tree",
                       "catalog": "talent-tree/synthetic_tree/master", "node": "notable-a", "nodeType": "notable"},
                      {"exact": "1", "origin": "catalog_literal", "source": "notable.mods[0].value"},
                      rank={"rank": None, "maxPoints": None, "serverPoint": None, "semantics": "selected_core_talent"}),
            candidate("slate", "sections.ServerSource.data.featuresInfo.talentBlock.dressingTalentBlocks[6]",
                      "+# to Attack Skill Level", {"status": "exact", "kind": "slate_mod_tlidb_id",
                       "catalog": "divinity-slate/master", "definition": "slate-a"},
                      {"exact": "1.25", "origin": "catalog_literal", "source": "slateMod.effects[1].value"},
                      installation="listed_in_dressing_blocks_placement_unverified"),
            candidate("pactspirit", "sections.ServerSource.data.featuresInfo.ContractInfosV2.ContractDatas[4]",
                      "+# Spirit Magus Skill Level", {"status": "bridged", "kind": "third_party_bridge_unhashed",
                       "catalog": "pactspirit/master", "definition": "pact-a", "node": 17},
                      {"exact": "4", "origin": "catalog_literal", "source": "node.effects[3].value"}, area=9)]
    domains = {"gear": domain("captured", 1, 1, 1, "all_observed_rows_bound", items=3),
               "talents": domain("captured", 2, 2, 3, "all_observed_rows_bound", notables={"observed": 1, "bound": 1}),
               "divinitySlates": domain("captured", 1, 1, 1, "all_observed_rows_bound", slates=1, placementVerified=False),
               "pactspirits": domain("captured", 1, 1, 1, "all_observed_rows_bound"),
               "etherealPrism": domain("captured", 0, 0, 0, "nothing_observed"),
               "supports": domain("captured", 3, None, None, "saved_catalog_domain_has_no_level_text",
                                  catalogMembers=1, catalogLevelMentions=0),
               "heroTraits": domain(catalogMembers=0, catalogLevelMentions=0),
               "heroMemories": domain(catalogMembers=0, catalogLevelMentions=0),
               "spTalentTree": domain(pairs=None), **{key: domain() for key in
               ("OtherWearItems", "JewelItems", "TalentJewelryDataList", "HeroCharacterItems")}}
    return {"format": "tli-effective-level-candidates-v0", "version": "0.3.1",
            "source": {"sha256": "a" * 64, "binding": "caller_supplied_document_only"},
            "arithmeticReady": False, "runtimeVerified": False, "identityVerified": False, "importComplete": False,
            "effectiveLevel": None, "uniquelyDerivable": False,
            "target": {"skillId": 91437, "status": "observed", "path": "sections.SkillLayout.data[3][1]",
                       "gemLevel": {"value": 17, "status": "ok", "meaning": "observed_gem_level_not_effective"},
                       "catalog": {"status": "bound", "path": "skill/Active/master", "category": "Active",
                                   "tags": ["Spell", "Projectile"]},
                       "skillItemLevel": {"total": 3, "equal": 1, "different": 1, "missing": 0, "invalid": 1,
                                          "semantics": "unknown"}},
            "candidates": rows, "domains": domains,
            "gaps": [{"domain": "talents", "path": rows[2]["path"], "reason": "rank_scaling_unknown"}],
            "limitations": ["source sha256 binds the caller-supplied document only; no bytes are read or verified",
                            "catalog members are taken as supplied; no catalog bytes, currency or patch are verified",
                            "eligibility is template wording against catalog tags only; no scope or stacking rule is verified",
                            "talent identities are computed position/tier ids, not native ids",
                            "no effective level is derived: candidates are never summed"]}


def native():
    """Describe fictional native fields without assigning their level semantics."""
    value = document()
    value["version"] = "0.4.0"
    value["target"]["nativeLevelFields"] = {
        "skillsRow": {"join": "exact_instance", "path": "sections.ServerSource.data.featuresInfo.skills.skills[9]",
                      "joinField": "Id"},
        "fields": {"Level": {"value": 17, "type": "int"}, "SkillItemLevel": {"value": 63, "type": "int"}},
        "levelEqualsGem": True, "semantics": {"Level": "unknown", "SkillItemLevel": "unknown"},
        "arithmeticReady": False, "effectiveLevel": None,
    }
    return value


class LevelCandidatesTests(unittest.TestCase):
    """Public projection keeps candidates diagnostic and source-bound."""

    def test_candidates_preserve_lexemes_and_unknown_effective_level(self):
        result = project(document(), "a" * 64)
        self.assertEqual((result["format"], result["effective_level"], result["candidates"][0]["amount"]["exact"]),
                         (CANONICAL_FORMAT, None, "2.70"))

    def test_native_levels_keep_the_exact_row_without_deriving_an_effective_level(self):
        result = project(native(), "a" * 64)
        fields = result["target"]["native_level_fields"]
        self.assertEqual((result["version"], fields["skills_row"], fields["fields"], fields["level_equals_gem"],
                          fields["semantics"], fields["arithmetic_ready"], fields["effective_level"], result["effective_level"]),
                         ("0.4.0", {"join": "exact_instance", "path": "sections.ServerSource.data.featuresInfo.skills.skills[9]",
                                    "join_field": "Id"},
                          {"Level": {"value": 17, "type": "int"}, "SkillItemLevel": {"value": 63, "type": "int"}},
                          True, {"Level": "unknown", "SkillItemLevel": "unknown"}, False, None, None))

    def test_native_fields_survive_detached_canonical_revalidation(self):
        result = project(native(), "a" * 64)
        expected = copy.deepcopy(result)
        result["target"]["native_level_fields"]["fields"]["Level"]["private"] = "discard-me"
        self.assertEqual(summary(result), expected)

    def test_legacy_ledgers_do_not_invent_native_observations(self):
        self.assertNotIn("native_level_fields", project(document(), "a" * 64)["target"])

    def test_new_ledgers_require_the_native_observation_contract(self):
        value = document()
        value["version"] = "0.4.0"
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_native_values_require_an_exact_row_join(self):
        for status in ("no_instance", "ambiguous_instance", "no_skills_row", "collection_limit", "section_invalid"):
            with self.subTest(status=status):
                value = native()
                value["target"]["nativeLevelFields"]["skillsRow"].update(join=status, path=None)
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_unavailable_native_fields_remain_unknown(self):
        for status in ("no_instance", "ambiguous_instance", "no_skills_row", "collection_limit", "section_invalid",
                       "section_not_decoded", "section_not_available", "section_not_captured", "section_absent",
                       "section_unrecognized"):
            with self.subTest(status=status):
                value = native()
                fields = value["target"]["nativeLevelFields"]
                fields["skillsRow"].update(join=status, path=None)
                fields["fields"] = {name: {"value": None, "type": "unavailable"} for name in ("Level", "SkillItemLevel")}
                fields["levelEqualsGem"] = None
                self.assertEqual(project(value, "a" * 64)["target"]["native_level_fields"]["skills_row"]["join"], status)

    def test_unknown_fields_cannot_be_substituted_for_native_integers(self):
        for row in ({"value": True, "type": "int"}, {"value": "17", "type": "int"},
                    {"value": 17, "type": "invalid"}, {"value": None, "type": "int"},
                    {"value": 10 ** 20, "type": "int"}, {"value": None, "type": "unavailable"}):
            with self.subTest(row=row):
                value = native()
                value["target"]["nativeLevelFields"]["fields"]["SkillItemLevel"] = row
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_native_integer_bounds_do_not_assert_game_level_ranges(self):
        for number in (0, -13):
            with self.subTest(number=number):
                value = native()
                value["target"]["nativeLevelFields"]["fields"]["SkillItemLevel"]["value"] = number
                self.assertEqual(project(value, "a" * 64)["target"]["native_level_fields"]["fields"]["SkillItemLevel"]["value"], number)

    def test_missing_or_invalid_native_levels_cannot_claim_gem_equality(self):
        for status in ("missing", "invalid"):
            with self.subTest(status=status):
                value = native()
                value["target"]["nativeLevelFields"]["fields"]["Level"] = {"value": None, "type": status}
                value["target"]["nativeLevelFields"]["levelEqualsGem"] = None
                self.assertIsNone(project(value, "a" * 64)["target"]["native_level_fields"]["level_equals_gem"])

    def test_native_level_difference_remains_a_difference_without_a_formula(self):
        value = native()
        value["target"]["nativeLevelFields"]["fields"]["Level"]["value"] = 23
        value["target"]["nativeLevelFields"]["levelEqualsGem"] = False
        self.assertFalse(project(value, "a" * 64)["target"]["native_level_fields"]["level_equals_gem"])

    def test_an_unknown_gem_level_cannot_be_compared_to_a_native_integer(self):
        value = native()
        value["target"]["gemLevel"].update(value=None, status="invalid_level")
        value["target"]["nativeLevelFields"]["levelEqualsGem"] = None
        self.assertIsNone(project(value, "a" * 64)["target"]["native_level_fields"]["level_equals_gem"])

    def test_native_row_and_equality_claims_are_recomputed(self):
        for key, change in (("skillsRow", {"join": "exact_instance", "path": "sections.SkillLayout.data[0][0]", "joinField": "Id"}),
                            ("skillsRow", {"join": "exact_instance", "path": "sections.ServerSource.data.featuresInfo.skills.skills[4096]", "joinField": "Id"}),
                            ("skillsRow", {"join": "exact_instance", "path": "sections.ServerSource.data.featuresInfo.skills.skills[9]", "joinField": "BaseId"}),
                            ("levelEqualsGem", False), ("levelEqualsGem", 1), ("arithmeticReady", True),
                            ("effectiveLevel", 17), ("semantics", {"Level": "effective_level", "SkillItemLevel": "unknown"})):
            with self.subTest(key=key, change=change):
                value = native()
                value["target"]["nativeLevelFields"][key] = change
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_unobserved_targets_cannot_claim_a_native_row(self):
        value = native()
        value["target"].update(status="ambiguous_installation", path=None, gemLevel=None)
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_unobserved_targets_keep_an_explicit_unavailable_witness(self):
        value = native()
        value["target"].update(status="ambiguous_installation", path=None, gemLevel=None)
        fields = value["target"]["nativeLevelFields"]
        fields["skillsRow"].update(join="target_unavailable", path=None)
        fields["fields"] = {name: {"value": None, "type": "unavailable"} for name in ("Level", "SkillItemLevel")}
        fields["levelEqualsGem"] = None
        self.assertIsNone(project(value, "a" * 64)["target"]["native_level_fields"]["effective_level"])

    def test_opaque_status_is_exclusive_to_the_special_tree(self):
        value = document()
        value["domains"]["JewelItems"].update(status="captured_opaque", candidateCoverage="unknown_section_captured_opaque")
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_a_bound_gear_candidate_cannot_have_zero_bound_rows(self):
        value = document()
        value["domains"]["gear"]["bound"] = 0
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_a_collection_limit_discards_all_other_domain_gaps(self):
        value = document()
        value["candidates"] = [row for row in value["candidates"] if row["domain"] != "gear"]
        value["domains"]["gear"] = {"status": "collection_limit", "observed": None, "bound": None,
                                    "boundLevelCandidates": None, "candidateCoverage": "unknown_collection_limit"}
        value["gaps"].extend([{"domain": "gear", "path": None, "reason": "collection_limit"},
                              {"domain": "gear", "path": None, "reason": "catalog_member_invalid"}])
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_unknown_extra_text_must_still_be_safe_json_text(self):
        value = document()
        value["account"] = "\ud800"
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_unknown_rows_cannot_claim_all_rows_bound(self):
        value = document()
        value["domains"]["gear"]["observed"] = 2
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_a_real_gap_cannot_claim_full_candidate_coverage(self):
        value = document()
        value["gaps"].append({"domain": "talents", "path": value["candidates"][1]["path"], "reason": "invalid_rank"})
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_gap_coordinates_must_match_their_reason(self):
        value = document()
        value["gaps"].append({"domain": "gear", "reason": "catalog_member_invalid", "path": "sections.WearItems.data[1]"})
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_prism_inventory_cannot_claim_level_candidates(self):
        value = document()
        value["domains"]["etherealPrism"]["boundLevelCandidates"] = 2
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_an_exact_gear_row_is_not_counted_twice(self):
        value = document()
        value["candidates"].append(copy.deepcopy(value["candidates"][0]))
        value["domains"]["gear"]["boundLevelCandidates"] = 2
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_an_unknown_observed_count_cannot_have_a_known_bound_count(self):
        value = document()
        value["candidates"] = [row for row in value["candidates"] if row["domain"] != "gear"]
        value["domains"]["gear"] = {"status": "captured", "observed": None, "bound": 0,
                                    "boundLevelCandidates": None, "candidateCoverage": "unknown_for_unresolved_rows"}
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_summary_is_idempotent(self):
        value = project(document(), "a" * 64)
        self.assertEqual(summary(value), value)

    def test_all_candidate_families_keep_their_distinct_evidence(self):
        result = project(document(), "a" * 64)
        self.assertEqual([(row["domain"], row["binding"]["status"], row["amount"] is None) for row in result["candidates"]],
                         [("gear", "exact", False), ("talent", "computed", False), ("talent", "computed", True),
                          ("talent", "exact", False), ("slate", "exact", False), ("pactspirit", "bridged", False)])

    def test_unknown_catalog_keeps_an_unverified_eligibility_object(self):
        value = document()
        value["target"]["catalog"] = {"status": "catalog_record_missing", "path": None, "category": None, "tags": None}
        for row in value["candidates"]:
            row["eligibility"].update(allTokensInSkillTags=None, skillCategory=None)
        self.assertEqual(project(value, "a" * 64)["candidates"][0]["eligibility"],
                         {"scope": "Physical", "scope_tokens": ["Physical"], "all_tokens_in_skill_tags": None,
                          "skill_category": None, "status": "unverified"})

    def test_ambiguous_installation_has_no_selected_gem(self):
        value = document()
        value["target"].update(status="ambiguous_installation", path=None, gemLevel=None)
        self.assertIsNone(project(value, "a" * 64)["target"]["gem_level"])

    def test_invalid_observed_gem_level_is_unknown_not_zero(self):
        value = document()
        value["target"]["gemLevel"].update(value=None, status="invalid_level")
        self.assertIsNone(project(value, "a" * 64)["target"]["gem_level"]["value"])

    def test_a_missing_domain_cannot_be_defaulted(self):
        value = document()
        del value["domains"]["heroMemories"]
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_source_hash_must_match_the_exact_caller_annotation(self):
        with self.assertRaises(ValueError):
            project(document(), "b" * 64)

    def test_only_the_pinned_version_is_accepted(self):
        for version in ("0.3.0", "0.2.0", None, False, []):
            with self.subTest(version=version):
                value = document()
                value["version"] = version
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_fixed_claims_cannot_be_promoted_in_raw_or_canonical_inputs(self):
        pairs = (("arithmeticReady", "arithmetic_ready"), ("runtimeVerified", "runtime_verified"),
                 ("identityVerified", "identity_verified"), ("importComplete", "import_complete"),
                 ("uniquelyDerivable", "uniquely_derivable"), ("effectiveLevel", "effective_level"))
        for raw, canonical in pairs:
            for normalized in (False, True):
                with self.subTest(field=raw, normalized=normalized):
                    value = summary(project(document(), "a" * 64)) if normalized else document()
                    value[canonical if normalized else raw] = 29 if raw == "effectiveLevel" else True
                    with self.assertRaises(ValueError):
                        summary(value) if normalized else project(value, "a" * 64)

    def test_typed_numbers_and_partition_counts_are_required(self):
        for field, invalid in (("total", True), ("equal", 1.0), ("missing", -1), ("invalid", None), ("total", 9)):
            with self.subTest(field=field, invalid=invalid):
                value = document()
                value["target"]["skillItemLevel"][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_unknown_item_level_partition_stays_unknown(self):
        value = document()
        value["target"]["skillItemLevel"].update({key: None for key in ("total", "equal", "different", "missing", "invalid")})
        self.assertIsNone(project(value, "a" * 64)["target"]["skill_item_level"]["total"])

    def test_eligibility_is_recomputed_only_as_unverified_word_membership(self):
        for field, invalid in (("allTokensInSkillTags", True), ("scopeTokens", ["Cold"]), ("status", "verified")):
            with self.subTest(field=field):
                value = document()
                value["candidates"][0]["eligibility"][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_gear_rolls_require_their_own_tier_bounds_and_plain_lexemes(self):
        for invalid in ("4.000000001", "1e0", "nan", "1234567890123", "1.1234567890", 2.7, True):
            with self.subTest(invalid=invalid):
                value = document()
                value["candidates"][0]["amount"]["exact"] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_multi_point_talents_cannot_acquire_a_literal_amount(self):
        value = document()
        value["candidates"][2]["amount"] = {"exact": "6", "origin": "catalog_literal", "source": "node.mods[0].value"}
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_unknown_rank_scaling_requires_an_explicit_gap(self):
        value = document()
        value["gaps"] = []
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_candidate_counts_cannot_be_forged(self):
        value = project(document(), "a" * 64)
        value["domains"]["talents"]["bound_level_candidates"] = 7
        with self.assertRaises(ValueError):
            summary(value)

    def test_source_paths_cannot_carry_arbitrary_text(self):
        for index in range(6):
            with self.subTest(index=index):
                value = document()
                value["candidates"][index]["path"] = "account/private-player-value"
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_candidates_keep_unknown_placement_and_bridge_scope(self):
        for index, field, invalid in ((4, "installation", "active"), (5, "area", True)):
            with self.subTest(index=index):
                value = document()
                value["candidates"][index][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_unknown_extra_fields_are_removed_at_every_depth(self):
        value = document()
        value["account"] = "privacy-canary"
        value["target"]["catalog"]["description"] = "privacy-canary"
        value["candidates"][0]["binding"]["instanceId"] = "privacy-canary"
        result = project(value, "a" * 64)
        result["domains"]["gear"]["extra"] = {"account": "privacy-canary"}
        self.assertNotIn("privacy-canary", json.dumps(summary(result)))

    def test_projection_and_summary_are_deeply_detached(self):
        value = document()
        original = copy.deepcopy(value)
        result = project(value, "a" * 64)
        detached = summary(result)
        detached["target"]["catalog"]["tags"].append("Changed")
        detached["candidates"][0]["binding"]["tier_bounds"]["min"] = "-4"
        self.assertEqual((value, result), (original, project(original, "a" * 64)))

    def test_malformed_containers_fail_with_a_fixed_non_echoing_error(self):
        for invalid in ([], None, {"privacy-canary": []}, {True: "privacy-canary"}, float("nan")):
            with self.subTest(kind=type(invalid).__name__):
                value = document()
                value["target"] = invalid
                with self.assertRaisesRegex(ValueError, r"^Level candidates [a-zA-Z ]+$"):
                    project(value, "a" * 64)

    def test_limits_apply_before_unknown_payloads_are_copied(self):
        cycle = []
        cycle.append(cycle)
        for invalid in ([None] * 4097, "x" * 4097, cycle, {"set"}, ("tuple",)):
            with self.subTest(kind=type(invalid).__name__):
                value = document()
                value["discarded"] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_collection_limit_is_a_whole_domain_unknown(self):
        value = document()
        value["candidates"] = [row for row in value["candidates"] if row["domain"] != "gear"]
        value["domains"]["gear"] = {"status": "collection_limit", "observed": None, "bound": None,
                                    "boundLevelCandidates": None, "candidateCoverage": "unknown_collection_limit"}
        value["gaps"].append({"domain": "gear", "path": None, "reason": "collection_limit"})
        self.assertIsNone(project(value, "a" * 64)["domains"]["gear"]["observed"])

    def test_unknown_talent_collection_cannot_keep_a_selected_notable(self):
        value = document()
        value["candidates"] = [value["candidates"][3]]
        for key in ("gear", "divinitySlates", "pactspirits"):
            value["domains"][key]["boundLevelCandidates"] = 0
        value["domains"]["talents"] = {"status": "captured", "observed": None, "bound": None,
                                       "boundLevelCandidates": None, "candidateCoverage": "unknown_for_unresolved_rows"}
        value["gaps"] = []
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_determinate_domains_cannot_erase_their_candidate_count(self):
        value = document()
        value["domains"]["gear"].update(boundLevelCandidates=None, candidateCoverage="unknown_for_unresolved_rows")
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_catalog_mentions_require_a_supplied_catalog_member(self):
        value = document()
        value["domains"]["heroTraits"]["catalogLevelMentions"] = 1
        with self.assertRaises(ValueError):
            project(value, "a" * 64)
