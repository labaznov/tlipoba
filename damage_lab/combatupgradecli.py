"""Publish a caller-priced full combat comparison into a fresh local directory."""

import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from .combatupgrades import evaluate


MAX_BYTES = 8 * 1024 * 1024


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Combat comparison JSON repeats an object field")
        result[key] = value
    return result


def _finite(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("Combat comparison JSON has a nonfinite number")
    if value == 0 and any(digit in "123456789" for digit in token.lower().partition("e")[0]):
        raise ValueError("Combat comparison JSON number cannot underflow to zero")
    return value


def _reject(token):
    raise ValueError("Combat comparison JSON has a nonfinite constant")


def main(argv=None):
    """Write a validated comparison and passive HTML atomically without replacing existing paths."""
    parser = argparse.ArgumentParser(
        prog="python -m damage_lab combat-upgrades", description="Условное сравнение полного боевого DPS по заданным ценам",
        exit_on_error=False, allow_abbrev=False, add_help=False)
    parser.add_argument("--scenario", action="append", type=Path, help="JSON полного сценария сравнения")
    parser.add_argument("--output", action="append", type=Path, help="Новый каталог результата")
    parser.add_argument("-h", "--help", action="store_true", help="Показать описание команды")
    try:
        arguments, extras = parser.parse_known_args(argv)
        if extras or any(len(value or []) > 1 for value in (arguments.scenario, arguments.output)):
            raise ValueError("Combat comparison arguments are unsupported")
        if arguments.help:
            parser.print_help()
            return 0
        if not arguments.scenario or not arguments.output:
            raise ValueError("Combat comparison requires scenario and output")
        source, target = arguments.scenario[0], arguments.output[0]
    except (argparse.ArgumentError, TypeError, ValueError, AttributeError):
        print("Ошибка боевого сравнения: укажите --scenario и --output без лишних аргументов", file=sys.stderr)
        return 1
    try:
        if os.path.lexists(target):
            raise FileExistsError
        target = target.resolve()
        if os.path.lexists(target):
            raise FileExistsError
        with source.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Combat comparison scenario exceeds eight mebibytes")
        report = evaluate(json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique,
                                     parse_float=_finite, parse_constant=_reject))
        from .combatupgradereport import render

        comparison = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        page = render(report).encode("utf-8")
    except FileExistsError:
        print("Ошибка боевого сравнения: путь результата уже существует", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError, ImportError, RuntimeError):
        print("Ошибка боевого сравнения: не удалось проверить сценарий или подготовить отчёт", file=sys.stderr)
        return 1
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".tli-combat-upgrades-", dir=target.parent) as directory:
            stage = Path(directory)
            (stage / "comparison.json").write_bytes(comparison)
            (stage / "index.html").write_bytes(page)
            if os.path.lexists(target):
                raise FileExistsError
            stage.rename(target)
    except FileExistsError:
        print("Ошибка боевого сравнения: путь результата уже существует", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, AttributeError, OverflowError, RuntimeError):
        print("Ошибка боевого сравнения: не удалось сохранить новый результат", file=sys.stderr)
        return 1
    print("Условное сравнение боя сохранено")
    return 0
