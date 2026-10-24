import unittest
from fractions import Fraction

from damage_lab.engine import calculate, cold, critical, topology


class DamageEngineTests(unittest.TestCase):
    """Check damage expectations against independently calculated examples."""

    def test_converted_hit_preserves_a_positive_pool_after_baseline_cancellation(self):
        self.assertEqual(cold(37, 0, 0, 1, 1e-17, -1, 0, []),
                         float(37 * Fraction.from_float(1e-17)))

    def test_native_cold_hit_preserves_a_positive_pool_after_baseline_cancellation(self):
        self.assertEqual(cold(0, 0, 43, 1, 1e-17, 0, -1, []),
                         float(43 * Fraction.from_float(1e-17)))

    def test_converted_hit_preserves_an_exact_fractional_pool(self):
        self.assertEqual(cold(37, 0, 0, 1, -1 + Fraction(1, 2 ** 1000), 0, 0, []),
                         float(Fraction(37, 2 ** 1000)))

    def test_observed_spell_burst_counts_do_not_change_conditional_arithmetic(self):
        panel = {"spell_dps": 379, "hit_min": 119, "hit_max": 237, "cast_rate": 1.3,
                 "crit_chance": .2, "crit_multiplier": 3, "max_tangles": 2,
                 "extra_attachments": 1, "cold_penetration": .11}
        for basis in ("panel", "hit"):
            condition = {"basis": basis, "active": 2, "hits": 4, "retention": .3, "resistance": .17,
                         "taken": .07, "uptime": .81, "lucky": False, "critical_more": 0}
            for count in (0, 3):
                with self.subTest(basis=basis, count=count):
                    self.assertEqual(calculate({**panel, "max_spell_burst": count}, condition),
                                     calculate(panel, condition))

    def test_positive_converted_hit_cannot_underflow_to_zero(self):
        with self.assertRaisesRegex(ValueError, "underflow"):
            cold(5e-324, 0, 0, 1, -.5, 0, 0, [])

    def test_positive_added_cold_hit_cannot_underflow_to_zero(self):
        with self.assertRaisesRegex(ValueError, "underflow"):
            cold(0, 0, 5e-324, .5, 0, 0, 0, [])

    def test_positive_critical_only_damage_cannot_underflow_to_zero(self):
        with self.assertRaisesRegex(ValueError, "underflow"):
            critical(1, 5e-324, lucky=False, more=-.5)

    def test_cold_requires_explicit_affix_metadata(self):
        for field in ("affix", "stacks", "mode"):
            with self.subTest(field=field):
                row = {"id": "a", "affix": "shared", "scope": "all", "value": 0.2,
                       "stacks": 1, "mode": "add"}
                del row[field]
                with self.assertRaisesRegex(ValueError, "requires"):
                    cold(103, 0, 0, 1, 0, 0, 0, [row])

    def test_cold_cannot_return_an_overflowed_hit(self):
        with self.assertRaisesRegex(ValueError, "Cold hit must be finite"):
            cold(1e15, 0, 0, 1, 0, 0, 0, [
                {"id": str(index), "affix": str(index), "scope": "all", "value": 1e6,
                 "stacks": 1, "mode": "add"} for index in range(50)
            ])

    def test_repeated_additional_affix_is_one_pool(self):
        self.assertAlmostEqual(cold(103, 0, 0, 1, 0, 0, 0, [
            {"id": "a", "affix": "shared", "scope": "all", "value": 0.2, "stacks": 1, "mode": "add"},
            {"id": "b", "affix": "shared", "scope": "all", "value": 0.3, "stacks": 1, "mode": "add"},
        ]), 154.5)

    def test_matching_affix_pools_are_shared_across_conversion_scopes(self):
        self.assertAlmostEqual(cold(103, 0, 0, 1, 0, 0, 0, [
            {"id": "a", "affix": "shared", "scope": "physical", "value": 0.2, "stacks": 1, "mode": "add"},
            {"id": "b", "affix": "shared", "scope": "cold", "value": 0.3, "stacks": 1, "mode": "add"},
        ]), 154.5)

    def test_native_cold_does_not_share_the_physical_only_pool(self):
        self.assertAlmostEqual(cold(103, 0, 19, 1, 0, 0, 0, [
            {"id": "a", "affix": "shared", "scope": "physical", "value": 0.2, "stacks": 1, "mode": "add"},
            {"id": "b", "affix": "shared", "scope": "cold", "value": 0.3, "stacks": 1, "mode": "add"},
        ]), 179.2)

    def test_one_affix_cannot_mix_stack_modes_across_conversion_scopes(self):
        with self.assertRaises(ValueError):
            cold(103, 0, 0, 1, 0, 0, 0, [
                {"id": "a", "affix": "shared", "scope": "physical", "value": 0.2, "mode": "add", "stacks": 1},
                {"id": "b", "affix": "shared", "scope": "cold", "value": 0.3, "mode": "multiply", "stacks": 1},
            ])

    def test_lucky_critical_strike_uses_two_rolls(self):
        self.assertAlmostEqual(critical(0.37, 4.2, lucky=True), 2.92992)

    def test_lucky_preserves_a_tiny_positive_chance_in_the_damage_expectation(self):
        self.assertEqual(critical(1e-17, 100, lucky=True, more=100), 1.000000000000202)

    def test_extra_attachments_do_not_create_extra_tangles(self):
        self.assertEqual(topology(3, 2, 3, 7, 0.2), {"attached": 3, "shotgun": 2.2, "factor": 6.6})

    def test_converted_physical_keeps_origin_modifiers_without_buffing_native_cold(self):
        self.assertAlmostEqual(cold(127, 19, 23, 1.37, 0.83, 0.41, 0.29, [
            {"id": "x", "affix": "x", "scope": "all", "value": 0.17, "stacks": 1, "mode": "add"},
            {"id": "y", "affix": "y", "scope": "physical", "value": 0.31, "stacks": 1, "mode": "add"},
            {"id": "z", "affix": "z", "scope": "cold", "value": 0.23, "stacks": 1, "mode": "add"},
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
                {"id": "same", "affix": "a", "scope": "all", "value": 0.31, "stacks": 1, "mode": "add"},
                {"id": "same", "affix": "b", "scope": "cold", "value": 0.71, "stacks": 1, "mode": "add"},
            ])

    def test_active_tangles_cannot_exceed_the_character_maximum(self):
        with self.assertRaises(ValueError):
            topology(2, 1, 3, 1, 0.8)

    def test_retention_cannot_be_nan(self):
        with self.assertRaises(ValueError):
            topology(3, 2, 2, 7, float("nan"))
