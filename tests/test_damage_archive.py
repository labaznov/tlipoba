import contextlib
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from damage_lab.archive import archive
from examples.make_fixture import fixture


class StaticBundleTests(unittest.TestCase):
    """Retain typed gear evidence without changing already observed character values."""

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
                             (str(path.resolve()), "log full precision; corroborated; identity_verified=false",
                              {"attr_id": "10103", "index": 1, "raw_value": "43721.25",
                               "raw_values": ["43721.25"],
                               "timestamp": "2001-02-03T04:05:07.000Z", "frame": 713,
                               "line_numbers": [17, 18]}))

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


if __name__ == "__main__":
    unittest.main()
