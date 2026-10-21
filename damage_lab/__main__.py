"""Create a fresh local damage database and an explicit scenario report."""

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from .engine import calculate
from .report import render


def parser():
    result = argparse.ArgumentParser(description="Локальная база TLI и условный расчёт DPS")
    result.add_argument("--package", required=True, type=Path, help="Каталог локального экспорта")
    result.add_argument("--observations", required=True, type=Path, help="JSON наблюдений с доказательствами")
    result.add_argument("--facts", required=True, type=Path, help="Проверенные правила TLIDB в JSON")
    result.add_argument("--output", required=True, type=Path, help="Новый каталог результата")
    result.add_argument("--basis", required=True, choices=("panel", "hit"), help="Панельный DPS либо некритический hit")
    result.add_argument("--active", required=True, type=int, help="Число активных Tangle")
    result.add_argument("--hits", required=True, type=int, help="Попадания в одну цель за каст одного Tangle")
    result.add_argument("--retention", required=True, type=float, help="Оставшаяся доля каждого следующего попадания, 0..1")
    result.add_argument("--resistance", required=True, type=float, help="Сопротивление холоду цели, доля: 40%% = 0.4")
    result.add_argument("--taken", required=True, type=float, help="Внешний increased damage taken, доля: 20%% = 0.2")
    result.add_argument("--uptime", required=True, type=float, help="Доля времени нанесения урона, 0..1")
    result.add_argument("--lucky", action=argparse.BooleanOptionalAction, default=None, help="Явно задать Lucky для --basis hit")
    result.add_argument("--critical-more", type=float, help="Критический more, доля: 26%% = 0.26; для --basis hit")
    return result


def main(argv=None, *, archiver=None):
    interface = parser()
    arguments = interface.parse_args(argv)
    if arguments.basis == "hit" and (arguments.lucky is None or arguments.critical_more is None):
        interface.error("--basis hit требует --lucky либо --no-lucky и --critical-more")
    if arguments.basis == "panel" and (arguments.lucky is not None or arguments.critical_more is not None):
        interface.error("Критические параметры задаются только для --basis hit, панель повторно не масштабируется")
    condition = {"basis": arguments.basis, "active": arguments.active, "hits": arguments.hits,
                 "retention": arguments.retention, "resistance": arguments.resistance,
                 "taken": arguments.taken, "uptime": arguments.uptime}
    if arguments.basis == "hit":
        condition.update(lucky=arguments.lucky, critical_more=arguments.critical_more)
    try:
        if arguments.output.exists():
            raise FileExistsError(f"Каталог результата уже существует: {arguments.output}")
        if archiver is None:
            from .archive import archive
            archiver = archive
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".damage-lab-", dir=arguments.output.parent) as folder:
            stage = Path(folder)
            record = archiver(arguments.package, arguments.observations, arguments.facts,
                              stage / "database.sqlite")
            calculation = calculate(record["stats"], condition)
            result = {"schema": 1, "status": "conditional", "name": record["name"],
                      "synthetic": record.get("synthetic", False),
                      "source_sha256": record.get("source_sha256"), "condition": condition,
                      "calculation": calculation, "benchmark": record.get("benchmark", {}),
                      "benchmark_role": "Independent validation only; never used as a damage multiplier"}
            (stage / "calculation.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            (stage / "index.html").write_text(render(record, calculation, condition), encoding="utf-8")
            if arguments.output.exists():
                raise FileExistsError(f"Каталог результата уже существует: {arguments.output}")
            stage.rename(arguments.output)
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        print(f"Ошибка расчёта: {str(error).rstrip('.')}", file=sys.stderr)
        return 1
    print(f"Условный DPS: {calculation['dps']:.6g}; отчёт: {arguments.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
