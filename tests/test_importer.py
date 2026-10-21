"""Import local packages without developer observations or combat assumptions."""

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from damage_lab.importer import main
from examples.make_fixture import fixture


def record():
    return {
        "name": "Synthetic import", "capturedAt": "2001-02-03T04:05:06Z",
        "character": "Synthetic Carino", "synthetic": True, "source_sha256": "a" * 64,
        "import_status": "partial", "missing_stats": ["cast_rate"],
        "stats": {"spell_dps": 84317}, "benchmark": {"survival": 9217},
        "observations": [{"key": "spell_dps", "label": "Spell DPS", "value": 84317,
                          "unit": "damage/s", "evidence": "native fixture", "precision": "exact integer"}],
        "inventory": {"gear": [{"name": "Synthetic wand", "details": ["Fictional modifier"]}]},
        "coverage": ["Synthetic unmapped effect"],
        "native_stats": {"format": "tli-native-stats-v1", "status": "decoded", "known": 2,
                         "protocol_verified": False, "unknown_stat_ids": 1},
        "facts": {"patch": "SS14", "checkedAt": "2001-02-03", "sources": {}},
    }


def archive(package, observations, facts, database, **inputs):
    if observations is not None:
        raise ValueError("Import must not require developer observations")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE fixture (value INTEGER)")
    return record()


class ImporterTests(unittest.TestCase):
    """User imports preserve partial data instead of inventing a damage total."""

    def test_import_preserves_available_optional_armor_penetration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data["stats"]["armor_penetration"] = 0.1375
                data["observations"].append({
                    "key": "armor_penetration", "label": "Armor DMG Mitigation Penetration", "value": 0.1375,
                    "unit": "fraction", "evidence": "synthetic-game.log", "precision": "exact synthetic value",
                })
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result")], archiver=source)
            result = json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
            self.assertEqual((result["stats"]["armor_penetration"], result["observations"][-1]["key"],
                              result["missing_stats"]), (0.1375, "armor_penetration", ["cast_rate"]))

    def test_game_log_is_passed_directly_to_the_automatic_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "game.log"
            path.write_text("71423", encoding="utf-8")

            def source(package, observations, facts, database, *, game_log):
                data = archive(package, observations, facts, database)
                data["stats"]["spell_dps"] = int(game_log.read_text(encoding="utf-8"))
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result"),
                      "--game-log", str(path)], archiver=source)
            self.assertEqual(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                             ["stats"]["spell_dps"], 71423)

    def test_import_cannot_choose_both_raw_and_normalized_log_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(SystemExit, "2"):
                    main(["--package", str(root), "--output", str(root / "result"),
                          "--game-log", "game.log", "--panel-log", "panel.json"], archiver=archive)

    def test_import_preserves_the_log_input_kind_without_its_private_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data["panel_log"] = {
                    "format": "tli-panel-log-v1", "status": "corroborated", "known": 9,
                    "unknown_attributes": 17, "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                    "identity_verified": False, "source_sha256": "b" * 64,
                    "input_kind": "game_log", "source_path": "PRIVATE-MARKER",
                }
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result")], archiver=source)
            result = json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
            self.assertEqual((result["panel_log"]["input_kind"], "PRIVATE-MARKER" in json.dumps(result)),
                             ("game_log", False))

    def test_import_keeps_catalog_skill_parameters_without_extra_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data["skill_values"] = [{
                    "group": 1, "position": 0, "role": "main", "name": "Fictional skill", "level": 17,
                    "description_status": "level_one", "description_level": 1, "status": "resolved",
                    "values": {"damage": 139.5}, "cells": {"damage": "279/2"}, "issues": [],
                    "source": {"catalogPath": "synthetic/catalog.json", "seasonId": 14, "tlidbId": 7007,
                               "guid": "synthetic-skill", "field": "damage", "raw": "PRIVATE-MARKER"},
                    "raw": "PRIVATE-MARKER",
                }]
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result")], archiver=source)
            result = json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
            self.assertEqual(result["skill_values"], [{
                "group": 1, "position": 0, "role": "main", "name": "Fictional skill", "level": 17,
                "description_status": "level_one", "description_level": 1, "status": "resolved",
                "values": {"damage": 139.5}, "cells": {"damage": "279/2"}, "issues": [],
                "source": {"catalogPath": "synthetic/catalog.json", "seasonId": 14, "tlidbId": 7007,
                           "guid": "synthetic-skill", "field": "damage"},
            }])

    def test_panel_observation_keeps_only_safe_row_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data["observations"][0]["source"] = {
                    "attr_id": 271, "index": 4, "raw_value": 71423, "raw_values": ["71423", "71423.0"],
                    "timestamp": "2001.02.03-04.05.06", "frame": 319, "line_numbers": [17, 23],
                    "raw": "PRIVATE-MARKER",
                }
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result")], archiver=source)
            self.assertEqual(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                             ["observations"][0]["source"], {
                "attr_id": 271, "index": 4, "raw_value": 71423, "raw_values": ["71423", "71423.0"],
                "timestamp": "2001.02.03-04.05.06", "frame": 319, "line_numbers": [17, 23],
            })

    def test_panel_log_is_passed_to_the_automatic_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "panel.log"
            path.write_text("71423", encoding="utf-8")

            def source(package, observations, facts, database, *, panel_log):
                data = archive(package, observations, facts, database)
                data["stats"]["spell_dps"] = int(panel_log.read_text(encoding="utf-8"))
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result"),
                      "--panel-log", str(path)], archiver=source)
            self.assertEqual(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                             ["stats"]["spell_dps"], 71423)

    def test_panel_log_summary_keeps_evidence_without_raw_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data["panel_log"] = {
                    "format": "synthetic-panel-selection", "status": "selected", "known": 9,
                    "unknown_attributes": 17, "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                    "identity_verified": False, "source_sha256": "b" * 64, "accountId": "PRIVATE-MARKER",
                    "raw": "PRIVATE-MARKER",
                }
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result")], archiver=source)
            self.assertEqual(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                             ["panel_log"], {
                "format": "synthetic-panel-selection", "status": "selected", "known": 9,
                "unknown_attributes": 17, "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                "identity_verified": False, "source_sha256": "b" * 64,
            })

    def test_import_writes_a_partial_record_without_manual_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root / "package"), "--output", str(root / "result")], archiver=archive)
            self.assertEqual(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                             ["import_status"], "partial")

    def test_import_creates_a_standalone_report_and_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root / "package"), "--output", str(root / "result")], archiver=archive)
            self.assertTrue((root / "result" / "database.sqlite").is_file()
                            and "Боевой DPS пока недоступен" in (root / "result" / "index.html").read_text(encoding="utf-8"))

    def test_import_json_omits_raw_sections_and_account_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data.update(sourceSections={"payload": "PRIVATE-MARKER"}, accountId="PRIVATE-MARKER")
                data["inventory"]["gear"][0]["accountId"] = "PRIVATE-MARKER"
                data["native_stats"]["raw"] = "PRIVATE-MARKER"
                return data

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root / "package"), "--output", str(root / "result")], archiver=source)
            self.assertNotIn("PRIVATE-MARKER", (root / "result" / "import.json").read_text(encoding="utf-8"))

    def test_import_cannot_claim_complete_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data["import_status"] = "complete"
                return data

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--package", str(root), "--output", str(root / "result")], archiver=source), 1)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "result").mkdir()
            (root / "result" / "keep.txt").write_text("preserved", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result")], archiver=archive)
            self.assertEqual((root / "result" / "keep.txt").read_text(encoding="utf-8"), "preserved")

    def test_invalid_package_does_not_leave_partial_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                database.write_bytes(b"partial stage")
                raise ValueError("Synthetic invalid capture")

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result")], archiver=source)
            self.assertEqual(list(root.iterdir()), [])

    def test_native_stats_path_is_passed_to_the_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database, *, native_stats):
                data = archive(package, observations, facts, database)
                data["stats"]["spell_dps"] = int(native_stats.read_text(encoding="utf-8"))
                return data

            (root / "native.json").write_text("93187", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--output", str(root / "result"),
                      "--native-stats", str(root / "native.json")], archiver=source)
            self.assertEqual(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                             ["stats"]["spell_dps"], 93187)

    def test_stdout_reports_partial_import_without_claiming_a_damage_total(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(["--package", str(root), "--output", str(root / "result")], archiver=archive)
            self.assertIn("Частичный импорт", output.getvalue())

    def test_real_synthetic_package_import_does_not_require_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root / "input")
            (root / "input" / "observations.json").unlink()
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root / "input"), "--output", str(root / "result")])
            data = json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
            self.assertEqual((data["stats"], data["benchmark"], data["import_status"]), ({}, {}, "partial"))

    def test_invalid_import_structure_has_a_bounded_error_without_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def source(package, observations, facts, database):
                data = archive(package, observations, facts, database)
                data["inventory"] = None
                return data

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--package", str(root), "--output", str(root / "result")], archiver=source), 1)
