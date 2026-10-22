"""Check automatic input publication with isolated local packages and outputs."""

import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from damage_lab.buildinputcli import main


@contextlib.contextmanager
def pipeline(*, assembler=None, renderer=None):
    """Isolate the CLI publication seam from independently owned active domain modules."""
    builder = ModuleType("damage_lab.buildinputs")
    page = ModuleType("damage_lab.buildinputreport")

    def assemble(record, *, skill_alias):
        return {"format": "tli-build-input-report-v1", "status": "blocked", "selection": {"alias": skill_alias},
                "record": record, "gaps": ["effective_level_unknown"]}

    def render(report):
        return "<!doctype html><html lang=ru><meta charset=utf-8><p>Входные данные, без DPS</p></html>"

    builder.assemble = assembler or assemble
    page.render = renderer or render
    with patch.dict(sys.modules, {builder.__name__: builder, page.__name__: page}):
        yield


class BuildInputCliTests(unittest.TestCase):
    """Keep CLI errors private while publishing input candidates without manual combat values."""

    def test_missing_required_arguments_return_one_without_system_exit_or_payload_echo(self):
        outcomes = []
        for arguments in ([], ["--package", "PRIVATE-INPUT-CANARY"],
                          ["--package", "unused", "--skill", "gem[1]"],
                          ["--package", "unused", "--output", "unused"]):
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(arguments)
            outcomes.append((status, len(errors.getvalue().splitlines()),
                             "PRIVATE-INPUT-CANARY" in errors.getvalue(),
                             errors.getvalue().rstrip().endswith(".")))
        self.assertEqual(outcomes, [(1, 1, False, False)] * 4)

    def test_unknown_abbreviated_repeated_and_conflicting_flags_are_refused_privately(self):
        base = ["--package", "unused", "--skill", "gem[3]", "--output", "unused"]
        cases = (["--pack", "PRIVATE-INPUT-CANARY", "--skill", "gem[3]", "--output", "unused"],
                 base + ["--observations", "PRIVATE-INPUT-CANARY"],
                 base + ["--skill", "gem[7]"], base + ["--package", "PRIVATE-INPUT-CANARY"],
                 base + ["--output", "PRIVATE-INPUT-CANARY"],
                 base + ["--facts", "one", "--facts", "PRIVATE-INPUT-CANARY"],
                 base + ["--native-stats", "one", "--native-stats", "PRIVATE-INPUT-CANARY"],
                 base + ["--panel-log", "one", "--game-log", "PRIVATE-INPUT-CANARY"],
                 ["--help", "--unknown", "PRIVATE-INPUT-CANARY"])
        outcomes = []
        for arguments in cases:
            errors, output = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = main(arguments)
            outcomes.append((status, output.getvalue(), len(errors.getvalue().splitlines()),
                             "PRIVATE-INPUT-CANARY" in errors.getvalue()))
        self.assertEqual(outcomes, [(1, "", 1, False)] * len(cases))

    def test_invalid_aliases_and_missing_flag_values_are_controlled_errors(self):
        outcomes = []
        for alias in ("gem[0]", "gem[01]", "gem[-1]", "gem[1.5]", "GEM[1]", "gem[١]", "PRIVATE-INPUT-CANARY"):
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                outcomes.append(main(["--package", "unused", "--skill", alias, "--output", "unused"]))
        for arguments in (["--package"], ["--package", "unused", "--skill"],
                          ["--package", "unused", "--skill", "gem[1]", "--output"], 17):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                outcomes.append(main(arguments))
        self.assertEqual(outcomes, [1] * 11)

    def test_alias_beyond_the_interface_limit_cannot_reach_the_archive(self):
        calls = []

        def unexpected(*arguments, **inputs):
            calls.append(True)
            raise ValueError("Unsupported alias reached the archive")

        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "result"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", folder, "--skill", "gem[1000000000]", "--output", str(target)],
                              archiver=unexpected)
            self.assertEqual((status, calls, list(Path(folder).iterdir())), (1, [], []))

    def test_help_requires_no_package_and_does_not_describe_manual_stat_input(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = main(["--help"])
        self.assertEqual((status, errors.getvalue(), "--package" in output.getvalue(), "--skill" in output.getvalue(),
                          "--output" in output.getvalue(), "--observations" in output.getvalue()),
                         (0, "", True, True, True, False))

    def test_optional_inputs_are_forwarded_without_manual_observations_and_failure_cleans_only_owned_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            preserved = root / ".tli-build-inputs-preserved"
            preserved.mkdir()
            (preserved / "sentinel").write_bytes(b"unrelated existing stage")
            calls = []

            def unavailable(package, observations, facts, database, **inputs):
                calls.append((package, observations, facts, database.name, database.parent.parent, inputs))
                database.write_bytes(b"private failed database")
                raise ValueError("PRIVATE-INPUT-CANARY")

            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["--package", str(root / "package"), "--skill", "gem[7]", "--output", str(root / "result"),
                               "--native-stats", str(root / "native.json"), "--panel-log", str(root / "panel.json")], archiver=unavailable)
            self.assertEqual((status, calls, sorted(path.name for path in root.iterdir()),
                              (preserved / "sentinel").read_bytes(), len(errors.getvalue().splitlines()),
                              "PRIVATE-INPUT-CANARY" in errors.getvalue()),
                             (1, [(root / "package", None, Path(__file__).parents[1] / "damage_lab/data/combat-ss14.json",
                                   "database.sqlite", root, {"native_stats": root / "native.json", "panel_log": root / "panel.json"})],
                              [".tli-build-inputs-preserved"], b"unrelated existing stage", 1, False))

    def test_custom_facts_and_original_game_log_paths_are_forwarded_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            calls = []

            def unavailable(package, observations, facts, database, **inputs):
                calls.append((package, observations, facts, inputs))
                raise OSError("PRIVATE-INPUT-CANARY")

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[9]", "--output", str(root / "result"),
                               "--facts", str(root / "facts.json"), "--game-log", str(root / "game.log")], archiver=unavailable)
            self.assertEqual((status, calls, list(root.iterdir())),
                             (1, [(root / "package", None, root / "facts.json", {"game_log": root / "game.log"})], []))

    def test_existing_output_files_and_directories_are_preserved_before_archiving(self):
        for directory in (False, True):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = root / "result"
                if directory:
                    target.mkdir()
                preserved = target / "inputs.json" if directory else target
                preserved.write_bytes(b"preserve existing output\x00\xff")

                def unexpected(*arguments, **inputs):
                    raise AssertionError("An existing output cannot reach the archive")

                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    status = main(["--package", str(root / "package"), "--skill", "gem[1]", "--output", str(target)], archiver=unexpected)
                self.assertEqual((status, preserved.read_bytes(), sorted(path.name for path in root.iterdir())),
                                 (1, b"preserve existing output\x00\xff", ["result"]))

    def test_normalized_existing_output_does_not_create_an_extra_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "package"
            source.mkdir()
            (source / "source.json").write_bytes(b"preserve source bytes")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(source), "--skill", "gem[1]", "--output", str(root / "unused" / "..")])
            self.assertEqual((status, sorted(path.name for path in root.iterdir()), (source / "source.json").read_bytes()),
                             (1, ["package"], b"preserve source bytes"))

    def test_dangling_output_links_are_preserved_without_following_the_missing_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "result"
            try:
                target.symlink_to(root / "missing", target_is_directory=True)
            except OSError:
                self.skipTest("Symbolic links are unavailable on this Windows account")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[1]", "--output", str(target)])
            self.assertEqual((status, os.path.lexists(target), target.readlink(), (root / "missing").exists()),
                             (1, True, root / "missing", False))

    def test_blocked_inputs_publish_json_html_and_database_without_manual_parameters(self):
        with tempfile.TemporaryDirectory() as folder, pipeline():
            root = Path(folder)
            source = root / "package"
            source.mkdir()
            raw = b"synthetic original package bytes\x00\xff"
            (source / "source.json").write_bytes(raw)

            def archive(package, observations, facts, database, **inputs):
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("CREATE TABLE diagnostic (status TEXT)")
                    connection.execute("INSERT INTO diagnostic VALUES ('partial')")
                    connection.commit()
                return {"synthetic": True, "name": "Синтетический пример"}

            output, errors = io.StringIO(), io.StringIO()
            target = root / "новый каталог" / "результат"
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = main(["--package", str(source), "--skill", "gem[7]", "--output", str(target)], archiver=archive)
            report = json.loads((target / "inputs.json").read_text(encoding="utf-8"))
            page = (target / "index.html").read_text(encoding="utf-8")
            with contextlib.closing(sqlite3.connect(target / "database.sqlite")) as connection:
                stored = connection.execute("SELECT status FROM diagnostic").fetchone()[0]
            self.assertEqual((status, errors.getvalue(), sorted(path.name for path in target.iterdir()),
                              report["format"], report["status"], report["selection"], report["gaps"],
                              report["record"]["name"], stored, page.startswith("<!doctype html>"),
                              (source / "source.json").read_bytes(), output.getvalue().strip()),
                             (0, "", ["database.sqlite", "index.html", "inputs.json"],
                              "tli-build-input-report-v1", "blocked", {"alias": "gem[7]"},
                              ["effective_level_unknown"], "Синтетический пример", "partial", True, raw,
                              "Входные данные сохранены; расчёт DPS не выполнялся"))

    def test_assembly_failure_publishes_nothing_and_preserves_preexisting_stage_lookalikes(self):
        def unavailable(record, *, skill_alias):
            raise ValueError("PRIVATE-INPUT-CANARY")

        with tempfile.TemporaryDirectory() as folder, pipeline(assembler=unavailable):
            root = Path(folder)
            preserved = root / ".tli-build-inputs-existing"
            preserved.mkdir()
            (preserved / "sentinel").write_bytes(b"preserved unrelated stage")

            def archive(package, observations, facts, database, **inputs):
                database.write_bytes(b"owned transient database")
                return {"synthetic": True}

            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["--package", str(root / "package"), "--skill", "gem[2]", "--output", str(root / "result")], archiver=archive)
            self.assertEqual((status, sorted(path.name for path in root.iterdir()),
                              (preserved / "sentinel").read_bytes(), len(errors.getvalue().splitlines()),
                              "PRIVATE-INPUT-CANARY" in errors.getvalue()),
                             (1, [".tli-build-inputs-existing"], b"preserved unrelated stage", 1, False))

    def test_renderer_failure_leaves_no_partially_published_result(self):
        def unavailable(report):
            raise RuntimeError("PRIVATE-INPUT-CANARY")

        with tempfile.TemporaryDirectory() as folder, pipeline(renderer=unavailable):
            root = Path(folder)

            def archive(package, observations, facts, database, **inputs):
                database.write_bytes(b"owned transient database")
                return {"synthetic": True}

            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["--package", str(root / "package"), "--skill", "gem[2]", "--output", str(root / "result")], archiver=archive)
            self.assertEqual((status, list(root.iterdir()), len(errors.getvalue().splitlines()),
                              "PRIVATE-INPUT-CANARY" in errors.getvalue()), (1, [], 1, False))

    def test_concurrent_output_creation_is_preserved_and_only_owned_stage_is_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "result"

            def archive(package, observations, facts, database, **inputs):
                database.write_bytes(b"owned transient database")
                return {"synthetic": True}

            def competing(report):
                target.mkdir()
                (target / "inputs.json").write_bytes(b"another writer owns this result")
                return "<!doctype html><p>synthetic</p>"

            with pipeline(renderer=competing), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[3]", "--output", str(target)], archiver=archive)
            self.assertEqual((status, sorted(path.name for path in root.iterdir()),
                              (target / "inputs.json").read_bytes(), sorted(path.name for path in target.iterdir())),
                             (1, ["result"], b"another writer owns this result", ["inputs.json"]))

    def test_nonfinite_assembler_output_is_refused_before_publication(self):
        def invalid(record, *, skill_alias):
            return {"opaque": float("nan")}

        with tempfile.TemporaryDirectory() as folder, pipeline(assembler=invalid):
            root = Path(folder)

            def archive(package, observations, facts, database, **inputs):
                database.write_bytes(b"owned transient database")
                return {"synthetic": True}

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[4]", "--output", str(root / "result")], archiver=archive)
            self.assertEqual((status, list(root.iterdir())), (1, []))

    def test_an_archiver_without_its_database_cannot_publish_an_incomplete_result(self):
        def archive(package, observations, facts, database, **inputs):
            return {"synthetic": True}

        with tempfile.TemporaryDirectory() as folder, pipeline():
            root = Path(folder)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[4]", "--output", str(root / "result")], archiver=archive)
            self.assertEqual((status, list(root.iterdir())), (1, []))

    def test_the_actual_assembler_saves_unknown_inputs_without_invoking_raw_damage(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        with tempfile.TemporaryDirectory() as folder, pipeline(assembler=assemble):
            root = Path(folder)
            data = record()
            data["raw_payload"] = "PRIVATE-INPUT-CANARY"

            def archive(package, observations, facts, database, **inputs):
                database.write_bytes(b"synthetic archived database")
                return data

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[1]", "--output", str(root / "result")], archiver=archive)
            report = json.loads((root / "result/inputs.json").read_text(encoding="utf-8"))
            self.assertEqual((status, report["status"], report["selection"], report["skill"]["effective_level"],
                              report["raw_spell"], report["arithmetic_ready"], "effective_level_unknown" in report["gaps"],
                              "critical_pools_unresolved" in report["gaps"], "PRIVATE-INPUT-CANARY" in json.dumps(report)),
                             (0, "blocked", {"alias": "gem[1]", "basis": "explicit_alias", "status": "observed"},
                              None, None, False, True, True, False))

    def test_an_unobserved_alias_is_saved_as_blocked_without_selecting_a_different_gem(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        with tempfile.TemporaryDirectory() as folder, pipeline(assembler=assemble):
            root = Path(folder)

            def archive(package, observations, facts, database, **inputs):
                database.write_bytes(b"synthetic archived database")
                return record()

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[17]", "--output", str(root / "result")], archiver=archive)
            report = json.loads((root / "result/inputs.json").read_text(encoding="utf-8"))
            self.assertEqual((status, report["status"], report["selection"], report["skill"], report["modifiers"],
                              "skill_not_observed" in report["gaps"], report["raw_spell"]),
                             (0, "blocked", {"alias": "gem[17]", "basis": "explicit_alias", "status": "not_observed"},
                              None, None, True, None))

    def test_a_real_synthetic_package_publishes_the_full_pipeline_without_manual_stats(self):
        from test_damage_archive import package
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = package(root)
            attached(source)
            original = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
            target = root / "result"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(source), "--skill", "gem[1]", "--output", str(target)])
            report = json.loads((target / "inputs.json").read_text(encoding="utf-8"))
            page = (target / "index.html").read_text(encoding="utf-8")
            with contextlib.closing(sqlite3.connect(target / "database.sqlite")) as connection:
                stored = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='installed_skill_profiles'").fetchone()[0])
                observations = connection.execute("SELECT count(*) FROM sources WHERE role='observations'").fetchone()[0]
            self.assertEqual((status, report["status"], report["selection"]["status"], report["skill"]["skill_id"],
                              report["skill"]["gem_level"], report["skill"]["effective_level"], report["raw_spell"],
                              stored["source"]["sha256"] == report["source_sha256"], observations,
                              page.startswith("<!doctype html>"), "DPS пока не рассчитывается" in page,
                              "effective_level_unknown" in page, "<script" in page.lower(),
                              {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}),
                             (0, "blocked", "observed", 90017, 7, None, None, True, 0, True, True, True, False, original))

    def test_bad_package_json_returns_one_private_line_and_preserves_all_source_bytes(self):
        from test_damage_archive import package

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = package(root)
            (source / "manifest.json").write_bytes(b'{"PRIVATE-INPUT-CANARY":')
            original = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                status = main(["--package", str(source), "--skill", "gem[1]", "--output", str(root / "result")])
            self.assertEqual((status, (root / "result").exists(), len(errors.getvalue().splitlines()),
                              "PRIVATE-INPUT-CANARY" in errors.getvalue(),
                              list(root.glob(".tli-build-inputs-*")),
                              {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}),
                             (1, False, 1, False, [], original))

    def test_output_parent_files_are_preserved_when_staging_cannot_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            parent = root / "parent"
            parent.write_bytes(b"preserve existing parent file")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = main(["--package", str(root / "package"), "--skill", "gem[1]", "--output", str(parent / "result")])
            self.assertEqual((status, parent.read_bytes(), sorted(path.name for path in root.iterdir())),
                             (1, b"preserve existing parent file", ["parent"]))
