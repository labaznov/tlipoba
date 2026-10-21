import unittest

from damage_lab.report import render


class DamageReportTests(unittest.TestCase):
    """Check report evidence and safe rendering without native snapshot leakage."""

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
