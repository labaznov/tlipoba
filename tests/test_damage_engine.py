import unittest

from damage_lab.engine import calculate, cold, critical, topology


class DamageEngineTests(unittest.TestCase):
    """Check damage expectations against independently calculated examples."""

    def test_lucky_critical_strike_uses_two_rolls(self):
        self.assertAlmostEqual(critical(0.37, 4.2, lucky=True), 2.92992)

    def test_extra_attachments_do_not_create_extra_tangles(self):
        self.assertEqual(topology(3, 2, 3, 7, 0.2), {"attached": 3, "shotgun": 2.2, "factor": 6.6})

    def test_converted_physical_keeps_origin_modifiers_without_buffing_native_cold(self):
        self.assertAlmostEqual(cold(127, 19, 23, 1.37, 0.83, 0.41, 0.29, [
            {"id": "x", "scope": "all", "value": 0.17},
            {"id": "y", "scope": "physical", "value": 0.31},
            {"id": "z", "scope": "cold", "value": 0.23},
        ]), 826.0268920839)

    def test_panel_dps_does_not_receive_critical_bonuses_twice(self):
        self.assertAlmostEqual(calculate(
            {"spell_dps": 379, "crit_chance": 0.73, "crit_multiplier": 8.1,
             "max_tangles": 3, "extra_attachments": 2, "cold_penetration": 0.13},
            {"basis": "panel", "active": 3, "hits": 7, "retention": 0.2,
             "resistance": 0.47, "taken": 0.19, "uptime": 0.83},
        )["dps"], 1630.6176348)

    def test_lucky_cannot_be_a_string(self):
        with self.assertRaises(ValueError):
            critical(0.51, 6.2, lucky="false")

    def test_tangles_cannot_exceed_the_documented_limit(self):
        with self.assertRaises(ValueError):
            topology(5, 4, 5, 1, 0.8)

    def test_raw_hit_uses_the_total_critical_multiplier(self):
        self.assertAlmostEqual(calculate(
            {"hit_min": 119, "hit_max": 237, "cast_rate": 1.3, "crit_chance": 0.2,
             "crit_multiplier": 3, "max_tangles": 2, "extra_attachments": 1, "cold_penetration": 0.11},
            {"basis": "hit", "active": 2, "hits": 4, "retention": 0.3, "resistance": 0.17,
             "taken": 0.07, "uptime": 0.81, "lucky": False, "critical_more": 0},
        )["dps"], 1002.932343504)

    def test_a_modifier_cannot_be_applied_twice(self):
        with self.assertRaises(ValueError):
            cold(19, 3, 7, 1.2, 0.3, 0.2, 0.4, [
                {"id": "same", "scope": "all", "value": 0.31},
                {"id": "same", "scope": "cold", "value": 0.71},
            ])

    def test_active_tangles_cannot_exceed_the_character_maximum(self):
        with self.assertRaises(ValueError):
            topology(2, 1, 3, 1, 0.8)

    def test_retention_cannot_be_nan(self):
        with self.assertRaises(ValueError):
            topology(3, 2, 2, 7, float("nan"))
