import copy
import unittest

from damage_lab.conditionalcombat import evaluate
from damage_lab.staticcombat import project
from test_staticcombat import conditional
from test_combatupgrades import unit


def combat():
    """A fictional neutral100-DPS scenario bound to the synthetic ledger source."""
    data = unit(100)
    data['spell']['context']['source_sha256'] = 'a' * 64
    return data


def ledger():
    """Use the canonical consumer for the pinned synthetic conditional source."""
    return project(conditional(), 'a' * 64)


def condition(value=True):
    return {'cursed': value, 'evidence': ['synthetic:target-state'] if value is not None else []}


def coverage():
    return {'status': 'confirmed', 'evidence': ['synthetic:conditional-pools-excluded']}


class ConditionalCombatTests(unittest.TestCase):
    """Compute one conditional outgoing multiplier without hidden activation or duplicate sources."""

    def test_confirmed_cursed_condition_applies_the_source_row_once(self):
        self.assertEqual(evaluate(combat(), ledger(), condition=condition(), coverage=coverage())['dps'], 120)

    def test_conditional_upgrade_reaches_existing_priced_combat_comparison(self):
        from damage_lab.conditionalcombat import compare

        base = conditional()
        base['modifiers'] = []
        base['accounting'].update(observed=0, compiled=0)
        document = {'format': 'tli-conditional-combat-upgrades-v1', 'currency': 'synthetic shard',
                    'condition': condition(), 'coverage': coverage(),
                    'baseline': {'combat': combat(), 'ledger': project(base, 'a' * 64)},
                    'candidates': [{'id': 'curse', 'name': 'Synthetic curse modifier', 'combat': combat(),
                                    'ledger': ledger(), 'cost': 5, 'missing': []}]}
        self.assertEqual([(row['delta'], row['per_cost']) for row in compare(document)['result']['candidates']],
                         [(20, 4)])

    def test_false_and_unknown_conditions_never_become_the_same_state(self):
        outcomes = [evaluate(combat(), ledger(), condition=condition(value), coverage=coverage())
                    for value in (False, None)]
        self.assertEqual([(row['dps'], row['status'], len(row['applied_rows'])) for row in outcomes],
                         [(100, 'conditional', 0), (None, 'blocked', 0)])

    def test_shared_affix_pool_adds_two_instances_instead_of_multiplying_them(self):
        data = conditional()
        second = copy.deepcopy(data['modifiers'][0])
        second['path'] = second['path'].replace('PrefixInfoList[0]', 'PrefixInfoList[1]')
        data['modifiers'].append(second)
        data['accounting'].update(observed=2, compiled=2)
        result = evaluate(combat(), project(data, 'a' * 64), condition=condition(), coverage=coverage())
        self.assertEqual((result['dps'], len(result['applied_rows']),
                          len({row['affix'] for row in result['applied_rows']})), (140, 2, 1))

    def test_inclusive_source_or_pool_is_refused_even_when_condition_is_false(self):
        seed = evaluate(combat(), ledger(), condition=condition(), coverage=coverage())['applied_rows'][0]
        for field in ('id', 'affix'):
            data = combat()
            row = {'id': 'synthetic-already', 'affix': 'synthetic-pool', 'value': .2,
                   'stacks': 1, 'mode': 'add', 'scope': 'all'}
            row[field] = seed[field]
            data['spell']['damage']['more'] = [row]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'already present'):
                evaluate(data, ledger(), condition=condition(False), coverage=coverage())

    def test_coverage_requires_an_explicit_exclusion_proof(self):
        for status in ('unknown', 'conflict'):
            result = evaluate(combat(), ledger(), condition=condition(), coverage={'status': status, 'evidence': []})
            self.assertEqual((result['dps'], result['applied_rows']), (None, []))
        for state in (True, False):
            with self.subTest(state=state), self.assertRaises(ValueError):
                evaluate(combat(), ledger(), condition={'cursed': state, 'evidence': []}, coverage=coverage())
        with self.assertRaises(ValueError):
            evaluate(combat(), ledger(), condition=condition(), coverage={'status': 'confirmed', 'evidence': []})

    def test_unknown_damage_group_remains_unknown_and_inputs_are_not_mutated(self):
        data, supplied = combat(), ledger()
        data['spell']['damage'] = None
        saved = copy.deepcopy((data, supplied))
        result = evaluate(data, supplied, condition=condition(), coverage=coverage())
        self.assertEqual((result['dps'], result['scenario']['spell']['damage'], result['applied_rows'],
                          (data, supplied)), (None, None, [], saved))

    def test_source_mismatch_and_promoted_ledger_condition_are_refused(self):
        data = combat()
        data['spell']['context']['source_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'source hash'):
            evaluate(data, ledger(), condition=condition(), coverage=coverage())
        supplied = ledger()
        supplied['modifiers'][0]['condition']['state'] = True
        with self.assertRaises(ValueError):
            evaluate(combat(), supplied, condition=condition(), coverage=coverage())

    def test_other_ledger_families_are_not_applied_or_blocked_by_an_unknown_curse(self):
        from test_staticcombat import document

        supplied = project(document(), 'a' * 64)
        result = evaluate(combat(), supplied, condition=condition(None), coverage={'status': 'unknown', 'evidence': []})
        self.assertEqual((result['dps'], result['applied_rows']), (100, []))

    def test_unknown_condition_blocks_upgrade_delta_and_ranking(self):
        from damage_lab.conditionalcombat import compare

        data = {'format': 'tli-conditional-combat-upgrades-v1', 'currency': 'synthetic shard',
                'condition': condition(None), 'coverage': coverage(), 'baseline': {'combat': combat(), 'ledger': ledger()},
                'candidates': [{'id': 'same', 'name': 'Synthetic same', 'combat': combat(), 'ledger': ledger(),
                                'cost': 5, 'missing': []}]}
        result = compare(data)
        self.assertEqual((result['result']['baseline']['dps'], result['result']['candidates'][0]['delta'],
                          result['ranking']), (None, None, []))

    def test_synthetic_fraction_change_reaches_upgrade_delta_without_claiming_a_real_variant(self):
        from damage_lab.conditionalcombat import compare

        fictional = conditional()
        fictional['modifiers'][0]['values'] = [{'exact': '30', 'fraction': '0.3', 'source': 'DynArgs[0]'}]
        data = {'format': 'tli-conditional-combat-upgrades-v1', 'currency': 'synthetic shard',
                'condition': condition(), 'coverage': coverage(), 'baseline': {'combat': combat(), 'ledger': ledger()},
                'candidates': [{'id': 'fictional', 'name': 'Mathematical fictional source only', 'combat': combat(),
                                'ledger': project(fictional, 'a' * 64), 'cost': 5, 'missing': []}]}
        self.assertEqual(compare(data)['result']['candidates'][0]['delta'], 10)

    def test_upgrade_comparison_preserves_legacy_and_joint_spell_version_rules(self):
        from damage_lab.conditionalcombat import compare
        from test_rawspell import double

        replacement = combat()
        replacement['spell'] = double()
        data = {'format': 'tli-conditional-combat-upgrades-v1', 'currency': 'synthetic shard',
                'condition': condition(), 'coverage': coverage(), 'baseline': {'combat': combat(), 'ledger': ledger()},
                'candidates': [{'id': 'joint', 'name': 'Synthetic joint', 'combat': replacement, 'ledger': ledger(),
                                'cost': 5, 'missing': []}]}
        with self.assertRaisesRegex(ValueError, 'model version'):
            compare(data)
