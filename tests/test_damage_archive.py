import contextlib
import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from damage_lab.archive import archive
from examples.make_fixture import fixture


class RawAttributeArchiveTests(unittest.TestCase):
    """Acquire structural attribute values automatically without promoting combat stats."""

    def test_native_package_automatically_stores_only_safe_raw_attribute_evidence(self):
        from damage_lab.rawattrbundle import read
        from test_rawattrbundle import message, source

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path, digest = source(directory, message(1, b"\x50\x2b" + message(13, b"ARCHIVE-ACCOUNT-CANARY")))
            expected = read(path, digest)
            data = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                row = connection.execute("SELECT json FROM documents WHERE role='raw_attribute_evidence'").fetchone()
                stored = json.loads(row[0]) if row else None
            self.assertEqual((data.get("raw_attribute_evidence"), stored, data["stats"], data["import_status"]),
                             (expected, expected, {}, "partial"))


class DiscoveryArchiveTests(unittest.TestCase):
    """Preserve scan limitations without storing raw process data or proving identity."""

    def test_legacy_packages_keep_memory_search_completeness_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = archive(package(root), None, facts(root), root / "out.sqlite")
            self.assertIn("Memory discovery completeness is unknown: scan pass evidence is unavailable",
                          result["coverage"])

    def test_read_gaps_survive_native_import_in_json_sqlite_and_html(self):
        from damage_lab.importer import snapshot
        from damage_lab.report import render_import

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            write(directory / "source.json", {"discovery": {"scanPasses": [
                {"complete": True, "readFailures": 0},
                {"complete": True, "readFailures": 0},
                {"complete": True, "readFailures": 7}]}})
            result = archive(directory, None, facts(root), root / "out.sqlite",
                             native_stats=native(root, directory))
            warning = ("Memory discovery has read gaps: pass 3 reports 7 read failures; "
                       "candidate uniqueness is not proven")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual((warning in snapshot(result)["coverage"],
                                  connection.execute("SELECT COUNT(*) FROM coverage WHERE text=?", (warning,)).fetchone()[0],
                                  warning in render_import(snapshot(result))), (True, 1, True))

    def test_unfinished_pass_cannot_become_complete_with_zero_read_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            write(directory / "source.json", {"discovery": {"scanPasses": [
                {"complete": True, "readFailures": 0},
                {"complete": False, "readFailures": 0},
                {"complete": True, "readFailures": 0}]}})
            self.assertIn("Memory discovery is incomplete: pass 2 did not finish; candidate uniqueness is not proven",
                          archive(directory, None, facts(root), root / "out.sqlite")["coverage"])

    def test_completed_scoped_reads_do_not_verify_atomicity_or_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            write(directory / "source.json", {"discovery": {"scanPasses": [
                {"complete": True, "readFailures": 0} for _ in range(3)]}})
            self.assertIn("Memory discovery completed three recorded chunk passes with zero reported chunk read failures; "
                          "candidate validation coverage, cross-pass atomicity and selected build identity remain unverified",
                          archive(directory, None, facts(root), root / "out.sqlite")["coverage"])

    def test_invalid_source_roots_are_refused(self):
        for source in (None, [], "synthetic source", 37):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                directory = package(root)
                write(directory / "source.json", source)
                with self.assertRaisesRegex(ValueError, "Memory discovery source must be an object"):
                    archive(directory, None, facts(root), root / "out.sqlite")

    def test_an_unknown_pass_count_keeps_search_completeness_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            write(directory / "source.json", {"discovery": {"scanPasses": [
                {"complete": True, "readFailures": 0}]}})
            self.assertIn("Memory discovery completeness is unknown: expected three recorded passes; "
                          "candidate uniqueness is not proven",
                          archive(directory, None, facts(root), root / "out.sqlite")["coverage"])

    def test_invalid_scan_evidence_is_refused(self):
        for evidence in (None, [], {"scanPasses": None}, {"scanPasses": []},
                         {"scanPasses": {}}, {"scanPasses": [None]},
                         {"scanPasses": [{}]}, {"scanPasses": [{"complete": "true", "readFailures": 0}]},
                         {"scanPasses": [{"complete": True, "readFailures": True}]},
                         {"scanPasses": [{"complete": True, "readFailures": -1}]},
                         {"scanPasses": [{"complete": True, "readFailures": 1.25}]}):
            with self.subTest(evidence=evidence), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                directory = package(root)
                write(directory / "source.json", {"discovery": evidence})
                with self.assertRaisesRegex(ValueError, "Memory discovery"):
                    archive(directory, None, facts(root), root / "out.sqlite")


def attachedmemories(directory, *, error=False):
    """Attach synthetic memory definitions or a source-bound acquisition error."""
    from test_memorybundle import diagnostic, failure

    artifact, descriptor, _ = (failure if error else diagnostic)(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["memoryDefinitionLedger"] = descriptor
    write(directory / "manifest.json", manifest)
    return artifact, descriptor


class MemoryDefinitionArchiveTests(unittest.TestCase):
    """Archive memory definitions and artifact hashes before reporting diagnostic facts."""

    def test_memory_definitions_are_preserved_in_json_sqlite_and_hashed_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor = attachedmemories(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                stored = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='memory_definitions'").fetchone()[0])
                self.assertEqual((stored, connection.execute(
                    "SELECT sha256,stored FROM sources WHERE role='memory_definitions'").fetchone()),
                                 (result["memory_definitions"], (descriptor["sha256"], 1)))

    def test_memory_producer_errors_keep_a_hashed_gap_without_an_empty_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor = attachedmemories(directory, error=True)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual(("memory_definitions" in result, connection.execute(
                    "SELECT sha256,stored FROM sources WHERE role='memory_definitions'").fetchone()),
                                 (False, (descriptor["sha256"], 0)))

    def test_legacy_memory_packages_keep_the_acquisition_gap_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = archive(package(root), None, facts(root), root / "out.sqlite")
            self.assertTrue("memory_definitions" not in result and any(
                "Memory definitions are unavailable" in row for row in result["coverage"]))

    def test_changed_memory_artifacts_are_refused_before_database_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attachedmemories(directory)
            with (directory / "memory-definition-ledger.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaises(ValueError):
                archive(directory, None, facts(root), root / "out.sqlite")
            self.assertFalse((root / "out.sqlite").exists())

    def test_memory_candidates_leave_existing_stats_and_benchmarks_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            before = archive(directory, observations(root), facts(root), root / "before.sqlite")
            attachedmemories(directory)
            after = archive(directory, observations(root), facts(root), root / "after.sqlite")
            self.assertEqual((after["stats"], after["benchmark"]), (before["stats"], before["benchmark"]))


def attachedlevels(directory, *, error=False):
    """Attach fictional level candidates for every exactly observed installed skill."""
    from damage_lab.installedskills import project
    from test_levelbundle import diagnostic, failure, persisted
    from test_skillbundle import attached

    raw, _ = attached(directory)
    if error:
        artifact, descriptor, _ = failure(directory)
    else:
        artifact, descriptor, source, _ = diagnostic(directory)
        installation = project(raw, source)
        members = [member for group in installation["groups"] for member in group["members"]]
        ledger = next(iter(artifact["targets"].values()))
        targets = {}
        for member in members:
            target = copy.deepcopy(ledger)
            target["source"]["sha256"] = source
            target["target"].update(skillId=member["skill_id"], path=member["path"], gemLevel={
                "value": member["gem_level"], "status": member["level_status"],
                "meaning": "observed_gem_level_not_effective"})
            target["domains"]["supports"]["observed"] = len(members)
            targets[str(member["skill_id"])] = target
        artifact.update(requestedIds=sorted(member["skill_id"] for member in members), targets=targets)
        artifact["selection"].update(observedMembers=len(members), invalidSkillIds=0)
        descriptor.update(requested=len(targets), targets=len(targets),
                          candidates=sum(len(target["candidates"]) for target in targets.values()),
                          gaps=sum(len(target["gaps"]) for target in targets.values()), ambiguousTargets=0)
        persisted(directory, artifact, descriptor)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["installedLevelCandidates"] = descriptor
    write(directory / "manifest.json", manifest)
    return artifact, descriptor


class InstalledLevelBundleTests(unittest.TestCase):
    """Preserve source-bound candidate levels without deriving effective levels or damage."""

    def test_level_candidates_are_preserved_in_record_sqlite_and_hashed_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor = attachedlevels(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                stored = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='installed_level_candidates'").fetchone()[0])
                self.assertEqual((stored, connection.execute(
                    "SELECT path,sha256,bytes,stored FROM sources WHERE role='installed_level_candidates'").fetchone()),
                    (json.loads(json.dumps(result["installed_level_candidates"])),
                     (str((directory / descriptor["file"]).resolve()), descriptor["sha256"],
                      (directory / descriptor["file"]).stat().st_size, 1)))

    def test_observed_gem_levels_and_invalid_levels_never_become_effective_levels(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attachedlevels(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")["installed_level_candidates"]
            self.assertEqual((result["requested_ids"], result["targets"]["90017"]["target"]["gem_level"]["value"],
                              result["targets"]["90053"]["target"]["gem_level"],
                              [target["effective_level"] for target in result["targets"].values()],
                              result["arithmetic_ready"], result["import_complete"]),
                ([90017, 90029, 90041, 90053], 7,
                 {"value": None, "status": "invalid_level", "meaning": "observed_gem_level_not_effective"},
                 [None] * 4, False, False))

    def test_a_hashed_level_acquisition_error_remains_a_gap_without_semantic_documents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor = attachedlevels(directory, error=True)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual(("installed_level_candidates" in result, connection.execute(
                    "SELECT COUNT(*) FROM documents WHERE role='installed_level_candidates'").fetchone()[0],
                    connection.execute("SELECT sha256,stored FROM sources WHERE role='installed_level_candidates'").fetchone(),
                    any("Installed level candidate acquisition failed" in row for row in result["coverage"])),
                    (False, 0, (descriptor["sha256"], 0), True))

    def test_legacy_packages_have_a_level_acquisition_gap_without_an_invented_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = archive(package(root), None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual(("installed_level_candidates" in result, connection.execute(
                    "SELECT COUNT(*) FROM sources WHERE role='installed_level_candidates'").fetchone()[0],
                    any("Installed level candidates are unavailable" in row for row in result["coverage"])), (False, 0, True))

    def test_tampered_level_bytes_source_counts_or_installation_are_refused_before_database_creation(self):
        from test_levelbundle import persisted

        outcomes = []
        for change in ("bytes", "source", "count", "path", "level"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                directory = package(root)
                artifact, descriptor = attachedlevels(directory)
                if change == "bytes":
                    with (directory / descriptor["file"]).open("ab") as stream:
                        stream.write(b" ")
                else:
                    if change == "source":
                        artifact["source"]["sha256"] = "f" * 64
                    elif change == "count":
                        descriptor["candidates"] += 1
                    elif change == "path":
                        artifact["targets"]["90017"]["target"]["path"] = "sections.SkillLayout.data[0][1]"
                    else:
                        artifact["targets"]["90017"]["target"]["gemLevel"]["value"] = 23
                    persisted(directory, artifact, descriptor)
                    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                    manifest["installedLevelCandidates"] = descriptor
                    write(directory / "manifest.json", manifest)
                try:
                    archive(directory, None, facts(root), root / "out.sqlite")
                except ValueError:
                    outcomes.append(not (root / "out.sqlite").exists())
        self.assertEqual(outcomes, [True] * 5)

    def test_level_candidates_do_not_change_the_existing_conditional_calculation(self):
        from damage_lab.engine import calculate

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            condition = {"basis": "panel", "active": 2, "hits": 3, "retention": 0.2,
                         "resistance": 0.23, "taken": 0.11, "uptime": 0.87}
            before = archive(directory, observations(root), facts(root), root / "before.sqlite")
            attachedlevels(directory)
            after = archive(directory, observations(root), facts(root), root / "after.sqlite")
            self.assertEqual((after["stats"], after["benchmark"], calculate(after["stats"], condition)),
                             (before["stats"], before["benchmark"], calculate(before["stats"], condition)))


class InstalledProfileBundleTests(unittest.TestCase):
    """Archive catalog lookups at observed gem levels without deriving effective character damage."""

    def test_lookup_profiles_are_preserved_in_record_sqlite_and_hashed_origin(self):
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor = attached(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                stored = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='installed_skill_profiles'").fetchone()[0])
                self.assertEqual((stored, connection.execute(
                    "SELECT sha256,stored FROM sources WHERE role='installed_skill_profiles'").fetchone()),
                                 (result["installed_skill_profiles"], (descriptor["sha256"], 1)))

    def test_failed_catalog_acquisition_is_a_gap_without_empty_profiles(self):
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attached(directory, error=True)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual(("installed_skill_profiles" in result, connection.execute(
                    "SELECT stored FROM sources WHERE role='installed_skill_profiles'").fetchone()[0],
                    any("Installed skill catalog acquisition failed" in row for row in result["coverage"])), (False, 0, True))

    def test_legacy_packages_disclose_missing_installed_catalog_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertTrue(any("Installed skill catalog profiles are unavailable" in row for row in archive(
                package(root), None, facts(root), root / "out.sqlite")["coverage"]))

    def test_changed_catalog_artifact_is_refused_before_database_creation(self):
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attached(directory)
            with (directory / "installed-skill-catalog.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaises(ValueError):
                archive(directory, None, facts(root), root / "out.sqlite")
            self.assertFalse((root / "out.sqlite").exists())

    def test_lookup_profiles_do_not_change_observed_stats_or_benchmark(self):
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            before = archive(directory, observations(root), facts(root), root / "before.sqlite")
            attached(directory)
            after = archive(directory, observations(root), facts(root), root / "after.sqlite")
            self.assertEqual((after["stats"], after["benchmark"], after["installed_skill_profiles"]["arithmetic_ready"]),
                             (before["stats"], before["benchmark"], False))


class SupportEffectBundleTests(unittest.TestCase):
    """Archive support candidates and declared catalog metadata without changing character stats."""

    def test_medium_creation_candidates_are_preserved_in_validated_sqlite_documents(self):
        from test_supportbundle import medium

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor, _ = medium(directory)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["installedSupportEffects"] = descriptor
            write(directory / "manifest.json", manifest)
            result = archive(directory, None, facts(root), root / "medium.sqlite")
            with contextlib.closing(sqlite3.connect(root / "medium.sqlite")) as connection:
                stored = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='installed_support_effects'").fetchone()[0])
            self.assertEqual((stored, result["stats"]), (result["installed_support_effects"], {}))

    def test_effect_candidates_and_catalog_are_preserved_in_record_sqlite_and_hashed_origin(self):
        from test_supportbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor = attached(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                stored = {role: json.loads(value) for role, value in connection.execute(
                    "SELECT role,json FROM documents WHERE role IN ('installed_support_effects','installed_support_catalog')")}
                self.assertEqual((stored, connection.execute(
                    "SELECT sha256,stored FROM sources WHERE role='installed_support_effects'").fetchone()),
                                 ({key: result[key] for key in ("installed_support_effects", "installed_support_catalog")},
                                  (descriptor["sha256"], 1)))

    def test_failed_support_acquisition_is_a_gap_without_empty_effect_or_catalog_documents(self):
        from test_supportbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attached(directory, error=True)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual((any(key in result for key in ("installed_support_effects", "installed_support_catalog")),
                                  connection.execute("SELECT stored FROM sources WHERE role='installed_support_effects'").fetchone()[0],
                                  any("Installed support effect acquisition failed" in row for row in result["coverage"])),
                                 (False, 0, True))

    def test_legacy_packages_disclose_unavailable_support_effect_acquisition(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertTrue(any("Installed support effect candidates are unavailable" in row for row in archive(
                package(root), None, facts(root), root / "out.sqlite")["coverage"]))

    def test_changed_support_artifact_is_refused_before_database_creation(self):
        from test_supportbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attached(directory)
            with (directory / "installed-support-effects.json").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaises(ValueError):
                archive(directory, None, facts(root), root / "out.sqlite")
            self.assertFalse((root / "out.sqlite").exists())

    def test_diagnostic_support_effects_preserve_preexisting_stats_and_benchmark(self):
        from test_supportbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            before = archive(directory, observations(root), facts(root), root / "before.sqlite")
            attached(directory)
            after = archive(directory, observations(root), facts(root), root / "after.sqlite")
            self.assertEqual((after["stats"], after["benchmark"], after["installed_support_effects"]["arithmetic_ready"],
                              after["installed_support_catalog"]["network_bytes_verified"]),
                             (before["stats"], before["benchmark"], False, False))


class InstalledBundleTests(unittest.TestCase):
    """Archive observed skill membership without inferring active effects."""

    def test_installation_is_preserved_in_record_sqlite_and_artifact_origin(self):
        from test_skillbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor = attached(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                stored = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='installed_skills'").fetchone()[0])
                self.assertEqual((stored, connection.execute(
                    "SELECT sha256,stored FROM sources WHERE role='installed_skills'").fetchone()),
                                 (result["installed_skills"], (descriptor["sha256"], 1)))

    def test_producer_error_remains_an_acquisition_gap_without_an_empty_inventory(self):
        from test_skillbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attached(directory, failure=True)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual(("installed_skills" in result, connection.execute(
                    "SELECT stored FROM sources WHERE role='installed_skills'").fetchone()[0],
                    any("Installed skill inventory failed" in row for row in result["coverage"])), (False, 0, True))

    def test_legacy_package_discloses_unavailable_installation_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertTrue(any("Installed skill inventory is unavailable" in row for row in archive(
                package(root), None, facts(root), root / "out.sqlite")["coverage"]))

    def test_invalid_installed_bundle_does_not_create_a_database(self):
        from test_skillbundle import attached

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            attached(directory)
            with (directory / "installed-skills.json").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaises(ValueError):
                archive(directory, None, facts(root), root / "out.sqlite")
            self.assertFalse((root / "out.sqlite").exists())


class StaticBundleTests(unittest.TestCase):
    """Retain typed gear evidence without changing already observed character values."""

    def test_automatic_compound_import_keeps_the_same_source_literal_in_sqlite(self):
        from test_staticbundle import lucky_bundle

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            lucky_bundle(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                stored = json.loads(connection.execute("SELECT json FROM documents WHERE role='static_combat'").fetchone()[0])
            self.assertEqual([(row["modifiers"][0]["family"], row["modifiers"][0]["semantics"],
                               row["modifiers"][0]["values"][0]["exact"]) for row in (result["static_combat"], stored)],
                             [("lucky_critical_damage_modifier", {"operation": "unresolved",
                               "value_role": "non_additional_percent", "lucky_critical_strike": True,
                               "arithmetic_ready": False}, "23.75")] * 2)

    def test_new_critical_arithmetic_gate_is_preserved_in_record_and_sqlite(self):
        from test_staticbundle import critical_bundle

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            critical_bundle(directory)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                stored = json.loads(connection.execute("SELECT json FROM documents WHERE role='static_combat'").fetchone()[0])
                self.assertEqual([row["modifiers"][0]["semantics"]["arithmetic_ready"]
                                  for row in (result["static_combat"], stored)], [False, False])

    def test_static_gear_bundle_is_imported_without_manual_observations(self):
        from test_staticbundle import fixture

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            fixture(directory)
            self.assertEqual(archive(directory, None, facts(root), root / "out.sqlite")
                             ["static_combat"]["accounting"]["compiled"], 1)

    def test_sqlite_stores_ledger_catalog_coordinates_and_hashed_artifact_origin(self):
        from test_staticbundle import fixture

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, bundle = fixture(directory)
            archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual((json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='static_combat_provenance'").fetchone()[0])
                    ["documents"][0]["byte_range"], connection.execute(
                        "SELECT sha256,stored FROM sources WHERE role='static_combat'").fetchone()),
                                 ([17, 319], (bundle["sha256"], 1)))

    def test_failed_static_bundle_is_a_gap_without_zero_effect_claims(self):
        from test_staticbundle import fixture

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            fixture(directory, error=True)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual(("static_combat" in result, connection.execute(
                    "SELECT stored FROM sources WHERE role='static_combat'").fetchone()[0],
                    any("Static gear modifier bundle failed" in value for value in result["coverage"])),
                                 (False, 0, True))

    def test_legacy_package_keeps_static_modifier_acquisition_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertTrue(any("Static gear modifiers are unavailable" in value for value in archive(
                package(root), None, facts(root), root / "out.sqlite")["coverage"]))

    def test_invalid_static_bundle_leaves_no_database(self):
        from test_staticbundle import fixture, saved

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            artifact, bundle = fixture(directory)
            artifact["identityVerified"] = True
            saved(directory, artifact, bundle)
            with self.assertRaises(ValueError):
                archive(directory, None, facts(root), root / "out.sqlite")
            self.assertFalse((root / "out.sqlite").exists())


def resolution_bundle(directory):
    """Write fictional saved-code evidence without a code or verified identity."""
    from test_buildresolution import document

    data = document()
    data["source"]["sha256"] = hashlib.sha256((directory / "source.json").read_bytes()).hexdigest()
    path = write(directory / "build-resolution.json", data)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["buildResolution"] = {
        "file": "build-resolution.json", "status": "diagnostic",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "sourceSha256": data["source"]["sha256"],
        "resolutionStatus": data["status"], "expectedCodeSupplied": True,
        "identityVerified": False, "transportVerified": False,
    }
    write(directory / "manifest.json", manifest)
    return path


class ResolutionBundleTests(unittest.TestCase):
    """A saved code match remains a claim with unknown payload freshness."""

    def test_saved_code_assessment_is_imported_with_unknown_freshness(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            resolution_bundle(directory)
            self.assertEqual(archive(directory, None, facts(root), root / "out.sqlite")
                             ["build_resolution"]["freshness"]["status"], "unknown")

    def test_assessment_and_artifact_provenance_are_saved_in_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            resolution_bundle(directory)
            archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual((json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='build_resolution'").fetchone()[0])["status"],
                    connection.execute("SELECT stored FROM sources WHERE role='build_resolution'").fetchone()[0]),
                                 ("matched_saved_code", 1))

    def test_resolution_manifest_cannot_escape_change_status_or_verify_identity(self):
        for field, value in (("file", "../build-resolution.json"), ("identityVerified", True),
                             ("transportVerified", True), ("sourceSha256", "b" * 64),
                             ("expectedCodeSupplied", 1), ("expectedCodeSupplied", False),
                             ("resolutionStatus", "unbound")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                directory = package(root)
                resolution_bundle(directory)
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                manifest["buildResolution"][field] = value
                write(directory / "manifest.json", manifest)
                with self.assertRaises(ValueError):
                    archive(directory, None, facts(root), root / "out.sqlite")

    def test_resolution_artifact_requires_the_exact_manifest_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = resolution_bundle(directory)
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "hash"):
                archive(directory, None, facts(root), root / "out.sqlite")

    def test_failed_assessment_does_not_publish_identity_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = resolution_bundle(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.update(status="error", error="ValueError")
            write(path, data)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["buildResolution"].update(status="error", resolutionStatus="error",
                                               sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            write(directory / "manifest.json", manifest)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            self.assertEqual((result["import_status"], "build_resolution" in result), ("partial", False))


def coverage_bundle(directory, guide=True):
    """Write a fictional acquisition audit tied to exact package bytes."""
    from test_importcoverage import document

    data = document(guide=guide)
    source = hashlib.sha256((directory / "source.json").read_bytes()).hexdigest()
    digest = hashlib.sha256((directory / "guide-data.json").read_bytes()).hexdigest() if guide else None
    data["source"]["sha256"] = source
    data["guide"] = {"supplied": guide, "sha256": digest, "binding": "unverified" if guide else "not_supplied"}
    path = write(directory / "import-coverage.json", data)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["importCoverage"] = {
        "file": "import-coverage.json", "status": "diagnostic", "importComplete": False,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "sourceSha256": source,
        "guideSha256": digest, "domains": len(data["domains"]),
    }
    write(directory / "manifest.json", manifest)
    return path


class CoverageBundleTests(unittest.TestCase):
    """Keep acquisition completeness separate from combat interpretation."""

    def test_bundled_acquisition_audit_is_imported_without_manual_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            coverage_bundle(directory)
            self.assertIs(archive(directory, None, facts(root), root / "out.sqlite")
                          ["import_coverage"]["import_complete"], False)

    def test_audit_projection_and_artifact_provenance_are_stored_in_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            coverage_bundle(directory)
            archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual((json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='import_coverage'").fetchone()[0])["import_complete"],
                    connection.execute("SELECT stored FROM sources WHERE role='import_coverage'").fetchone()[0]),
                                 (False, 1))

    def test_audit_artifact_requires_its_exact_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = coverage_bundle(directory)
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "hash"):
                archive(directory, None, facts(root), root / "out.sqlite")

    def test_audit_manifest_cannot_escape_or_claim_completeness_or_another_guide(self):
        for field, value in (("file", "../import-coverage.json"), ("importComplete", True),
                             ("sourceSha256", "b" * 64), ("guideSha256", "b" * 64),
                             ("domains", True), ("domains", 8), ("status", "verified")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                directory = package(root)
                coverage_bundle(directory)
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                manifest["importCoverage"][field] = value
                write(directory / "manifest.json", manifest)
                with self.assertRaises(ValueError):
                    archive(directory, None, facts(root), root / "out.sqlite")

    def test_audit_cannot_change_its_source_despite_a_rehashed_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = coverage_bundle(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["source"]["sha256"] = "b" * 64
            write(path, data)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["importCoverage"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            write(directory / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "source"):
                archive(directory, None, facts(root), root / "out.sqlite")

    def test_a_diagnostic_audit_cannot_expand_the_known_domain_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = coverage_bundle(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["domains"]["extraDomain"] = {}
            write(path, data)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["importCoverage"].update(domains=10, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            write(directory / "manifest.json", manifest)
            with self.assertRaises(ValueError):
                archive(directory, None, facts(root), root / "out.sqlite")

    def test_failed_audit_keeps_partial_import_without_domain_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = coverage_bundle(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.update(status="error", domains={}, importComplete=False)
            write(path, data)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["importCoverage"].update(status="error", domains=0,
                                               sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            write(directory / "manifest.json", manifest)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            self.assertEqual((result["import_status"], "import_coverage" in result), ("partial", False))

    def test_an_audit_without_a_guide_does_not_claim_to_have_read_the_package_guide(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            coverage_bundle(directory, guide=False)
            self.assertEqual(archive(directory, None, facts(root), root / "out.sqlite")
                             ["import_coverage"]["guide"],
                             {"supplied": False, "sha256": None, "binding": "not_supplied"})

    def test_legacy_package_exposes_the_missing_automatic_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIn("Automatic import coverage audit is unavailable in this legacy package",
                          archive(package(root), None, facts(root), root / "out.sqlite")["coverage"])


def trait_bundle(directory):
    """Write synthetic rank evidence bound to this package's source bytes."""
    from test_traitranks import document

    data = document()
    data["source"]["sha256"] = hashlib.sha256((directory / "source.json").read_bytes()).hexdigest()
    path = write(directory / "trait-ranks.json", data)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["traitRanks"] = {
        "file": "trait-ranks.json", "status": "diagnostic", "rankRuleVerified": False,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sourceSha256": data["source"]["sha256"], "traits": len(data["traits"]),
    }
    write(directory / "manifest.json", manifest)
    return path


class TraitBundleTests(unittest.TestCase):
    """Preserve automatic rank candidates without promoting a rule to a rank."""

    def test_bundled_candidates_are_imported_automatically_without_manual_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            trait_bundle(directory)
            self.assertEqual([row["rank"] for row in archive(directory, None, facts(root), root / "out.sqlite")
                              ["trait_ranks"]["traits"]], [None, None])

    def test_candidate_projection_is_stored_in_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            trait_bundle(directory)
            archive(directory, None, facts(root), root / "out.sqlite")
            with contextlib.closing(sqlite3.connect(root / "out.sqlite")) as connection:
                self.assertEqual(json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='trait_ranks'").fetchone()[0])["rule_status"],
                                 "rank_rule_unverified")

    def test_rank_bundle_requires_its_exact_artifact_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = trait_bundle(directory)
            path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash"):
                archive(directory, None, facts(root), root / "out.sqlite")

    def test_failed_rank_bundle_preserves_partial_import_without_candidate_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = trait_bundle(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.update(status="error", memories=[], traits=[], gaps=["Catalog unavailable"])
            write(path, data)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["traitRanks"].update(status="error", traits=0, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            write(directory / "manifest.json", manifest)
            result = archive(directory, None, facts(root), root / "out.sqlite")
            self.assertEqual((result["import_status"], "trait_ranks" in result), ("partial", False))

    def test_artifact_cannot_replace_its_source_hash_even_with_a_valid_manifest_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            path = trait_bundle(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["source"]["sha256"] = "b" * 64
            write(path, data)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["traitRanks"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            write(directory / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "source"):
                archive(directory, None, facts(root), root / "out.sqlite")

    def test_rank_manifest_cannot_claim_verified_rules_or_escape_the_package(self):
        for field, value in (("file", "../trait-ranks.json"), ("rankRuleVerified", True),
                             ("sourceSha256", "b" * 64), ("traits", True), ("traits", 7)):
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                directory = package(root)
                trait_bundle(directory)
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                manifest["traitRanks"][field] = value
                write(directory / "manifest.json", manifest)
                with self.assertRaises(ValueError):
                    archive(directory, None, facts(root), root / "out.sqlite")

class UnitTests(unittest.TestCase):
    """Reject incompatible units before calculating with observed values."""

    def test_critical_chance_cannot_use_count_units(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "input"
            fixture(root)
            data = json.loads((root / "observations.json").read_text(encoding="utf-8"))
            data["panel"][4].update(unit="count", display="0.4137")
            write(root / "observations.json", data)
            with self.assertRaisesRegex(ValueError, "crit_chance.*fraction"):
                archive(root, root / "observations.json", facts(root), root / "result.sqlite")

    def test_null_prism_is_a_valid_empty_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            build = json.loads((directory / "build.json").read_text(encoding="utf-8"))
            build["loadouts"]["loadouts"][0]["skillTree"]["slots"][0]["equippedPrism"] = None
            write(directory / "build.json", build)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["buildSha256"] = hashlib.sha256((directory / "build.json").read_bytes()).hexdigest()
            write(directory / "manifest.json", manifest)
            self.assertEqual(len(archive(directory, observations(root), facts(root), root / "result.sqlite")
                                 ["inventory"]["talents"]), 1)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def package(root, *, ranks=None, manifest_hash=None):
    """Write a small but complete exporter package and return its directory."""
    directory = root / "package"
    build = write(directory / "build.json", {"id": "b1", "patch": "SS14", "loadouts": {
        "currentLoadoutId": "l1", "loadouts": [{
            "id": "l1", "hero": {"heroId": "Carino: Zealot of War", "traits": {"level60": "t60"}},
            "heroMemories": {"inventory": [], "equipped": {}},
            "etherealPrisms": {"inventory": [{"id": "prism1"}], "equipped": {"slot3": "prism1"}},
            "gear": {"equipped": {}, "inventory": []}, "vorax": {"equipped": {}, "inventory": []},
            "skills": {"activeSkills": [], "passiveSkills": []},
            "skillTree": {"slots": [{"treeId": "prophet", "nodePoints": ranks or {"n1": 3},
                                     "selectedNotable12": None, "selectedNotable24": "c24"}]},
            "divinity": {"inventory": [], "placements": []},
            "pactspirits": [{"guid": "p1", "level": 6}], "kismets": [],
            "mercenaries": {"mercenaryId": None, "skills": []}, "scentBottle": {},
            "config": {"characterLevel": 96}}]}})
    write(directory / "guide-data.json", {
        "name": "t-build",
        "character": {"englishName": "Carino", "class": "Divineshot", "trait": "Zealot of War",
                      "level": 96, "traits": [{"name": "Extreme Heat", "unlockLevel": 60}]},
        "gear": [{"slot": "gloves", "name": "Tyrant's Smoldering Hold", "rarity": "Legendary",
                  "itemLevel": 90, "affixes": [{"text": "Lucky Critical Strike\n+30% Critical Strike Damage"}]}],
        "skillGroups": [{"kind": "active", "main": {"name": "Chromatic Shot", "level": 20},
                         "supports": [{"name": "Activation Medium: Tangle", "level": 20}]}],
        "talentTrees": [{"id": "prophet", "englishName": "Prophet", "points": 3,
                         "nodes": [{"guid": "n1", "rank": 3, "maxPoints": 3, "type": "micro",
                                    "text": "+2 Max Frostbite Rating"},
                                   {"guid": "n0", "rank": 0, "maxPoints": 3, "type": "micro",
                                    "text": "UNRANKED-NODE"}],
                         "notables": [{"guid": "c24", "threshold": 24, "englishName": "Extreme Coldness",
                                       "text": "Cold core"},
                                      {"guid": "c12", "threshold": 12, "englishName": "UNSELECTED-CORE",
                                       "text": "unused"}]}],
        "heroMemories": [{"name": "Memory of Origin", "itemLevel": 86, "affixes": ["+45% Cold Damage"]}],
        "sourceSections": {"PlayeBaseInfo": "SOURCE-SECTION-MARKER"}})
    write(directory / "source.json", {"raw": "RAW-SOURCE-MARKER"})
    write(directory / "manifest.json", {
        "identity": {"title": "t-build"}, "capturedAt": "2001-02-03T04:05:06+00:00",
        "status": "ready_with_gaps",
        "buildSha256": manifest_hash or hashlib.sha256(build.read_bytes()).hexdigest()})
    write(directory / "transfer-report.json", {
        "complete": False, "canClaimFullTransfer": False,
        "issues": ["etherealPrisms: Prism modifier 1234308021 is absent from the Compendium SS14 catalog."],
        "systems": {"etherealPrisms": {"status": "partial", "observed": 1, "mapped": 1,
                                       "issues": ["Prism modifier 1234308021 is absent"],
                                       "effectMappingComplete": False}}})
    return directory


def observations(root, *, panel=(), missing_evidence=False):
    """Write user observations whose screenshots exist unless told otherwise."""
    shot = root / "shots" / "panel.png"
    if not missing_evidence:
        shot.parent.mkdir(parents=True, exist_ok=True)
        shot.write_bytes(b"png")
    rows = [
        ("spell_dps", "Spell DPS", "31,729", 31729, "damage/s"),
        ("hit_min", "Total Spell Damage", "842.7K", 842700, "damage"),
        ("hit_max", "Total Spell Damage", "1.7M", 1700000, "damage"),
        ("cast_rate", "Spells cast per second", "4.73 /s", 4.73, "casts/s"),
        ("crit_chance", "Spell Critical Strike Ch...", "41.37%", 0.4137, "fraction"),
        ("crit_multiplier", "Spell Critical Strike Da...", "287%", 2.87, "multiplier"),
        ("max_tangles", "Max Tangle Quantity", "3", 3, "count"),
        ("extra_attachments", "Additional Tangle Atta...", "2", 2, "count"),
        ("cold_penetration", "Cold Penetration", "7%", 0.07, "fraction"),
        ("armour_mitigation", "Armor DMG Mitigation...", "8%", 0.08, "fraction"),
    ]
    return write(root / "observations.json", {
        "subject": {"server": "SS14", "player": "synthetic-example", "level": 96},
        "evidence": {"panel": {"path": str(shot), "shows": "stat panel"}},
        "panel": [{"key": k, "label": label, "display": display, "value": value, "unit": unit,
                   "evidence": "panel"} for k, label, display, value, unit in rows] + list(panel),
        "benchmark": {"label": "Damage (Level 73)", "evidence": "panel", "values": [
            {"key": "average_dps", "label": "Average DPS in a span of time", "display": "185,319",
             "value": 185319, "unit": "damage/s"},
            {"key": "duration", "label": "Duration", "display": "00:00:17", "value": 17, "unit": "s"},
            {"key": "highest_5s", "label": "Highest DPS in 5s", "display": "216,011",
             "value": 216011, "unit": "damage/s"},
            {"key": "average_5s", "label": "Average DPS in 5s", "display": "179,433",
             "value": 179433, "unit": "damage/s"},
            {"key": "survival", "label": "My Survival", "display": "9127", "value": 9127,
             "unit": "survival"}]},
        "notes": ["Benchmark label Damage (Level 73) names the target window; the character is level 96."]})


def facts(root):
    return write(root / "facts.json", {"patch": "SS14", "chromatic": {"id": 7007}})


def slates(directory, count):
    """Add fictional decoded slate effects without any planner placements."""
    transfer = json.loads((directory / "transfer-report.json").read_text(encoding="utf-8"))
    transfer["systems"]["divinity"] = {
        "status": "partial", "observed": count, "mapped": 0, "occupiedCells": 0,
        "effectMappingComplete": False, "decodedEffects": count,
        "issues": ["Synthetic slate shape, direction and position are unverified"],
        "decodedSlates": [{
            "sourceEncoding": "rpc.WareHousePosItem", "sourceItemId": f"synthetic-item-{index}",
            "sourceBaseId": f"synthetic-base-{index}", "sourceRareValue": 3,
            "catalogBase": {"guid": f"synthetic-base-guid-{index}", "name": f"Synthetic slate {index}"},
            "influenceCorroborated": True, "unmappedTalentIds": [],
            "effects": [{"list": "enchant", "slotIndex": 2, "tlidbId": f"synthetic-effect-{index}",
                         "modGuid": f"synthetic-mod-{index}", "nodeType": "Medium Talent",
                         "slateType": "Synthetic School", "description": "+17% Synthetic Cold Damage"}],
        } for index in range(count)],
    }
    return write(directory / "transfer-report.json", transfer)


def native(root, directory):
    """Write fictional native stats bound to the synthetic package source."""
    return write(root / "native-stats.json", {
        "format": "tli-native-stats-v1", "version": "0.1.0", "status": "decoded",
        "profile": {"name": "attrInfo-v1", "message": "rpc.ViewPlayerAttrInfo"},
        "source": {"section": "sections.ServerSource.data.attrInfo", "capturedAt": "2001-02-03T04:05:06+00:00",
                   "sha256": hashlib.sha256((directory / "source.json").read_bytes()).hexdigest()},
        "known": [{"key": key, "value": value, "wire": wire, "wireType": "varint",
                   "evidence": "corroborated", "protocolVerified": False,
                   "corroboration": "Independent synthetic observation",
                   "sourcePath": "sections.ServerSource.data.attrInfo[1].bytesHex"}
                  for key, value, wire in (("spell_dps", 43721, "1.10"), ("survival", 8033, "1.11"))],
        "unknown": [{"wire": "1.9", "statId": 937, "value": 271},
                    {"wire": "1.3", "type": "float32", "value": 2.7}],
        "omitted": [], "gaps": ["Synthetic unnamed attributes have no verified names"],
        "heroTraits": {"activeTraitIds": [999001], "source": "synthetic-traits", "levels": None},
        "coverage": {"known": 2, "unknownStatIds": 1, "unknownEntries": 2, "omitted": 0, "missing": []},
    })


def panel(root, anchor):
    """Write a fictional complete panel cohort with full numeric tokens."""
    return write(root / "panel-log.json", {
        "format": "tli-panel-log-v1", "source": {"sha256": "b" * 64}, "gaps": [],
        "cohorts": [{"timestamp": "2001-02-03T04:05:07.000Z", "frame": 713, "status": "resolved", "issues": [],
                     "attributes": [{"id": identity, "name": name, "status": "resolved",
                                     "values": [float(token) for token in tokens], "raw_values": tokens,
                                     "line_numbers": [17 + index * 2, 18 + index * 2]}
                                    for index, (identity, name, tokens) in enumerate((
                                        ("10103", "Spell DPS", [anchor]),
                                        ("11800", "Total Spell Damage", ["731.125", "1117.625"]),
                                        ("21000", "Spells cast per second", ["4.8125"]),
                                        ("21212", "Spell Critical Strike Chance", ["31.75"]),
                                        ("21400", "Spell Critical Strike Damage", ["287.5"]),
                                        ("21714", "Max Tangle Quantity", ["3"]),
                                        ("21715", "Additional Tangle Attach Quantity", ["2"]),
                                        ("11000", "Cold Penetration", ["9.25"]),
                                    ))]}],
    })


def game(root, anchor):
    """Write a fictional raw game log with one complete numeric panel state."""
    path = root / "game.log"
    prefix = "[2001.02.03-04.05.07:000][713]TLLua: Display: [Game] RoleAttrMgr@"
    path.write_text("\n".join(line for identity, name, tokens in (
        ("10103", "Spell DPS", [anchor]),
        ("11800", "Total Spell Damage", ["731.125", "1117.625"]),
        ("21000", "Spells cast per second", ["4.8125"]),
        ("21212", "Spell Critical Strike Chance", ["31.75"]),
        ("21400", "Spell Critical Strike Damage", ["287.5"]),
        ("21714", "Max Tangle Quantity", ["3"]),
        ("21715", "Additional Tangle Attach Quantity", ["2"]),
        ("11000", "Cold Penetration", ["9.25"]),
    ) for line in (prefix + f"Attri.Id  {name}  {identity}",
                   prefix + ", ".join(f"[{index}] = {token}" for index, token in enumerate(tokens, 1)))) + "\n",
                    encoding="utf-8")
    return path


def dump(database):
    with contextlib.closing(sqlite3.connect(database)) as connection:
        return "\n".join(connection.iterdump())


class ArchiveContractTest(unittest.TestCase):
    """Check the dictionary that the damage report consumes."""

    def test_empty_talent_slots_do_not_require_a_guide_tree_or_hide_selected_trees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            document = json.loads((directory / "build.json").read_text(encoding="utf-8"))
            slots = document["loadouts"]["loadouts"][0]["skillTree"]["slots"]
            slots.insert(0, {"treeId": None, "nodePoints": {}, "selectedNotable12": None,
                             "selectedNotable24": None, "prismId": None, "equippedPrism": None,
                             "prismCoreTalentOverride": None, "inverseImageState": None})
            slots.append({"treeId": None, "nodePoints": {}})
            write(directory / "build.json", document)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["buildSha256"] = hashlib.sha256((directory / "build.json").read_bytes()).hexdigest()
            write(directory / "manifest.json", manifest)
            result = archive(directory, None, facts(root), root / "empty-slots.sqlite")
            self.assertEqual([tree["name"] for tree in result["inventory"]["talents"]], ["Prophet (3 points)"])

    def test_unselected_talent_slots_cannot_hide_allocations_or_other_state(self):
        from damage_lab.archive import talents

        for field, value in (("nodePoints", {"fictional-node": 2}), ("nodePoints", None),
                             ("nodePoints", []), ("selectedNotable12", "fictional-core"),
                             ("selectedNotable24", "fictional-core"), ("equippedPrism", {}),
                             ("prismId", "fictional-prism"), ("prismCoreTalentOverride", {}),
                             ("inverseImageState", False), ("unrecognizedState", 0)):
            with self.subTest(field=field):
                slot = {"treeId": None, "nodePoints": {}, field: value}
                with self.assertRaises(ValueError):
                    talents({"talentTrees": []}, {"skillTree": {"slots": [slot]}}, [])

    def test_a_selected_unknown_talent_tree_is_still_refused(self):
        from damage_lab.archive import talents

        with self.assertRaises(ValueError):
            talents({"talentTrees": []}, {"skillTree": {"slots": [{"treeId": "fictional-unknown", "nodePoints": {}}]}}, [])

    def test_returns_agreed_contract_from_package_and_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = archive(package(root), observations(root), facts(root), root / "db" / "build.sqlite")
            self.assertLessEqual({"name", "capturedAt", "character", "stats", "observations", "benchmark",
                                  "facts", "inventory", "coverage", "source_sha256"}, set(result))
            self.assertEqual(result["name"], "t-build")
            self.assertEqual(result["capturedAt"], "2001-02-03T04:05:06+00:00")
            self.assertEqual(result["character"], "Carino / Divineshot / Zealot of War")
            self.assertEqual(result["stats"]["spell_dps"], 31729)
            self.assertEqual(result["stats"]["crit_multiplier"], 2.87)
            self.assertEqual(result["benchmark"], {"average_dps": 185319, "duration": 17,
                                                   "highest_5s": 216011, "average_5s": 179433,
                                                   "survival": 9127})
            self.assertEqual(result["facts"], {"patch": "SS14", "chromatic": {"id": 7007}})
            self.assertEqual(result["source_sha256"], hashlib.sha256(
                (root / "package" / "source.json").read_bytes()).hexdigest())
            self.assertLessEqual({"gear", "skills", "talents", "memories"}, set(result["inventory"]))
            for section in result["inventory"].values():
                for entry in section:
                    self.assertEqual(set(entry), {"name", "details"})
                    self.assertTrue(all(isinstance(line, str) for line in entry["details"]))
            for row in result["observations"]:
                self.assertEqual(set(row), {"key", "label", "value", "unit", "evidence", "precision"})

    def test_talents_keep_only_ranked_nodes_and_selected_cores(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = archive(package(root), observations(root), facts(root), root / "build.sqlite")
            text = json.dumps(result["inventory"]["talents"], ensure_ascii=False)
            self.assertIn("+2 Max Frostbite Rating", text)
            self.assertIn("Extreme Coldness", text)
            self.assertNotIn("UNRANKED-NODE", text)
            self.assertNotIn("UNSELECTED-CORE", text)

    def test_coverage_discloses_gaps_instead_of_claiming_a_full_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            coverage = "\n".join(archive(package(root), observations(root), facts(root),
                                         root / "build.sqlite")["coverage"])
            self.assertIn("1234308021", coverage)
            self.assertIn("Armor DMG Mitigation...", coverage)
            self.assertIn("Damage (Level 73)", coverage)
            self.assertIn("Lucky", coverage)
            self.assertIn("Compendium", coverage)

    def test_missing_screenshot_is_disclosed_and_user_values_are_kept(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = archive(package(root), observations(root, missing_evidence=True), facts(root),
                             root / "build.sqlite")
            self.assertEqual(result["stats"]["hit_min"], 842700)
            self.assertIn(str(root / "shots" / "panel.png"), "\n".join(result["coverage"]))

    def test_synthetic_archive_discloses_fictional_values_without_claiming_screenshots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root / "example")
            result = archive(root / "example", root / "example" / "observations.json", facts(root),
                             root / "build.sqlite")
            self.assertEqual((result.get("synthetic"),
                              "Синтетический пример" in "\n".join(result["coverage"]),
                              "Скриншот «" in "\n".join(result["coverage"]),
                              "Значения пользователя сохранены" in "\n".join(result["coverage"])),
                             (True, True, False, False))

    def test_secondary_tree_does_not_infer_an_unselected_twelve_point_core(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            guide = json.loads((directory / "guide-data.json").read_text(encoding="utf-8"))
            guide["talentTrees"][0]["points"] = 29
            write(directory / "guide-data.json", guide)
            self.assertNotIn("core на пороге 12 не выбран", "\n".join(archive(
                directory, observations(root), facts(root), root / "build.sqlite")["coverage"]))

    def test_prism_core_override_is_preserved_with_its_actual_description(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            build = json.loads((directory / "build.json").read_text(encoding="utf-8"))
            slot = build["loadouts"]["loadouts"][0]["skillTree"]["slots"][0]
            slot.update(selectedNotable24=None,
                        prismCoreTalentOverride={"name": "Crushing Blast", "description": "+31% vs Elites", "iconUrl": ""},
                        equippedPrism={"replacesCoreTalent": True})
            write(directory / "build.json", build)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["buildSha256"] = hashlib.sha256((directory / "build.json").read_bytes()).hexdigest()
            write(directory / "manifest.json", manifest)
            result = archive(directory, observations(root), facts(root), root / "build.sqlite")
            self.assertTrue(all(value in json.dumps(result["inventory"]["talents"], ensure_ascii=False)
                                for value in ("Замена core призмой", "Crushing Blast", "+31% vs Elites")))


class ArchiveSlateTest(unittest.TestCase):
    """Keep decoded slate effects visible without assuming their board layout."""

    def test_keeps_six_decoded_slates_in_the_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            slates(directory, 6)
            self.assertEqual([entry["name"] for entry in archive(
                directory, observations(root), facts(root), root / "build.sqlite",
            )["inventory"]["slates"]], [f"Synthetic slate {index}" for index in range(6)])

    def test_decoded_slate_keeps_source_effects_and_unknown_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            slates(directory, 1)
            text = "\n".join(archive(directory, observations(root), facts(root), root / "build.sqlite")
                             ["inventory"]["slates"][0]["details"])
            self.assertTrue(all(value in text for value in (
                "sourceBaseId: synthetic-base-0", "catalogBase: synthetic-base-guid-0",
                "sourceEncoding: rpc.WareHousePosItem", "influenceCorroborated: true",
                "provenance: transfer-report.json / systems.divinity.decodedSlates[0]",
                "layout: unknown (shape, direction, board position)", "damage application: not applied automatically",
                "enchant[2]", "synthetic-effect-0", "synthetic-mod-0", "Medium Talent", "Synthetic School",
                "+17% Synthetic Cold Damage",
            )))

    def test_slate_without_catalog_base_keeps_its_effects_and_unknown_identifiers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            report = slates(directory, 1)
            transfer = json.loads(report.read_text(encoding="utf-8"))
            transfer["systems"]["divinity"]["decodedSlates"][0].update(
                catalogBase=None, unmappedTalentIds=["synthetic-unmapped"],
            )
            write(report, transfer)
            entry = archive(directory, observations(root), facts(root), root / "build.sqlite")["inventory"]["slates"][0]
            self.assertEqual((entry["name"], "catalogBase: unknown" in entry["details"],
                              'unmappedTalentIds: ["synthetic-unmapped"]' in entry["details"],
                              "+17% Synthetic Cold Damage" in "\n".join(entry["details"])),
                             ("Unknown divinity slate (synthetic-base-0)", True, True, True))

    def test_system_details_and_coverage_keep_the_decoded_effect_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            slates(directory, 6)
            result = archive(directory, observations(root), facts(root), root / "build.sqlite")
            system = next(entry for entry in result["inventory"]["systems"] if entry["name"] == "divinity")
            self.assertEqual(("decodedEffects: 6" in system["details"],
                              "decodedEffects: 6" in "\n".join(result["coverage"])), (True, True))

    def test_coverage_identifies_manual_observations_as_developer_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertTrue(any("developer input" in line and "автоматический импорт" in line
                                and "неполный" in line for line in archive(
                                    package(root), observations(root), facts(root), root / "build.sqlite",
                                )["coverage"]))

    def test_decoded_slates_do_not_change_planner_layout_or_character_stats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            slates(directory, 6)
            database = root / "build.sqlite"
            result = archive(directory, observations(root), facts(root), database)
            with contextlib.closing(sqlite3.connect(database)) as connection:
                row = connection.execute("SELECT report, build FROM systems WHERE name = 'divinity'").fetchone()
            report = json.loads(row[0])
            self.assertEqual((report["status"], report["mapped"], report["effectMappingComplete"],
                              report["decodedEffects"], len(report["decodedSlates"]), json.loads(row[1]),
                              result["stats"]["spell_dps"]),
                             ("partial", 0, False, 6, 6, {"inventory": [], "placements": []}, 31729))

    def test_decoded_slate_inventory_is_preserved_in_sqlite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            slates(directory, 1)
            database = root / "build.sqlite"
            archive(directory, observations(root), facts(root), database)
            with contextlib.closing(sqlite3.connect(database)) as connection:
                row = connection.execute("SELECT name, details FROM inventory WHERE section = 'slates'").fetchone()
            self.assertEqual((row[0], "+17% Synthetic Cold Damage" in "\n".join(json.loads(row[1]))),
                             ("Synthetic slate 0", True))


class ArchiveNativeTest(unittest.TestCase):
    """Bind corroborated automatic stats to the exact captured source."""

    def test_native_spell_dps_and_survival_replace_only_their_developer_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            result = archive(directory, observations(root), facts(root), root / "build.sqlite",
                             native_stats=native(root, directory))
            self.assertEqual((result["stats"]["spell_dps"], result["benchmark"]["survival"],
                              result["stats"]["hit_min"], result["benchmark"]["average_dps"]),
                             (43721, 8033, 842700, 185319))

    def test_native_stats_cannot_belong_to_another_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = native(root, directory)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["source"]["sha256"] = "7" * 64
            write(path, document)
            with self.assertRaisesRegex(ValueError, "Native stats source sha256"):
                archive(directory, observations(root), facts(root), root / "build.sqlite", native_stats=path)

    def test_native_stats_cannot_use_an_unknown_format_or_undecoded_status(self):
        for field, value in (("format", "future-format"), ("status", "absent"), ("status", "unsupported")):
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = package(root)
                path = native(root, directory)
                document = json.loads(path.read_text(encoding="utf-8"))
                document[field] = value
                write(path, document)
                with self.assertRaisesRegex(ValueError, "Native stats"):
                    archive(directory, observations(root), facts(root), root / "build.sqlite", native_stats=path)

    def test_native_fields_require_the_exact_corroborated_wire_contract(self):
        for field, value in (("key", "cast_rate"), ("wire", "1.11"), ("wireType", "float64"),
                             ("evidence", "inferred"), ("protocolVerified", True), ("sourcePath", "other"),
                             ("corroboration", ""), ("value", -1), ("value", True), ("value", 1.5)):
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = package(root)
                path = native(root, directory)
                document = json.loads(path.read_text(encoding="utf-8"))
                document["known"][0][field] = value
                write(path, document)
                with self.assertRaisesRegex(ValueError, "Native stats"):
                    archive(directory, observations(root), facts(root), root / "build.sqlite", native_stats=path)

    def test_native_summary_discloses_named_count_unknown_count_and_missing_automatic_stats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            result = archive(directory, observations(root), facts(root), root / "build.sqlite",
                             native_stats=native(root, directory))
            self.assertEqual(result["native_stats"], {
                "format": "tli-native-stats-v1", "status": "decoded", "known": 2, "unknown_stat_ids": 1,
                "source_sha256": hashlib.sha256((directory / "source.json").read_bytes()).hexdigest(),
                "protocol_verified": False, "missing_trait_levels": True,
                "missing_automatic_stats": ["hit_min", "hit_max", "cast_rate", "crit_chance", "crit_multiplier",
                                            "max_tangles", "extra_attachments", "cold_penetration", "armour_mitigation"],
            })

    def test_native_provenance_uses_json_evidence_and_preserves_the_input_document_and_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = native(root, directory)
            database = root / "build.sqlite"
            result = archive(directory, observations(root), facts(root), database, native_stats=path)
            rows = {row["key"]: row for row in result["observations"]}
            with contextlib.closing(sqlite3.connect(database)) as connection:
                source = connection.execute("SELECT path, sha256, stored FROM sources WHERE role='native_stats'").fetchone()
                original = json.loads(connection.execute("SELECT json FROM documents WHERE role='observations'").fetchone()[0])
                imported = json.loads(connection.execute("SELECT json FROM documents WHERE role='native_stats'").fetchone()[0])
            self.assertEqual((source, original["panel"][0]["value"], imported["known"][0]["value"],
                              rows["spell_dps"]["evidence"], rows["benchmark_survival"]["evidence"],
                              "wire 1.10" in rows["spell_dps"]["precision"],
                              "exact integer" in rows["spell_dps"]["precision"]),
                             ((str(path.resolve()), hashlib.sha256(path.read_bytes()).hexdigest(), 1),
                              31729, 43721, str(path.resolve()), str(path.resolve()), True, True))

    def test_native_coverage_discloses_conflicting_values_and_unverified_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            text = "\n".join(archive(directory, observations(root), facts(root), root / "build.sqlite",
                                    native_stats=native(root, directory))["coverage"])
            self.assertTrue(all(value in text for value in (
                "Native stats conflict: spell_dps", "31729", "43721", "Native stats conflict: survival", "9127", "8033",
                "protocolVerified=false", "unknownStatIds: 1", "missing hero trait levels", "hit_min",
                "Synthetic unnamed attributes have no verified names",
            )))

    def test_detects_the_decoded_native_stats_declared_by_the_package_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            (directory / "native-stats.json").write_bytes(native(root, directory).read_bytes())
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["nativeStats"] = {"file": "native-stats.json", "status": "decoded", "known": 2, "protocolVerified": False}
            write(directory / "manifest.json", manifest)
            result = archive(directory, observations(root), facts(root), root / "build.sqlite")
            self.assertEqual((result["stats"]["spell_dps"], result["native_stats"]["known"]), (43721, 2))

    def test_native_manifest_cannot_select_a_path_outside_the_fixed_package_file(self):
        for name in ("../native-stats.json", "nested/native-stats.json", "C:/native-stats.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = package(root)
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                manifest["nativeStats"] = {"file": name, "status": "decoded", "known": 2, "protocolVerified": False}
                write(directory / "manifest.json", manifest)
                with self.assertRaisesRegex(ValueError, "Native stats manifest file"):
                    archive(directory, observations(root), facts(root), root / "build.sqlite")

    def test_missing_native_survival_keeps_developer_input_with_an_explicit_gap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = native(root, directory)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["known"] = document["known"][:1]
            document["coverage"].update(known=1, missing=["survival"])
            write(path, document)
            result = archive(directory, observations(root), facts(root), root / "build.sqlite", native_stats=path)
            self.assertEqual((result["benchmark"]["survival"], result["native_stats"]["known"],
                              "Native stats missing known fields: survival" in "\n".join(result["coverage"])),
                             (9127, 1, True))

    def test_native_coverage_counts_cannot_disagree_with_the_input_entries(self):
        for field in ("known", "unknownStatIds", "unknownEntries", "omitted"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = package(root)
                path = native(root, directory)
                document = json.loads(path.read_text(encoding="utf-8"))
                document["coverage"][field] += 1
                write(path, document)
                with self.assertRaisesRegex(ValueError, "Native stats coverage counts"):
                    archive(directory, observations(root), facts(root), root / "build.sqlite", native_stats=path)

    def test_native_fields_cannot_be_duplicated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = native(root, directory)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["known"].append(dict(document["known"][0]))
            document["coverage"]["known"] = 3
            write(path, document)
            with self.assertRaisesRegex(ValueError, "Native stats contain an unsupported or duplicate"):
                archive(directory, observations(root), facts(root), root / "build.sqlite", native_stats=path)

    def test_unavailable_native_bundle_keeps_an_explicit_developer_fallback(self):
        for status in ("absent", "unsupported", "error"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = package(root)
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                manifest["nativeStats"] = {"file": "native-stats.json", "status": status, "known": 0, "protocolVerified": False}
                write(directory / "manifest.json", manifest)
                result = archive(directory, observations(root), facts(root), root / "build.sqlite")
                self.assertEqual((result["stats"]["spell_dps"], any(
                    f"Native stats bundle status: {status}" in line and "developer input" in line
                    for line in result["coverage"])), (31729, True))

    def test_explicit_native_input_takes_priority_over_manifest_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["nativeStats"] = {"file": "../unselected.json", "status": "decoded", "known": 2, "protocolVerified": False}
            write(directory / "manifest.json", manifest)
            self.assertEqual(archive(directory, observations(root), facts(root), root / "build.sqlite",
                                     native_stats=native(root, directory))["stats"]["spell_dps"], 43721)

    def test_invalid_native_hash_does_not_leave_a_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = native(root, directory)
            document = json.loads(path.read_text(encoding="utf-8"))
            del document["source"]["sha256"]
            write(path, document)
            database = root / "build.sqlite"
            try:
                archive(directory, observations(root), facts(root), database, native_stats=path)
            except ValueError:
                pass
            self.assertFalse(database.exists())


class ArchiveImportTest(unittest.TestCase):
    """Import available package data without fabricating developer observations."""

    def test_imports_native_stats_and_inventory_without_manual_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            result = archive(directory, None, facts(root), root / "build.sqlite", native_stats=native(root, directory))
            self.assertEqual((result["stats"], result["benchmark"], result["import_status"], result["missing_stats"],
                              [row["key"] for row in result["observations"]], len(result["inventory"]["gear"])),
                             ({"spell_dps": 43721}, {"survival": 8033}, "partial",
                              ["hit_min", "hit_max", "cast_rate", "crit_chance", "crit_multiplier",
                               "max_tangles", "extra_attachments", "cold_penetration"],
                              ["spell_dps", "benchmark_survival"], 1))

    def test_import_without_native_stats_keeps_missing_values_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = archive(package(root), None, facts(root), root / "build.sqlite")
            self.assertEqual((result["stats"], result["benchmark"], result["observations"],
                              result["import_status"], result["missing_stats"]),
                             ({}, {}, [], "partial", ["spell_dps", "hit_min", "hit_max", "cast_rate", "crit_chance",
                                                       "crit_multiplier", "max_tangles", "extra_attachments",
                                                       "cold_penetration"]))

    def test_import_without_manual_input_does_not_create_observation_documents_or_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            database = root / "build.sqlite"
            archive(directory, None, facts(root), database, native_stats=native(root, directory))
            with contextlib.closing(sqlite3.connect(database)) as connection:
                self.assertEqual((connection.execute("SELECT count(*) FROM sources WHERE role='observations'").fetchone()[0],
                                  connection.execute("SELECT count(*) FROM documents WHERE role='observations'").fetchone()[0],
                                  connection.execute("SELECT count(*) FROM sources WHERE role LIKE 'evidence:native_stats:%'").fetchone()[0]),
                                 (0, 0, 2))

    def test_import_coverage_lists_missing_benchmark_fields_without_claiming_manual_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            text = "\n".join(archive(directory, None, facts(root), root / "build.sqlite",
                                    native_stats=native(root, directory))["coverage"])
            self.assertEqual(("Missing benchmark fields: average_dps, duration, highest_5s, average_5s" in text,
                              any(marker in text for marker in ("скриншот", "Скриншот", "Damage (Level", "observations.json"))),
                             (True, False))

    def test_explicit_manual_input_still_requires_all_required_stats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = observations(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["panel"] = [row for row in data["panel"] if row["key"] != "hit_min"]
            write(path, data)
            with self.assertRaisesRegex(ValueError, "Missing stats: hit_min"):
                archive(directory, path, facts(root), root / "build.sqlite", native_stats=native(root, directory))

    def test_explicit_manual_input_still_requires_the_benchmark_damage_measurement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = observations(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["benchmark"]["values"] = [row for row in data["benchmark"]["values"] if row["key"] != "average_dps"]
            write(path, data)
            with self.assertRaisesRegex(ValueError, "Missing benchmark: average_dps"):
                archive(package(root), path, facts(root), root / "build.sqlite")

    def test_import_without_manual_input_still_rejects_native_stats_from_another_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = native(root, directory)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["source"]["sha256"] = "5" * 64
            write(path, document)
            with self.assertRaisesRegex(ValueError, "Native stats source sha256"):
                archive(directory, None, facts(root), root / "build.sqlite", native_stats=path)

    def test_native_bundle_import_does_not_read_an_unselected_observations_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            (directory / "native-stats.json").write_bytes(native(root, directory).read_bytes())
            (directory / "observations.json").write_text("malformed unselected developer file", encoding="utf-8")
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["nativeStats"] = {"file": "native-stats.json", "status": "decoded", "known": 2, "protocolVerified": False}
            write(directory / "manifest.json", manifest)
            self.assertEqual(archive(directory, None, facts(root), root / "build.sqlite")["stats"], {"spell_dps": 43721})

    def test_failed_native_bundle_does_not_claim_nonexistent_developer_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["nativeStats"] = {"file": "native-stats.json", "status": "error", "known": 0, "protocolVerified": False}
            write(directory / "manifest.json", manifest)
            result = archive(directory, None, facts(root), root / "build.sqlite")
            text = "\n".join(result["coverage"])
            self.assertEqual((result["stats"], result["benchmark"], "no manual observations were provided" in text,
                              "developer input remains in use" in text), ({}, {}, True, False))

    def test_synthetic_import_does_not_claim_that_a_benchmark_was_supplied(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            guide = json.loads((directory / "guide-data.json").read_text(encoding="utf-8"))
            guide["synthetic"] = True
            write(directory / "guide-data.json", guide)
            text = "\n".join(archive(directory, None, facts(root), root / "build.sqlite")["coverage"])
            self.assertEqual(("Синтетический пример: состав пакета" in text,
                              "бенчмарк вымышлены" in text), (True, False))


class ArchivePanelLogTest(unittest.TestCase):
    """Corroborate automatic panel evidence using the same package native anchor."""

    def test_raw_and_normalized_logs_cannot_be_supplied_together(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            with self.assertRaisesRegex(ValueError, "game_log and panel_log are mutually exclusive"):
                archive(directory, None, facts(root), root / "build.sqlite",
                        native_stats=native(root, directory), panel_log=panel(root, "43721.25"),
                        game_log=game(root, "43721.25"))

    def test_raw_game_log_imports_without_manual_or_intermediate_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = game(root, "43721.25")
            result = archive(directory, None, facts(root), root / "build.sqlite",
                             native_stats=native(root, directory), game_log=path)
            self.assertEqual((result["stats"]["spell_dps"], result["stats"]["cast_rate"], result["missing_stats"],
                              result["panel_log"]["input_kind"], result["panel_log"]["identity_verified"],
                              next(row["evidence"] for row in result["observations"] if row["key"] == "hit_min"),
                              sorted(path.name for path in root.iterdir())),
                             (43721.25, 4.8125, [], "game_log", False, str(path.resolve()),
                              ["build.sqlite", "facts.json", "game.log", "native-stats.json", "package"]))

    def test_optional_armor_penetration_keeps_its_fraction_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = panel(root, "43721.25")
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cohorts"][0]["attributes"].append({
                "id": "11201", "name": "Armor DMG Mitigation Penetration", "status": "resolved",
                "values": [7.375], "raw_values": ["7.375"], "line_numbers": [41, 42]})
            write(path, data)
            result = archive(directory, None, facts(root), root / "build.sqlite",
                             native_stats=native(root, directory), panel_log=path)
            row = next(row for row in result["observations"] if row["key"] == "armor_penetration")
            self.assertEqual((result["stats"]["armor_penetration"], row["unit"], row["source"]["attr_id"],
                              row["source"]["raw_value"], result["missing_stats"], result["panel_log"]["known"]),
                             (.07375, "fraction", "11201", "7.375", [], 10))

    def test_raw_snapshot_provenance_cannot_reread_a_growing_log(self):
        from damage_lab.logstats import select

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = game(root, "43721.25")
            original = path.read_bytes()

            def selecting(document, expected):
                with path.open("ab") as handle:
                    handle.write(b"Unrelated private-growth-canary\n")
                return select(document, expected)

            with patch("damage_lab.logstats.select", new=selecting):
                result = archive(directory, None, facts(root), root / "build.sqlite",
                                 native_stats=native(root, directory), game_log=path)
            with contextlib.closing(sqlite3.connect(root / "build.sqlite")) as connection:
                source = connection.execute("SELECT path, sha256, bytes, stored FROM sources WHERE role='game_log'").fetchone()
                evidence = connection.execute("SELECT sha256, bytes FROM sources WHERE role='evidence:panel_log:cast_rate'").fetchone()
                document = json.loads(connection.execute("SELECT json FROM documents WHERE role='panel_log'").fetchone()[0])
                self.assertEqual((source, evidence, result["panel_log"]["source_sha256"],
                                  document["source"]["bytesRead"], len(path.read_bytes()) > len(original),
                                  "private-growth-canary" in dump(root / "build.sqlite")),
                                 ((str(path.resolve()), hashlib.sha256(original).hexdigest(), len(original), 0),
                                  (hashlib.sha256(original).hexdigest(), len(original)),
                                  hashlib.sha256(original).hexdigest(), len(original), True, False))

    def test_raw_log_cannot_use_manual_dps_as_its_native_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "corroborated native Spell DPS anchor"):
                archive(package(root), observations(root), facts(root), root / "build.sqlite",
                        game_log=game(root, "31729"))

    def test_ambiguous_raw_cohorts_cannot_choose_a_damage_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = game(root, "43721.25")
            with path.open("a", encoding="utf-8") as handle:
                handle.write(path.read_text(encoding="utf-8").replace("[713]", "[719]").replace("4.8125", "4.9375"))
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                archive(directory, None, facts(root), root / "build.sqlite",
                        native_stats=native(root, directory), game_log=path)

    def test_native_anchored_log_completes_required_stats_without_manual_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            result = archive(directory, None, facts(root), root / "build.sqlite",
                             native_stats=native(root, directory), panel_log=panel(root, "43721.25"))
            self.assertEqual((result["stats"], result["benchmark"], result["missing_stats"],
                              result["native_stats"]["missing_automatic_stats"], result["import_status"],
                              result["panel_log"]["status"], result["panel_log"]["identity_verified"]),
                             ({"spell_dps": 43721.25, "hit_min": 731.125, "hit_max": 1117.625,
                               "cast_rate": 4.8125, "crit_chance": .3175, "crit_multiplier": 2.875,
                               "max_tangles": 3, "extra_attachments": 2, "cold_penetration": .0925},
                              {"survival": 8033}, [], [], "partial", "corroborated", False))

    def test_manual_spell_dps_cannot_supply_a_missing_native_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "corroborated native Spell DPS anchor"):
                archive(package(root), observations(root), facts(root), root / "build.sqlite",
                        panel_log=panel(root, "31729"))

    def test_native_survival_cannot_supply_a_spell_dps_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = native(root, directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["known"] = data["known"][1:]
            data["coverage"]["known"] = 1
            data["coverage"]["missing"] = ["spell_dps"]
            write(path, data)
            with self.assertRaisesRegex(ValueError, "corroborated native Spell DPS anchor"):
                archive(directory, observations(root), facts(root), root / "build.sqlite",
                        native_stats=path, panel_log=panel(root, "31729"))

    def test_mismatched_log_cannot_leave_an_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            with self.assertRaisesRegex(ValueError, "match"):
                archive(directory, None, facts(root), root / "build.sqlite",
                        native_stats=native(root, directory), panel_log=panel(root, "43722"))
            self.assertFalse((root / "build.sqlite").exists())

    def test_ambiguous_log_cannot_choose_a_cohort(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = panel(root, "43721.25")
            data = json.loads(path.read_text(encoding="utf-8"))
            cohort = json.loads(json.dumps(data["cohorts"][0]))
            cohort.update(frame=719, timestamp="2001-02-03T04:05:08.000Z")
            cohort["attributes"][2].update(values=[4.9375], raw_values=["4.9375"])
            data["cohorts"].append(cohort)
            write(path, data)
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                archive(directory, None, facts(root), root / "build.sqlite",
                        native_stats=native(root, directory), panel_log=path)

    def test_log_keeps_evidence_precision_and_original_numeric_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = panel(root, "43721.25")
            result = archive(directory, None, facts(root), root / "build.sqlite",
                             native_stats=native(root, directory), panel_log=path)
            row = next(row for row in result["observations"] if row["key"] == "spell_dps")
            self.assertEqual((row["evidence"], row["precision"], row["source"]),
                             (str(path.resolve()), "printed token; rounding unknown; corroborated; identity_verified=false",
                              {"attr_id": "10103", "index": 1, "raw_value": "43721.25",
                               "raw_values": ["43721.25"],
                               "timestamp": "2001-02-03T04:05:07.000Z", "frame": 713,
                               "line_numbers": [17, 18]}))

    def test_panel_numeric_policy_reaches_json_sqlite_and_html_without_exactness_claims(self):
        from damage_lab.importer import snapshot
        from damage_lab.report import render_import

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            result = archive(directory, None, facts(root), root / "build.sqlite",
                             native_stats=native(root, directory), panel_log=panel(root, "43721.25"))
            with contextlib.closing(sqlite3.connect(root / "build.sqlite")) as connection:
                selection = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='panel_log_selection'").fetchone()[0])
            page = render_import(snapshot(result))
            self.assertEqual((result["panel_log"]["numeric_policy"], snapshot(result)["panel_log"]["numeric_policy"],
                              selection["summary"]["numeric_policy"],
                              "Точность печати неизвестна" in page, "full-precision log" in page),
                             ({"printer_precision": "unknown", "stored_numbers": "binary64", "raw_tokens": "preserved",
                               "native_anchor": {"operator": "absolute_difference_lte", "tolerance": "0.5", "unit": "damage/s",
                                                 "meaning": "selection_heuristic", "rounding_verified": False}},
                              result["panel_log"]["numeric_policy"], result["panel_log"]["numeric_policy"], True, False))

    def test_database_keeps_log_document_hash_and_rounded_native_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = panel(root, "43721.25")
            archive(directory, None, facts(root), root / "build.sqlite",
                    native_stats=native(root, directory), panel_log=path)
            with contextlib.closing(sqlite3.connect(root / "build.sqlite")) as connection:
                documents = {role: json.loads(value) for role, value in connection.execute("SELECT role, json FROM documents")}
                source = connection.execute("SELECT path, sha256, stored FROM sources WHERE role='panel_log'").fetchone()
                self.assertEqual((documents["panel_log"], documents["panel_log_selection"]["summary"]["source_sha256"],
                                  documents["native_stats"]["known"][0]["value"], source),
                                 (json.loads(path.read_text(encoding="utf-8")), "b" * 64, 43721,
                                  (str(path.resolve()), hashlib.sha256(path.read_bytes()).hexdigest(), 1)))

    def test_manual_conflicts_remain_explicit_after_log_enrichment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            result = archive(directory, observations(root), facts(root), root / "build.sqlite",
                             native_stats=native(root, directory), panel_log=panel(root, "43721.25"))
            self.assertTrue(any("Panel log conflict: cast_rate; previous input 4.73; corroborated log 4.8125 used" == item
                                for item in result["coverage"]))

    def test_log_cannot_remove_strict_manual_benchmark_requirements(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            path = observations(root)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["benchmark"]["values"] = []
            write(path, data)
            with self.assertRaisesRegex(ValueError, "benchmark"):
                archive(directory, path, facts(root), root / "build.sqlite",
                        native_stats=native(root, directory), panel_log=panel(root, "43721.25"))


class ArchiveWitnessTest(unittest.TestCase):
    """Keep verified companion references in ordinary imports without storing private log text."""

    def test_witness_survives_archive_snapshot_sqlite_and_import_html(self):
        from damage_lab.buildinputs import assemble
        from damage_lab.buildinputreport import render
        from damage_lab.importer import snapshot
        from damage_lab.report import render_import
        from test_damage_report import pages
        from test_witnessbundle import persisted

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor, _ = persisted(directory)
            manifest = json.loads((directory / 'manifest.json').read_text())
            manifest['selectedBuildWitness'] = descriptor
            write(directory / 'manifest.json', manifest)
            result = archive(directory, None, facts(root), root / 'build.sqlite')
            with contextlib.closing(sqlite3.connect(root / 'build.sqlite')) as connection:
                document = json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role='selected_build_witness'").fetchone()[0])
                origin = connection.execute(
                    "SELECT stored FROM sources WHERE role='selected_build_witness'").fetchone()[0]
            html = render_import(snapshot(result)) + render(assemble(result, skill_alias='gem[999]'))
            html += ''.join(pages(result))
            self.assertEqual((document, snapshot(result)['selected_build_witness'], origin,
                              html.count('Сверка уровней с журналом'),
                              'SYNTHETIC-CANARY' in html + json.dumps(snapshot(result)) + dump(root / 'build.sqlite')),
                             (result['selected_build_witness'], document, 1, 4, False))

    def test_invalid_companion_becomes_visible_rejection_without_aborting_import(self):
        from damage_lab.importer import snapshot
        from test_witnessbundle import persisted

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor, _ = persisted(directory)
            descriptor['eventIndex'] = 1
            manifest = json.loads((directory / 'manifest.json').read_text())
            manifest['selectedBuildWitness'] = descriptor
            write(directory / 'manifest.json', manifest)
            result = snapshot(archive(directory, None, facts(root), root / 'build.sqlite'))
            self.assertEqual((result['import_status'], result['selected_build_witness']['status'],
                              result['selected_build_witness']['reason'], result['selected_build_witness']['artifact']),
                             ('partial', 'rejected', 'binding_failed', None))

    def test_explicit_not_requested_survives_without_new_files(self):
        from test_witnessbundle import descriptor

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            manifest = json.loads((directory / 'manifest.json').read_text())
            manifest['selectedBuildWitness'] = descriptor('not_requested')
            write(directory / 'manifest.json', manifest)
            self.assertEqual(archive(directory, None, facts(root), root / 'build.sqlite')[
                'selected_build_witness']['status'], 'not_requested')

    def test_legacy_imports_keep_witness_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertNotIn('selected_build_witness', archive(package(root), None, facts(root), root / 'build.sqlite'))

    def test_source_bound_error_survives_without_packet_copy(self):
        from damage_lab.importer import snapshot
        from test_witnessbundle import failed

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            _, descriptor, _ = failed(directory)
            (directory / 'state-log-packet.json').unlink()
            manifest = json.loads((directory / 'manifest.json').read_text())
            manifest['selectedBuildWitness'] = descriptor
            write(directory / 'manifest.json', manifest)
            self.assertEqual(snapshot(archive(directory, None, facts(root), root / 'build.sqlite'))[
                'selected_build_witness']['integrity']['references'], 'artifact_verified')

    def test_witness_does_not_change_stats_or_the_blocked_raw_model(self):
        from damage_lab.buildinputs import assemble
        from test_witnessbundle import persisted

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = package(root)
            before = archive(directory, observations(root), facts(root), root / 'before.sqlite')
            _, descriptor, _ = persisted(directory)
            manifest = json.loads((directory / 'manifest.json').read_text())
            manifest['selectedBuildWitness'] = descriptor
            write(directory / 'manifest.json', manifest)
            after = archive(directory, observations(root), facts(root), root / 'after.sqlite')
            diagnostic = assemble(after, skill_alias='gem[999]')
            self.assertEqual((after['stats'], after['benchmark'], diagnostic['status'], diagnostic['arithmetic_ready']),
                             (before['stats'], before['benchmark'], 'blocked', False))


class ArchiveSkillValuesTest(unittest.TestCase):
    """Preserve catalog skill parameters without applying them as damage modifiers."""

    def test_missing_export_parameters_remain_unavailable_in_result_and_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = archive(package(root), None, facts(root), root / "build.sqlite")
            with contextlib.closing(sqlite3.connect(root / "build.sqlite")) as connection:
                document = connection.execute("SELECT json FROM documents WHERE role='skill_values'").fetchone()
                self.assertEqual(([(row["name"], row["status"], row["values"]) for row in result["skill_values"]],
                                  json.loads(document[0])),
                                 ([("Chromatic Shot", "unavailable", {}),
                                   ("Activation Medium: Tangle", "unavailable", {})], result["skill_values"]))


class ArchiveDatabaseTest(unittest.TestCase):
    """Check what a fresh SQLite archive stores and what stays out of it."""

    def test_new_database_holds_hashed_sources_observations_facts_and_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = package(root)
            database = root / "build.sqlite"
            archive(source, observations(root), facts(root), database)
            with contextlib.closing(sqlite3.connect(database)) as connection:
                hashes = dict(connection.execute("SELECT role, sha256 FROM sources"))
                self.assertEqual(hashes["build"], hashlib.sha256((source / "build.json").read_bytes()).hexdigest())
                self.assertEqual(hashes["source"], hashlib.sha256((source / "source.json").read_bytes()).hexdigest())
                self.assertIn("evidence:panel", hashes)
                self.assertEqual(connection.execute(
                    "SELECT value FROM observations WHERE key = 'benchmark_average_dps'").fetchone()[0], 185319)
                self.assertEqual(json.loads(connection.execute(
                    "SELECT json FROM documents WHERE role = 'facts'").fetchone()[0])["chromatic"], {"id": 7007})
                self.assertEqual(connection.execute(
                    "SELECT name FROM inventory WHERE section = 'gear'").fetchone()[0], "Tyrant's Smoldering Hold")
                self.assertTrue(connection.execute("SELECT count(*) FROM systems").fetchone()[0])

    def test_raw_source_and_source_sections_stay_out_of_database_and_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "build.sqlite"
            result = archive(package(root), observations(root), facts(root), database)
            for text in (dump(database), json.dumps(result, ensure_ascii=False)):
                self.assertNotIn("RAW-SOURCE-MARKER", text)
                self.assertNotIn("SOURCE-SECTION-MARKER", text)


class ArchivePrecisionTest(unittest.TestCase):
    """Check that displayed numbers survive with their units and rounding."""

    def test_displayed_double_damage_observation_cannot_exceed_a_probability(self):
        from damage_lab.archive import recorded

        data = {"evidence": {"panel": {"path": "synthetic-evidence"}},
                "panel": [{"key": "double_damage_chance", "label": "Double Damage Chance", "value": 1.1375,
                           "display": "113.75%", "unit": "fraction", "evidence": "panel"}],
                "benchmark": {"values": [], "evidence": "panel"}}
        with self.assertRaisesRegex(ValueError, "double_damage_chance"):
            recorded(data, partial=True)

    def test_displayed_double_damage_observation_requires_fraction_units(self):
        from damage_lab.archive import recorded

        data = {"evidence": {"panel": {"path": "synthetic-evidence"}},
                "panel": [{"key": "double_damage_chance", "label": "Double Damage Chance", "value": 0.375,
                           "display": "0.375", "unit": "count", "evidence": "panel"}],
                "benchmark": {"values": [], "evidence": "panel"}}
        with self.assertRaisesRegex(ValueError, "unit must be fraction"):
            recorded(data, partial=True)

    def test_named_spell_burst_observations_cannot_use_negative_or_fractional_counts(self):
        from damage_lab.archive import recorded

        for value in (-3, 2.75):
            data = {"evidence": {"panel": {"path": "synthetic-evidence"}},
                    "panel": [{"key": "max_spell_burst", "label": "Max Spell Burst", "value": value,
                               "display": str(value), "unit": "count", "evidence": "panel"}],
                    "benchmark": {"values": [], "evidence": "panel"}}
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "max_spell_burst"):
                recorded(data, partial=True)

    def test_rounded_display_keeps_unit_and_precision_without_inventing_digits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "build.sqlite"
            result = archive(package(root), observations(root), facts(root), database)
            rows = {row["key"]: row for row in result["observations"]}
            self.assertEqual((rows["hit_min"]["value"], rows["hit_min"]["unit"]), (842700, "damage"))
            self.assertIn("842.7K", rows["hit_min"]["precision"])
            self.assertIn("±50 ", rows["hit_min"]["precision"])
            self.assertIn("±50000 ", rows["hit_max"]["precision"])
            self.assertEqual((rows["crit_chance"]["value"], rows["crit_chance"]["unit"]), (0.4137, "fraction"))
            self.assertIn("±0.00005 ", rows["crit_chance"]["precision"])
            with contextlib.closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute(
                    "SELECT value, unit, display FROM observations WHERE key = 'crit_multiplier'").fetchone(),
                    (2.87, "multiplier", "287%"))

    def test_value_that_lost_its_percent_scale_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "build.sqlite"
            wrong = {"key": "cold_bonus", "label": "Cold Damage Bonus", "display": "93%", "value": 93,
                     "unit": "fraction", "evidence": "panel"}
            with self.assertRaisesRegex(ValueError, "cold_bonus"):
                archive(package(root), observations(root, panel=[wrong]), facts(root), database)
            self.assertFalse(database.exists())


class ArchiveSafetyTest(unittest.TestCase):
    """Check that archiving never replaces or half-writes a database."""

    def test_existing_database_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "build.sqlite"
            database.write_bytes(b"previous archive")
            with self.assertRaises(FileExistsError):
                archive(package(root), observations(root), facts(root), database)
            self.assertEqual(database.read_bytes(), b"previous archive")

    def test_build_that_differs_from_manifest_hash_leaves_no_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "build.sqlite"
            with self.assertRaisesRegex(ValueError, "build.json"):
                archive(package(root, manifest_hash="0" * 64), observations(root), facts(root), database)
            self.assertFalse(database.exists())

    def test_talent_ranks_that_disagree_between_files_are_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "prophet"):
                archive(package(root, ranks={"n1": 2}), observations(root), facts(root), root / "build.sqlite")

    def test_unknown_current_loadout_is_rejected_without_selecting_the_first(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            build = json.loads((directory / "build.json").read_text(encoding="utf-8"))
            build["loadouts"]["currentLoadoutId"] = "unknown"
            write(directory / "build.json", build)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["buildSha256"] = hashlib.sha256((directory / "build.json").read_bytes()).hexdigest()
            write(directory / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "loadout.*unknown"):
                archive(directory, observations(root), facts(root), root / "build.sqlite")

    def test_empty_loadouts_have_a_meaningful_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = package(root)
            build = json.loads((directory / "build.json").read_text(encoding="utf-8"))
            build["loadouts"]["loadouts"] = []
            write(directory / "build.json", build)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            manifest["buildSha256"] = hashlib.sha256((directory / "build.json").read_bytes()).hexdigest()
            write(directory / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "No loadouts"):
                archive(directory, observations(root), facts(root), root / "build.sqlite")


class SyntheticObservationsTest(unittest.TestCase):
    """Check fractional units and totals using self-contained fictional data."""

    def test_main_stats_are_stored_as_fractions_and_totals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root / "example")
            result = archive(root / "example", root / "example" / "observations.json", facts(root),
                             root / "build.sqlite")
            self.assertEqual(result["stats"], {"spell_dps": 31729, "hit_min": 913, "hit_max": 1437,
                                               "cast_rate": 4.73, "crit_chance": 0.4137,
                                               "crit_multiplier": 2.87, "max_tangles": 2,
                                               "extra_attachments": 1, "cold_penetration": 0.07})


FOREIGN = "LOADOUT-CANARY-0259-GUID"


def slot(guid=None, level=20, *, enabled=None):
    """One exporter-shaped skill slot (planner_transfer.py): disabled unless it names a skill."""
    return {"skillGuid": guid, "enabled": guid is not None if enabled is None else enabled, "level": level,
            "supports": [None] * 5}


def producer(root, groups, active, passive):
    """Rewrite package() into the exporter shape: guide groups with guids, loadout slots, refreshed hash."""
    directory = package(root)
    guide = json.loads((directory / "guide-data.json").read_text(encoding="utf-8"))
    guide["skillGroups"] = [{"kind": kind, "main": {"name": f"Synthetic skill {index}", "guid": guid, "level": level},
                             "supports": []} for index, (kind, guid, level) in enumerate(groups)]
    write(directory / "guide-data.json", guide)
    build = json.loads((directory / "build.json").read_text(encoding="utf-8"))
    build["loadouts"]["loadouts"][0]["skills"] = {"activeSkills": active, "passiveSkills": passive}
    write(directory / "build.json", build)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["buildSha256"] = hashlib.sha256((directory / "build.json").read_bytes()).hexdigest()
    write(directory / "manifest.json", manifest)
    return directory


GROUPS = [("active", "skill-a", 20), ("active", "skill-b", 18), ("aura", "skill-c", 15)]


def matching():
    return ([slot("skill-a", 20), slot("skill-b", 18)] + [slot() for _ in range(3)],
            [slot("skill-c", 15)] + [slot() for _ in range(3)])


class LoadoutSkillConsistencyTest(unittest.TestCase):
    """The current loadout skills and the guide groups of one package describe the same composition."""

    MESSAGE = "^Current loadout skills differ between build.json and guide-data.json$"

    def refused(self, groups, active, passive):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = producer(root, groups, active, passive)
            with self.assertRaisesRegex(ValueError, self.MESSAGE):
                archive(directory, observations(root), facts(root), root / "build.sqlite")
            self.assertFalse((root / "build.sqlite").exists())

    def test_matching_producer_slots_import_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = producer(root, GROUPS, *matching())
            result = archive(directory, observations(root), facts(root), root / "build.sqlite")
            with contextlib.closing(sqlite3.connect(root / "build.sqlite")) as connection:
                row = connection.execute("SELECT status FROM systems WHERE name = 'skills'").fetchone()
        self.assertEqual(([entry["name"] for entry in result["inventory"]["skills"]], row),
                         (["Synthetic skill 0 (level 20)", "Synthetic skill 1 (level 18)",
                           "Synthetic skill 2 (level 15)"], ("build_only",)))

    def test_a_foreign_loadout_skill_is_refused(self):
        active, passive = matching()
        active[0] = slot(FOREIGN, 20)
        self.refused(GROUPS, active, passive)

    def test_a_guide_skill_missing_from_the_loadout_is_refused(self):
        active, passive = matching()
        passive[0] = slot()
        self.refused(GROUPS, active, passive)

    def test_a_loadout_level_disagreement_is_refused(self):
        active, passive = matching()
        active[1] = slot("skill-b", 19)
        self.refused(GROUPS, active, passive)

    def test_active_and_passive_groups_do_not_cross_match(self):
        active, passive = matching()
        active[2], passive[0] = slot("skill-c", 15), slot()
        self.refused(GROUPS, active, passive)

    def test_duplicate_instances_keep_their_multiplicity(self):
        active, passive = matching()
        active[2] = slot("skill-a", 20)
        self.refused(GROUPS, active, passive)
        self.refused(GROUPS + [("active", "skill-a", 20)], *matching())

    def test_disabled_slots_cannot_hide_guide_groups(self):
        self.refused(GROUPS, [slot() for _ in range(5)], [slot() for _ in range(4)])

    def test_the_same_skill_at_two_levels_matches_each_instance(self):
        groups = [("active", "skill-a", 20), ("active", "skill-a", 7)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = producer(root, groups, [slot("skill-a", 7), slot("skill-a", 20)] + [slot() for _ in range(3)],
                                 [slot() for _ in range(4)])
            result = archive(directory, observations(root), facts(root), root / "build.sqlite")
        self.assertEqual([entry["name"] for entry in result["inventory"]["skills"]],
                         ["Synthetic skill 0 (level 20)", "Synthetic skill 1 (level 7)"])

    def test_malformed_canonical_slots_and_groups_are_refused(self):
        for label, change in (("enabled is an integer", lambda a, p, g: a[0].update(enabled=1)),
                              ("enabled is text", lambda a, p, g: a[0].update(enabled="true")),
                              ("enabled slot without a guid", lambda a, p, g: a.__setitem__(0, slot(None, 20, enabled=True))),
                              ("empty guid", lambda a, p, g: a[0].update(skillGuid="")),
                              ("boolean level", lambda a, p, g: a[0].update(level=True)),
                              ("text level", lambda a, p, g: a[0].update(level="20")),
                              ("slot is not an object", lambda a, p, g: a.__setitem__(4, None)),
                              ("float slot level", lambda a, p, g: a[0].update(level=20.0)),
                              ("guide main without a guid", lambda a, p, g: g.__setitem__(0, ("active", None, 20))),
                              ("float guide level", lambda a, p, g: g.__setitem__(0, ("active", "skill-a", 20.0))),
                              ("boolean guide level", lambda a, p, g: (g.__setitem__(0, ("active", "skill-a", True)),
                                                                       a.__setitem__(0, slot("skill-a", 1)))),
                              ("unknown guide kind", lambda a, p, g: g.__setitem__(2, ("module", "skill-c", 15)))):
            with self.subTest(label):
                active, passive = matching()
                groups = list(GROUPS)
                change(active, passive, groups)
                self.refused(groups, active, passive)

    def test_malformed_guide_groups_are_refused_safely(self):
        # Revision 0265: each shape below escaped as TypeError, AttributeError or KeyError (captures/20261026-0264).
        def guid(value):
            return lambda guide: guide["skillGroups"][0]["main"].update(guid=value)

        for label, change in (("guid is a list", guid([])), ("guid is an object", guid({})),
                              ("guid is an integer", guid(7)), ("guid is empty", guid("")),
                              ("main is null", lambda guide: guide["skillGroups"][0].update(main=None)),
                              ("group is null", lambda guide: guide["skillGroups"].__setitem__(0, None)),
                              ("main is missing", lambda guide: guide["skillGroups"][0].pop("main")),
                              ("kind is missing", lambda guide: guide["skillGroups"][0].pop("kind")),
                              ("groups are not a list", lambda guide: guide.update(skillGroups={"0": guide["skillGroups"][0]})),
                              ("groups are null", lambda guide: guide.update(skillGroups=None))):
            with self.subTest(label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = producer(root, GROUPS, *matching())
                guide = json.loads((directory / "guide-data.json").read_text(encoding="utf-8"))
                change(guide)
                write(directory / "guide-data.json", guide)
                with self.assertRaisesRegex(ValueError, self.MESSAGE):
                    archive(directory, observations(root), facts(root), root / "build.sqlite")
                self.assertFalse((root / "build.sqlite").exists())

    def test_the_import_command_refuses_a_malformed_guide_guid_safely(self):
        from damage_lab.__main__ import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = producer(root, GROUPS, *matching())
            guide = json.loads((directory / "guide-data.json").read_text(encoding="utf-8"))
            guide["skillGroups"][0]["main"]["guid"] = [FOREIGN]
            write(directory / "guide-data.json", guide)
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                code = main(["import", "--package", str(directory), "--output", str(root / "result")])
            published = (root / "result").exists()
        self.assertEqual((code, published, "differ between build.json and guide-data.json" in errors.getvalue(),
                          FOREIGN in errors.getvalue(), "Synthetic skill" in errors.getvalue()),
                         (1, False, True, False, False))

    def test_legacy_empty_arrays_keep_the_guide_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = archive(package(root), observations(root), facts(root), root / "build.sqlite")
        self.assertEqual([entry["name"] for entry in result["inventory"]["skills"]], ["Chromatic Shot (level 20)"])

    def test_the_import_command_publishes_nothing_for_a_mismatch(self):
        from damage_lab.__main__ import main

        active, passive = matching()
        active[0] = slot(FOREIGN, 20)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = producer(root, GROUPS, active, passive)
            errors = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                code = main(["import", "--package", str(directory), "--output", str(root / "result")])
            published = (root / "result").exists()
        self.assertEqual((code, published, "differ between build.json and guide-data.json" in errors.getvalue(),
                          FOREIGN in errors.getvalue(), "Synthetic skill" in errors.getvalue()),
                         (1, False, True, False, False))


if __name__ == "__main__":
    unittest.main()
