import copy
import json
import unittest

from damage_lab.logtables import parse_event
from damage_lab.logbuild import candidates, project
from test_logtables import ELIDED, event, tables


def document(entries=None):
    """Return a synthetic saved reader snapshot without account or instance identifiers."""
    if entries is None:
        entries = [("bag", [("wearItems", [("1", [("PageId", "007"), ("Index", "2"),
                    ("Item", [("BaseId", "9001"), ("Prefix", [("1", [("Id", "800003"), ("DynArgs", [("1", "11.50")])])])])])])]),
                   ("heroCharacterv3OverView", [("pointOverView", [("activeId", [("1", "41")])])]),
                   ("skillLayout", [("slots", None)])]
    lines = event(entries)
    tree = parse_event(lines)
    return {"format": "tli-build-log-v1", "version": "0.1.2", "status": "diagnostic", "scope": "printed_tree_only",
            "import_complete": False, "identity": "unknown", "runtime": "unknown", "freshness": "unknown",
            "selected_skill": "unknown", "build_code": "unknown",
            "limits": {"max_source_bytes": 1 << 30, "max_lines": 20000000, "max_line_bytes": 512, "max_events": 512,
                       "max_event_lines": 20000, "max_event_bytes": 16 << 20, "max_retained_bytes": 32 << 20, "chunk_bytes": 1 << 16},
            "source": {"kind": "ordinary_log", "sha256": "a" * 64, "snapshotBytes": 17000, "bytesRead": 17000,
                       "lines": len(lines) + 8, "ignoredLines": 8, "oversizedLines": 0, "retainedEventBytes": 9000,
                       "incompleteFinalLine": None},
            "events": [{"start_line": 3, "end_line": len(lines) + 2, "boundary": "next_record",
                        "header_trailing_space": False, "tree": tree}], "rejected": []}


def skill_document(items, dressed):
    """Build a synthetic candidate with independently printed skill collections."""
    return document([("bag", [("wearItems", None), ("dressSkillItems", dressed)]),
                     ("heroCharacterv3OverView", None), ("skillLayout", None),
                     ("skills", [("skills", items)])])


class LogBuildTest(unittest.TestCase):
    """Project one printed player-state candidate without reconstructing a verified build."""

    def test_explicit_event_keeps_lexical_tokens_and_unprinted_conditions(self):
        result = project(document(), 0, "a" * 64)
        row = result["domains"]["equipment"]["rows"][0]
        self.assertEqual((row["alias"], row["fields"]["page_id"]["values"][0]["text"],
                          row["fields"]["prefix_args"]["values"][0]["text"], row["conditions"], result["import_complete"]),
                         ("equipment[0]", "007", "11.50", {"condition": "not_printed", "filter": "not_printed", "behavior": "not_printed"}, False))

    def test_printed_skill_levels_remain_distinct_lexical_fields(self):
        data = skill_document([("1", [("BaseId", "8153"), ("Level", "019"),
                                       ("SkillItemLevel", "6"), ("RareValue", "03")])], None)
        rows = project(data, 0, "a" * 64)["domains"]["skill_items"]["rows"]
        self.assertEqual([{field: [(value["text"], value["class"]) for value in result["values"]]
                           for field, result in row["fields"].items()} for row in rows],
                         [{"base_id": [("8153", "int")], "level": [("019", "text")],
                           "skill_item_level": [("6", "int")], "rarity": [("03", "text")]}])

    def test_dressed_skills_keep_slot_and_nested_lexical_fields(self):
        data = skill_document(None, [("1", [("PageId", "003"), ("Index", "02"),
            ("Item", [("BaseId", "8153"), ("Level", "019"), ("SkillItemLevel", "6"), ("RareValue", "4")])])])
        rows = project(data, 0, "a" * 64)["domains"]["dressed_skill_items"]["rows"]
        self.assertEqual([{field: [value["text"] for value in result["values"]]
                           for field, result in row["fields"].items()} for row in rows],
                         [{"page_id": ["003"], "index": ["02"], "base_id": ["8153"],
                           "level": ["019"], "skill_item_level": ["6"], "rarity": ["4"]}])

    def test_printed_layout_slot_keys_are_retained_as_lexical_fields(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", [("1", [("key", "3")]), ("2", [("key", "5")])])])])
        rows = project(data, 0, "a" * 64)["domains"]["skill_layout"]["rows"]
        self.assertEqual([{field: [(value["text"], value["class"]) for value in result["values"]]
                           for field, result in row["fields"].items()} for row in rows],
                         [{"slot_key": [("3", "int")]}, {"slot_key": [("5", "int")]}])

    def test_layout_keys_keep_raw_grammar_tokens_without_numeric_conversion(self):
        entries = [(str(index), [("key", token)])
                   for index, token in enumerate(("007", "-4", "2.50", "false", "slot word"), 1)]
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", entries)])])
        rows = project(data, 0, "a" * 64)["domains"]["skill_layout"]["rows"]
        self.assertEqual([(row["fields"]["slot_key"]["values"][0]["text"],
                           row["fields"]["slot_key"]["values"][0]["class"]) for row in rows],
                         [("007", "text"), ("-4", "int"), ("2.50", "float"), ("false", "bool"), ("slot word", "text")])

    def test_layout_projection_strips_skill_references_and_unapproved_fields(self):
        entries = [("1", [("key", "3"), ("Id", "LAYOUTCANARY"), ("Other", "LAYOUTCANARY"),
                          ("value", [("skillId", "LAYOUTCANARY"), ("Other", "LAYOUTCANARY")])])]
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", entries)])])
        self.assertNotIn("LAYOUTCANARY", json.dumps(project(data, 0, "a" * 64)))

    def test_a_layout_row_without_a_key_retains_an_explicit_missing_field(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", [("1", [("value", [("skillId", "LAYOUTCANARY")])])])])])
        self.assertEqual(project(data, 0, "a" * 64)["domains"]["skill_layout"]["rows"],
                         [{"alias": "skill_layout[0]", "path": ["skillLayout", "slots", "1"],
                           "fields": {"slot_key": {"status": "not_printed", "values": [],
                               "missing_paths": [["skillLayout", "slots", "1", "key"]],
                               "elided_paths": [], "empty_paths": []}}}])

    def test_layout_elision_retains_thirty_visible_keys_without_a_total(self):
        entries = [(str(index), [("key", str(index))]) for index in range(1, 31)] + [("31", ELIDED)]
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", entries)])])
        result = project(data, 0, "a" * 64)["domains"]["skill_layout"]
        self.assertEqual((result["status"], result["visible_entries"], result["total_entries"], len(result["rows"]),
                          result["rows"][0]["fields"]["slot_key"]["values"][0]["text"],
                          result["rows"][-1]["path"], result["rows"][-1]["fields"]["slot_key"]["values"][0]["text"],
                          result["gaps"]),
                         ("elided", 30, None, 30, "1", ["skillLayout", "slots", "30"], "30",
                          [{"path": ["skillLayout", "slots"], "reason": "subtree_elided"}]))

    def test_a_missing_layout_collection_does_not_fabricate_rows(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None), ("skillLayout", None)])
        result = project(data, 0, "a" * 64)["domains"]["skill_layout"]
        self.assertEqual((result["status"], result["rows"], result["gaps"]),
                         ("not_printed", [], [{"path": ["skillLayout", "slots"], "reason": "not_printed"}]))

    def test_an_empty_layout_collection_does_not_fabricate_rows(self):
        result = project(document(), 0, "a" * 64)["domains"]["skill_layout"]
        self.assertEqual((result["status"], result["visible_entries"], result["total_entries"], result["rows"], result["gaps"]),
                         ("complete", 0, None, [], [{"path": ["skillLayout", "slots"], "reason": "empty_container_type_unknown"}]))

    def test_a_wholly_elided_layout_collection_does_not_fabricate_rows(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", tables(30) + [("slots", ELIDED)])])
        result = project(data, 0, "a" * 64)["domains"]["skill_layout"]
        self.assertEqual((result["status"], result["rows"], result["total_entries"]), ("elided", [], None))

    def test_layout_slots_cannot_use_a_nonarray_container(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", [("wrong", [("key", "3")])])])])
        with self.assertRaises(ValueError):
            project(data, 0, "a" * 64)

    def test_layout_keys_do_not_promote_snapshot_identity_or_completeness(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", [("1", [("key", "3")])])])])
        result = project(data, 0, "a" * 64)
        self.assertEqual((result["format"], result["counts"]["domains"], result["scope"], result["import_complete"],
                          result["identity"], result["runtime"], result["freshness"], result["selected_skill"],
                          result["build_code"], result["domains"]["pact_roster"]["rows"], result["domains"]["stats"]["rows"]),
                         ("tli-log-build-domains-v1", 14, "printed_subtree_only", False,
                          "unknown", "unknown", "unknown", "unknown", "unknown", [], []))

    def test_skill_collections_strip_identifiers_and_unapproved_fields(self):
        fields = [("Id", "PRIVATECANARY"), ("key", "PRIVATECANARY"), ("Lock", "PRIVATECANARY"),
                  ("Exp", "PRIVATECANARY"), ("DropSource", "PRIVATECANARY"), ("Other", "PRIVATECANARY")]
        data = skill_document([("1", [("BaseId", "8153"), *fields])],
                              [("1", [("PageId", "3"), *fields, ("Item", [("BaseId", "8153"), *fields])])])
        self.assertNotIn("PRIVATECANARY", json.dumps(project(data, 0, "a" * 64)))

    def test_an_unprinted_skill_field_keeps_its_missing_path(self):
        data = skill_document([("1", [("Level", "019"), ("Other", "ignored")])], None)
        self.assertEqual(project(data, 0, "a" * 64)["domains"]["skill_items"]["rows"][0]["fields"]["skill_item_level"],
                         {"status": "not_printed", "values": [], "missing_paths": [["skills", "skills", "1", "SkillItemLevel"]],
                          "elided_paths": [], "empty_paths": []})

    def test_an_empty_printed_skill_field_does_not_become_a_number(self):
        data = skill_document([("1", [("SkillItemLevel", None)])], None)
        self.assertEqual(project(data, 0, "a" * 64)["domains"]["skill_items"]["rows"][0]["fields"]["skill_item_level"],
                         {"status": "complete", "values": [], "missing_paths": [], "elided_paths": [],
                          "empty_paths": [["skills", "skills", "1", "SkillItemLevel"]]})

    def test_skill_collections_do_not_fill_each_others_missing_levels(self):
        data = skill_document([("1", [("BaseId", "8153"), ("Level", "019")])],
                              [("1", [("Item", [("BaseId", "8153"), ("SkillItemLevel", "6")])])])
        result = project(data, 0, "a" * 64)["domains"]
        self.assertEqual((result["skill_items"]["rows"][0]["fields"]["skill_item_level"]["status"],
                          result["dressed_skill_items"]["rows"][0]["fields"]["level"]["status"]),
                         ("not_printed", "not_printed"))

    def test_skill_item_elision_retains_thirty_visible_rows_without_a_total(self):
        entries = [(str(index), [("Level", str(index))]) for index in range(1, 31)] + [("31", ELIDED)]
        result = project(skill_document(entries, None), 0, "a" * 64)["domains"]["skill_items"]
        self.assertEqual((result["status"], result["visible_entries"], result["total_entries"], len(result["rows"]),
                          result["rows"][0]["fields"]["level"]["values"][0]["text"],
                          result["rows"][-1]["path"], result["rows"][-1]["fields"]["level"]["values"][0]["text"],
                          result["gaps"]),
                         ("elided", 30, None, 30, "1", ["skills", "skills", "30"], "30",
                          [{"path": ["skills", "skills"], "reason": "subtree_elided"}]))

    def test_dressed_skill_elision_retains_thirty_visible_rows_without_a_total(self):
        entries = [(str(index), [("Item", [("Level", str(index))])]) for index in range(1, 31)] + [("31", ELIDED)]
        result = project(skill_document(None, entries), 0, "a" * 64)["domains"]["dressed_skill_items"]
        self.assertEqual((result["status"], result["visible_entries"], result["total_entries"], len(result["rows"]),
                          result["rows"][0]["fields"]["level"]["values"][0]["text"],
                          result["rows"][-1]["path"], result["rows"][-1]["fields"]["level"]["values"][0]["text"],
                          result["gaps"]),
                         ("elided", 30, None, 30, "1", ["bag", "dressSkillItems", "30"], "30",
                          [{"path": ["bag", "dressSkillItems"], "reason": "subtree_elided"}]))

    def test_missing_skill_collections_do_not_fabricate_rows(self):
        result = project(document(), 0, "a" * 64)["domains"]
        self.assertEqual([(result[name]["status"], result[name]["rows"])
                          for name in ("skill_items", "dressed_skill_items")],
                         [("not_printed", []), ("not_printed", [])])

    def test_empty_skill_collections_do_not_fabricate_rows(self):
        result = project(skill_document(None, None), 0, "a" * 64)["domains"]
        self.assertEqual([(result[name]["status"], result[name]["rows"], result[name]["gaps"][0]["reason"])
                          for name in ("skill_items", "dressed_skill_items")],
                         [("complete", [], "empty_container_type_unknown"), ("complete", [], "empty_container_type_unknown")])

    def test_wholly_elided_skill_collections_do_not_fabricate_rows(self):
        entries = [("bag", [("wearItems", None)] + tables(29) + [("dressSkillItems", ELIDED)]),
                   ("skills", tables(30) + [("skills", ELIDED)]),
                   ("heroCharacterv3OverView", None), ("skillLayout", None)]
        result = project(document(entries), 0, "a" * 64)["domains"]
        self.assertEqual([(result[name]["status"], result[name]["rows"])
                          for name in ("skill_items", "dressed_skill_items")], [("elided", []), ("elided", [])])

    def test_skill_items_cannot_use_a_nonarray_container(self):
        with self.assertRaises(ValueError):
            project(skill_document([("wrong", [("Level", "019")])], None), 0, "a" * 64)

    def test_dressed_skill_items_cannot_use_a_nonarray_container(self):
        with self.assertRaises(ValueError):
            project(skill_document(None, [("wrong", [("Item", [("Level", "019")])])]), 0, "a" * 64)

    def test_skill_facts_do_not_promote_the_snapshot_or_change_diagnostic_domains(self):
        result = project(skill_document([("1", [("Level", "019")])], None), 0, "a" * 64)
        self.assertEqual((result["format"], result["counts"]["domains"], result["scope"], result["import_complete"],
                          result["identity"], result["runtime"], result["freshness"], result["selected_skill"],
                          result["build_code"], result["domains"]["skill_layout"]["rows"], result["domains"]["stats"]["rows"]),
                         ("tli-log-build-domains-v1", 14, "printed_subtree_only", False,
                          "unknown", "unknown", "unknown", "unknown", "unknown", [], []))

    def test_envelope_source_index_and_candidate_context_are_validated(self):
        for field, value in (("format", "other"), ("version", "0.1.1"), ("scope", "whole_build"),
                             ("import_complete", 0), ("identity", "verified"), ("runtime", "verified"),
                             ("selected_skill", "chosen"), ("freshness", "current"), ("build_code", "CANARY")):
            data = document()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, 0, "a" * 64)
        for index in (True, -1, 1, "0", None):
            with self.subTest(index=index), self.assertRaises(ValueError):
                project(document(), index, "a" * 64)
        for digest in ("b" * 64, "A" * 64, None):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                project(document(), 0, digest)
        with self.assertRaises(ValueError):
            project(document([("prices", [("1", "9.0")])]), 0, "a" * 64)

    def test_tree_metadata_counts_lexical_classes_and_shapes_are_strict(self):
        cases = (("format", "other"), ("version", "0.1.0"), ("status", "complete_build"), ("root", None),
                 ("header", {"logTimeText": "CANARY", "frame": 1, "timezone": "unknown"}))
        for field, value in cases:
            data = document()
            data["events"][0]["tree"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, 0, "a" * 64)
        for field, value in (("nodes", 1), ("leaves", True), ("maxDepth", 100), ("elisions", 1)):
            data = document()
            data["events"][0]["tree"]["counts"][field] = value
            with self.subTest(count=field), self.assertRaises(ValueError):
                project(data, 0, "a" * 64)

    def test_root_elision_does_not_poison_complete_children_or_invent_tail_rows(self):
        entries = [("bag", [("wearItems", [("1", [("Item", [("BaseId", "9001")])])])]),
                   ("heroCharacterv3OverView", [("pointOverView", [("activeId", [("1", "41")])])]),
                   ("skillLayout", [("slots", tables(30) + [("31", ELIDED)])])]
        entries += [("other" + str(index), [("v", "1")]) for index in range(27)] + [("tail", ELIDED)]
        result = project(document(entries), 0, "a" * 64)
        self.assertEqual((result["domains"]["equipment"]["status"], result["domains"]["skill_layout"]["status"],
                          result["domains"]["skill_layout"]["visible_entries"], len(result["domains"]["skill_layout"]["rows"]),
                          result["domains"]["stats"]["status"]), ("complete", "elided", 30, 30, "not_printed"))

    def test_candidates_only_enumerate_structural_matches_without_selection_or_merging(self):
        data = document([("prices", [("1", "9.0")])])
        chosen = document()["events"][0]
        chosen["start_line"] = data["events"][0]["end_line"] + 2
        chosen["end_line"] = chosen["start_line"] + chosen["tree"]["counts"]["lines"]
        data["source"]["lines"] = chosen["end_line"] + 1
        data["events"].append(chosen)
        self.assertEqual(candidates(data, "a" * 64), [1])

    def test_an_entire_supported_domain_can_be_elided_without_fabricated_rows(self):
        overview = [("other" + str(index), [("v", "1")]) for index in range(30)] + [("reminiscence", ELIDED)]
        entries = [("bag", [("wearItems", None)]), ("heroCharacterv3OverView", [("reminiscenceOverView", overview)]),
                   ("skillLayout", [("slots", None)])]
        result = project(document(entries), 0, "a" * 64)
        self.assertEqual((result["domains"]["memories"]["status"], result["domains"]["memories"]["rows"]), ("elided", []))

    def test_all_six_composition_domains_keep_only_narrow_lexical_fields(self):
        entries = [("bag", [("wearItems", [("1", [("Item", [("BaseId", "9001"), ("Id", "PRIVATECANARY")])])]),
                            ("dressingTalentBlocks", [("1", [("Item", [("BaseTalentList", [("1", "1001")]), ("Id", "PRIVATECANARY")])])])]),
                   ("heroCharacterv3OverView", [("reminiscenceOverView", [("reminiscence", [("1", [("index", "2"),
                       ("detail", [("ReminiscenceFixedLevel", "7"), ("ReminiscenceFixedLevelFromEnhance", "2"), ("Id", "PRIVATECANARY")])])])]),
                       ("pointOverView", [("activeId", [("1", "41")])])]),
                   ("talentBlockInfluence", [("1", [("key", "PRIVATECANARY"), ("value", [("EffectTalentIds", [("1", "1001")])])])]),
                   ("ContractInfosV2", [("ContractDatas", [("1", [("areaId", "4"), ("servantId", "77")])])]),
                   ("player", [("Name", "PRIVATECANARY"), ("PlayerId", "PRIVATECANARY")]),
                   ("skillLayout", [("slots", None)])]
        result = project(document(entries), 0, "a" * 64)
        self.assertEqual((result["counts"]["rows"], "PRIVATECANARY" in json.dumps(result),
                          result["domains"]["slates"]["rows"][0]["fields"]["direction"]["status"]), (6, False, "not_printed"))

    def test_printed_conditions_remain_unmapped_instead_of_becoming_empty_lists(self):
        data = document([("bag", [("wearItems", [("1", [("Item", [("Prefix", [("1", [("Condition", None)])])])])])]),
                         ("heroCharacterv3OverView", None), ("skillLayout", None)])
        self.assertEqual(project(data, 0, "a" * 64)["domains"]["equipment"]["rows"][0]["conditions"]["condition"], "printed_unmapped")

    def test_source_limits_context_and_declared_counts_reject_invalid_types(self):
        for field, value in (("snapshotBytes", 1 << 31), ("bytesRead", 5), ("lines", True),
                             ("retainedEventBytes", 33 << 20), ("kind", "network")):
            data = document()
            data["source"][field] = value
            with self.subTest(source=field), self.assertRaises(ValueError):
                project(data, 0, "a" * 64)
        for field, value in (("start_line", 0), ("end_line", 999999), ("boundary", "verified"), ("header_trailing_space", 0)):
            data = document()
            data["events"][0][field] = value
            with self.subTest(event=field), self.assertRaises(ValueError):
                project(data, 0, "a" * 64)
        data = document()
        data["limits"]["max_events"] = True
        with self.assertRaises(ValueError):
            candidates(data, "a" * 64)

    def test_unrecognized_array_shapes_do_not_become_guessed_lists(self):
        data = document([("bag", [("wearItems", [("wrong", [("Item", [("BaseId", "9001")])])])]),
                         ("heroCharacterv3OverView", None), ("skillLayout", None)])
        with self.assertRaises(ValueError):
            project(data, 0, "a" * 64)

    def test_projection_strips_unknown_metadata_and_is_detached(self):
        data = document()
        data["source"]["path"] = "C:/PRIVATECANARY.log"
        data["events"][0]["tree"]["header"]["playerId"] = "PRIVATECANARY"
        before = copy.deepcopy(data)
        first = project(data, 0, "a" * 64)
        second = project(data, 0, "a" * 64)
        first["domains"]["equipment"]["rows"][0]["fields"]["base_id"]["values"][0]["path"].clear()
        self.assertEqual((data, "PRIVATECANARY" in json.dumps(second), bool(second["domains"]["equipment"]["rows"][0]["path"])),
                         (before, False, True))

    def test_an_empty_snapshot_has_no_candidates_and_no_implicit_selection(self):
        data = document()
        data["events"] = []
        data["source"]["retainedEventBytes"] = 0
        self.assertEqual(candidates(data, "a" * 64), [])

    def test_snapshot_boundary_remains_an_explicit_transport_limit(self):
        data = document()
        data["events"][0]["boundary"] = "snapshot_boundary"
        data["source"]["lines"] = data["events"][0]["end_line"]
        result = project(data, 0, "a" * 64)
        self.assertEqual((result["event"]["boundary"], result["identity"], result["freshness"]), ("snapshot_boundary", "unknown", "unknown"))

    def test_a_known_collection_cannot_be_a_scalar_diagnostic(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", "not-a-collection")])])
        with self.assertRaises(ValueError):
            project(data, 0, "a" * 64)

    def test_retained_byte_claims_cannot_exceed_the_source_or_event_budget(self):
        for field, value in (("snapshotBytes", 2), ("retainedEventBytes", 18000)):
            data = document()
            data["source"][field] = value
            if field == "snapshotBytes":
                data["source"]["bytesRead"] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, 0, "a" * 64)
        data = document()
        data["limits"]["max_event_bytes"] = 100
        with self.assertRaises(ValueError):
            project(data, 0, "a" * 64)

    def test_two_candidates_are_projected_independently_by_explicit_index(self):
        data = document()
        second = document([("bag", [("wearItems", [("1", [("Item", [("BaseId", "9002")])])])]),
                           ("heroCharacterv3OverView", None), ("skillLayout", None)])["events"][0]
        second["start_line"] = data["events"][0]["end_line"] + 2
        second["end_line"] = second["start_line"] + second["tree"]["counts"]["lines"]
        data["events"].append(second)
        data["source"]["lines"] = second["end_line"] + 1
        self.assertEqual((candidates(data, "a" * 64), project(data, 1, "a" * 64)["domains"]["equipment"]["rows"][0]
                          ["fields"]["base_id"]["values"][0]["text"]), ([0, 1], "9002"))

    def test_malformed_containers_and_error_messages_never_echo_private_payloads(self):
        for field, value in (("source", None), ("events", {}), ("limits", []), ("rejected", False)):
            data = document()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError) as caught:
                project(data, 0, "a" * 64)
            self.assertEqual(str(caught.exception), "Log build projection requires a supported bounded saved-tree contract")


if __name__ == "__main__":
    unittest.main()
