"""Publish a conditional upgrade comparison from one local scenario file."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .upgrades import evaluate
from .upgradereport import render


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Upgrade JSON cannot repeat object fields")
        result[key] = value
    return result


def reject(value):
    raise ValueError("Upgrade JSON cannot contain nonfinite constants")


def main(argv=None):
    """Write JSON and passive HTML together into a fresh result directory."""
    parser = argparse.ArgumentParser(description="Условное сравнение улучшений по заданным ценам",
                                     exit_on_error=False, allow_abbrev=False)
    parser.add_argument("--scenario", required=True, type=Path, help="JSON нормализованного сценария")
    parser.add_argument("--output", required=True, type=Path, help="Новый каталог результата")
    try:
        arguments, extras = parser.parse_known_args(argv)
        if extras:
            raise ValueError("Upgrade command arguments are unsupported")
        if arguments.output.exists():
            raise FileExistsError
        with arguments.scenario.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Upgrade scenario exceeds eight mebibytes")
        report = evaluate(json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique, parse_constant=reject))
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".tli-upgrades-", dir=arguments.output.parent) as directory:
            stage = Path(directory)
            (stage / "upgrades.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            (stage / "index.html").write_text(render(report), encoding="utf-8")
            if arguments.output.exists():
                raise FileExistsError
            stage.rename(arguments.output)
    except FileExistsError:
        print("Ошибка сравнения улучшений: каталог результата уже существует", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError, argparse.ArgumentError):
        print("Ошибка сравнения улучшений: не удалось обработать сценарий или записать результат", file=sys.stderr)
        return 1
    print(f"Условное сравнение улучшений: {arguments.output}")
    return 0
