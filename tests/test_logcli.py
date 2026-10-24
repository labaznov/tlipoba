import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from damage_lab.logcli import main, render


def snapshot(path):
    """Read a small real file into fictional diagnostic event metadata."""
    raw = path.read_bytes()
    return {"source": {"sha256": hashlib.sha256(raw).hexdigest(), "snapshotBytes": len(raw), "bytesRead": len(raw),
                       "lines": 7, "ignoredLines": 2, "oversizedLines": 0, "incompleteFinalLine": False},
            "events": [{"private": "RAW-TREE-MARKER"}] * 3, "rejected": [{"private": "RAW-REJECTED-MARKER"}]}


class Builder:
    """Provide separate synthetic state candidates without merging their values."""

    @staticmethod
    def partial_candidates(document, source):
        return []

    @staticmethod
    def candidates(document, source):
        return [0, 2]

    @staticmethod
    def project(document, index, source):
        return {"format": "tli-log-build-domains-v2", "scope": "printed_subtree_only", "import_complete": False,
                "identity": "unknown", "runtime": "unknown", "freshness": "unknown", "selected_skill": "unknown",
                "build_code": "unknown", "source": {"sha256": source, "snapshot_bytes": document["source"]["snapshotBytes"]},
                "event": {"index": index, "start_line": index + 1, "end_line": index + 2, "boundary": "next_record"},
                "domains": {"skill_items": {"path": ["skills", "skills"], "status": "complete", "node_kind": "table",
                                         "visible_entries": 1, "total_entries": None, "gaps": [],
                                         "rows": [{"alias": "skill_items[0]", "path": ["skills", "skills", "1"], "fields": {
                                             "base": {"status": "complete", "values": [{"path": ["base"],
                                             "text": "</pre><script>bad()</script>", "class": "text"}]}}}]}},
                "counts": {"domains": 1, "rows": 1, "lexical_values": 1}}

    @staticmethod
    def skill_references(document, index, source):
        return {"format": "tli-log-skill-references-v1", "scope": "printed_subtree_only",
                "evidence": "lexical_token_equality_within_one_event", "import_complete": False,
                "installation": "unknown", "activation": "unknown", "effective_level": "unknown",
                "inventory_completeness": "unknown", "coordinate_binding": "pending_CalSkillTabIndex",
                "record_binding": "pending_InitSkillSlotItemData_return", "counts": {"references": 1},
                "layout_side": {"status": "complete"}, "items_side": {"status": "complete", "closed": True},
                "references": [{"layout_alias": "skill_layout[0]", "layout_path": ["skillLayout", "slots", "1"],
                    "reference_path": ["skillLayout", "slots", "1", "value", "skillId"],
                    "status": "observed_token_match", "skill_items_alias": "skill_items[0]",
                    "skill_items_path": ["skills", "skills", "1"], "visible_match_count": 1,
                    "uniqueness": "unique_in_closed_printed_subtree"}]}

    @staticmethod
    def installation_graph(document, index, source):
        return {"skill_references": Builder.skill_references(document, index, source), "slots": [], "tabs": [],
                "derivation": {"runtime_binding": "unverified"}}


class LogCliTests(unittest.TestCase):
    """Save distinct diagnostic event projections through a local atomic CLI."""

    def test_default_import_keeps_bag_elided_character_separate_from_full_events(self):
        from test_logbuild import partial_document

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            output = Path(folder) / "result"
            code = main(["--game-log", str(Path(folder) / "placeholder.log"), "--output", str(output)],
                        reader=lambda path: partial_document())
            data = json.loads((output / "log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((code, data["version"], len(data["events"]), len(data.get("partial_events", []))),
                             (0, "0.3.0", 0, 1))

    def test_partial_html_shows_unknown_equipment_and_same_event_reference_targets(self):
        from test_logbuild import partial_document

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            output = Path(folder) / "result"
            main(["--game-log", str(Path(folder) / "placeholder.log"), "--output", str(output)],
                 reader=lambda path: partial_document())
            data = json.loads((output / "log-import.json").read_text(encoding="utf-8"))
            page = (output / "index.html").read_text(encoding="utf-8")
            self.assertEqual(([text in page for text in ("Частично напечатанное состояние", "экипировка неизвестна",
                              "Видимых записей: —", 'href="#event-0-skill_items[0]"', 'id="event-0-skill_items[0]"')],
                              data["partial_events"][0]["installation_graph"]["activation"],
                              data["partial_selection"]["selected"]), ([True] * 5, "unknown", [0]))

    def test_explicit_event_cannot_select_a_partial_shape_as_full(self):
        from test_logbuild import partial_document

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            output = Path(folder) / "result"
            code = main(["--game-log", str(Path(folder) / "placeholder.log"), "--event", "0", "--output", str(output)],
                        reader=lambda path: partial_document())
            self.assertEqual((code, output.exists()), (1, False))

    def test_explicit_full_selection_reports_but_does_not_project_partial_candidates(self):
        from test_logbuild import document, partial_document

        data = document()
        second = copy.deepcopy(partial_document()["events"][0])
        offset = data["events"][0]["end_line"] + 3
        second["start_line"] += offset
        second["end_line"] += offset
        data["events"].append(second)
        data["source"]["lines"] = second["end_line"] + 8
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            output = Path(folder) / "result"
            main(["--game-log", str(Path(folder) / "placeholder.log"), "--event", "0", "--output", str(output)],
                 reader=lambda path: data)
            report = json.loads((output / "log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((len(report["events"]), report["partial_events"], report["partial_selection"]),
                             (1, [], {"mode": "not_requested_for_explicit_full_event", "candidates": [1],
                                      "selected": [], "merged": False}))

    def test_malformed_partial_schema_does_not_publish_output(self):
        from test_logbuild import partial_document

        data = partial_document()
        data["events"][0]["tree"]["elisions"][0]["printedTableEntries"] = 29
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            output = Path(folder) / "result"
            code = main(["--game-log", str(Path(folder) / "placeholder.log"), "--output", str(output)],
                        reader=lambda path: data)
            self.assertEqual((code, list(Path(folder).iterdir())), (1, []))

    def test_installation_graphs_and_html_targets_stay_in_their_own_log_event(self):
        from test_logtables import event

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            lines = []
            for key in ("103", "1007"):
                lines.extend(event([("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                    ("skillLayout", [("slots", [("1", [("key", key)])])])]) + ["[closed]"])
            path = root / "input.log"
            path.write_text("\n".join(lines) + "\n", encoding="ascii")
            main(["--game-log", str(path), "--output", str(root / "result")])
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            page = (root / "result/index.html").read_text(encoding="utf-8")
            self.assertEqual(([(row["installation_graph"]["event"]["index"],
                row["installation_graph"]["slots"][0]["tab_candidate"],
                row["installation_graph"]["slots"][0]["position_candidate"],
                row["installation_graph"]["source"]["sha256"] == data["source"]["sha256"]) for row in data["events"]],
                [value in page for value in ('href="#event-0-skill_layout[0]"', 'id="event-0-skill_layout[0]"',
                    'href="#event-1-skill_layout[0]"', 'id="event-1-skill_layout[0]"')]),
                ([(0, 1, 4, True), (1, 7, 1, True)], [True] * 4))

    def test_legacy_html_reports_that_installation_coordinates_are_unavailable(self):
        document = snapshot(Path(__file__))
        event = Builder.project(document, 0, document["source"]["sha256"])
        event["skill_references"] = Builder.skill_references(document, 0, document["source"]["sha256"])
        page = render({"source": {"sha256": "a" * 64, "bytes_read": 9},
                       "acquisition": {"parsed_events": 1, "rejected_events": 0}, "gaps": [], "events": [event]})
        self.assertIn("Кандидаты позиций недоступны в этом отчёте", page)

    def test_html_displays_conditional_coordinates_collisions_and_same_event_links(self):
        document = snapshot(Path(__file__))
        event = Builder.project(document, 2, document["source"]["sha256"])
        event["skill_references"] = Builder.skill_references(document, 2, document["source"]["sha256"])
        event["installation_graph"] = {"slots": [{"layout_alias": "skill_layout[0]", "slot_key_status": "coordinated",
            "tab_candidate": 7, "position_candidate": 3}], "tabs": [{"tab_candidate": 7,
            "slots": ["skill_layout[0]"], "collisions": [{"position_candidate": 3,
                "aliases": ["skill_layout[0]", "skill_layout[1]"], "winner": "unknown"}]}],
            "derivation": {"constants_unchanged": "assumed", "canary": "<script>graph()</script>"}}
        page = render({"source": {"sha256": "a" * 64, "bytes_read": 9},
                       "acquisition": {"parsed_events": 1, "rejected_events": 0}, "gaps": [], "events": [event]})
        self.assertEqual(tuple(value in page for value in ("Условные позиции навыков", "коллизии", "winner",
            "constants_unchanged", "&lt;script&gt;graph()&lt;/script&gt;", 'href="#event-2-skill_layout[0]"',
            "<td>7</td><td>3</td>", "<script>graph()</script>")), (True, True, True, True, True, True, True, False))

    def test_ordinary_import_saves_conditional_installation_coordinates_from_the_same_event(self):
        from test_logtables import event

        entries = [("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None),
                   ("skillLayout", [("slots", [("1", [("key", "205"), ("value", [("skillId", "PRIVATE-GRAPH-CANARY")])])])]),
                   ("skills", [("skills", [("1", [("Id", "PRIVATE-GRAPH-CANARY"), ("BaseId", "9749")])])])]
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = root / "input.log"
            path.write_bytes(("\r\n".join(event(entries)) + "\r\n[closed]\r\n").encode("ascii"))
            code = main(["--game-log", str(path), "--output", str(root / "result")])
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            graph = data["events"][0]["installation_graph"]
            self.assertEqual((code, data["version"], graph["slots"][0]["tab_candidate"],
                              graph["slots"][0]["position_candidate"], graph["skill_references"], graph["import_complete"],
                              "PRIVATE-GRAPH-CANARY" in json.dumps(data)),
                             (0, "0.3.0", 2, 6, data["events"][0]["skill_references"], False, False))

    def test_ordinary_import_keeps_memory_catalog_and_affix_ids_separate(self):
        from test_logtables import event

        detail = [("BaseId", "9737"), ("Id", "PRIVATE-MEMORY-CANARY"),
                  ("BaseAffix", [("1", [("Id", "870061"), ("DynArgs", [("1", "12.875")])])])]
        entries = [("bag", [("wearItems", None)]), ("skillLayout", None),
                   ("heroCharacterv3OverView", [("reminiscenceOverView", [("reminiscence", [
                       ("1", [("detail", detail)])])])])]
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = root / "input.log"
            path.write_bytes(("\r\n".join(event(entries)) + "\r\n[closed]\r\n").encode("ascii"))
            code = main(["--game-log", str(path), "--output", str(root / "result")])
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            page = (root / "result/index.html").read_text(encoding="utf-8")
            fields = data["events"][0]["domains"]["memories"]["rows"][0]["fields"]
            self.assertEqual((code, fields["base_id"]["values"][0]["text"],
                              fields["base_affix_id"]["values"][0]["text"], "base_affix_args" in page,
                              "PRIVATE-MEMORY-CANARY" in json.dumps(data) + page, data["events"][0]["import_complete"]),
                             (0, "9737", "870061", True, False, False))

    def test_ordinary_import_keeps_skill_affixes_without_parent_instance_ids(self):
        from test_logtables import event

        items = [("1", [("BaseId", "9751"), ("Id", "PRIVATE-PARENT-CANARY"),
                         ("Prefix", [("1", [("Id", "870031"), ("DynArgs", [("1", "031.75")])])])])]
        entries = [("bag", [("wearItems", None)]), ("heroCharacterv3OverView", None), ("skillLayout", None),
                   ("skills", [("skills", items)])]
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = root / "input.log"
            path.write_bytes(("\r\n".join(event(entries)) + "\r\n[closed]\r\n").encode("ascii"))
            code = main(["--game-log", str(path), "--output", str(root / "result")])
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            page = (root / "result/index.html").read_text(encoding="utf-8")
            fields = data["events"][0]["domains"]["skill_items"]["rows"][0]["fields"]
            self.assertEqual((code, fields["prefix_args"]["values"][0]["text"],
                              fields["base_id"]["values"][0]["text"], "prefix_args" in page,
                              "PRIVATE-PARENT-CANARY" in json.dumps(data) + page, data["events"][0]["import_complete"]),
                             (0, "031.75", "9751", True, False, False))

    def test_html_shows_reference_limits_and_unapplied_bindings(self):
        document = snapshot(Path(__file__))
        event = Builder.project(document, 0, document["source"]["sha256"])
        event["skill_references"] = Builder.skill_references(document, 0, document["source"]["sha256"])
        event["skill_references"].update(inventory_completeness="unknown", installation="unknown", activation="unknown",
            effective_level="unknown", coordinate_binding="pending_CalSkillTabIndex",
            record_binding="pending_InitSkillSlotItemData_return", counts={"references": 1})
        page = render({"source": {"sha256": "a" * 64, "bytes_read": 9},
                       "acquisition": {"parsed_events": 1, "rejected_events": 0}, "gaps": [], "events": [event]})
        self.assertTrue(all(value in page for value in ("inventory_completeness", "pending_CalSkillTabIndex",
            "pending_InitSkillSlotItemData_return", "lexical_token_equality_within_one_event", "counts")))

    def test_html_distinguishes_a_skipped_lookup_from_unknown_uniqueness(self):
        document = snapshot(Path(__file__))
        event = Builder.project(document, 0, document["source"]["sha256"])
        event["skill_references"] = Builder.skill_references(document, 0, document["source"]["sha256"])
        event["skill_references"]["references"][0].update(status="sentinel_observed", skill_items_alias=None,
            skill_items_path=None, visible_match_count=None, uniqueness=None)
        page = render({"source": {"sha256": "b" * 64, "bytes_read": 13},
                       "acquisition": {"parsed_events": 1, "rejected_events": 0}, "gaps": [], "events": [event]})
        self.assertIn("<td>—</td><td>—</td><td>—</td>", page)

    def test_all_candidates_are_written_separately_without_raw_table_payloads(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic source")
            main(["--game-log", str(source), "--output", str(root / "result")], reader=snapshot, builder=Builder)
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((data["selection"], [row["event"]["index"] for row in data["events"]],
                              "RAW-TREE-MARKER" in json.dumps(data), "RAW-REJECTED-MARKER" in json.dumps(data)),
                             ({"mode": "all_candidates", "candidates": [0, 2], "selected": [0, 2], "merged": False}, [0, 2], False, False))

    def test_each_event_keeps_its_own_reference_observations_next_to_the_domains(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic reference source")
            main(["--game-log", str(source), "--output", str(root / "result")], reader=snapshot, builder=Builder)
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            self.assertEqual([(row["event"]["index"], row["skill_references"]["references"][0]["skill_items_alias"],
                               row["counts"]["domains"], row["import_complete"]) for row in data["events"]],
                             [(0, "skill_items[0]", 1, False), (2, "skill_items[0]", 1, False)])

    def test_html_reference_links_target_only_the_matching_event_rows(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic reference source")
            main(["--game-log", str(source), "--output", str(root / "result")], reader=snapshot, builder=Builder)
            page = (root / "result/index.html").read_text(encoding="utf-8")
            self.assertEqual(('href="#event-0-skill_items[0]"' in page, 'id="event-0-skill_items[0]"' in page,
                              'href="#event-2-skill_items[0]"' in page, 'id="event-2-skill_items[0]"' in page,
                              page.count("observed_token_match")), (True, True, True, True, 2))

    def test_reference_refusal_cannot_publish_partial_output_or_private_error(self):
        class Refused:
            """Supply a failed reference projection after an otherwise accepted event."""

            candidates = staticmethod(Builder.candidates)
            partial_candidates = staticmethod(Builder.partial_candidates)
            project = staticmethod(Builder.project)

            @staticmethod
            def installation_graph(document, index, source):
                raise ValueError("PRIVATE-REFERENCE-CANARY")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic reference source")
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                code = main(["--game-log", str(source), "--output", str(root / "result")], reader=snapshot, builder=Refused)
            self.assertEqual((code, "PRIVATE-REFERENCE-CANARY" in output.getvalue(), (root / "result").exists()),
                             (1, False, False))

    def test_html_shows_the_visible_count_for_ambiguous_references(self):
        class Ambiguous:
            """Supply two visible matches without selecting an item row."""

            candidates = staticmethod(Builder.candidates)
            partial_candidates = staticmethod(Builder.partial_candidates)
            project = staticmethod(Builder.project)

            @staticmethod
            def installation_graph(document, index, source):
                result = Builder.installation_graph(document, index, source)
                result["skill_references"]["references"][0].update(status="ambiguous_visible_duplicates", skill_items_alias=None,
                    skill_items_path=None, visible_match_count=2, uniqueness=None)
                return result

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic ambiguous source")
            main(["--game-log", str(source), "--event", "0", "--output", str(root / "result")],
                 reader=snapshot, builder=Ambiguous)
            page = (root / "result/index.html").read_text(encoding="utf-8")
            self.assertEqual(("<th>Видимых совпадений</th>" in page, "<td>2</td>" in page), (True, True))

    def test_explicit_event_index_selects_one_candidate_without_verifying_identity(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic source")
            main(["--game-log", str(source), "--event", "2", "--output", str(root / "result")], reader=snapshot, builder=Builder)
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((len(data["events"]), data["identity"], data["import_complete"]), (1, "unknown", False))

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            (root / "result").mkdir()
            (root / "result/keep.txt").write_text("preserved", encoding="utf-8")
            main(["--game-log", str(root / "absent.log"), "--output", str(root / "result")], reader=snapshot, builder=Builder)
            self.assertEqual((root / "result/keep.txt").read_text(encoding="utf-8"), "preserved")

    def test_non_candidate_event_cannot_create_partial_outputs(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic source")
            main(["--game-log", str(source), "--event", "1", "--output", str(root / "result")], reader=snapshot, builder=Builder)
            self.assertEqual([path.name for path in root.iterdir()], ["input.log"])

    def test_empty_candidate_list_is_a_diagnostic_without_fabricated_build(self):
        class Empty:
            """Represent a readable log with no supported state table observed."""

            partial_candidates = staticmethod(Builder.partial_candidates)

            @staticmethod
            def candidates(document, source):
                return []

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic source")
            main(["--game-log", str(source), "--output", str(root / "result")], reader=snapshot, builder=Empty)
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((data["events"], data["selection"]["selected"], bool(data["gaps"])), ([], [], True))

    def test_default_reader_and_projector_import_a_real_synthetic_log(self):
        from test_logtables import event

        entries = [("bag", [("wearItems", [("1", [("Item", [("BaseId", "9001")])])])]),
                   ("heroCharacterv3OverView", [("pointOverView", [("activeId", [("1", "41")])])]),
                   ("skillLayout", [("slots", None)])]
        raw = ("\r\n".join(event(entries)) + "\r\n[closed]\r\n").encode("ascii")
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(raw)
            main(["--game-log", str(source), "--output", str(root / "result")])
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((data["source"]["sha256"], data["selection"]["selected"],
                              data["events"][0]["domains"]["equipment"]["rows"][0]["fields"]["base_id"]["values"][0]["text"]),
                             (hashlib.sha256(raw).hexdigest(), [0], "9001"))

    def test_html_escapes_lexical_values_and_contains_no_executable_payload(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"synthetic source")
            main(["--game-log", str(source), "--output", str(root / "result")], reader=snapshot, builder=Builder)
            page = (root / "result/index.html").read_text(encoding="utf-8")
            self.assertEqual(("<script>bad()" in page, "&lt;script&gt;bad()" in page,
                              "События не объединены" in page), (False, True, True))

    def test_error_text_cannot_echo_private_log_payloads(self):
        def broken(path):
            raise ValueError("PRIVATE-INPUT-MARKER")

        with tempfile.TemporaryDirectory() as folder:
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                code = main(["--game-log", str(Path(folder) / "input.log"), "--output", str(Path(folder) / "result")],
                            reader=broken, builder=Builder)
            self.assertEqual((code, "PRIVATE-INPUT-MARKER" in output.getvalue(), (Path(folder) / "result").exists()),
                             (1, False, False))

    def test_context_flag_saves_a_hash_bound_packet_without_rendering_neighbours(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"PRIVATE-NEIGHBOUR\n[2001.02.03-04.05.06:007][ 19]TLNetGame: Display: [Game]\n+n [17]\n")
            code = main(["--game-log", str(source), "--context", "--output", str(root / "result")])
            packet = (root / "result/log-context.json").read_bytes()
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            page = (root / "result/index.html").read_text(encoding="utf-8")
            self.assertEqual((code, data["context"]["sha256"], data["context"]["bytes"],
                              "PRIVATE-NEIGHBOUR" in packet.decode(), "PRIVATE-NEIGHBOUR" in json.dumps(data),
                              "PRIVATE-NEIGHBOUR" in page), (0, hashlib.sha256(packet).hexdigest(), len(packet), True, False, False))

    def test_context_source_change_cannot_publish_a_partial_result(self):
        from damage_lab.buildlog import snapshot as capture

        def changing(path):
            document = capture(path)
            path.write_bytes(path.read_bytes().replace(b"17", b"29"))
            return document

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"[2001.02.03-04.05.06:007][ 19]TLNetGame: Display: [Game]\n+n [17]\n")
            code = main(["--game-log", str(source), "--context", "--output", str(root / "result")], reader=changing)
            self.assertEqual((code, sorted(path.name for path in root.iterdir())), (1, ["input.log"]))

    def test_context_complete_describes_saved_windows_even_for_rejected_trees(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "input.log"
            source.write_bytes(b"[2001.02.03-04.05.06:007][ 19]TLNetGame: Display: [Game]\nnot a tree\n")
            main(["--game-log", str(source), "--context", "--output", str(root / "result")])
            page = (root / "result/index.html").read_text(encoding="utf-8")
            self.assertIn("Complete контекста означает сохранение запрошенных окон строк", page)

    def test_explicit_catalog_file_enriches_only_separate_selected_partial_event(self):
        from test_logbuild import partial_document
        from test_logcatalogfile import envelope

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps(envelope()), encoding="utf-8")
            code = main(["--game-log", str(root / "placeholder.log"), "--skill-catalog", str(catalog),
                         "--output", str(root / "result")], reader=lambda path: partial_document())
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((code, data["version"], data["skill_catalog_source"]["kind"],
                              data["partial_events"][0]["skill_catalog"]["rows"][0]["identity"]["tlidb_id"]),
                             (0, "0.3.0", "saved_skill_catalog", 9001))

    def test_invalid_catalog_is_refused_even_before_an_empty_source_is_projected(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            catalog = root / "invalid.json"
            catalog.write_text('{"format":"invalid"}', encoding="utf-8")
            calls = []
            code = main(["--game-log", str(root / "placeholder.log"), "--skill-catalog", str(catalog),
                         "--output", str(root / "result")], reader=lambda path: calls.append(path))
            self.assertEqual((code, calls, (root / "result").exists()), (1, [], False))

    def test_catalog_enrichment_keeps_explicit_strict_selection_and_suppresses_partial(self):
        from test_logbuild import reference_document, partial_document
        from test_logcatalogfile import envelope

        data = reference_document([("1", [("BaseId", "9001")])], None)
        second = copy.deepcopy(partial_document()["events"][0])
        offset = data["events"][0]["end_line"] + 3
        second["start_line"] += offset
        second["end_line"] += offset
        data["events"].append(second)
        data["source"]["lines"] = second["end_line"] + 8
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps(envelope()), encoding="utf-8")
            main(["--game-log", str(root / "placeholder.log"), "--skill-catalog", str(catalog), "--event", "0",
                  "--output", str(root / "result")], reader=lambda path: data)
            report = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            candidate = report["events"][0]["skill_catalog"]
            self.assertEqual((candidate["event"]["index"], candidate["source"]["sha256"],
                              report["partial_events"], report["partial_selection"]["selected"]),
                             (0, data["source"]["sha256"], [], []))

    def test_catalog_candidate_html_escapes_labels_and_keeps_levels_unknown(self):
        data = snapshot(Path(__file__))
        event = Builder.project(data, 0, data["source"]["sha256"])
        event["skill_references"] = Builder.skill_references(data, 0, data["source"]["sha256"])
        event["skill_catalog"] = {"rows": [{"alias": "<script>label</script>", "identity": None,
                                            "status": "gap", "reason": "<img src=x>"}]}
        page = render({"source": {"sha256": "a" * 64, "bytes_read": 9},
                       "acquisition": {"parsed_events": 1, "rejected_events": 0}, "gaps": [], "events": [event],
                       "skill_catalog_source": {"kind": "saved_skill_catalog", "sha256": "b" * 64, "bytes": 19}})
        self.assertEqual(("<script>label" in page, "&lt;script&gt;label&lt;/script&gt;" in page,
                          "&lt;img src=x&gt;" in page, "неизвестен" in page), (False, True, True, True))
