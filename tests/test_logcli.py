import contextlib
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
    def candidates(document, source):
        return [0, 2]

    @staticmethod
    def project(document, index, source):
        return {"format": "tli-log-build-domains-v1", "scope": "printed_subtree_only", "import_complete": False,
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


class LogCliTests(unittest.TestCase):
    """Save distinct diagnostic event projections through a local atomic CLI."""

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
            project = staticmethod(Builder.project)

            @staticmethod
            def skill_references(document, index, source):
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
            project = staticmethod(Builder.project)

            @staticmethod
            def skill_references(document, index, source):
                result = Builder.skill_references(document, index, source)
                result["references"][0].update(status="ambiguous_visible_duplicates", skill_items_alias=None,
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
