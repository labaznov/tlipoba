import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from damage_lab.__main__ import main
from examples.make_fixture import fixture


class DamageCliTests(unittest.TestCase):
    """Check CLI outputs with an isolated local archive fake."""

    def test_cli_passes_the_automatic_stats_file_to_the_importer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "native.json").write_text('{"spell_dps": 9173}', encoding="utf-8")

            def archive(package, observations, facts, database, *, native_stats):
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture (value INTEGER)")
                return {"name": "Automatic fixture", "native_stats": {"known": 1}, "stats": {
                    **json.loads(native_stats.read_text(encoding="utf-8")), "max_tangles": 3,
                    "extra_attachments": 2, "cold_penetration": 0.13}}

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--observations", "absent.json", "--facts", "absent.json",
                      "--output", str(root / "result"), "--basis", "panel", "--active", "3",
                      "--hits", "7", "--retention", "0.2", "--resistance", "0.47",
                      "--taken", "0.19", "--uptime", "0.83", "--native-stats", str(root / "native.json")],
                     archiver=archive)
            result = json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))
            self.assertEqual((result["calculation"]["single_projectile_dps"], result["native_stats"]),
                             (9173, {"known": 1}))

    def test_cli_applies_reference_relative_combat_to_the_report_and_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root / "input")
            context = {"reference": {"damage": [], "cast": [], "taken": []},
                       "target": {"damage": [{"id": "heat", "affix": "heat", "value": 0.37,
                                             "stacks": 1, "mode": "add"}], "cast": [], "taken": []},
                       "tick_frequency": None, "armor": 0, "nonphysical": True,
                       "missing": ["Heat uptime"], "notes": ["Synthetic combat"]}
            (root / "combat.json").write_text(json.dumps(context), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root / "input"), "--observations", str(root / "input" / "observations.json"),
                      "--facts", "damage_lab/data/tlidb-ss14.json", "--output", str(root / "result"),
                      "--basis", "panel", "--active", "2", "--hits", "3", "--retention", "0.2",
                      "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87",
                      "--combat", str(root / "combat.json")])
            result = json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))
            self.assertEqual((result["calculation"]["combat"]["damage_ratio"],
                              result["condition"]["combat"],
                              "Synthetic combat" in (root / "result" / "index.html").read_text(encoding="utf-8")),
                             (1.37, context, True))

    def test_cli_keeps_benchmark_comparison_separate_from_calculation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root / "input")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root / "input"), "--observations", str(root / "input" / "observations.json"),
                      "--facts", "damage_lab/data/tlidb-ss14.json", "--output", str(root / "result"),
                      "--basis", "panel", "--active", "2", "--hits", "3", "--retention", "0.2",
                      "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
            result = json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))
            self.assertEqual(result["validation"]["difference"],
                             result["calculation"]["dps"] - result["benchmark"]["average_dps"])

    def test_json_keeps_the_synthetic_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root / "input")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root / "input"), "--observations", str(root / "input" / "observations.json"),
                      "--facts", "damage_lab/data/tlidb-ss14.json", "--output", str(root / "result"),
                      "--basis", "panel", "--active", "2", "--hits", "3", "--retention", "0.2",
                      "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
            self.assertIs(json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))["synthetic"], True)

    def test_cli_writes_calculation_and_standalone_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def archive(package, observations, facts, database):
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture (value INTEGER)")
                return {"name": "Odd build", "character": "Carino", "stats": {
                    "spell_dps": 379, "max_tangles": 3, "extra_attachments": 2,
                    "cold_penetration": 0.13}, "inventory": {}, "coverage": []}

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--observations", str(root / "observations.json"),
                      "--facts", str(root / "facts.json"), "--output", str(root / "result"),
                      "--hits", "7", "--retention", "0.2", "--active", "3", "--resistance", "0.47",
                      "--taken", "0.19", "--uptime", "0.83", "--basis", "panel"], archiver=archive)
            result = json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))
            self.assertEqual((round(result["calculation"]["dps"], 7),
                              (root / "result" / "database.sqlite").exists(),
                              "Условный расчёт" in (root / "result" / "index.html").read_text(encoding="utf-8")),
                             (1630.6176348, True, True))

    def test_cli_cannot_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([
                    "--package", folder, "--observations", "absent.json", "--facts", "absent.json",
                    "--output", folder, "--hits", "7", "--retention", "0.2", "--active", "3",
                    "--resistance", "0.47", "--taken", "0.19", "--uptime", "0.83", "--basis", "panel",
                ]), 1)

    def test_cli_does_not_leave_output_after_invalid_scenario(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def archive(package, observations, facts, database):
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture (value INTEGER)")
                return {"name": "Odd build", "stats": {"spell_dps": 379, "max_tangles": 3,
                        "extra_attachments": 2, "cold_penetration": 0.13}}

            with contextlib.redirect_stderr(io.StringIO()):
                main(["--package", str(root), "--observations", "absent.json", "--facts", "absent.json",
                      "--output", str(root / "result"), "--hits", "7", "--retention", "0.2",
                      "--active", "19", "--resistance", "0.47", "--taken", "0.19",
                      "--uptime", "0.83", "--basis", "panel"], archiver=archive)
            self.assertFalse((root / "result").exists())
