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


def rawevidence():
    """Create one safe synthetic protocol group without account or combat meaning."""
    from damage_lab.rawattrbundle import read
    from test_rawattrbundle import message, source

    with tempfile.TemporaryDirectory() as folder:
        return read(*source(folder, message(1, b"\x50\x35")))


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


def supported():
    """Pair synthetic candidate evidence with its declared master and English metadata."""
    from damage_lab.supportcatalog import project as catalog
    from damage_lab.supportinventory import project as inventory
    from test_supportcatalog import document as catalog_document
    from test_supportinventory import document as inventory_document

    data = record()
    raw = catalog_document()
    path = "skill/Noble_Support/i18n/en"
    raw["documents"].append({**raw["documents"][1], "category": "Noble_Support", "logicalPath": path,
                             "member": path, "address": f"/data/SS14/{path}.json", "byteRange": [411, 612]})
    raw["categories"]["Noble_Support"]["english"] = "present"
    data["installed_support_effects"] = inventory(inventory_document(), data["source_sha256"])
    data["installed_support_catalog"] = catalog(raw)
    return data


def profiled():
    """Keep fictional catalog lookups at observed gem levels."""
    from damage_lab.installedprofiles import project
    from test_installedprofiles import records, installation, catalog

    data = record()
    data["installed_skill_profiles"] = project(records(), installation(), catalog())
    return data


def leveled():
    """Keep a fictional source-bound level-grant bundle without an effective level."""
    from damage_lab.levelbundle import read
    from test_levelbundle import diagnostic

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        _, descriptor, source, installation = diagnostic(path)
        bundle, _ = read(path, descriptor, source, installation)
    data = record()
    data.update(source_sha256=source, installed_skills=installation, installed_level_candidates=bundle)
    return data


def memoried():
    """Keep synthetic memory definitions and declared catalog slices source-bound."""
    from damage_lab.memorybundle import read
    from test_memorybundle import diagnostic

    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        _, descriptor, source = diagnostic(directory)
        bundle, _ = read(directory, descriptor, source)
    return {**record(), "source_sha256": source, "memory_definitions": bundle}


class RawAttributeImporterTests(unittest.TestCase):
    """Keep safe protocol evidence source-bound without changing combat observations."""

    def test_snapshot_keeps_safe_raw_evidence_without_changing_the_damage_inputs(self):
        from damage_lab.importer import snapshot

        data = record()
        data["raw_attribute_evidence"] = rawevidence()
        data["source_sha256"] = data["raw_attribute_evidence"]["source"]["sha256"]
        data["raw_attribute_evidence"]["private"] = "PRIVATE-SNAPSHOT-CANARY"
        result = snapshot(data)
        self.assertEqual((result.get("raw_attribute_evidence", {}).get("status"), result["stats"],
                          "PRIVATE-SNAPSHOT-CANARY" in json.dumps(result)),
                         ("decoded", {"spell_dps": 84317}, False))

    def test_snapshot_requires_a_nonnull_enclosing_source_hash_when_raw_evidence_exists(self):
        from damage_lab.importer import snapshot

        for absent in (True, False):
            with self.subTest(absent=absent):
                data = record()
                data["raw_attribute_evidence"] = rawevidence()
                data.pop("source_sha256")
                if not absent:
                    data["source_sha256"] = None
                with self.assertRaises(ValueError):
                    snapshot(data)

    def test_snapshot_refuses_raw_evidence_from_another_source(self):
        from damage_lab.importer import snapshot

        data = {**record(), "raw_attribute_evidence": rawevidence()}
        with self.assertRaises(ValueError):
            snapshot(data)

    def test_cli_automatically_keeps_protocol_evidence_and_omits_opaque_accounts(self):
        from test_rawattrbundle import message, source

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            fixture(root / "package")
            source(root / "package", message(1, b"\x50\x35" + message(13, b"CLI-ACCOUNT-CANARY")))
            code = main(["--package", str(root / "package"), "--output", str(root / "result")])
            data = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            page = (root / "result/index.html").read_text(encoding="utf-8")
            self.assertEqual((code, data.get("raw_attribute_evidence", {}).get("status"),
                              "CLI-ACCOUNT-CANARY" in json.dumps(data) + page,
                              "Сырые протокольные показатели" in page, data["stats"]),
                             (0, "decoded", False, True, {}))


class MemoryDefinitionImporterTests(unittest.TestCase):
    """Keep imported memory facts separate from character arithmetic."""

    def test_memory_definitions_survive_the_snapshot_without_changing_stats(self):
        from damage_lab.importer import snapshot

        data = memoried()
        result = snapshot(data)
        self.assertEqual((result["memory_definitions"], result["stats"], result["benchmark"]),
                         (data["memory_definitions"], {"spell_dps": 84317}, {"survival": 9217}))

    def test_memory_summary_distinguishes_absence_from_a_null_document(self):
        from damage_lab.importer import memorysummary

        self.assertEqual(memorysummary(record()), {})
        with self.assertRaises(ValueError):
            memorysummary({**record(), "memory_definitions": None})

    def test_memory_summary_requires_the_same_record_source(self):
        from damage_lab.importer import memorysummary

        data = memoried()
        data["source_sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            memorysummary(data)

    def test_memory_summary_drops_unknown_fields_and_detaches_nested_values(self):
        from damage_lab.importer import memorysummary

        data = memoried()
        data["memory_definitions"]["ledger"]["candidates"][0]["opaque"] = "PRIVATE-MEMORY-CANARY"
        result = memorysummary(data)
        result["memory_definitions"]["ledger"]["candidates"][0]["own_values"].clear()
        self.assertEqual(("PRIVATE-MEMORY-CANARY" in json.dumps(result),
                          len(data["memory_definitions"]["ledger"]["candidates"][0]["own_values"])), (False, 1))

    def test_automatic_import_keeps_memory_definitions_without_manual_values(self):
        from test_damage_archive import attachedmemories, package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            directory = package(root)
            attachedmemories(directory)
            status = main(["--package", str(directory), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual((status, result["memory_definitions"]["ledger"]["accounting"]["candidates"],
                              result["memory_definitions"]["ledger"]["arithmetic_ready"], result["import_status"]),
                             (0, 1, False, "partial"))


class ImporterTests(unittest.TestCase):
    """User imports preserve partial data instead of inventing a damage total."""

    def test_level_candidates_survive_the_snapshot_without_changing_stats_or_benchmarks(self):
        from damage_lab.importer import snapshot

        data = leveled()
        result = snapshot(data)
        self.assertEqual((result["installed_level_candidates"], result["stats"], result["benchmark"]),
                         (data["installed_level_candidates"], {"spell_dps": 84317}, {"survival": 9217}))

    def test_level_summary_distinguishes_absence_from_a_null_document(self):
        from damage_lab.importer import levelsummary

        self.assertEqual(levelsummary(record()), {})
        with self.assertRaises(ValueError):
            levelsummary({**record(), "installed_level_candidates": None})

    def test_level_summary_requires_matching_record_and_installation_sources(self):
        from damage_lab.importer import levelsummary

        for field in ("source_sha256", "installed_skills"):
            data = leveled()
            if field == "source_sha256":
                data[field] = "f" * 64
            else:
                data[field]["source"]["sha256"] = "f" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                levelsummary(data)

    def test_level_summary_strips_unknown_properties_and_detaches_nested_candidates(self):
        from damage_lab.importer import levelsummary

        data = leveled()
        data["installed_level_candidates"]["targets"]["91437"]["candidates"][0]["private"] = "discard-me"
        result = levelsummary(data)["installed_level_candidates"]
        result["targets"]["91437"]["candidates"][0]["amount"]["exact"] = "9"
        self.assertEqual(("private" in result["targets"]["91437"]["candidates"][0],
            data["installed_level_candidates"]["targets"]["91437"]["candidates"][0]["amount"]["exact"]), (False, "2.70"))

    def test_automatic_import_keeps_level_candidates_without_manual_stats_or_effective_levels(self):
        from test_damage_archive import attachedlevels, package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            attachedlevels(path)
            status = main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual((status, result["installed_level_candidates"]["accounting"]["targets"],
                              result["installed_level_candidates"]["arithmetic_ready"],
                              result["installed_level_candidates"]["targets"]["90017"]["effective_level"]), (0, 4, False, None))

    def test_installed_profiles_keep_observed_levels_and_unknown_damage_gates_in_the_snapshot(self):
        from damage_lab.importer import snapshot

        result = snapshot(profiled())
        profiles = result["installed_skill_profiles"]
        self.assertEqual((profiles["members"][0]["gem_level"], profiles["members"][0]["profile"]["level"],
                          profiles["members"][0]["effective_level"], profiles["arithmetic_ready"],
                          profiles["activation"], profiles["patch"], result["stats"], result["benchmark"]),
                         (7, 7, None, False, "unknown", "unknown", {"spell_dps": 84317}, {"survival": 9217}))

    def test_profile_summary_requires_the_record_source_hash_to_match(self):
        from damage_lab.importer import profilesummary

        for source in (None, "b" * 64):
            with self.subTest(source=source):
                data = profiled()
                data["source_sha256"] = source
                with self.assertRaises(ValueError):
                    profilesummary(data)

    def test_profile_summary_distinguishes_absent_evidence_from_a_null_document(self):
        from damage_lab.importer import profilesummary

        self.assertEqual(profilesummary(record()), {})
        for invalid in (None, {}, []):
            with self.subTest(invalid=invalid):
                data = record()
                data["installed_skill_profiles"] = invalid
                with self.assertRaises(ValueError):
                    profilesummary(data)

    def test_profile_summary_revalidates_levels_counts_and_unverified_claims(self):
        from damage_lab.importer import profilesummary

        for path, value in ((("arithmetic_ready",), True), (("runtime_verified",), True),
                            (("identity_verified",), True), (("import_complete",), True),
                            (("activation",), "active"), (("patch",), "SS14"), (("effective_level",), 7),
                            (("accounting", "profiled"), 4), (("members", 0, "effective_level"), 7),
                            (("members", 0, "profile", "runtimeVerified"), True)):
            with self.subTest(path=path):
                data = profiled()
                node = data["installed_skill_profiles"]
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    profilesummary(data)

    def test_profile_summary_drops_private_extras_and_detaches_nested_evidence(self):
        from damage_lab.importer import profilesummary

        data = profiled()
        profiles = data["installed_skill_profiles"]
        member = profiles["members"][0]
        for node in (profiles, profiles["source"], profiles["catalog"], profiles["catalog"]["documents"][0],
                     member, member["profile"], member["profile"]["identity"], member["profile"]["tags"],
                     member["profile"]["hit"], member["profile"]["hit"]["binding"]):
            node["opaque"] = "PRIVATE-PROFILE-IMPORT-MARKER"
        result = profilesummary(data)
        result["installed_skill_profiles"]["catalog"]["documents"][0]["byte_range"][0] = 1
        result["installed_skill_profiles"]["members"][0]["profile"]["tags"]["skill"].clear()
        self.assertEqual((set(result), "PRIVATE-PROFILE-IMPORT-MARKER" in json.dumps(result),
                          profiles["catalog"]["documents"][0]["byte_range"],
                          member["profile"]["tags"]["skill"]),
                         ({"installed_skill_profiles"}, False, [19, 87],
                          ["activation_medium", "projectile", "spell"]))

    def test_automatic_import_keeps_catalog_profiles_without_manual_stats_or_damage_changes(self):
        from test_damage_archive import package
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            main(["--package", str(path), "--output", str(root / "before")])
            before = json.loads((root / "before/import.json").read_text(encoding="utf-8"))
            attached(path)
            status = main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            profiles = result["installed_skill_profiles"]
            self.assertEqual((status, profiles["source"]["sha256"] == result["source_sha256"],
                              profiles["members"][0]["gem_level"], profiles["members"][0]["effective_level"],
                              profiles["arithmetic_ready"], profiles["activation"], result["import_status"],
                              result["stats"] == before["stats"], result["benchmark"] == before["benchmark"]),
                             (0, True, 7, None, False, "unknown", "partial", True, True))

    def test_catalog_acquisition_error_does_not_invent_empty_imported_profiles(self):
        from test_damage_archive import package
        from test_skillcatalogbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            attached(path, error=True)
            status = main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual((status, "installed_skill_profiles" in result, result["import_status"]),
                             (0, False, "partial"))

    def test_legacy_import_keeps_installed_skill_profiles_unavailable(self):
        from test_damage_archive import package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            status = main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual((status, "installed_skill_profiles" in result, result["import_status"]),
                             (0, False, "partial"))

    def test_support_candidates_and_catalog_remain_non_arithmetic_in_the_snapshot(self):
        from damage_lab.importer import snapshot

        result = snapshot(supported())
        self.assertEqual((result["installed_support_effects"]["arithmetic_ready"],
                          result["installed_support_effects"]["activation"],
                          result["installed_support_catalog"]["network_bytes_verified"],
                          result["stats"], result["benchmark"]),
                         (False, "unknown", False, {"spell_dps": 84317}, {"survival": 9217}))

    def test_support_summary_requires_both_diagnostic_documents(self):
        from damage_lab.importer import supportsummary

        for field in ("installed_support_effects", "installed_support_catalog"):
            with self.subTest(field=field):
                data = supported()
                data.pop(field)
                with self.assertRaises(ValueError):
                    supportsummary(data)

    def test_support_summary_cannot_belong_to_another_record_source(self):
        from damage_lab.importer import supportsummary

        for source in (None, "b" * 64):
            with self.subTest(source=source):
                data = supported()
                data["source_sha256"] = source
                with self.assertRaises(ValueError):
                    supportsummary(data)

    def test_support_summary_drops_unknown_fields_without_aliasing_nested_evidence(self):
        from damage_lab.importer import supportsummary

        data = supported()
        for node in (data["installed_support_effects"], data["installed_support_effects"]["members"][1],
                     data["installed_support_effects"]["members"][1]["effects"],
                     data["installed_support_catalog"], data["installed_support_catalog"]["documents"][0]):
            node["opaque"] = "PRIVATE-SUPPORT-IMPORT-MARKER"
        result = supportsummary(data)
        result["installed_support_catalog"]["documents"][0]["byte_range"][0] = 1
        result["installed_support_effects"]["members"][1]["effects"]["constants"].clear()
        self.assertEqual(("PRIVATE-SUPPORT-IMPORT-MARKER" in json.dumps(result),
                          data["installed_support_catalog"]["documents"][0]["byte_range"],
                          len(data["installed_support_effects"]["members"][1]["effects"]["constants"])),
                         (False, [19, 87], 4))

    def test_support_summary_revalidates_claims_and_declared_catalog_coherence(self):
        from damage_lab.importer import supportsummary

        for path, value in ((("installed_support_effects", "runtime_verified"), True),
                            (("installed_support_catalog", "network_bytes_verified"), True),
                            (("installed_support_catalog", "records"), 999),
                            (("installed_support_catalog", "categories", "Noble_Support", "english"), "missing")):
            with self.subTest(path=path):
                data = supported()
                node = data
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    supportsummary(data)

    def test_support_summary_distinguishes_absence_from_null_documents(self):
        from damage_lab.importer import supportsummary

        self.assertEqual(supportsummary(record()), {})
        for inventory, catalog in ((None, None), (None, {}), ({}, None)):
            with self.subTest(inventory=inventory, catalog=catalog):
                data = record()
                data.update(installed_support_effects=inventory, installed_support_catalog=catalog)
                with self.assertRaises(ValueError):
                    supportsummary(data)

    def test_support_summary_requires_declared_catalog_sources_for_typed_effects(self):
        from damage_lab.importer import supportsummary

        data = supported()
        catalog = data["installed_support_catalog"]
        catalog["documents"] = [entry for entry in catalog["documents"] if entry["category"] != "Noble_Support"]
        catalog["categories"]["Noble_Support"] = {"master": "missing", "english": "missing"}
        with self.assertRaises(ValueError):
            supportsummary(data)

    def test_automatic_import_keeps_source_bound_support_candidates_without_manual_stats(self):
        from test_damage_archive import package
        from test_supportbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            attached(path)
            status = main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            inventory = result["installed_support_effects"]
            self.assertEqual((status, inventory["source"]["sha256"] == result["source_sha256"],
                              inventory["arithmetic_ready"], inventory["activation"],
                              result["installed_support_catalog"]["network_bytes_verified"], result["import_status"]),
                             (0, True, False, "unknown", False, "partial"))

    def test_support_producer_error_does_not_invent_an_empty_canonical_inventory(self):
        from test_damage_archive import package
        from test_supportbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            attached(path, error=True)
            status = main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual((status, "installed_support_effects" in result,
                              "installed_support_catalog" in result, result["import_status"]),
                             (0, False, False, "partial"))

    def test_legacy_package_keeps_support_effects_unavailable_in_the_automatic_import(self):
        from test_damage_archive import package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            status = main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual((status, "installed_support_effects" in result,
                              "installed_support_catalog" in result, result["import_status"]),
                             (0, False, False, "partial"))

    def test_import_json_keeps_installation_and_unknown_activation_without_manual_stats(self):
        from test_damage_archive import package
        from test_skillbundle import attached

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            path = package(root)
            attached(path)
            main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual((result["installed_skills"]["runtime"]["activation"],
                              result["installed_skills"]["relationships"][0]["effective_level"]), ("unknown", None))

    def test_installation_summary_revalidates_record_source_and_strips_unknown_fields(self):
        from damage_lab.importer import snapshot
        from damage_lab.installedskills import project
        from test_installedskills import document

        data = record()
        data["installed_skills"] = project(document(), "a" * 64)
        data["installed_skills"]["groups"][0]["members"][0]["raw"] = "PRIVATE-INSTALLATION-MARKER"
        self.assertNotIn("PRIVATE-INSTALLATION-MARKER", json.dumps(snapshot(data)))
        data["source_sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            snapshot(data)

    def test_import_keeps_new_critical_inventory_unresolved_and_non_arithmetic(self):
        from test_staticbundle import critical_bundle, package

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            path = package(root)
            critical_bundle(path)
            main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            self.assertEqual(result["static_combat"]["modifiers"][0]["semantics"], {
                "operation": "unresolved", "value_role": "non_additional_percent", "arithmetic_ready": False})

    def test_import_json_preserves_static_evidence_and_catalog_provenance(self):
        from test_staticbundle import fixture, package

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            path = package(root)
            fixture(path)
            main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
            self.assertEqual((result["static_combat"]["runtime"]["verified"],
                              result["static_combat_provenance"]["network_bytes_verified"]), (False, False))

    def test_static_summary_revalidates_record_source_and_drops_unknown_fields(self):
        from damage_lab.importer import snapshot
        from damage_lab.staticcombat import project
        from test_staticcombat import document

        data = record()
        data["static_combat"] = project(document(), "a" * 64)
        data["static_combat"]["modifiers"][0]["raw"] = "PRIVATE-STATIC-MARKER"
        result = snapshot(data)
        self.assertEqual((result["static_combat"]["accounting"]["compiled"],
                          "PRIVATE-STATIC-MARKER" in json.dumps(result)), (1, False))

    def test_static_summary_cannot_belong_to_a_different_record_source(self):
        from damage_lab.importer import snapshot
        from damage_lab.staticcombat import project
        from test_staticcombat import document

        data = record()
        data["static_combat"] = project(document(), "a" * 64)
        data["source_sha256"] = "e" * 64
        with self.assertRaises(ValueError):
            snapshot(data)

    def test_import_keeps_a_saved_code_match_distinct_from_identity_verification(self):
        from test_damage_archive import package, resolution_bundle

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            path = package(root)
            resolution_bundle(path)
            main(["--package", str(path), "--output", str(root / "result")])
            result = json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
            self.assertEqual((result["build_resolution"]["status"],
                              result["build_resolution"]["identity"]["payload_self_identifies"]),
                             ("matched_saved_code", False))

    def test_resolution_summary_removes_unknown_nested_properties(self):
        from damage_lab.buildresolution import project
        from damage_lab.importer import snapshot
        from test_buildresolution import document

        data = record()
        block = project(document(), "a" * 64)
        for row in (block, block["source"], block["identity"], block["transport"], block["gate"],
                    block["coverage"]["data_version"], block["coverage"]["affix_versions"], block["freshness"]):
            row["raw"] = "PRIVATE-RESOLUTION-MARKER"
        data["build_resolution"] = block
        self.assertNotIn("PRIVATE-RESOLUTION-MARKER", json.dumps(snapshot(data)["build_resolution"]))

    def test_import_preserves_the_automatic_acquisition_audit(self):
        from test_damage_archive import coverage_bundle, package

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            path = package(root)
            coverage_bundle(path)
            main(["--package", str(path), "--output", str(root / "result")])
            self.assertIs(json.loads((root / "result" / "import.json").read_text(encoding="utf-8"))
                          ["import_coverage"]["import_complete"], False)

    def test_acquisition_summary_drops_unknown_properties_at_each_depth(self):
        from damage_lab.importcoverage import project
        from damage_lab.importer import snapshot
        from test_importcoverage import document

        data = record()
        block = project(document(), "a" * 64, None)
        for row in (block, block["source"], block["guide"], block["domains"]["equipment"],
                    block["domains"]["equipment"]["counts"], block["gaps"][0]):
            row["raw"] = "PRIVATE-AUDIT-MARKER"
        data["import_coverage"] = block
        self.assertNotIn("PRIVATE-AUDIT-MARKER", json.dumps(snapshot(data)["import_coverage"]))

    def test_import_keeps_bundled_candidate_ranks_unresolved(self):
        from test_damage_archive import package, trait_bundle

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            path = package(root)
            trait_bundle(path)
            main(["--package", str(path), "--output", str(root / "result")])
            self.assertEqual([row["rank"] for row in json.loads(
                (root / "result" / "import.json").read_text(encoding="utf-8"))["trait_ranks"]["traits"]],
                             [None, None])

    def test_rank_summary_drops_extra_properties_at_each_depth(self):
        from damage_lab.importer import snapshot
        from damage_lab.traitranks import project
        from test_traitranks import document

        data = record()
        block = project(document(), "a" * 64)
        for row in (block, block["traits"][1], block["traits"][1]["candidates"][0],
                    block["memories"][0], block["memories"][0]["fields"]["client_fixed"],
                    block["memories"][0]["linkage"]):
            row["raw"] = "PRIVATE-RANK-MARKER"
        data["trait_ranks"] = block
        self.assertNotIn("PRIVATE-RANK-MARKER", json.dumps(snapshot(data)["trait_ranks"]))

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

    def test_game_log_spell_burst_count_reaches_json_sqlite_and_html_without_manual_inputs(self):
        from test_damage_archive import facts, game, native, package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            directory = package(root)
            path = game(root, "43721.25")
            with path.open("a", encoding="utf-8") as stream:
                prefix = "[2001.02.03-04.05.07:000][713]TLLua: Display: [Game] RoleAttrMgr@"
                stream.write(prefix + "Attri.Id  Max Spell Burst  21604\n" + prefix + "[1] = 0.00\n")
            status = main(["--package", str(directory), "--output", str(root / "result"),
                           "--facts", str(facts(root)), "--native-stats", str(native(root, directory)),
                           "--game-log", str(path)])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            page = (root / "result/index.html").read_text(encoding="utf-8")
            row = next((row for row in result["observations"] if row["key"] == "max_spell_burst"), {})
            with contextlib.closing(sqlite3.connect(root / "result/database.sqlite")) as connection:
                stored = connection.execute(
                    "SELECT value, unit FROM observations WHERE key='max_spell_burst'").fetchone()
            self.assertEqual((status, result["stats"].get("max_spell_burst"), stored,
                              row.get("source", {}).get("raw_value"), "Max Spell Burst" in page,
                              result["panel_log"]["identity_verified"], result["import_status"]),
                             (0, 0, (0, "count"), "0.00", True, False, "partial"))

    def test_game_log_double_damage_observation_reaches_json_sqlite_and_html_without_a_dps_correction(self):
        from test_damage_archive import facts, game, native, package

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            directory = package(root)
            path = game(root, "43721.25")
            with path.open("a", encoding="utf-8") as stream:
                prefix = "[2001.02.03-04.05.07:000][713]TLLua: Display: [Game] RoleAttrMgr@"
                stream.write(prefix + "Attri.Id  Double Damage Chance  21401\n" + prefix + "[1] = 37.1250\n")
            status = main(["--package", str(directory), "--output", str(root / "result"),
                           "--facts", str(facts(root)), "--native-stats", str(native(root, directory)),
                           "--game-log", str(path)])
            result = json.loads((root / "result/import.json").read_text(encoding="utf-8"))
            page = (root / "result/index.html").read_text(encoding="utf-8")
            row = next((row for row in result["observations"] if row["key"] == "double_damage_chance"), {})
            with contextlib.closing(sqlite3.connect(root / "result/database.sqlite")) as connection:
                stored = connection.execute(
                    "SELECT value, unit FROM observations WHERE key='double_damage_chance'").fetchone()
            self.assertEqual((status, result["stats"].get("double_damage_chance"), stored,
                              row.get("source", {}).get("raw_value"), "Double Damage Chance" in page,
                              result["stats"]["spell_dps"], result["panel_log"]["identity_verified"], result["import_status"]),
                             (0, 0.37125, (0.37125, "fraction"), "37.1250", True, 43721.25, False, "partial"))

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

    def test_panel_numeric_policy_survives_the_safe_summary(self):
        from damage_lab.importer import logsummary
        from damage_lab.logstats import select
        from test_logstats import document

        selection = select(document(), 3217)
        self.assertEqual(logsummary(selection["summary"])["numeric_policy"], {
            "printer_precision": "unknown", "stored_numbers": "binary64", "raw_tokens": "preserved",
            "native_anchor": {"operator": "absolute_difference_lte", "tolerance": "0.5", "unit": "damage/s",
                              "meaning": "selection_heuristic", "rounding_verified": False}})

    def test_panel_numeric_policy_cannot_publish_extra_private_fields(self):
        from damage_lab.importer import logsummary
        from damage_lab.logstats import select
        from test_logstats import document

        selection = select(document(), 3217)["summary"]
        selection["numeric_policy"] = {"private": "PRIVATE-MARKER"}
        with self.assertRaisesRegex(ValueError, "numeric policy"):
            logsummary(selection)

    def test_panel_numeric_policy_rejects_nested_private_values(self):
        from damage_lab.importer import logsummary
        from damage_lab.logstats import select
        from test_logstats import document

        policy = {"printer_precision": "unknown", "stored_numbers": "binary64", "raw_tokens": "preserved",
                  "native_anchor": {"operator": "absolute_difference_lte", "tolerance": "0.5", "unit": "damage/s",
                                    "meaning": "selection_heuristic", "rounding_verified": False}}
        for path in (("native_anchor", "private"), ("native_anchor", "meaning")):
            selection = select(document(), 3217)["summary"]
            selection["numeric_policy"] = json.loads(json.dumps(policy))
            selection["numeric_policy"][path[0]][path[1]] = "PRIVATE-MARKER"
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "numeric policy"):
                logsummary(selection)

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
