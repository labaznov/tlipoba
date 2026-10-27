"""Publish a bounded, counts-only diagnostic for two source byte references."""

import argparse
from html import escape
import json
from pathlib import Path
import sys
import tempfile

from .wirediff import LIMITS, SummaryError, summary


def read(path, limit):
    with path.open('rb') as stream:
        return stream.read(limit + 1)


def render(report):
    rows = ''.join(f'<tr><th>{escape(status)}</th><td>{count}</td></tr>'
                   for status, count in report['counts']['byStatus'].items())
    reference = escape(json.dumps({'artifact': report['artifact'], 'sources': report['sources']},
                                 ensure_ascii=False, indent=2))
    omissions = escape(json.dumps({'omitted': report['counts']['omitted'],
                                  'privacySuppressedKeys': report['counts']['privacySuppressedKeys']},
                                 ensure_ascii=False, indent=2))
    return ('<!doctype html><html lang="ru"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Диагностика двух снимков</title><body><h1>Диагностика двух снимков</h1>'
            f'<p>Статус: {escape(report["status"])}, строк: {report["counts"]["rows"]}</p>'
            '<p>Ссылки совпали с переданными байтами. Сравнения заявил внешний экспортёр; '
            'арифметика не пересчитывалась. Персонаж, актуальность, выбранная страница, '
            'атомарность и причинность изменения неизвестны. Данные не используются для DPS.</p>'
            f'<table><caption>Счётчики статусов</caption>{rows}</table>'
            f'<h2>Исключённые данные</h2><pre>{omissions}</pre>'
            f'<h2>Ссылки на входные байты</h2><pre>{reference}</pre></body></html>')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Проверка двух снимков и сводка счётчиков',
                                     exit_on_error=False, allow_abbrev=False)
    for name in ('artifact', 'source-a', 'source-b', 'output'):
        parser.add_argument('--' + name, type=Path)
    try:
        arguments, extras = parser.parse_known_args(argv)
        if extras or any(value is None for value in vars(arguments).values()):
            raise ValueError('arguments')
        if arguments.output.exists() or arguments.output.is_symlink():
            raise FileExistsError
        report = summary(read(arguments.artifact, LIMITS['maxArtifactBytes']),
                         read(arguments.source_a, LIMITS['maxSourceBytes']),
                         read(arguments.source_b, LIMITS['maxSourceBytes']))
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.tli-native-diff-', dir=arguments.output.parent) as directory:
            stage = Path(directory)
            (stage / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
                                              + '\n', encoding='utf-8')
            (stage / 'index.html').write_text(render(report), encoding='utf-8')
            if arguments.output.exists() or arguments.output.is_symlink():
                raise FileExistsError
            stage.rename(arguments.output)
    except FileExistsError:
        print('Ошибка диагностики: каталог результата уже существует', file=sys.stderr)
        return 1
    except SummaryError as error:
        print('Ошибка диагностики: ' + error.code, file=sys.stderr)
        return 1
    except (OSError, ValueError, argparse.ArgumentError):
        print('Ошибка диагностики: не удалось проверить входы или записать результат', file=sys.stderr)
        return 1
    print('Диагностика сохранена: summary.json и index.html')
    return 0
