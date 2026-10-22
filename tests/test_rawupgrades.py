import copy
import unittest

from damage_lab.rawupgrades import evaluate
from test_rawspell import scenario as spell


def scenario():
    baseline = spell()
    baseline["damage"].update(base={"min": 101, "max": 149}, physical={"min": 7, "max": 11},
                              cold={"min": 13, "max": 19}, effectiveness=2,
                              increased={"all": .2, "physical": .3, "cold": .5})
    baseline["critical"].update(chance=.2, multiplier=3, more=0)
    baseline["casting"].update(interval=.5, increased=0)
    return {"format": "tli-raw-upgrade-scenario-v1", "baseline": baseline,
            "currency": "synthetic shard", "candidates": []}


def candidate(identity, target, cost):
    return {"id": identity, "name": "Synthetic " + identity, "scenario": target, "cost": cost, "missing": []}


class RawUpgradesTests(unittest.TestCase):
    """Compare complete source-hit replacements without reusing a panel aggregate."""

    def test_unavailable_spell_groups_block_comparison_without_hiding_supplied_candidates(self):
        for group in ("damage", "critical", "casting"):
            for side in ("baseline", "candidate", "both"):
                with self.subTest(group=group, side=side):
                    document = scenario()
                    document["candidates"] = [candidate("replacement", copy.deepcopy(document["baseline"]), 13)]
                    if side in ("baseline", "both"):
                        document["baseline"][group] = None
                    if side in ("candidate", "both"):
                        document["candidates"][0]["scenario"][group] = None
                    if group in ("damage", "casting") and side != "both":
                        with self.assertRaisesRegex(ValueError, "must share skill"):
                            evaluate(document)
                        continue
                    result = evaluate(document)
                    row = result["candidates"][0]
                    self.assertEqual((row["delta"], row["relative"], row["per_cost"], row["status"],
                                      row["eligible_for_ranking"], result["ranking"], group + ": unavailable" in row["gaps"]),
                                     (None, None, None, "blocked", False, [], True))

    def test_unavailable_damage_does_not_allow_a_different_known_skill(self):
        document = scenario()
        document["baseline"]["damage"] = None
        document["candidates"] = [candidate("replacement", spell(), 13)]
        document["candidates"][0]["scenario"]["context"]["skill_id"] = "other-synthetic-spell"
        with self.assertRaisesRegex(ValueError, "must share skill"):
            evaluate(document)

    def test_a_flat_replacement_recomputes_the_full_hit_instead_of_adding_both_items(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["damage"]["physical"] = {"min": 17, "max": 23}
        document["candidates"] = [candidate("physical", target, 7)]
        result = evaluate(document)
        self.assertEqual(tuple(round(value, 8) for value in (
            result["baseline"]["pre_defence_dps"], result["candidates"][0]["pre_defence_dps"],
            result["candidates"][0]["delta"])), (953.12, 1076.32, 123.2))

    def test_only_the_documented_scenario_and_candidate_fields_are_accepted(self):
        for target, key, value in (("top", "format", "other-v1"), ("top", "panel", {}),
                                   ("top", "currency", " shard "), ("top", "candidates", {}),
                                   ("candidate", "id", ""), ("candidate", "name", 17),
                                   ("candidate", "target", {}), ("candidate", "missing", [""])):
            document = scenario()
            document["candidates"] = [candidate("one", copy.deepcopy(document["baseline"]), 7)]
            (document if target == "top" else document["candidates"][0])[key] = value
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                evaluate(document)

    def test_costs_require_finite_nonnegative_numbers_and_candidate_ids_are_unique(self):
        for cost in (True, False, -3, float("inf"), float("nan"), "7", {}, 10 ** 1000):
            document = scenario()
            document["candidates"] = [candidate("one", copy.deepcopy(document["baseline"]), cost)]
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                evaluate(document)
        document = scenario()
        document["candidates"] = [candidate("same", copy.deepcopy(document["baseline"]), 7)] * 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            evaluate(document)

    def test_variants_require_the_same_skill_catalog_roll_model_and_tick_hypothesis(self):
        for section, field, value in (("context", "skill_id", "different-spell"),
                                       ("context", "catalog_sha256", "c" * 64),
                                       ("damage", "roll_model", "lucky_damage"), ("casting", "frequency", 30)):
            document = scenario()
            target = copy.deepcopy(document["baseline"])
            target[section][field] = value
            document["candidates"] = [candidate("one", target, 7)]
            with self.subTest(section=section, field=field), self.assertRaises(ValueError):
                evaluate(document)

    def test_blocked_baselines_never_produce_a_delta_or_ranking(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["damage"]["physical"] = {"min": 17, "max": 23}
        document["baseline"]["context"]["gates"]["level"]["status"] = "unknown"
        document["candidates"] = [candidate("known-target", target, 7)]
        result = evaluate(document)
        self.assertEqual((result["status"], result["candidates"][0]["delta"], result["ranking"]), ("blocked", None, []))

    def test_candidate_gaps_block_the_raw_result_instead_of_subtracting_a_partial_model(self):
        document = scenario()
        document["candidates"] = [candidate("partial", copy.deepcopy(document["baseline"]), 7)]
        document["candidates"][0]["missing"] = ["Unmapped native flat"]
        result = evaluate(document)["candidates"][0]
        self.assertEqual((result["status"], result["result"]["status"], result["pre_defence_dps"], result["delta"]),
                         ("blocked", "blocked", None, None))

    def test_cost_ranking_separates_free_changes_then_orders_paid_gains_and_ties(self):
        document = scenario()
        physical = copy.deepcopy(document["baseline"])
        physical["damage"]["physical"] = {"min": 17, "max": 23}
        base = copy.deepcopy(document["baseline"])
        base["damage"]["base"] = {"min": 121, "max": 169}
        document["candidates"] = [candidate("tie-b", copy.deepcopy(physical), 7),
                                  candidate("paid", copy.deepcopy(physical), 14),
                                  candidate("free", base, 0), candidate("tie-a", physical, 7),
                                  candidate("unpriced", copy.deepcopy(physical), None),
                                  candidate("neutral", copy.deepcopy(document["baseline"]), 1)]
        self.assertEqual(evaluate(document)["ranking"], ["free", "tie-a", "tie-b", "paid"])

    def test_unpriced_and_free_changes_have_no_division_by_zero_or_market_claim(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["damage"]["physical"] = {"min": 17, "max": 23}
        document["candidates"] = [candidate("unpriced", copy.deepcopy(target), None), candidate("free", target, 0)]
        result = evaluate(document)
        self.assertEqual([(row["status"], row["per_cost"], row["eligible_for_cost_ranking"])
                          for row in result["candidates"]], [("unpriced", None, False), ("free", None, True)])

    def test_unrepresentable_gain_per_cost_is_rejected_instead_of_ranking_zero_or_infinity(self):
        for amount, cost in ((1, 5e-324), (1e-300, 1e300)):
            document = scenario()
            document["baseline"]["damage"].update(base={"min": 0, "max": 0}, physical={"min": 0, "max": 0},
                                                  cold={"min": 0, "max": 0}, effectiveness=1,
                                                  increased={"all": 0, "physical": 0, "cold": 0})
            document["baseline"]["critical"].update(chance=0, multiplier=1, more=0)
            document["baseline"]["casting"].update(interval=1, increased=0)
            target = copy.deepcopy(document["baseline"])
            target["damage"]["base"] = {"min": amount, "max": amount}
            document["candidates"] = [candidate("extreme-price", target, cost)]
            with self.subTest(amount=amount, cost=cost), self.assertRaisesRegex(ValueError, "Gain per cost"):
                evaluate(document)

    def test_native_cold_flat_and_converted_physical_have_distinct_increased_scopes(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["damage"]["cold"] = {"min": 23, "max": 31}
        document["candidates"] = [candidate("cold", target, 11)]
        self.assertAlmostEqual(evaluate(document)["candidates"][0]["delta"], 104.72)

    def test_a_physical_increased_change_leaves_the_native_cold_component_unchanged(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["damage"]["increased"]["physical"] = .8
        document["candidates"] = [candidate("physical-scope", target, 13)]
        result = evaluate(document)["candidates"][0]
        self.assertEqual((round(result["delta"], 8), {key: round(value, 8) for key, value in
                                                    result["result"]["noncritical"]["components"]["native"].items()}),
                         (200.2, {"min": 44.2, "max": 64.6}))

    def test_confirmed_effective_level_base_and_source_changes_are_allowed(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["context"].update(source_sha256="c" * 64, effective_level=18)
        target["context"]["gates"]["level"]["evidence"] = ["synthetic:effective-level-18"]
        target["damage"]["base"] = {"min": 121, "max": 169}
        document["candidates"] = [candidate("level", target, 17)]
        self.assertAlmostEqual(evaluate(document)["candidates"][0]["delta"], 112)

    def test_zero_baselines_have_no_invented_relative_gain_or_free_infinity(self):
        document = scenario()
        for field in ("base", "physical", "cold"):
            document["baseline"]["damage"][field] = {"min": 0, "max": 0}
        target = copy.deepcopy(document["baseline"])
        target["damage"]["base"] = {"min": 7, "max": 7}
        document["candidates"] = [candidate("new", target, 0),
                                  candidate("equal", copy.deepcopy(document["baseline"]), 0)]
        result = evaluate(document)
        self.assertEqual((result["ranking"], [(row["status"], row["relative"], row["per_cost"])
                                              for row in result["candidates"]]),
                         (["new"], [("free", None, None), ("not_upgrade", None, None)]))

    def test_a_blocked_candidate_has_no_partial_numeric_comparison(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["context"]["gates"]["conversion"]["status"] = "conflict"
        document["candidates"] = [candidate("conflict", target, 7)]
        row = evaluate(document)["candidates"][0]
        self.assertEqual((row["delta"], row["relative"], row["per_cost"], row["eligible_for_cost_ranking"]),
                         (None, None, None, False))

    def test_candidate_numeric_validation_still_runs_when_the_baseline_is_blocked(self):
        document = scenario()
        target = copy.deepcopy(document["baseline"])
        target["damage"]["cold"]["max"] = True
        document["baseline"]["context"]["gates"]["version"]["status"] = "unknown"
        document["candidates"] = [candidate("invalid", target, 7)]
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_shared_context_mismatches_are_rejected_even_for_blocked_variants(self):
        document = scenario()
        document["baseline"]["missing"] = ["Missing base binding"]
        target = copy.deepcopy(document["baseline"])
        target["context"]["catalog_sha256"] = "c" * 64
        document["candidates"] = [candidate("other-catalog", target, 7)]
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_the_report_and_all_nested_scenarios_are_detached_from_the_inputs(self):
        document = scenario()
        document["candidates"] = [candidate("partial", copy.deepcopy(document["baseline"]), 7)]
        document["candidates"][0]["missing"] = ["Unmapped critical effect"]
        before = copy.deepcopy(document)
        result = evaluate(document)
        result["scenario"]["baseline"]["damage"]["base"]["min"] = 999
        result["baseline"]["trace"][0]["min"] = 999
        result["candidates"][0]["result"]["scenario"]["missing"].append("new")
        self.assertEqual(document, before)

    def test_every_usable_result_remains_conditional_and_prices_belong_to_the_caller(self):
        document = scenario()
        document["candidates"] = [candidate("equal", copy.deepcopy(document["baseline"]), 7)]
        result = evaluate(document)
        self.assertEqual((result["status"], result["baseline"]["status"], result["candidates"][0]["result"]["status"],
                          result["price_source"], result["quantity_scope"]),
                         ("conditional", "conditional", "conditional", "caller", "pre_defence_single_caster"))

    def test_equal_cost_efficiency_uses_lower_price_before_identity_and_excludes_losses(self):
        document = scenario()
        document["baseline"]["damage"].update(base={"min": 100, "max": 100}, physical={"min": 0, "max": 0},
                                              cold={"min": 0, "max": 0}, effectiveness=1,
                                              increased={"all": 0, "physical": 0, "cold": 0})
        document["baseline"]["critical"].update(chance=0, multiplier=1, more=0)
        document["baseline"]["casting"].update(interval=1, increased=0)
        for identity, amount, cost in (("a-expensive", 400, 6), ("z-cheap", 200, 2), ("loss", 17, 1)):
            target = copy.deepcopy(document["baseline"])
            target["damage"]["base"] = {"min": amount, "max": amount}
            document["candidates"].append(candidate(identity, target, cost))
        self.assertEqual(evaluate(document)["ranking"], ["z-cheap", "a-expensive"])

    def test_malformed_nested_scenarios_and_missing_lists_fail_with_value_errors(self):
        for value in (None, [], {}, {"missing": None}, {"missing": [{}]}):
            document = scenario()
            document["candidates"] = [candidate("invalid", value, 7)]
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate(document)

    def test_free_positive_variants_are_separate_from_a_finite_cost_ratio(self):
        document = scenario()
        for identity, amount in (("b", 400), ("a", 200)):
            target = copy.deepcopy(document["baseline"])
            target["damage"]["base"] = {"min": amount, "max": amount}
            document["candidates"].append(candidate(identity, target, 0))
        self.assertEqual(evaluate(document)["ranking"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
