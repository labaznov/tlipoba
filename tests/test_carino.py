"""Synthetic fixed-state examples for Carino Heat modifiers."""

import unittest


class CarinoTests(unittest.TestCase):
    """Verify explicit Heat state without inventing a combat rotation."""

    def test_rank_two_heat_emits_one_additive_damage_modifier(self):
        from damage_lab.carino import heat

        self.assertEqual(heat(7, 2, 1.0, False), {
            "damage": [{"id": "carino-heat-damage", "affix": "carino-incinerated-glory",
                        "value": 0.02, "stacks": 7, "mode": "add"}],
            "cast": [],
        })

    def test_eternal_flames_emits_additive_cast_speed_when_selected(self):
        from damage_lab.carino import heat

        self.assertEqual(heat(11, 5, 1.0, True)["cast"], [
            {"id": "carino-heat-cast", "affix": "carino-eternal-flames",
             "value": 0.004, "stacks": 11, "mode": "add"},
        ])

    def test_heat_cannot_be_a_negative_fractional_or_boolean_count(self):
        from damage_lab.carino import heat

        for count in (-7, 3.5, 2.0, True, False, None, "11", float("inf"), float("nan")):
            with self.subTest(count=count), self.assertRaises(ValueError):
                heat(count, 2, 1.0, False)

    def test_rank_must_be_an_explicit_integer_from_one_through_five(self):
        from damage_lab.carino import heat

        for rank in (0, 6, -1, True, False, 2.0, 2.5, None, "2", float("inf"), float("nan")):
            with self.subTest(rank=rank), self.assertRaises(ValueError):
                heat(7, rank, 1.0, False)

    def test_effect_must_be_a_finite_nonnegative_number(self):
        from damage_lab.carino import heat

        for effect in (-0.3, True, False, None, "1.5", float("inf"), float("nan")):
            with self.subTest(effect=effect), self.assertRaises(ValueError):
                heat(7, 2, effect, False)

    def test_eternal_flames_requires_an_explicit_boolean(self):
        from damage_lab.carino import heat

        for eternal in (0, 1, None, "false"):
            with self.subTest(eternal=eternal), self.assertRaises(ValueError):
                heat(7, 2, 1.0, eternal)

    def test_explicit_effect_scales_rank_five_damage_and_eternal_cast_speed(self):
        from damage_lab.carino import heat
        from damage_lab.formulas import additional

        state = heat(13, 5, 1.5, True)
        self.assertEqual(tuple(round(additional(state[layer]), 12) for layer in ("damage", "cast")), (1.585, 1.078))

    def test_each_supported_rank_uses_its_published_damage_per_stack(self):
        from damage_lab.carino import heat

        self.assertEqual([heat(1, rank, 1.0, False)["damage"][0]["value"] for rank in (1, 2, 3, 4, 5)],
                         [0.016, 0.02, 0.023, 0.026, 0.03])

    def test_zero_heat_is_neutral_with_eternal_flames(self):
        from damage_lab.carino import heat
        from damage_lab.formulas import additional

        state = heat(0, 2, 1.5, True)
        self.assertEqual(tuple(additional(state[layer]) for layer in ("damage", "cast")), (1.0, 1.0))

    def test_zero_effect_disables_bonuses_without_changing_the_supplied_heat(self):
        from damage_lab.carino import heat

        state = heat(37, 5, 0.0, True)
        self.assertEqual([(state[layer][0]["value"], state[layer][0]["stacks"]) for layer in ("damage", "cast")],
                         [(0.0, 37), (0.0, 37)])

    def test_missing_rank_cannot_select_a_default(self):
        from damage_lab.carino import heat

        with self.assertRaises(TypeError):
            heat(7, effect=1.0, eternal=False)

    def test_fixed_state_cannot_overflow_its_additive_heat_contribution(self):
        from damage_lab.carino import heat

        for count, effect in ((100000, 1e308), (10**400, 1.0)):
            with self.subTest(count=count, effect=effect), self.assertRaises(ValueError):
                heat(count, 5, effect, True)

    def test_heat_does_not_infer_a_ceiling_from_magazine_capacity(self):
        from damage_lab.carino import heat

        self.assertEqual(heat(937, 1, 1.0, False)["damage"][0]["stacks"], 937)

    def test_missing_effect_cannot_select_burning_red_or_another_default(self):
        from damage_lab.carino import heat

        with self.assertRaises(TypeError):
            heat(7, 2, eternal=False)

    def test_modifying_one_compilation_does_not_change_the_next_state(self):
        from damage_lab.carino import heat

        state = heat(7, 2, 1.0, True)
        state["damage"][0]["value"] = 93
        self.assertEqual(heat(7, 2, 1.0, True)["damage"][0]["value"], 0.02)
