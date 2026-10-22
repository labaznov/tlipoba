import copy
import unittest

from damage_lab.combatupgrades import evaluate
from test_rawcombat import scenario as combat


def scenario():
    """A complete shared-target comparison with independent combat damage oracles."""
    baseline = combat()
    baseline["target"].update(armor=100000, armor_effectiveness=.5, armor_penetration=.1)
    hit = copy.deepcopy(baseline)
    hit["spell"]["damage"]["base"] = {"min": 200, "max": 200}
    topology = copy.deepcopy(baseline)
    topology["topology"]["extra"] = 2
    return {"format": "tli-combat-upgrade-scenario-v1", "baseline": baseline, "currency": "synthetic tokens",
            "candidates": [candidate("hit", hit, 17), candidate("topology", topology, 11)]}


def candidate(identity, target, cost):
    return {"id": identity, "name": "Synthetic " + identity, "scenario": target, "cost": cost, "missing": []}


def unit(amount):
    """A neutral target and one caster expose exact whole-DPS price and ranking examples."""
    target = combat()
    target["spell"]["damage"]["base"] = {"min": amount, "max": amount}
    target["spell"]["critical"].update(chance=0, multiplier=1)
    target["spell"]["casting"]["interval"] = 1
    target["topology"].update(maximum=1, extra=0, active=1, hits=1)
    target["target"].update(cold_resistance=0, cold_penetration=0, armor=0, armor_effectiveness=1,
                             armor_penetration=0, increased_taken=0, more_taken=[])
    target["uptime"] = 1
    return target


class CombatUpgradesTests(unittest.TestCase):
    """Compare complete conditional combat replacements without duplicating owned spell or target stages."""

    def test_unavailable_spell_groups_cannot_produce_combat_deltas_or_price_rankings(self):
        for group in ("damage", "critical", "casting"):
            for side in ("baseline", "candidate", "both"):
                with self.subTest(group=group, side=side):
                    document = scenario()
                    document["candidates"] = document["candidates"][:1]
                    if side in ("baseline", "both"):
                        document["baseline"]["spell"][group] = None
                    if side in ("candidate", "both"):
                        document["candidates"][0]["scenario"]["spell"][group] = None
                    if group in ("damage", "casting") and side != "both":
                        with self.assertRaisesRegex(ValueError, "must share skill"):
                            evaluate(document)
                        continue
                    row = evaluate(document)["candidates"][0]
                    self.assertEqual((row["delta"], row["relative"], row["per_cost"], row["status"],
                                      row["eligible_for_cost_ranking"], "spell: " + group + ": unavailable" in row["gaps"]),
                                     (None, None, None, "blocked", False, True))

    def test_unavailable_casting_does_not_allow_different_known_target_conditions(self):
        document = scenario()
        document["baseline"]["spell"]["casting"] = None
        document["candidates"][0]["scenario"]["target"]["cold_resistance"] = .37
        with self.assertRaisesRegex(ValueError, "complete target and uptime"):
            evaluate(document)

    def test_hit_and_topology_replacements_match_independent_full_combat_oracles(self):
        result = evaluate(scenario())
        self.assertEqual((round(result["baseline"]["dps"], 6),
                          [(row["id"], round(row["dps"], 6), round(row["delta"], 6))
                           for row in result["candidates"]]),
                         (291.06, [("hit", 582.12, 291.06), ("topology", 436.59, 145.53)]))

    def test_every_target_field_and_uptime_must_remain_identical(self):
        changes = (("cold_resistance", .3), ("cold_penetration", .2), ("armor", 17000),
                   ("armor_effectiveness", .7), ("armor_penetration", .2),
                   ("armor_penetration_order", "before_effectiveness"), ("increased_taken", .3),
                   ("more_taken", []), ("uptime", .7))
        for field, value in changes:
            with self.subTest(field=field):
                document = scenario()
                target = document["candidates"][0]["scenario"]
                (target if field == "uptime" else target["target"])[field] = value
                with self.assertRaisesRegex(ValueError, "complete target and uptime"):
                    evaluate(document)

    def test_shared_skill_catalog_roll_model_and_tick_hypothesis_cannot_change(self):
        for section, field, value in (("context", "skill_id", "other-synthetic-spell"),
                                       ("context", "catalog_sha256", "e" * 64),
                                       ("damage", "roll_model", "lucky_damage"), ("casting", "frequency", 30)):
            with self.subTest(section=section, field=field):
                document = scenario()
                document["candidates"][0]["scenario"]["spell"][section][field] = value
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_confirmed_source_level_and_spell_changes_are_complete_replacements(self):
        document = scenario()
        document["candidates"][0]["scenario"]["spell"]["context"].update(source_sha256="e" * 64, effective_level=18)
        row = evaluate(document)["candidates"][0]
        self.assertEqual((row["result"]["spell"]["scenario"]["context"]["effective_level"],
                          round(row["dps"], 6), round(row["delta"], 6)), (18, 582.12, 291.06))

    def test_a_blocked_baseline_prevents_comparisons_without_hiding_candidate_results(self):
        document = scenario()
        document["baseline"]["gates"]["inheritance"]["status"] = "unknown"
        result = evaluate(document)
        self.assertEqual((result["status"], result["baseline"]["dps"], result["ranking"],
                          [(row["status"], row["result"]["status"], row["delta"], row["relative"],
                            row["per_cost"], row["eligible_for_ranking"], row["gaps"])
                           for row in result["candidates"]]),
                         ("blocked", None, [], [("blocked", "conditional", None, None, None, False,
                                                 ["inheritance: unknown"])] * 2))

    def test_missing_candidate_effects_block_its_full_result_and_all_price_comparisons(self):
        document = scenario()
        document["candidates"][0]["missing"] = ["Unmapped replacement effect"]
        row = evaluate(document)["candidates"][0]
        self.assertEqual((row["status"], row["result"]["status"], row["dps"], row["delta"],
                          row["relative"], row["per_cost"], row["eligible_for_cost_ranking"], row["gaps"]),
                         ("blocked", "blocked", None, None, None, None, False, ["Unmapped replacement effect"]))

    def test_unknown_or_conflicting_candidate_gates_never_produce_partial_deltas(self):
        outcomes = []
        for name in ("inheritance", "hit_topology", "target_state"):
            for status in ("unknown", "conflict"):
                document = scenario()
                document["candidates"][0]["scenario"]["gates"][name]["status"] = status
                row = evaluate(document)["candidates"][0]
                outcomes.append((row["dps"], row["delta"], row["relative"], row["per_cost"],
                                 row["eligible_for_ranking"], row["status"]))
        self.assertEqual(outcomes, [(None, None, None, None, False, "blocked")] * 6)

    def test_unresolved_spell_coverage_stays_blocked_inside_the_combat_result(self):
        document = scenario()
        document["candidates"][0]["scenario"]["spell"]["missing"] = ["Unmapped critical operation"]
        row = evaluate(document)["candidates"][0]
        self.assertEqual((row["result"]["spell"]["status"], row["result"]["dps"], row["delta"], row["gaps"]),
                         ("blocked", None, None, ["spell: Unmapped critical operation"]))

    def test_every_candidate_is_validated_even_when_the_baseline_is_blocked(self):
        for change in ("spell", "target", "topology", "cost", "missing"):
            with self.subTest(change=change):
                document = scenario()
                document["baseline"]["missing"] = ["Unknown baseline modifier"]
                row = document["candidates"][1]
                if change == "spell":
                    row["scenario"]["spell"]["damage"]["base"]["max"] = True
                elif change == "target":
                    row["scenario"]["target"]["armor"] = float("nan")
                elif change == "topology":
                    row["scenario"]["topology"]["active"] = 2.0
                else:
                    row[change] = True
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_shared_target_and_context_mismatches_still_fail_for_blocked_scenarios(self):
        for change in ("target", "context"):
            with self.subTest(change=change):
                document = scenario()
                document["baseline"]["missing"] = ["Unknown baseline modifier"]
                document["candidates"][0]["missing"] = ["Unknown candidate modifier"]
                target = document["candidates"][0]["scenario"]
                if change == "target":
                    target["target"]["armor"] = 18000
                else:
                    target["spell"]["context"]["skill_id"] = "different-spell"
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_free_and_unpriced_gains_keep_distinct_statuses_without_infinite_ratios(self):
        document = scenario()
        document["candidates"][0]["cost"] = None
        document["candidates"][1]["cost"] = 0
        result = evaluate(document)
        self.assertEqual(([(row["status"], row["per_cost"], row["eligible_for_ranking"],
                            row["eligible_for_cost_ranking"]) for row in result["candidates"]], result["ranking"]),
                         ([("unpriced", None, True, False), ("free", None, True, True)], ["topology"]))

    def test_cost_ranking_places_free_first_then_paid_efficiency_cost_and_identity(self):
        document = scenario()
        document["baseline"] = unit(100)
        document["candidates"] = [candidate(identity, unit(amount), cost) for identity, amount, cost in
                                  (("tie-b", 200, 2), ("a-expensive", 400, 6), ("free-b", 500, 0),
                                   ("loss", 17, 1), ("neutral", 100, 1), ("free-a", 200, 0),
                                   ("tie-a", 200, 2), ("unpriced", 600, None), ("paid", 150, 2))]
        self.assertEqual(evaluate(document)["ranking"], ["free-a", "free-b", "tie-a", "tie-b", "a-expensive", "paid"])

    def test_positive_gains_report_full_combat_relative_and_cost_ratios(self):
        document = scenario()
        document["baseline"] = unit(173)
        document["candidates"] = [candidate("hit", unit(211), 19)]
        row = evaluate(document)["candidates"][0]
        self.assertEqual((row["dps"], row["delta"], row["relative"], row["per_cost"], row["status"]),
                         (211, 38, 38 / 173, 2, "upgrade"))

    def test_zero_baselines_have_no_invented_relative_gain_and_losses_are_not_upgrades(self):
        document = scenario()
        document["baseline"] = unit(0)
        document["candidates"] = [candidate("new", unit(19), 0), candidate("equal", unit(0), 0)]
        result = evaluate(document)
        self.assertEqual((result["ranking"], [(row["status"], row["relative"], row["per_cost"])
                                              for row in result["candidates"]]),
                         (["new"], [("free", None, None), ("not_upgrade", None, None)]))

    def test_nonpositive_deltas_remain_visible_but_are_excluded_from_both_rankings(self):
        document = scenario()
        document["baseline"] = unit(197)
        document["candidates"] = [candidate("loss", unit(179), 3), candidate("equal", unit(197), None)]
        result = evaluate(document)
        self.assertEqual((result["ranking"], [(row["delta"], row["per_cost"], row["status"],
                                                row["eligible_for_ranking"], row["eligible_for_cost_ranking"])
                                               for row in result["candidates"]]),
                         ([], [(-18, -6, "not_upgrade", False, False), (0, None, "not_upgrade", False, False)]))

    def test_unrepresentable_price_quotients_fail_instead_of_ranking_zero_or_infinity(self):
        for amount, cost in ((1, 5e-324), (1e-300, 1e300)):
            with self.subTest(amount=amount, cost=cost):
                document = scenario()
                document["baseline"] = unit(0)
                document["candidates"] = [candidate("extreme-price", unit(amount), cost)]
                with self.assertRaisesRegex(ValueError, "Gain per cost"):
                    evaluate(document)

    def test_unrepresentable_relative_gain_fails_even_with_an_unknown_price(self):
        document = scenario()
        document["baseline"] = unit(5e-324)
        document["candidates"] = [candidate("huge-relative", unit(1), None)]
        with self.assertRaisesRegex(ValueError, "Relative gain"):
            evaluate(document)

    def test_new_topology_keeps_the_raw_spell_cap_per_caster(self):
        document = scenario()
        baseline = unit(100)
        baseline["spell"]["casting"]["interval"] = .025
        baseline["topology"].update(maximum=2)
        target = copy.deepcopy(baseline)
        target["topology"].update(extra=1, active=2)
        document.update(baseline=baseline, candidates=[candidate("two-casters", target, 7)])
        row = evaluate(document)["candidates"][0]
        self.assertEqual((row["result"]["spell"]["rate"]["effective"], row["dps"], row["delta"]), (30, 6000, 3000))

    def test_only_exact_comparator_and_candidate_shapes_are_accepted(self):
        for target, field, value in (("top", "format", "tli-raw-upgrade-scenario-v1"),
                                    ("top", "panel", {}), ("top", "currency", " tokens "),
                                    ("top", "candidates", {}), ("candidate", "id", ""),
                                    ("candidate", "name", 17), ("candidate", "missing", [""]),
                                    ("candidate", "market_verified", True)):
            with self.subTest(target=target, field=field):
                document = scenario()
                (document if target == "top" else document["candidates"][0])[field] = value
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_costs_require_finite_nonnegative_numbers_with_bool_excluded(self):
        for cost in (True, False, -3, float("inf"), float("nan"), "7", {}, 10 ** 1000):
            with self.subTest(cost=cost):
                document = scenario()
                document["candidates"][0]["cost"] = cost
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_duplicate_candidate_identities_fail_instead_of_overwriting_ranking_entries(self):
        document = scenario()
        document["candidates"][1]["id"] = document["candidates"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            evaluate(document)

    def test_missing_fields_and_nonobject_nested_scenarios_cannot_choose_defaults(self):
        for value in (None, [], {}, {"missing": None}, {"missing": [{}]}):
            with self.subTest(value=value):
                document = scenario()
                document["candidates"][0]["scenario"] = value
                with self.assertRaises(ValueError):
                    evaluate(document)
        for field in ("format", "baseline", "currency", "candidates"):
            with self.subTest(field=field):
                document = scenario()
                document.pop(field)
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_comparator_lists_and_text_have_explicit_input_bounds(self):
        for field in ("candidates", "missing", "name", "currency"):
            with self.subTest(field=field):
                document = scenario()
                if field == "candidates":
                    document[field] *= 501
                elif field == "missing":
                    document["candidates"][0][field] = ["gap"] * 1001
                else:
                    (document if field == "currency" else document["candidates"][0])[field] = "x" * 1025
                with self.assertRaisesRegex(ValueError, "bounded"):
                    evaluate(document)

    def test_reports_and_nested_scenarios_are_detached_from_the_caller_and_each_other(self):
        document = scenario()
        before = copy.deepcopy(document)
        result = evaluate(document)
        result["scenario"]["baseline"]["target"]["armor"] = 999
        result["scenario"]["candidates"][0]["scenario"]["spell"]["damage"]["base"]["min"] = 999
        result["candidates"][0]["result"]["scenario"]["gates"]["inheritance"]["evidence"].append("changed")
        self.assertEqual((document, result["baseline"]["scenario"]["target"]["armor"],
                          result["candidates"][0]["result"]["spell"]["scenario"]["damage"]["base"]["min"],
                          result["scenario"]["candidates"][0]["scenario"]["gates"]["inheritance"]["evidence"]),
                         (before, 100000, 200, ["synthetic:inheritance"]))

    def test_usable_results_remain_conditional_and_prices_belong_to_the_caller(self):
        result = evaluate(scenario())
        self.assertEqual((result["format"], result["status"], result["baseline"]["status"],
                          [row["result"]["status"] for row in result["candidates"]],
                          result["currency"], result["price_source"], result["quantity_scope"]),
                         ("tli-combat-upgrade-report-v1", "conditional", "conditional", ["conditional"] * 2,
                          "synthetic tokens", "caller", "conditional_combat_dps"))

    def test_errors_do_not_echo_private_payload_fields_or_end_in_a_period(self):
        outcomes = []
        for field in ("id", "unsupported"):
            document = scenario()
            if field == "id":
                for row in document["candidates"]:
                    row["id"] = "PRIVATE-PAYLOAD-MARKER"
            else:
                document["PRIVATE-PAYLOAD-MARKER"] = 17
            with self.assertRaises(ValueError) as caught:
                evaluate(document)
            outcomes.append(("PRIVATE-PAYLOAD-MARKER" in str(caught.exception),
                             str(caught.exception).endswith("."), "\n" in str(caught.exception)))
        self.assertEqual(outcomes, [(False, False, False)] * 2)

    def test_empty_candidates_are_a_valid_baseline_only_report(self):
        document = scenario()
        document["candidates"] = []
        result = evaluate(document)
        self.assertEqual((result["status"], result["candidates"], result["ranking"]), ("conditional", [], []))
