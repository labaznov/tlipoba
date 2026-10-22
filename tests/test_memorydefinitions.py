"""Check fictional memory rows without assigning combat roles to catalog definitions."""

import copy
import json
import unittest

from damage_lab.memorydefinitions import project, summary


def document():
    """Describe independent fictional rows with exact lexical catalog and own values."""
    return {"format": "tli-memory-definition-ledger-v1", "version": "0.1.1",
        "source": {"sha256": "a" * 64, "binding": "caller_supplied"},
        "arithmeticReady": False, "runtimeVerified": False, "identityVerified": False, "importComplete": False,
        "catalog": {"logicalPaths": ["hero-memory/master", "hero-memory/i18n/en"], "modifierIds": 7,
                    "collisions": 1, "invalidEntries": 2, "invalidGroups": []},
        "domain": {"status": "captured", "path": "sections.HeroCharacter.data.HeroJewels"},
        "candidates": [{"alias": "heroMemory[0].PrefixInfoList[1]",
            "path": "sections.HeroCharacter.data.HeroJewels[0]._Raw_Data.AffixList.PrefixInfoList[1]",
            "nativeId": 8100073017, "disposition": "exact_definition",
            "definition": {"logicalPath": "hero-memory/master", "group": "randomAffixes", "id": "fictional-memory-row",
                           "modifierId": "8100073017", "memoryType": "Discipline"},
            "template": {"text": "+#% fictional memory value\nA second unresolved line", "source": "hero-memory/i18n/en"},
            "catalogTier": {"tier": 3, "level": None, "literal": None,
                            "range": {"min": "-0.375", "max": "19.125000001"}, "sign": "+", "unit": "%"},
            "ownValues": [{"index": 0, "exact": "7.312500", "source": "DynArgs[0]"}],
            "serverMirror": {"status": "same", "issue": None},
            "nativeConditions": {"Condition": "empty", "Filter": "present", "Behavior": "missing"},
            "memoryType": {"catalog": "Discipline", "helper": "Discipline", "status": "consistent", "basis": "helper_TYPES_convention"},
            "operator": "unresolved", "activation": "unknown", "rankScaling": "unknown", "lineRoles": "unresolved",
            "runtimePoolIdentity": "unresolved"}],
        "omitted": [{"alias": "heroMemory[1].BaseAttrInfoList[2]",
            "path": "sections.HeroCharacter.data.HeroJewels[1]._Raw_Data.AffixList.BaseAttrInfoList[2]",
            "nativeId": 9200031019, "disposition": "ambiguous_catalog_modifier"}],
        "structuralGaps": [{"path": "sections.HeroCharacter.data.HeroJewels[2]", "reason": "jewel_invalid"}],
        "accounting": {"jewels": 3, "rows": 2, "emptySlots": 1, "candidates": 1, "omitted": 1,
                       "structuralGaps": 1, "reconciles": True}}


class MemoryDefinitionsTests(unittest.TestCase):
    """Keep exact definitions and source rows diagnostic, reconciled and detached."""

    def test_catalog_range_and_own_lexemes_stay_separate_with_unresolved_roles(self):
        result = project(document(), "a" * 64)
        row = result["candidates"][0]
        self.assertEqual((row["catalog_tier"]["range"], row["own_values"], row["line_roles"], result["arithmetic_ready"]),
                         ({"min": "-0.375", "max": "19.125000001"},
                          [{"index": 0, "exact": "7.312500", "source": "DynArgs[0]"}], "unresolved", False))

    def test_ambiguous_native_ids_remain_omitted_without_a_partial_definition(self):
        result = project(document(), "a" * 64)
        self.assertEqual(result["omitted"], [{"alias": "heroMemory[1].BaseAttrInfoList[2]",
            "path": "sections.HeroCharacter.data.HeroJewels[1]._Raw_Data.AffixList.BaseAttrInfoList[2]",
            "native_id": 9200031019, "disposition": "ambiguous_catalog_modifier"}])

    def test_invalid_native_id_is_null_only_for_the_invalid_id_disposition(self):
        for disposition, native in (("native_id_invalid", 13), ("no_exact_catalog_modifier", None),
                                     ("ambiguous_catalog_modifier", True), ("own_value_invalid", "13"),
                                     ("definition_invalid", 0), ("memory_type_conflict", 10 ** 20)):
            with self.subTest(disposition=disposition):
                value = document()
                value["omitted"][0].update(disposition=disposition, nativeId=native)
                with self.assertRaisesRegex(ValueError, "^Memory definitions contain an invalid source-bound diagnostic contract$"):
                    project(value, "a" * 64)

    def test_every_documented_omission_preserves_the_row_without_inventing_a_candidate(self):
        dispositions = ("native_id_invalid", "no_exact_catalog_modifier", "ambiguous_catalog_modifier", "definition_invalid",
                        "english_template_missing", "english_template_invalid", "memory_type_conflict", "own_value_invalid")
        for disposition in dispositions:
            with self.subTest(disposition=disposition):
                value = document()
                value["omitted"][0].update(disposition=disposition, nativeId=None if disposition == "native_id_invalid" else 9200031019)
                self.assertEqual(project(value, "a" * 64)["omitted"][0]["disposition"], disposition)

    def test_all_five_catalog_groups_are_exact_identifiers_without_role_assignment(self):
        for group in ("baseStats", "fixedAffixes", "randomAffixes", "revivedAffixes", "specialRandomAffixes"):
            with self.subTest(group=group):
                value = document()
                value["candidates"][0]["definition"]["group"] = group
                self.assertEqual(project(value, "a" * 64)["candidates"][0]["definition"]["group"], group)

    def test_catalog_definition_identity_has_no_prefix_or_metadata_fallback(self):
        for field, invalid in (("logicalPath", "gear/master"), ("group", "random"), ("id", "not a catalog id"),
                               ("modifierId", "810007301"), ("modifierId", 8100073017), ("memoryType", "Other")):
            with self.subTest(field=field):
                value = document()
                value["candidates"][0]["definition"][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_any_catalog_type_is_not_promoted_to_consistent_helper_mapping(self):
        for helper in (None, "Origin", "Discipline", "Progress"):
            with self.subTest(helper=helper):
                value = document()
                value["candidates"][0]["definition"]["memoryType"] = "Any"
                value["candidates"][0]["memoryType"].update(catalog="Any", helper=helper, status="catalog_any")
                self.assertEqual(project(value, "a" * 64)["candidates"][0]["memory_type"]["status"], "catalog_any")

    def test_missing_helper_type_stays_unknown_and_never_asserts_catalog_native_proof(self):
        value = document()
        value["candidates"][0]["memoryType"].update(helper=None, status="unknown")
        self.assertEqual(project(value, "a" * 64)["candidates"][0]["memory_type"],
                         {"catalog": "Discipline", "helper": None, "status": "unknown", "basis": "helper_TYPES_convention"})

    def test_memory_type_contradictions_cannot_create_exact_candidates(self):
        for field, invalid in (("catalog", "Origin"), ("helper", "Progress"), ("helper", "Any"),
                               ("status", "catalog_any"), ("basis", "native_verified")):
            with self.subTest(field=field):
                value = document()
                value["candidates"][0]["memoryType"][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_tier_literal_and_own_values_remain_independent_even_when_equal(self):
        value = document()
        value["candidates"][0]["catalogTier"].update(literal="7.312500", range=None, sign=None, unit=None, level=0)
        result = project(value, "a" * 64)["candidates"][0]
        self.assertEqual((result["catalog_tier"]["literal"], result["own_values"][0]["exact"], result["operator"]),
                         ("7.312500", "7.312500", "unresolved"))

    def test_catalog_tiers_require_exclusive_ordered_exact_values_and_bounded_metadata(self):
        for change in ("both", "neither", "reversed", "float", "tier_bool", "tier_negative", "tier_large",
                       "level_float", "level_large", "sign_unicode", "unit_unbound"):
            with self.subTest(change=change):
                value = document()
                tier = value["candidates"][0]["catalogTier"]
                if change == "both":
                    tier["literal"] = "7"
                elif change == "neither":
                    tier["range"] = None
                elif change == "reversed":
                    tier["range"].update(min="19.2", max="-0.375")
                elif change == "float":
                    tier["range"]["min"] = 0.125
                elif change.startswith("tier"):
                    tier["tier"] = {"tier_bool": True, "tier_negative": -1, "tier_large": 10 ** 18}[change]
                elif change.startswith("level"):
                    tier["level"] = 3.0 if change == "level_float" else 10 ** 18
                elif change == "sign_unicode":
                    tier["sign"] = "−"
                else:
                    tier["unit"] = "damage"
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_exact_own_numbers_cannot_be_float_expression_exponent_or_unicode_coercions(self):
        for invalid in (True, 7, 7.3125, "1/3", "1+2", "1e-3", " 7.3", "+7.3", "٣", "1" * 13, "0." + "1" * 10):
            with self.subTest(invalid=invalid):
                value = document()
                value["candidates"][0]["ownValues"][0]["exact"] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_own_values_keep_contiguous_indices_and_their_exact_dynargs_paths(self):
        for change in ("index", "bool", "source", "duplicate"):
            with self.subTest(change=change):
                value = document()
                values = value["candidates"][0]["ownValues"]
                if change == "duplicate":
                    values.append(copy.deepcopy(values[0]))
                else:
                    values[0]["source" if change == "source" else "index"] = "DynArgs[1]" if change == "source" else True if change == "bool" else 2
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_templates_allow_utf8_and_lf_without_replacing_unencodable_or_control_text(self):
        value = document()
        value["candidates"][0]["template"]["text"] = "Память — # 🌟\nUnresolved"
        self.assertEqual(json.loads(json.dumps(project(value, "a" * 64), ensure_ascii=False).encode("utf-8"))["candidates"][0]["template"]["text"],
                         "Память — # 🌟\nUnresolved")

    def test_invalid_templates_are_refused_without_payload_echo(self):
        for invalid in ("", "\ud800", "memory\r\nline", "memory\tline", "memory\x7fline", "x" * 1025, None, {}):
            with self.subTest(invalid=invalid):
                value = document()
                value["candidates"][0]["template"]["text"] = invalid
                with self.assertRaisesRegex(ValueError, "^Memory definitions contain an invalid source-bound diagnostic contract$"):
                    project(value, "a" * 64)

    def test_documented_mirror_status_issue_pairs_preserve_uncertainty(self):
        pairs = (("same", None), ("absent", None), ("different", None), ("different", "length_mismatch"),
                 ("unknown", "mirror_value_invalid"), ("unknown", "mirror_ambiguous"),
                 ("unknown", "mirror_container_invalid"), ("unknown", "mirror_row_invalid"))
        for status, issue in pairs:
            with self.subTest(status=status, issue=issue):
                value = document()
                value["candidates"][0]["serverMirror"].update(status=status, issue=issue)
                self.assertEqual(project(value, "a" * 64)["candidates"][0]["server_mirror"], {"status": status, "issue": issue})

    def test_malformed_mirrors_cannot_be_promoted_to_absence_or_equality(self):
        for status, issue in (("same", "mirror_row_invalid"), ("absent", "mirror_container_invalid"),
                              ("unknown", None), ("unknown", "length_mismatch"), ("different", "mirror_value_invalid"),
                              ("unknown", "mirror_list_unmapped")):
            with self.subTest(status=status, issue=issue):
                value = document()
                value["candidates"][0]["serverMirror"].update(status=status, issue=issue)
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_unmapped_lists_only_report_the_documented_unknown_mirror(self):
        value = document()
        row = value["candidates"][0]
        row["path"] = row["path"].replace("PrefixInfoList", "ChipAffixList")
        row["alias"] = row["alias"].replace("PrefixInfoList", "ChipAffixList")
        row["serverMirror"].update(status="unknown", issue="mirror_list_unmapped")
        self.assertEqual(project(value, "a" * 64)["candidates"][0]["server_mirror"],
                         {"status": "unknown", "issue": "mirror_list_unmapped"})

    def test_native_conditions_are_three_fixed_fields_of_lexical_states(self):
        for field in ("Condition", "Filter", "Behavior"):
            for invalid in ([], {}, None, True, "active"):
                with self.subTest(field=field, invalid=invalid):
                    value = document()
                    value["candidates"][0]["nativeConditions"][field] = invalid
                    with self.assertRaises(ValueError):
                        project(value, "a" * 64)

    def test_source_paths_and_aliases_must_describe_the_same_bounded_row(self):
        for field, invalid in (("alias", "heroMemory[1].PrefixInfoList[1]"),
                               ("path", "sections.HeroCharacter.data.HeroJewels[3]._Raw_Data.AffixList.PrefixInfoList[1]"),
                               ("path", "sections.HeroCharacter.data.HeroJewels[0]._Raw_Data.AffixList.PrefixInfoList[4096]"),
                               ("path", "sections.ServerSource.data.secret")):
            with self.subTest(field=field, invalid=invalid):
                value = document()
                value["candidates"][0][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_candidates_and_omissions_cannot_claim_the_same_source_row(self):
        value = document()
        value["omitted"][0].update(alias=value["candidates"][0]["alias"], path=value["candidates"][0]["path"])
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_structural_gap_reasons_determine_their_exact_source_path_shape(self):
        for reason, path in (("jewel_invalid", "sections.HeroCharacter.data.HeroJewels[2]"),
                             ("affix_list_invalid", "sections.HeroCharacter.data.HeroJewels[2]._Raw_Data.AffixList"),
                             ("affix_container_invalid", "sections.HeroCharacter.data.HeroJewels[2]._Raw_Data.AffixList.BAffixInfoList"),
                             ("row_invalid", "sections.HeroCharacter.data.HeroJewels[2]._Raw_Data.AffixList.BAffixInfoList[4]")):
            with self.subTest(reason=reason):
                value = document()
                value["structuralGaps"] = [{"path": path, "reason": reason}]
                self.assertEqual(project(value, "a" * 64)["structural_gaps"], [{"path": path, "reason": reason}])

    def test_structural_gaps_cannot_overlap_valid_rows_or_use_a_different_reason_shape(self):
        for path in ("sections.HeroCharacter.data.HeroJewels[0]", "sections.HeroCharacter.data.HeroJewels[2]._Raw_Data.AffixList",
                     "sections.HeroCharacter.data.HeroJewels[3]", "heroMemory[2]"):
            with self.subTest(path=path):
                value = document()
                value["structuralGaps"][0]["path"] = path
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_catalog_collision_metadata_cannot_coexist_with_a_selected_same_id(self):
        value = document()
        value["omitted"][0]["nativeId"] = value["candidates"][0]["nativeId"]
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_the_same_native_id_cannot_carry_conflicting_global_catalog_facts(self):
        for section, field, invalid in (("definition", "id", "other-fictional-definition"),
                                        ("template", "text", "A conflicting catalog template"),
                                        ("catalogTier", "level", 17)):
            with self.subTest(section=section):
                value = document()
                clone = copy.deepcopy(value["candidates"][0])
                clone.update(alias="heroMemory[0].PrefixInfoList[2]",
                             path="sections.HeroCharacter.data.HeroJewels[0]._Raw_Data.AffixList.PrefixInfoList[2]")
                clone[section][field] = invalid
                value["candidates"].append(clone)
                value["accounting"].update(rows=3, candidates=2)
                with self.assertRaisesRegex(ValueError, "^Memory definitions contain an invalid source-bound diagnostic contract$"):
                    project(value, "a" * 64)

    def test_one_definition_can_have_distinct_instance_values_conditions_mirrors_and_helper_types(self):
        value = document()
        row = value["candidates"][0]
        row["definition"]["memoryType"] = "Any"
        row["memoryType"].update(catalog="Any", status="catalog_any")
        clone = copy.deepcopy(row)
        clone.update(alias="heroMemory[0].PrefixInfoList[2]",
                     path="sections.HeroCharacter.data.HeroJewels[0]._Raw_Data.AffixList.PrefixInfoList[2]")
        clone["ownValues"][0]["exact"] = "13.625"
        clone["serverMirror"].update(status="different", issue=None)
        clone["nativeConditions"]["Filter"] = "invalid"
        clone["memoryType"]["helper"] = "Progress"
        value["candidates"].append(clone)
        value["accounting"].update(rows=3, candidates=2)
        result = summary(project(value, "a" * 64))
        self.assertEqual([(row["own_values"][0]["exact"], row["server_mirror"]["status"],
                           row["native_conditions"]["filter"], row["memory_type"]["helper"])
                          for row in result["candidates"]],
                         [("7.312500", "same", "present", "Discipline"), ("13.625", "different", "invalid", "Progress")])

    def test_captured_accounting_cannot_hide_or_fabricate_rows(self):
        for field, invalid in (("rows", 3), ("candidates", 0), ("omitted", 0), ("structuralGaps", 0),
                               ("jewels", 2), ("emptySlots", True), ("reconciles", 1), ("reconciles", False)):
            with self.subTest(field=field):
                value = document()
                value["accounting"][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_absent_uncaptured_and_invalid_domains_keep_every_list_and_count_unknown(self):
        for status in ("absent", "not_captured", "invalid"):
            with self.subTest(status=status):
                value = document()
                value["domain"]["status"] = status
                value.update(candidates=None, omitted=None, structuralGaps=None)
                value["accounting"] = dict.fromkeys(value["accounting"])
                result = project(value, "a" * 64)
                self.assertEqual((result["candidates"], result["omitted"], result["structural_gaps"], list(result["accounting"].values())),
                                 (None, None, None, [None] * 7))

    def test_unknown_domain_is_not_an_empty_complete_domain(self):
        value = document()
        value["domain"]["status"] = "absent"
        with self.assertRaises(ValueError):
            project(value, "a" * 64)

    def test_an_explicitly_captured_empty_domain_keeps_observed_zero_counts(self):
        value = document()
        value.update(candidates=[], omitted=[], structuralGaps=[])
        value["accounting"] = {"jewels": 0, "rows": 0, "emptySlots": 0, "candidates": 0, "omitted": 0,
                               "structuralGaps": 0, "reconciles": True}
        self.assertEqual(project(value, "a" * 64)["accounting"],
                         {"jewels": 0, "rows": 0, "empty_slots": 0, "candidates": 0, "omitted": 0,
                          "structural_gaps": 0, "reconciles": True})

    def test_zero_jewels_cannot_claim_an_empty_affix_slot(self):
        value = document()
        value.update(candidates=[], omitted=[], structuralGaps=[])
        value["accounting"] = {"jewels": 0, "rows": 0, "emptySlots": 1, "candidates": 0, "omitted": 0,
                               "structuralGaps": 0, "reconciles": True}
        with self.assertRaisesRegex(ValueError, "^Memory definitions contain an invalid source-bound diagnostic contract$"):
            project(value, "a" * 64)

    def test_bounded_native_and_tier_upper_endpoints_remain_exact_integers(self):
        value = document()
        row = value["candidates"][0]
        row["nativeId"] = 10 ** 20 - 1
        row["definition"]["modifierId"] = str(10 ** 20 - 1)
        row["catalogTier"].update(tier=10 ** 18 - 1, level=10 ** 18 - 1)
        result = project(value, "a" * 64)["candidates"][0]
        self.assertEqual((result["native_id"], result["catalog_tier"]["tier"], result["catalog_tier"]["level"]),
                         (10 ** 20 - 1, 10 ** 18 - 1, 10 ** 18 - 1))

    def test_summary_revalidates_paths_count_claims_and_known_nested_types(self):
        for path, invalid in ((("candidates", 0, "server_mirror", "issue"), "mirror_row_invalid"),
                               (("candidates", 0, "catalog_tier", "range"), []),
                               (("candidates", 0, "own_values", 0, "index"), True),
                               (("omitted", 0, "native_id"), None), (("accounting", "rows"), 3),
                               (("source", "binding"), "authenticated")):
            with self.subTest(path=path):
                value = project(document(), "a" * 64)
                node = value
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = invalid
                with self.assertRaisesRegex(ValueError, "^Memory definitions contain an invalid source-bound diagnostic contract$"):
                    summary(value)

    def test_version_source_hash_and_all_verification_claims_are_fixed(self):
        for field, invalid in (("version", "0.1.0"), ("format", "tli-other-v1"), ("arithmeticReady", True),
                               ("runtimeVerified", 0), ("identityVerified", True), ("importComplete", True)):
            with self.subTest(field=field):
                value = document()
                value[field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)
        for digest in ("b" * 64, "A" * 64, None, [], "private payload"):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                project(document(), digest)

    def test_known_source_and_catalog_metadata_do_not_accept_unverified_replacements(self):
        for section, field, invalid in (("source", "binding", "authenticated"), ("catalog", "collisions", 8),
                                        ("catalog", "collisions", 0), ("catalog", "modifierIds", 1),
                                        ("catalog", "invalidEntries", -1), ("catalog", "invalidGroups", ["unknown"]),
                                        ("catalog", "invalidGroups", ["randomAffixes"]),
                                        ("catalog", "logicalPaths", ["hero-memory/master"])):
            with self.subTest(section=section, field=field):
                value = document()
                value[section][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_all_runtime_operator_rank_line_and_pool_roles_stay_unknown(self):
        for field, invalid in (("operator", "more"), ("activation", "active"), ("rankScaling", "confirmed"),
                               ("lineRoles", []), ("runtimePoolIdentity", "nativeId")):
            with self.subTest(field=field):
                value = document()
                value["candidates"][0][field] = invalid
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_summary_deeply_drops_unknown_properties_and_revalidates_derived_claims(self):
        expected = project(document(), "a" * 64)
        value = copy.deepcopy(expected)
        for row in (value, value["source"], value["catalog"], value["domain"], value["accounting"], value["candidates"][0],
                    value["candidates"][0]["definition"], value["candidates"][0]["catalog_tier"]["range"],
                    value["candidates"][0]["own_values"][0], value["candidates"][0]["native_conditions"], value["omitted"][0]):
            row["opaque"] = {"account": "PRIVATE-MEMORY-CANARY"}
        self.assertEqual(summary(value), expected)

    def test_projection_and_summary_results_are_detached_without_mutating_inputs(self):
        raw = document()
        original = copy.deepcopy(raw)
        canonical = project(raw, "a" * 64)
        detached = summary(canonical)
        detached["catalog"]["logical_paths"].append("private")
        detached["candidates"][0]["own_values"][0]["exact"] = "1"
        self.assertEqual((raw, canonical), (original, project(original, "a" * 64)))

    def test_preflight_refuses_cycles_reused_containers_invalid_utf8_and_unbounded_shapes(self):
        shared = []
        cycle = {}
        cycle["self"] = cycle
        depth = None
        for _ in range(33):
            depth = [depth]
        for invalid in (cycle, [shared, shared], "\udfff", [None] * 4097, [[None] * 4096 for _ in range(5)], depth,
                        float("inf"), float("nan"), {1: "private"}):
            with self.subTest(kind=type(invalid).__name__):
                value = document()
                value["opaque"] = invalid
                with self.assertRaisesRegex(ValueError, "^Memory definitions contain an invalid source-bound diagnostic contract$"):
                    project(value, "a" * 64)
