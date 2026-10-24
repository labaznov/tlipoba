"""Compute bounded exact relative ratios under caller-asserted product and invariance proofs.

See docs/RELATIVE_GAIN.md for admission, evidence obligations and unsupported player inference.
"""
from __future__ import annotations

from fractions import Fraction

LIMITS = {'maxFactors': 64, 'maxVariables': 1024, 'maxEdges': 8192, 'maxChanges': 256, 'maxNameChars': 128,
          'maxRefChars': 512, 'maxProvenance': 8, 'maxInputBits': 256, 'maxResultBits': 12288, 'maxReasons': 64}
MODEL_KEYS = frozenset({'form', 'proof', 'factors', 'context'})
CONTEXT_KEYS = frozenset({'baseline', 'quantity', 'target'})
FACTOR_KEYS = frozenset({'name', 'dependsOn', 'activation', 'old', 'new', 'positiveFinite', 'invariance', 'provenance'})
INVARIANCE_KEYS = frozenset({'kind', 'ref', 'factor', 'upgrade', 'baseline'})
GRAPH_KEYS = frozenset({'edges', 'complete'})
UPGRADE_KEYS = frozenset({'id', 'changes'})
ACTIVATIONS = ('always', 'proven_same', 'unknown')
INVARIANCE_KINDS = ('dependency_disjoint', 'independent_invariance_proof')
PROVENANCE_KINDS = ('source_contract', 'catalog_row', 'declared_bound')
# Every fixed public reason code (each at most 32 characters); results never carry any other text.
REASON_CODES = ('malformed', 'malformed_name', 'unsupported_form', 'empty_changes', 'duplicate_factor_name',
                'interval_order', 'domain', 'invariance_contradiction', 'factors', 'variables', 'edges', 'changes',
                'name_chars', 'ref_chars', 'provenance', 'input_bits', 'result_bits', 'no_invariance_claim',
                'graph_incomplete', 'depends_on_unknown', 'depends_on_changed', 'proof_binding_mismatch',
                'activation_not_proven', 'positive_finite_missing', 'provenance_missing', 'changed_factor_unknown',
                'activation_unknown')
RESULT_KEYS = ('metric', 'status', 'ratio', 'tight', 'context', 'upgrade', 'cancelled', 'changed', 'trace', 'reasons',
               'reasonsOmitted', 'limit')


class _Refusal(Exception):
    """A fixed refusal outcome: status error / domain_error / resource_limit with one fixed reason code."""

    def __init__(self, status, reason, limit=None):
        super().__init__(reason)
        self.status, self.reason, self.limit = status, reason, limit


def _malformed():
    return _Refusal('error', 'malformed')


def _closed(value, keys):
    """An exact dict with exactly `keys`: every key's exact str type is admitted first (iteration neither hashes nor
    compares keys), and only then is membership tested, so a foreign key's __hash__ / __eq__ never runs."""
    if type(value) is not dict or len(value) != len(keys):
        raise _malformed()
    for key in value:
        if type(key) is not str:
            raise _malformed()
    if not all(key in keys for key in value):
        raise _malformed()
    return value


def _names(items):
    """Names from an unordered collection, refused by fixed tiers over ALL items so that iteration order (which
    depends on the hash seed) never decides the code: exact types, then lengths, then characters. Nothing is
    hashed or sorted before every item is admitted."""
    items = list(items)
    if not all(type(item) is str for item in items):
        raise _malformed()
    if any(len(item) > LIMITS['maxNameChars'] for item in items):
        raise _Refusal('resource_limit', 'name_chars', 'name_chars')
    if not all(item and all(' ' <= char <= '~' for char in item) for item in items):
        raise _Refusal('error', 'malformed_name')
    return items


def _text(value, limit, limit_name):
    """A non-empty printable-ASCII str: type, then length (before any character scan), then characters."""
    if type(value) is not str:
        raise _malformed()
    if len(value) > LIMITS[limit]:
        raise _Refusal('resource_limit', limit_name, limit_name)
    if not value or not all(' ' <= char <= '~' for char in value):
        raise _Refusal('error', 'malformed_name')
    return value


def _name(value):
    return _text(value, 'maxNameChars', 'name_chars')


def _ref(value):
    return _text(value, 'maxRefChars', 'ref_chars')


def _ref_holder(value):
    return _ref(_closed(value, frozenset({'ref'}))['ref'])


def _interval(value):
    if value is None:
        return None
    if type(value) is not tuple or len(value) != 2 or not all(type(bound) is Fraction for bound in value):
        raise _malformed()
    for bound in value:                                  # bit lengths only: no comparison, no arithmetic
        if bound.numerator.bit_length() > LIMITS['maxInputBits'] or bound.denominator.bit_length() > LIMITS['maxInputBits']:
            raise _Refusal('resource_limit', 'input_bits', 'input_bits')
    return value


def _bounded(container, kind, limit, limit_name):
    """The container's own type and size, checked before any child is visited."""
    if type(container) is not kind:
        raise _malformed()
    if len(container) > LIMITS[limit]:
        raise _Refusal('resource_limit', limit_name, limit_name)
    return container


class _Variables:
    """The distinct names of dependsOn, edges and changes, capped at maxVariables (only admitted names are added)."""

    def __init__(self):
        self.seen = set()

    def add(self, name):
        self.seen.add(name)
        if len(self.seen) > LIMITS['maxVariables']:
            raise _Refusal('resource_limit', 'variables', 'variables')


def _admit_factor(raw, variables):
    _closed(raw, FACTOR_KEYS)
    name = _name(raw['name'])
    depends = raw['dependsOn']
    if depends is not None:
        for item in _names(_bounded(depends, frozenset, 'maxVariables', 'variables')):
            variables.add(item)
    if type(raw['activation']) is not str or raw['activation'] not in ACTIVATIONS:
        raise _malformed()
    old, new = _interval(raw['old']), _interval(raw['new'])
    positive = None if raw['positiveFinite'] is None else _ref_holder(raw['positiveFinite'])
    invariance = raw['invariance']
    if invariance is not None:
        _closed(invariance, INVARIANCE_KEYS)
        if type(invariance['kind']) is not str or invariance['kind'] not in INVARIANCE_KINDS:
            raise _malformed()
        invariance = {'kind': invariance['kind'], 'ref': _ref(invariance['ref']), 'factor': _name(invariance['factor']),
                      'upgrade': _name(invariance['upgrade']), 'baseline': _name(invariance['baseline'])}
    provenance = []
    for entry in _bounded(raw['provenance'], list, 'maxProvenance', 'provenance'):
        _closed(entry, frozenset({'kind', 'ref'}))
        if type(entry['kind']) is not str or entry['kind'] not in PROVENANCE_KINDS:
            raise _malformed()
        provenance.append({'kind': entry['kind'], 'ref': _ref(entry['ref'])})
    return {'name': name, 'dependsOn': None if depends is None else frozenset(depends), 'activation': raw['activation'],
            'old': old, 'new': new, 'positiveFinite': positive, 'invariance': invariance, 'provenance': provenance}


def _admit(model, graph, upgrade):
    """Phase A in a fixed traversal order (model, its factors in order, graph, upgrade); the first failure decides."""
    variables = _Variables()
    _closed(model, MODEL_KEYS)
    if type(model['form']) is not str:
        raise _malformed()
    if model['form'] != 'product':
        raise _Refusal('error', 'unsupported_form')
    product_ref = _ref_holder(model['proof'])
    factors = [_admit_factor(raw, variables) for raw in _bounded(model['factors'], list, 'maxFactors', 'factors')]
    context = _closed(model['context'], CONTEXT_KEYS)
    context = {key: _name(context[key]) for key in ('baseline', 'quantity', 'target')}
    _closed(graph, GRAPH_KEYS)
    raw_edges = list(_bounded(graph['edges'], frozenset, 'maxEdges', 'edges'))
    if not all(type(edge) is tuple and len(edge) == 2 for edge in raw_edges):
        raise _malformed()
    _names([end for edge in raw_edges for end in edge])         # tiers over every endpoint before any hashing
    edges = [(source, target) for source, target in raw_edges]
    for source, target in edges:
        variables.add(source)
        variables.add(target)
    if type(graph['complete']) is not bool:
        raise _malformed()
    _closed(upgrade, UPGRADE_KEYS)
    upgrade_id = _name(upgrade['id'])
    changes = _bounded(upgrade['changes'], frozenset, 'maxChanges', 'changes')
    if not changes:
        raise _Refusal('error', 'empty_changes')
    for change in _names(changes):
        variables.add(change)
    names = [f['name'] for f in factors]
    if len(set(names)) != len(names):                    # A5: before any proof binding
        raise _Refusal('error', 'duplicate_factor_name')
    return {'productRef': product_ref, 'factors': factors, 'context': context, 'edges': edges,
            'complete': graph['complete'], 'upgrade': upgrade_id, 'changes': frozenset(changes)}


def _validate_numbers(factors):
    """Phase B on admitted (bounded) intervals; each comparison multiplies at most 256-bit integers."""
    for factor in factors:
        for interval in (factor['old'], factor['new']):
            if interval is None:
                continue
            low, high = interval
            if low > high:
                raise _Refusal('error', 'interval_order')
            if low <= 0:
                raise _Refusal('domain_error', 'domain')


def _closure(changes, edges):
    successors = {}
    for source, target in edges:
        successors.setdefault(source, []).append(target)
    reached, frontier = set(changes), list(changes)
    while frontier:                                       # a visited set: cycles terminate, O(V + E)
        for target in successors.get(frontier.pop(), ()):
            if target not in reached:
                reached.add(target)
                frontier.append(target)
    return reached


def _classify(factor, admitted, closure):
    """Why a factor does not cancel ([] means it cancels); the contradiction check is applied by the caller."""
    invariance, reasons = factor['invariance'], []
    if invariance is None:
        return ['no_invariance_claim']
    if invariance['kind'] == 'dependency_disjoint':
        if not admitted['complete']:
            reasons.append('graph_incomplete')
        elif factor['dependsOn'] is None:
            reasons.append('depends_on_unknown')
        elif factor['dependsOn'] & closure:
            reasons.append('depends_on_changed')
    elif (invariance['factor'], invariance['upgrade'], invariance['baseline']) != \
            (factor['name'], admitted['upgrade'], admitted['context']['baseline']):
        reasons.append('proof_binding_mismatch')
    if factor['activation'] not in ('always', 'proven_same'):
        reasons.append('activation_not_proven')
    if factor['positiveFinite'] is None:
        reasons.append('positive_finite_missing')
    if not any(p['kind'] in ('source_contract', 'catalog_row') or p['ref'] == invariance['ref']
               for p in factor['provenance']):
        reasons.append('provenance_missing')
    return reasons


def _refused(refusal):
    return {'metric': 'ratio', 'status': refusal.status, 'ratio': None, 'tight': False, 'context': None,
            'upgrade': None, 'cancelled': [], 'changed': [], 'trace': None, 'reasons': [refusal.reason],
            'reasonsOmitted': 0, 'limit': refusal.limit}


def relative(model, graph, upgrade):
    """The exact relative ratio of one declared upgrade under a declared product model; see the module docstring."""
    try:
        admitted = _admit(model, graph, upgrade)
        factors = admitted['factors']
        _validate_numbers(factors)
        closure = _closure(admitted['changes'], admitted['edges'])
        classifications, cancelled, retained = [], [], []
        for factor in factors:
            reasons = _classify(factor, admitted, closure)
            if not reasons and factor['old'] is not None and factor['new'] is not None:
                (old_low, old_high), (new_low, new_high) = factor['old'], factor['new']
                if max(old_low, new_low) > min(old_high, new_high):      # only for an applicable claim
                    raise _Refusal('error', 'invariance_contradiction')
            if not reasons:
                cancelled.append(factor)
            else:
                if factor['old'] is None or factor['new'] is None:
                    reasons.append('changed_factor_unknown')
                if factor['activation'] == 'unknown':
                    reasons.append('activation_unknown')
                retained.append(factor)
            classifications.append({'factor': factor['name'], 'class': 'cancelled' if not reasons else 'retained',
                                    'reasons': reasons})
    except _Refusal as refusal:
        return _refused(refusal)
    status_reasons = []
    for entry in classifications:
        for code in entry['reasons']:
            if code in ('changed_factor_unknown', 'activation_unknown') and code not in status_reasons:
                status_reasons.append(code)
    trace = {'productProof': {'ref': admitted['productRef']},
             # The ACTUAL binding the cancellation relied on: for dependency_disjoint the graph, not the declared
             # fields, licenses it, so the declared factor/upgrade/baseline are never echoed as the binding.
             'invarianceProofs': [{'kind': f['invariance']['kind'], 'ref': f['invariance']['ref'], 'factor': f['name'],
                                   'upgrade': admitted['upgrade'], 'baseline': admitted['context']['baseline']}
                                  for f in cancelled],
             'positiveFiniteProofs': [{'factor': f['name'], 'ref': f['positiveFinite']} for f in cancelled],
             'provenance': [{'factor': f['name'], **p} for f in factors for p in f['provenance']],
             'classifications': classifications}
    result = {'metric': 'ratio', 'status': None, 'ratio': None, 'tight': False, 'context': dict(admitted['context']),
              'upgrade': admitted['upgrade'], 'cancelled': sorted(f['name'] for f in cancelled),
              'changed': sorted(f['name'] for f in retained), 'trace': trace,
              'reasons': status_reasons[:LIMITS['maxReasons']],
              'reasonsOmitted': max(0, len(status_reasons) - LIMITS['maxReasons']), 'limit': None}
    if status_reasons:
        result['status'] = 'inconclusive'
        return result
    # Phase D: conservative bit estimate of each product, before any multiplication (cancelled factors excluded).
    estimates = [0, 0, 0, 0]
    for factor in retained:
        (old_low, old_high), (new_low, new_high) = factor['old'], factor['new']
        estimates[0] += new_low.numerator.bit_length() + old_high.denominator.bit_length()
        estimates[1] += new_low.denominator.bit_length() + old_high.numerator.bit_length()
        estimates[2] += new_high.numerator.bit_length() + old_low.denominator.bit_length()
        estimates[3] += new_high.denominator.bit_length() + old_low.numerator.bit_length()
    if max(estimates, default=0) > LIMITS['maxResultBits']:
        return _refused(_Refusal('resource_limit', 'result_bits', 'result_bits'))
    low = high = Fraction(1)
    exact = True
    for factor in retained:
        (old_low, old_high), (new_low, new_high) = factor['old'], factor['new']
        low *= new_low / old_high
        high *= new_high / old_low
        exact = exact and old_low == old_high and new_low == new_high
    result.update(status='exact' if exact else 'interval', ratio=(low, high))
    return result
