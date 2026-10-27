"""Upgrade CLI fixtures use temporary files and synthetic model inputs."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from damage_lab.__main__ import main
from test_upgrades import candidate, scenario


class UpgradeCliTests(unittest.TestCase):
    """Publish conditional upgrade reports without touching existing results."""

    def test_upgrade_dispatch_publishes_json_and_html_in_a_new_directory(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            document = scenario()
            document["candidates"] = [candidate("paid", 0.25, 17)]
            source = root / "scenario.json"
            source.write_text(json.dumps(document), encoding="utf-8")
            status = main(["upgrades", "--scenario", str(source), "--output", str(root / "result")])
            report = json.loads((root / "result/upgrades.json").read_text(encoding="utf-8"))
            self.assertEqual((status, report["status"], report["candidates"][0]["delta"], report["ranking"],
                              "Условное сравнение улучшений" in (root / "result/index.html").read_text(encoding="utf-8"),
                              sorted(path.name for path in (root / "result").iterdir())),
                             (0, "conditional", 250, ["paid"], True, ["index.html", "upgrades.json"]))

    def test_existing_results_are_refused_without_overwriting_files_or_directories(self):
        for directory in (True, False):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source, target = root / "scenario.json", root / "result"
                source.write_text(json.dumps(scenario()), encoding="utf-8")
                if directory:
                    target.mkdir()
                artifact = target / "upgrades.json" if directory else target
                artifact.write_bytes(b"preserve-result")
                errors = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                    status = main(["upgrades", "--scenario", str(source), "--output", str(target)])
                self.assertEqual((status, artifact.read_bytes(), errors.getvalue().strip()),
                                 (1, b"preserve-result", "Ошибка сравнения улучшений: каталог результата уже существует"))

    def test_scenarios_larger_than_eight_mebibytes_leave_no_result(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            data = json.dumps(scenario()).encode("utf-8")
            source = root / "scenario.json"
            source.write_bytes(data + b" " * (8 * 1024 * 1024 + 1 - len(data)))
            status = main(["upgrades", "--scenario", str(source), "--output", str(root / "result")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir())), (1, ["scenario.json"]))

    def test_duplicate_json_fields_cannot_silently_replace_prices_or_currency(self):
        for field, replacement in (('"currency": "synthetic token"',
                                    '"currency":"PRIVATE-UPGRADE-CANARY","currency":"synthetic token"'),
                                   ('"cost": 17', '"cost":17,"cost":31')):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                document = scenario()
                document["candidates"] = [candidate("paid", 0.25, 17)]
                source = root / "scenario.json"
                source.write_text(json.dumps(document).replace(field, replacement), encoding="utf-8")
                errors = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                    status = main(["upgrades", "--scenario", str(source), "--output", str(root / "result")])
                self.assertEqual((status, sorted(path.name for path in root.iterdir()),
                                  "PRIVATE-UPGRADE-CANARY" in errors.getvalue()), (1, ["scenario.json"], False))

    def test_unknown_arguments_fail_without_printing_private_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scenario.json"
            source.write_text(json.dumps(scenario()), encoding="utf-8")
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["upgrades", "--scenario", str(source), "--output", str(root / "result"),
                               "--override", "PRIVATE-UPGRADE-CANARY"])
            self.assertEqual((status, (root / "result").exists(), len(errors.getvalue().splitlines()),
                              "PRIVATE" in errors.getvalue(), errors.getvalue().rstrip().endswith(".")),
                             (1, False, 1, False, False))

    def test_utf8_bom_and_unicode_paths_and_currency_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            document = scenario()
            document["currency"] = "синтетический жетон"
            source = root / "сценарий.json"
            source.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8-sig")
            target = root / "новый каталог" / "результат"
            status = main(["upgrades", "--scenario", str(source), "--output", str(target)])
            self.assertEqual((status, json.loads((target / "upgrades.json").read_text(encoding="utf-8"))["currency"],
                              "синтетический жетон" in (target / "index.html").read_text(encoding="utf-8")),
                             (0, "синтетический жетон", True))

    def test_exactly_eight_mebibytes_remain_a_supported_input_size(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            data = json.dumps(scenario()).encode("utf-8")
            source = root / "scenario.json"
            source.write_bytes(data + b" " * (8 * 1024 * 1024 - len(data)))
            self.assertEqual(main(["upgrades", "--scenario", str(source), "--output", str(root / "result")]), 0)

    def test_invalid_inputs_leave_no_result_and_do_not_echo_private_payloads(self):
        document = scenario()
        document["panel"]["spell_dps"] = float("nan")
        for data in (b'{"PRIVATE-UPGRADE-CANARY":', b'\xffPRIVATE-UPGRADE-CANARY', b"null",
                     json.dumps(document).encode("utf-8"), b"[" * 1800 + b"0" + b"]" * 1800):
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / "scenario.json"
                source.write_bytes(data)
                errors = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                    status = main(["upgrades", "--scenario", str(source), "--output", str(root / "result")])
                self.assertEqual((status, sorted(path.name for path in root.iterdir()), len(errors.getvalue().splitlines()),
                                  "PRIVATE" in errors.getvalue(), errors.getvalue().rstrip().endswith(".")),
                                 (1, ["scenario.json"], 1, False, False))

    def test_missing_input_does_not_create_an_output_parent(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            status = main(["upgrades", "--scenario", str(root / "missing.json"), "--output", str(root / "new/result")])
            self.assertEqual((status, list(root.iterdir())), (1, []))

    def test_rendering_failure_cleans_staged_files_before_publication(self):
        def unavailable(report):
            raise ValueError("PRIVATE-UPGRADE-CANARY")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "scenario.json"
            source.write_text(json.dumps(scenario()), encoding="utf-8")
            errors = io.StringIO()
            with patch("damage_lab.upgradecli.render", unavailable), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["upgrades", "--scenario", str(source), "--output", str(root / "result")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir()), "PRIVATE" in errors.getvalue()),
                             (1, ["scenario.json"], False))
