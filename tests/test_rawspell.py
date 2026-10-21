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


def modifier(identity, affix, value, scope=None):
    result = {"id": identity, "affix": affix, "value": value, "stacks": 1, "mode": "add"}
    if scope is not None:
        result["scope"] = scope
    return result


class RawSpellTests(unittest.TestCase):
    """Check a raw spell expectation without using a character panel."""

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
