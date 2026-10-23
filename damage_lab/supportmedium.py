"""Typed canonical projection of one support_effects 0.3 mediumTrigger subtree (pure, stdlib; task 1040).

project(document, base_id=..., category=..., prefix=..., omissions=..., canonical=False) validates the subtree
of ONE member against closed key sets and the fixed 1025 vocabulary, and returns a fresh canonical snake_case
dict. document is raw camelCase producer output, or (canonical=True) an earlier canonical projection. prefix
({status, rows, null_rows}) and omissions ([{origin, path, reason}]) are the member's CANONICAL context from the
parent. Every refusal is a ValueError with a fixed sentence that never echoes the input.

Only the medium subtree is checked here: global and leaf versions, legacy 0.2, row counts with null padding,
cross-line path and nativeId/lineId uniqueness and the catalog-document join are the parent's job. The
consumer holds no catalog record body, so the tier match, ranges and template origin are producer_reported
claims ('catalog_claims'), never re-derived; the tier is never inferred from the nativeId. Nothing is
evaluated: no fraction, rate, reciprocal or DPS. See docs/SUPPORT_INVENTORY.md.
"""
from __future__ import annotations

import re
from decimal import Decimal

from .supporteffects import DECIMAL, MEDIUM, MEDIUM_ROLE, MEDIUM_SLOTS, NATIVE_ID, UNRESOLVED

PATH = re.compile(r'prefix\[(0|[1-9][0-9]{0,8})\]')
HELD = 'unresolved_prefix_peer'
CATALOG_GAPS = ('pinned_line_not_declared', 'pinned_line_ambiguous', 'pinned_template_missing', 'pinned_template_drift')
NATIVE_GAPS = ('prefix_absent', 'line_not_observed', 'line_unresolved_rows_present', 'row_omitted')
PIN = {'tlidb_id': MEDIUM['tlidbId'], 'category': MEDIUM['category'], 'line_id': MEDIUM['lineId'],
       'template_source': 'english.lineTemplates'}
# (raw key, canonical key) of every closed object; a raw document uses the first names, a canonical one the second.
NAMES = {'medium': (('status', 'status'), ('reason', 'reason'), ('paths', 'paths'), ('pin', 'pin'), ('line', 'line')),
         'pin': (('tlidbId', 'tlidb_id'), ('category', 'category'), ('lineId', 'line_id'), ('templateSource', 'template_source')),
         'line': (('origin', 'origin'), ('path', 'path'), ('lineId', 'line_id'), ('nativeId', 'native_id'), ('tier', 'tier'),
                  ('tierSource', 'tier_source'), ('tierMeaning', 'tier_meaning'), ('role', 'role'), ('template', 'template'),
                  ('templateSource', 'template_source'), ('slots', 'slots'), ('nativeVersion', 'native_version'),
                  ('status', 'status'), ('semantics', 'semantics'), ('runtime', 'runtime'), ('rateDerived', 'rate_derived')),
         'slot': (('slot', 'slot'), ('quantity', 'quantity'), ('unit', 'unit'), ('exact', 'exact'), ('range', 'range')),
         'range': (('min', 'min'), ('max', 'max')),
         'version': (('value', 'value'), ('meaning', 'meaning'))}
FIXED = {'origin': 'native_prefix_row', 'line_id': MEDIUM['lineId'], 'tier_source': 'exact_native_modifier_id',
         'tier_meaning': 'catalog_line_tier', 'role': MEDIUM_ROLE, 'template': MEDIUM['template'],
         'template_source': 'english.lineTemplates', 'status': 'native_roll_exact', 'semantics': 'catalog_creation_interval',
         'runtime': 'unverified'}


def _fail(message):
    raise ValueError(message)


def _str(value, expected):
    """An exact str equal to expected; the type is checked before any comparison (no subclass hooks run)."""
    return type(value) is str and value == expected


def _admit(value, keys):
    """An exact dict with exactly the given keys: length first, then exact str key types, then set equality."""
    return type(value) is dict and len(value) == len(keys) and all(type(key) is str for key in value) and set(value) == keys


def _closed(value, kind, canonical, extra=()):
    """{canonical key: value} of an object whose keys are exactly the declared ones (plus canonical-only extras)."""
    names = NAMES[kind]
    keys = {name[1] if canonical else name[0] for name in names} | (set(extra) if canonical else set())
    if not _admit(value, keys):
        _fail(f'medium trigger {kind} object does not have the expected keys')
    return {canonical_key: value[canonical_key if canonical else raw_key] for raw_key, canonical_key in names} | \
        ({key: value[key] for key in extra} if canonical else {})


def _int(value, low=0, high=10 ** 12):
    return type(value) is int and low <= value < high


def _index(path):
    """The index of a constructed prefix[i] path, or None."""
    match = PATH.fullmatch(path) if type(path) is str else None
    return int(match.group(1)) if match else None


def _context(prefix, omissions):
    """(rows or None, {index: reason}) of the canonical parent context; refused unless safe to use."""
    if not _admit(prefix, {'status', 'rows', 'null_rows'}):
        _fail('medium trigger prefix context is malformed')
    if _str(prefix['status'], 'absent') and prefix['rows'] is None and prefix['null_rows'] is None:
        if omissions is not None:
            _fail('medium trigger omissions context does not fit an absent prefix')
        return None, {}
    if not _str(prefix['status'], 'supplied') or not _int(prefix['rows']) or not _int(prefix['null_rows']) \
            or prefix['null_rows'] > prefix['rows']:
        _fail('medium trigger prefix context is malformed')
    if type(omissions) is not list:
        _fail('medium trigger omissions context is malformed')
    reasons = {}
    for omission in omissions:
        if not _admit(omission, {'origin', 'path', 'reason'}) \
                or not _str(omission['origin'], 'native_prefix_row') or type(omission['reason']) is not str:
            _fail('medium trigger omissions context is malformed')
        index = _index(omission['path'])
        if index is None or index >= prefix['rows'] or index in reasons:
            _fail('medium trigger omissions context is malformed')
        reasons[index] = omission['reason']
    return prefix['rows'], reasons


def _paths(value, rows):
    """Sorted unique indices of a constructed paths list (within rows when the prefix is supplied)."""
    if type(value) is not list:
        _fail('medium trigger paths are malformed')
    indices = [_index(path) for path in value]
    if any(index is None or (rows is not None and index >= rows) for index in indices) or indices != sorted(set(indices)):
        _fail('medium trigger paths are malformed')
    if rows is None and indices:
        _fail('medium trigger paths do not fit an absent prefix')
    return indices


def _decimal(text):
    return Decimal(text) if type(text) is str and DECIMAL.fullmatch(text) else None


def _slots(value, canonical):
    if type(value) is not list or len(value) != len(MEDIUM_SLOTS):
        _fail('medium trigger slots are malformed')
    slots = []
    for number, (item, (quantity, unit)) in enumerate(zip(value, MEDIUM_SLOTS), 1):
        slot = _closed(item, 'slot', canonical)
        if type(slot['slot']) is not int or slot['slot'] != number or not _str(slot['quantity'], quantity) \
                or not _str(slot['unit'], unit):
            _fail('medium trigger slot identity is not the fixed one')
        bounds = _closed(slot['range'], 'range', canonical)
        exact, low, high = _decimal(slot['exact']), _decimal(bounds['min']), _decimal(bounds['max'])
        # Decimal(text) and comparisons are exact: no caller context rounds them.
        if exact is None or low is None or high is None or low < 0 or exact < 0 or not low <= exact <= high:
            _fail('medium trigger slot values are malformed or out of range')
        slots.append({'slot': number, 'quantity': quantity, 'unit': unit, 'exact': slot['exact'],
                      'range': {'min': bounds['min'], 'max': bounds['max']}})
    return slots


def _line(value, canonical):
    line = _closed(value, 'line', canonical, extra=('catalog_claims',))
    if not all(_str(line[key], expected) for key, expected in FIXED.items()):
        _fail('medium trigger line has an unsupported fixed field')
    if line['rate_derived'] is not False or (canonical and not _str(line['catalog_claims'], 'producer_reported')):
        _fail('medium trigger line has an unsupported fixed field')
    if _index(line['path']) is None or type(line['native_id']) is not str or not NATIVE_ID.fullmatch(line['native_id']) \
            or type(line['tier']) is not int:             # the stored tier: any exact non-bool int, no bounds
        _fail('medium trigger line identity is malformed')
    version = line['native_version']
    if version is not None:
        version = _closed(version, 'version', canonical)
        if type(version['value']) is not int or not _str(version['meaning'], 'unverified'):
            _fail('medium trigger native version is malformed')
        version = {'value': version['value'], 'meaning': 'unverified'}
    return {**FIXED, 'path': line['path'], 'native_id': line['native_id'], 'tier': line['tier'],
            'slots': _slots(line['slots'], canonical), 'native_version': version, 'rate_derived': False,
            'catalog_claims': 'producer_reported'}


def _ordered(line):
    keys = [name[1] for name in NAMES['line']] + ['catalog_claims']
    return {key: line[key] for key in keys}


def project(document, *, base_id, category, prefix, omissions, canonical=False):
    """Fresh canonical mediumTrigger of one member; see the module docstring."""
    if type(canonical) is not bool or type(base_id) is not int or type(category) is not str:
        _fail('medium trigger projection arguments are malformed')
    if base_id != MEDIUM['tlidbId']:
        if not _admit(document, {'status'}) or not _str(document['status'], 'not_applicable'):
            _fail('medium trigger status does not fit its base')
        return {'status': 'not_applicable'}
    rows, reasons = _context(prefix, omissions)
    medium = _closed(document, 'medium', canonical)
    pin = _closed(medium['pin'], 'pin', canonical)
    if type(pin['tlidb_id']) is not int or pin['tlidb_id'] != PIN['tlidb_id'] \
            or not all(_str(pin[key], PIN[key]) for key in ('category', 'line_id', 'template_source')):
        _fail('medium trigger pin does not match the fixed pin')
    status, reason = medium['status'], medium['reason']
    if type(status) is not str or status not in ('bound', 'gap'):
        _fail('medium trigger status does not fit its base')
    indices = _paths(medium['paths'], rows)
    unresolved = sorted(index for index, why in reasons.items() if why in UNRESOLVED)
    held = sorted(index for index, why in reasons.items() if why == HELD)
    matched = category == MEDIUM['category']
    if status == 'bound':
        if not matched or reason is not None or rows is None:
            _fail('medium trigger status does not fit its context')
        line = _line(medium['line'], canonical)
        if indices != [_index(line['path'])] or indices[0] in reasons or unresolved or held:
            _fail('medium trigger paths do not agree with the prefix omissions')
        return {'status': 'bound', 'reason': None, 'paths': list(medium['paths']), 'pin': dict(PIN), 'line': _ordered(line)}
    if medium['line'] is not None or type(reason) is not str:
        _fail('medium trigger gap is malformed')
    allowed = ('category_mismatch',) if not matched else CATALOG_GAPS + NATIVE_GAPS
    if reason not in allowed:
        _fail('medium trigger reason is not allowed here')
    if held and reason != 'line_unresolved_rows_present':
        _fail('medium trigger paths do not agree with the prefix omissions')
    if reason == 'prefix_absent':
        ok = rows is None
    elif reason == 'line_not_observed':
        ok = rows is not None and not indices and not unresolved
    elif reason == 'line_unresolved_rows_present':
        ok = rows is not None and bool(unresolved) and len(held) <= 1 and indices == sorted(unresolved + held)
    elif reason == 'row_omitted':
        ok = bool(indices) and all(index in reasons for index in indices)
    else:                                                # category and catalog gaps: declared paths, possibly empty
        ok = all(index in reasons for index in indices)
    if not ok:
        _fail('medium trigger paths do not agree with the prefix omissions')
    return {'status': 'gap', 'reason': reason, 'paths': list(medium['paths']), 'pin': dict(PIN), 'line': None}
