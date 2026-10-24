import copy
import unittest

from damage_lab.conditionalreport import build, render
from test_conditionalcli import record, context


def report():
    """Rebuild automatic inputs using synthetic file-origin declarations."""
    return build(record(), context(), skill_alias='gem[1]', origins={
        'import': {'kind': 'automatic_import_json', 'sha256': 'c' * 64, 'bytes': 177},
        'context': {'kind': 'conditional_combat_context', 'sha256': 'd' * 64, 'bytes': 311}})


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
