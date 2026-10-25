import copy
import json
import unittest

from damage_lab.upgradegoal import evaluate
from test_combatupgrades import candidate, unit


def scenario(baseline, rows):
    return {"format": "tli-combat-upgrade-scenario-v1", "baseline": unit(baseline),
            "currency": "synthetic tokens", "candidates": rows}


class UpgradeGoalTests(unittest.TestCase):
    """Choose supported progress within an explicit caller-priced budget."""

    def test_cheapest_sufficient_option_can_differ_from_the_efficiency_winner(self):
        report = evaluate(scenario(1000, [candidate("efficient", unit(1500), 100),
                                          candidate("sufficient", unit(1100), 25)]),
                          minimum=100, budget=30)
        self.assertEqual(report["goal"]["selected"], "sufficient")

    def test_efficiency_order_is_preserved_alongside_the_cheapest_sufficient_order(self):
        report = evaluate(scenario(1000, [candidate("efficient", unit(1500), 100),
                                          candidate("sufficient", unit(1100), 25)]),
                          minimum=100, budget=100)
        self.assertEqual((report["ranking"], report["goal"]["ranking"]),
                         (["efficient", "sufficient"], ["sufficient", "efficient"]))

    def test_minimum_gain_requires_a_finite_positive_number(self):
        for minimum in (0, -1, True, False, float("nan"), float("inf"), -float("inf"), "3", None, 10 ** 400):
            with self.subTest(minimum=minimum), self.assertRaisesRegex(ValueError, "minimum"):
                evaluate(scenario(100, []), minimum=minimum, budget=17)

    def test_budget_requires_a_finite_nonnegative_number(self):
        for budget in (-1, True, False, float("nan"), float("inf"), -float("inf"), "3", None, 10 ** 400):
            with self.subTest(budget=budget), self.assertRaisesRegex(ValueError, "budget"):
                evaluate(scenario(100, []), minimum=13, budget=budget)

    def test_exact_minimum_and_budget_boundaries_are_included(self):
        report = evaluate(scenario(100, [candidate("boundary", unit(117), 13)]), minimum=17, budget=13)
        self.assertEqual(report["goal"]["selected"], "boundary")

    def test_no_rounding_tolerance_promotes_a_gain_below_the_minimum(self):
        report = evaluate(scenario(100, [candidate("small", unit(117), 13)]),
                          minimum=17.000000000001, budget=13)
        self.assertIsNone(report["goal"]["selected"])

    def test_positive_free_progress_can_meet_a_zero_budget(self):
        report = evaluate(scenario(100, [candidate("free", unit(127), 0)]), minimum=17, budget=0)
        self.assertEqual(report["goal"]["selected"], "free")

    def test_equal_cost_prefers_the_greater_supported_gain(self):
        report = evaluate(scenario(100, [candidate("a-small", unit(127), 0),
                                         candidate("z-large", unit(153), 0)]), minimum=17, budget=0)
        self.assertEqual(report["goal"]["ranking"], ["z-large", "a-small"])

    def test_equal_cost_and_gain_use_identity_for_a_deterministic_tie(self):
        report = evaluate(scenario(100, [candidate("b", unit(127), 7),
                                         candidate("a", unit(127), 7)]), minimum=17, budget=7)
        self.assertEqual(report["goal"]["ranking"], ["a", "b"])

    def test_unknown_price_is_not_assumed_to_be_affordable(self):
        report = evaluate(scenario(100, [candidate("unknown", unit(127), None)]), minimum=17, budget=0)
        self.assertEqual((report["goal"]["status"], report["goal"]["selected"], report["goal"]["ranking"]),
                         ("no_supported_affordable_candidate", None, []))

    def test_unsupported_effects_cannot_beat_a_supported_affordable_candidate(self):
        unsupported = candidate("unknown", unit(197), 1)
        unsupported["missing"] = ["unmapped effect"]
        report = evaluate(scenario(100, [unsupported, candidate("supported", unit(127), 9)]),
                          minimum=17, budget=9)
        self.assertEqual(report["goal"]["selected"], "supported")

    def test_unknown_baseline_stats_block_selection(self):
        document = scenario(100, [candidate("candidate", unit(127), 9)])
        document["baseline"]["spell"]["critical"] = None
        report = evaluate(document, minimum=17, budget=9)
        self.assertEqual((report["goal"]["status"], report["goal"]["selected"], report["goal"]["ranking"]),
                         ("blocked", None, []))

    def test_no_match_is_explicit_even_when_the_efficiency_ranking_is_nonempty(self):
        report = evaluate(scenario(100, [candidate("expensive", unit(137), 19)]), minimum=17, budget=13)
        self.assertEqual((report["goal"]["status"], report["goal"]["selected"], report["ranking"]),
                         ("no_supported_affordable_candidate", None, ["expensive"]))

    def test_currency_and_absolute_combat_scope_are_preserved_without_conversion(self):
        report = evaluate(scenario(100, []), minimum=17, budget=13)
        self.assertEqual((report["goal"]["minimum_gain"], report["goal"]["budget"],
                          report["goal"]["currency"], report["goal"]["quantity_scope"]),
                         (17, 13, "synthetic tokens", "conditional_combat_dps"))

    def test_input_scenario_is_not_changed_by_the_goal_query(self):
        document = scenario(100, [candidate("candidate", unit(127), 9)])
        preserved = copy.deepcopy(document)
        evaluate(document, minimum=17, budget=9)
        self.assertEqual(document, preserved)

    def test_candidates_still_require_the_same_target_and_uptime(self):
        document = scenario(100, [candidate("candidate", unit(127), 9)])
        document["candidates"][0]["scenario"]["uptime"] = .5
        with self.assertRaisesRegex(ValueError, "target and uptime"):
            evaluate(document, minimum=17, budget=9)

    def test_equivalent_whole_number_goals_have_byte_identical_json(self):
        document = scenario(100, [candidate("candidate", unit(127), 9)])
        self.assertEqual(json.dumps(evaluate(document, minimum=17, budget=9), sort_keys=True),
                         json.dumps(evaluate(document, minimum=17.0, budget=9.0), sort_keys=True))

    def test_a_large_integer_minimum_is_preserved_without_rounding_through_float(self):
        report = evaluate(scenario(100, []), minimum=2 ** 53 + 1, budget=1)
        self.assertEqual((type(report["goal"]["minimum_gain"]), report["goal"]["minimum_gain"]),
                         (int, 2 ** 53 + 1))

    def test_rejected_candidates_keep_each_known_reason_in_input_order(self):
        unsupported = candidate("missing", unit(127), None)
        unsupported["missing"] = ["unmapped effect"]
        report = evaluate(scenario(100, [candidate("unpriced", unit(127), None), unsupported,
                                         candidate("small", unit(107), 9), candidate("regression", unit(97), 7),
                                         candidate("expensive", unit(129), 11), candidate("supported", unit(127), 9)]),
                          minimum=17, budget=9)
        self.assertEqual(report["goal"]["excluded"],
                         [{"id": "unpriced", "reasons": ["unpriced"]},
                          {"id": "missing", "reasons": ["blocked", "unpriced"]},
                          {"id": "small", "reasons": ["below_minimum"]},
                          {"id": "regression", "reasons": ["not_upgrade"]},
                          {"id": "expensive", "reasons": ["over_budget"]}])

    def test_goal_validation_precedes_model_evaluation(self):
        with self.assertRaisesRegex(ValueError, "minimum"):
            evaluate({"invalid": "scenario"}, minimum=0, budget=13)

    def test_negative_zero_budget_has_one_canonical_zero_representation(self):
        report = evaluate(scenario(100, [candidate("free", unit(127), 0)]), minimum=17, budget=-0.0)
        self.assertEqual((type(report["goal"]["budget"]), report["goal"]["budget"]), (int, 0))
