import copy
import unittest

from damage_lab.rawcombat import evaluate
from test_rawspell import double


def scenario():
    """A fully declared synthetic spell and target with an independent 415.8 DPS oracle."""
    return {
        "format": "tli-raw-cold-combat-v1",
        "spell": {
            "format": "tli-raw-cold-spell-v1",
            "context": {"source_sha256": "c" * 64, "catalog_sha256": "d" * 64,
                        "skill_id": "synthetic-cold-spell", "effective_level": 13,
                        "gates": {name: {"status": "confirmed", "evidence": ["synthetic:" + name]}
                                  for name in ("version", "level", "base", "conversion")}},
            "damage": {"base": {"min": 100, "max": 100}, "physical": {"min": 0, "max": 0},
                       "cold": {"min": 0, "max": 0}, "effectiveness": 1,
                       "increased": {"all": 0, "physical": 0, "cold": 0}, "more": [], "roll_model": "midpoint"},
            "critical": {"chance": .25, "multiplier": 3, "lucky": False, "more": 0},
            "casting": {"interval": .5, "increased": 0, "more": [], "frequency": None},
            "missing": [], "notes": ["Synthetic complete spell pools"]},
        "topology": {"maximum": 3, "extra": 1, "active": 3, "hits": 3, "retention": .25},
        "target": {"cold_resistance": .4, "cold_penetration": .1, "armor": 0,
                   "armor_effectiveness": 1, "armor_penetration": 0,
                   "armor_penetration_order": "after_effectiveness", "increased_taken": .2,
                   "more_taken": [{"id": "target-more", "affix": "exposure", "value": .1,
                                   "stacks": 1, "mode": "add"}]},
        "uptime": .5,
        "gates": {name: {"status": "confirmed", "evidence": ["synthetic:" + name]}
                  for name in ("inheritance", "hit_topology", "target_state")},
        "missing": [], "notes": ["Synthetic topology and target assertions"],
    }


class RawCombatTests(unittest.TestCase):
    """Compose declared spell stages once while keeping unknown combat evidence blocked."""

    def test_joint_spell_expectation_is_applied_once_before_combat_factors(self):
        document = scenario()
        document["spell"] = double()
        result = evaluate(document)
        self.assertAlmostEqual(result["dps"], 173.25)

    def test_unknown_double_damage_blocks_combat_without_replacing_it_by_zero(self):
        document = scenario()
        document["spell"] = double()
        document["spell"]["double_damage"] = None
        result = evaluate(document)
        self.assertEqual((result["dps"], result["gaps"]), (None, ["spell: double_damage: unavailable"]))

    def test_complete_spell_topology_and_target_match_the_independent_oracle(self):
        self.assertAlmostEqual(evaluate(scenario())["dps"], 415.8)

    def test_unknown_or_conflicting_combat_gates_leave_downstream_numbers_null(self):
        outcomes = []
        for name in ("inheritance", "hit_topology", "target_state"):
            for status in ("unknown", "conflict"):
                document = scenario()
                document["gates"][name]["status"] = status
                report = evaluate(document)
                outcomes.append((report["status"], report["dps"], report["topology"], report["factors"],
                                 report["armor_mitigation"], report["trace"], f"{name}: {status}" in report["gaps"]))
        self.assertEqual(outcomes, [("blocked", None, None, None, None, [], True)] * 6)

    def test_missing_effect_coverage_blocks_the_combat_total(self):
        document = scenario()
        document["missing"] = ["unresolved inheritance modifier"]
        result = evaluate(document)
        self.assertEqual((result["status"], result["dps"], result["gaps"]),
                         ("blocked", None, ["unresolved inheritance modifier"]))

    def test_panel_reference_and_other_unsupported_fields_are_rejected(self):
        for field in ("panel", "reference", "benchmark", "heat", "cast_rate", "critical_more"):
            with self.subTest(field=field):
                document = scenario()
                document[field] = "PRIVATE-INPUT-MARKER"
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_required_fields_cannot_be_omitted_or_extended_in_nested_objects(self):
        for name in ("topology", "target"):
            for change in ("missing", "extra"):
                with self.subTest(name=name, change=change):
                    document = scenario()
                    if change == "missing":
                        document[name].pop(next(iter(document[name])))
                    else:
                        document[name]["PRIVATE-INPUT-MARKER"] = 17
                    with self.assertRaises(ValueError):
                        evaluate(document)

    def test_invalid_numeric_types_are_rejected_even_when_a_combat_gate_is_unknown(self):
        cases = (("topology", "maximum", True), ("topology", "extra", 1.0),
                 ("topology", "active", False), ("topology", "hits", 3.0),
                 ("target", "cold_resistance", True), ("target", "cold_penetration", None),
                 ("target", "armor", "PRIVATE-INPUT-MARKER"),
                 ("target", "increased_taken", float("nan")), (None, "uptime", True))
        for name, field, value in cases:
            with self.subTest(name=name, field=field):
                document = scenario()
                document["gates"]["inheritance"]["status"] = "unknown"
                (document if name is None else document[name])[field] = value
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_target_more_requires_complete_strict_rows_without_damage_scope(self):
        variants = [None, {}, [None]]
        for field, value in (("scope", "all"), ("value", True), ("stacks", 1001), ("id", " ")):
            row = copy.deepcopy(scenario()["target"]["more_taken"][0])
            row[field] = value
            variants.append([row])
        for rows in variants:
            with self.subTest(rows=rows):
                document = scenario()
                document["target"]["more_taken"] = rows
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_a_positive_target_more_product_cannot_underflow_to_zero(self):
        document = scenario()
        document["target"]["more_taken"] = [{"id": "tiny", "affix": "tiny", "value": -.9,
                                             "stacks": 400, "mode": "multiply"}]
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_a_positive_combat_stage_cannot_underflow_to_zero(self):
        document = scenario()
        document["spell"]["damage"]["base"] = {"min": 5e-324, "max": 5e-324}
        document["spell"]["critical"].update(chance=0, multiplier=1)
        document["spell"]["casting"]["interval"] = 1
        document["topology"].update(maximum=1, extra=0, active=1, hits=1)
        document["target"].update(cold_resistance=.5, cold_penetration=0, increased_taken=0, more_taken=[])
        document["uptime"] = 1
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_finite_spell_and_target_factors_cannot_overflow_the_combat_total(self):
        document = scenario()
        document["spell"]["damage"]["more"] = [{"id": "raw", "affix": "raw", "scope": "all",
                                                 "value": 1e6, "stacks": 47, "mode": "multiply"}]
        document["target"]["more_taken"][0].update(value=1e6, stacks=5, mode="multiply")
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_three_casters_keep_ninety_aggregate_casts_without_a_global_cap(self):
        document = scenario()
        document["spell"]["critical"].update(chance=0, multiplier=1)
        document["spell"]["casting"]["interval"] = .025
        document["topology"].update(maximum=4, extra=2, active=3, hits=1, retention=1)
        document["target"].update(cold_resistance=0, cold_penetration=0, increased_taken=0, more_taken=[])
        document["uptime"] = 1
        result = evaluate(document)
        self.assertEqual((result["spell"]["rate"]["effective"], result["topology"]["attached"], result["dps"]),
                         (30, 3, 9000))

    def test_trace_stages_apply_the_existing_spell_expectation_once(self):
        result = evaluate(scenario())
        self.assertEqual((result["spell"]["expected_hit"], result["trace"][0]["input"],
                          [round(row["output"], 6) for row in result["trace"]]),
                         (150, 300, [900, 630, 630, 756, 831.6, 415.8]))

    def test_explicit_armor_orders_replace_legacy_nonphysical_effectiveness(self):
        outcomes = []
        for order in ("after_effectiveness", "before_effectiveness"):
            document = scenario()
            document["target"].update(armor=100000, armor_effectiveness=.5, armor_penetration=.1,
                                      armor_penetration_order=order)
            outcomes.append(round(evaluate(document)["dps"], 6))
        self.assertEqual(outcomes, [291.06, 270.27])

    def test_negative_armor_mitigation_is_not_clamped_away(self):
        document = scenario()
        document["target"]["armor_penetration"] = .2
        self.assertAlmostEqual(evaluate(document)["dps"], 498.96)

    def test_target_more_rows_use_their_explicit_affix_pool_identity(self):
        outcomes = []
        for affix in ("exposure", "different"):
            document = scenario()
            document["target"]["more_taken"].append(
                {"id": "second", "affix": affix, "value": .2, "stacks": 1, "mode": "add"})
            outcomes.append(round(evaluate(document)["dps"], 6))
        self.assertEqual(outcomes, [491.4, 498.96])

    def test_blocked_spell_stays_nested_and_does_not_produce_a_combat_trace(self):
        document = scenario()
        document["spell"]["context"]["gates"]["version"]["status"] = "unknown"
        result = evaluate(document)
        self.assertEqual((result["status"], result["dps"], result["trace"], result["spell"]["status"],
                          result["spell"]["pre_defence_dps"], result["gaps"]),
                         ("blocked", None, [], "blocked", None, ["spell: version: unknown"]))

    def test_explicit_zero_combat_factors_remain_valid_conditional_zero(self):
        changes = (("topology", "active", 0), ("topology", "hits", 0),
                   ("target", "increased_taken", -1), (None, "uptime", 0))
        outcomes = []
        for name, field, value in changes:
            document = scenario()
            (document if name is None else document[name])[field] = value
            result = evaluate(document)
            outcomes.append((result["status"], result["dps"]))
        document = scenario()
        document["target"]["more_taken"][0]["value"] = -1
        result = evaluate(document)
        outcomes.append((result["status"], result["dps"]))
        self.assertEqual(outcomes, [("conditional", 0)] * 5)

    def test_confirmed_combat_gates_require_nonempty_evidence(self):
        document = scenario()
        document["gates"]["target_state"]["evidence"] = []
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_invalid_target_still_raises_when_the_source_spell_is_blocked(self):
        document = scenario()
        document["spell"]["missing"] = ["unmapped source effect"]
        document["target"]["armor_effectiveness"] = None
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_input_and_both_nested_scenario_copies_are_detached(self):
        document = scenario()
        original = copy.deepcopy(document)
        first = evaluate(document)
        first["scenario"]["gates"]["inheritance"]["evidence"].append("changed")
        first["spell"]["scenario"]["context"]["gates"]["base"]["evidence"].append("changed")
        second = evaluate(document)
        self.assertEqual((document, second["scenario"], second["spell"]["scenario"]),
                         (original, original, original["spell"]))

    def test_errors_cannot_echo_private_field_names_or_modifier_identities(self):
        outcomes = []
        for change in ("field", "duplicate"):
            document = scenario()
            if change == "field":
                document["target"]["PRIVATE-INPUT-MARKER"] = 1
            else:
                document["target"]["more_taken"][0]["id"] = "PRIVATE-INPUT-MARKER"
                document["target"]["more_taken"].append(copy.deepcopy(document["target"]["more_taken"][0]))
            with self.assertRaises(ValueError) as caught:
                evaluate(document)
            outcomes.append(("PRIVATE-INPUT-MARKER" in str(caught.exception), str(caught.exception).endswith("."),
                             "\n" in str(caught.exception)))
        self.assertEqual(outcomes, [(False, False, False)] * 2)

    def test_supported_numeric_bounds_reject_outside_values_and_nonfinite_inputs(self):
        cases = (("topology", "maximum", 5), ("topology", "extra", -1), ("topology", "hits", 1001),
                 ("topology", "retention", 1.01), ("target", "cold_resistance", -10.1),
                 ("target", "cold_penetration", 10.1), ("target", "armor", -1),
                 ("target", "armor", float("inf")), ("target", "armor", 10 ** 1000),
                 ("target", "armor_effectiveness", 1.1), ("target", "armor_penetration", -.1),
                 ("target", "increased_taken", 101), (None, "uptime", -.1))
        for name, field, value in cases:
            with self.subTest(name=name, field=field):
                document = scenario()
                (document if name is None else document[name])[field] = value
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_all_explicit_armor_fields_are_mandatory_and_never_select_legacy_defaults(self):
        for field in ("armor_effectiveness", "armor_penetration", "armor_penetration_order"):
            with self.subTest(field=field):
                document = scenario()
                document["target"][field] = None
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_armor_accepts_finite_values_without_an_invented_upper_game_cap(self):
        document = scenario()
        document["target"]["armor"] = 1.7976931348623157e308
        self.assertAlmostEqual(evaluate(document)["dps"], 83.16)

    def test_raw_spell_tick_hypothesis_is_not_applied_twice(self):
        document = scenario()
        document["spell"]["casting"].update(interval=.19, increased=.3, frequency=30)
        result = evaluate(document)
        self.assertAlmostEqual(result["dps"], 1247.4)

    def test_explicit_cold_immunity_without_penetration_gives_conditional_zero(self):
        document = scenario()
        document["target"].update(cold_resistance=1, cold_penetration=0)
        self.assertEqual(evaluate(document)["dps"], 0)

    def test_bad_gate_shapes_status_and_text_lists_fail_without_input_echo(self):
        for field, value in (("status", "PRIVATE-INPUT-MARKER"), ("evidence", "PRIVATE-INPUT-MARKER"),
                             ("evidence", [" "]), ("evidence", ["x" * 1025])):
            with self.subTest(field=field):
                document = scenario()
                document["gates"]["target_state"][field] = value
                with self.assertRaises(ValueError) as caught:
                    evaluate(document)
                self.assertNotIn("PRIVATE-INPUT-MARKER", str(caught.exception))

    def test_wrong_formats_or_missing_top_level_fields_cannot_choose_defaults(self):
        for field in scenario():
            with self.subTest(field=field):
                document = scenario()
                document.pop(field)
                with self.assertRaises(ValueError):
                    evaluate(document)
        document = scenario()
        document["format"] = "other"
        with self.assertRaises(ValueError):
            evaluate(document)

    def test_nonscalar_formats_raise_value_error(self):
        # Spec 1: invalid format shapes stay ValueError, matching the v1 contract
        for value in ([], {}):
            with self.subTest(value=value):
                document = scenario()
                document["format"] = value
                with self.assertRaisesRegex(ValueError, "Unsupported raw combat format"):
                    evaluate(document)

    def test_target_modifier_collections_are_bounded(self):
        document = scenario()
        document["target"]["more_taken"] = document["target"]["more_taken"] * 1001
        with self.assertRaises(ValueError):
            evaluate(document)

    def _neutral(self, base):
        # Spec 3: 100 DPS, maximum 4, active 4, extra 1, hits 1, retention 1
        document = scenario()
        document["format"] = "tli-raw-cold-combat-v2"
        document["spell"]["critical"].update(chance=0, multiplier=1)
        document["spell"]["casting"]["interval"] = 1
        document["topology"] = {"maximum": 4, "extra": 1, "active": 4, "hits": 1, "retention": 1, "base": base}
        document["target"].update(cold_resistance=0, cold_penetration=0, armor=0, armor_effectiveness=1,
                                  armor_penetration=0, increased_taken=0, more_taken=[])
        document["uptime"] = 1
        return document

    def test_known_v2_base_sets_attached_count_without_changing_v1_shape(self):
        # Spec 2 and 3
        self.assertEqual(evaluate(self._neutral(1))["dps"], 200)
        self.assertEqual(evaluate(self._neutral(2))["topology"]["base"], 2)
        self.assertEqual(evaluate(self._neutral(2))["dps"], 300)
        self.assertEqual(evaluate(self._neutral(0))["dps"], 100)
        legacy = scenario()
        self.assertEqual(set(evaluate(legacy)["topology"]), {"attached", "shotgun", "factor"})

    def test_null_base_blocks_without_a_substitute_and_rejects_a_confirmed_gate(self):
        # Spec 4
        unknown = self._neutral(None)
        unknown["gates"]["hit_topology"] = {"status": "unknown", "evidence": []}
        blocked = evaluate(unknown)
        self.assertIsNone(blocked["dps"])
        self.assertIsNone(blocked["topology"])
        self.assertIn("topology.base: unavailable", blocked["gaps"])
        confirmed = self._neutral(None)
        with self.assertRaisesRegex(ValueError, "unknown base"):
            evaluate(confirmed)
        invalid = self._neutral(None)
        invalid["topology"]["active"] = 5
        invalid["gates"]["hit_topology"] = {"status": "unknown", "evidence": []}
        with self.assertRaisesRegex(ValueError, "exceed"):
            evaluate(invalid)
        for bad in (True, 1.5, -1, 1001):
            with self.assertRaises(ValueError):
                evaluate(self._neutral(bad))
        missing = self._neutral(1)
        missing["topology"].pop("base")
        with self.assertRaises(ValueError):
            evaluate(missing)

    def test_null_base_still_rejects_invalid_more_taken(self):
        # Spec 4: invalid siblings are rejected before a blocked report
        document = self._neutral(None)
        document["gates"]["hit_topology"] = {"status": "unknown", "evidence": []}
        document["target"]["more_taken"] = [{"id": "x"}]
        with self.assertRaises(ValueError):
            evaluate(document)
        conflict = self._neutral(None)
        conflict["gates"]["hit_topology"] = {"status": "conflict", "evidence": []}
        blocked = evaluate(conflict)
        self.assertIsNone(blocked["dps"])
        self.assertIn("topology.base: unavailable", blocked["gaps"])
        sibling = self._neutral(None)
        sibling["gates"]["hit_topology"] = {"status": "unknown", "evidence": []}
        sibling["topology"]["extra"] = -1
        with self.assertRaises(ValueError):
            evaluate(sibling)
