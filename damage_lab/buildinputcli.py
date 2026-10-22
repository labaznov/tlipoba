"""Prepare automatic raw-input candidates without calculating character damage."""

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile


def main(argv=None, *, archiver=None):
    """Save automatic input diagnostics into a fresh local result directory."""
    parser = argparse.ArgumentParser(
        prog="python -m damage_lab inputs", description="Автоматическая подготовка входных данных навыка",
        exit_on_error=False, allow_abbrev=False, add_help=False)
    for name in ("package", "output", "facts", "native-stats", "panel-log", "game-log"):
        parser.add_argument("--" + name, action="append", type=Path)
    parser.add_argument("--skill", action="append", help="Публичный alias камня gem[n]")
    parser.add_argument("-h", "--help", action="store_true", help="Показать описание команды")
    try:
        arguments, extras = parser.parse_known_args(argv)
        if extras or any(len(value or []) > 1 for value in (
                arguments.package, arguments.output, arguments.facts, arguments.native_stats,
                arguments.panel_log, arguments.game_log, arguments.skill)):
            raise ValueError("Input command arguments are unsupported")
        if arguments.panel_log and arguments.game_log:
            raise ValueError("Panel log and game log are mutually exclusive")
        if arguments.help:
            parser.print_help()
            return 0
        if (not arguments.package or not arguments.output or not arguments.skill
                or re.fullmatch(r"gem\[[1-9][0-9]{0,8}\]", arguments.skill[0], re.ASCII) is None):
            raise ValueError("Input command requires package skill and output")
    except (argparse.ArgumentError, TypeError, ValueError, AttributeError):
        print("Ошибка подготовки входных данных: укажите --package, --skill gem[n] и --output без лишних аргументов", file=sys.stderr)
        return 1
    try:
        target = arguments.output[0]
        if os.path.lexists(target):
            raise FileExistsError
        target = target.resolve()
        if os.path.lexists(target):
            raise FileExistsError
        if archiver is None:
            from .archive import archive
            archiver = archive
        inputs = {}
        for name, value in (("native_stats", arguments.native_stats), ("panel_log", arguments.panel_log),
                            ("game_log", arguments.game_log)):
            if value:
                inputs[name] = value[0]
        facts = arguments.facts[0] if arguments.facts else Path(__file__).with_name("data") / "combat-ss14.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".tli-build-inputs-", dir=target.parent) as directory:
            stage = Path(directory)
            database = stage / "database.sqlite"
            record = archiver(arguments.package[0], None, facts, database, **inputs)
            from .buildinputs import assemble
            from .buildinputreport import render

            report = assemble(record, skill_alias=arguments.skill[0])
            raw = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
            page = render(report).encode("utf-8")
            if not database.is_file():
                raise ValueError("Input preparation requires its archived database")
            (stage / "inputs.json").write_bytes(raw)
            (stage / "index.html").write_bytes(page)
            if os.path.lexists(target):
                raise FileExistsError
            stage.rename(target)
    except FileExistsError:
        print("Ошибка подготовки входных данных: путь результата уже существует", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError,
            ImportError, RuntimeError, sqlite3.Error):
        print("Ошибка подготовки входных данных: не удалось проверить пакет или сохранить новый результат", file=sys.stderr)
        return 1
    print("Входные данные сохранены; расчёт DPS не выполнялся")
    return 0
