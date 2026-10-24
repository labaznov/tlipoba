import copy
import unittest

from damage_lab.traitranks import project


def document():
    path = "sections.HeroCharacter.data.HeroJewels[0]._Raw_Data"
    return {
        "format": "tli-trait-rank-candidates-v1", "source": {"sha256": "a" * 64},
        "ruleStatus": "rank_rule_unverified",
        "candidateRules": {"client_fixed": "C", "fixed_plus_enhance": "C + E"},
        "gaps": [], "assumptions": ["Synthetic mapping is unverified"],
        "memoriesWithoutSelectedTrait": [],
        "memories": [{"position": 0, "baseId": 9871,
                      "fields": {
                          "clientFixed": {"path": path + ".ReminiscenceFixedLevel", "status": "ok", "value": 3},
                          "fromEnhance": {"path": path + ".ReminiscenceFixedLevelFromEnhance", "status": "ok", "value": 0},
                          "serverFixed": {"path": path + ".ServerPlayerItem.ReminiscenceFixedLevel", "status": "ok", "value": 1},
                          "level": {"path": path + ".ReminiscenceLevel", "status": "ok", "value": 37}},
                      "fixedAffixContribution": 2,
                      "fixedAffixSource": path + ".ServerPlayerItem.BaseAffix",
                      "consistency": "consistent", "linkage": {"status": "index_match", "slot": 1}}],
        "traits": [{"traitId": "987001", "index": 0, "rank": None, "memoryPosition": None,
                    "status": "no_verified_source", "candidates": [], "candidatesAgree": None},
                   {"traitId": "987011", "index": 1, "rank": None, "memoryPosition": 0,
                    "status": "rank_rule_unverified", "candidatesAgree": True,
                    "candidates": [
                        {"rule": "client_fixed", "formula": "C", "inputs": [path + ".ReminiscenceFixedLevel"],
                         "value": 3, "status": "rank_rule_unverified"},
                        {"rule": "fixed_plus_enhance", "formula": "C + E",
                         "inputs": [path + ".ReminiscenceFixedLevel", path + ".ReminiscenceFixedLevelFromEnhance"],
                         "value": 3, "status": "rank_rule_unverified"}]}]}


class TraitRanksTest(unittest.TestCase):
    """Unverified trait candidates remain observations rather than selected ranks."""

    def test_equal_candidates_never_resolve_a_rank(self):
        self.assertEqual([row["rank"] for row in project(document(), "a" * 64)["traits"]], [None, None])

    def test_document_requires_the_exact_producer_contract(self):
        for field, value in (("format", "other"), ("ruleStatus", "verified"),
                             ("candidateRules", {"client_fixed": "C + 1", "fixed_plus_enhance": "C + E"})):
            with self.subTest(field=field):
                data = document()
                data[field] = value
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_source_hash_must_match_the_exact_package_snapshot(self):
        with self.assertRaises(ValueError):
            project(document(), "b" * 64)

    def test_unknown_properties_are_removed_at_every_depth(self):
        data = document()
        for row in (data, data["source"], data["traits"][1], data["traits"][1]["candidates"][0],
                    data["memories"][0], data["memories"][0]["fields"]["clientFixed"], data["memories"][0]["linkage"]):
            row["account"] = {"rawItemId": "private-canary"}
        self.assertNotIn("private-canary", str(project(data, "a" * 64)))

    def test_memory_counts_require_nonnegative_integers(self):
        for value in (True, 3.0, -1, "3"):
            with self.subTest(value=value):
                data = document()
                data["memories"][0]["fields"]["clientFixed"]["value"] = value
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_memory_paths_cannot_point_to_arbitrary_source_fields(self):
        data = document()
        data["memories"][0]["fields"]["level"]["path"] = "sections.Account.secret"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_memory_consistency_must_match_its_numeric_inputs(self):
        data = document()
        data["memories"][0]["consistency"] = "unchecked"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_a_selected_rank_is_rejected_even_when_candidates_agree(self):
        data = document()
        data["traits"][1]["rank"] = 3
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_candidate_arithmetic_cannot_add_the_fixed_affix_twice(self):
        data = document()
        data["traits"][1]["candidates"][0]["value"] = 5
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_candidate_formula_and_input_paths_are_exact(self):
        for key, value in (("rule", "choose_best"), ("formula", "C + F"), ("inputs", ["sections.Account.secret"])):
            with self.subTest(key=key):
                data = document()
                data["traits"][1]["candidates"][0][key] = value
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_candidate_status_cannot_hide_available_inputs(self):
        data = document()
        data["traits"][1]["candidates"][0]["status"] = "missing_input"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_candidate_agreement_must_match_the_values(self):
        data = document()
        data["traits"][1]["candidatesAgree"] = False
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_trait_status_must_match_its_candidate_statuses(self):
        data = document()
        data["traits"][1]["status"] = "no_usable_candidate"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_duplicate_memory_positions_cannot_overwrite_a_source(self):
        data = document()
        data["memories"].append(data["memories"][0])
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_duplicate_trait_ids_cannot_claim_two_slots(self):
        data = document()
        data["traits"][0]["traitId"] = data["traits"][1]["traitId"]
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_unclaimed_memory_slots_must_match_the_exported_links(self):
        data = document()
        data["memoriesWithoutSelectedTrait"] = [1]
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_duplicate_indexes_remain_explicit_unresolved_rows(self):
        data = document()
        for row in data["traits"]:
            row.update(index=1, status="duplicate_index", memoryPosition=None, candidates=[], candidatesAgree=None)
        self.assertEqual([row["status"] for row in project(data, "a" * 64)["traits"]], ["duplicate_index", "duplicate_index"])

    def test_an_invalid_index_remains_an_explicit_unresolved_row(self):
        data = document()
        data["traits"][1].update(index=None, status="invalid_index", memoryPosition=None, candidates=[], candidatesAgree=None)
        data["memoriesWithoutSelectedTrait"] = [1]
        self.assertEqual(project(data, "a" * 64)["traits"][1]["status"], "invalid_index")

    def test_missing_enhancement_is_not_replaced_with_zero(self):
        data = document()
        data["memories"][0]["fields"]["fromEnhance"].update(status="missing", value=None)
        data["traits"][1]["candidates"][1].update(status="missing_input", value=None)
        data["traits"][1]["candidatesAgree"] = None
        self.assertIsNone(project(data, "a" * 64)["traits"][1]["candidates"][1]["value"])

    def test_conflicting_fixed_inputs_keep_the_candidate_but_no_rank(self):
        data = document()
        data["memories"][0]["fields"]["serverFixed"]["value"] = 4
        data["memories"][0]["consistency"] = "conflict"
        data["traits"][1]["status"] = "input_conflict"
        for row in data["traits"][1]["candidates"]:
            row["status"] = "input_conflict"
        self.assertEqual(project(data, "a" * 64)["traits"][1]["candidates"][0]["value"], 3)

    def test_unknown_tier_tables_preserve_the_gap_without_choosing_a_rank(self):
        data = document()
        data["traits"][1]["status"] = "no_usable_candidate"
        for row in data["traits"][1]["candidates"]:
            row["status"] = "unknown_tier_table"
        self.assertIsNone(project(data, "a" * 64)["traits"][1]["rank"])

    def test_candidate_table_statuses_cannot_contradict_each_other(self):
        for status in ("unknown_tier_table", "out_of_range"):
            with self.subTest(status=status):
                data = document()
                data["traits"][1]["candidates"][1]["status"] = status
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_unverified_slot_link_does_not_expose_candidates(self):
        data = document()
        data["memories"][0]["linkage"] = {"status": "unverified", "reason": "no server memory overview"}
        data["traits"][1].update(status="slot_link_unverified", memoryPosition=None, candidates=[], candidatesAgree=None)
        self.assertEqual(project(data, "a" * 64)["traits"][1]["candidates"], [])

    def test_notes_cannot_contain_arbitrary_nested_objects(self):
        for key in ("gaps", "assumptions"):
            with self.subTest(key=key):
                data = document()
                data[key] = [{"account": "private-canary"}]
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_missing_required_fields_fail_with_contract_errors(self):
        for key in document():
            with self.subTest(key=key):
                data = document()
                del data[key]
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_projection_is_detached_from_the_source(self):
        data = document()
        original = copy.deepcopy(data)
        result = project(data, "a" * 64)
        result["memories"][0]["fields"]["level"]["value"] = 91
        result["traits"][1]["candidates"][0]["inputs"].append("synthetic")
        self.assertEqual(data, original)

    def test_enhancement_changes_only_its_named_candidate(self):
        data = document()
        data["memories"][0]["fields"]["fromEnhance"]["value"] = 2
        data["traits"][1]["candidates"][1]["value"] = 5
        data["traits"][1]["candidatesAgree"] = False
        self.assertEqual([row["value"] for row in project(data, "a" * 64)["traits"][1]["candidates"]], [3, 5])

    def test_invalid_client_input_preserves_an_unresolved_candidate(self):
        data = document()
        data["memories"][0]["fields"]["clientFixed"].update(status="invalid", value=None)
        data["memories"][0]["consistency"] = "unchecked"
        data["traits"][1].update(status="no_usable_candidate", candidatesAgree=None)
        for row in data["traits"][1]["candidates"]:
            row.update(value=None, status="invalid_input")
        self.assertEqual(project(data, "a" * 64)["traits"][1]["candidates"][0]["status"], "invalid_input")

    def test_boolean_counts_are_rejected_outside_memory_fields(self):
        for path in (("memories", 0, "position"), ("memories", 0, "baseId"),
                     ("memories", 0, "fixedAffixContribution"), ("memories", 0, "linkage", "slot"),
                     ("traits", 1, "index"), ("traits", 1, "memoryPosition"),
                     ("traits", 1, "candidates", 0, "value")):
            with self.subTest(path=path):
                data = document()
                row = data
                for key in path[:-1]:
                    row = row[key]
                row[path[-1]] = True
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_non_json_container_shapes_fail_with_contract_errors(self):
        for value in (None, True, [], "not an object"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    project(value, "a" * 64)

    def test_missing_sections_can_remain_an_explicit_empty_diagnostic(self):
        data = document()
        data.update(memories=[], traits=[], memoriesWithoutSelectedTrait=[], gaps=["Synthetic section unavailable"])
        self.assertEqual(project(data, "a" * 64)["gaps"], ["Synthetic section unavailable"])

    def test_empty_numeric_rank_outside_the_table_is_preserved_as_a_gap(self):
        data = document()
        for key in ("clientFixed", "serverFixed"):
            data["memories"][0]["fields"][key]["value"] = 0
        data["memories"][0]["fixedAffixContribution"] = 0
        data["traits"][1]["status"] = "no_usable_candidate"
        for row in data["traits"][1]["candidates"]:
            row.update(value=0, status="out_of_range")
        self.assertEqual(project(data, "a" * 64)["traits"][1]["candidates"][0]["value"], 0)
