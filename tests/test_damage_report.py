import unittest

from damage_lab.report import render, render_import, scenarios


class DamageReportTests(unittest.TestCase):
    """Check report evidence and safe rendering without native snapshot leakage."""

    def test_import_report_preserves_level_parameters_without_applying_them_again(self):
        result = render_import({"skill_values": [{
            "name": "Fictional <skill>", "level": 17, "status": "resolved",
            "values": {"damage": 139.5},
        }]})
        self.assertTrue(all(value in result for value in (
            "Параметры навыков по уровню", "Fictional &lt;skill&gt;", "17", "resolved", "139.5",
            "не применены повторно к агрегатам панели",
        )))

    def test_import_report_explains_panel_log_provenance_without_an_identity_claim(self):
        result = render_import({"panel_log": {
            "format": "tli-panel-log-v1", "status": "corroborated", "known": 9, "unknown_attributes": 17,
            "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271, "raw": "PRIVATE-MARKER"},
            "identity_verified": False, "source_sha256": "b" * 64, "raw": "PRIVATE-MARKER",
        }})
        self.assertTrue(all(value in result for value in (
            "Лог панели", "2001.02.03-04.05.06", "271", "b" * 64, "identity_verified: false",
            "Совпадение Spell DPS не подтверждает принадлежность лога персонажу",
        )) and "PRIVATE-MARKER" not in result)

    def test_import_report_preserves_safe_panel_row_source_coordinates(self):
        result = render_import({"stats": {"spell_dps": 71423}, "observations": [{
            "key": "spell_dps", "unit": "damage/s", "source": {
                "attr_id": "10103", "index": 1, "raw_value": "71423.25",
                "raw_values": ["71423.25", "71423.2500"],
                "timestamp": "2001.02.03-04.05.06", "frame": 271, "line_numbers": [17, 23],
                "raw": "PRIVATE-MARKER",
            },
        }]})
        self.assertTrue(all(value in result for value in (
            "10103", "71423.2500", "2001.02.03-04.05.06", "271", "[17, 23]",
        )) and "PRIVATE-MARKER" not in result)

    def test_automatic_report_reproduction_uses_the_panel_log_without_manual_observations(self):
        result = render(
            {"stats": {}, "panel_log": {
                "format": "tli-panel-log-v1", "status": "corroborated", "known": 9, "unknown_attributes": 17,
                "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                "identity_verified": False, "source_sha256": "b" * 64,
            }},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 2, "hits": 3, "retention": 0.2, "resistance": 0.23,
             "taken": 0.11, "uptime": 0.87, "observations_provided": False},
        )
        self.assertTrue("--panel-log ПАНЕЛЬ_СТАТОВ.json" in result and "--observations" not in result
                        and "identity_verified: false" in result)

    def test_import_report_accepts_sparse_stats_without_a_damage_calculation(self):
        self.assertIn("Боевой DPS пока недоступен", render_import({
            "name": "Sparse fixture", "stats": {"spell_dps": 84317}, "benchmark": {},
            "inventory": {"gear": [{"name": "Fictional wand", "details": ["Fictional effect"]}]},
            "coverage": ["Unknown effect"], "missing_stats": ["cast_rate"], "import_status": "partial",
        }))

    def test_import_report_preserves_each_available_inventory_section(self):
        self.assertTrue(all(f"Fictional {section}" in render_import({
            "inventory": {name: [{"name": f"Fictional {name}", "details": [f"Effect {name}"]}]
                          for name in ("gear", "skills", "talents", "memories", "slates", "traits", "systems")},
            "stats": {}, "benchmark": {}, "missing_stats": ["cast_rate"], "coverage": ["Unknown layout"],
        }) for section in ("gear", "skills", "talents", "memories", "slates", "traits", "systems")))

    def test_import_report_does_not_render_private_native_payloads(self):
        self.assertNotIn("PRIVATE-MARKER", render_import({
            "accountId": "PRIVATE-MARKER", "sourceSections": {"payload": "PRIVATE-MARKER"},
            "native_stats": {"known": 2, "raw": "PRIVATE-MARKER"}, "stats": {}, "benchmark": {},
        }))

    def test_import_report_escapes_inventory_markup(self):
        self.assertIn("&lt;script&gt;fixture&lt;/script&gt;", render_import({
            "inventory": {"gear": [{"name": "<script>fixture</script>", "details": []}]},
            "stats": {}, "benchmark": {},
        }))

    def test_import_report_keeps_automatic_field_provenance(self):
        self.assertTrue(all(value in render_import({
            "stats": {"spell_dps": 84317}, "benchmark": {"survival": 9217},
            "native_stats": {"known": 2, "unknown_stat_ids": 17},
            "observations": [{"key": "spell_dps", "label": "Spell DPS", "unit": "damage/s",
                              "precision": "wire 1.10; exact integer", "evidence": "synthetic-native.json"}],
        }) for value in ("84 317", "9 217", "wire 1.10", "synthetic-native.json", "неизвестных stat ID: 17")))

    def test_import_report_keeps_fractional_values_and_displays_their_true_units(self):
        result = render_import({
            "stats": {"crit_chance": 0.4137, "cast_rate": 4.73, "crit_multiplier": 2.87},
            "observations": [{"key": key, "unit": unit, "precision": "exact synthetic value"}
                             for key, unit in (("crit_chance", "fraction"), ("cast_rate", "casts/s"),
                                               ("crit_multiplier", "multiplier"))],
        })
        self.assertTrue(all(row in result for row in (
            "<td>crit_chance</td><td>41.37%</td><td>%</td>",
            "<td>cast_rate</td><td>4.73</td><td>casts/s</td>",
            "<td>crit_multiplier</td><td>2.87</td><td>multiplier</td>",
        )))

    def test_import_report_preserves_round_trip_digits_and_large_native_integers(self):
        result = render_import({
            "stats": {"cast_rate": 1.2345678901234567, "crit_chance": 0.12345678901234566,
                      "spell_dps": 9223372036854775807},
            "observations": [{"key": key, "unit": unit, "precision": "exact synthetic value"}
                             for key, unit in (("cast_rate", "casts/s"), ("crit_chance", "fraction"),
                                               ("spell_dps", "damage/s"))],
        })
        self.assertTrue(all(row in result for row in (
            "<td>cast_rate</td><td>1.2345678901234567</td>",
            "<td>crit_chance</td><td>12.345678901234566%</td>",
            "<td>spell_dps</td><td>9 223 372 036 854 775 807</td>",
        )))

    def test_import_report_does_not_offer_manual_stats_or_a_scenario_total(self):
        result = render_import({"stats": {}, "benchmark": {}, "missing_stats": ["cast_rate"]})
        self.assertTrue("cast_rate" in result and "ручной ввод характеристик не требуется" in result
                        and "Условный расчёт" not in result and "--observations" not in result)

    def test_scenario_grid_applies_the_same_combat_context(self):
        self.assertIn("<td>587</td>", scenarios(
            {"stats": {"spell_dps": 379, "cast_rate": 6.3, "max_tangles": 3,
                       "extra_attachments": 2, "cold_penetration": 0.13}},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1,
             "combat": {"reference": {"damage": [], "cast": [], "taken": []},
                        "target": {"damage": [{"id": "test", "affix": "test", "value": 0.37,
                                              "stacks": 1, "mode": "add"}], "cast": [], "taken": []},
                        "tick_frequency": None, "armor": 0, "nonphysical": True,
                        "missing": [], "notes": []}},
        ))

    def test_report_renders_decoded_slates_even_when_layout_is_unknown(self):
        self.assertIn("Fictional slate effect", render(
            {"name": "Fixture", "stats": {},
             "inventory": {"slates": [{"name": "Fixture slate", "details": ["Fictional slate effect"]}]}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_synthetic_report_does_not_claim_game_measurement(self):
        self.assertTrue(all(value in render(
            {"synthetic": True, "name": "Fictional", "character": "Carino", "stats": {},
             "benchmark": {"average_dps": 179}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ) for value in ("Синтетический пример", "Вымышленный бенчмарк", "Значения заданы для проверки арифметики")))

    def test_synthetic_report_avoids_observed_game_labels(self):
        self.assertNotIn("Измерено в игре", render(
            {"synthetic": True, "name": "Fictional", "character": "Carino", "stats": {}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_escapes_inventory_markup(self):
        self.assertIn("&lt;script&gt;alert(7)&lt;/script&gt;", render(
            {"name": "Fixture", "character": "Carino", "stats": {},
             "inventory": {"gear": [{"name": "<script>alert(7)</script>", "details": []}]}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_distinguishes_observed_and_conditional_values(self):
        self.assertTrue(all(text in render(
            {"name": "Fixture", "character": "Carino", "stats": {"spell_dps": 31729},
             "benchmark": {"average_dps": 185319}},
            {"dps": 909, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ) for text in ("Измерено в игре", "185 319", "Панельный Spell DPS", "31 729", "Условный расчёт", "909")))

    def test_report_does_not_render_native_sections_or_account_ids(self):
        self.assertNotIn("NATIVE-SECRET", render(
            {"name": "Fixture", "character": "Carino", "stats": {},
             "sourceSections": {"payload": "NATIVE-SECRET"}, "accountId": "NATIVE-SECRET"},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_drops_unsafe_source_urls(self):
        self.assertNotIn('href="javascript:', render(
            {"name": "Fixture", "character": "Carino", "stats": {},
             "facts": {"sources": {"bad": "javascript:alert(7)"}}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_marks_shotgun_rows_as_scenarios(self):
        self.assertTrue(all(text in render(
            {"name": "Fixture", "character": "Carino", "stats": {
                "spell_dps": 379, "max_tangles": 3, "extra_attachments": 2,
                "cold_penetration": 0.13}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ) for text in ("Сценарии, а не подтверждённые границы", "20%", "80%", "13")))
