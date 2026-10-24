"""Apply source-bound target-Cursed damage only under an explicit scenario condition."""

import copy

from . import combatupgrades, rawcombat, staticcombat


def _object(value, fields, label):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError(f'{label} requires exactly its supported fields')


def _evidence(value):
    if type(value) is not list or len(value) > 1000 or any(
            type(item) is not str or not item or item != item.strip() or len(item) > 1024 for item in value):
        raise ValueError('Conditional combat evidence requires bounded nonempty trimmed references')


def _claims(condition, coverage):
    _object(condition, 'cursed evidence', 'Target condition')
    if condition['cursed'] is not None and type(condition['cursed']) is not bool:
        raise ValueError('Target Cursed state must be boolean or unknown')
    _evidence(condition['evidence'])
    if condition['cursed'] is not None and not condition['evidence']:
        raise ValueError('A declared target Cursed state requires evidence')
    _object(coverage, 'status evidence', 'Conditional source coverage')
    if coverage['status'] not in ('confirmed', 'unknown', 'conflict'):
        raise ValueError('Conditional source coverage status must be confirmed unknown or conflict')
    _evidence(coverage['evidence'])
    if coverage['status'] == 'confirmed' and not coverage['evidence']:
        raise ValueError('Confirmed conditional source coverage requires evidence')


def evaluate(combat, ledger, *, condition, coverage):
    """Prepare outgoing damage from a caller-asserted target state and excluded source pools."""
    _claims(condition, coverage)
    ledger = staticcombat.summary(ledger)
    # The real evaluator validates all supplied groups, including blocked scenarios
    rawcombat.evaluate(combat)
    source = ledger['source']['sha256']
    if combat['spell']['context']['source_sha256'] != source:
        raise ValueError('Conditional ledger and spell must share their exact source hash')
    prepared = copy.deepcopy(combat)
    rows = [row for row in ledger['modifiers'] if row['family'] == 'conditional_damage_more']
    damage = prepared['spell']['damage']
    applied = []
    for row in rows:
        identity = 'static:' + source + ':' + row['path']
        pool = 'conditional:' + row['definition']['catalog'] + ':' + row['pool']['id']
        if damage is not None and any(value['id'] == identity or value['affix'] == pool for value in damage['more']):
            raise ValueError('Conditional damage source or pool is already present in the scenario')
        if condition['cursed'] is True and coverage['status'] == 'confirmed' and damage is not None:
            modifier = {'id': identity, 'affix': pool, 'value': float(row['values'][0]['fraction']),
                        'stacks': 1, 'mode': 'add', 'scope': 'all'}
            # Original rows are checked separately; two ledger instances intentionally share a pool
            applied.append(modifier)
    if rows:
        if condition['cursed'] is None:
            prepared['missing'].append('target_cursed: unknown')
        if coverage['status'] != 'confirmed':
            prepared['missing'].append('conditional_coverage: ' + coverage['status'])
    if damage is not None:
        damage['more'].extend(applied)
    result = rawcombat.evaluate(prepared)
    return {'format': 'tli-conditional-combat-report-v1', 'source': copy.deepcopy(ledger['source']),
            'condition': copy.deepcopy(condition), 'coverage': copy.deepcopy(coverage), 'applied_rows': applied,
            'scenario': prepared, 'result': result, 'dps': result['dps'], 'status': result['status'],
            'gaps': list(result['gaps']), 'runtime_verified': False, 'identity_verified': False,
            'import_complete': False, 'arithmetic_ready': False}


def compare(document):
    """Compare prepared variants under one shared condition and source-exclusion claim."""
    _object(document, 'format currency condition coverage baseline candidates', 'Conditional comparison')
    if document['format'] != 'tli-conditional-combat-upgrades-v1':
        raise ValueError('Unsupported conditional combat comparison format')
    _object(document['baseline'], 'combat ledger', 'Conditional baseline')
    if type(document['candidates']) is not list or len(document['candidates']) > 1000:
        raise ValueError('Conditional candidates require a bounded list')
    baseline = evaluate(**document['baseline'], condition=document['condition'], coverage=document['coverage'])
    candidates, preparations = [], []
    for candidate in document['candidates']:
        _object(candidate, 'id name combat ledger cost missing', 'Conditional candidate')
        result = evaluate(candidate['combat'], candidate['ledger'],
                          condition=document['condition'], coverage=document['coverage'])
        candidates.append({'id': candidate['id'], 'name': candidate['name'], 'scenario': result['scenario'],
                           'cost': candidate['cost'], 'missing': candidate['missing']})
        preparations.append({'id': candidate['id'], 'preparation': result})
    result = combatupgrades.evaluate({'format': 'tli-combat-upgrade-scenario-v1', 'currency': document['currency'],
                                     'baseline': baseline['scenario'], 'candidates': candidates})
    return {'format': 'tli-conditional-combat-upgrade-report-v1', 'condition': copy.deepcopy(document['condition']),
            'coverage': copy.deepcopy(document['coverage']), 'preparation': {'baseline': baseline, 'candidates': preparations},
            'result': result, 'status': result['status'], 'ranking': list(result['ranking']),
            'runtime_verified': False, 'identity_verified': False, 'import_complete': False, 'arithmetic_ready': False}
