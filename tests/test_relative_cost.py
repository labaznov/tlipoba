import copy
import unittest
from fractions import Fraction

from damage_lab.relative import relative
from damage_lab.relative_cost import dominates, per_cost


def ratio(old, new):
    return relative(
        {'form': 'product', 'proof': {'ref': 'product:cost'},
         'context': {'baseline': 'base:cost', 'quantity': 'damage', 'target': 'spell:cost'},
         'factors': [{'name': 'hit', 'dependsOn': None, 'activation': 'always', 'old': old, 'new': new,
                      'positiveFinite': None, 'invariance': None, 'provenance': []}]},
        {'edges': frozenset(), 'complete': False}, {'id': 'item:cost', 'changes': frozenset({'gear'})})


def point(value):
    return (Fraction(value), Fraction(value))


def price(value, currency='currency:cost'):
    return {'amount': Fraction(value), 'currency': currency}


class RelativeCostTest(unittest.TestCase):
    """Check exact gain per explicit scenario price through the public library seam."""

    def test_a_fifth_of_relative_gain_at_one_fiftieth_cost_gives_ten(self):
        result = per_cost(ratio(point(1), point(Fraction(6, 5))), price(Fraction(1, 50)))
        self.assertEqual((result['status'], result['gain']), ('gain_per_cost', (Fraction(10), Fraction(10))))

    def test_interval_gain_has_exact_literal_bounds(self):
        result = per_cost(ratio(point(1), (Fraction(21, 20), Fraction(11, 10))), price(5))
        self.assertEqual(result['gain'], (Fraction(1, 100), Fraction(1, 50)))

    def test_unknown_price_stays_distinct_from_free(self):
        result = per_cost(ratio(point(1), point(Fraction(6, 5))), None)
        self.assertEqual((result['status'], result['gain'], result['amount'], result['reasons']),
                         ('inconclusive', None, None, ['price_unknown']))

    def test_free_positive_gain_has_no_infinite_score(self):
        result = per_cost(ratio(point(1), point(Fraction(6, 5))), price(0))
        self.assertEqual((result['status'], result['gain'], result['amount']), ('no_cost', None, Fraction(0)))

    def test_crossing_one_keeps_gain_unproved_even_when_free(self):
        result = per_cost(ratio(point(1), (Fraction(1), Fraction(40, 37))), price(0))
        self.assertEqual((result['status'], result['reasons']), ('inconclusive', ['gain_not_proven_positive']))

    def test_a_wholly_nonpositive_gain_stays_unranked(self):
        result = per_cost(ratio(point(1), (Fraction(9, 10), Fraction(1))), price(Fraction(7, 9)))
        self.assertEqual((result['status'], result['gain']), ('no_positive_gain', None))

    def test_negative_price_is_a_domain_error(self):
        self.assertEqual(per_cost(ratio(point(1), point(2)), price(-3))['reasons'], ['negative_price'])

    def test_float_price_is_refused(self):
        result = per_cost(ratio(point(1), point(2)), {'amount': 0.25, 'currency': 'currency:cost'})
        self.assertEqual(result['reasons'], ['malformed_cost'])

    def test_price_bits_are_checked_before_its_sign(self):
        result = per_cost(ratio(point(1), point(2)), price(-(2 ** 300)))
        self.assertEqual((result['status'], result['reasons']), ('resource_limit', ['input_bits']))

    def test_unknown_factor_passes_through_with_valid_price(self):
        result = per_cost(ratio(None, None), price(Fraction(4, 7)))
        self.assertEqual((result['status'], result['ratioStatus'], result['amount']),
                         ('inconclusive', 'inconclusive', Fraction(4, 7)))

    def test_bad_price_is_refused_before_unknown_ratio_passthrough(self):
        result = per_cost(ratio(None, None), {'amount': True, 'currency': 'currency:cost'})
        self.assertEqual((result['status'], result['ratioStatus']), ('error', None))

    def test_an_already_priced_result_cannot_be_priced_again(self):
        result = per_cost(ratio(point(1), point(2)), price(3))
        self.assertEqual(per_cost(result, price(4))['reasons'], ['metric_not_ratio'])

    def test_oversized_metric_mapping_is_refused_at_shape_admission(self):
        source = {'metric': 'gain_per_cost', **{f'extra:{index}': None for index in range(15)}}
        self.assertEqual(per_cost(source, price(1))['reasons'], ['malformed_result'])

    def test_unproved_activation_cannot_carry_an_exact_ratio(self):
        source = ratio(point(1), point(Fraction(6, 5)))
        source['trace']['classifications'][0]['reasons'] = ['activation_not_proven']
        self.assertEqual(per_cost(source, price(1))['reasons'], ['inconsistent_result'])

    def test_embedded_unproved_activation_cannot_be_ranked(self):
        source = per_cost(ratio(point(1), point(Fraction(6, 5))), price(1))
        other = copy.deepcopy(source)
        source['trace']['classifications'][0]['reasons'] = ['activation_not_proven']
        self.assertEqual(dominates(source, other),
                         {'winner': None, 'status': 'error', 'reason': 'inconsistent_result', 'side': 'a'})

    def test_ratio_bits_are_checked_before_reversed_bounds(self):
        source = ratio(point(1), point(2))
        source['ratio'] = (Fraction(2 ** 12289), Fraction(1))
        self.assertEqual(per_cost(source, price(1))['reasons'], ['result_bits'])

    def test_free_ratio_avoids_the_positive_price_result_estimate(self):
        source = ratio(point(1), point(2))
        source['ratio'] = point(2 ** 12287 + 1)
        self.assertEqual((per_cost(source, price(0))['status'], per_cost(source, price(Fraction(1, 3)))['reasons']),
                         ('no_cost', ['result_bits']))

    def test_only_strictly_separated_ratio_intervals_have_a_winner(self):
        result = dominates(ratio(point(1), (Fraction(7, 5), Fraction(9, 5))),
                           ratio(point(1), (Fraction(11, 10), Fraction(13, 10))))
        self.assertEqual((result['winner'], result['reason']), ('a', 'strict_non_overlap'))

    def test_touching_intervals_overlap(self):
        result = dominates(ratio(point(1), (Fraction(6, 5), Fraction(3, 2))),
                           ratio(point(1), (Fraction(11, 10), Fraction(6, 5))))
        self.assertEqual((result['winner'], result['reason']), (None, 'overlap'))

    def test_same_upgrade_at_lower_price_can_dominate(self):
        source = ratio(point(1), point(Fraction(6, 5)))
        result = dominates(per_cost(source, price(Fraction(1, 50))), per_cost(source, price(Fraction(1, 100))))
        self.assertEqual((result['winner'], result['status']), ('b', 'dominates'))

    def test_different_contexts_cannot_be_compared(self):
        source = ratio(point(1), point(Fraction(6, 5)))
        other = copy.deepcopy(source)
        other['context']['baseline'] = 'base:other'
        self.assertEqual(dominates(source, other)['reason'], 'context_differs')

    def test_different_currencies_cannot_be_compared(self):
        source = ratio(point(1), point(Fraction(6, 5)))
        self.assertEqual(dominates(per_cost(source, price(3)), per_cost(source, price(4, 'currency:other')))['reason'],
                         'currency_differs')

    def test_ratio_and_gain_metrics_cannot_be_compared(self):
        source = ratio(point(1), point(Fraction(6, 5)))
        self.assertEqual(dominates(source, per_cost(source, price(1)))['reason'], 'incomparable_metric')

    def test_free_result_does_not_dominate_a_priced_result(self):
        source = ratio(point(1), point(Fraction(6, 5)))
        self.assertEqual(dominates(per_cost(source, price(0)), per_cost(source, price(1)))['reason'],
                         'no_comparable_interval')

    def test_gain_price_bits_are_checked_before_branch_predicates(self):
        source = per_cost(ratio(point(1), point(2)), price(3))
        source['amount'] = Fraction(-(2 ** 300))
        self.assertEqual(dominates(source, source),
                         {'winner': None, 'status': 'resource_limit', 'reason': 'input_bits', 'side': 'a'})

    def test_pricing_preserves_the_input(self):
        source = ratio(point(1), point(2))
        before = copy.deepcopy(source)
        per_cost(source, price(3))
        self.assertEqual(source, before)

    def test_result_trace_is_detached_from_the_input(self):
        source = ratio(point(1), point(2))
        result = per_cost(source, price(3))
        result['trace']['classifications'][0]['reasons'].append('changed')
        self.assertEqual(source['trace']['classifications'][0]['reasons'], ['no_invariance_claim'])

    def test_foreign_keys_run_no_callbacks_during_admission(self):
        armed = [False]

        class Key(str):
            """Expose any callback caused by inspecting a foreign dictionary key."""

            def __hash__(self):
                if armed[0]:
                    raise AssertionError('Foreign key callback reached')
                return str.__hash__(self)

            def __eq__(self, other):
                if armed[0]:
                    raise AssertionError('Foreign key callback reached')
                return str.__eq__(self, other)

        source = ratio(point(1), point(2))
        source = {(Key(key) if key == 'metric' else key): value for key, value in source.items()}
        armed[0] = True
        self.assertEqual(per_cost(source, price(1))['reasons'], ['malformed_result'])
