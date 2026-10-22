"""Typed profile of one exactly identified catalog skill at one explicit level (offline, pure).

profile(skills, tlidb_id, level) reads a catalog skill record (guide_model.Catalog.skills) and returns
what the damage rules need, each with an explicit status and never a default:
- tags, validated as a whole collection, split into skill tags (for ledger_inputs / path_damage),
  damage-type tags and reserved path scopes (elemental, damage), which are never skill tags; absent,
  invalid and supplied (even empty) collections stay distinct, as do the explicit mainStat attributes;
- effectivenessOfAddedDamage and the castSpeed field as exact decimal text, or not_stated / invalid;
- the base spell hit range at the level, only when the template has exactly one damage line of the
  exact form "Deals #-# Spell <Type> Damage", its binding is a value<N>Min/Max pair, and the binding
  re-renders the whole catalog description at the binding level. That is catalog-internal
  consistency, not a runtime fact; levels are never interpolated.
Catalog-only candidate fields; not an effective-level, version or runtime resolver.
"""
from __future__ import annotations

import re
from fractions import Fraction

DAMAGE_TYPES = ("physical", "lightning", "cold", "fire", "erosion")

FORMAT = 'tli-skill-profile-v0'
VERSION = '0.2.1'
DEALS = re.compile(r'Deals #-# Spell (Physical|Cold|Fire|Lightning|Erosion) Damage\.?')
PERCENT = re.compile(r'([0-9]{1,4}(?:\.[0-9]{1,4})?)%')
SECONDS = re.compile(r'([0-9]{1,3}(?:\.[0-9]{1,4})?) s')
TOKEN = re.compile(r'#-#|#')
GUID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
RESERVED = ('elemental', 'damage', 'all')        # path scopes downstream; never skill tags
ATTRIBUTES = {'Strength': 'strength', 'Dexterity': 'dexterity', 'Intelligence': 'intelligence'}


def _tag(text):
    return re.sub(r'[^a-z]+', '_', text.lower()).strip('_')


def _tags(record):
    """Tags split into skill, damage-type and reserved categories; the whole collection must be valid first."""
    empty = {'skill': None, 'damageTypes': None, 'reserved': None, 'catalog': None}
    if record.get('tags') is None:
        return {'status': 'absent', **empty}
    tags = record['tags']
    if not isinstance(tags, list) or not all(isinstance(tag, str) and _tag(tag) for tag in tags):
        return {'status': 'invalid', **empty}
    normalized = sorted({_tag(tag) for tag in tags})
    return {'status': 'supplied', 'skill': [t for t in normalized if t not in DAMAGE_TYPES and t not in RESERVED],
            'damageTypes': [t for t in normalized if t in DAMAGE_TYPES], 'reserved': [t for t in normalized if t in RESERVED],
            'catalog': list(tags)}


def _main_stat(record):
    """Explicit attribute names only (Strength, Dexterity, Intelligence); no lexical inference."""
    if record.get('mainStat') is None:
        return {'status': 'absent', 'attributes': None}
    stats = record['mainStat']
    if not isinstance(stats, list) or not all(isinstance(stat, str) and stat in ATTRIBUTES for stat in stats) or len(set(stats)) != len(stats):
        return {'status': 'invalid', 'attributes': None}
    return {'status': 'supplied', 'attributes': [ATTRIBUTES[stat] for stat in stats]}


def _identity(record, tlidb_id):
    guid = record.get('id')
    status = 'absent' if guid is None else 'ok' if isinstance(guid, str) and GUID.fullmatch(guid) else 'invalid'
    return {'status': 'exact', 'tlidbId': tlidb_id, 'guid': guid if status == 'ok' else None, 'guidStatus': status}


def _ordered(low, high):
    """True for a non-negative, ordered integer damage range."""
    return type(low) is int and type(high) is int and 0 <= low <= high


def _stated(value, pattern, key, scale):
    if value is None or value == '':
        return {'status': 'not_stated', 'text': value if value == '' else None, key: None}
    match = pattern.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        return {'status': 'invalid', 'text': None, key: None}
    return {'status': 'stated', 'text': value, key: _decimal(Fraction(match.group(1)) / scale)}


def _decimal(value):
    """Exact decimal text of a Fraction with a power-of-ten denominator."""
    sign, value = ('-' if value < 0 else ''), abs(value)
    whole, rest = divmod(value.numerator, value.denominator)
    if not rest:
        return f'{sign}{whole}'
    digits = []
    for _ in range(12):
        rest *= 10
        digit, rest = divmod(rest, value.denominator)
        digits.append(str(digit))
        if not rest:
            break
    return f'{sign}{whole}.' + ''.join(digits)


def _render(template, bindings, row):
    """The description the bindings produce from one level row, or None if a binding cannot render."""
    tokens, pieces = TOKEN.findall(template), TOKEN.split(template)
    out = []
    for token, binding in zip(tokens, bindings):
        if isinstance(binding, dict) and set(binding) == {'c'} and isinstance(binding['c'], str):
            out.append(binding['c'])
        elif isinstance(binding, str) and token == '#-#' and binding.endswith('Min'):
            low, high = row.get(binding), row.get(binding[:-3] + 'Max')
            if type(low) is not int or type(high) is not int:
                return None
            out.append(f'{low}-{high}')
        elif isinstance(binding, str) and token == '#' and type(row.get(binding)) is int:
            out.append(str(row[binding]))
        else:
            return None
    return pieces[0] + ''.join(value + piece for value, piece in zip(out, pieces[1:]))


def _hit(record, level):
    bindings_spec, rows = record.get('descriptionBindings'), record.get('levelProgression')
    english = record.get('english') if isinstance(record.get('english'), dict) else {}
    if not isinstance(bindings_spec, dict) or not isinstance(rows, list):
        return {'status': 'no_binding'}
    key = bindings_spec.get('template')
    if not isinstance(key, str):
        return {'status': 'no_binding'}           # the key is checked before any lookup
    template, description = english.get(key), english.get('description')
    bindings, checked = bindings_spec.get('bindings'), bindings_spec.get('level')
    if not isinstance(template, str) or not isinstance(description, str) or not isinstance(bindings, list) or type(checked) is not int:
        return {'status': 'no_binding'}
    lines = template.split('\n')
    candidates = [index for index, line in enumerate(lines) if line.startswith('Deals ')]
    if len(candidates) > 1:
        return {'status': 'multiple_damage_lines'}
    match = DEALS.fullmatch(lines[candidates[0]]) if candidates else None
    if match is None:
        return {'status': 'no_spell_hit_line'}
    tokens = TOKEN.findall(template)
    if len(tokens) != len(bindings):
        return {'status': 'binding_count_mismatch'}
    position = len(TOKEN.findall('\n'.join(lines[:candidates[0]]) + ('\n' if candidates[0] else '')))
    low_key = bindings[position]
    if tokens[position] != '#-#' or not isinstance(low_key, str) or not re.fullmatch(r'value[0-9]{1,2}Min', low_key):
        return {'status': 'binding_not_range'}
    high_key = low_key[:-3] + 'Max'
    by_level = {}
    for row in rows:
        if isinstance(row, dict) and type(row.get('level')) is int:
            by_level.setdefault(row['level'], []).append(row)
    reference = by_level.get(checked, [])
    if len(reference) != 1 or _render(template, bindings, reference[0]) != description:
        return {'status': 'render_mismatch'}
    if not _ordered(reference[0].get(low_key), reference[0].get(high_key)):
        return {'status': 'invalid_range'}
    selected = by_level.get(level, [])
    if len(selected) != 1:
        return {'status': 'level_not_in_table'}
    low, high = selected[0].get(low_key), selected[0].get(high_key)
    if type(low) is not int or type(high) is not int:
        return {'status': 'non_integer_value'}
    if not _ordered(low, high):
        return {'status': 'invalid_range'}
    return {'status': 'catalog_render_consistent', 'type': match.group(1).lower(), 'min': str(low), 'max': str(high),
            'level': level, 'binding': {'min': low_key, 'max': high_key}, 'checkedAtLevel': checked}


def profile(skills, tlidb_id, level):
    """Typed profile of catalog skill tlidb_id at an explicit level; every field states its own status."""
    if not isinstance(skills, dict):
        raise ValueError('skills must map tlidb ids to catalog skill records')
    if type(tlidb_id) is not int or tlidb_id < 1 or type(level) is not int or level < 1:
        raise ValueError('tlidb_id and level must be positive integers')
    record = skills.get(str(tlidb_id))
    base = {'format': FORMAT, 'version': VERSION, 'runtimeVerified': False, 'level': level}
    if not isinstance(record, dict) or type(record.get('tlidbId')) is not int or record['tlidbId'] != tlidb_id:
        return {**base, 'identity': {'status': 'no_exact_skill', 'tlidbId': tlidb_id}, 'tags': None,
                'effectivenessOfAddedDamage': None, 'castSpeedField': None, 'mainStat': None, 'hit': {'status': 'no_exact_skill'}}
    return {**base, 'identity': _identity(record, tlidb_id), 'tags': _tags(record),
            'effectivenessOfAddedDamage': _stated(record.get('effectivenessOfAddedDamage'), PERCENT, 'value', 100),
            'castSpeedField': _stated(record.get('castSpeed'), SECONDS, 'seconds', 1),
            'mainStat': _main_stat(record), 'hit': _hit(record, level)}
