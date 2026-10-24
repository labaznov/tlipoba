"""Render automatic conditional combat without adding character stats or activation evidence."""

import copy
import json
import re

from .buildinputs import assemble
from .conditionalcombat import evaluate
from .importer import snapshot
from .report import staticdetails, text
from .staticcombat import summary

FORMAT = 'tli-automatic-conditional-combat-report-v1'


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError('Automatic conditional report requires exactly its supported fields')


def _origins(origins):
    _object(origins, 'import context')
    for name, kind, maximum in (('import', 'automatic_import_json', 4 * 1024**2),
                                ('context', 'conditional_combat_context', 1024**2)):
        row = origins[name]
        _object(row, 'kind sha256 bytes')
        if (row['kind'] != kind or type(row['sha256']) is not str
                or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None
                or type(row['bytes']) is not int or not 1 <= row['bytes'] <= maximum):
            raise ValueError('Automatic conditional origins require bounded exact byte metadata')


def build(record, context, *, skill_alias, origins):
    """Assemble the imported spell unchanged and apply only explicitly declared fight context."""
    _origins(origins)
    _object(context, 'format topology target uptime gates missing notes condition coverage')
    if context['format'] != 'tli-conditional-combat-context-v1':
        raise ValueError('Unsupported automatic conditional combat context format')
    record = snapshot(record)
    if 'static_combat' not in record:
        raise ValueError('Automatic conditional combat requires an imported static ledger')
    ledger = summary(record['static_combat'])
    inputs = assemble(record, skill_alias=skill_alias)
    if inputs['raw_spell'] is None:
        raise ValueError('Selected automatic spell context is unavailable')
    combat = {'format': 'tli-raw-cold-combat-v1', 'spell': copy.deepcopy(inputs['raw_spell']),
              **{key: copy.deepcopy(context[key]) for key in ('topology', 'target', 'uptime', 'gates', 'missing', 'notes')}}
    calculation = evaluate(combat, ledger, condition=context['condition'], coverage=context['coverage'])
    return {'format': FORMAT, 'version': '0.1.0', 'origins': copy.deepcopy(origins), 'context': copy.deepcopy(context),
            'automatic_inputs': inputs, 'calculation': calculation,
            'import_complete': False, 'runtime_verified': False, 'identity_verified': False}


def render(report):
    """Rebuild accepted observations before displaying gaps and unapplied versus applied inventory."""
    _object(report, 'format version origins context automatic_inputs calculation import_complete runtime_verified identity_verified')
    if report['format'] != FORMAT or report['version'] != '0.1.0' or any(
            report[key] is not False for key in ('import_complete', 'runtime_verified', 'identity_verified')):
        raise ValueError('Unsupported or promoted automatic conditional report')
    expected = build(report['automatic_inputs']['record'], report['context'],
                     skill_alias=report['automatic_inputs']['selection']['alias'], origins=report['origins'])
    if report != expected:
        raise ValueError('Automatic conditional report differs from its source-bound reconstruction')
    result = expected['calculation']
    pretty = lambda value: text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    detected = [row for row in expected['automatic_inputs']['record']['static_combat']['modifiers']
                if row['family'] == 'conditional_damage_more']
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Автоматический условный расчёт</title>'
            '<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
            '<h1>Автоматический условный расчёт</h1><p>Текущий персонаж, полный импорт и точный DPS не подтверждены.</p>'
            f'<p>Статус: {text(result["status"])}; DPS: {text(result["dps"]) if result["dps"] is not None else "Неизвестно"}</p>'
            f'<h2>Происхождение файлов</h2><pre>{pretty(expected["origins"])}</pre>'
            '<p>Хеши связывают сохранённые файлы; текущий персонаж и свежесть не подтверждены.</p>'
            f'<h2>Явные условия и покрытие</h2><pre>{pretty({"condition": result["condition"], "coverage": result["coverage"]})}</pre>'
            f'<h2>Пробелы автоматических входов</h2><pre>{pretty(expected["automatic_inputs"]["gaps"])}</pre>'
            f'<h2>Пробелы расчёта</h2><pre>{pretty(result["gaps"])}</pre>'
            '<h2>Обнаруженные условные строки</h2><p>Наличие в импорте не означает активацию.</p>'
            f'<pre>{pretty(detected)}</pre><h2>Применённые строки</h2><pre>{pretty(result["applied_rows"])}</pre>'
            f'<h2>Привязка источника расчёта</h2><pre>{pretty(result["source"])}</pre>'
            + staticdetails(expected['automatic_inputs']['record']) + '</html>\n')
