import copy
import hashlib
import json
from pathlib import Path
import unittest

from damage_lab.conditionalreport import build, render
from test_conditionalcli import record, context


def report():
    """Rebuild automatic inputs using synthetic file-origin declarations."""
    return build(record(), context(), skill_alias='gem[1]', origins={
        'import': {'kind': 'automatic_import_json', 'sha256': 'c' * 64, 'bytes': 177},
        'context': {'kind': 'conditional_combat_context', 'sha256': 'd' * 64, 'bytes': 311}})


def v2(base):
    """Same synthetic fight, with an explicit Tangle base and no confirmed null."""
    data = context()
    data['format'] = 'tli-conditional-combat-context-v2'
    data['topology'] = dict(data['topology'], base=base)
    if base is None:
        data['gates']['hit_topology'] = {'status': 'unknown', 'evidence': []}
    return data


def built(declared):
    return build(record(), declared, skill_alias='gem[1]', origins=report()['origins'])


class ConditionalReportTests(unittest.TestCase):
    """Show detected inventory separately from applied conditional arithmetic."""

    def test_html_shows_unknown_damage_condition_and_unapplied_inventory(self):
        page = render(report())
        self.assertEqual([fragment in page for fragment in ('Неизвестно', 'blocked', 'target_cursed',
                          '&quot;state&quot;: &quot;unknown&quot;', 'Обнаруженные условные строки', 'Применённые строки',
                          'Пробелы автоматических входов', 'Хеши связывают сохранённые файлы')], [True] * 8)

    def test_caller_text_is_escaped_and_unknown_fields_cannot_be_copied_into_html(self):
        data = report()
        declared = copy.deepcopy(data['context'])
        declared['notes'].append('<script>private()</script>')
        declared['condition']['evidence'].append('<img src=x>')
        data = build(record(), declared, skill_alias='gem[1]', origins=data['origins'])
        page = render(data)
        self.assertEqual(('<img src=x>' in page, '&lt;img src=x&gt;' in page), (False, True))
        data['arbitrary'] = '<script>unknown()</script>'
        with self.assertRaises(ValueError):
            render(data)

    def test_report_reconstruction_refuses_dps_promotion_and_preserves_input(self):
        data = report()
        saved = copy.deepcopy(data)
        render(data)
        self.assertEqual(data, saved)
        data['calculation']['dps'] = 120
        with self.assertRaises(ValueError):
            render(data)

    def test_nested_float_and_bool_substitutions_are_rejected(self):
        data = report()
        data['calculation']['scenario']['topology']['maximum'] = 3.0
        data['calculation']['scenario']['topology']['extra'] = True
        with self.assertRaises(ValueError):
            render(data)

    def test_v1_json_matches_the_prechange_report(self):
        raw = (Path(__file__).parent / 'fixtures' / 'automatic-conditional-v1-report.json').read_bytes()
        current = (json.dumps(report(), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        self.assertEqual((hashlib.sha256(raw).hexdigest(), len(raw), current),
                         ('13c49c34004102920c8a2fa417a763408a9650a1f651a164bef3d682771c8b65', 59341, raw))

    def test_html_labels_base_immediately_after_the_status(self):
        legacy = render(report())
        known = render(built(v2(2)))
        zero = render(built(v2(0)))
        unknown = render(built(v2(None)))
        status = '<p>Статус: blocked; DPS: Неизвестно</p>'
        self.assertEqual([page[page.index(status) + len(status):page.index(status) + len(status) + len(label)]
                          for page, label in (
                              (legacy, '<p>База Tangle: 1, непроверенное допущение legacy</p>'),
                              (known, '<p>База Tangle: 2</p>'),
                              (zero, '<p>База Tangle: 0</p>'),
                              (unknown, '<p>База Tangle: неизвестно</p>'))],
                         ['<p>База Tangle: 1, непроверенное допущение legacy</p>', '<p>База Tangle: 2</p>',
                          '<p>База Tangle: 0</p>', '<p>База Tangle: неизвестно</p>'])

    def test_v2_preserves_exact_base_and_stays_spell_blocked(self):
        rows = []
        for base in (0, 2, None):
            data = built(v2(base))
            spell = data['automatic_inputs']['raw_spell']
            rows.append((data['version'], data['format'], data['context']['topology']['base'],
                         data['calculation']['scenario']['format'], data['calculation']['scenario']['topology']['base'],
                         'topology.base: unavailable' in data['calculation']['gaps'], data['calculation']['dps'],
                         data['calculation']['result']['topology'], data['calculation']['result']['factors'],
                         [spell[name] for name in ('damage', 'critical', 'casting', 'double_damage')],
                         [data[name] for name in ('import_complete', 'runtime_verified', 'identity_verified')]))
        self.assertEqual(rows, [
            ('0.1.1', 'tli-automatic-conditional-combat-report-v1', 0, 'tli-raw-cold-combat-v2', 0, False, None, None, None, [None] * 4, [False, False, False]),
            ('0.1.1', 'tli-automatic-conditional-combat-report-v1', 2, 'tli-raw-cold-combat-v2', 2, False, None, None, None, [None] * 4, [False, False, False]),
            ('0.1.1', 'tli-automatic-conditional-combat-report-v1', None, 'tli-raw-cold-combat-v2', None, True, None, None, None, [None] * 4, [False, False, False])])

    def test_v2_rejects_invalid_base_confirmed_null_and_siblings(self):
        self.assertIsNone(built(v2(None))['context']['topology']['base'])
        confirmed = v2(None)
        confirmed['gates']['hit_topology'] = {'status': 'confirmed', 'evidence': ['synthetic:hit_topology']}
        with self.assertRaisesRegex(ValueError, 'unknown base'):
            built(confirmed)
        sibling = v2(None)
        sibling['target']['more_taken'] = [{'id': 'x'}]
        with self.assertRaisesRegex(ValueError, 'Target additional modifier'):
            built(sibling)
        for bad in (True, 2.0, 1001, -1):
            with self.assertRaisesRegex(ValueError, 'integer from 0 through 1000'):
                built(v2(bad))
        missing = v2(2)
        del missing['topology']['base']
        with self.assertRaisesRegex(ValueError, 'Combat topology'):
            built(missing)
        extra = v2(2)
        extra['topology']['rank'] = 1
        with self.assertRaisesRegex(ValueError, 'Combat topology'):
            built(extra)
        foreign = v2(2)
        foreign['spell'] = {'damage': 1}
        with self.assertRaisesRegex(ValueError, 'supported fields'):
            built(foreign)
        for bad in ([], {}):
            declared = context()
            declared['format'] = bad
            with self.assertRaisesRegex(ValueError, 'Unsupported automatic conditional'):
                built(declared)

    def test_version_pairs_are_rejected_before_reconstruction(self):
        paired = built(v2(2))
        self.assertEqual((paired['version'], paired['context']['format']), ('0.1.1', 'tli-conditional-combat-context-v2'))
        paired['version'] = '0.1.0'
        paired['automatic_inputs']['record'] = None
        with self.assertRaisesRegex(ValueError, 'Unsupported or promoted'):
            render(paired)
        legacy = report()
        legacy['version'] = '0.1.1'
        legacy['automatic_inputs']['record'] = None
        with self.assertRaisesRegex(ValueError, 'Unsupported or promoted'):
            render(legacy)

    def test_v2_recomputed_substitutions_stay_escaped_and_immutable(self):
        declared = v2(2)
        declared['condition']['evidence'].append('<script>private()</script>')
        data = built(declared)
        saved = copy.deepcopy(data)
        page = render(data)
        self.assertEqual((data, '<script>private()</script>' in page, '&lt;script&gt;private()&lt;/script&gt;' in page),
                         (saved, False, True))
        for label, mutate in (
                ('base-float', lambda item: item['calculation']['scenario']['topology'].__setitem__('base', 2.0)),
                ('base-bool', lambda item: item['calculation']['scenario']['topology'].__setitem__('base', True)),
                ('maximum-float', lambda item: item['calculation']['scenario']['topology'].__setitem__('maximum', 3.0)),
                ('extra-bool', lambda item: item['calculation']['scenario']['topology'].__setitem__('extra', True)),
                ('raw-format', lambda item: item['calculation']['scenario'].__setitem__('format', 'tli-raw-cold-combat-v1')),
                ('context-base', lambda item: item['context']['topology'].__setitem__('base', 0)),
                ('dps', lambda item: item['calculation'].__setitem__('dps', 120)),
                ('verified', lambda item: item.__setitem__('runtime_verified', True))):
            with self.subTest(label=label):
                tampered = built(v2(2))
                mutate(tampered)
                with self.assertRaises(ValueError):
                    render(tampered)

    def test_malformed_envelopes_raise_value_error(self):
        self.assertEqual((render(report()).count('База Tangle: 1, непроверенное допущение legacy'),
                          render(built(v2(2))).count('База Tangle: 2</p>')), (1, 1))
        cases = (
            ('version', []), ('version', {}), ('version', None), ('version', True), ('version', 1),
            ('context.format', []), ('context.format', {}), ('context.format', None), ('context.format', True),
            ('context', {}), ('context', None), ('context', []), ('format', []), ('format', {}),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = report()
                data['automatic_inputs']['record'] = None
                if field == 'context.format':
                    data['context']['format'] = value
                else:
                    data[field] = value
                with self.assertRaises(ValueError) as caught:
                    render(data)
                self.assertEqual(str(caught.exception), 'Unsupported or promoted automatic conditional report')
        missing = report()
        missing['automatic_inputs']['record'] = None
        del missing['context']
        with self.assertRaises(ValueError):
            render(missing)
