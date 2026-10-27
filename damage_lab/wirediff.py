"""Verify two source byte references and retain only producer-reported comparison counts.

See docs/NATIVE_DIFF.md for evidence limits and the separate diagnostic command.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter

FORMAT = 'tli-native-wire-diff-summary-v1'
VERSION = '0.1.0'
PRODUCER = {'format': 'tli-native-wire-diff-v0', 'version': '0.1.0'}
DECODER = {'format': 'tli-native-stats-v1', 'version': '0.2.0'}
LIMITS = {'maxArtifactBytes': 2 ** 20, 'maxSourceBytes': 16 * 2 ** 20, 'maxDepth': 64, 'maxTokens': 100_000,
          'maxNumberToken': 64, 'maxRows': 8192, 'maxSuppressed': 2048, 'maxOmittedPerState': 4096,
          'maxDigits': 632, 'maxSegments': 5, 'maxField': 2 ** 29 - 1}
STATUSES = ('unchanged', 'changed', 'signed_zero_changed', 'type_changed', 'added_absent_vs_default_unknown',
            'removed_absent_vs_default_unknown', 'ambiguous_repeated_stat', 'ambiguous_repeated_wire',
            'opaque_not_compared', 'omitted_not_compared')
CODES = frozenset(('input_type', 'artifact_too_large', 'source_too_large', 'artifact_token_limit',
                   'artifact_json_malformed', 'artifact_schema', 'producer_unsupported', 'status_unsupported',
                   'rows_limit', 'row_schema', 'counts_mismatch', 'source_mismatch'))
TOP_KEYS = frozenset(('format', 'version', 'status', 'reason', 'side', 'sources', 'decoder', 'identity', 'counts',
                      'rows', 'flags'))
ROW_KEYS = frozenset(('key', 'status', 'beforeType', 'afterType', 'before', 'after', 'delta', 'ratio'))
PRODUCER_FLAGS = {'semanticIdentity': 'unknown', 'selection': 'unknown', 'atomicity': 'unknown',
                  'currentness': 'unknown', 'labelsPromoted': False, 'confounding': 'judged_by_input_diff_only'}
IDENTITY = {'compared': {'author': 'typed_match', 'version': 'equal', 'binding': 'author_only'},
            'identical_sources': {'author': None, 'version': None, 'binding': 'author_only'}}
OMISSIONS = ('account identifier', 'free text string')
NUMERIC = ('varint', 'float32', 'float64')
FLOATS = ('float32', 'float64')
OPAQUE = ('itemBaseId', 'bytes')
ZERO = {'num': '0', 'den': '1'}
SHA256 = re.compile(r'[0-9a-f]{64}')
NUM = re.compile(r'-?(?:0|[1-9][0-9]*)')                                   # ASCII digits only; '-0' refused below
DEN = re.compile(r'[1-9][0-9]*')
PATH = re.compile(r'1(?:\.[1-9][0-9]{0,8}){1,4}')                          # root 1, then 1..4 canonical field numbers
OUTSIDE = re.compile(rb'["\[\]{},:]')
INSIDE = re.compile(rb'["\\]')


class SummaryError(ValueError):
    """A fixed refusal: the message is the code alone, so no input text, value or callback result is echoed."""

    def __init__(self, code):
        if code not in CODES:
            raise AssertionError('unknown summary code')
        super().__init__(code)
        self.code = code


def _lexical(data):
    """One forward pass before any parse: depth at most 64 and at most 100,000 keys plus values.

    Every key and every value except the root follows exactly one of `[ { , :` outside strings, so their number is at
    most that count plus one. Each byte is examined at most once; an unterminated string or dangling escape is refused.
    """
    position, depth, count, size = 0, 0, 0, len(data)
    while True:
        mark = OUTSIDE.search(data, position)
        if mark is None:
            return
        position = mark.end()
        byte = mark.group()
        if byte == b'"':
            while True:
                inner = INSIDE.search(data, position)
                if inner is None or (inner.group() == b'\\' and inner.end() >= size):
                    raise SummaryError('artifact_json_malformed')
                position = inner.end() + (inner.group() == b'\\')
                if inner.group() == b'"':
                    break
            continue
        if byte in b'[{':
            depth += 1
            if depth > LIMITS['maxDepth']:
                raise SummaryError('artifact_json_malformed')
        elif byte in b']}':
            depth -= 1
        if byte in b'[{,:':
            count += 1
            if count + 1 > LIMITS['maxTokens']:
                raise SummaryError('artifact_token_limit')


def _parse(data):
    """Strict JSON through stdlib hooks: no duplicate keys, NaN or Infinity, long number tokens or non-finite floats."""
    _lexical(data)

    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise SummaryError('artifact_json_malformed')
            obj[key] = value
        return obj

    def number(token):
        if len(token) > LIMITS['maxNumberToken'] or not math.isfinite(float(token)):
            raise SummaryError('artifact_json_malformed')
        return float(token)

    def integer(token):
        if len(token) > LIMITS['maxNumberToken']:
            raise SummaryError('artifact_json_malformed')
        return int(token)

    def constant(_token):
        raise SummaryError('artifact_json_malformed')

    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_float=number, parse_int=integer,
                          parse_constant=constant)
    except SummaryError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise SummaryError('artifact_json_malformed') from None


def _exact(value, keys):
    return type(value) is dict and set(value) == set(keys)


def _same(value, expected):
    """Exact equality with exact types (so 0 never equals False and 1 never equals True)."""
    return _exact(value, expected) and all(type(value[key]) is type(item) and value[key] == item
                                           for key, item in expected.items())


def _count(value, high):
    return type(value) is int and 0 <= value <= high


def _rational(value):
    if not (_exact(value, ('num', 'den')) and type(value['num']) is str and type(value['den']) is str):
        return False
    num, den = value['num'], value['den']
    return (len(num) <= LIMITS['maxDigits'] + 1 and len(den) <= LIMITS['maxDigits'] and NUM.fullmatch(num) is not None
            and num != '-0' and len(num.lstrip('-')) <= LIMITS['maxDigits'] and DEN.fullmatch(den) is not None)


def _key(key):
    """The canonical sort key (0, statId) or (1, field tuple); None when the key is not admitted."""
    if _exact(key, ('kind', 'statId')) and type(key['kind']) is str and key['kind'] == 'stat':
        stat_id = key['statId']
        return (0, stat_id) if type(stat_id) is int and 0 <= stat_id < 2 ** 64 else None
    if _exact(key, ('kind', 'path')) and type(key['kind']) is str and key['kind'] == 'wire':
        path = key['path']
        if type(path) is not str or len(path) > LIMITS['maxSegments'] * 10 or PATH.fullmatch(path) is None:
            return None
        fields = tuple(int(segment) for segment in path.split('.'))     # at most 9 ASCII digits each
        return (1, fields) if all(field <= LIMITS['maxField'] for field in fields) else None
    return None


def _payload(status, stat, kinds, numbers):
    """The per-status matrix: which types and which of before/after/delta/ratio must be present."""
    before_type, after_type = kinds
    before, after, delta, ratio = numbers
    present = tuple(value is not None for value in numbers)
    if status == 'unchanged':
        return before_type == after_type in NUMERIC and present == (True, True, False, False) and before == after
    if status == 'changed':
        return (before_type == after_type in NUMERIC and present[:3] == (True, True, True)
                and present[3] == (before['num'] != '0'))
    if status == 'signed_zero_changed':
        return before_type == after_type in FLOATS and before == after == delta == ZERO and ratio is None
    if status == 'type_changed':
        return before_type in NUMERIC and after_type in NUMERIC and before_type != after_type and not any(present)
    if status == 'added_absent_vs_default_unknown':
        return before_type is None and after_type in NUMERIC and present == (False, True, False, False)
    if status == 'removed_absent_vs_default_unknown':
        return after_type is None and before_type in NUMERIC and present == (True, False, False, False)
    if status == 'opaque_not_compared':
        return (not stat and not any(present) and (before_type in OPAQUE or after_type in OPAQUE)
                and all(kind is None or kind in NUMERIC + OPAQUE for kind in kinds))
    if status == 'ambiguous_repeated_stat' and not stat or status == 'ambiguous_repeated_wire' and stat:
        return False
    return kinds == (None, None) and not any(present)                    # ambiguous_* and omitted_not_compared


def _rows(rows):
    if type(rows) is not list:
        raise SummaryError('artifact_schema')
    if len(rows) > LIMITS['maxRows']:
        raise SummaryError('rows_limit')                                # checked before any row is walked
    previous = None
    for item in rows:
        if not _exact(item, ROW_KEYS):
            raise SummaryError('row_schema')
        order = _key(item['key'])
        status, kinds = item['status'], (item['beforeType'], item['afterType'])
        numbers = (item['before'], item['after'], item['delta'], item['ratio'])
        if (order is None or (previous is not None and order <= previous) or type(status) is not str
                or status not in STATUSES
                or not all(kind is None or (type(kind) is str and kind in NUMERIC + OPAQUE) for kind in kinds)
                or (order[0] == 0 and not all(kind in (None, 'float64') for kind in kinds))
                or not all(value is None or _rational(value) for value in numbers)
                or not _payload(status, order[0] == 0, kinds, numbers)):
            raise SummaryError('row_schema')
        previous = order
    return Counter(item['status'] for item in rows)


def _counts(counts, rows, statuses, compared):
    """Reconcile the reported counts exactly with the rows; return a new copy."""
    if not (_exact(counts, ('rows', 'byStatus', 'omitted', 'privacySuppressedKeys'))
            and type(counts['rows']) is int and counts['rows'] == len(rows)
            and _exact(counts['byStatus'], STATUSES)
            and all(_count(counts['byStatus'][name], LIMITS['maxRows']) and counts['byStatus'][name] == statuses[name]
                    for name in STATUSES)
            and _count(counts['privacySuppressedKeys'], LIMITS['maxSuppressed'] if compared else 0)
            and _exact(counts['omitted'], ('a', 'b'))):
        raise SummaryError('counts_mismatch')
    omitted = {}
    for side in ('a', 'b'):
        state = counts['omitted'][side]
        if not compared:
            if state is not None:
                raise SummaryError('counts_mismatch')
            omitted[side] = None
            continue
        if not (_exact(state, OMISSIONS) and all(_count(state[reason], LIMITS['maxOmittedPerState'])
                                                 for reason in OMISSIONS)
                and sum(state.values()) <= LIMITS['maxOmittedPerState']):
            raise SummaryError('counts_mismatch')
        omitted[side] = {reason: state[reason] for reason in OMISSIONS}
    return {'rows': counts['rows'], 'byStatus': {name: counts['byStatus'][name] for name in STATUSES},
            'omitted': omitted, 'privacySuppressedKeys': counts['privacySuppressedKeys']}


def _references(sources, compared):
    if not _exact(sources, ('a', 'b')):
        raise SummaryError('artifact_schema')
    refs = {}
    for side in ('a', 'b'):
        ref = sources[side]
        if not (_exact(ref, ('bytes', 'sha256')) and _count(ref['bytes'], LIMITS['maxSourceBytes'])
                and type(ref['sha256']) is str and SHA256.fullmatch(ref['sha256'])):
            raise SummaryError('artifact_schema')
        refs[side] = (ref['bytes'], ref['sha256'])
    if (refs['a'][1] != refs['b'][1]) != compared:                         # compared: distinct; no-op: identical
        raise SummaryError('artifact_schema')
    return refs


def summary(artifact_bytes, source_a_bytes, source_b_bytes):
    inputs = (artifact_bytes, source_a_bytes, source_b_bytes)
    if not all(type(data) is bytes for data in inputs):
        raise SummaryError('input_type')
    if len(artifact_bytes) > LIMITS['maxArtifactBytes']:
        raise SummaryError('artifact_too_large')
    if any(len(data) > LIMITS['maxSourceBytes'] for data in inputs[1:]):
        raise SummaryError('source_too_large')
    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
    top = _parse(artifact_bytes)
    if not _exact(top, TOP_KEYS):
        raise SummaryError('artifact_schema')
    if not (_same({'format': top['format'], 'version': top['version']}, PRODUCER) and _same(top['decoder'], DECODER)):
        raise SummaryError('producer_unsupported')
    status = top['status']
    if type(status) is not str or status not in IDENTITY:
        raise SummaryError('status_unsupported')
    compared = status == 'compared'
    if not (top['reason'] is None and top['side'] is None and _same(top['flags'], PRODUCER_FLAGS)
            and _same(top['identity'], IDENTITY[status])):
        raise SummaryError('artifact_schema')
    refs = _references(top['sources'], compared)
    statuses = _rows(top['rows'])
    if not compared and top['rows']:
        raise SummaryError('artifact_schema')
    counts = _counts(top['counts'], top['rows'], statuses, compared)
    actual = {}
    for side, data in zip('ab', inputs[1:]):
        if len(data) != refs[side][0]:
            raise SummaryError('source_mismatch')
        actual[side] = hashlib.sha256(data).hexdigest()
        if actual[side] != refs[side][1]:
            raise SummaryError('source_mismatch')
    return {'format': FORMAT, 'version': VERSION, 'status': status,
            'artifact': {'sha256': artifact_sha, 'bytes': len(artifact_bytes)},
            'sources': {side: {'sha256': actual[side], 'bytes': refs[side][0]} for side in 'ab'},
            'counts': counts,
            'verification': {'sources': 'bytes_match', 'comparisons': 'producer_reported'},
            'flags': {'identity': 'unknown', 'currentness': 'unknown', 'selection': 'unknown', 'atomicity': 'unknown',
                      'labelsPromoted': False, 'arithmeticReady': False}}
