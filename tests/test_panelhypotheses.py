"""Compare fictional panel hypotheses without inferring the game's damage formula."""

from fractions import Fraction
from decimal import Inexact, localcontext
import unittest


def state(chance, multiplier, more):
    """Provide explicitly asserted point bounds for a fictional comparison."""
    return {key: (value, value) for key, value in {
        "s": Fraction(1), "a": Fraction(1), "r": Fraction(1),
        "p": chance, "m": multiplier, "k": more,
    }.items()}


class PanelHypothesesTests(unittest.TestCase):
    """Keep exact candidate incompatibility separate from formula identification."""

    def test_exact_candidate_ratios_can_disagree_without_selecting_a_formula(self):
        from damage_lab.panelhypotheses import compare

        result = compare(state(Fraction(1, 4), Fraction(3), Fraction(1, 10)),
                         state(Fraction(3, 4), Fraction(3), Fraction(1, 10)),
                         (Fraction(5, 3), Fraction(5, 3)), invariant=True)
        self.assertEqual((result["status"], result["bounds"], result["selected"],
                          [(row["ratio"], row["relation"]) for row in result["models"].values()]),
                         ("conditional", "caller_asserted", None, [
                             ((Fraction(5, 3), Fraction(5, 3)), "compatible"),
                             ((Fraction(23, 15), Fraction(23, 15)), "incompatible"),
                             ((Fraction(109, 63), Fraction(109, 63)), "incompatible"),
                             ((Fraction(5, 3), Fraction(5, 3)), "compatible"),
                         ]))

    def test_lucky_and_critical_more_hypotheses_can_coincide_with_nonzero_more(self):
        from damage_lab.panelhypotheses import compare

        result = compare(state(Fraction(1, 10), Fraction(2), Fraction(1, 3)),
                         state(Fraction(1, 5), Fraction(2), Fraction(1, 3)),
                         (Fraction(8, 7), Fraction(8, 7)), invariant=True)
        self.assertEqual([(result["models"][name]["ratio"], result["models"][name]["relation"])
                          for name in ("H0", "H1", "H2")], [
                              ((Fraction(12, 11), Fraction(12, 11)), "incompatible"),
                              ((Fraction(8, 7), Fraction(8, 7)), "compatible"),
                              ((Fraction(8, 7), Fraction(8, 7)), "compatible"),
                          ])

    def test_a_positive_multiplier_below_one_keeps_the_valid_degeneracy(self):
        from damage_lab.panelhypotheses import compare

        result = compare(state(Fraction(1, 2), Fraction(1, 2), Fraction(0)),
                         state(Fraction(2, 3), Fraction(1, 2), Fraction(0)),
                         (Fraction(8, 9), Fraction(8, 9)), invariant=True)
        self.assertEqual([row["ratio"] for row in result["models"].values()],
                         [(Fraction(8, 9), Fraction(8, 9))] * 4)

    def test_zero_intermediate_more_is_usable_until_the_final_factor_reaches_zero(self):
        from damage_lab.panelhypotheses import compare

        for chance, expected in ((Fraction(1, 2), {"ratio": (Fraction(2, 3), Fraction(2, 3)),
                                                  "relation": "compatible", "reason": None}),
                                 (Fraction(1), {"ratio": None, "relation": "unknown",
                                                "reason": "nonpositive_factor"})):
            result = compare(state(Fraction(1, 4), Fraction(2), Fraction(-1)),
                             state(chance, Fraction(2), Fraction(-1)),
                             (Fraction(2, 3), Fraction(2, 3)), invariant=True)
            with self.subTest(chance=chance):
                self.assertEqual(result["models"]["H2"], expected)

    def test_probability_bounds_propagate_through_the_monotone_lucky_transform(self):
        from damage_lab.panelhypotheses import compare

        after = state(Fraction(1, 4), Fraction(3), Fraction(0))
        after["p"] = (Fraction(1, 4), Fraction(3, 4))
        result = compare(state(Fraction(1, 4), Fraction(3), Fraction(0)), after, None, invariant=True)
        self.assertEqual((result["models"]["H0"]["ratio"], result["models"]["H1"]["ratio"]),
                         ((Fraction(1), Fraction(5, 3)), (Fraction(1), Fraction(23, 15))))

    def test_closed_intervals_are_compatible_at_a_shared_endpoint(self):
        from damage_lab.panelhypotheses import compare

        result = compare(state(Fraction(1, 4), Fraction(3), Fraction(1, 10)),
                         state(Fraction(3, 4), Fraction(3), Fraction(1, 10)),
                         (Fraction(23, 15), Fraction(5, 3)), invariant=True)
        self.assertEqual([row["relation"] for row in result["models"].values()],
                         ["compatible", "compatible", "incompatible", "compatible"])

    def test_missing_inputs_only_hide_the_candidates_that_use_them(self):
        from damage_lab.panelhypotheses import compare

        for field, names in (("a", ["H3"]), ("k", ["H2"])):
            before = state(Fraction(1, 4), Fraction(3), Fraction(0))
            before[field] = None
            result = compare(before, state(Fraction(1, 4), Fraction(3), Fraction(0)),
                             (Fraction(1), Fraction(1)), invariant=True)
            with self.subTest(field=field):
                self.assertEqual((result["status"], [name for name, row in result["models"].items()
                                                     if row["reason"] == "input_missing"]),
                                 ("conditional", names))

    def test_unknown_or_conflicting_invariance_cannot_classify_candidates(self):
        from damage_lab.panelhypotheses import compare

        for invariant, reason in ((None, "invariance_not_asserted"), (False, "invariance_conflict")):
            result = compare(state(Fraction(1, 4), Fraction(3), Fraction(0)),
                             state(Fraction(3, 4), Fraction(3), Fraction(0)),
                             (Fraction(5, 3), Fraction(5, 3)), invariant=invariant)
            with self.subTest(invariant=invariant):
                self.assertEqual((result["status"], list(result["models"].values())),
                                 ("inconclusive", [{"ratio": None, "relation": "unknown", "reason": reason}] * 4))

    def test_unavailable_observation_keeps_predictions_without_a_compatibility_verdict(self):
        from damage_lab.panelhypotheses import compare

        result = compare(state(Fraction(1, 4), Fraction(3), Fraction(0)),
                         state(Fraction(1, 4), Fraction(3), Fraction(0)), None, invariant=True)
        self.assertEqual((result["status"], list(result["models"].values())),
                         ("inconclusive", [{"ratio": (Fraction(1), Fraction(1)), "relation": "unknown",
                                           "reason": "observation_missing"}] * 4))

    def test_all_incompatible_candidates_still_do_not_identify_an_alternative_formula(self):
        from damage_lab.panelhypotheses import compare

        result = compare(state(Fraction(1, 4), Fraction(3), Fraction(0)),
                         state(Fraction(1, 4), Fraction(3), Fraction(0)),
                         (Fraction(11), Fraction(13)), invariant=True)
        self.assertEqual((result["status"], result["selected"],
                          [row["relation"] for row in result["models"].values()]),
                         ("conditional", None, ["incompatible"] * 4))

    def test_malformed_or_oversized_fields_cannot_hide_behind_disabled_invariance(self):
        from damage_lab.panelhypotheses import compare

        for change in ({"p": (Fraction(0), Fraction(2))}, {"m": (Fraction(0), Fraction(0))},
                       {"k": (Fraction(-2), Fraction(-2))}, {"r": (Fraction(2), Fraction(1))},
                       {"p": (0, 0)}, {"m": [Fraction(1), Fraction(2)]}, {"a": "private-canary"},
                       {"s": (Fraction(1, 1 << 128), Fraction(1, 1 << 128))},
                       {"a": (Fraction(1 << 128), Fraction(1 << 128))}, {"extra": None}):
            with self.subTest(field=list(change)), self.assertRaisesRegex(ValueError, "^panel hypotheses input malformed$"):
                compare({**state(Fraction(1, 4), Fraction(3), Fraction(0)), **change},
                        state(Fraction(1, 4), Fraction(3), Fraction(0)), None, invariant=False)

    def test_nonpositive_or_untyped_observed_bounds_are_rejected_even_without_invariance(self):
        from damage_lab.panelhypotheses import compare

        for observed in ((Fraction(0), Fraction(1)), (Fraction(-1), Fraction(1)),
                         (1, 2), [Fraction(1), Fraction(2)]):
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                compare(state(Fraction(1, 4), Fraction(3), Fraction(0)),
                        state(Fraction(1, 4), Fraction(3), Fraction(0)), observed, invariant=None)

    def test_a_numeric_truth_value_cannot_assert_invariance(self):
        from damage_lab.panelhypotheses import compare

        with self.assertRaises(ValueError):
            compare(state(Fraction(1, 4), Fraction(3), Fraction(0)),
                    state(Fraction(1, 4), Fraction(3), Fraction(0)), None, invariant=1)

    def test_fraction_arithmetic_is_independent_of_decimal_precision_and_traps(self):
        from damage_lab.panelhypotheses import compare

        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            context.clear_flags()
            result = compare(state(Fraction(1, 4), Fraction(3), Fraction(1, 10)),
                             state(Fraction(3, 4), Fraction(3), Fraction(1, 10)), None, invariant=True)
            self.assertEqual((result["models"]["H2"]["ratio"], any(context.flags.values())),
                             ((Fraction(109, 63), Fraction(109, 63)), False))

    def test_repeated_calls_do_not_share_mutable_verdicts(self):
        from damage_lab.panelhypotheses import compare

        before = state(Fraction(1, 4), Fraction(3), Fraction(0))
        after = state(Fraction(1, 4), Fraction(3), Fraction(0))
        result = compare(before, after, (Fraction(1), Fraction(1)), invariant=True)
        result["models"]["H0"]["relation"] = "private-canary"
        self.assertEqual(compare(before, after, (Fraction(1), Fraction(1)), invariant=True)["models"]["H0"],
                         {"ratio": (Fraction(1), Fraction(1)), "relation": "compatible", "reason": None})
