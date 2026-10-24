import copy
import hashlib
import json
import unittest

from damage_lab import logbuild
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


def memory_document(fields):
    """Keep synthetic memory catalog and affix fields in their printed detail object."""
    return document([("bag", [("wearItems", None)]), ("skillLayout", None),
                     ("heroCharacterv3OverView", [("reminiscenceOverView", [("reminiscence", [
                         ("1", [("detail", fields)])])])])])


def empty_affixes():
    """Describe every newly admitted unprinted skill-affix field independently of production maps."""
    return {family + "_" + field: [] for family in ("base_affix", "prefix", "suffix", "slot", "enchant", "chip")
            for field in ("id", "version", "source", "args")}


def reference_document(items, slots):
    """Keep synthetic item tokens and layout references within one printed candidate."""
    return document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                     ("skillLayout", [("slots", slots)]), ("skills", [("skills", items)])])


def partial_document():
    """Render the measured thirty-table root elision with fictional visible domains."""
    entries = [("heroCharacterv3OverView", [("pointOverView", [("activeId", [("1", "41")])])]),
               ("skillLayout", [("slots", [("1", [("key", "101"), ("value", [("skillId", "token77")])])])]),
               ("player", [("synthetic", "1")]),
               ("skills", [("skills", [("1", [("Id", "token77"), ("BaseId", "9001")])])]),
               ("geniusInfos", [("synthetic", "1")])]
    return document(entries + [("filler" + str(index), [("n", "1")]) for index in range(25)] + [("bag", ELIDED)])


def refusals(data):
    """Capture both public seams fixed refusals without inspecting private validation helpers."""
    results = []
    for operation in (project, logbuild.skill_references):
        try:
            operation(data, 0, "a" * 64)
        except ValueError as error:
            results.append(str(error))
        else:
            results.append(None)
    return results


class LogBuildTest(unittest.TestCase):
    """Project one printed player-state candidate without reconstructing a verified build."""

    def test_bag_elided_character_shape_is_separate_from_full_candidates(self):
        data = partial_document()
        self.assertEqual((candidates(data, "a" * 64), logbuild.partial_candidates(data, "a" * 64)), ([], [0]))

    def test_partial_projection_preserves_unknown_gear_and_visible_traits(self):
        result = logbuild.project_partial(partial_document(), 0, "a" * 64)
        equipment = result["domains"]["equipment"]
        self.assertEqual((result["format"], result["structure"], equipment["status"], equipment["visible_entries"],
                          equipment["rows"], [value["text"] for value in
                              result["domains"]["traits"]["rows"][0]["fields"]["trait_id"]["values"]]),
                         ("tli-log-partial-build-domains-v1",
                          {"kind": "bag_elided_character_shape", "unavailable_paths": [["bag", "wearItems"]]},
                          "not_printed", None, [], ["41"]))

    def test_partial_skill_references_and_coordinates_do_not_promote_activation(self):
        data = partial_document()
        references = logbuild.partial_skill_references(data, 0, "a" * 64)
        graph = logbuild.partial_installation_graph(data, 0, "a" * 64)
        self.assertEqual((references["references"][0]["status"], graph["slots"][0]["tab_candidate"],
                          graph["slots"][0]["position_candidate"], graph["activation"], graph["effective_level"]),
                         ("observed_token_match", 1, 2, "unknown", "unknown"))

    def test_partial_mode_never_weakens_full_selection_or_projects_full_shapes(self):
        for operation in (project, logbuild.skill_references, logbuild.installation_graph):
            with self.subTest(operation=operation.__name__), self.assertRaises(ValueError):
                operation(partial_document(), 0, "a" * 64)
        data = document()
        self.assertEqual(logbuild.partial_candidates(data, "a" * 64), [])
        for operation in (logbuild.project_partial, logbuild.partial_skill_references,
                          logbuild.partial_installation_graph):
            with self.subTest(operation=operation.__name__), self.assertRaises(ValueError):
                operation(data, 0, "a" * 64)

    def test_partial_fingerprint_requires_all_five_nonempty_tables_and_elided_bag(self):
        for name in ("heroCharacterv3OverView", "skillLayout", "player", "skills", "geniusInfos"):
            for replacement in (None, "17"):
                data = partial_document()
                entries = data["events"][0]["tree"]["root"]["entries"]
                next(row for row in entries if row[0] == name)[1] = (
                    {"t": "empty"} if replacement is None else {"t": "scalar", "class": "int", "text": "17"})
                with self.subTest(name=name, replacement=replacement), self.assertRaises(ValueError):
                    logbuild.project_partial(data, 0, "a" * 64)

    def test_partial_seams_revalidate_grammar_source_and_index(self):
        malformed = partial_document()
        malformed["events"][0]["tree"]["elisions"][0]["printedTableEntries"] = 29
        for operation in (logbuild.project_partial, logbuild.partial_skill_references,
                          logbuild.partial_installation_graph):
            for data, index, digest in ((malformed, 0, "a" * 64), (partial_document(), 1, "a" * 64),
                                       (partial_document(), 0, "b" * 64)):
                with self.subTest(operation=operation.__name__, index=index, digest=digest), self.assertRaises(ValueError):
                    operation(data, index, digest)
        with self.assertRaises(ValueError):
            logbuild.partial_candidates(malformed, "a" * 64)

    def test_valid_unrelated_fingerprint_is_not_a_partial_character(self):
        data = partial_document()
        next(row for row in data["events"][0]["tree"]["root"]["entries"] if row[0] == "player")[0] = "other"
        self.assertEqual(logbuild.partial_candidates(data, "a" * 64), [])
        with self.assertRaises(ValueError):
            logbuild.project_partial(data, 0, "a" * 64)

    def test_multiple_partial_events_keep_separate_source_coordinates(self):
        data = partial_document()
        second = copy.deepcopy(data["events"][0])
        second["start_line"] += second["end_line"] + 3
        second["end_line"] += data["events"][0]["end_line"] + 3
        data["events"].append(second)
        data["source"]["lines"] = second["end_line"] + 8
        indexes = logbuild.partial_candidates(data, "a" * 64)
        projections = [logbuild.project_partial(data, index, "a" * 64) for index in indexes]
        self.assertEqual((indexes, [row["event"]["index"] for row in projections],
                          projections[0]["event"]["start_line"] != projections[1]["event"]["start_line"],
                          [row["identity"] for row in projections]), ([0, 1], [0, 1], True, ["unknown", "unknown"]))

    def test_installation_key_zero_does_not_turn_a_reference_sentinel_into_an_installed_item(self):
        data = reference_document([("1", [("Id", "0")])], [("1", [("key", "0"), ("value", [("skillId", "0")])])])
        row = logbuild.installation_graph(data, 0, "a" * 64)["slots"][0]
        self.assertEqual((row["tab_candidate"], row["position_candidate"], row["reference_status"], row["skill_items_alias"]),
                         (0, 1, "sentinel_observed", None))

    def test_installation_graph_keeps_thirty_visible_slots_without_inventing_the_elided_tail(self):
        data = reference_document(None, [(str(index + 1), [("key", str(100 + index))]) for index in range(30)] + [("31", ELIDED)])
        graph = logbuild.installation_graph(data, 0, "a" * 64)
        self.assertEqual((len(graph["slots"]), graph["slots"][-1]["layout_alias"], graph["skill_references"]["layout_side"]["status"],
                          graph["inventory_completeness"]), (30, "skill_layout[29]", "elided", "unknown"))

    def test_installation_graph_does_not_mutate_or_disclose_private_instance_tokens(self):
        data = reference_document([("1", [("Id", "PRIVATE-ITEM-INSTANCE-CANARY")])], [("1", [
            ("key", "103"), ("value", [("skillId", "PRIVATE-ITEM-INSTANCE-CANARY"), ("status", "PRIVATE-STATUS-CANARY")])])])
        saved = copy.deepcopy(data)
        packet = json.dumps(logbuild.installation_graph(data, 0, "a" * 64), sort_keys=True)
        self.assertEqual((data, "PRIVATE-ITEM-INSTANCE-CANARY" in packet, "PRIVATE-STATUS-CANARY" in packet), (saved, False, False))

    def test_installation_graph_preserves_public_refusals_for_malformed_and_oversized_keys(self):
        duplicate = reference_document(None, [("1", [("key", "17"), ("other", "18")])])
        duplicate["events"][0]["tree"]["root"]["entries"][2][1]["entries"][0][1]["entries"][0][1]["entries"][1][0] = "key"
        oversized = reference_document(None, [("1", [("key", "17")])])
        oversized["events"][0]["tree"]["root"]["entries"][2][1]["entries"][0][1]["entries"][0][1]["entries"][0][1]["text"] = "9" * 5000
        results = []
        for data in (reference_document(None, [("1", [("key", [("v", "17")])])]),
                     duplicate,
                     oversized):
            for operation in (project, logbuild.skill_references, logbuild.installation_graph):
                try:
                    operation(data, 0, "a" * 64)
                except ValueError as error:
                    results.append(str(error))
                else:
                    results.append(None)
        self.assertEqual(results, ["Log build projection requires a supported bounded saved-tree contract"] * 9)

    def test_installation_coordinates_require_the_current_slot_key_allowlist(self):
        data = reference_document(None, [("1", [("key", "101")])])
        domain = logbuild.DOMAINS["skill_layout"]
        try:
            logbuild.DOMAINS["skill_layout"] = ("skillLayout.slots", {})
            result = logbuild.installation_graph(data, 0, "a" * 64)
        finally:
            logbuild.DOMAINS["skill_layout"] = domain
        self.assertEqual((result["slots"][0]["slot_key_status"], result["slots"][0]["tab_candidate"], result["tabs"]),
                         ("key_not_allowlisted", None, []))

    def test_installation_graph_accepts_an_opaque_layout_policy_without_reading_keys(self):
        data = reference_document(None, [("1", [("key", "101")])])
        domain = logbuild.DOMAINS["skill_layout"]
        try:
            logbuild.DOMAINS["skill_layout"] = ("skillLayout.slots", None)
            result = logbuild.installation_graph(data, 0, "a" * 64)
        finally:
            logbuild.DOMAINS["skill_layout"] = domain
        self.assertEqual((result["slots"], result["tabs"]), ([], []))

    def test_installation_coordinates_do_not_apply_to_a_different_allowlisted_path(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("other", [("1", [("key", "102")])])])])
        domain = logbuild.DOMAINS["skill_layout"]
        try:
            logbuild.DOMAINS["skill_layout"] = ("skillLayout.other", {"slot_key": "key"})
            result = logbuild.installation_graph(data, 0, "a" * 64)
        finally:
            logbuild.DOMAINS["skill_layout"] = domain
        self.assertEqual(result["slots"][0]["slot_key_status"], "key_not_allowlisted")

    def test_installation_graph_does_not_promote_source_candidates_into_a_verified_build(self):
        graph = logbuild.installation_graph(reference_document(None, [("1", [("key", "101")])]), 0, "a" * 64)
        self.assertEqual((graph["format"], graph["scope"], graph["import_complete"],
                          [graph[key] for key in ("identity", "runtime", "freshness", "selected_skill", "build_code",
                              "installation", "activation", "effective_level", "inventory_completeness", "raw_binding")],
                          graph["source"], graph["event"], graph["derivation"]), (
            "tli-log-installation-candidates-v1", "conditional_saved_helper_coordinates", False, ["unknown"] * 10,
            graph["skill_references"]["source"], graph["skill_references"]["event"], {
                "helper": "SkillConstantMgr.CalSkillTabIndex", "input_domain": "canonical_int32_lexeme",
                "captured_initial_values": [100, 1000, 6], "constants_unchanged": "assumed",
                "operand_conventions": "inspected_static_listing", "runtime_binding": "unverified",
                "record_identity": "same_argument_on_successful_InitSkillSlotItemData_return",
                "snapshot_unchanged_during_call": "required", "ui_role": "unknown"}))

    def test_installation_graph_retains_the_unchanged_reference_trace_and_peer_ambiguity(self):
        data = reference_document([("1", [("Id", "private-peer")]), ("2", [("Id", "private-peer")])],
                                  [("1", [("key", "101"), ("value", [("skillId", "private-peer")])])])
        graph = logbuild.installation_graph(data, 0, "a" * 64)
        self.assertEqual((graph["skill_references"], graph["slots"][0]),
                         (logbuild.skill_references(data, 0, "a" * 64), {
                             "layout_alias": "skill_layout[0]", "slot_key_status": "coordinated",
                             "tab_candidate": 1, "position_candidate": 2,
                             "reference_status": "ambiguous_visible_duplicates", "reference_detail": "scalar",
                             "skill_items_alias": None, "visible_match_count": 2, "uniqueness": None}))

    def test_installation_graph_keeps_every_alias_in_coordinate_collisions(self):
        data = reference_document(None, [(str(index + 1), [("key", key)])
                                         for index, key in enumerate(("1001", "6", "205", "1", "100"))])
        self.assertEqual(logbuild.installation_graph(data, 0, "a" * 64)["tabs"], [
            {"tab_candidate": 1, "slots": ["skill_layout[3]", "skill_layout[4]"], "collisions": [
                {"position_candidate": 1, "aliases": ["skill_layout[3]", "skill_layout[4]"], "winner": "unknown"}]},
            {"tab_candidate": 2, "slots": ["skill_layout[2]"], "collisions": []},
            {"tab_candidate": 6, "slots": ["skill_layout[0]", "skill_layout[1]"], "collisions": [
                {"position_candidate": 1, "aliases": ["skill_layout[0]", "skill_layout[1]"], "winner": "unknown"}]}])

    def test_installation_graph_accepts_unprinted_and_empty_slot_collections(self):
        entries = [("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None), ("skillLayout", tables(30) + [("31", ELIDED)])]
        self.assertEqual([logbuild.installation_graph(data, 0, "a" * 64)["slots"]
                          for data in (document(), reference_document(None, None), document(entries))], [[], [], []])

    def test_installation_coordinates_do_not_guess_a_key_hidden_by_the_printer(self):
        data = reference_document(None, [("1", tables(30) + [("31", ELIDED)])])
        self.assertEqual(logbuild.installation_graph(data, 0, "a" * 64)["slots"][0]["slot_key_status"],
                         "key_hidden_by_elision")

    def test_installation_coordinates_keep_an_explicitly_elided_key_unavailable(self):
        data = reference_document(None, [("1", tables(30) + [("key", ELIDED)])])
        self.assertEqual(logbuild.installation_graph(data, 0, "a" * 64)["slots"][0]["slot_key_status"], "key_elided")

    def test_installation_coordinates_follow_the_saved_helper_across_int32_boundaries(self):
        keys = ("-2147483648", "-1", "-0", "3", "99", "100", "205", "999", "1000", "1001", "1006", "1007", "2147483647")
        data = reference_document(None, [(str(index + 1), [("key", key)]) for index, key in enumerate(keys)])
        self.assertEqual([(row["tab_candidate"], row["position_candidate"])
                          for row in logbuild.installation_graph(data, 0, "a" * 64)["slots"]],
                         [(-2147483648, 1), (-1, 1), (0, 1), (3, 1), (99, 1), (1, 1), (2, 6), (9, 100),
                          (5, 6), (6, 1), (6, 6), (7, 1), (357913780, 3)])

    def test_installation_coordinates_keep_non_integer_and_outside_keys_unavailable(self):
        keys = ("1.0", "true", "false", "001", "not-a-position", "2147483648", "-2147483649", "100000000001", "9" * 300)
        data = reference_document(None, [(str(index + 1), [("key", key)]) for index, key in enumerate(keys)])
        self.assertEqual([(row["slot_key_status"], row["tab_candidate"], row["position_candidate"])
                          for row in logbuild.installation_graph(data, 0, "a" * 64)["slots"]],
                         [("key_not_integer", None, None)] * 5 + [("key_outside_domain", None, None)] * 4)

    def test_installation_coordinates_distinguish_missing_and_printed_empty_keys(self):
        data = reference_document(None, [("1", [("value", [("skillId", "0")])]), ("2", [("key", None)]), ("3", None)])
        self.assertEqual([(row["slot_key_status"], row["tab_candidate"], row["position_candidate"])
                          for row in logbuild.installation_graph(data, 0, "a" * 64)["slots"]],
                         [("key_not_printed", None, None), ("key_printed_empty", None, None), ("key_printed_empty", None, None)])

    def test_corrected_memory_alias_semantics_use_the_second_projection_format(self):
        self.assertEqual(project(memory_document([("BaseId", "9767")]), 0, "a" * 64)["format"],
                         "tli-log-build-domains-v2")

    def test_memories_keep_the_catalog_id_when_the_base_affix_has_a_different_id(self):
        data = memory_document([("BaseId", "9727"), ("BaseAffix", [("1", [("Id", "870047")])])])
        fields = project(data, 0, "a" * 64)["domains"]["memories"]["rows"][0]["fields"]
        self.assertEqual(fields["base_id"]["values"], [{
            "path": ["heroCharacterv3OverView", "reminiscenceOverView", "reminiscence", "1", "detail", "BaseId"],
            "text": "9727", "class": "int"}])

    def test_memories_keep_all_base_affix_tokens_under_separate_names(self):
        data = memory_document([("BaseId", "9733"), ("BaseAffix", [("1", [("Id", "870053"),
            ("Version", "007"), ("source", "002"), ("DynArgs", [("1", "-0.750")])])])])
        fields = project(data, 0, "a" * 64)["domains"]["memories"]["rows"][0]["fields"]
        self.assertEqual(([(name, [(row["text"], row["path"][-3:]) for row in fields[name]["values"]])
                           for name in ("base_affix_id", "base_affix_version", "base_affix_source", "base_affix_args")],
                          set(fields) & {"base_version", "base_source", "base_args"}),
                         ([("base_affix_id", [("870053", ["BaseAffix", "1", "Id"])]),
                           ("base_affix_version", [("007", ["BaseAffix", "1", "Version"])]),
                           ("base_affix_source", [("002", ["BaseAffix", "1", "source"])]),
                           ("base_affix_args", [("-0.750", ["1", "DynArgs", "1"])])], set()))

    def test_an_unprinted_memory_catalog_id_does_not_fall_back_to_an_affix_id(self):
        data = memory_document([("BaseAffix", [("1", [("Id", "870059")])])])
        fields = project(data, 0, "a" * 64)["domains"]["memories"]["rows"][0]["fields"]
        self.assertEqual((fields["base_id"]["status"], fields["base_id"]["values"],
                          fields["base_id"]["missing_paths"], fields["base_affix_id"]["values"][0]["text"]),
                         ("not_printed", [], [["heroCharacterv3OverView", "reminiscenceOverView", "reminiscence", "1", "detail", "BaseId"]],
                          "870059"))

    def test_an_unprinted_memory_base_affix_does_not_hide_the_printed_catalog_id(self):
        data = memory_document([("BaseId", "9749")])
        fields = project(data, 0, "a" * 64)["domains"]["memories"]["rows"][0]["fields"]
        self.assertEqual((fields["base_id"]["values"][0]["text"], fields["base_affix_id"]["status"],
                          fields["base_affix_id"]["values"]), ("9749", "not_printed", []))

    def test_equipment_base_affixes_keep_their_printed_argument_tokens(self):
        data = document([("bag", [("wearItems", [("1", [("Item", [("BaseAffix", [("1", [
            ("Id", "860031"), ("Version", "003"), ("DynArgs", [("1", "17.250")])])])])])])]),
            ("heroCharacterv3OverView", None), ("skillLayout", None)])
        fields = project(data, 0, "a" * 64)["domains"]["equipment"]["rows"][0]["fields"]
        self.assertEqual(fields.get("base_affix_args", {}).get("values"), [{
            "path": ["bag", "wearItems", "1", "Item", "BaseAffix", "1", "DynArgs", "1"],
            "text": "17.250", "class": "float"}])

    def test_equipment_base_affixes_cannot_overwrite_the_catalog_base_id(self):
        data = document([("bag", [("wearItems", [("1", [("Item", [("BaseId", "9711"),
            ("BaseAffix", [("1", [("Id", "860031")])])])])])]),
            ("heroCharacterv3OverView", None), ("skillLayout", None)])
        fields = project(data, 0, "a" * 64)["domains"]["equipment"]["rows"][0]["fields"]
        self.assertEqual([row["text"] for row in fields["base_id"]["values"]], ["9711"])

    def test_equipment_slot_and_chip_affixes_keep_values_and_unmapped_conditions(self):
        data = document([("bag", [("wearItems", [("1", [("Item", [
            ("SlotAffix", [("1", [("Id", "870043")])]),
            ("ChipAffix", [("1", [("DynArgs", [("1", "-0.375")]), ("Condition", "UNMAPPED")])])])])])]),
            ("heroCharacterv3OverView", None), ("skillLayout", None)])
        row = project(data, 0, "a" * 64)["domains"]["equipment"]["rows"][0]
        self.assertEqual((row["fields"].get("slot_id", {}).get("values"),
                          row["fields"].get("chip_args", {}).get("values"), row["conditions"]),
                         ([{"path": ["bag", "wearItems", "1", "Item", "SlotAffix", "1", "Id"],
                            "text": "870043", "class": "int"}],
                          [{"path": ["bag", "wearItems", "1", "Item", "ChipAffix", "1", "DynArgs", "1"],
                            "text": "-0.375", "class": "float"}],
                          {"condition": "printed_unmapped", "filter": "not_printed", "behavior": "not_printed"}))

    def test_skills_keep_six_affix_families_and_the_separate_catalog_base_id(self):
        lists = [(name, [("1", [("Id", str(870101 + index)), ("DynArgs", [("1", str(index) + ".250")])])])
                 for index, name in enumerate(("BaseAffix", "Prefix", "Suffix", "SlotAffix", "EnchantAffixs", "ChipAffix"))]
        data = skill_document([("1", [("BaseId", "9711"), ("Id", "PRIVATE-INSTANCE-X")] + lists)], None)
        result = project(data, 0, "a" * 64)
        fields = result["domains"]["skill_items"]["rows"][0]["fields"]
        self.assertEqual(([fields.get(name, {}).get("values", []) for name in
                           ("base_affix_args", "prefix_args", "suffix_args", "slot_args", "enchant_args", "chip_args")],
                          [value["text"] for value in fields["base_id"]["values"]],
                          "PRIVATE-INSTANCE-X" in json.dumps(result)),
                         ([[{"path": ["skills", "skills", "1", native, "1", "DynArgs", "1"],
                             "text": str(index) + ".250", "class": "float"}]
                           for index, native in enumerate(("BaseAffix", "Prefix", "Suffix", "SlotAffix", "EnchantAffixs", "ChipAffix"))],
                          ["9711"], False))

    def test_dressed_skills_keep_affix_and_catalog_ids_under_distinct_names(self):
        data = skill_document(None, [("1", [("Item", [("BaseId", "9751"),
            ("BaseAffix", [("1", [("Id", "870019"), ("source", "004")])])])])])
        fields = project(data, 0, "a" * 64)["domains"]["dressed_skill_items"]["rows"][0]["fields"]
        self.assertEqual([(name, [row["text"] for row in fields[name]["values"]]) for name in
                          ("base_id", "base_affix_id", "base_affix_source")],
                         [("base_id", ["9751"]), ("base_affix_id", ["870019"]), ("base_affix_source", ["004"])])

    def test_skills_exclude_base_attribute_and_fixed_affix_lists(self):
        data = skill_document([("1", [("BaseAttrAffix", [("1", [("Id", "EXCLUDED-BASE-CANARY")])]),
            ("FixedBaseAffix", [("1", [("Id", "EXCLUDED-FIXED-CANARY")])])])], None)
        result = json.dumps(project(data, 0, "a" * 64))
        self.assertEqual([token for token in ("EXCLUDED-BASE-CANARY", "EXCLUDED-FIXED-CANARY", "base_attr_id", "fixed_base_id")
                          if token in result], [])

    def test_memories_do_not_acquire_slot_or_chip_fields_from_the_expanded_registry(self):
        data = document([("bag", [("wearItems", None)]), ("skillLayout", None),
            ("heroCharacterv3OverView", [("reminiscenceOverView", [("reminiscence", [("1", [("detail", [
                ("SlotAffix", [("1", [("Id", "MEMORY-SLOT-CANARY")])]),
                ("ChipAffix", [("1", [("Id", "MEMORY-CHIP-CANARY")])])])])])])])])
        row = project(data, 0, "a" * 64)["domains"]["memories"]["rows"][0]
        self.assertEqual((set(row["fields"]) & {"slot_id", "chip_id"}, "MEMORY-SLOT-CANARY" in json.dumps(row),
                          "MEMORY-CHIP-CANARY" in json.dumps(row)), (set(), False, False))

    def test_new_skill_fields_distinguish_missing_empty_and_elided_lists(self):
        results = []
        for fields in ([], [("Prefix", None)], [("Prefix", tables(30) + [("31", ELIDED)])]):
            data = skill_document([("1", fields or [("BaseId", "9711")])], None)
            value = project(data, 0, "a" * 64)["domains"]["skill_items"]["rows"][0]["fields"]["prefix_args"]
            results.append((value["status"], bool(value["missing_paths"]), bool(value["empty_paths"]), bool(value["elided_paths"])))
        self.assertEqual(results, [("not_printed", True, False, False), ("complete", False, True, False),
                                   ("elided", True, False, True)])

    def test_duplicate_affix_ids_stay_in_separate_source_occurrences(self):
        data = skill_document([("1", [("Prefix", [("1", [("Id", "870037")]), ("2", [("Id", "870037")])]),
                                        ("BaseAffix", [("1", [("Id", "870037")])])])], None)
        fields = project(data, 0, "a" * 64)["domains"]["skill_items"]["rows"][0]["fields"]
        self.assertEqual([(value["text"], value["path"][-3:]) for name in ("base_affix_id", "prefix_id")
                          for value in fields[name]["values"]],
                         [("870037", ["BaseAffix", "1", "Id"]), ("870037", ["Prefix", "1", "Id"]),
                          ("870037", ["Prefix", "2", "Id"])])

    def test_new_affix_arguments_preserve_lexical_forms_without_numeric_conversion(self):
        data = skill_document([("1", [("ChipAffix", [("1", [("DynArgs", [("1", "0002"), ("2", "-0.00"),
                                                                                         ("3", "true")])])])])], None)
        field = project(data, 0, "a" * 64)["domains"]["skill_items"]["rows"][0]["fields"]["chip_args"]
        self.assertEqual([(value["text"], value["class"]) for value in field["values"]],
                         [("0002", "text"), ("-0.00", "float"), ("true", "bool")])

    def test_nested_skill_argument_tables_remain_a_controlled_importer_subset_refusal(self):
        data = skill_document([("1", [("Prefix", [("1", [("DynArgs", [("1", [("1", "NESTED-CANARY")])])])])])], None)
        self.assertEqual(refusals(data), ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_noncontiguous_new_affix_lists_remain_a_controlled_refusal(self):
        data = skill_document([("1", [("SlotAffix", [("3", [("Id", "870013")])])])], None)
        self.assertEqual(refusals(data), ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_new_gear_base_conditions_are_unmapped_without_exporting_their_contents(self):
        data = document([("bag", [("wearItems", [("1", [("Item", [("BaseAffix", [("1", [
            ("Condition", "CONDITION-PRIVATE-CANARY")])])])])])]),
            ("heroCharacterv3OverView", None), ("skillLayout", None)])
        row = project(data, 0, "a" * 64)["domains"]["equipment"]["rows"][0]
        self.assertEqual((row["conditions"]["condition"], "CONDITION-PRIVATE-CANARY" in json.dumps(row)),
                         ("printed_unmapped", False))

    def test_new_affix_observations_leave_the_source_and_unknown_gates_unchanged(self):
        data = skill_document([("1", [("Prefix", [("1", [("Id", "870013")])])])], None)
        before = copy.deepcopy(data)
        result = project(data, 0, "a" * 64)
        self.assertEqual((data, result["counts"]["domains"], result["import_complete"], result["runtime"],
                          result["identity"], result["freshness"], result["selected_skill"]),
                         (before, 14, False, "unknown", "unknown", "unknown", "unknown"))

    def test_one_visible_reference_matches_the_same_events_item_alias(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", [("1", [("key", "3"), ("value", [("skillId", "STONE-X9")])])])]),
                         ("skills", [("skills", [("1", [("Id", "STONE-X9"), ("BaseId", "9007")])])])])
        self.assertEqual(logbuild.skill_references(data, 0, "a" * 64)["references"][0]["skill_items_alias"], "skill_items[0]")

    def test_duplicate_visible_tokens_never_choose_an_item_alias(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", [("1", [("value", [("skillId", "DUPLICATE")])])])]),
                         ("skills", [("skills", [("1", [("Id", "DUPLICATE"), ("BaseId", "8153")]),
                                                ("2", [("Id", "DUPLICATE"), ("BaseId", "8153")])])])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["skill_items_alias"], row.get("status"), row.get("visible_match_count")),
                         (None, "ambiguous_visible_duplicates", 2))

    def test_hidden_item_rows_keep_visible_matches_conditional(self):
        items = [(str(index), [("Id", "ITEM" + str(index))]) for index in range(1, 31)] + [("31", ELIDED)]
        data = reference_document(items, [("1", [("value", [("skillId", "ITEM7")])]),
                                          ("2", [("value", [("skillId", "ITEM99")])])])
        rows = logbuild.skill_references(data, 0, "a" * 64)["references"]
        self.assertEqual([(row["status"], row.get("uniqueness"), row["visible_match_count"]) for row in rows],
                         [("observed_token_match", "unknown", 1), ("no_visible_match_items_incomplete", None, 0)])

    def test_a_printed_zero_observes_the_sentinel_without_looking_up_an_equal_item(self):
        data = reference_document([("1", [("Id", "0")])], [("1", [("value", [("skillId", "0")])])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["status"], row["visible_match_count"], row["skill_items_alias"], row["uniqueness"]),
                         ("sentinel_observed", None, None, None))

    def test_a_scalar_reference_parent_is_an_observation_gap_without_a_refusal(self):
        data = reference_document([("1", [("Id", "UNUSED")])], [("1", [("value", "PARENTCANARY")])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["status"], row.get("reference_detail"), row.get("reference_path"), row["visible_match_count"]),
                         ("reference_shape_unsupported", "parent_scalar", ["skillLayout", "slots", "1", "value"], None))

    def test_reference_results_keep_a_fixed_diagnostic_envelope_without_fabricating_empty_rows(self):
        data = reference_document([("1", [("Id", "TOKEN")])], None)
        projection = project(data, 0, "a" * 64)
        self.assertEqual(logbuild.skill_references(data, 0, "a" * 64), {
            "format": "tli-log-skill-references-v1", "scope": "printed_subtree_only",
            "evidence": "lexical_token_equality_within_one_event", "import_complete": False,
            "identity": "unknown", "runtime": "unknown", "freshness": "unknown", "selected_skill": "unknown",
            "build_code": "unknown", "installation": "unknown", "activation": "unknown", "effective_level": "unknown",
            "inventory_completeness": "unknown", "coordinate_binding": "pending_CalSkillTabIndex",
            "record_binding": "pending_InitSkillSlotItemData_return", "source": projection["source"], "event": projection["event"],
            "layout_side": {"path": ["skillLayout", "slots"], "status": "empty", "visible_rows": 0, "total_rows": None},
            "items_side": {"path": ["skills", "skills"], "status": "complete", "visible_rows": 1, "total_rows": None,
                           "rows_with_token": 1, "rows_without_token": 0, "hidden_rows": False, "closed": True},
            "references": [], "counts": {"reference_not_printed": 0, "reference_elided": 0, "reference_printed_empty": 0,
                "reference_shape_unsupported": 0, "sentinel_observed": 0, "no_match_items_not_printed": 0,
                "no_match_items_printed_empty": 0, "ambiguous_visible_duplicates": 0, "observed_token_match": 0,
                "no_visible_match_items_incomplete": 0, "no_visible_match_closed_printed_subtree": 0}})

    def test_a_printed_empty_row_does_not_fabricate_a_reference_parent(self):
        row = logbuild.skill_references(reference_document(None, [("1", None)]), 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"], row["visible_match_count"]),
                         ("row_printed_empty", "reference_not_printed", ["skillLayout", "slots", "1", "value"], None))

    def test_an_unprinted_reference_parent_retains_its_first_missing_path(self):
        row = logbuild.skill_references(reference_document(None, [("1", [("key", "9")])]), 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"]),
                         ("parent_missing", "reference_not_printed", ["skillLayout", "slots", "1", "value"]))

    def test_a_reference_parent_hidden_after_thirty_tables_is_elided(self):
        data = reference_document(None, [("1", tables(30) + [("tail", ELIDED)])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"]),
                         ("parent_hidden_tail", "reference_elided", ["skillLayout", "slots", "1", "value"]))

    def test_an_elided_reference_parent_stays_distinct_from_a_missing_parent(self):
        data = reference_document(None, [("1", tables(30) + [("value", ELIDED)])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"]),
                         ("parent_elided", "reference_elided", ["skillLayout", "slots", "1", "value"]))

    def test_a_printed_empty_parent_leaves_its_child_unprinted(self):
        data = reference_document(None, [("1", [("value", None)])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"]),
                         ("parent_printed_empty", "reference_not_printed", ["skillLayout", "slots", "1", "value", "skillId"]))

    def test_an_unprinted_reference_leaf_retains_the_full_leaf_path(self):
        data = reference_document(None, [("1", [("value", [("Other", "ignored")])])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"]),
                         ("leaf_missing", "reference_not_printed", ["skillLayout", "slots", "1", "value", "skillId"]))

    def test_a_reference_leaf_hidden_after_thirty_tables_is_elided(self):
        data = reference_document(None, [("1", [("value", tables(30) + [("tail", ELIDED)])])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"]),
                         ("leaf_hidden_tail", "reference_elided", ["skillLayout", "slots", "1", "value", "skillId"]))

    def test_an_elided_reference_leaf_does_not_become_an_empty_reference(self):
        data = reference_document(None, [("1", [("value", tables(30) + [("skillId", ELIDED)])])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["visible_match_count"]),
                         ("leaf_elided", "reference_elided", None))

    def test_a_printed_empty_leaf_is_an_observed_empty_without_a_lookup(self):
        data = reference_document(None, [("1", [("value", [("skillId", None)])])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["reference_path"], row["visible_match_count"]),
                         ("leaf_printed_empty", "reference_printed_empty", ["skillLayout", "slots", "1", "value", "skillId"], None))

    def test_a_table_reference_leaf_is_an_observation_gap_without_a_refusal(self):
        data = reference_document(None, [("1", [("value", [("skillId", [("Other", "LEAFCANARY")])])])])
        row = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((row["reference_detail"], row["status"], row["visible_match_count"]),
                         ("leaf_table", "reference_shape_unsupported", None))

    def test_scalar_references_emit_only_the_projected_coordinate_alias_and_paths(self):
        data = reference_document([("1", [("Id", "MATCH")])], [("1", [("value", [("skillId", "MATCH")])])])
        self.assertEqual(logbuild.skill_references(data, 0, "a" * 64)["references"], [{
            "layout_alias": "skill_layout[0]", "layout_path": ["skillLayout", "slots", "1"],
            "reference_path": ["skillLayout", "slots", "1", "value", "skillId"], "status": "observed_token_match",
            "reference_detail": "scalar", "skill_items_alias": "skill_items[0]", "skill_items_path": ["skills", "skills", "1"],
            "visible_match_count": 1, "uniqueness": "unique_in_closed_printed_subtree"}])

    def test_only_the_exact_printed_zero_is_a_sentinel(self):
        data = reference_document([(str(index), [("Id", token)]) for index, token in enumerate(("00", "-0", "0.0", " 0"), 1)],
            [(str(index), [("value", [("skillId", token)])]) for index, token in enumerate(("00", "-0", "0.0", " 0"), 1)])
        self.assertEqual([(row["status"], row["visible_match_count"]) for row in logbuild.skill_references(data, 0, "a" * 64)["references"]],
                         [("observed_token_match", 1)] * 4)

    def test_token_matching_does_not_coerce_numeric_text_or_fold_case(self):
        data = reference_document([("1", [("Id", "7")]), ("2", [("Id", "a1")])],
            [("1", [("value", [("skillId", "007")])]), ("2", [("value", [("skillId", "A1")])])])
        self.assertEqual([(row["status"], row["visible_match_count"]) for row in logbuild.skill_references(data, 0, "a" * 64)["references"]],
                         [("no_visible_match_closed_printed_subtree", 0)] * 2)

    def test_an_unprinted_item_collection_stops_before_token_lookup(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", [("slots", [("1", [("value", [("skillId", "UNMATCHED")])])])])])
        result = logbuild.skill_references(data, 0, "a" * 64)
        self.assertEqual((result["items_side"], result["references"][0]["status"], result["references"][0]["visible_match_count"]),
                         ({"path": ["skills", "skills"], "status": "not_printed", "visible_rows": 0, "total_rows": None,
                           "rows_with_token": 0, "rows_without_token": 0, "hidden_rows": False, "closed": False},
                          "no_match_items_not_printed", None))

    def test_a_printed_empty_item_collection_stops_before_token_lookup(self):
        result = logbuild.skill_references(reference_document(None, [("1", [("value", [("skillId", "UNMATCHED")])])]), 0, "a" * 64)
        self.assertEqual((result["items_side"]["status"], result["items_side"]["closed"],
                          result["references"][0]["status"], result["references"][0]["visible_match_count"]),
                         ("empty", False, "no_match_items_printed_empty", None))

    def test_a_wholly_elided_item_collection_keeps_no_visible_matches_incomplete(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
            ("skillLayout", [("slots", [("1", [("value", [("skillId", "UNMATCHED")])])])]),
            ("skills", tables(30) + [("skills", ELIDED)])])
        result = logbuild.skill_references(data, 0, "a" * 64)
        self.assertEqual((result["items_side"], result["references"][0]["status"], result["references"][0]["visible_match_count"]),
                         ({"path": ["skills", "skills"], "status": "elided", "visible_rows": 0, "total_rows": None,
                           "rows_with_token": 0, "rows_without_token": 0, "hidden_rows": True, "closed": False},
                          "no_visible_match_items_incomplete", 0))

    def test_one_unprinted_item_token_prevents_closed_subtree_uniqueness(self):
        data = reference_document([("1", [("Id", "MATCH")]), ("2", [("Other", "ignored")])],
            [("1", [("value", [("skillId", "MATCH")])]), ("2", [("value", [("skillId", "UNMATCHED")])])])
        result = logbuild.skill_references(data, 0, "a" * 64)
        self.assertEqual((result["items_side"]["closed"], result["items_side"]["rows_without_token"],
                          [(row["status"], row["uniqueness"]) for row in result["references"]]),
                         (False, 1, [("observed_token_match", "unknown"), ("no_visible_match_items_incomplete", None)]))

    def test_non_scalar_item_tokens_are_counted_without_becoming_matches(self):
        items = [("1", [("Id", "MATCH")]), ("2", None), ("3", [("Other", "ignored")]),
                 ("4", [("Id", None)]), ("5", [("Id", [("Other", "ignored")])]), ("6", tables(30) + [("Id", ELIDED)])]
        result = logbuild.skill_references(reference_document(items, [("1", [("value", [("skillId", "MATCH")])])]), 0, "a" * 64)
        self.assertEqual((result["items_side"], result["references"][0]["uniqueness"]),
                         ({"path": ["skills", "skills"], "status": "elided", "visible_rows": 6, "total_rows": None,
                           "rows_with_token": 1, "rows_without_token": 5, "hidden_rows": False, "closed": False}, "unknown"))

    def test_nested_item_elision_does_not_invent_hidden_item_rows(self):
        items = [("1", [("Id", "MATCH"), ("Other", tables(30) + [("tail", ELIDED)])])]
        result = logbuild.skill_references(reference_document(items, [("1", [("value", [("skillId", "MATCH")])])]), 0, "a" * 64)
        self.assertEqual((result["items_side"]["status"], result["items_side"]["hidden_rows"],
                          result["items_side"]["closed"], result["references"][0]["uniqueness"]),
                         ("elided", False, False, "unknown"))

    def test_references_use_the_same_item_aliases_and_paths_as_the_public_projection(self):
        data = reference_document([("1", [("Id", "FIRST")]), ("2", [("Id", "SECOND")])],
                                 [("1", [("value", [("skillId", "SECOND")])])])
        projection = project(data, 0, "a" * 64)
        result = logbuild.skill_references(data, 0, "a" * 64)["references"][0]
        self.assertEqual((result["layout_alias"], result["layout_path"], result["skill_items_alias"], result["skill_items_path"]),
                         (projection["domains"]["skill_layout"]["rows"][0]["alias"], projection["domains"]["skill_layout"]["rows"][0]["path"],
                          projection["domains"]["skill_items"]["rows"][1]["alias"], projection["domains"]["skill_items"]["rows"][1]["path"]))

    def test_duplicate_layout_keys_do_not_merge_distinct_printed_reference_rows(self):
        data = reference_document([("1", [("Id", "MATCH")])],
            [("1", [("key", "7"), ("value", [("skillId", "MATCH")])]), ("2", [("key", "7"), ("value", [("skillId", "MATCH")])])])
        self.assertEqual([(row["layout_alias"], row["skill_items_alias"]) for row in logbuild.skill_references(data, 0, "a" * 64)["references"]],
                         [("skill_layout[0]", "skill_items[0]"), ("skill_layout[1]", "skill_items[0]")])

    def test_layout_elision_preserves_thirty_references_without_inventing_a_total(self):
        data = reference_document(None, [(str(index), [("key", str(index))]) for index in range(1, 31)] + [("31", ELIDED)])
        result = logbuild.skill_references(data, 0, "a" * 64)
        self.assertEqual((result["layout_side"], len(result["references"]), result["references"][-1]["layout_path"]),
                         ({"path": ["skillLayout", "slots"], "status": "elided", "visible_rows": 30, "total_rows": None},
                          30, ["skillLayout", "slots", "30"]))

    def test_a_missing_layout_collection_does_not_invent_references(self):
        result = logbuild.skill_references(skill_document(None, None), 0, "a" * 64)
        self.assertEqual((result["layout_side"], result["references"]),
                         ({"path": ["skillLayout", "slots"], "status": "not_printed", "visible_rows": 0, "total_rows": None}, []))

    def test_a_wholly_elided_layout_collection_does_not_invent_references(self):
        data = document([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                         ("skillLayout", tables(30) + [("slots", ELIDED)])])
        result = logbuild.skill_references(data, 0, "a" * 64)
        self.assertEqual((result["layout_side"], result["references"]),
                         ({"path": ["skillLayout", "slots"], "status": "elided", "visible_rows": 0, "total_rows": None}, []))

    def test_reference_counts_include_all_statuses_with_zeroes_for_unobserved_cases(self):
        data = reference_document([("1", [("Id", "ALPHA")]), ("2", [("Id", "DUP")]), ("3", [("Id", "DUP")])],
            [("1", [("value", [("skillId", "ALPHA")])]), ("2", [("value", [("skillId", "0")])]),
             ("3", [("value", [("skillId", "DUP")])]), ("4", [("value", [("skillId", "UNMATCHED")])]),
             ("5", [("value", [("skillId", "ALPHA")])]), ("6", [("value", [("Other", "ignored")])])])
        self.assertEqual(logbuild.skill_references(data, 0, "a" * 64)["counts"], {
            "reference_not_printed": 1, "reference_elided": 0, "reference_printed_empty": 0, "reference_shape_unsupported": 0,
            "sentinel_observed": 1, "no_match_items_not_printed": 0, "no_match_items_printed_empty": 0,
            "ambiguous_visible_duplicates": 1, "observed_token_match": 2, "no_visible_match_items_incomplete": 0,
            "no_visible_match_closed_printed_subtree": 1})

    def test_reference_tokens_and_their_hashes_never_leave_the_private_comparison(self):
        canaries = ("SECRETMATCH93", "SECRETDUPE27", "SECRETMISS81")
        data = reference_document([("1", [("Id", canaries[0])]), ("2", [("Id", canaries[1])]), ("3", [("Id", canaries[1])])],
            [(str(index), [("value", [("skillId", token)])]) for index, token in enumerate(canaries, 1)])
        result = json.dumps(logbuild.skill_references(data, 0, "a" * 64))
        self.assertEqual([value for token in canaries for value in (token, hashlib.sha256(token.encode()).hexdigest()) if value in result], [])

    def test_reference_matching_never_borrows_items_from_another_event(self):
        data = reference_document([("1", [("Id", "DIFFERENT")])], [("1", [("value", [("skillId", "ONLYLATER")])])])
        data["events"].append(reference_document([("1", [("Id", "ONLYLATER")])], None)["events"][0])
        self.assertEqual(logbuild.skill_references(data, 0, "a" * 64)["references"][0]["status"],
                         "no_visible_match_closed_printed_subtree")

    def test_unrelated_malformed_equipment_keeps_the_same_public_refusal(self):
        data = document([("bag", [("wearItems", [("1", [("Item", [("BaseId", [("Other", "REFUSALCANARY")])])])])]),
                         ("heroCharacterv3OverView", None), ("skillLayout", None)])
        self.assertEqual(refusals(data), ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_unrelated_malformed_affixes_keep_the_same_public_refusal(self):
        data = document([("bag", [("wearItems", [("1", [("Item", [("Prefix", [("1", [("Id", [("Other", "AFFIXCANARY")])])])])])])]),
                         ("heroCharacterv3OverView", None), ("skillLayout", None)])
        self.assertEqual(refusals(data), ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_nonarray_layout_slots_keep_the_same_public_refusal(self):
        data = reference_document(None, [("wrong", [("key", "3")])])
        self.assertEqual(refusals(data), ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_nonarray_skill_items_keep_the_same_public_refusal(self):
        data = reference_document([("wrong", [("Id", "REFUSALCANARY")])], None)
        self.assertEqual(refusals(data), ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_scalar_layout_rows_keep_the_same_public_refusal(self):
        data = reference_document(None, [("1", "REFUSALCANARY")])
        self.assertEqual(refusals(data), ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_a_noncandidate_event_keeps_the_same_public_refusal(self):
        self.assertEqual(refusals(document([("Other", "REFUSALCANARY")])),
                         ["Log build projection requires a supported bounded saved-tree contract"] * 2)

    def test_reference_observations_do_not_mutate_the_input_or_existing_projection(self):
        data = reference_document([("1", [("Id", "MATCH"), ("Level", "019"), ("SkillItemLevel", "6")])],
                                 [("1", [("key", "007"), ("value", [("skillId", "MATCH")])])])
        before = copy.deepcopy(data)
        projection = project(data, 0, "a" * 64)
        logbuild.skill_references(data, 0, "a" * 64)
        self.assertEqual((data, project(data, 0, "a" * 64)), (before, projection))

    def test_the_projection_keeps_fourteen_domains_and_its_approved_field_sets(self):
        data = reference_document([("1", [("Id", "MATCH"), ("Level", "019"), ("SkillItemLevel", "6")])],
                                 [("1", [("key", "007"), ("value", [("skillId", "MATCH")])])])
        result = project(data, 0, "a" * 64)
        self.assertEqual((result["format"], result["counts"]["domains"], set(result["domains"]["skill_layout"]["rows"][0]["fields"]),
                          set(result["domains"]["skill_items"]["rows"][0]["fields"]), "references" in result,
                          result["import_complete"], result["selected_skill"]),
                         ("tli-log-build-domains-v2", 14, {"slot_key"}, {"base_id", "level", "skill_item_level", "rarity", *empty_affixes()}, False, False, "unknown"))

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
                           "skill_item_level": [("6", "int")], "rarity": [("03", "text")], **empty_affixes()}])

    def test_dressed_skills_keep_slot_and_nested_lexical_fields(self):
        data = skill_document(None, [("1", [("PageId", "003"), ("Index", "02"),
            ("Item", [("BaseId", "8153"), ("Level", "019"), ("SkillItemLevel", "6"), ("RareValue", "4")])])])
        rows = project(data, 0, "a" * 64)["domains"]["dressed_skill_items"]["rows"]
        self.assertEqual([{field: [value["text"] for value in result["values"]]
                           for field, result in row["fields"].items()} for row in rows],
                         [{"page_id": ["003"], "index": ["02"], "base_id": ["8153"],
                           "level": ["019"], "skill_item_level": ["6"], "rarity": ["4"], **empty_affixes()}])

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
                         ("tli-log-build-domains-v2", 14, "printed_subtree_only", False,
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
                         ("tli-log-build-domains-v2", 14, "printed_subtree_only", False,
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
