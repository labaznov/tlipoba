import contextlib
import copy
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from damage_lab.__main__ import main
from examples.make_fixture import fixture


class DamageCliTests(unittest.TestCase):
    """Check CLI outputs with isolated archives and synthetic packages."""

    def test_conditional_command_routes_to_its_automatic_import_interface(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['conditional-combat', '--help']), 0)

    def test_fixed_implicit_proof_survives_calculation_json_and_sqlite_without_reapplying_damage(self):
        from test_damage_archive import facts, observations, package
        from test_staticbundle import fixed_bundle

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "with-implicit"):
                if name == "with-implicit":
                    fixed_bundle(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            ledger = results[1]["static_combat"]
            with contextlib.closing(sqlite3.connect(root / "with-implicit/database.sqlite")) as connection:
                stored = json.loads(connection.execute("SELECT json FROM documents WHERE role='static_combat'").fetchone()[0])
            self.assertEqual((results[1]["calculation"], stored, ledger["modifiers"][0]["fixed_implicit"]["arithmetic_ready"]),
                             (results[0]["calculation"], ledger, False))

    def test_passive_candidates_survive_json_and_sqlite_without_reapplying_their_damage(self):
        from test_damage_archive import facts, observations, package
        from test_skillcatalogbundle import focus

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "with-focus"):
                if name == "with-focus":
                    focus(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            profiles = results[1]["installed_skill_profiles"]
            with contextlib.closing(sqlite3.connect(root / "with-focus/database.sqlite")) as connection:
                stored = json.loads(connection.execute("SELECT json FROM documents WHERE role='installed_skill_profiles'").fetchone()[0])
            self.assertEqual((results[1]["calculation"], stored, profiles["members"][0]["passive_effect"]["candidate"]["value"]["fraction"]),
                             (results[0]["calculation"], profiles, {"numerator": -13, "denominator": 800}))

    def test_memory_definitions_reach_calculation_json_without_reapplying_damage(self):
        from test_damage_archive import attachedmemories, facts, observations, package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "with-memories"):
                if name == "with-memories":
                    attachedmemories(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            self.assertEqual((results[1]["calculation"], results[1]["memory_definitions"]["ledger"]["arithmetic_ready"],
                              results[1]["memory_definitions"]["ledger"]["accounting"]["candidates"]),
                             (results[0]["calculation"], False, 1))

    def test_level_candidates_are_preserved_without_changing_the_conditional_damage(self):
        from test_damage_archive import attachedlevels, facts, observations, package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "with-levels"):
                if name == "with-levels":
                    attachedlevels(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            self.assertEqual((results[1]["calculation"], results[1]["installed_level_candidates"]["accounting"]["targets"],
                              results[1]["installed_level_candidates"]["arithmetic_ready"]), (results[0]["calculation"], 4, False))

    def test_inputs_command_needs_no_manual_character_stats_or_combat_parameters(self):
        from test_damage_archive import package
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            path = package(root)
            attached(path)
            status = main(["inputs", "--package", str(path), "--skill", "gem[1]", "--output", str(root / "result")])
            report = json.loads((root / "result/inputs.json").read_text(encoding="utf-8"))
            self.assertEqual((status, report["selection"]["alias"], report["skill"]["skill_id"], report["raw_spell"],
                              (root / "result/index.html").is_file(), (root / "result/database.sqlite").is_file()),
                             (0, "gem[1]", 90017, None, True, True))

    def test_catalog_profiles_are_preserved_without_changing_the_calculated_damage(self):
        from test_damage_archive import facts, observations, package
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "with-profiles"):
                if name == "with-profiles":
                    attached(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            self.assertEqual((results[1]["calculation"], results[1]["installed_skill_profiles"]["members"][0]["effective_level"],
                              results[1]["installed_skill_profiles"]["arithmetic_ready"]),
                             (results[0]["calculation"], None, False))

    def test_support_effect_diagnostics_are_preserved_without_reapplying_damage(self):
        from test_damage_archive import facts, observations, package
        from test_supportbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "with-supports"):
                if name == "with-supports":
                    attached(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            self.assertEqual((results[1]["calculation"], results[1]["installed_support_effects"]["arithmetic_ready"],
                              results[1]["installed_support_catalog"]["network_bytes_verified"]),
                             (results[0]["calculation"], False, False))

    def test_combat_upgrade_command_publishes_complete_comparison_without_panel_parameters(self):
        from test_combatupgrades import scenario

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "scenario.json"
            source.write_text(json.dumps(scenario()), encoding="utf-8")
            code = main(["combat-upgrades", "--scenario", str(source), "--output", str(root / "result")])
            report = json.loads((root / "result/comparison.json").read_text(encoding="utf-8"))
            self.assertEqual((code, report["ranking"], round(report["baseline"]["dps"], 2),
                              (root / "result/index.html").is_file()), (0, ["hit", "topology"], 291.06, True))

    def test_log_import_command_needs_no_package_or_combat_parameters(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            (root / "input.log").write_bytes(b"ordinary unrelated log line\r\n")
            code = main(["import-log", "--game-log", str(root / "input.log"), "--output", str(root / "result")])
            data = json.loads((root / "result/log-import.json").read_text(encoding="utf-8"))
            self.assertEqual((code, data["import_complete"], data["events"]), (0, False, []))

    def test_static_gear_ledger_is_preserved_without_reapplying_its_damage(self):
        from test_damage_archive import facts, observations, package
        from test_skillbundle import attached
        from test_staticbundle import critical_bundle

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "with-ledger"):
                if name == "with-ledger":
                    critical_bundle(path)
                    attached(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            self.assertEqual((results[1]["calculation"], results[1]["static_combat"]["runtime"]["verified"],
                              results[1]["static_combat_provenance"]["documents"][0]["byte_range"],
                              results[1]["static_combat"]["modifiers"][0]["semantics"]["arithmetic_ready"],
                              results[1]["installed_skills"]["runtime"]["activation"]),
                             (results[0]["calculation"], False, [17, 319], False, "unknown"))

    def test_calculation_preserves_unknown_freshness_after_a_saved_code_match(self):
        from test_damage_archive import facts, observations, package, resolution_bundle

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            resolution_bundle(path)
            main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                  "--output", str(root / "result"), "--basis", "panel", "--active", "2", "--hits", "3",
                  "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
            self.assertEqual(json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))
                             ["build_resolution"]["freshness"]["status"], "unknown")

    def test_calculation_keeps_the_audit_without_altering_the_damage(self):
        from test_damage_archive import coverage_bundle, facts, observations, package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            results = []
            for name in ("before", "audited"):
                if name == "audited":
                    coverage_bundle(path)
                main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                      "--output", str(root / name), "--basis", "panel", "--active", "2", "--hits", "3",
                      "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
                results.append(json.loads((root / name / "calculation.json").read_text(encoding="utf-8")))
            self.assertEqual((results[1]["import_coverage"]["import_complete"], results[1]["calculation"]["dps"]),
                             (False, results[0]["calculation"]["dps"]))

    def test_calculation_preserves_rank_candidates_without_applying_a_rank(self):
        from test_damage_archive import facts, observations, package, trait_bundle

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            trait_bundle(path)
            main(["--package", str(path), "--observations", str(observations(root)), "--facts", str(facts(root)),
                  "--output", str(root / "result"), "--basis", "panel", "--active", "2", "--hits", "3",
                  "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"])
            self.assertEqual([row["rank"] for row in json.loads(
                (root / "result" / "calculation.json").read_text(encoding="utf-8"))["trait_ranks"]["traits"]],
                             [None, None])

    def test_game_log_allows_conditional_calculation_without_intermediate_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "game.log").write_text("71423", encoding="utf-8")

            def source(package, observations, facts, database, *, game_log):
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture (value INTEGER)")
                return {"name": "Automatic raw fixture", "synthetic": True, "stats": {
                    "spell_dps": int(game_log.read_text(encoding="utf-8")), "hit_min": 913,
                    "hit_max": 1437, "cast_rate": 4.73, "crit_chance": 0.4137, "crit_multiplier": 2.87,
                    "max_tangles": 2, "extra_attachments": 1, "cold_penetration": 0.07},
                    "panel_log": {"format": "tli-panel-log-v1", "status": "corroborated", "known": 9,
                                  "unknown_attributes": 17, "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                                  "identity_verified": False, "source_sha256": "b" * 64,
                                  "input_kind": "game_log"}}

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--facts", "fixture.json", "--output", str(root / "result"),
                      "--game-log", str(root / "game.log"), "--basis", "panel", "--active", "2",
                      "--hits", "3", "--retention", "0.2", "--resistance", "0.23",
                      "--taken", "0.11", "--uptime", "0.87"], archiver=source)
            result = json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))
            self.assertEqual((result["status"], result["condition"]["observations_provided"],
                              result["calculation"]["single_projectile_dps"], result["panel_log"]["input_kind"]),
                             ("conditional", False, 71423, "game_log"))

    def test_calculation_cannot_choose_both_raw_and_normalized_log_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(SystemExit, "2"):
                    main(["--package", str(root), "--facts", "fixture.json", "--output", str(root / "result"),
                          "--game-log", "game.log", "--panel-log", "panel.json", "--basis", "panel",
                          "--active", "2", "--hits", "3", "--retention", "0.2", "--resistance", "0.23",
                          "--taken", "0.11", "--uptime", "0.87"],
                         archiver=lambda package, observations, facts, database, **inputs: {"stats": {}})

    def test_panel_log_allows_conditional_calculation_without_manual_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "panel.log").write_text("71423", encoding="utf-8")

            def source(package, observations, facts, database, *, panel_log):
                if observations is not None:
                    raise ValueError("Unexpected manual observations")
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture (value INTEGER)")
                return {"name": "Automatic fixture", "synthetic": True, "stats": {
                    "spell_dps": int(panel_log.read_text(encoding="utf-8")), "hit_min": 913,
                    "hit_max": 1437, "cast_rate": 4.73, "crit_chance": 0.4137, "crit_multiplier": 2.87,
                    "max_tangles": 2, "extra_attachments": 1, "cold_penetration": 0.07},
                    "panel_log": {"format": "synthetic-panel-selection", "status": "corroborated", "known": 9,
                                  "unknown_attributes": 17, "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                                  "identity_verified": False, "source_sha256": "b" * 64,
                                  "raw": "PRIVATE-MARKER"}}

            with contextlib.redirect_stdout(io.StringIO()):
                main(["--package", str(root), "--facts", "fixture.json", "--output", str(root / "result"),
                      "--panel-log", str(root / "panel.log"), "--basis", "panel", "--active", "2",
                      "--hits", "3", "--retention", "0.2", "--resistance", "0.23",
                      "--taken", "0.11", "--uptime", "0.87"], archiver=source)
            result = json.loads((root / "result" / "calculation.json").read_text(encoding="utf-8"))
            self.assertEqual((result["status"], result["condition"]["observations_provided"],
                              result["calculation"]["single_projectile_dps"], result["panel_log"]),
                             ("conditional", False, 71423, {
                                 "format": "synthetic-panel-selection", "status": "corroborated", "known": 9,
                                 "unknown_attributes": 17, "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                                 "identity_verified": False, "source_sha256": "b" * 64}))

    def test_automatic_calculation_reports_missing_stats_before_calculating(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def source(package, observations, facts, database):
                if observations is not None:
                    raise ValueError("Developer observations were not requested")
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture (value INTEGER)")
                return {"name": "Sparse fixture", "stats": {"spell_dps": 71423}}

            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                main(["--package", str(root), "--facts", "fixture.json", "--output", str(root / "result"),
                      "--basis", "panel", "--active", "2", "--hits", "3", "--retention", "0.2",
                      "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87"], archiver=source)
            self.assertIn("Не хватает автоматически извлечённых показателей", errors.getvalue())

    def test_import_subcommand_routes_without_calculation_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def source(package, observations, facts, database):
                if observations is not None:
                    raise ValueError("Unexpected developer input")
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE fixture (value INTEGER)")
                return {"name": "Sparse route fixture", "import_status": "partial", "missing_stats": ["cast_rate"],
                        "coverage": ["Unknown effect"], "stats": {"spell_dps": 84317}, "benchmark": {}, "inventory": {}}

            with contextlib.redirect_stdout(io.StringIO()):
                main(["import", "--package", str(root), "--output", str(root / "result")], archiver=source)
            self.assertEqual(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                             ["stats"], {"spell_dps": 84317})

    def test_module_import_command_reads_sys_argv_without_developer_parameters(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root / "input")
            (root / "input" / "observations.json").unlink()
            result = subprocess.run([
                sys.executable, "-m", "damage_lab", "import", "--package", str(root / "input"),
                "--output", str(root / "result"),
            ], capture_output=True, text=True, encoding="utf-8", timeout=20,
               cwd=Path(__file__).resolve().parents[1], env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual((result.returncode, (root / "result" / "import.json").is_file()), (0, True))

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


class StalePanelWarningTests(unittest.TestCase):
    """The newer conflicting panel state survives into machine-facing calculation JSON."""

    ARGS = ("--basis", "panel", "--active", "2", "--hits", "3",
            "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87")

    def calculation(self, root, name, package_path, native_path, panel_path):
        from test_damage_archive import facts

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = main(["--package", str(package_path), "--native-stats", str(native_path),
                         "--panel-log", str(panel_path), "--facts", str(facts(root)),
                         "--output", str(root / name), *self.ARGS])
        if code != 0:
            return code, None
        return code, json.loads((root / name / "calculation.json").read_text(encoding="utf-8"))

    def stale_package(self, root):
        from test_damage_archive import native, package, panel as written

        path = package(root)
        document = json.loads(written(root, "43721").read_text(encoding="utf-8"))
        newer = copy.deepcopy(document["cohorts"][0])
        newer.update(timestamp="2001-02-03T04:05:09.000Z", frame=715)
        newer["attributes"][0].update(values=[99999.0], raw_values=["99999"])
        document["cohorts"].append(newer)
        (root / "stale-panel.json").write_text(json.dumps(document), encoding="utf-8")
        return path, native(root, path), root / "stale-panel.json"

    def test_a_newer_conflicting_panel_reaches_calculation_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package_path, native_path, panel_path = self.stale_package(root)
            code, result = self.calculation(root, "stale", package_path, native_path, panel_path)
            self.assertEqual(code, 0)
            self.assertEqual((result["status"], result["panel_log"]["identity_verified"],
                              result["panel_log"]["newer_state_conflict"]),
                             ("conditional", False, True))
            self.assertIn("does not verify the current state", result["panel_log"]["stale_selection_warning"])
            self.assertIn(result["panel_log"]["cohort"]["timestamp"], ("2001-02-03T04:05:07.000Z",))

    def test_an_ordinary_panel_reports_no_conflict(self):
        from test_damage_archive import native, package, panel as written

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = package(root)
            code, result = self.calculation(root, "ordinary", path, native(root, path), written(root, "43721"))
            self.assertEqual(code, 0)
            self.assertIsNone(result["panel_log"]["newer_state_conflict"])
            self.assertIn("current-state comparison is unknown",
                          result["panel_log"]["stale_selection_warning"])

    def test_logsummary_refuses_forged_warning_text(self):
        from damage_lab.importer import logsummary

        base = {"format": "tli-panel-log-v1", "status": "corroborated", "known": 8, "unknown_attributes": 0,
                "identity_verified": False, "source_sha256": "b" * 64,
                "cohort": {"timestamp": "2001-02-03T04:05:07.000Z", "frame": 713},
                "newer_state_conflict": "yes", "stale_selection_warning": None}
        with self.assertRaisesRegex(ValueError, "boolean"):
            logsummary(base)
        forged = dict(base, newer_state_conflict=True, stale_selection_warning="player swapped skills")
        with self.assertRaisesRegex(ValueError, "fixed contract"):
            logsummary(forged)
        legacy = {key: value for key, value in base.items()
                  if key not in ("newer_state_conflict", "stale_selection_warning")}
        projected = logsummary(legacy)
        self.assertNotIn("newer_state_conflict", projected)
        self.assertNotIn("stale_selection_warning", projected)
        bare = {key: value for key, value in base.items()
                if key not in ("newer_state_conflict", "stale_selection_warning")}
        with self.assertRaisesRegex(ValueError, "together"):
            logsummary({**bare, "newer_state_conflict": True})
        with self.assertRaisesRegex(ValueError, "together"):
            logsummary({**bare, "stale_selection_warning": None})
        from damage_lab.logstats import CONFLICT_WARNING
        with self.assertRaisesRegex(ValueError, "agree"):
            logsummary({**base, "newer_state_conflict": False,
                        "stale_selection_warning": CONFLICT_WARNING})
        consistent = logsummary({**base, "newer_state_conflict": False, "stale_selection_warning": None})
        self.assertEqual((consistent["newer_state_conflict"], consistent["stale_selection_warning"]),
                         (False, None))
        from damage_lab.logstats import UNKNOWN_WARNING as unknown
        accepted = logsummary({**base, "newer_state_conflict": None, "stale_selection_warning": unknown})
        self.assertEqual((accepted["newer_state_conflict"], accepted["stale_selection_warning"]),
                         (None, unknown))
        for pair in ((None, None), (None, CONFLICT_WARNING), (True, unknown)):
            with self.subTest(pair=pair):
                with self.assertRaisesRegex(ValueError, "agree"):
                    logsummary({**base, "newer_state_conflict": pair[0],
                                "stale_selection_warning": pair[1]})


class PartialCohortEndToEndTests(unittest.TestCase):
    """A newer partial differing cohort surfaces unknown, not conflict-free, in JSON."""

    ARGS = ("--basis", "panel", "--active", "2", "--hits", "3",
            "--retention", "0.2", "--resistance", "0.23", "--taken", "0.11", "--uptime", "0.87")

    def test_a_newer_partial_differing_cohort_reaches_calculation_json_as_unknown(self):
        from test_damage_archive import facts, native, package, panel as written

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = package(root)
            document = json.loads(written(root, "43721").read_text(encoding="utf-8"))
            newer = copy.deepcopy(document["cohorts"][0])
            newer.update(timestamp="2001-02-03T04:05:09.000Z", frame=715, status="partial")
            newer["attributes"][0].update(values=[99999.0], raw_values=["99999"])
            newer["attributes"][1].update(status="unresolved", values=None)
            document["cohorts"].append(newer)
            (root / "partial-panel.json").write_text(json.dumps(document), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["--package", str(path), "--native-stats", str(native(root, path)),
                             "--panel-log", str(root / "partial-panel.json"), "--facts", str(facts(root)),
                             "--output", str(root / "out"), *self.ARGS])
            self.assertEqual(code, 0)
            result = json.loads((root / "out" / "calculation.json").read_text(encoding="utf-8"))
            self.assertEqual((result["status"], result["panel_log"]["identity_verified"],
                              result["panel_log"]["newer_state_conflict"]),
                             ("conditional", False, None))
            self.assertIn("current-state comparison is unknown", result["panel_log"]["stale_selection_warning"])

    def test_a_snapshot_gap_reaches_calculation_json_as_unknown(self):
        from test_damage_archive import facts, native, package, panel as written

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = package(root)
            document = json.loads(written(root, "43721").read_text(encoding="utf-8"))
            document["gaps"].append(
                "Final line 40 was unterminated at the snapshot boundary and was not parsed.")
            (root / "gap-panel.json").write_text(json.dumps(document), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["--package", str(path), "--native-stats", str(native(root, path)),
                             "--panel-log", str(root / "gap-panel.json"), "--facts", str(facts(root)),
                             "--output", str(root / "out"), *self.ARGS])
            self.assertEqual(code, 0)
            result = json.loads((root / "out" / "calculation.json").read_text(encoding="utf-8"))
            self.assertIsNone(result["panel_log"]["newer_state_conflict"])
            self.assertIn("current-state comparison is unknown",
                          result["panel_log"]["stale_selection_warning"])

    def test_a_rejected_line_reaches_json_sqlite_and_html_as_unknown(self):
        import sqlite3

        from test_damage_archive import facts, native, package, panel as written

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = package(root)
            document = json.loads(written(root, "43721").read_text(encoding="utf-8"))
            document["rejected"] = [{"line": 40, "reason": "unrecognized panel line"}]
            (root / "rejected-panel.json").write_text(json.dumps(document), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["--package", str(path), "--native-stats", str(native(root, path)),
                             "--panel-log", str(root / "rejected-panel.json"), "--facts", str(facts(root)),
                             "--output", str(root / "out"), *self.ARGS])
            self.assertEqual(code, 0)
            result = json.loads((root / "out" / "calculation.json").read_text(encoding="utf-8"))
            self.assertIsNone(result["panel_log"]["newer_state_conflict"])
            self.assertIn("Panel comparison coverage is incomplete",
                          result["panel_log"]["stale_selection_warning"])
            with contextlib.closing(sqlite3.connect(root / "out" / "database.sqlite")) as connection:
                stored = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='panel_log_selection'").fetchone()[0])
            self.assertIsNone(stored["summary"]["newer_state_conflict"])
            self.assertIn("Panel comparison coverage is incomplete",
                          stored["summary"]["stale_selection_warning"])
            page = (root / "out" / "index.html").read_text(encoding="utf-8")
            self.assertIn("unknown", page)
            self.assertIn("Panel comparison coverage is incomplete", page)
