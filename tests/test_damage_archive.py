import contextlib
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from damage_lab.archive import archive
from examples.make_fixture import fixture

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
