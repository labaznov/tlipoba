"""Synthetic upgrade comparisons independent of player data and markets."""

import copy
import unittest

from damage_lab.upgrades import evaluate


def scenario():
    return {
        "format": "tli-upgrade-scenario-v1",
        "panel": {"spell_dps": 1000, "cast_rate": 11, "max_tangles": 2,
                  "extra_attachments": 0, "cold_penetration": 0},
        "condition": {"basis": "panel", "active": 1, "hits": 1, "retention": 0.25,
                      "lucky": False, "critical_more": 0, "resistance": 0, "taken": 0, "uptime": 1},
        "combat": {"reference": {"damage": [], "cast": [], "taken": []},
                   "target": {"damage": [], "cast": [], "taken": []},
                   "tick_frequency": None, "armor": 0, "nonphysical": True,
                   "missing": [], "notes": []},
        "currency": "synthetic token",
        "candidates": [],
    }


def candidate(identity, value, cost):
    return {"id": identity, "name": f"Synthetic {identity}",
            "target": {"damage": [{"id": identity, "affix": "amplification", "value": value,
                                    "stacks": 1, "mode": "add"}], "cast": [], "taken": []},
            "cost": cost, "missing": []}


class Upgrades(unittest.TestCase):
    """Compare only explicit supported modifier replacements."""

    def test_replacement_uses_the_complete_target_pool_over_the_shared_reference(self):
        document = scenario()
        document["combat"]["reference"]["damage"] = [
            {"id": "old-a", "affix": "amplification", "value": 0.25, "stacks": 1, "mode": "add"},
            {"id": "old-b", "affix": "amplification", "value": 0.15, "stacks": 1, "mode": "add"},
        ]
        document["combat"]["target"]["damage"] = copy.deepcopy(document["combat"]["reference"]["damage"])
        document["candidates"] = [candidate("replacement", 0.75, 17)]
        result = evaluate(document)
        self.assertEqual((result["baseline"]["dps"], result["candidates"][0]["dps"],
                          result["candidates"][0]["delta"]), (1000, 1250, 250))

    def test_cost_ranking_places_positive_free_changes_first_then_gain_per_cost(self):
        document = scenario()
        document["candidates"] = [candidate("paid", 0.6, 20), candidate("tie-b", 0.3, 10),
                                  candidate("free", 0.1, 0), candidate("tie-a", 0.3, 10),
                                  candidate("unpriced", 0.9, None), candidate("equal", 0, 1),
                                  candidate("loss", -0.1, 2)]
        self.assertEqual(evaluate(document)["ranking"], ["free", "tie-a", "tie-b", "paid"])

    def test_unknown_candidate_effects_remain_visible_and_block_ranking(self):
        document = scenario()
        document["candidates"] = [candidate("partial", 0.75, 0)]
        document["candidates"][0]["missing"] = ["Unmapped trigger"]
        result = evaluate(document)
        self.assertEqual((result["ranking"], result["candidates"][0]["status"],
                          result["candidates"][0]["gaps"]), ([], "incomplete", ["Unmapped trigger"]))

    def test_unknown_fields_cannot_override_the_shared_scenario(self):
        for path, field in (((), "benchmark"), (("panel",), "damage"), (("condition",), "tick"),
                            (("candidates", 0), "panel"), (("candidates", 0), "combat")):
            document = scenario()
            document["candidates"] = [candidate("one", 0.3, 17)]
            target = document
            for part in path:
                target = target[part]
            target[field] = 37
            with self.subTest(path=path, field=field), self.assertRaises(ValueError):
                evaluate(document)

    def test_nonfinite_boolean_and_out_of_domain_numbers_cannot_enter_a_comparison(self):
        for path, value in ((("panel", "spell_dps"), True), (("panel", "cast_rate"), False),
                            (("panel", "hit_min"), -1), (("panel", "crit_multiplier"), float("inf")),
                            (("panel", "max_tangles"), 2.0), (("condition", "active"), True),
                            (("condition", "lucky"), 0), (("condition", "critical_more"), True),
                            (("condition", "taken"), float("nan")), (("candidates", 0, "cost"), True),
                            (("candidates", 0, "cost"), -7), (("candidates", 0, "cost"), float("inf"))):
            document = scenario()
            document["candidates"] = [candidate("one", 0.3, 17)]
            target = document
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                evaluate(document)

    def test_overflowing_gain_per_cost_cannot_be_ranked_as_infinity(self):
        document = scenario()
        document["candidates"] = [candidate("tiny-price", 0.75, 5e-324)]
        with self.assertRaisesRegex(ValueError, "Gain per cost"):
            evaluate(document)

    def test_malformed_structure_and_untrimmed_text_fail_with_value_errors(self):
        for path, value in ((("format",), "other-v1"), (("currency",), " token "),
                            (("candidates",), {}), (("candidates", 0, "id"), ""),
                            (("candidates", 0, "name"), 17), (("candidates", 0, "missing"), {}),
                            (("candidates", 0, "missing"), [""])):
            document = scenario()
            document["candidates"] = [candidate("one", 0.3, 17)]
            target = document
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                evaluate(document)

    def test_duplicate_candidate_identities_cannot_overwrite_a_rank(self):
        document = scenario()
        document["candidates"] = [candidate("same", 0.3, 17), candidate("same", 0.6, 13)]
        with self.assertRaisesRegex(ValueError, "Duplicate candidate"):
            evaluate(document)

    def test_the_selected_basis_requires_its_fields_without_invented_defaults(self):
        for basis in ("panel", "hit"):
            document = scenario()
            document["condition"]["basis"] = basis
            del document["panel"]["spell_dps"]
            with self.subTest(basis=basis), self.assertRaisesRegex(ValueError, "Upgrade panel"):
                evaluate(document)

    def test_an_inverted_optional_hit_range_cannot_hide_behind_panel_basis(self):
        document = scenario()
        document["panel"].update(hit_min=173, hit_max=137)
        with self.assertRaisesRegex(ValueError, "Hit range"):
            evaluate(document)

    def test_cast_upgrades_cannot_exceed_the_shared_thirty_cast_cap(self):
        document = scenario()
        document["panel"]["cast_rate"] = 23
        document["candidates"] = [candidate("speed", 0, 17)]
        document["candidates"][0]["target"]["cast"] = [
            {"id": "speed", "affix": "acceleration", "value": 0.5, "stacks": 1, "mode": "add"},
        ]
        self.assertAlmostEqual(evaluate(document)["candidates"][0]["dps"], 1304.3478260869565)

    def test_tick_hypothesis_applies_equally_to_baseline_and_candidate_casts(self):
        document = scenario()
        document["panel"]["cast_rate"] = 8.7
        document["combat"]["tick_frequency"] = 30
        document["candidates"] = [candidate("speed", 0, 17)]
        document["candidates"][0]["target"]["cast"] = [
            {"id": "speed", "affix": "acceleration", "value": 0.4, "stacks": 1, "mode": "add"},
        ]
        result = evaluate(document)
        self.assertEqual((result["baseline"]["combat"]["actual_cast_rate"],
                          result["candidates"][0]["result"]["combat"]["actual_cast_rate"]), (7.5, 10))

    def test_candidate_gain_reuses_geometry_target_defense_and_uptime(self):
        document = scenario()
        document["panel"].update(extra_attachments=1, cold_penetration=0.1)
        document["condition"].update(active=2, hits=3, retention=0.25, resistance=0.4, taken=0.2, uptime=0.75)
        document["combat"]["armor"] = 50000
        document["candidates"] = [candidate("power", 0.5, 17)]
        self.assertAlmostEqual(evaluate(document)["candidates"][0]["delta"], 567)

    def test_unpriced_effects_can_have_a_supported_gain_without_cost_ranking(self):
        document = scenario()
        document["candidates"] = [candidate("unpriced", 0.75, None)]
        result = evaluate(document)["candidates"][0]
        self.assertEqual((result["status"], result["eligible_for_ranking"],
                          result["eligible_for_cost_ranking"], result["per_cost"]), ("unpriced", True, False, None))

    def test_zero_baseline_has_no_invented_relative_gain_or_free_infinity(self):
        document = scenario()
        document["panel"]["spell_dps"] = 0
        document["candidates"] = [candidate("zero", 0.75, 0)]
        result = evaluate(document)["candidates"][0]
        self.assertEqual((result["relative"], result["per_cost"], result["status"]), (None, None, "not_upgrade"))

    def test_shared_missing_effects_block_a_supported_numerical_gain(self):
        document = scenario()
        document["combat"]["missing"] = ["Unverified inheritance"]
        document["candidates"] = [candidate("power", 0.5, 17)]
        self.assertEqual(evaluate(document)["ranking"], [])

    def test_results_preserve_a_detached_copy_of_all_scenario_assumptions(self):
        document = scenario()
        document["combat"]["notes"] = ["Synthetic target"]
        document["candidates"] = [candidate("power", 0.5, 17)]
        previous = copy.deepcopy(document)
        result = evaluate(document)
        result["scenario"]["combat"]["notes"].append("Changed result")
        result["baseline"]["trace"][0]["value"] = 999
        result["candidates"][0]["result"]["combat"]["missing"].append("Changed gap")
        self.assertEqual(document, previous)

    def test_hit_basis_keeps_the_same_critical_expectation_for_every_candidate(self):
        document = scenario()
        document["condition"]["basis"] = "hit"
        document["panel"].update(hit_min=100, hit_max=300, crit_chance=0.25, crit_multiplier=4)
        document["candidates"] = [candidate("power", 0.5, 17)]
        self.assertEqual(evaluate(document)["candidates"][0]["delta"], 1925)

    def test_report_and_candidate_calculations_stay_conditional_with_no_declared_gaps(self):
        document = scenario()
        document["candidates"] = [candidate("free", 0.5, 0)]
        result = evaluate(document)
        self.assertEqual((result["status"], result["baseline"]["status"],
                          result["candidates"][0]["result"]["status"], result["price_source"]),
                         ("conditional", "conditional", "conditional", "caller"))

    def test_candidate_assumptions_keep_coverage_gaps_without_filling_them_with_damage(self):
        document = scenario()
        document["candidates"] = [candidate("partial", 0.5, 17)]
        document["candidates"][0]["missing"] = ["Unmapped projectile interaction"]
        result = evaluate(document)["candidates"][0]
        self.assertIn("Не учтено: Unmapped projectile interaction", result["result"]["assumptions"])

    def test_target_modifier_instances_cannot_be_duplicated_to_inflate_a_gain(self):
        document = scenario()
        document["candidates"] = [candidate("duplicate", 0.5, 17)]
        document["candidates"][0]["target"]["damage"] *= 2
        with self.assertRaisesRegex(ValueError, "Duplicate modifier"):
            evaluate(document)

    def test_target_effect_overflow_cannot_escape_as_a_candidate_dps(self):
        document = scenario()
        document["candidates"] = [candidate("overflow", 1e308, 17)]
        with self.assertRaisesRegex(ValueError, "Combat DPS must be finite"):
            evaluate(document)
