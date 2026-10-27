"""Bound four research hypotheses using caller-asserted exact intervals.

compare(before, after, observed, *, invariant) encloses, for each fixed candidate, the ratio F(after)/F(before) of

    H0: s*r*(1 + p(m-1))        H1: s*r*(1 + q(m-1)), q = 2p - p**2
    H2: s*r*((1-p) + p*m*(1+k))  H3: a*r*(1 + p(m-1))

from caller-asserted exact rational intervals, and marks it compatible or incompatible with an observed ratio
interval (inclusive overlap). These are hypotheses, not game formulas. Nothing is selected, no common factor K is
estimated and nothing is fitted. invariant=True is the CALLER'S assumption of one common positive K across both
states, never verified. Bounds are caller assertions, never inferred from printed digits. The enclosures are
general (each state bounded independently), not joint-tight, and say nothing causal.

Every input is validated before candidate arithmetic, whatever invariant is; a refusal is one fixed ValueError.
Validation comparisons use endpoints whose numerator and denominator sizes have already been bounded.
"""
from __future__ import annotations

from fractions import Fraction

FORMAT = 'tli-panel-hypotheses-v1'
MODELS = ('H0', 'H1', 'H2', 'H3')
FIELDS = ('s', 'a', 'r', 'p', 'm', 'k')
NEEDS = {'H0': ('s', 'r', 'p', 'm'), 'H1': ('s', 'r', 'p', 'm'), 'H2': ('s', 'r', 'p', 'm', 'k'),
         'H3': ('a', 'r', 'p', 'm')}
MAX_BITS = 128
ERROR = 'panel hypotheses input malformed'


def _interval(value):
    """An exact (low, high) tuple of exact Fractions with bounded parts and low <= high; else a refusal."""
    if (type(value) is not tuple or len(value) != 2 or not all(type(bound) is Fraction for bound in value)
            or not all(abs(bound.numerator).bit_length() <= MAX_BITS and bound.denominator.bit_length() <= MAX_BITS
                       for bound in value) or value[0] > value[1]):
        raise ValueError(ERROR)
    return value


def _state(value):
    """The six fields exactly, each None (unknown) or an interval inside its domain."""
    if type(value) is not dict or len(value) != len(FIELDS) or not all(type(key) is str for key in value) \
            or set(value) != set(FIELDS):
        raise ValueError(ERROR)
    out = {}
    for key in FIELDS:
        if value[key] is None:
            out[key] = None
            continue
        low, high = _interval(value[key])
        if ((key in ('s', 'a', 'r', 'm') and low <= 0) or (key == 'p' and (low < 0 or high > 1))
                or (key == 'k' and low < -1)):
            raise ValueError(ERROR)
        out[key] = (low, high)
    return out


def _mul(x, y):
    """Product of two nonnegative intervals."""
    return (x[0] * y[0], x[1] * y[1])


def _critical(p, multiplier):
    """(1 - p) + p*M = 1 + p(M - 1), bilinear in (p, M): its range over a box is attained at the corners, so no
    dependent interval subtraction widens it or produces a false negative bound."""
    corners = [1 + pv * (mv - 1) for pv in p for mv in multiplier]
    return (min(corners), max(corners))


def _q(p):
    """q = 2p - p**2 is nondecreasing on [0, 1], so its interval is exactly the endpoint transformation."""
    return tuple(2 * value - value * value for value in p)


def _factor(name, x):
    """The candidate's factor interval, or None when its lower bound is not strictly positive."""
    base = x['a'] if name == 'H3' else x['s']
    if name == 'H1':
        critical = _critical(_q(x['p']), x['m'])
    elif name == 'H2':
        critical = _critical(x['p'], _mul(x['m'], (1 + x['k'][0], 1 + x['k'][1])))   # M = m(1+k) >= 0
    else:
        critical = _critical(x['p'], x['m'])
    factor = _mul(_mul(base, x['r']), critical)
    return factor if factor[0] > 0 else None


def compare(before, after, observed, *, invariant):
    before, after = _state(before), _state(after)
    if observed is not None and _interval(observed)[0] <= 0:
        raise ValueError(ERROR)
    if invariant is not None and type(invariant) is not bool:
        raise ValueError(ERROR)
    models = {}
    for name in MODELS:
        if invariant is not True:
            reason = 'invariance_not_asserted' if invariant is None else 'invariance_conflict'
            models[name] = {'ratio': None, 'relation': 'unknown', 'reason': reason}
            continue
        if any(before[key] is None or after[key] is None for key in NEEDS[name]):
            models[name] = {'ratio': None, 'relation': 'unknown', 'reason': 'input_missing'}
            continue
        low, high = _factor(name, before), _factor(name, after)
        if low is None or high is None:
            models[name] = {'ratio': None, 'relation': 'unknown', 'reason': 'nonpositive_factor'}
            continue
        ratio = (high[0] / low[1], high[1] / low[0])
        if observed is None:
            models[name] = {'ratio': ratio, 'relation': 'unknown', 'reason': 'observation_missing'}
            continue
        overlap = ratio[0] <= observed[1] and observed[0] <= ratio[1]
        models[name] = {'ratio': ratio, 'relation': 'compatible' if overlap else 'incompatible', 'reason': None}
    available = any(model['ratio'] is not None for model in models.values())
    status = 'conditional' if invariant is True and observed is not None and available else 'inconclusive'
    return {'format': FORMAT, 'status': status, 'bounds': 'caller_asserted', 'selected': None, 'models': models}
