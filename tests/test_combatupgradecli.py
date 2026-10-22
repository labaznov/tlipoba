import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from damage_lab.combatupgradecli import main
from test_combatupgrades import scenario


class CombatUpgradeCliTests(unittest.TestCase):
    """Publish only complete conditional comparisons while preserving local inputs and existing paths."""

    def test_missing_required_arguments_return_one_without_exiting_or_echoing_input(self):
        outcomes = []
        for arguments in ([], ["--scenario", "PRIVATE-COMBAT-CANARY"], ["--output", "PRIVATE-COMBAT-CANARY"], ["--scenario"]):
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(arguments)
            outcomes.append((status, len(errors.getvalue().splitlines()), "PRIVATE-COMBAT-CANARY" in errors.getvalue(),
                             errors.getvalue().rstrip().endswith(".")))
        self.assertEqual(outcomes, [(1, 1, False, False)] * 4)

    def test_unknown_abbreviated_and_repeated_flags_are_refused_without_payload_echo(self):
        outcomes = []
        for arguments in (["--scen", "PRIVATE-COMBAT-CANARY", "--output", "unused"],
                          ["--scenario", "unused", "--output", "unused", "--override", "PRIVATE-COMBAT-CANARY"],
                          ["--scenario", "unused", "--scenario", "PRIVATE-COMBAT-CANARY", "--output", "unused"],
                          ["--scenario", "unused", "--output", "unused", "--output", "PRIVATE-COMBAT-CANARY"],
                          ["--help", "--unknown", "PRIVATE-COMBAT-CANARY"]):
            errors, output = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = main(arguments)
            outcomes.append((status, output.getvalue(), len(errors.getvalue().splitlines()),
                             "PRIVATE-COMBAT-CANARY" in errors.getvalue()))
        self.assertEqual(outcomes, [(1, "", 1, False)] * 5)

    def test_help_returns_zero_without_required_paths_or_system_exit(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = main(["--help"])
        self.assertEqual((status, "--scenario" in output.getvalue(), "--output" in output.getvalue(), errors.getvalue()),
                         (0, True, True, ""))

    def test_existing_output_files_and_directories_are_preserved_byte_for_byte(self):
        for directory in (False, True):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source, target = root / "scenario.json", root / "result"
                source.write_bytes(b"PRIVATE-COMBAT-CANARY")
                if directory:
                    target.mkdir()
                preserved = target / "comparison.json" if directory else target
                preserved.write_bytes(b"existing result\x00\xff")
                errors = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                    status = main(["--scenario", str(source), "--output", str(target)])
                self.assertEqual((status, preserved.read_bytes(), source.read_bytes(), errors.getvalue().strip()),
                                 (1, b"existing result\x00\xff", b"PRIVATE-COMBAT-CANARY",
                                  "Ошибка боевого сравнения: путь результата уже существует"))

    def test_output_equal_to_the_input_cannot_replace_the_scenario(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "scenario.json"
            source.write_bytes(b"preserve the source")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(source)])
            self.assertEqual((status, source.read_bytes()), (1, b"preserve the source"))

    def test_normalized_existing_output_is_refused_without_creating_an_extra_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scenario.json"
            source.write_bytes(b"preserve input")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(root / "unused" / "..")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir()), source.read_bytes()),
                             (1, ["scenario.json"], b"preserve input"))

    def test_missing_or_directory_inputs_dont_create_an_output_parent(self):
        outcomes = []
        for directory in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / "source"
                if directory:
                    source.mkdir()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    status = main(["--scenario", str(source), "--output", str(root / "new" / "result")])
                outcomes.append((status, (root / "new").exists(), source.is_dir()))
        self.assertEqual(outcomes, [(1, False, False), (1, False, True)])

    def test_strict_json_errors_are_refused_before_calling_the_evaluator(self):
        def unexpected(document):
            raise AssertionError("The evaluator cannot receive refused JSON")

        for raw in (b'{"currency":"PRIVATE-COMBAT-CANARY","currency":"synthetic"}',
                    b'{"candidate":{"cost":17,"cost":31}}', b'{"opaque":NaN}',
                    b'{"opaque":Infinity}', b'{"opaque":1e400}', b'{"cost":1e-400}',
                    b'{"cost":-1e-400}', b'{"cost":1e-999999999999999999999}',
                    b'\xffPRIVATE-COMBAT-CANARY',
                    b'{"PRIVATE-COMBAT-CANARY":'):
            with self.subTest(size=len(raw)), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / "scenario.json"
                source.write_bytes(raw)
                errors = io.StringIO()
                with patch("damage_lab.combatupgradecli.evaluate", unexpected), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                    status = main(["--scenario", str(source), "--output", str(root / "new" / "result")])
                self.assertEqual((status, sorted(path.name for path in root.iterdir()), source.read_bytes(),
                                  len(errors.getvalue().splitlines()), "PRIVATE-COMBAT-CANARY" in errors.getvalue()),
                                 (1, ["scenario.json"], raw, 1, False))

    def test_nested_non_scenario_json_returns_one_without_output_or_source_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scenario.json"
            raw = b"[" * 1800 + b"0" + b"]" * 1800
            source.write_bytes(raw)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(root / "new" / "result")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir()), source.read_bytes()),
                             (1, ["scenario.json"], raw))

    def test_an_input_above_eight_mebibytes_is_refused_before_evaluation(self):
        def unexpected(document):
            raise AssertionError("Oversize input cannot reach the evaluator")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scenario.json"
            raw = json.dumps(scenario()).encode("utf-8")
            source.write_bytes(raw + b" " * (8 * 1024 * 1024 + 1 - len(raw)))
            with patch("damage_lab.combatupgradecli.evaluate", unexpected), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(root / "result")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir()), source.stat().st_size),
                             (1, ["scenario.json"], 8 * 1024 * 1024 + 1))

    def test_model_validation_failure_leaves_no_parent_or_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            document = scenario()
            document["baseline"]["gates"]["inheritance"]["status"] = "unknown"
            document["candidates"][1]["scenario"]["target"]["armor"] = "PRIVATE-COMBAT-CANARY"
            source = root / "scenario.json"
            raw = json.dumps(document).encode("utf-8")
            source.write_bytes(raw)
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["--scenario", str(source), "--output", str(root / "new" / "result")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir()), source.read_bytes(),
                              "PRIVATE-COMBAT-CANARY" in errors.getvalue()), (1, ["scenario.json"], raw, False))

    def test_renderer_failure_occurs_before_any_output_directory_is_created(self):
        def unavailable(report):
            raise ValueError("PRIVATE-COMBAT-CANARY")

        renderer = ModuleType("damage_lab.combatupgradereport")
        renderer.render = unavailable
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scenario.json"
            source.write_text(json.dumps(scenario()), encoding="utf-8")
            errors = io.StringIO()
            with patch.dict(sys.modules, {renderer.__name__: renderer}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["--scenario", str(source), "--output", str(root / "new" / "result")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir()), "PRIVATE-COMBAT-CANARY" in errors.getvalue()),
                             (1, ["scenario.json"], False))

    def test_a_target_created_before_publication_survives_and_only_owned_stage_is_cleaned(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "scenario.json", root / "result"
            source.write_text(json.dumps(scenario()), encoding="utf-8")
            preserved = root / ".tli-combat-upgrades-preserved"
            preserved.mkdir()
            (preserved / "sentinel").write_bytes(b"preexisting stage lookalike")

            def competing(report):
                target.write_bytes(b"another writer owns this result")
                return "<html>synthetic renderer</html>"

            renderer = ModuleType("damage_lab.combatupgradereport")
            renderer.render = competing
            with patch.dict(sys.modules, {renderer.__name__: renderer}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(target)])
            self.assertEqual((status, target.read_bytes(), (preserved / "sentinel").read_bytes(),
                              sorted(path.name for path in root.iterdir())),
                             (1, b"another writer owns this result", b"preexisting stage lookalike",
                              [".tli-combat-upgrades-preserved", "result", "scenario.json"]))

    def test_complete_comparisons_publish_full_combat_oracles_and_passive_html_together(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "scenario.json", root / "result"
            raw = json.dumps(scenario()).encode("utf-8")
            source.write_bytes(raw)
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["--scenario", str(source), "--output", str(target)])
            report = json.loads((target / "comparison.json").read_text(encoding="utf-8"))
            page = (target / "index.html").read_text(encoding="utf-8")
            self.assertEqual((status, errors.getvalue(), source.read_bytes(),
                              sorted(path.name for path in target.iterdir()), report["format"], report["status"],
                              round(report["baseline"]["dps"], 6),
                              [round(row["delta"], 6) for row in report["candidates"]], report["ranking"],
                              report["price_source"], report["quantity_scope"],
                              page.startswith("<!doctype html>"), "<script" in page.lower()),
                             (0, "", raw, ["comparison.json", "index.html"], "tli-combat-upgrade-report-v1",
                              "conditional", 291.06, [291.06, 145.53], ["hit", "topology"], "caller",
                              "conditional_combat_dps", True, False))

    def test_utf8_bom_and_unicode_names_and_currency_survive_without_rewriting_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "сценарий.json", root / "новый каталог" / "результат"
            document = scenario()
            document["currency"] = "синтетический жетон"
            document["candidates"][0]["name"] = "Синтетическое усиление"
            raw = b"\xef\xbb\xbf" + json.dumps(document, ensure_ascii=False).encode("utf-8")
            source.write_bytes(raw)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(target)])
            report = json.loads((target / "comparison.json").read_text(encoding="utf-8"))
            page = (target / "index.html").read_text(encoding="utf-8")
            self.assertEqual((status, source.read_bytes(), report["currency"], report["candidates"][0]["name"],
                              "синтетический жетон" in page, "Синтетическое усиление" in page),
                             (0, raw, "синтетический жетон", "Синтетическое усиление", True, True))

    def test_exactly_eight_mebibytes_is_accepted_without_modifying_the_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "scenario.json", root / "result"
            raw = json.dumps(scenario()).encode("utf-8")
            raw += b" " * (8 * 1024 * 1024 - len(raw))
            source.write_bytes(raw)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(target)])
            self.assertEqual((status, source.read_bytes(), sorted(path.name for path in target.iterdir())),
                             (0, raw, ["comparison.json", "index.html"]))

    def test_blocked_baselines_still_publish_complete_reports_with_null_gains(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "scenario.json", root / "result"
            document = scenario()
            document["baseline"]["gates"]["inheritance"]["status"] = "unknown"
            source.write_text(json.dumps(document), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(target)])
            report = json.loads((target / "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual((status, report["status"], report["baseline"]["dps"], report["ranking"],
                              [(row["status"], row["delta"], row["relative"], row["per_cost"])
                               for row in report["candidates"]], (target / "index.html").is_file()),
                             (0, "blocked", None, [], [("blocked", None, None, None)] * 2, True))

    def test_free_and_unpriced_comparisons_keep_null_ratios_and_distinct_statuses(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "scenario.json", root / "result"
            document = scenario()
            document["candidates"][0]["cost"] = None
            document["candidates"][1]["cost"] = 0
            source.write_text(json.dumps(document), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(target)])
            report = json.loads((target / "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual((status, [(row["cost"], row["status"], row["per_cost"])
                                      for row in report["candidates"]], report["ranking"]),
                             (0, [(None, "unpriced", None), (0, "free", None)], ["topology"]))

    def test_exact_zero_with_a_large_exponent_stays_zero_instead_of_becoming_an_input_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "scenario.json", root / "result"
            raw = json.dumps(scenario()).replace('"cost": 17', '"cost": 0e-999999999999999999999').encode("utf-8")
            source.write_bytes(raw)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(target)])
            report = json.loads((target / "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual((status, report["candidates"][0]["cost"], report["candidates"][0]["status"]),
                             (0, 0, "free"))

    def test_output_parent_files_are_preserved_when_publication_cannot_create_a_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, parent = root / "scenario.json", root / "parent"
            raw = json.dumps(scenario()).encode("utf-8")
            source.write_bytes(raw)
            parent.write_bytes(b"existing parent file")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--scenario", str(source), "--output", str(parent / "result")])
            self.assertEqual((status, source.read_bytes(), parent.read_bytes(), sorted(path.name for path in root.iterdir())),
                             (1, raw, b"existing parent file", ["parent", "scenario.json"]))
