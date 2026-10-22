"""Typed candidate effects of one installed special support (offline, pure, catalog-bound).

effects(record, native_base_id=..., prefix_rows=...) takes an exact catalog skill record, the native base id
of the installed gem (SkillData._Raw_Data.ConfigBaseId) and its native ServerPlayerItem.Prefix rows. The record
binds only when record.tlidbId equals the native base id; otherwise the result is an explicit binding gap.
- Rolled lines: a row's full Id must equal exactly one tierProgression[t].lines[].modifierId of a declared
  line, its DynArgs count must equal the tier's value count, and every roll must lie in its own tier's
  [min, max]; signs are never flipped and no other tier is tried. Only two demonstrated templates are typed.
- Constants: exact catalog literals of english.templateDescription (a text line index, not a JSON index),
  among them the Physical -> Cold 100 % conversion; text of unknown lines is never copied.
Constants and rolls keep separate origins; additional-group identity across supports stays unresolved.
Everything is diagnostic: arithmeticReady false, activation/effective level/patch unknown. No DPS.
See docs/SUPPORT_EFFECTS.md.
"""
from __future__ import annotations

import math
import re
from decimal import Context, Decimal

FORMAT = 'tli-support-effects-v0'
VERSION = '0.2.0'
DECIMAL = re.compile(r'-?\d{1,12}(?:\.\d{1,9})?')
NATIVE_ID = re.compile(r'[A-Za-z0-9]{1,32}')
TEMPLATES = {'+#% additional Hit Damage for the supported skill': ('additional_hit_damage', '+'),
             '#% additional damage for the supported skill': ('additional_damage', '')}
CONSTANTS = {
    "Converts 100% of the supported skill's Physical Damage to Cold Damage":
        ('conversion', {'from': 'physical', 'to': 'cold', 'percent': '100'}),
    '+20% additional damage for the supported skill': ('additional_damage', {'percent': '20'}),
    "+25% additional damage ratio granted by the supported skill's main attribute": ('main_attribute_ratio', {'percent': '25'}),
    '+30% additional Projectile Speed for the supported skill': ('projectile_speed', {'percent': '30'}),
    'The supported skill gains the Cold Tag': ('tag_grant', {'tag': 'cold'}),
    'Inflicts Frostbite when the supported skill deals Hit Cold Damage':
        ('ailment_on_hit', {'ailment': 'frostbite', 'trigger': 'hit_cold_damage'}),
    'Enhances the tracking ability of the supported skill. Affected by Projectile Speed': ('tracking', {}),
    'Supports Chromatic Shot': ('support_restriction', {}),
    'Supports Chromatic Shot.': ('support_restriction', {}),
    'This skill can only be installed in the fifth Support Skill Slot of each Active Skill': ('slot_restriction', {}),
    'This skill can only be installed in the third Support Skill Slot of each Active Skill.': ('slot_restriction', {}),
}
UNKNOWN = {'arithmeticReady': False, 'activation': 'unknown', 'effectiveLevel': 'unknown', 'patch': 'unknown',
           'runtimeVerified': False, 'additionalGroupIdentity': 'unresolved'}


class EffectsError(ValueError):
    """An input outside the adapter's contract; the message never echoes the input."""


EXACT = Context(prec=50)        # explicit context: never the caller's; 50 digits hold every bounded value exactly


def _exact(value):
    """Exact lexical text of a roll or bound within one bounded contract, or None.

    Every accepted value is at most 12 integer and 9 fraction digits: an int below 10**12 in magnitude
    (checked before any text conversion), a finite float whose repr has that plain form, or such text.
    """
    if type(value) is int:
        return str(value) if abs(value) < 10 ** 12 else None
    if type(value) is float and math.isfinite(value):
        text = repr(value)
        return text if DECIMAL.fullmatch(text) else None
    if isinstance(value, str) and DECIMAL.fullmatch(value):
        return value
    return None


def _fraction(text):
    """text / 100, exact and independent of the caller's Decimal context."""
    return format(Decimal(text).scaleb(-2, context=EXACT).normalize(context=EXACT), 'f')


def _schema_ok(record):
    """The containers and identity leaves this adapter reads are well-formed (absent is allowed, malformed is not)."""
    lines = record.get('lines')
    if lines is not None and not (isinstance(lines, list) and all(isinstance(l, dict) and isinstance(l.get('id'), str) for l in lines)):
        return False
    tiers = record.get('tierProgression')
    if tiers is not None:
        if not isinstance(tiers, list):
            return False
        for tier in tiers:
            if not isinstance(tier, dict) or type(tier.get('tier')) is not int or not isinstance(tier.get('lines'), list):
                return False
            if not all(isinstance(l, dict) and isinstance(l.get('id'), str) and isinstance(l.get('modifierId'), str)
                       for l in tier['lines']):
                return False
    english = record.get('english')
    if english is not None:
        if not isinstance(english, dict):
            return False
        templates, text = english.get('lineTemplates'), english.get('templateDescription')
        if templates is not None and not (isinstance(templates, dict)
                                          and all(isinstance(k, str) and isinstance(v, str) for k, v in templates.items())):
            return False
        if text is not None and not isinstance(text, str):
            return False
    return True


def _rolled(index, row, declared, lookup, templates):
    """(line dict, None) or (None, reason) for one native prefix row."""
    native = row.get('Id') if isinstance(row, dict) else None
    if isinstance(native, bool) or not (type(native) is int or (isinstance(native, str) and NATIVE_ID.fullmatch(native))) \
            or not isinstance(row.get('DynArgs'), list):
        return None, 'invalid_row'
    matches = lookup.get(str(native), [])
    if not matches:
        return None, 'no_exact_definition'
    if len(matches) > 1:
        return None, 'ambiguous_definition'
    tier, line = matches[0]
    if line.get('id') not in declared:
        return None, 'line_not_declared'
    specs, dyn = line.get('values'), row['DynArgs']
    if not isinstance(specs, list) or len(dyn) != len(specs):
        return None, 'value_count_mismatch'
    rolls = [_exact(value) for value in dyn]
    if any(roll is None for roll in rolls):
        return None, 'invalid_value'
    template = templates.get(line['id'])
    if not isinstance(template, str):
        return None, 'unsupported_template'
    if template.startswith('-') and any(Decimal(roll) < 0 for roll in rolls):
        return None, 'sign_convention_unresolved'         # an explicit minus and a negative roll: whose sign is it?
    if template not in TEMPLATES or template.count('#') != len(specs):
        return None, 'unsupported_template'
    role, sign = TEMPLATES[template]
    values = []
    for roll, spec in zip(rolls, specs):
        low, high = (_exact(spec.get(key)) if isinstance(spec, dict) else None for key in ('min', 'max'))
        if low is None or high is None or Decimal(low) > Decimal(high):
            return None, 'invalid_range'
        if sign == '+' and (Decimal(roll) < 0 or Decimal(low) < 0):
            return None, 'sign_convention_unresolved'
        if not Decimal(low) <= Decimal(roll) <= Decimal(high):
            return None, 'value_out_of_range'
        values.append({'exact': roll, 'fraction': _fraction(roll), 'range': {'min': low, 'max': high}})
    version = row.get('Version')
    return {'origin': 'native_prefix_row', 'path': f'prefix[{index}]', 'lineId': line['id'], 'nativeId': str(native),
            'tier': tier, 'role': role, 'unit': 'percent', 'template': template, 'values': values,
            'nativeVersion': {'value': version, 'meaning': 'unverified'} if type(version) is int else None,
            'status': 'native_roll_exact'}, None


def _constants(text, templates):
    """(constants, issues) from the template description lines; rolled-template lines are skipped."""
    rolled_lines = {line for value in templates.values() if isinstance(value, str) for line in value.split('\n')}
    constants, issues = [], []
    for number, line in enumerate(text.split('\n')):
        source = {'field': 'templateDescription', 'line': number}
        if not line.strip() or line in rolled_lines:
            continue
        if line in CONSTANTS:
            kind, parameters = CONSTANTS[line]
            constants.append({'origin': 'catalog_literal', 'source': source, 'kind': kind, 'parameters': dict(parameters),
                              'status': 'catalog_literal_unverified_runtime'})
        else:
            issues.append({'source': source, 'reason': 'placeholder_without_line' if '#' in line else 'unknown_constant'})
    return constants, issues


def effects(record, *, native_base_id, prefix_rows):
    """Candidate typed effects of one installed special support; see the module docstring."""
    if not isinstance(record, dict):
        raise EffectsError('record must be a catalog skill record object')
    if type(native_base_id) is not int:
        raise EffectsError('native_base_id must be an integer')
    if prefix_rows is not None and not isinstance(prefix_rows, list):
        raise EffectsError('prefix_rows must be a list or None')
    catalog_id = record.get('tlidbId') if type(record.get('tlidbId')) is int else None
    identity = {'status': 'supplied_data_exact' if catalog_id == native_base_id else
                'catalog_identity_invalid' if catalog_id is None else 'base_identity_mismatch',
                'catalogTlidbId': catalog_id, 'nativeBaseId': native_base_id,
                'category': record.get('category') if isinstance(record.get('category'), str) else None,
                'guid': record.get('id') if isinstance(record.get('id'), str) else None}
    prefix = ({'status': 'absent', 'rows': None, 'nullRows': None} if prefix_rows is None else
              {'status': 'supplied', 'rows': len(prefix_rows), 'nullRows': sum(1 for row in prefix_rows if row is None)})
    result = {'format': FORMAT, 'version': VERSION, 'identity': identity, **UNKNOWN, 'prefix': prefix,
              'catalogSchema': None, 'rolledLines': None, 'omissions': None, 'constants': None, 'constantIssues': None}
    if identity['status'] != 'supplied_data_exact':
        return result                                    # binding gap: nothing from this record is attributed
    result['catalogSchema'] = 'ok' if _schema_ok(record) else 'invalid'
    if result['catalogSchema'] != 'ok':
        return result                                    # a malformed supplied schema is a gap, never empty data
    english = record.get('english') if isinstance(record.get('english'), dict) else {}
    templates = english.get('lineTemplates') if isinstance(english.get('lineTemplates'), dict) else {}
    if isinstance(english.get('templateDescription'), str):
        result['constants'], result['constantIssues'] = _constants(english['templateDescription'], templates)
    if prefix_rows is None:
        return result
    declared = {line.get('id') for line in record.get('lines') or [] if isinstance(line, dict)}
    lookup = {}
    for tier in record.get('tierProgression') or []:
        if isinstance(tier, dict) and type(tier.get('tier')) is int:
            for line in tier.get('lines') or []:
                if isinstance(line, dict) and isinstance(line.get('modifierId'), str):
                    lookup.setdefault(line['modifierId'], []).append((tier['tier'], line))
    # Known identities are counted before any value is validated: a duplicated exact id or line, even with a
    # malformed or invalid peer row, leaves no single candidate behind.
    line_of = {}
    for index, row in enumerate(prefix_rows):
        native = row.get('Id') if isinstance(row, dict) else None
        if type(native) is int or (isinstance(native, str) and NATIVE_ID.fullmatch(native)):
            matches = lookup.get(str(native), [])
            if len(matches) == 1:
                line_of[index] = matches[0][1]['id']
    counts = {}
    for line_id in line_of.values():
        counts[line_id] = counts.get(line_id, 0) + 1
    rolled, omissions = [], []
    for index, row in enumerate(prefix_rows):
        if row is None:
            continue
        if counts.get(line_of.get(index), 0) > 1:
            omissions.append({'origin': 'native_prefix_row', 'path': f'prefix[{index}]', 'reason': 'duplicate_line'})
            continue
        line, reason = _rolled(index, row, declared, lookup, templates)
        if line is None:
            omissions.append({'origin': 'native_prefix_row', 'path': f'prefix[{index}]', 'reason': reason})
        else:
            rolled.append(line)
    result.update(rolledLines=rolled, omissions=omissions)
    return result
