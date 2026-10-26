import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

_TESTS = Path(__file__).resolve().parent
_PROJECT = _TESTS.parent
sys.path[:0] = [str(_PROJECT), str(_TESTS)]

from damage_lab.conditionalcombat import compare, evaluate
from damage_lab.conditionalreport import render
from damage_lab import conditionalreport
from damage_lab.engine import cold
from damage_lab.rawcombat import evaluate as raw_evaluate
from damage_lab.rawspell import _number
from damage_lab.staticcombat import project
from fractions import Fraction
from test_conditionalcombat import combat, condition, coverage
from test_conditionalreport import report
from test_staticcombat import conditional
from test_conditionalcli import record, context


def rows(pairs, *, pool=None):
    data = conditional()
    built = []
    for index, (percent, fraction) in enumerate(pairs):
        row = copy.deepcopy(data['modifiers'][0])
        if index:
            row['path'] = row['path'].replace('PrefixInfoList[0]', f'PrefixInfoList[{index}]')
        row['values'] = [{'exact': percent, 'fraction': fraction, 'source': 'DynArgs[0]'}]
        if pool is not None and index == 1:
            row['pool'] = {**row['pool'], 'id': pool}
            row['definition'] = {**row['definition'], 'id': pool}
        built.append(row)
    data['modifiers'] = built
    data['accounting'].update(observed=len(built), compiled=len(built))
    return project(data, 'a' * 64)


def run(pairs, **keywords):
    return evaluate(combat(), rows(pairs, **keywords), condition=condition(), coverage=coverage())


class ExactPoolsFinalTests(unittest.TestCase):
    """Canonical percent decimals, not the ledger's fraction spelling, drive one pool."""

    def test_p0_cancellation_is_exactly_zero(self):
        result = run((('-99.999999999', '-0.99999999999'), ('-0.000000001', '-0.00000000001')))
        self.assertEqual(result['dps'], 0)
        self.assertEqual([row['exact_value'] for row in result['applied_rows']],
                         ['-0.99999999999', '-0.00000000001'])

    def test_p1_false_negative_factor_becomes_zero(self):
        result = run((('-6.373950278', '-0.06373950278'), ('-93.626049722', '-0.93626049722')))
        self.assertEqual(result['dps'], 0)

    def test_p5_positive_residual_is_one_nano(self):
        result = run((('-99.999999998', '-0.99999999998'), ('-0.000000001', '-0.00000000001')))
        expected = 1e-9
        self.assertLess(abs(result['dps'] - expected) / expected, 1e-15)

    def test_p6_genuine_negative_factor_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'cannot be negative'):
            run((('-99.999999999', '-0.99999999999'), ('-0.000000002', '-0.00000000002')))

    def test_p7_exact_value_above_the_bound_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'range'):
            run((('100000000.000000001', '1000000.00000000001'),))

    def test_p4_fraction_spellings_share_one_canonical_value(self):
        spellings = ('-0.99999999999', '-9.9999999999E-1', '-0.999999999990000', '-99999999999E-11')
        found = [run((('-99.999999999', spelling),))['applied_rows'][0]['exact_value'] for spelling in spellings]
        self.assertEqual(found, ['-0.99999999999'] * 4)
        # Spec 9: normalization strips only fractional zeros, preserving integer places.
        for percent, fraction in (('1000', '10'), ('10000', '100'), ('-0', '0')):
            with self.subTest(percent=percent):
                self.assertEqual(run(((percent, fraction),))['applied_rows'][0]['exact_value'], fraction)

    def test_exact_value_is_refused_outside_additive_damage_rows(self):
        plain = {'id': 'synthetic-row', 'affix': 'synthetic-pool', 'value': 0.2, 'stacks': 1, 'mode': 'add'}
        spell = combat()
        spell['spell']['casting']['more'] = [{**plain, 'exact_value': '0.2'}]
        with self.assertRaisesRegex(ValueError, 'unsupported fields'):
            raw_evaluate(spell)
        fight = combat()
        fight['target']['more_taken'] = [{**plain, 'exact_value': '0.2'}]
        with self.assertRaisesRegex(ValueError, 'unsupported fields'):
            raw_evaluate(fight)
        mixed_mode = combat()
        mixed_mode['spell']['damage']['more'] = [{**plain, 'mode': 'multiply', 'scope': 'all', 'exact_value': '0.2'}]
        with self.assertRaisesRegex(ValueError, 'additive'):
            raw_evaluate(mixed_mode)
        extra = combat()
        extra['spell']['damage']['more'] = [{**plain, 'scope': 'all', 'unexpected': 'not accepted'}]
        with self.assertRaisesRegex(ValueError, 'unsupported fields'):
            raw_evaluate(extra)

    def test_a_mixed_exact_pool_and_a_bad_value_are_refused(self):
        data = combat()
        data['spell']['damage']['more'] = [
            {'id': 'exact-row', 'affix': 'shared-pool', 'value': 0.25, 'stacks': 1, 'mode': 'add',
             'scope': 'all', 'exact_value': '0.25'},
            {'id': 'plain-row', 'affix': 'shared-pool', 'value': 0.25, 'stacks': 1, 'mode': 'add', 'scope': 'all'}]
        with self.assertRaisesRegex(ValueError, 'mix'):
            raw_evaluate(data)
        data['spell']['damage']['more'] = [
            {'id': 'bad-row', 'affix': 'other-pool', 'value': 0.2, 'stacks': 1, 'mode': 'add',
             'scope': 'all', 'exact_value': '0.25'}]
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            raw_evaluate(data)
        with self.assertRaises(ValueError):
            _number(Fraction(1, 5), -1, 100, 'Additional modifier')
        # Spec 9: hand-written replay rows obey the same bounded canonical grammar.
        for text in ('0.20', '-0', '.2', '2e-1', '+0.2', '0.123456789012'):
            data['spell']['damage']['more'] = [
                {'id': 'grammar-row', 'affix': 'grammar-pool', 'value': float(Fraction(text)), 'stacks': 1,
                 'mode': 'add', 'scope': 'all', 'exact_value': text}]
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'canonical'):
                raw_evaluate(data)
        for text in ('-1', '1000000'):
            data['spell']['damage']['more'][0].update(value=float(text), exact_value=text)
            self.assertEqual(raw_evaluate(data)['dps'], 100 * (1 + int(text)))

    def test_old_results_duplicates_and_other_pools_stay(self):
        self.assertEqual(evaluate(combat(), project(conditional(), 'a' * 64),
                                  condition=condition(), coverage=coverage())['dps'], 120)
        data = conditional()
        second = copy.deepcopy(data['modifiers'][0])
        second['path'] = second['path'].replace('PrefixInfoList[0]', 'PrefixInfoList[1]')
        data['modifiers'].append(second)
        data['accounting'].update(observed=2, compiled=2)
        added = evaluate(combat(), project(data, 'a' * 64), condition=condition(), coverage=coverage())
        self.assertEqual(added['dps'], 140)
        outcomes = [evaluate(combat(), project(conditional(), 'a' * 64), condition=condition(value), coverage=coverage())
                    for value in (False, None)]
        self.assertEqual([(row['dps'], len(row['applied_rows'])) for row in outcomes], [(100, 0), (None, 0)])
        source = conditional()
        source['modifiers'].append(copy.deepcopy(source['modifiers'][0]))
        source['accounting'].update(observed=2, compiled=2)
        with self.assertRaises(ValueError):
            project(source, 'a' * 64)
        multiplied = run((('-50', '-0.5'), ('-50', '-0.5')), pool='11111111-1111-1111-1111-111111111111')
        self.assertEqual(multiplied['dps'], 25)
        # Spec 8: direct cold() must validate before exact substitution and traverse an iterator once.
        plain = {'id': 'boundary-row', 'affix': 'boundary-pool', 'value': 0.25,
                 'stacks': 1, 'mode': 'add', 'scope': 'all'}
        for row in ({key: value for key, value in plain.items() if key != 'affix'},
                    {**{key: value for key, value in plain.items() if key != 'value'}, 'exact_value': '0.25'}, []):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, 'requires'):
                cold(100, 0, 0, 1, 0, 0, 0, [row])
        self.assertEqual(cold(100, 0, 0, 1, 0, 0, 0, iter([plain])), 125)

    def test_json_replay_and_priced_compare_match(self):
        result = run((('-99.999999999', '-0.99999999999'), ('-0.000000001', '-0.00000000001')))
        self.assertEqual(raw_evaluate(json.loads(json.dumps(result['scenario'], allow_nan=False)))['dps'], 0)
        residual = run((('-99.999999998', '-0.99999999998'), ('-0.000000001', '-0.00000000001')))
        self.assertEqual(raw_evaluate(json.loads(json.dumps(residual['scenario'], allow_nan=False)))['dps'],
                         residual['dps'])
        json.dumps(result, allow_nan=False)
        baseline = conditional()
        baseline['modifiers'] = []
        baseline['accounting'].update(observed=0, compiled=0)
        document = {'format': 'tli-conditional-combat-upgrades-v1', 'currency': 'synthetic shard',
                    'condition': condition(), 'coverage': coverage(),
                    'baseline': {'combat': combat(), 'ledger': project(baseline, 'a' * 64)},
                    'candidates': [{'id': 'cancel', 'name': 'Exact cancel', 'combat': combat(),
                                    'ledger': rows((('-99.999999999', '-0.99999999999'),
                                                    ('-0.000000001', '-0.00000000001'))),
                                    'cost': 5, 'missing': []}]}
        compared = compare(document)['result']
        self.assertEqual((compared['candidates'][0]['delta'], compared['ranking']), (-100, []))

    def test_old_applied_rows_must_be_regenerated(self):
        # Spec 7, 10: TEST-ONLY complete spell; the real automatic assembler still has unavailable raw groups.
        assemble = conditionalreport.assemble

        def synthetic(record, *, skill_alias):
            inputs = assemble(record, skill_alias=skill_alias)
            spell = combat()['spell']
            spell['context']['source_sha256'] = inputs['raw_spell']['context']['source_sha256']
            inputs['raw_spell'] = spell
            return inputs

        declared = context()
        declared.update({key: value for key, value in combat().items()
                         if key in ('topology', 'target', 'uptime', 'gates', 'missing', 'notes')})
        declared.update(condition=condition(), coverage=coverage())
        with mock.patch.object(conditionalreport, 'assemble', synthetic):
            fresh = conditionalreport.build(record(), declared, skill_alias='gem[1]', origins=report()['origins'])
            self.assertEqual((len(fresh['calculation']['applied_rows']), fresh['calculation']['dps'],
                              [fresh[key] for key in ('import_complete', 'runtime_verified', 'identity_verified')]),
                             (1, 120, [False] * 3))
            page = render(fresh)
            self.assertIn('exact_value', page)
            self.assertEqual(render(json.loads(json.dumps(fresh, allow_nan=False))), page)
            saved = copy.deepcopy(fresh)
            for row in saved['calculation']['applied_rows'] + saved['calculation']['scenario']['spell']['damage']['more']:
                row.pop('exact_value', None)  # applied/scenario rows intentionally share objects before serialization
            with self.assertRaisesRegex(ValueError, 'source-bound reconstruction'):
                render(saved)
        legacy = json.loads((_TESTS / 'fixtures/automatic-conditional-v1-report.json').read_text(encoding='utf-8'))
        self.assertEqual(legacy['calculation']['applied_rows'], [])
        self.assertIn('Применённые строки', render(legacy))


if __name__ == '__main__':
    unittest.main()
