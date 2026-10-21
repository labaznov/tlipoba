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

    def test_context_cannot_accept_armor_penetration(self):
        scenario = context()
        scenario["armor_penetration"] = 0.13
        with self.assertRaisesRegex(ValueError, "Combat context requires exactly"):
            apply({"cast_rate": 8.7}, {"dps": 137, "trace": [], "assumptions": []}, scenario)
