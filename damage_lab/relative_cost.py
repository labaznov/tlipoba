"""Compute bounded relative gain per explicit scenario price and strict interval dominance.

See docs/RELATIVE_COST.md for structural evidence limits and unsupported player inference.
"""
from __future__ import annotations

from fractions import Fraction

from . import relative as kernel

RESULT_BITS = kernel.LIMITS['maxResultBits']
INPUT_BITS = kernel.LIMITS['maxInputBits']
NAME_CHARS, REF_CHARS, CODE_CHARS = 128, 512, 32
RATIO_KEYS = frozenset(kernel.RESULT_KEYS)
GAIN_KEYS = frozenset({'metric', 'status', 'gain', 'tight', 'amount', 'currency', 'context', 'upgrade', 'ratio',
                       'ratioStatus', 'trace', 'reasons', 'reasonsOmitted', 'limit'})
TRACE_KEYS = frozenset({'productProof', 'invarianceProofs', 'positiveFiniteProofs', 'provenance', 'classifications'})
CONTEXT_KEYS = frozenset({'baseline', 'quantity', 'target'})
RATIO_STATUSES = ('exact', 'interval', 'inconclusive', 'error', 'domain_error', 'resource_limit')
GAIN_STATUSES = ('gain_per_cost', 'no_cost', 'no_positive_gain', 'inconclusive', 'error', 'domain_error',
                 'resource_limit')
RATIO_ERROR_CODES = ('malformed', 'malformed_name', 'unsupported_form', 'empty_changes', 'duplicate_factor_name',
                     'interval_order', 'invariance_contradiction')
LIMIT_CODES = ('factors', 'variables', 'edges', 'changes', 'name_chars', 'ref_chars', 'provenance', 'input_bits',
               'result_bits')
CLASS_CODES = ('no_invariance_claim', 'graph_incomplete', 'depends_on_unknown', 'depends_on_changed',
               'proof_binding_mismatch', 'activation_not_proven', 'positive_finite_missing', 'provenance_missing',
               'changed_factor_unknown', 'activation_unknown')
CLAIM_EXCLUSIVE = frozenset({'graph_incomplete', 'depends_on_unknown', 'depends_on_changed', 'proof_binding_mismatch'})
STATUS_CODES = ('changed_factor_unknown', 'activation_unknown')
INVARIANCE_KINDS = ('dependency_disjoint', 'independent_invariance_proof')
PROVENANCE_KINDS = ('source_contract', 'catalog_row', 'declared_bound')
OWN_CODES = {'error': ('metric_not_ratio', 'malformed_result', 'inconsistent_result', 'malformed_cost'),
             'domain_error': ('negative_price',), 'resource_limit': ('result_bits', 'input_bits')}
FAILURE_CODES = OWN_CODES['error'] + OWN_CODES['domain_error'] + OWN_CODES['resource_limit'] + (
    'price_unknown', 'ratio_not_above_one', 'gain_not_proven_positive', 'zero_price', 'metric_unknown',
    'no_comparable_interval', 'incomparable_metric', 'context_differs', 'currency_differs', 'strict_non_overlap',
    'overlap')


class _Fail(Exception):
    """A fixed, source-free refusal (status, reason); `limit` mirrors the reason for resource_limit."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason
        self.limit = reason if status == 'resource_limit' else None


def _malformed():
    return _Fail('error', 'malformed_result')


def _inconsistent():
    return _Fail('error', 'inconsistent_result')


def _closed(value, keys, fail):
    """Exact dict and length, then every key's exact str type by iteration (no hash/eq), then membership."""
    if type(value) is not dict or len(value) != len(keys):
        raise fail()
    for key in value:
        if type(key) is not str:
            raise fail()
    if not all(key in keys for key in value):
        raise fail()
    return value


def _text(value, limit, fail):
    if type(value) is not str or not 1 <= len(value) <= limit or not all(' ' <= char <= '~' for char in value):
        raise fail()
    return value


def _list(value, maximum, fail):
    if type(value) is not list or len(value) > maximum:
        raise fail()
    return value


def _pair(value, fail):
    if value is None:
        return None
    if type(value) is not tuple or len(value) != 2 or not all(type(bound) is Fraction for bound in value):
        raise fail()
    return value


def _bits(value, limit):
    return value.numerator.bit_length() <= limit and value.denominator.bit_length() <= limit


def _bits_pair(pair, limit, status, reason):
    if pair is not None and not all(_bits(bound, limit) for bound in pair):
        raise _Fail(status, reason)


def _context(value):
    if value is None:
        return None
    _closed(value, CONTEXT_KEYS, _malformed)
    return {key: _text(value[key], NAME_CHARS, _malformed) for key in ('baseline', 'quantity', 'target')}


def _codes(value, maximum):
    return [_text(code, CODE_CHARS, _malformed) for code in _list(value, maximum, _malformed)]


def _shape_trace(value):
    """Phase 1 of a trace: a closed, bounded, detached copy (no predicates)."""
    if value is None:
        return None
    _closed(value, TRACE_KEYS, _malformed)
    product = _closed(value['productProof'], frozenset({'ref'}), _malformed)
    invariance = []
    for proof in _list(value['invarianceProofs'], 64, _malformed):
        _closed(proof, frozenset({'kind', 'ref', 'factor', 'upgrade', 'baseline'}), _malformed)
        if type(proof['kind']) is not str or proof['kind'] not in INVARIANCE_KINDS:
            raise _malformed()
        invariance.append({'kind': proof['kind'], 'ref': _text(proof['ref'], REF_CHARS, _malformed),
                           'factor': _text(proof['factor'], NAME_CHARS, _malformed),
                           'upgrade': _text(proof['upgrade'], NAME_CHARS, _malformed),
                           'baseline': _text(proof['baseline'], NAME_CHARS, _malformed)})
    positive = []
    for proof in _list(value['positiveFiniteProofs'], 64, _malformed):
        _closed(proof, frozenset({'factor', 'ref'}), _malformed)
        positive.append({'factor': _text(proof['factor'], NAME_CHARS, _malformed),
                         'ref': _text(proof['ref'], REF_CHARS, _malformed)})
    provenance = []
    for entry in _list(value['provenance'], 512, _malformed):
        _closed(entry, frozenset({'factor', 'kind', 'ref'}), _malformed)
        if type(entry['kind']) is not str or entry['kind'] not in PROVENANCE_KINDS:
            raise _malformed()
        provenance.append({'factor': _text(entry['factor'], NAME_CHARS, _malformed), 'kind': entry['kind'],
                           'ref': _text(entry['ref'], REF_CHARS, _malformed)})
    classifications = []
    for entry in _list(value['classifications'], 64, _malformed):
        _closed(entry, frozenset({'factor', 'class', 'reasons'}), _malformed)
        if type(entry['class']) is not str or entry['class'] not in ('cancelled', 'retained'):
            raise _malformed()
        reasons = _codes(entry['reasons'], 6)
        if not all(code in CLASS_CODES for code in reasons):
            raise _malformed()
        classifications.append({'factor': _text(entry['factor'], NAME_CHARS, _malformed), 'class': entry['class'],
                                'reasons': reasons})
    return {'productProof': {'ref': _text(product['ref'], REF_CHARS, _malformed)}, 'invarianceProofs': invariance,
            'positiveFiniteProofs': positive, 'provenance': provenance, 'classifications': classifications}


def _common(value, keys, metric, statuses):
    """Phase 1 for the fields both result kinds share; returns a detached copy of them."""
    _closed(value, keys, _malformed)
    if type(value['metric']) is not str or value['metric'] != metric:
        raise _malformed()
    if type(value['status']) is not str or value['status'] not in statuses:
        raise _malformed()
    if value['tight'] is not False:
        raise _malformed()
    upgrade = value['upgrade']
    if type(value['reasonsOmitted']) is not int or (value['limit'] is not None and type(value['limit']) is not str):
        raise _malformed()
    return {'metric': metric, 'status': value['status'], 'tight': False,
            'context': _context(value['context']),
            'upgrade': None if upgrade is None else _text(upgrade, NAME_CHARS, _malformed),
            'trace': _shape_trace(value['trace']), 'reasons': _codes(value['reasons'], 64),
            'reasonsOmitted': value['reasonsOmitted'],
            'limit': None if value['limit'] is None else _text(value['limit'], CODE_CHARS, _malformed)}


def _shape_ratio(value):
    copy = _common(value, RATIO_KEYS, 'ratio', RATIO_STATUSES)
    copy['ratio'] = _pair(value['ratio'], _malformed)
    copy['cancelled'] = [_text(n, NAME_CHARS, _malformed) for n in _list(value['cancelled'], 64, _malformed)]
    copy['changed'] = [_text(n, NAME_CHARS, _malformed) for n in _list(value['changed'], 64, _malformed)]
    return copy


def _check_trace(r):
    """Phase 3 joint consistency of names, proofs, provenance and status codes (structural; no proof content)."""
    trace = r['trace']
    entries = trace['classifications']
    names = [entry['factor'] for entry in entries]
    if len(set(names)) != len(names):
        raise _inconsistent()
    for entry in entries:
        reasons = entry['reasons']
        if entry['class'] == 'cancelled':
            if reasons:
                raise _inconsistent()
            continue
        if not reasons or len(set(reasons)) != len(reasons) or len(CLAIM_EXCLUSIVE.intersection(reasons)) > 1:
            raise _inconsistent()
        if 'no_invariance_claim' in reasons and not set(reasons) - {'no_invariance_claim'} <= set(STATUS_CODES):
            raise _inconsistent()
        # Activation consistency, as 0502 derives both codes from the same unknown activation (task 0545):
        # activation_not_proven implies activation_unknown, and activation_unknown needs activation_not_proven or the
        # early no-claim path. Structural only; nothing is recomputed or verified.
        if 'activation_not_proven' in reasons and 'activation_unknown' not in reasons:
            raise _inconsistent()
        if 'activation_unknown' in reasons and not ('activation_not_proven' in reasons or 'no_invariance_claim' in reasons):
            raise _inconsistent()
    cancelled = [entry['factor'] for entry in entries if entry['class'] == 'cancelled']
    retained = [entry['factor'] for entry in entries if entry['class'] == 'retained']
    if r['cancelled'] != sorted(cancelled) or r['changed'] != sorted(retained):
        raise _inconsistent()
    proofs, positives = trace['invarianceProofs'], trace['positiveFiniteProofs']
    if len(proofs) != len(cancelled) or len(positives) != len(cancelled):
        raise _inconsistent()
    for name, proof, positive in zip(cancelled, proofs, positives):
        if (proof['factor'], proof['upgrade'], proof['baseline']) != (name, r['upgrade'], r['context']['baseline']) \
                or positive['factor'] != name:
            raise _inconsistent()
    index, last, counts = {name: i for i, name in enumerate(names)}, -1, {}
    for entry in trace['provenance']:
        if entry['factor'] not in index or index[entry['factor']] < last:
            raise _inconsistent()
        last = index[entry['factor']]
        counts[last] = counts.get(last, 0) + 1
        if counts[last] > 8:
            raise _inconsistent()
    for name, proof in zip(cancelled, proofs):
        if not any(entry['factor'] == name and (entry['kind'] in ('source_contract', 'catalog_row')
                                                or entry['ref'] == proof['ref']) for entry in trace['provenance']):
            raise _inconsistent()
    occurrences = []
    for entry in entries:
        for code in entry['reasons']:
            if code in STATUS_CODES and code not in occurrences:
                occurrences.append(code)
    if r['status'] in ('exact', 'interval') and occurrences:
        raise _inconsistent()
    if r['status'] == 'inconclusive' and (not occurrences or r['reasons'] != occurrences):
        raise _inconsistent()


def _check_ratio(r):
    """Phase 3 of a ratio result: the per-status table, then the trace consistency (bits were admitted already)."""
    status, ratio, reasons = r['status'], r['ratio'], r['reasons']
    if r['reasonsOmitted'] != 0:
        raise _inconsistent()
    present = r['context'] is not None and r['upgrade'] is not None and r['trace'] is not None
    if status in ('exact', 'interval', 'inconclusive'):
        if not present or r['limit'] is not None or (ratio is None) != (status == 'inconclusive'):
            raise _inconsistent()
        if status != 'inconclusive':
            low, high = ratio
            if reasons or not low > 0 or (status == 'exact' and low != high) or (status == 'interval' and not low < high):
                raise _inconsistent()
        _check_trace(r)
        return
    if ratio is not None or r['context'] is not None or r['upgrade'] is not None or r['trace'] is not None \
            or r['cancelled'] or r['changed'] or len(reasons) != 1:
        raise _inconsistent()
    code = reasons[0]
    allowed = {'error': RATIO_ERROR_CODES, 'domain_error': ('domain',), 'resource_limit': LIMIT_CODES}[status]
    if code not in allowed or r['limit'] != (code if status == 'resource_limit' else None):
        raise _inconsistent()


def _admit_ratio(value):
    r = _shape_ratio(value)                                                      # phase 1
    _bits_pair(r['ratio'], RESULT_BITS, 'resource_limit', 'result_bits')         # phase 2
    _check_ratio(r)                                                              # phase 3
    return r


def _admit_gain(value):
    g = _common(value, GAIN_KEYS, 'gain_per_cost', GAIN_STATUSES)                # phase 1
    g['gain'] = _pair(value['gain'], _malformed)
    amount = value['amount']
    if amount is not None and type(amount) is not Fraction:
        raise _malformed()
    g['amount'] = amount
    g['currency'] = None if value['currency'] is None else _text(value['currency'], NAME_CHARS, _malformed)
    g['ratio'] = _pair(value['ratio'], _malformed)
    status = value['ratioStatus']
    if status is not None and (type(status) is not str or status not in RATIO_STATUSES):
        raise _malformed()
    g['ratioStatus'] = status
    _bits_pair(g['gain'], RESULT_BITS, 'resource_limit', 'result_bits')         # phase 2, in key order
    if amount is not None and not _bits(amount, INPUT_BITS):
        raise _Fail('resource_limit', 'input_bits')
    _bits_pair(g['ratio'], RESULT_BITS, 'resource_limit', 'result_bits')
    _check_gain(g)                                                               # phase 3
    return g


def _projection(g, reasons, limit):
    entries = g['trace']['classifications'] if g['trace'] is not None else []
    return {'status': g['ratioStatus'], 'ratio': g['ratio'], 'context': g['context'], 'upgrade': g['upgrade'],
            'trace': g['trace'], 'reasons': reasons, 'limit': limit, 'reasonsOmitted': 0,
            'cancelled': sorted(e['factor'] for e in entries if e['class'] == 'cancelled'),
            'changed': sorted(e['factor'] for e in entries if e['class'] == 'retained')}


def _check_gain(g):
    status, ratio_status, reasons = g['status'], g['ratioStatus'], g['reasons']
    if g['reasonsOmitted'] != 0:
        raise _inconsistent()
    if ratio_status is None:                                                     # own refusal: no embedded ratio
        if status not in OWN_CODES or len(reasons) != 1 or reasons[0] not in OWN_CODES[status] or any(
                g[key] is not None for key in ('gain', 'amount', 'currency', 'context', 'upgrade', 'ratio', 'trace')) \
                or g['limit'] != (reasons[0] if status == 'resource_limit' else None):
            raise _inconsistent()
        return
    priced = g['amount'] is not None
    if priced != (g['currency'] is not None) or (priced and g['amount'] < 0):
        raise _inconsistent()
    if ratio_status not in ('exact', 'interval'):                                # passthrough
        if status != ratio_status or g['gain'] is not None:
            raise _inconsistent()
        _check_ratio(_projection(g, reasons, g['limit']))
        return
    _check_ratio(_projection(g, [], None))
    if g['limit'] is not None or status not in ('gain_per_cost', 'no_cost', 'no_positive_gain', 'inconclusive'):
        raise _inconsistent()
    low, high = g['ratio']
    if status == 'gain_per_cost':
        if not priced or g['gain'] is None or reasons or not g['amount'] > 0 or not low > 1:
            raise _inconsistent()
        gain_low, gain_high = g['gain']
        if not gain_low > 0 or not gain_low <= gain_high or (gain_low == gain_high) != (ratio_status == 'exact'):
            raise _inconsistent()
        return
    if g['gain'] is not None:
        raise _inconsistent()
    if status == 'no_cost':
        ok = priced and g['amount'] == 0 and low > 1 and reasons == ['zero_price']
    elif status == 'no_positive_gain':
        ok = priced and high <= 1 and reasons == ['ratio_not_above_one']
    elif reasons == ['price_unknown']:
        ok = not priced
    else:
        ok = priced and reasons == ['gain_not_proven_positive'] and low <= 1 < high
    if not ok:
        raise _inconsistent()


def _admit_cost(cost):
    """None (unknown price), or (amount, currency): malformed, then bits, then sign."""
    if cost is None:
        return None, None

    def fail():
        return _Fail('error', 'malformed_cost')
    _closed(cost, frozenset({'amount', 'currency'}), fail)
    amount = cost['amount']
    if type(amount) is not Fraction:
        raise fail()
    currency = _text(cost['currency'], NAME_CHARS, fail)
    if not _bits(amount, INPUT_BITS):
        raise _Fail('resource_limit', 'input_bits')
    if amount < 0:
        raise _Fail('domain_error', 'negative_price')
    return amount, currency


def _gain(status, *, gain=None, amount=None, currency=None, r=None, reasons=(), limit=None, ratio_status=None):
    return {'metric': 'gain_per_cost', 'status': status, 'gain': gain, 'tight': False, 'amount': amount,
            'currency': currency, 'context': None if r is None else r['context'],
            'upgrade': None if r is None else r['upgrade'],
            'ratio': None if r is None else r['ratio'], 'ratioStatus': ratio_status,
            'trace': None if r is None else r['trace'], 'reasons': list(reasons), 'reasonsOmitted': 0, 'limit': limit}


def _own(failure):
    return _gain(failure.status, reasons=[failure.reason], limit=failure.limit)


def _estimate(value, amount):
    numerator = max(value.numerator.bit_length(), value.denominator.bit_length()) + 1 + amount.denominator.bit_length()
    return max(numerator, value.denominator.bit_length() + amount.numerator.bit_length())


def per_cost(result, cost):
    """Relative gain per unit cost of one ratio result, with the fixed precedence of docs/RELATIVE_COST.md."""
    try:
        # The count is admitted BEFORE any key traversal (task 0545): only the exact 14-key gain shape can be probed.
        if type(result) is dict and len(result) == len(GAIN_KEYS) and all(type(key) is str for key in result) \
                and 'metric' in result and type(result['metric']) is str and result['metric'] == 'gain_per_cost':
            raise _Fail('error', 'metric_not_ratio')
        r = _admit_ratio(result)
        amount, currency = _admit_cost(cost)
    except _Fail as failure:
        return _own(failure)
    if r['status'] not in ('exact', 'interval'):                                 # passthrough of a non-comparable ratio
        return _gain(r['status'], amount=amount, currency=currency, r=r, reasons=r['reasons'], limit=r['limit'],
                     ratio_status=r['status'])
    status = r['status']
    if amount is None:
        return _gain('inconclusive', r=r, reasons=['price_unknown'], ratio_status=status)
    low, high = r['ratio']
    if high <= 1:
        return _gain('no_positive_gain', amount=amount, currency=currency, r=r, reasons=['ratio_not_above_one'],
                     ratio_status=status)
    if low <= 1:
        return _gain('inconclusive', amount=amount, currency=currency, r=r, reasons=['gain_not_proven_positive'],
                     ratio_status=status)
    if amount == 0:
        return _gain('no_cost', amount=amount, currency=currency, r=r, reasons=['zero_price'], ratio_status=status)
    if max(_estimate(low, amount), _estimate(high, amount)) > RESULT_BITS:     # before any subtraction or division
        return _own(_Fail('resource_limit', 'result_bits'))
    return _gain('gain_per_cost', gain=((low - 1) / amount, (high - 1) / amount), amount=amount, currency=currency,
                 r=r, ratio_status=status)


def _metric(value):
    # The count is capped BEFORE any key traversal (task 0545): at most the 14 keys of the largest admitted shape are
    # ever visited; a larger mapping is malformed_result without traversal. A small mapping with an unknown metric
    # keeps its metric_unknown code.
    if type(value) is not dict or len(value) > len(GAIN_KEYS) or not all(type(key) is str for key in value):
        raise _malformed()
    metric = value.get('metric')
    if type(metric) is not str or metric not in ('ratio', 'gain_per_cost'):
        raise _Fail('error', 'metric_unknown')
    return metric


def dominates(a, b):
    """Strict interval dominance between two comparable results; never ranks free, unpriced or refused results."""
    admitted = []
    for side, value in (('a', a), ('b', b)):
        try:
            metric = _metric(value)
            admitted.append((metric, _admit_ratio(value) if metric == 'ratio' else _admit_gain(value)))
        except _Fail as failure:
            return {'winner': None, 'status': failure.status, 'reason': failure.reason, 'side': side}

    def comparable(metric, result):
        return result['status'] in ('exact', 'interval') if metric == 'ratio' else result['status'] == 'gain_per_cost'

    def verdict(status, reason, winner=None):
        return {'winner': winner, 'status': status, 'reason': reason, 'side': None}

    (metric_a, first), (metric_b, second) = admitted
    if not comparable(metric_a, first) or not comparable(metric_b, second):
        return verdict('inconclusive', 'no_comparable_interval')
    if metric_a != metric_b:
        return verdict('incomparable', 'incomparable_metric')
    if first['context'] != second['context']:
        return verdict('incomparable', 'context_differs')
    if metric_a == 'gain_per_cost' and first['currency'] != second['currency']:
        return verdict('incomparable', 'currency_differs')
    key = 'ratio' if metric_a == 'ratio' else 'gain'
    (a_low, a_high), (b_low, b_high) = first[key], second[key]
    if a_low > b_high:
        return verdict('dominates', 'strict_non_overlap', 'a')
    if b_low > a_high:
        return verdict('dominates', 'strict_non_overlap', 'b')
    return verdict('inconclusive', 'overlap')
