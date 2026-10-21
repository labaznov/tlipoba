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
