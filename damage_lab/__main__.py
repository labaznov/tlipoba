"""Create a fresh local damage database and an explicit scenario report."""

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from .archive import REQUIRED_STATS
from .combat import apply
from .engine import calculate
from .report import render
from .validation import compare


def parser():
    result = argparse.ArgumentParser(description="Локальная база TLI и условный расчёт DPS")
    result.add_argument("--package", required=True, type=Path, help="Каталог локального экспорта")
    result.add_argument("--observations", type=Path, help="Необязательный JSON дополнительных наблюдений с доказательствами")
    result.add_argument("--facts", required=True, type=Path, help="Проверенные правила TLIDB в JSON")
    result.add_argument("--output", required=True, type=Path, help="Новый каталог результата")
    result.add_argument("--basis", required=True, choices=("panel", "hit"), help="Панельный DPS либо некритический hit")
    result.add_argument("--active", required=True, type=int, help="Число активных Tangle")
    result.add_argument("--hits", required=True, type=int, help="Попадания в одну цель за каст одного Tangle")
    result.add_argument("--retention", required=True, type=float, help="Оставшаяся доля каждого следующего попадания, 0..1")
    result.add_argument("--resistance", required=True, type=float, help="Эффективное сопротивление холоду цели, доля: 40%% = 0.4")
    result.add_argument("--taken", required=True, type=float, help="Внешний increased damage taken, доля: 20%% = 0.2")
    result.add_argument("--uptime", required=True, type=float, help="Доля времени нанесения урона, 0..1")
    result.add_argument("--lucky", action=argparse.BooleanOptionalAction, default=None, help="Явно задать Lucky для --basis hit")
    result.add_argument("--critical-more", type=float, help="Критический more, доля: 26%% = 0.26; для --basis hit")
    result.add_argument("--combat", type=Path, help="JSON исходного и целевого боевого состояния, без повторного учёта панели")
    result.add_argument("--native-stats", type=Path, help="Автоматически извлечённые статы того же source.json; импорт пока частичный")
    logs = result.add_mutually_exclusive_group()
    logs.add_argument("--panel-log", type=Path, help="Нормализованный JSON панели для сопоставления с native Spell DPS")
    logs.add_argument("--game-log", type=Path, help="Исходный игровой журнал без промежуточного JSON")
    return result


def main(argv=None, *, archiver=None):
    commands = list(sys.argv[1:] if argv is None else argv)
    if commands and commands[0] == "import":
        from .importer import main as importing
        return importing(commands[1:], archiver=archiver)
    if commands and commands[0] == "upgrades":
        from .upgradecli import main as upgrading
        return upgrading(commands[1:])
    interface = parser()
    arguments = interface.parse_args(commands)
    if arguments.basis == "hit" and (arguments.lucky is None or arguments.critical_more is None):
        interface.error("--basis hit требует --lucky либо --no-lucky и --critical-more")
    if arguments.basis == "panel" and (arguments.lucky is not None or arguments.critical_more is not None):
        interface.error("Критические параметры задаются только для --basis hit, панель повторно не масштабируется")
    condition = {"basis": arguments.basis, "active": arguments.active, "hits": arguments.hits,
                 "retention": arguments.retention, "resistance": arguments.resistance,
                 "taken": arguments.taken, "uptime": arguments.uptime}
    condition["observations_provided"] = arguments.observations is not None
    if arguments.basis == "hit":
        condition.update(lucky=arguments.lucky, critical_more=arguments.critical_more)
    try:
        if arguments.output.exists():
            raise FileExistsError(f"Каталог результата уже существует: {arguments.output}")
        if arguments.combat:
            condition["combat"] = json.loads(arguments.combat.read_text(encoding="utf-8-sig"))
        if archiver is None:
            from .archive import archive
            archiver = archive
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".damage-lab-", dir=arguments.output.parent) as folder:
            stage = Path(folder)
            inputs = {"native_stats": arguments.native_stats} if arguments.native_stats else {}
            if arguments.panel_log:
                inputs["panel_log"] = arguments.panel_log
            if arguments.game_log:
                inputs["game_log"] = arguments.game_log
            record = archiver(arguments.package, arguments.observations, arguments.facts,
                              stage / "database.sqlite", **inputs)
            if arguments.observations is None:
                missing = [key for key in REQUIRED_STATS if key not in record["stats"]]
                if missing:
                    raise ValueError("Не хватает автоматически извлечённых показателей: " + ", ".join(missing)
                                     + "; импорт остаётся частичным")
            calculation = calculate(record["stats"], condition)
            if "combat" in condition:
                calculation = apply(record["stats"], calculation, condition["combat"])
                (stage / "combat.json").write_text(
                    json.dumps(condition["combat"], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
            result = {"schema": 1, "status": "conditional", "name": record["name"],
                      "synthetic": record.get("synthetic", False),
                      "source_sha256": record.get("source_sha256"), "condition": condition,
                      "calculation": calculation, "benchmark": record.get("benchmark", {}),
                      "benchmark_role": "Independent validation only; never used as a damage multiplier"}
            if "average_dps" in result["benchmark"]:
                result["validation"] = compare(calculation["dps"], result["benchmark"]["average_dps"])
            if "native_stats" in record:
                result["native_stats"] = record["native_stats"]
            if "panel_log" in record:
                from .importer import logsummary
                result["panel_log"] = logsummary(record["panel_log"])
            if "trait_ranks" in record:
                from .importer import ranksummary
                result["trait_ranks"] = ranksummary(record["trait_ranks"])
            if "import_coverage" in record:
                from .importcoverage import summary
                result["import_coverage"] = summary(record["import_coverage"])
            if "build_resolution" in record:
                from .buildresolution import summary
                result["build_resolution"] = summary(record["build_resolution"])
            from .importer import staticsummary
            result.update(staticsummary(record))
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
