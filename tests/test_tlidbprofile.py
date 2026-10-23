import hashlib
import unittest
from decimal import localcontext

from damage_lab.tlidbprofile import ProfileError, profile


def description(base, shotgun):
    return (f'Chromatic Shot:<br/>Deals <span class="text-mod">{base}</span> Spell Physical Damage<br/>'
            'This skill fires <span class="text-mod">1</span> Projectile in its base state.<br/>'
            'Projectile Quantity of this skill <span class="text-mod">+2</span><br/>'
            f"This skill's Shotgun Effect falloff coefficient is {shotgun}%")


def row(level, base, effect):
    effectiveness = (f'<div data-source="damage_effective">Effectiveness of added damage {effect}%</div>'
                     if effect is not None else '')
    return (f'<tr><td>{level}</td><td>{effectiveness}'
            f'<div data-source="des">{description(base, "73")}</div></td></tr>')


def page(rows=None, *, prefix='', version='SS9Season', total=None):
    rows = [row(1, '13-19', '112.37'), row(2, '17-23', None)] if rows is None else rows
    return (f'<html><body>{prefix}<h1>Chromatic Shot</h1><div class="card ui_item popupItem">'
            f'<div class="item_ver">{version}</div><div class="text-center icon"><div class="level">2</div></div>'
            '<div class="d-flex justify-content-center"><div>Mana Cost</div><div class="ps-2">9</div></div>'
            '<div class="d-flex justify-content-center"><div>Cast Speed</div><div class="ps-2">1.37</div></div>'
            '<div class="d-flex justify-content-center"><div>Effectiveness of added damage</div>'
            '<div class="ps-2">119.73%</div></div>'
            f'<div class="explicitMod">{description("17-23", "73")}</div></div>'
            '<div class="card ui_item"><div class="card-header">Info</div>'
            '<div class="card-body"><div>id: 7007</div></div></div>'
            f'<div class="card mb-2"><div class="card-header">Progression /{len(rows) if total is None else total}</div>'
            '<div class="collapse show"><table class="table" data-table-id="t1"><thead><tr>'
            '<th>level</th><th>Descript</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div></body></html>').encode('utf-8')


def parse(data):
    return profile(data, hashlib.sha256(data).hexdigest(), source_url='https://tlidb.com/en/Chromatic_Shot')


class TlidbProfileTest(unittest.TestCase):
    """Verify offline source candidates without selecting a character's runtime data or effective level."""

    def test_identity_is_a_catalog_observation(self):
        self.assertEqual(parse(page())['identity'], {'name': 'Chromatic Shot', 'infoId': 7007,
                                                     'itemVersionLabel': 'SS9Season', 'headerLevel': 2})

    def test_header_keeps_displayed_cast_rate_and_unknown_precision(self):
        self.assertEqual(parse(page())['header']['castSpeed'],
                         {'display': '1.37', 'meaning': 'displayed_casts_per_second', 'precision': 'unknown'})

    def test_percent_scaling_is_exact_under_hostile_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(parse(page())['header']['effectiveness'],
                             {'display': '119.73%', 'percent': '119.73', 'fraction': '1.1973'})

    def test_each_row_keeps_its_own_base_range(self):
        self.assertEqual([entry['baseDamage'] for entry in parse(page())['rows']],
                         [{'min': '13', 'max': '19'}, {'min': '17', 'max': '23'}])

    def test_missing_effectiveness_is_not_filled_from_the_header_or_previous_row(self):
        self.assertIsNone(parse(page())['rows'][1]['effectiveness'])

    def test_missing_effectiveness_is_an_explicit_gap(self):
        self.assertIn({'level': 2, 'field': 'effectiveness', 'reason': 'not_in_own_row'}, parse(page())['gaps'])

    def test_projectile_descriptions_do_not_claim_actual_projectile_count(self):
        self.assertEqual(parse(page())['rows'][0]['projectiles'],
                         {'intrinsicBase': '1', 'quantityModifier': '+2', 'totalActual': 'unknown'})

    def test_source_season_does_not_select_runtime_or_enable_arithmetic(self):
        result = parse(page())
        self.assertEqual((result['runtimeVersion'], result['effectiveLevel'], result['arithmeticReady'],
                          result['applicability']),
                         ('unknown', None, False, 'catalog_page_text_only_not_runtime_data'))

    def test_source_url_is_caller_declared(self):
        self.assertEqual(parse(page())['source']['urlMeaning'], 'caller_declared_not_origin_verified')

    def test_comment_decoy_cannot_redirect_unicode_byte_spans(self):
        data = page(prefix=f'<p>Жёлтый</p><!-- {row(1, "13-19", "112.37")} -->')
        result = parse(data)
        self.assertTrue(all(start > data.index(b'<tbody>') and data[start:end].decode('utf-8') ==
                            data.decode('utf-8')[entry['source']['charSpan'][0]:entry['source']['charSpan'][1]]
                            for entry in result['rows'] for start, end in [entry['source']['byteSpan']]))

    def test_input_digest_must_match_before_extraction(self):
        with self.assertRaises(ProfileError):
            profile(page(), '0' * 64, source_url='https://tlidb.com/en/Chromatic_Shot')

    def test_url_cannot_carry_arbitrary_metadata_or_query_parameters(self):
        for url in ({'private': 'SYNTHETIC-CANARY'}, 'https://tlidb.com/en/Chromatic_Shot?x=1'):
            with self.subTest(url=url), self.assertRaises(ProfileError):
                profile(page(), hashlib.sha256(page()).hexdigest(), source_url=url)

    def test_comment_page_is_not_a_source_profile(self):
        with self.assertRaises(ProfileError):
            parse(b'<!--' + page() + b'-->')

    def test_self_closing_raw_text_tags_cannot_expose_a_fake_page(self):
        for tag in ('script', 'style', 'SCRIPT', 'STYLE', 'template', 'textarea', 'title', 'noscript'):
            with self.subTest(tag=tag), self.assertRaises(ProfileError):
                parse(f'<{tag}/>'.encode() + page() + f'</{tag}>'.encode())

    def test_inert_ancestors_cannot_expose_a_fake_page(self):
        for tag in ('template', 'textarea', 'title', 'noscript'):
            with self.subTest(tag=tag), self.assertRaises(ProfileError):
                parse(f'<{tag}>'.encode() + page() + f'</{tag}>'.encode())

    def test_inert_markup_cannot_supply_a_base_damage_role(self):
        value = 'Deals <span class="text-mod">13-19</span> Spell Physical Damage'
        for hidden in (f'<!-- {value} -->', f'<script>{value}</script>', f'<template>{value}</template>',
                       f'<style>{value}</style>', f'<noscript>{value}</noscript>'):
            with self.subTest(hidden=hidden[:12]), self.assertRaises(ProfileError):
                parse(page().replace(value.encode(), hidden.encode(), 1))

    def test_duplicate_role_attributes_are_ambiguous(self):
        for duplicate in (b'data-source="other" data-source="des"', b'DATA-SOURCE="other" data-source="des"'):
            with self.subTest(duplicate=duplicate), self.assertRaises(ProfileError):
                parse(page().replace(b'data-source="des"', duplicate, 1))

    def test_stray_text_between_cells_is_not_silently_ignored(self):
        with self.assertRaises(ProfileError):
            parse(page().replace(b'<td>1</td><td>', b'<td>1</td>unexpected<td>', 1))

    def test_empty_progression_is_invalid(self):
        with self.assertRaises(ProfileError):
            parse(page([], total=0))

    def test_duplicate_and_noncontiguous_levels_are_invalid(self):
        for rows in ([row(1, '13-19', '112'), row(1, '17-23', None)],
                     [row(1, '13-19', '112'), row(3, '17-23', None)]):
            with self.subTest(rows=rows), self.assertRaises(ProfileError):
                parse(page(rows))

    def test_count_mismatch_is_invalid(self):
        with self.assertRaises(ProfileError):
            parse(page(total=7))

    def test_version_labels_have_a_short_grammar(self):
        for version in ('X' * 5000, 'SS9 Season'):
            with self.subTest(version=version[:30]), self.assertRaises(ProfileError):
                parse(page(version=version))

    def test_entity_encoded_scalar_is_not_guessed(self):
        with self.assertRaises(ProfileError):
            parse(page().replace(b'119.73%', b'119.7&#51;%'))

    def test_malformed_processing_instructions_are_refused(self):
        with self.assertRaises(ProfileError):
            parse(b'<?' * 4000)

    def test_long_unclosed_identity_is_refused(self):
        with self.assertRaises(ProfileError):
            parse(b'<h1>' + b'<' * 12000)

    def test_source_admission_bounds_bytes_depth_nodes_and_rows(self):
        for data in (b'x' * (4 * 1024 * 1024 + 1), page(prefix='<div>' * 130),
                     page(prefix='<br>' * 20001), page([row(level, '13-19', '112') for level in range(1, 66)])):
            with self.subTest(size=len(data)), self.assertRaises(ProfileError):
                parse(data)

    def test_invalid_utf8_is_a_controlled_refusal(self):
        with self.assertRaises(ProfileError):
            parse(b'\xff' + page())

    def test_inverted_base_range_is_a_controlled_refusal(self):
        with self.assertRaises(ProfileError):
            parse(page([row(1, '31-19', '112')]))

    def test_error_message_does_not_echo_a_page_value(self):
        with self.assertRaises(ProfileError) as raised:
            parse(page(version='SYNTHETIC-PRIVATE-CANARY'))
        self.assertNotIn('CANARY', str(raised.exception))

    def test_result_mutation_does_not_change_later_extraction(self):
        first = parse(page())
        first['rows'][0]['baseDamage']['min'] = 'mutated'
        self.assertEqual(parse(page())['rows'][0]['baseDamage']['min'], '13')


if __name__ == '__main__':
    unittest.main()
