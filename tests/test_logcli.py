import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from damage_lab.logcli import main


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
                "domains": {"equipment": {"path": ["bag", "wearItems"], "status": "complete", "node_kind": "table",
                                         "visible_entries": 1, "total_entries": None, "gaps": [],
                                         "rows": [{"alias": "gear[0]", "path": ["bag", "wearItems", "1"], "fields": {
                                             "base": {"status": "complete", "values": [{"path": ["base"],
                                             "text": "</pre><script>bad()</script>", "class": "text"}]}}}]}},
                "counts": {"domains": 1, "rows": 1, "lexical_values": 1}}


class LogCliTests(unittest.TestCase):
    """Save distinct diagnostic event projections through a local atomic CLI."""

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
