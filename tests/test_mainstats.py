import copy
import unittest

from damage_lab.mainstats import evaluate


def scenario(attributes, eligible, per_point):
    return {
        "format": "tli-main-stat-scenario-v1",
        "context": {"source_sha256": "c" * 64, "catalog_sha256": "d" * 64,
                    "skill_id": "synthetic-mixed-main-stat"},
        "attributes": attributes,
        "eligible": eligible,
        "per_point": per_point,
        "ratio": {"selection": "none", "evidence": ["synthetic:no-ratio-modifiers"]},
        "gates": {name: {"status": "confirmed", "evidence": ["synthetic:" + name]}
                  for name in ("patch", "main_stat_binding", "activation")},
    }


class MainStatTests(unittest.TestCase):
    """Check explicit baseline main-stat arithmetic without a character panel."""

    def test_matching_final_totals_add_before_the_single_factor(self):
        document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                            ["strength", "intelligence"], .0037)
        self.assertAlmostEqual(evaluate(document)["factor"], 2.036)

    def test_unconfirmed_evidence_blocks_both_numeric_outputs(self):
        document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                            ["strength", "intelligence"], .0037)
        document["gates"]["activation"]["status"] = "unknown"
        result = evaluate(document)
        self.assertEqual((result["status"], result["bonus"], result["factor"], result["gaps"]),
                         ("blocked", None, None, ["activation: unknown"]))

    def test_unknown_selected_total_stays_unknown_even_with_a_zero_rate(self):
        document = scenario({"strength": None, "dexterity": 0, "intelligence": 197},
                            ["strength"], 0)
        result = evaluate(document)
        self.assertEqual((result["bonus"], result["factor"], result["gaps"]),
                         (None, None, ["strength: final total unknown"]))

    def test_missing_or_unsupported_structure_is_a_controlled_error(self):
        original = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                            ["strength"], .0037)
        documents = [None, [], {}, {**original, "panel": 283}, {**original, "format": "other"}]
        for field in original:
            document = copy.deepcopy(original)
            del document[field]
            documents.append(document)
        for field in ("context", "attributes", "ratio", "gates"):
            documents.append({**original, field: []})
            documents.append({**original, field: {**original[field], "extra": "unsupported"}})
            for name in original[field]:
                document = copy.deepcopy(original)
                del document[field][name]
                documents.append(document)
        for document in documents:
            with self.subTest(document=document):
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_invalid_numeric_inputs_are_rejected_even_when_the_result_is_blocked(self):
        for field in ("strength", "dexterity", "intelligence", "per_point"):
            for value in (True, False, -13, float("nan"), float("inf"), -float("inf"), "19", [], 10 ** 400):
                with self.subTest(field=field, value=value):
                    document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                                        ["strength"], .0037)
                    document["gates"]["patch"]["status"] = "unknown"
                    if field == "per_point":
                        document[field] = value
                    else:
                        document["attributes"][field] = value
                    with self.assertRaises(ValueError):
                        evaluate(document)

    def test_eligibility_accepts_only_a_distinct_list_of_main_attribute_names(self):
        for eligible in (None, "strength", {}, ["strength", "strength"], ["cold"], ["spell"],
                         ["Strength"], [True], [[]], ["strength", "dexterity", "intelligence", "other"]):
            with self.subTest(eligible=eligible):
                document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                                    eligible, .0037)
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_context_requires_exact_hashes_and_an_explicit_skill_identity(self):
        for field, values in (("source_sha256", (None, True, "A" * 64, "c" * 63, "g" * 64)),
                              ("catalog_sha256", (None, [], "D" * 64, "d" * 65, "d" * 63 + "\n")),
                              ("skill_id", (None, True, [], "", " skill", "skill ", "x" * 1025))):
            for value in values:
                with self.subTest(field=field, value=value):
                    document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                                        ["strength"], .0037)
                    document["context"][field] = value
                    with self.assertRaises(ValueError):
                        evaluate(document)

    def test_each_confirmed_gate_requires_well_formed_evidence(self):
        for name in ("patch", "main_stat_binding", "activation"):
            for gate in (None, [], {}, {"status": "verified", "evidence": ["synthetic"]},
                         {"status": None, "evidence": ["synthetic"]},
                         {"status": "confirmed", "evidence": []},
                         {"status": "confirmed", "evidence": "synthetic"},
                         {"status": "confirmed", "evidence": [None]},
                         {"status": "confirmed", "evidence": [" "]},
                         {"status": "unknown", "evidence": [True]},
                         {"status": "unknown", "evidence": ["x" * 1025]},
                         {"status": "unknown", "evidence": ["x"] * 1001},
                         {"status": "confirmed", "evidence": ["synthetic"], "extra": 19}):
                with self.subTest(name=name, gate=gate):
                    document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                                        ["strength"], .0037)
                    document["gates"][name] = gate
                    with self.assertRaises(ValueError):
                        evaluate(document)

    def test_no_ratio_selection_requires_evidence_and_cannot_accept_an_operator(self):
        for ratio in ({"selection": "none", "evidence": []},
                      {"selection": "relative", "evidence": ["synthetic"]},
                      {"selection": None, "evidence": ["synthetic"]},
                      {"selection": "none", "evidence": None},
                      {"selection": "unknown", "evidence": [False]},
                      {"selection": "none", "evidence": ["synthetic"], "value": .25}):
            with self.subTest(ratio=ratio):
                document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                                    ["strength"], .0037)
                document["ratio"] = ratio
                with self.assertRaises(ValueError):
                    evaluate(document)

    def test_unknown_ratio_does_not_fall_back_to_the_baseline(self):
        document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                            ["strength"], .0037)
        document["ratio"] = {"selection": "unknown", "evidence": []}
        result = evaluate(document)
        self.assertEqual((result["status"], result["bonus"], result["factor"], result["gaps"]),
                         ("blocked", None, None, ["ratio: unknown"]))

    def test_unknown_unselected_total_is_excluded_and_visible_in_the_trace(self):
        document = scenario({"strength": 83, "dexterity": None, "intelligence": 197},
                            ["strength", "intelligence"], .0037)
        result = evaluate(document)
        self.assertEqual((result["status"], result["trace"][1]),
                         ("conditional", {"label": "Main attribute contribution", "attribute": "dexterity",
                                          "selected": False, "value": None, "contribution": None}))

    def test_source_context_and_nested_evidence_are_preserved_without_aliasing(self):
        document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                            ["strength", "intelligence"], .0037)
        original = copy.deepcopy(document)
        result = evaluate(document)
        preserved = copy.deepcopy(result["scenario"])
        result["scenario"]["context"]["source_sha256"] = "e" * 64
        result["scenario"]["gates"]["patch"]["evidence"].append("synthetic:changed")
        result["scenario"]["eligible"].append("dexterity")
        self.assertEqual((document, preserved), (original, original))

    def test_numeric_results_cannot_overflow_or_lose_a_positive_contribution_to_zero(self):
        for attributes, eligible, rate in (({"strength": 1e308, "dexterity": 0, "intelligence": 0},
                                            ["strength"], 2),
                                           ({"strength": 1e308, "dexterity": 1e308, "intelligence": 0},
                                            ["strength", "dexterity"], 1),
                                           ({"strength": 5e-324, "dexterity": 0, "intelligence": 0},
                                            ["strength"], .5)):
            with self.subTest(attributes=attributes, rate=rate):
                with self.assertRaises(ValueError):
                    evaluate(scenario(attributes, eligible, rate))

    def test_each_unknown_or_conflicting_gate_blocks_without_inventing_contributions(self):
        for name in ("patch", "main_stat_binding", "activation"):
            for status in ("unknown", "conflict"):
                with self.subTest(name=name, status=status):
                    document = scenario({"strength": 83, "dexterity": 47, "intelligence": 197},
                                        ["strength", "intelligence"], .0037)
                    document["gates"][name] = {"status": status, "evidence": []}
                    result = evaluate(document)
                    self.assertEqual((result["status"], result["bonus"], result["factor"],
                                      result["gaps"], [row["contribution"] for row in result["trace"]]),
                                     ("blocked", None, None, [f"{name}: {status}"], [None, None, None]))

    def test_known_zero_totals_or_zero_rate_produce_a_neutral_conditional_factor(self):
        for attributes, rate in (({"strength": 0, "dexterity": None, "intelligence": 0}, .0071),
                                 ({"strength": 83, "dexterity": None, "intelligence": 197}, 0)):
            with self.subTest(attributes=attributes, rate=rate):
                result = evaluate(scenario(attributes, ["strength", "intelligence"], rate))
                self.assertEqual((result["status"], result["bonus"], result["factor"]),
                                 ("conditional", 0, 1))

    def test_explicit_empty_main_stat_binding_does_not_turn_unknown_totals_into_inputs(self):
        result = evaluate(scenario({"strength": None, "dexterity": None, "intelligence": None}, [], .0071))
        self.assertEqual((result["status"], result["bonus"], result["factor"], result["gaps"]),
                         ("conditional", 0, 1, []))

    def test_scaled_contributions_can_be_finite_when_the_unscaled_total_would_overflow(self):
        result = evaluate(scenario({"strength": 1e308, "dexterity": 1e308, "intelligence": None},
                                   ["strength", "dexterity"], .001))
        self.assertAlmostEqual(result["bonus"] / 1e305, 2)

    def test_fractional_totals_and_an_explicit_point_rate_are_not_rounded_to_game_defaults(self):
        result = evaluate(scenario({"strength": 23.5, "dexterity": 79.25, "intelligence": 613},
                                   ["strength", "dexterity"], .0072))
        self.assertAlmostEqual(result["bonus"], .7398)
