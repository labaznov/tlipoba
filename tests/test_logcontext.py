import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from damage_lab.buildlog import snapshot
from damage_lab.logcontext import collect


def log(root, data):
    path = root / "input.log"
    path.write_bytes(data)
    return path


def event(value=17):
    return f"[2001.02.03-04.05.06:007][ 19]TLNetGame: Display: [Game]\n+n [{value}]\n".encode()


class LogContextTests(unittest.TestCase):
    """Bind retained neighbouring lines to the same file prefix as the parsed events."""

    def test_context_retains_event_and_neighbours_without_changing_the_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), b"before\n" + event() + b"[other] after\n")
            source = snapshot(path)
            before = json.dumps(source, sort_keys=True)
            result = collect(path, source)
            self.assertEqual((result["source"]["sha256"], [row["text"] for row in result["lines"]],
                              json.dumps(source, sort_keys=True), result["import_complete"]),
                             (hashlib.sha256(path.read_bytes()).hexdigest(),
                              ["before", "[2001.02.03-04.05.06:007][ 19]TLNetGame: Display: [Game]", "+n [17]", "[other] after"],
                              before, False))

    def test_changed_prefix_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event(17))
            source = snapshot(path)
            path.write_bytes(event(29))
            with self.assertRaisesRegex(ValueError, "source prefix"):
                collect(path, source)

    def test_appended_records_are_outside_the_bound_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event())
            source = snapshot(path)
            with path.open("ab") as stream:
                stream.write(b"[other] new private line\n")
            self.assertEqual([row["number"] for row in collect(path, source)["lines"]], [1, 2])

    def test_sensitive_markers_are_omitted_explicitly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), b"Authorization: Bearer SYNTHETIC-CREDENTIAL\n" + event())
            result = collect(path, snapshot(path))
            self.assertEqual((result["lines"][0]["omission"], "SYNTHETIC-CREDENTIAL" in json.dumps(result),
                              result["status"]), ("sensitive_marker", False, "partial"))

    def test_oversized_context_lines_are_not_silently_truncated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), b"x" * 4097 + b"\n" + event())
            result = collect(path, snapshot(path))
            self.assertEqual((result["lines"][0]["omission"], result["status"]), ("line_limit", "partial"))

    def test_context_windows_share_lines_without_merging_events(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event(17) + event(29))
            result = collect(path, snapshot(path))
            self.assertEqual((len(result["events"]), len(result["lines"]), result["events_merged"]), (2, 4, False))

    def test_rejected_tree_context_is_preserved_as_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event().split(b"\n")[0] + b"\nnot a tree\n")
            result = collect(path, snapshot(path))
            self.assertEqual((result["events"][0]["parser_status"], result["lines"][1]["text"]),
                             ("rejected", "not a tree"))

    def test_unicode_neighbours_remain_lexical_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), "синтетический контекст\n".encode() + event())
            self.assertEqual(collect(path, snapshot(path))["lines"][0]["text"], "синтетический контекст")

    def test_no_events_does_not_prove_no_character_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), b"ordinary record\n")
            result = collect(path, snapshot(path))
            self.assertEqual((result["status"], result["identity"]), ("no_events", "unknown"))

    def test_context_includes_exactly_twenty_physical_neighbours_on_each_side(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), b"[other] before\n" * 31 + event() + b"[other] after\n" * 37)
            self.assertEqual([row["number"] for row in collect(path, snapshot(path))["lines"]], list(range(12, 54)))

    def test_event_cap_is_reported_without_merging_or_choosing_a_build(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), b"".join(event(value) for value in range(21)))
            result = collect(path, snapshot(path))
            self.assertEqual((len(result["events"]), result["omitted_events"], result["status"], result["identity"]),
                             (20, 1, "partial", "unknown"))

    def test_line_cap_counts_unretained_window_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event() + b"+n [1]\n" * 20_025)
            result = collect(path, snapshot(path))
            self.assertEqual((len(result["lines"]), result["unretained_lines"], result["status"]), (20_000, 27, "partial"))

    def test_retained_byte_cap_preserves_explicit_omissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event() + (b"+n [" + b"x" * 490 + b"]\n") * 10_000)
            result = collect(path, snapshot(path))
            self.assertEqual((result["retained_bytes"] <= 4 << 20,
                              any(row.get("omission") == "retained_limit" for row in result["lines"]),
                              result["status"]), (True, True, "partial"))

    def test_serialized_artifact_limit_includes_json_escape_expansion(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event() + (b"+n [" + b"\x01" * 490 + b"]\n") * 3000)
            with self.assertRaisesRegex(ValueError, "artifact byte limit"):
                collect(path, snapshot(path))

    def test_incomplete_final_line_is_explicitly_omitted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event() + b"[other] unfinished")
            result = collect(path, snapshot(path))
            self.assertEqual((result["lines"][-1]["omission"], result["status"]), ("incomplete_final_line", "partial"))

    def test_invalid_utf8_context_is_explicitly_omitted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), b"\xff\n" + event())
            self.assertEqual(collect(path, snapshot(path))["lines"][0]["omission"], "encoding")

    def test_shrunk_source_prefix_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event())
            source = snapshot(path)
            path.write_bytes(b"short")
            with self.assertRaisesRegex(ValueError, "source prefix shrank"):
                collect(path, source)

    def test_boolean_event_coordinates_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = log(Path(folder), event())
            source = snapshot(path)
            source["events"][0]["start_line"] = True
            with self.assertRaisesRegex(ValueError, "event bounds"):
                collect(path, source)
