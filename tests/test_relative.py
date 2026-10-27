import unittest
import copy
from fractions import Fraction

from damage_lab.relative import relative


def candidate(name, old, new):
    return {'name': name, 'dependsOn': None, 'activation': 'always', 'old': old, 'new': new,
            'positiveFinite': None, 'invariance': None, 'provenance': []}


def claimed(name, old, new, kind):
    factor = candidate(name, old, new)
    factor.update(dependsOn=frozenset(), positiveFinite={'ref': 'positive:q'},
                  invariance={'kind': kind, 'ref': 'invariant:q', 'factor': name,
                              'upgrade': 'upgrade:q', 'baseline': 'baseline:q'},
                  provenance=[{'kind': 'source_contract', 'ref': 'contract:q'}])
    return factor


def model(factors):
    return {'form': 'product', 'proof': {'ref': 'product:q'}, 'factors': factors,
            'context': {'baseline': 'baseline:q', 'quantity': 'damage', 'target': 'skill:q'}}


def graph(edges, complete):
    return {'edges': frozenset(edges), 'complete': complete}


def upgrade(changes):
    return {'id': 'upgrade:q', 'changes': frozenset(changes)}


class RelativeTest(unittest.TestCase):
    """Verify exact ratios under explicit product and invariance assertions."""

    def test_unknown_common_factor_cancels_only_under_declared_proofs(self):
        result = relative(model([
            claimed('U', None, None, 'independent_invariance_proof'),
            candidate('M', (Fraction(9, 7), Fraction(9, 7)), (Fraction(13, 8), Fraction(13, 8)))]),
            graph([], False), upgrade(['gear']))
        self.assertEqual((result['status'], result['ratio'], result['cancelled'], result['tight']),
                         ('exact', (Fraction(91, 72), Fraction(91, 72)), ['U'], False))

    def test_uncorrelated_intervals_produce_outward_quotient_bounds(self):
        result = relative(model([candidate('M', (Fraction(2), Fraction(3)), (Fraction(5, 2), Fraction(4)))]),
                          graph([], False), upgrade(['gear']))
        self.assertEqual((result['status'], result['ratio']), ('interval', (Fraction(5, 6), Fraction(2))))

    def test_removing_invariance_can_widen_a_point_to_an_interval(self):
        interval = (Fraction(2), Fraction(3))
        common = claimed('U', interval, interval, 'independent_invariance_proof')
        before = relative(model([common]), graph([], False), upgrade(['gear']))
        common['invariance'] = None
        after = relative(model([common]), graph([], False), upgrade(['gear']))
        self.assertEqual((before['ratio'], after['ratio']),
                         ((Fraction(1), Fraction(1)), (Fraction(2, 3), Fraction(3, 2))))

    def test_a_changed_dependency_cannot_be_cancelled(self):
        factor = claimed('U', None, None, 'dependency_disjoint')
        factor['dependsOn'] = frozenset({'level'})
        result = relative(model([factor]), graph([('gear', 'rank'), ('rank', 'level')], True), upgrade(['gear']))
        self.assertEqual((result['status'], result['ratio'], result['cancelled']), ('inconclusive', None, []))

    def test_closure_includes_the_initial_change(self):
        factor = claimed('U', None, None, 'dependency_disjoint')
        factor['dependsOn'] = frozenset({'gear'})
        self.assertEqual(relative(model([factor]), graph([], True), upgrade(['gear']))['status'], 'inconclusive')

    def test_incomplete_graph_cannot_assert_disjointness(self):
        factor = claimed('U', None, None, 'dependency_disjoint')
        self.assertEqual(relative(model([factor]), graph([], False), upgrade(['gear']))['cancelled'], [])

    def test_a_cycle_terminates_and_keeps_unrelated_factor_disjoint(self):
        factor = claimed('U', None, None, 'dependency_disjoint')
        factor['dependsOn'] = frozenset({'cast'})
        result = relative(model([factor]), graph([('gear', 'rank'), ('rank', 'gear')], True), upgrade(['gear']))
        self.assertEqual(result['ratio'], (Fraction(1), Fraction(1)))

    def test_independent_proof_must_bind_factor_upgrade_and_baseline(self):
        results = []
        for field in ('factor', 'upgrade', 'baseline'):
            factor = claimed('U', None, None, 'independent_invariance_proof')
            factor['invariance'][field] = 'other:q'
            results.append(relative(model([factor]), graph([], False), upgrade(['gear']))['status'])
        self.assertEqual(results, ['inconclusive'] * 3)

    def test_dependency_trace_records_actual_bindings(self):
        factor = claimed('Actual-U', None, None, 'dependency_disjoint')
        factor['invariance'].update(factor='Declared-V', upgrade='other:q', baseline='other:q')
        result = relative(model([factor]), graph([], True), upgrade(['gear']))
        proof = result['trace']['invarianceProofs'][0]
        self.assertEqual((result['cancelled'], proof['factor'], proof['upgrade'], proof['baseline']),
                         (['Actual-U'], 'Actual-U', 'upgrade:q', 'baseline:q'))

    def test_conflicting_numeric_invariance_is_an_error(self):
        factor = claimed('U', (Fraction(2), Fraction(2)), (Fraction(3), Fraction(3)), 'independent_invariance_proof')
        self.assertEqual(relative(model([factor]), graph([], False), upgrade(['gear']))['reasons'],
                         ['invariance_contradiction'])

    def test_oversized_fraction_is_refused_before_interval_order(self):
        factor = candidate('M', (Fraction(2 ** 300), Fraction(1)), None)
        result = relative(model([factor]), graph([], False), upgrade(['gear']))
        self.assertEqual((result['status'], result['reasons']), ('resource_limit', ['input_bits']))

    def test_zero_and_reversed_intervals_have_distinct_validity_failures(self):
        results = [relative(model([candidate('M', interval, None)]), graph([], False), upgrade(['gear']))['status']
                   for interval in ((Fraction(0), Fraction(2)), (Fraction(3), Fraction(2)))]
        self.assertEqual(results, ['domain_error', 'error'])

    def test_only_exact_fraction_bounds_are_admitted(self):
        result = relative(model([candidate('M', (1, 2), None)]), graph([], False), upgrade(['gear']))
        self.assertEqual((result['status'], result['context'], result['trace']), ('error', None, None))

    def test_duplicate_factor_names_are_refused(self):
        result = relative(model([candidate('U', None, None), candidate('U', None, None)]),
                          graph([], False), upgrade(['gear']))
        self.assertEqual(result['reasons'], ['duplicate_factor_name'])

    def test_foreign_dictionary_keys_are_refused_without_callbacks(self):
        armed = [False]

        class Key(str):
            """A foreign key that exposes any callback before admission."""

            def __hash__(self):
                if armed[0]:
                    raise AssertionError('Foreign key callback reached')
                return str.__hash__(self)

            def __eq__(self, other):
                if armed[0]:
                    raise AssertionError('Foreign key callback reached')
                return str.__eq__(self, other)

        source = {Key('form'): 'product', 'proof': {'ref': 'product:q'}, 'factors': [], 'context': {}}
        armed[0] = True
        self.assertEqual(relative(source, graph([], False), upgrade(['gear']))['reasons'], ['malformed'])

    def test_unordered_admission_has_fixed_priority(self):
        results = []
        factor = candidate('U', None, None)
        factor['dependsOn'] = frozenset({'x' * 129, '\x00'})
        results.append(relative(model([factor]), graph([], False), upgrade(['gear']))['reasons'])
        results.append(relative(model([]), graph([('gear', 'x' * 129), ('gear', '\x00')], False),
                                upgrade(['gear']))['reasons'])
        results.append(relative(model([]), graph([], False), upgrade(['x' * 129, '\x00']))['reasons'])
        self.assertEqual(results, [['name_chars']] * 3)

    def test_product_bit_estimate_refuses_large_retained_factors(self):
        old = (Fraction(2 ** 255 - 19, 2 ** 254 - 27),) * 2
        new = (Fraction(2 ** 253 - 31, 2 ** 252 - 41),) * 2
        factors = [candidate('M' + str(index), old, new) for index in range(64)]
        result = relative(model(factors), graph([], False), upgrade(['gear']))
        self.assertEqual((result['status'], result['ratio'], result['reasons']),
                         ('resource_limit', None, ['result_bits']))

    def test_cancelled_factors_do_not_inflate_product_estimate(self):
        interval = (Fraction(2 ** 255 - 19, 2 ** 254 - 27),) * 2
        factors = [claimed('U' + str(index), interval, interval, 'independent_invariance_proof') for index in range(63)]
        factors.append(candidate('M', (Fraction(2),) * 2, (Fraction(3),) * 2))
        self.assertEqual(relative(model(factors), graph([], False), upgrade(['gear']))['ratio'],
                         (Fraction(3, 2), Fraction(3, 2)))

    def test_inputs_remain_unchanged(self):
        source = model([claimed('U', None, None, 'independent_invariance_proof')])
        before = copy.deepcopy(source)
        relative(source, graph([], False), upgrade(['gear']))
        self.assertEqual(source, before)

    def test_unproved_partial_inputs_remain_inconclusive(self):
        factor = candidate('unknown_damage', None, None)
        factor['activation'] = 'unknown'
        result = relative(model([factor]), graph([], False), upgrade(['gear']))
        self.assertEqual((result['metric'], result['status'], result['ratio'], result['cancelled']),
                         ('ratio', 'inconclusive', None, []))
