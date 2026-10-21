"""Synthetic examples for explicitly selected combat arithmetic."""

import unittest


class FormulasTests(unittest.TestCase):
    """Verify public formula contracts with independent numeric examples."""

    def test_additional_sums_repeated_affixes_before_multiplying_distinct_affixes(self):
        from damage_lab.formulas import additional

        self.assertAlmostEqual(additional([
            {"id": "wand", "affix": "spell", "value": 0.13, "stacks": 2, "mode": "add"},
            {"id": "ring", "affix": "spell", "value": 0.07, "stacks": 1, "mode": "add"},
            {"id": "talent", "affix": "cold", "value": 0.19, "stacks": 1, "mode": "add"},
        ]), 1.5827)

    def test_additional_compounds_stacks_when_the_affix_explicitly_multiplies(self):
        from damage_lab.formulas import additional

        self.assertAlmostEqual(additional([
            {"id": "first", "affix": "sequence", "value": 0.2, "stacks": 2, "mode": "multiply"},
            {"id": "second", "affix": "sequence", "value": 0.2, "stacks": 1, "mode": "multiply"},
        ]), 1.728)

    def test_additional_cannot_count_the_same_instance_twice(self):
        from damage_lab.formulas import additional

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            additional([
                {"id": "same", "affix": "spell", "value": 0.17, "stacks": 1, "mode": "add"},
                {"id": "same", "affix": "cold", "value": 0.31, "stacks": 1, "mode": "add"},
            ])

    def test_additional_cannot_mix_stack_modes_for_one_affix(self):
        from damage_lab.formulas import additional

        with self.assertRaisesRegex(ValueError, "mode"):
            additional([
                {"id": "first", "affix": "spell", "value": 0.23, "stacks": 1, "mode": "add"},
                {"id": "second", "affix": "spell", "value": 0.41, "stacks": 2, "mode": "multiply"},
            ])

    def test_additional_cannot_accept_nonfinite_or_boolean_values(self):
        from damage_lab.formulas import additional

        for value in (True, False, float("nan"), float("inf"), -float("inf"), "0.13"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                additional([{"id": "one", "affix": "spell", "value": value, "stacks": 1, "mode": "add"}])

    def test_additional_cannot_accept_invalid_stack_counts(self):
        from damage_lab.formulas import additional

        for count in (-3, True, False, 1.5, 2.0, float("inf"), float("nan"), "2"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                additional([{"id": "one", "affix": "spell", "value": 0.13, "stacks": count, "mode": "add"}])

    def test_additional_cannot_accept_an_unknown_stack_mode(self):
        from damage_lab.formulas import additional

        with self.assertRaisesRegex(ValueError, "mode"):
            additional([{"id": "one", "affix": "spell", "value": 0.29, "stacks": 1, "mode": "automatic"}])

    def test_additional_cannot_turn_negative_factors_into_damage(self):
        from damage_lab.formulas import additional

        for mode in ("add", "multiply"):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "factor"):
                additional([{"id": "one", "affix": "spell", "value": -1.7, "stacks": 2, "mode": mode}])

    def test_additional_cannot_infer_missing_row_fields(self):
        from damage_lab.formulas import additional

        for field in ("id", "affix", "value", "stacks", "mode"):
            row = {"id": "one", "affix": "spell", "value": 0.29, "stacks": 1, "mode": "add"}
            del row[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                additional([row])

    def test_additional_cannot_accept_empty_or_nontext_identities(self):
        from damage_lab.formulas import additional

        for field in ("id", "affix"):
            for value in ("", "  ", True, 17, None, []):
                row = {"id": "one", "affix": "spell", "value": 0.29, "stacks": 1, "mode": "add"}
                row[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    additional([row])

    def test_additional_returns_one_for_no_modifiers(self):
        from damage_lab.formulas import additional

        self.assertEqual(additional([]), 1.0)

    def test_additional_preserves_a_zero_factor(self):
        from damage_lab.formulas import additional

        self.assertEqual(additional([{"id": "one", "affix": "spell", "value": -1, "stacks": 1, "mode": "add"}]), 0)

    def test_additional_ignores_zero_stacks(self):
        from damage_lab.formulas import additional

        self.assertEqual(additional([{"id": "one", "affix": "spell", "value": 0.43, "stacks": 0, "mode": "multiply"}]), 1)

    def test_additional_validates_the_sum_of_an_additive_pool(self):
        from damage_lab.formulas import additional

        self.assertAlmostEqual(additional([
            {"id": "drawback", "affix": "spell", "value": -1.4, "stacks": 1, "mode": "add"},
            {"id": "benefit", "affix": "spell", "value": 0.6, "stacks": 1, "mode": "add"},
        ]), 0.2)

    def test_additional_cannot_return_nonfinite_products(self):
        from damage_lab.formulas import additional

        with self.assertRaises(ValueError):
            additional([
                {"id": "first", "affix": "spell", "value": 1e200, "stacks": 1, "mode": "add"},
                {"id": "second", "affix": "cold", "value": 1e200, "stacks": 1, "mode": "add"},
            ])

    def test_tangle_rate_caps_continuous_casts_per_caster(self):
        from damage_lab.formulas import tangle_rate

        self.assertEqual(tangle_rate(47, frequency=None), 30)

    def test_tangle_rate_rounds_up_tick_intervals_only_when_selected(self):
        from damage_lab.formulas import tangle_rate

        self.assertEqual(tangle_rate(8.9, frequency=30), 7.5)

    def test_tangle_rate_is_zero_without_casting(self):
        from damage_lab.formulas import tangle_rate

        self.assertEqual(tangle_rate(0, frequency=30), 0)

    def test_tangle_rate_cannot_accept_invalid_cast_rates(self):
        from damage_lab.formulas import tangle_rate

        for rate in (-1.9, True, False, float("inf"), float("nan"), "7"):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                tangle_rate(rate, frequency=None)

    def test_tangle_rate_cannot_select_an_unsupported_tick_frequency(self):
        from damage_lab.formulas import tangle_rate

        for frequency in (True, False, 0, 60, float("nan"), float("inf"), "30"):
            with self.subTest(frequency=frequency), self.assertRaises(ValueError):
                tangle_rate(0, frequency=frequency)

    def test_armor_reduces_monster_physical_hit_damage(self):
        from damage_lab.formulas import armor

        self.assertAlmostEqual(armor(25000, nonphysical=False), 0.47619047619047616)

    def test_armor_applies_sixty_percent_of_mitigation_to_nonphysical_hits(self):
        from damage_lab.formulas import armor

        self.assertAlmostEqual(armor(25000, nonphysical=True), 0.2857142857142857)

    def test_armor_caps_physical_mitigation_at_eighty_percent(self):
        from damage_lab.formulas import armor

        self.assertEqual(armor(190000, nonphysical=False), 0.8)

    def test_armor_cannot_accept_negative_nonfinite_or_boolean_armor(self):
        from damage_lab.formulas import armor

        for value in (-173, True, False, float("inf"), float("nan"), "25000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                armor(value, nonphysical=False)

    def test_armor_cannot_guess_a_nonphysical_flag(self):
        from damage_lab.formulas import armor

        for flag in (0, 1, None, "False"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                armor(17000, nonphysical=flag)

    def test_armor_returns_zero_when_the_target_has_no_armor(self):
        from damage_lab.formulas import armor

        self.assertEqual(armor(0, nonphysical=True), 0)

    def test_armor_caps_before_applying_the_nonphysical_coefficient(self):
        from damage_lab.formulas import armor

        self.assertEqual(armor(190000, nonphysical=True), 0.48)

    def test_tangle_rate_preserves_the_continuous_rate_without_tick_rounding(self):
        from damage_lab.formulas import tangle_rate

        self.assertEqual(tangle_rate(8.9), 8.9)

    def test_tangle_rate_preserves_an_exact_tick_boundary(self):
        from damage_lab.formulas import tangle_rate

        self.assertEqual(tangle_rate(7.5, frequency=30), 7.5)

    def test_tangle_rate_caps_tick_casts_per_caster(self):
        from damage_lab.formulas import tangle_rate

        self.assertEqual(tangle_rate(41, frequency=30), 30)

    def test_additional_cannot_overflow_a_compounded_factor(self):
        from damage_lab.formulas import additional

        with self.assertRaises(ValueError):
            additional([{"id": "one", "affix": "spell", "value": 1e200, "stacks": 3, "mode": "multiply"}])

    def test_tangle_rate_cannot_overflow_a_finite_slow_interval(self):
        from damage_lab.formulas import tangle_rate

        self.assertEqual(tangle_rate(1e-308, frequency=30), 1e-308)
