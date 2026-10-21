import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from damage_lab.panellog import CHUNK, harvest, main, read


def log(body, frame=713, second=19):
    return f"[2026.10.17-12.31.{second:02}:427][{frame:3}]TLLua: Display: [Game] RoleAttrMgr@{body}"


def rows(name="Spell DPS", stat=10103, token="7123.456789"):
    return [log(f"Attri.Id  {name}  {stat}"), log(f"[1] = {token}")]


def run(arguments):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main([str(argument) for argument in arguments])


class PanelLogTest(unittest.TestCase):
    """Ordinary log pairs provide exact numbers without importing unrelated game messages."""

    def test_raw_decimal_tokens_are_preserved(self):
        self.assertEqual(harvest(rows())["cohorts"][0]["attributes"][0]["raw_values"], ["7123.456789"])

    def test_ranges_preserve_index_order(self):
        data = [log("Attri.Id  Total Spell Damage  11800"), log("[1] = 3.71e2, [2] = 923.61")]
        self.assertEqual(harvest(data)["cohorts"][0]["attributes"][0]["values"], [371.0, 923.61])

    def test_values_in_another_frame_cannot_complete_an_attribute(self):
        data = [rows()[0], log("[1] = 7123.456789", frame=714)]
        self.assertEqual(harvest(data)["cohorts"][0]["attributes"][0]["status"], "unresolved")

    def test_duplicate_ids_cannot_replace_earlier_values(self):
        self.assertEqual(harvest(rows() + rows(token="8123.45"))["cohorts"][0]["status"], "partial")

    def test_unrelated_identifiers_are_not_retained(self):
        self.assertNotIn("private-canary", json.dumps(harvest([rows()[0], "Account private-canary", rows()[1]])))

    def test_nonfinite_tokens_cannot_be_resolved(self):
        for token in ("NaN", "1e999", "inf", "3abc"):
            with self.subTest(token=token):
                self.assertEqual(harvest(rows(token=token))["cohorts"][0]["status"], "partial")

    def test_overflowing_integer_tokens_cannot_be_resolved(self):
        self.assertEqual(harvest(rows(token="9" * 400))["cohorts"][0]["status"], "partial")

    def test_nonzero_tokens_cannot_underflow_to_resolved_zero(self):
        self.assertEqual(harvest(rows(token="1e-999"))["cohorts"][0]["status"], "partial")

    def test_unrecognized_panel_lines_break_header_binding(self):
        data = [rows()[0], log("new unknown panel record"), rows()[1]]
        self.assertEqual(harvest(data)["cohorts"][0]["status"], "partial")

    def test_backwards_timestamps_cannot_combine_separate_states(self):
        data = rows() + [log("Attri.Id  Total Spell Damage  11800", second=1),
                         log("[1] = 371, [2] = 923", second=1)]
        self.assertEqual(len(harvest(data)["cohorts"]), 2)

    def test_values_earlier_than_the_header_cannot_bind(self):
        data = [rows()[0], log("[1] = 7123.456789", second=18)]
        self.assertEqual(harvest(data)["cohorts"][0]["status"], "partial")

    def test_appended_lines_are_outside_the_opened_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "game.log"
            original = ("synthetic padding\n" * CHUNK).encode()
            source.write_bytes(original)
            digest, metadata = hashlib.sha256(), {}
            iterator = read(source, digest, metadata)
            next(iterator)
            with source.open("ab") as handle:
                handle.write(b"late-private-canary\n")
            list(iterator)
            self.assertEqual((metadata["bytesRead"], digest.hexdigest()),
                             (len(original), hashlib.sha256(original).hexdigest()))

    def test_truncated_sources_cannot_produce_a_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "game.log"
            source.write_bytes(b"synthetic padding\n" * CHUNK)
            iterator = read(source, hashlib.sha256(), {})
            next(iterator)
            with source.open("r+b") as handle:
                handle.truncate(31)
            with self.assertRaisesRegex(ValueError, "shrank"):
                list(iterator)

    def test_unterminated_values_cannot_complete_a_header(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "game.log", Path(folder) / "panel.json"
            source.write_text("\n".join(rows()), encoding="utf-8")
            run([source, target])
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["cohorts"][0]["status"], "partial")

    def test_new_output_has_source_hash_and_unverified_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "game.log", Path(folder) / "panel.json"
            source.write_text("\n".join(rows()) + "\n", encoding="utf-8")
            run([source, target])
            result = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual((result["source"]["sha256"], result["identity"]["status"]),
                             (hashlib.sha256(source.read_bytes()).hexdigest(), "unverified"))

    def test_existing_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "game.log", Path(folder) / "panel.json"
            source.write_text("\n".join(rows()) + "\n", encoding="utf-8")
            target.write_text("keep", encoding="utf-8")
            run([source, target])
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
