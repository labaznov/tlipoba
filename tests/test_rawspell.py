import copy
import unittest

from damage_lab.rawspell import evaluate


def scenario():
    return {
        "format": "tli-raw-cold-spell-v1",
        "context": {"source_sha256": "a" * 64, "catalog_sha256": "b" * 64,
                    "skill_id": "synthetic-spell", "effective_level": 17,
                    "gates": {name: {"status": "confirmed", "evidence": ["synthetic:" + name]}
                              for name in ("version", "level", "base", "conversion")}},
        "damage": {"base": {"min": 103, "max": 137},
                   "physical": {"min": 7, "max": 11}, "cold": {"min": 13, "max": 19},
                   "effectiveness": 1.3, "increased": {"all": .2, "physical": .3, "cold": .4},
                   "more": [], "roll_model": "midpoint"},
        "critical": {"chance": .25, "multiplier": 3, "lucky": False, "more": .2},
        "casting": {"interval": .8, "increased": .6, "more": [], "frequency": None},
        "missing": [], "notes": ["All inputs are synthetic scenario assertions"],
    }


def double():
    """Declare a synthetic constant hit with branch-conditional Double Damage."""
    document = scenario()
    document["format"] = "tli-raw-cold-spell-v2"
    document["damage"].update(base={"min": 100, "max": 100}, physical={"min": 0, "max": 0},
                              cold={"min": 0, "max": 0}, effectiveness=1,
                              increased={"all": 0, "physical": 0, "cold": 0})
    document["critical"].update(chance=0, multiplier=1, more=0)
    document["casting"].update(interval=1, increased=0)
    document["double_damage"] = {"noncritical": .25, "critical": 0, "mean_model": "shared_midpoint",
                                 "gate": {"status": "confirmed", "evidence": ["synthetic:joint-law"]}}
    return document


def modifier(identity, affix, value, scope=None):
    result = {"id": identity, "affix": affix, "value": value, "stacks": 1, "mode": "add"}
    if scope is not None:
        result["scope"] = scope
    return result


def subnormal():
    """Return a complete fictional scenario at the smallest positive float boundary."""
    document = scenario()
    document["damage"].update(base={"min": 5e-324, "max": 5e-324}, physical={"min": 0, "max": 0},
                              cold={"min": 0, "max": 0}, effectiveness=1,
                              increased={"all": 0, "physical": 0, "cold": 0})
    document["critical"].update(chance=0, multiplier=1, more=0)
    document["casting"].update(interval=1, increased=0)
    return document


class RawSpellTests(unittest.TestCase):
    """Check a raw spell expectation without using a character panel."""

    def test_explicit_double_damage_expectation_is_an_optin_scenario(self):
        document = double()
        self.assertEqual(evaluate(document)["pre_defence_dps"], 125)

    def test_joint_branches_keep_critical_lucky_and_more_once(self):
        outcomes = []
        for lucky, more in ((False, 0), (True, 0), (False, 1)):
            document = double()
            document["critical"].update(chance=.5, multiplier=3, lucky=lucky, more=more)
            document["double_damage"].update(noncritical=0, critical=1)
            report = evaluate(document)
            outcomes.append((report["expected_hit"], report["critical_factor"]))
        self.assertEqual(outcomes, [(350, 2), (475, 2.5), (650, 3.5)])

    def test_double_damage_boundaries_and_zero_critical_factor_do_not_divide(self):
        outcomes = []
        for chance in (0, 1):
            document = double()
            document["double_damage"]["noncritical"] = chance
            outcomes.append(evaluate(document)["pre_defence_dps"])
        document["critical"].update(chance=1, multiplier=0)
        outcomes.append(evaluate(document)["pre_defence_dps"])
        self.assertEqual(outcomes, [100, 200, 0])

    def test_unknown_double_damage_blocks_without_inventing_zero(self):
        outcomes = []
        for status in (None, "unknown", "conflict"):
            document = double()
            if status is None:
                document["double_damage"] = None
            else:
                document["double_damage"]["gate"]["status"] = status
            result = evaluate(document)
            outcomes.append((result["format"], result["status"], result["pre_defence_dps"], result["gaps"]))
        self.assertEqual(outcomes, [("tli-raw-cold-spell-report-v2", "blocked", None,
                                    ["double_damage: " + status])
                                   for status in ("unavailable", "unknown", "conflict")])

    def test_double_damage_validates_all_fields_and_supplied_siblings_before_blocking(self):
        for field, value in (("noncritical", True), ("critical", -1), ("noncritical", float("nan")),
                             ("critical", 1.01), ("mean_model", "independent"), ("extra", 1),
                             ("gate", {"status": "confirmed", "evidence": []})):
            document = double()
            document["damage"] = None
            document["double_damage"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                evaluate(document)
        document = double()
        document["double_damage"] = None
        document["casting"]["interval"] = 0
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_each_explicitly_unavailable_group_blocks_even_with_confirmed_context_gates(self):
        for name in ("damage", "critical", "casting"):
            with self.subTest(name=name):
                document = scenario()
                document[name] = None
                result = evaluate(document)
                self.assertEqual((result["status"], result["pre_defence_dps"], result["trace"], result["gaps"],
                                  result["scenario"][name]), ("blocked", None, [], [name + ": unavailable"], None))

    def test_all_unavailable_groups_preserve_unknown_context_without_creating_zero_inputs(self):
        document = scenario()
        document.update(damage=None, critical=None, casting=None)
        document["context"]["effective_level"] = None
        document["context"]["gates"]["level"] = {"status": "unknown", "evidence": []}
        document["missing"] = ["incomplete source pools"]
        result = evaluate(document)
        self.assertEqual((result["gaps"], result["scenario"], set(result)),
            (["level: unknown", "incomplete source pools", "damage: unavailable", "critical: unavailable", "casting: unavailable"],
             document, {"format", "status", "pre_defence_dps", "gaps", "scenario", "trace", "assumptions"}))

    def test_nonnull_sibling_groups_are_fully_validated_before_an_unavailable_group_can_return(self):
        for absent, present, field, invalid in (("damage", "critical", "chance", True),
                                               ("critical", "casting", "interval", 0),
                                               ("casting", "damage", "effectiveness", float("nan"))):
            with self.subTest(absent=absent, present=present):
                document = scenario()
                document[absent] = None
                document[present][field] = invalid
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_empty_or_invalid_groups_are_not_treated_as_explicitly_unavailable(self):
        for name in ("damage", "critical", "casting"):
            for invalid in ({}, [], True, False, "unknown", 0):
                with self.subTest(name=name, invalid=invalid):
                    document = scenario()
                    document[name] = invalid
                    document["missing"] = ["blocked by another source gap"]
                    with self.assertRaises(ValueError):
                        evaluate(document)

    def test_unavailable_groups_do_not_make_context_missing_or_notes_validation_optional(self):
        for change in ("hash", "level", "gate", "notes", "missing"):
            with self.subTest(change=change):
                document = scenario()
                document.update(damage=None, critical=None, casting=None)
                if change == "hash":
                    document["context"]["source_sha256"] = "PRIVATE-RAW-CANARY"
                elif change == "level":
                    document["context"]["effective_level"] = None
                elif change == "gate":
                    document["context"]["gates"]["version"]["evidence"] = []
                else:
                    document[change] = None
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_explicit_unknown_does_not_supply_an_absent_group_field(self):
        for name in ("damage", "critical", "casting"):
            with self.subTest(name=name):
                document = scenario()
                document.update(damage=None, critical=None, casting=None)
                del document[name]
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_unavailable_groups_do_not_hide_invalid_modifier_rows_in_a_supplied_group(self):
        for name, scope in (("damage", "all"), ("casting", None)):
            with self.subTest(name=name):
                document = scenario()
                document["critical"] = None
                document[name]["more"] = [modifier("duplicate", "same", .2, scope), modifier("duplicate", "same", .3, scope)]
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_blocked_group_scenarios_remain_detached_without_mutating_supplied_siblings(self):
        document = scenario()
        document["damage"] = None
        original = copy.deepcopy(document)
        result = evaluate(document)
        result["scenario"]["casting"]["more"].append(modifier("later", "later", .2))
        result["scenario"]["notes"].append("changed")
        result["gaps"].append("changed")
        self.assertEqual((document, result["scenario"]["damage"]), (original, None))

    def test_an_unresolved_level_can_remain_null_while_numeric_damage_is_blocked(self):
        for status in ("unknown", "conflict"):
            with self.subTest(status=status):
                document = scenario()
                document["context"]["effective_level"] = None
                document["context"]["gates"]["level"] = {"status": status, "evidence": []}
                result = evaluate(document)
                self.assertEqual((result["status"], result["pre_defence_dps"], result["gaps"], result["trace"],
                                  result["scenario"]["context"]["effective_level"]),
                                 ("blocked", None, ["level: " + status], [], None))

    def test_a_confirmed_level_cannot_be_null_even_when_another_gate_is_unknown(self):
        for name in ("version", "base", "conversion"):
            with self.subTest(name=name):
                document = scenario()
                document["context"]["effective_level"] = None
                document["context"]["gates"][name]["status"] = "unknown"
                with self.assertRaisesRegex(ValueError, "Effective skill level"):
                    evaluate(document)

    def test_supplied_levels_still_require_strict_integers_with_every_gate_status(self):
        for status in ("confirmed", "unknown", "conflict"):
            for level in (True, False, 0, -3, 1001, 17.0, "17", {}, []):
                with self.subTest(status=status, level=level):
                    document = scenario()
                    document["context"]["effective_level"] = level
                    document["context"]["gates"]["level"]["status"] = status
                    with self.assertRaisesRegex(ValueError, "Effective skill level"):
                        evaluate(document)

    def test_confirmed_integer_boundary_levels_remain_supported(self):
        outcomes = []
        for level in (1, 1000):
            document = scenario()
            document["context"]["effective_level"] = level
            result = evaluate(document)
            outcomes.append((result["status"], result["scenario"]["context"]["effective_level"],
                             round(result["pre_defence_dps"], 6)))
        self.assertEqual(outcomes, [("conditional", 1, 935.583), ("conditional", 1000, 935.583)])

    def test_unknown_level_does_not_supply_a_missing_effective_level_field(self):
        document = scenario()
        del document["context"]["effective_level"]
        document["context"]["gates"]["level"]["status"] = "unknown"
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_null_level_does_not_bypass_other_gate_and_damage_validation(self):
        for change in ("gate", "damage", "hash"):
            with self.subTest(change=change):
                document = scenario()
                document["context"]["effective_level"] = None
                document["context"]["gates"]["level"]["status"] = "unknown"
                if change == "gate":
                    document["context"]["gates"]["conversion"]["evidence"] = []
                elif change == "damage":
                    document["damage"]["base"]["min"] = True
                else:
                    document["context"]["source_sha256"] = "invalid"
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_null_level_blocked_scenarios_are_detached_from_the_caller(self):
        document = scenario()
        document["context"]["effective_level"] = None
        document["context"]["gates"]["level"]["status"] = "conflict"
        original = copy.deepcopy(document)
        result = evaluate(document)
        result["scenario"]["context"]["effective_level"] = 29
        result["scenario"]["context"]["gates"]["level"]["evidence"].append("changed")
        result["gaps"].append("changed")
        self.assertEqual(document, original)

    def test_positive_expected_hit_cannot_underflow_to_zero(self):
        document = subnormal()
        document["critical"].update(chance=1, multiplier=.5)
        with self.assertRaisesRegex(ValueError, "underflow"):
            evaluate(document)

    def test_positive_pre_defence_damage_cannot_underflow_to_zero(self):
        document = subnormal()
        document["casting"]["interval"] = 2
        with self.assertRaisesRegex(ValueError, "underflow"):
            evaluate(document)

    def test_positive_cast_rate_cannot_underflow_to_zero(self):
        document = scenario()
        document["casting"].update(interval=1e6, increased=-.9999999999999999,
                                   more=[{"id": "tiny", "affix": "slow", "value": -.9, "stacks": 320, "mode": "multiply"}])
        with self.assertRaisesRegex(ValueError, "underflow"):
            evaluate(document)

    def test_positive_midpoint_cannot_underflow_to_zero(self):
        document = subnormal()
        document["damage"]["base"]["min"] = 0
        with self.assertRaisesRegex(ValueError, "underflow"):
            evaluate(document)

    def test_positive_midpoint_spread_cannot_underflow_before_adding_the_minimum(self):
        document = subnormal()
        document["damage"]["base"]["max"] = 1e-323
        with self.assertRaisesRegex(ValueError, "underflow"):
            evaluate(document)

    def test_physical_conversion_and_native_cold_have_separate_increased_scopes(self):
        self.assertAlmostEqual(evaluate(scenario())["noncritical"]["mean"], 283.51)

    def test_critical_expectation_and_cast_rate_produce_pre_defence_damage(self):
        self.assertAlmostEqual(evaluate(scenario())["pre_defence_dps"], 935.583)

    def test_same_affix_is_pooled_across_conversion_scopes(self):
        document = scenario()
        document["damage"]["more"] = [modifier("one", "shared", .2, "physical"),
                                        modifier("two", "shared", .3, "cold")]
        self.assertAlmostEqual(evaluate(document)["noncritical"]["mean"], 418.609)

    def test_lucky_changes_critical_probability_without_changing_damage_rolls(self):
        document = scenario()
        document["critical"]["lucky"] = True
        self.assertAlmostEqual(evaluate(document)["critical_factor"], 2.1375)

    def test_lucky_cannot_lower_the_expected_hit_for_a_tiny_positive_critical_chance(self):
        document = scenario()
        document["critical"].update(chance=1e-17, multiplier=100, more=100)
        baseline = evaluate(document)["expected_hit"]
        document["critical"]["lucky"] = True
        self.assertGreater(evaluate(document)["expected_hit"], baseline)

    def test_cast_speed_uses_base_interval_and_complete_additional_pool(self):
        document = scenario()
        document["casting"]["more"] = [modifier("first", "speed", .2), modifier("second", "speed", .3)]
        self.assertAlmostEqual(evaluate(document)["rate"]["smooth"], 3)

    def test_tick_rounding_is_an_explicit_separate_hypothesis(self):
        document = scenario()
        document["casting"].update(interval=.19, increased=.3, frequency=30)
        self.assertEqual(evaluate(document)["rate"]["effective"], 6)

    def test_continuous_rate_is_capped_per_caster(self):
        document = scenario()
        document["casting"]["interval"] = .01
        self.assertEqual(evaluate(document)["rate"]["effective"], 30)

    def test_unconfirmed_gate_blocks_numeric_dps(self):
        for status in ("unknown", "conflict"):
            with self.subTest(status=status):
                document = scenario()
                document["context"]["gates"]["version"]["status"] = status
                self.assertEqual((evaluate(document)["status"], evaluate(document)["pre_defence_dps"]),
                                 ("blocked", None))

    def test_missing_effect_blocks_numeric_dps(self):
        document = scenario()
        document["missing"] = ["unmapped flat modifier"]
        self.assertEqual(evaluate(document)["gaps"], ["unmapped flat modifier"])

    def test_confirmed_gate_requires_an_evidence_reference(self):
        document = scenario()
        document["context"]["gates"]["base"]["evidence"] = []
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_panel_or_topology_overrides_cannot_enter_raw_spell_model(self):
        for field in ("panel", "benchmark", "active", "hits", "retention"):
            with self.subTest(field=field):
                document = scenario()
                document[field] = 17
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_invalid_ranges_and_numbers_are_rejected_even_when_a_gate_is_unknown(self):
        for value in (True, float("nan"), float("inf"), -7, "103"):
            with self.subTest(value=value):
                document = scenario()
                document["context"]["gates"]["base"]["status"] = "unknown"
                document["damage"]["base"]["min"] = value
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_unordered_damage_range_is_rejected(self):
        document = scenario()
        document["damage"]["cold"] = {"min": 23, "max": 19}
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_other_roll_models_are_not_silently_reduced_to_midpoint(self):
        document = scenario()
        document["damage"]["roll_model"] = "lucky_damage"
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_boolean_damage_and_speed_modifiers_are_rejected(self):
        for domain, scope in (("damage", "all"), ("casting", None)):
            with self.subTest(domain=domain):
                document = scenario()
                document[domain]["more"] = [modifier("one", "shared", True, scope)]
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_result_and_trace_are_detached_from_the_input(self):
        document = scenario()
        expected = copy.deepcopy(document)
        result = evaluate(document)
        result["scenario"]["context"]["gates"]["base"]["evidence"].append("changed")
        self.assertEqual(document, expected)

    def test_zero_cast_factor_has_zero_dps_without_division_by_zero(self):
        document = scenario()
        document["casting"]["increased"] = -1
        self.assertEqual(evaluate(document)["pre_defence_dps"], 0)

    def test_tiny_interval_cannot_overflow_the_raw_rate(self):
        document = scenario()
        document["casting"]["interval"] = 1e-320
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_equal_subnormal_endpoints_keep_their_representable_midpoint(self):
        document = scenario()
        document["damage"].update(base={"min": 5e-324, "max": 5e-324},
                                  physical={"min": 0, "max": 0}, cold={"min": 0, "max": 0},
                                  effectiveness=1, increased={"all": 0, "physical": 0, "cold": 0})
        document["critical"].update(chance=0, multiplier=1, more=0)
        document["casting"].update(interval=1, increased=0)
        self.assertEqual(evaluate(document)["pre_defence_dps"], 5e-324)
