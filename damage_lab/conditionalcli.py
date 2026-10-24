"""Calculate conditional combat from an automatic import and separately declared combat context."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from .supportbundle import _constant, _float, _pairs


def _read(path, maximum, kind):
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('Automatic conditional input exceeds its byte limit')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)
    return value, {'kind': kind, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def main(argv=None):
    """Save an automatic conditional report into a new local directory."""
    parser = argparse.ArgumentParser(prog='python -m damage_lab conditional-combat',
                                    allow_abbrev=False, exit_on_error=False, add_help=False)
    parser.add_argument('--import', dest='record', action='append', type=Path)
    parser.add_argument('--skill', action='append')
    parser.add_argument('--context', action='append', type=Path)
    parser.add_argument('--output', action='append', type=Path)
    parser.add_argument('-h', '--help', action='store_true')
    try:
        arguments, extras = parser.parse_known_args(argv)
        options = (arguments.record, arguments.skill, arguments.context, arguments.output)
        if extras or any(len(value or []) > 1 for value in options):
            raise ValueError('Unsupported automatic conditional arguments')
        if arguments.help:
            parser.print_help()
            return 0
        if any(not value for value in options):
            raise ValueError('Automatic conditional arguments are incomplete')
        target = arguments.output[0]
        if os.path.lexists(target):
            raise FileExistsError
        target = target.resolve()
        if os.path.lexists(target):
            raise FileExistsError
        record, origin = _read(arguments.record[0], 4 * 1024**2, 'automatic_import_json')
        context, context_origin = _read(arguments.context[0], 1024**2, 'conditional_combat_context')
        from .conditionalreport import build, render

        report = build(record, context, skill_alias=arguments.skill[0], origins={'import': origin, 'context': context_origin})
        raw = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        page = render(report).encode('utf-8')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.tli-conditional-', dir=target.parent) as directory:
            stage = Path(directory)
            (stage / 'conditional-combat.json').write_bytes(raw)
            (stage / 'index.html').write_bytes(page)
            if os.path.lexists(target):
                raise FileExistsError
            stage.rename(target)
    except (argparse.ArgumentError, OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError, RuntimeError):
        print('Ошибка автоматического условного расчёта: входы или новый каталог результата не соответствуют контракту', file=sys.stderr)
        return 1
    print('Автоматический условный расчёт сохранён; полнота импорта и точный DPS не подтверждены')
    return 0
