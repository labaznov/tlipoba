"""Combat scenarios apply explicit changes to an observed anchor."""

import copy
import unittest

from damage_lab.combat import apply


def context():
    return {
        "reference": {"damage": [], "cast": [], "taken": []},
        "target": {"damage": [], "cast": [], "taken": []},
        "tick_frequency": None,
        "armor": 0,
        "nonphysical": True,
        "missing": [],
        "notes": [],
    }


class CombatTests(unittest.TestCase):
    """Explicit scenario factors preserve a neutral anchor."""

    def test_armor_order_after_effectiveness_uses_the_explicit_conditional_vector(self):
        scenario = context()
        scenario.update(armor=13579, armor_effectiveness=0.6, armor_penetration=0.08,
                        armor_penetration_order="after_effectiveness")
        self.assertAlmostEqual(apply({"cast_rate": 8.7}, {
            "dps": 100, "trace": [], "assumptions": [],
        }, scenario)["dps"], 88.70301342219885)

    def test_explicit_armor_order_stays_in_the_unresolved_coverage(self):
        scenario = context()
        scenario.update(armor=13579, armor_effectiveness=0.6, armor_penetration=0.08,
                        armor_penetration_order="before_effectiveness")
        self.assertIn("Порядок применения пробивания и эффективности брони не подтверждён",
                      apply({"cast_rate": 8.7}, {"dps": 100, "trace": [], "assumptions": []},
                            scenario)["combat"]["missing"])

    def test_explicit_null_armor_fields_cannot_choose_the_legacy_default(self):
        scenario = context()
        scenario.update(armor_penetration=None, armor_effectiveness=None, armor_penetration_order=None)
        with self.assertRaises(ValueError):
            apply({"cast_rate": 8.7}, {"dps": 100, "trace": [], "assumptions": []}, scenario)

    def test_panel_selector_uses_the_imported_armor_penetration(self):
        scenario = context()
        scenario.update(armor=13579, armor_effectiveness=0.6, armor_penetration="panel",
                        armor_penetration_order="after_effectiveness")
        self.assertAlmostEqual(apply({"cast_rate": 8.7, "armor_penetration": 0.08}, {
            "dps": 100, "trace": [], "assumptions": [],
        }, scenario)["dps"], 88.70301342219885)

    def test_panel_selector_cannot_replace_missing_armor_penetration_with_zero(self):
        scenario = context()
        scenario.update(armor_effectiveness=0.6, armor_penetration="panel",
                        armor_penetration_order="after_effectiveness")
        with self.assertRaisesRegex(ValueError, "Panel armor penetration is missing"):
            apply({"cast_rate": 8.7}, {"dps": 100, "trace": [], "assumptions": []}, scenario)

    def test_numeric_armor_penetration_cannot_override_an_imported_value(self):
        scenario = context()
        scenario.update(armor_effectiveness=0.6, armor_penetration=0.09,
                        armor_penetration_order="after_effectiveness")
        with self.assertRaisesRegex(ValueError, "must match"):
            apply({"cast_rate": 8.7, "armor_penetration": 0.08},
                  {"dps": 100, "trace": [], "assumptions": []}, scenario)

    def test_boolean_panel_penetration_cannot_equal_a_numeric_scenario(self):
        for value in (False, True):
            scenario = context()
            scenario.update(armor_effectiveness=0.6, armor_penetration=0 if value is False else 1,
                            armor_penetration_order="after_effectiveness")
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply({"cast_rate": 8.7, "armor_penetration": value},
                      {"dps": 100, "trace": [], "assumptions": []}, scenario)

    def test_panel_penetration_trace_shows_the_number_without_an_extra_multiplier(self):
        scenario = context()
        scenario.update(armor_effectiveness=0.6, armor_penetration="panel",
                        armor_penetration_order="after_effectiveness")
        self.assertIn({"label": "Пробивание редукции брони из панели", "value": 0.08, "unit": "fraction"},
                      apply({"cast_rate": 8.7, "armor_penetration": 0.08},
                            {"dps": 100, "trace": [], "assumptions": []}, scenario)["trace"])

    def test_armor_result_keeps_the_resolved_panel_source_and_chosen_hypothesis(self):
        scenario = context()
        scenario.update(armor_effectiveness=0.6, armor_penetration="panel",
                        armor_penetration_order="before_effectiveness")
        result = apply({"cast_rate": 8.7, "armor_penetration": 0.08},
                       {"dps": 100, "trace": [], "assumptions": []}, scenario)
        self.assertEqual(tuple(result["combat"][field] for field in (
            "armor_effectiveness", "armor_penetration", "armor_penetration_order", "armor_penetration_source")),
                         (0.6, 0.08, "before_effectiveness", "panel"))

    def test_explicit_armor_hypothesis_replaces_the_obsolete_anchor_limitation(self):
        scenario = context()
        scenario.update(armor_effectiveness=0.6, armor_penetration=0.08,
                        armor_penetration_order="after_effectiveness")
        limitation = "Броня учитывается только при явном боевом контексте; пробивание брони не реализовано"
        self.assertNotIn(limitation, apply({"cast_rate": 8.7}, {
            "dps": 100, "trace": [], "assumptions": [limitation, "Пробивание брони не моделируется"],
        }, scenario)["assumptions"])

    def test_order_before_effectiveness_replays_the_other_conditional_vector(self):
        scenario = context()
        scenario.update(armor=13579, armor_effectiveness=0.6, armor_penetration=0.08,
                        armor_penetration_order="before_effectiveness")
        self.assertAlmostEqual(apply({"cast_rate": 8.7}, {
            "dps": 100, "trace": [], "assumptions": [],
        }, scenario)["dps"], 85.50301342219885)

    def test_negative_armor_mitigation_increases_damage_without_clamping(self):
        scenario = context()
        scenario.update(armor=4321, nonphysical=False, armor_effectiveness=1, armor_penetration=0.15,
                        armor_penetration_order="after_effectiveness")
        self.assertAlmostEqual(apply({"cast_rate": 8.7}, {
            "dps": 100, "trace": [], "assumptions": [],
        }, scenario)["dps"], 102.24951237720906)

    def test_carino_heat_uses_both_the_observed_and_target_state(self):
        scenario = context()
        scenario["carino"] = {"rank": 2, "eternal": True,
                              "reference": {"heat": 7, "effect": 1},
                              "target": {"heat": 13, "effect": 1.5}}
        self.assertAlmostEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["dps"], 175.1685609939245)

    def test_carino_does_not_infer_the_heat_effect(self):
        scenario = context()
        scenario["carino"] = {"rank": 2, "eternal": True,
                              "reference": {"heat": 7}, "target": {"heat": 13, "effect": 1.5}}
        with self.assertRaisesRegex(ValueError, "Carino reference requires"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_compiling_carino_does_not_change_the_input_context(self):
        scenario = context()
        scenario["carino"] = {"rank": 2, "eternal": True,
                              "reference": {"heat": 7, "effect": 1},
                              "target": {"heat": 13, "effect": 1.5}}
        previous = copy.deepcopy(scenario)
        apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)
        self.assertEqual(scenario, previous)

    def test_carino_does_not_claim_verified_tangle_inheritance(self):
        scenario = context()
        scenario["carino"] = {"rank": 2, "eternal": False,
                              "reference": {"heat": 0, "effect": 1},
                              "target": {"heat": 13, "effect": 1}}
        self.assertIn("Наследование Heat модификаторов Tangle не подтверждено", apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["combat"]["missing"])

    def test_carino_cannot_duplicate_a_manual_damage_affix(self):
        scenario = context()
        scenario["carino"] = {"rank": 2, "eternal": False,
                              "reference": {"heat": 0, "effect": 1},
                              "target": {"heat": 7, "effect": 1}}
        scenario["target"]["damage"] = [{"id": "manual-copy", "affix": "carino-incinerated-glory",
                                          "value": 0.02, "stacks": 7, "mode": "add"}]
        with self.assertRaisesRegex(ValueError, "Carino modifiers cannot be supplied manually"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_carino_cannot_duplicate_a_manual_cast_affix(self):
        scenario = context()
        scenario["carino"] = {"rank": 2, "eternal": True,
                              "reference": {"heat": 7, "effect": 1},
                              "target": {"heat": 13, "effect": 1}}
        scenario["reference"]["cast"] = [{"id": "manual-copy", "affix": "carino-eternal-flames",
                                           "value": 0.004, "stacks": 7, "mode": "add"}]
        with self.assertRaisesRegex(ValueError, "Carino modifiers cannot be supplied manually"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_neutral_context_preserves_damage(self):
        self.assertEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "status": "conditional", "trace": [], "assumptions": [],
        }, context())["dps"], 137)

    def test_damage_changes_use_the_target_over_reference_ratio(self):
        scenario = context()
        scenario["reference"]["damage"] = [{
            "id": "before", "affix": "amplification", "value": 0.5, "stacks": 1, "mode": "add",
        }]
        scenario["target"]["damage"] = [{
            "id": "after", "affix": "amplification", "value": 1.25, "stacks": 1, "mode": "add",
        }]
        self.assertEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "status": "conditional", "trace": [], "assumptions": [],
        }, scenario)["dps"], 205.5)

    def test_damage_taken_changes_are_applied_once(self):
        scenario = context()
        scenario["reference"]["taken"] = [{
            "id": "before", "affix": "vulnerability", "value": 0.4, "stacks": 1, "mode": "add",
        }]
        scenario["target"]["taken"] = [{
            "id": "after", "affix": "vulnerability", "value": 0.75, "stacks": 1, "mode": "add",
        }]
        self.assertEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["dps"], 171.25)

    def test_cast_changes_use_the_observed_reference_rate(self):
        scenario = context()
        scenario["reference"]["cast"] = [{
            "id": "before", "affix": "acceleration", "value": 0.25, "stacks": 1, "mode": "add",
        }]
        scenario["target"]["cast"] = [{
            "id": "after", "affix": "acceleration", "value": 0.5, "stacks": 1, "mode": "add",
        }]
        self.assertAlmostEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["dps"], 164.4)

    def test_nonphysical_armor_reduces_the_anchor_once(self):
        scenario = context()
        scenario["armor"] = 50000
        self.assertAlmostEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["dps"], 82.2)

    def test_missing_context_field_has_a_clear_error(self):
        scenario = context()
        del scenario["notes"]
        with self.assertRaisesRegex(ValueError, "Combat context requires"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_unknown_reference_layer_is_rejected(self):
        scenario = context()
        scenario["reference"]["benchmark"] = 123
        with self.assertRaisesRegex(ValueError, "Reference context requires"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_missing_coverage_requires_text_entries(self):
        scenario = context()
        scenario["missing"] = [17]
        with self.assertRaisesRegex(ValueError, "Missing coverage must contain text"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_modifier_layers_require_arrays(self):
        scenario = context()
        scenario["target"]["damage"] = {}
        with self.assertRaisesRegex(ValueError, "Target damage must be an array"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_zero_reference_factor_has_a_clear_error(self):
        scenario = context()
        scenario["reference"]["damage"] = [{
            "id": "disabled", "affix": "suppression", "value": -1, "stacks": 1, "mode": "add",
        }]
        with self.assertRaisesRegex(ValueError, "Reference damage factor must be positive"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_zero_rate_preserves_a_zero_anchor(self):
        self.assertEqual(apply({"cast_rate": 0}, {
            "dps": 0, "trace": [], "assumptions": [],
        }, context())["dps"], 0)

    def test_zero_rate_cannot_describe_nonzero_anchor_damage(self):
        with self.assertRaisesRegex(ValueError, "Zero cast rate requires zero anchor DPS"):
            apply({"cast_rate": 0}, {"dps": 137, "trace": [], "assumptions": []}, context())

    def test_result_exposes_each_relative_combat_factor(self):
        self.assertEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, context())["combat"], {
            "damage_ratio": 1.0, "cast_ratio": 1.0, "taken_ratio": 1.0,
            "actual_cast_rate": 8.7, "armor_mitigation": 0.0, "missing": [],
        })

    def test_scenario_stays_conditional_even_when_no_gap_is_listed(self):
        self.assertEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "status": "complete", "trace": [], "assumptions": [],
        }, context())["status"], "conditional")

    def test_trace_appends_each_combat_factor_after_the_anchor(self):
        scenario = context()
        scenario["armor"] = 50000
        self.assertEqual([round(entry["factor"], 12) for entry in apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [{"label": "Начало", "factor": 3}], "assumptions": [],
        }, scenario)["trace"]], [3, 1.0, 1.0, 1.0, 0.6])

    def test_missing_effects_remain_visible_without_changing_damage(self):
        scenario = context()
        scenario["missing"] = ["Unknown effect"]
        scenario["notes"] = ["Explicit scenario"]
        self.assertIn("Не учтено: Unknown effect", apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": ["Original assumption"],
        }, scenario)["assumptions"])

    def test_armor_penetration_limitation_is_visible(self):
        self.assertIn("Пробивание брони не моделируется", apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, context())["assumptions"])

    def test_modifier_rows_reject_unknown_fields(self):
        scenario = context()
        scenario["target"]["damage"] = [{
            "id": "new", "affix": "effect", "value": 0.3, "stacks": 1,
            "mode": "add", "benchmark": 1.7,
        }]
        with self.assertRaisesRegex(ValueError, "Target damage modifier requires exactly"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_overflow_cannot_be_reported_as_damage(self):
        scenario = context()
        scenario["target"]["damage"] = [{
            "id": "huge", "affix": "effect", "value": 1e308, "stacks": 1, "mode": "add",
        }]
        with self.assertRaisesRegex(ValueError, "Combat DPS must be finite"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_tick_hypothesis_quantizes_the_observed_cast_rate(self):
        scenario = context()
        scenario["tick_frequency"] = 30
        self.assertEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["combat"]["actual_cast_rate"], 7.5)

    def test_casting_above_the_cap_does_not_amplify_the_capped_anchor(self):
        scenario = context()
        scenario["target"]["cast"] = [{
            "id": "fast", "affix": "acceleration", "value": 0.75, "stacks": 1, "mode": "add",
        }]
        self.assertEqual(apply({"cast_rate": 37.3}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["dps"], 137)

    def test_result_does_not_share_mutable_anchor_or_context_values(self):
        panel = {"cast_rate": 8.7}
        anchor = {"dps": 137, "trace": [{"label": "Start", "value": 137}], "assumptions": ["Original"]}
        scenario = context()
        scenario["missing"] = ["Unknown effect"]
        previous = copy.deepcopy((panel, anchor, scenario))
        result = apply(panel, anchor, scenario)
        result["trace"][0]["value"] = 999
        result["combat"]["missing"].append("New gap")
        self.assertEqual((panel, anchor, scenario), previous)

    def test_unresolved_effects_do_not_supply_an_extra_damage_factor(self):
        scenario = context()
        scenario["missing"] = ["Effect A", "Effect B"]
        self.assertEqual(apply({"cast_rate": 8.7}, {
            "dps": 137, "trace": [], "assumptions": [],
        }, scenario)["dps"], 137)

    def test_zero_reference_cast_factor_cannot_be_divided(self):
        scenario = context()
        scenario["reference"]["cast"] = [{
            "id": "stopped", "affix": "suppression", "value": -1, "stacks": 1, "mode": "add",
        }]
        with self.assertRaisesRegex(ValueError, "Reference cast factor must be positive"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)

    def test_context_cannot_accept_partial_armor_penetration_parameters(self):
        for fields in (("armor_penetration",), ("armor_effectiveness",), ("armor_penetration_order",),
                       ("armor_penetration", "armor_effectiveness"),
                       ("armor_penetration", "armor_penetration_order"),
                       ("armor_effectiveness", "armor_penetration_order")):
            scenario = context()
            values = {"armor_penetration": 0.13, "armor_effectiveness": 0.6,
                      "armor_penetration_order": "after_effectiveness"}
            scenario.update({field: values[field] for field in fields})
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "Combat context requires exactly"):
                apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)
