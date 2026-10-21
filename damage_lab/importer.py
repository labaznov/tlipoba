"""Import available build evidence without requiring manual combat parameters."""

import argparse
import copy
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from .archive import BENCHMARK, REQUIRED_STATS
from .report import render_import
from .skillvalues import SOURCE


def logsummary(data):
    """Keep selection evidence without raw log payloads or identity claims."""
    if data["identity_verified"] is not False:
        raise ValueError("Panel log cannot verify build identity")
    result = {key: copy.deepcopy(data[key]) for key in (
        "format", "status", "known", "unknown_attributes", "identity_verified", "source_sha256",
    )}
    result["cohort"] = {key: copy.deepcopy(data["cohort"][key]) for key in ("timestamp", "frame")}
    return result


def snapshot(data):
    """Project the archive contract without native documents or account fields."""
    if data["import_status"] != "partial":
        raise ValueError("Import coverage must remain partial")
    result = {key: copy.deepcopy(data[key]) for key in (
        "name", "import_status", "missing_stats", "coverage",
    )}
    for key in ("capturedAt", "character", "synthetic", "source_sha256"):
        if key in data:
            result[key] = copy.deepcopy(data[key])
    result["stats"] = {key: value for key, value in data["stats"].items() if key in REQUIRED_STATS}
    result["benchmark"] = {key: value for key, value in data["benchmark"].items() if key in BENCHMARK}
    result["inventory"] = {
        section: [{"name": entry["name"], "details": copy.deepcopy(entry["details"])} for entry in entries]
        for section, entries in data["inventory"].items()
        if section in ("gear", "skills", "talents", "memories", "slates", "traits", "systems")
    }
    result["observations"] = []
    for entry in data.get("observations", []):
        if entry["key"] not in REQUIRED_STATS and entry["key"] not in {f"benchmark_{key}" for key in BENCHMARK}:
            continue
        row = {key: copy.deepcopy(entry[key]) for key in ("key", "label", "value", "unit", "precision", "evidence")}
        if "source" in entry:
            row["source"] = {key: copy.deepcopy(entry["source"][key]) for key in (
                "attr_id", "index", "raw_value", "timestamp", "frame", "line_numbers",
            )}
            if "raw_values" in entry["source"]:
                row["source"]["raw_values"] = copy.deepcopy(entry["source"]["raw_values"])
        result["observations"].append(row)
    if "native_stats" in data:
        result["native_stats"] = {key: copy.deepcopy(data["native_stats"][key]) for key in (
            "format", "status", "known", "unknown_stat_ids", "source_sha256", "protocol_verified",
            "missing_trait_levels", "missing_automatic_stats",
        ) if key in data["native_stats"]}
    if "panel_log" in data:
        result["panel_log"] = logsummary(data["panel_log"])
    if "skill_values" in data:
        result["skill_values"] = []
        for entry in data["skill_values"]:
            row = {key: copy.deepcopy(entry[key]) for key in (
                "group", "position", "role", "name", "level", "description_status", "description_level",
                "status", "values", "cells", "issues",
            )}
            row["source"] = {key: copy.deepcopy(entry["source"][key]) for key in SOURCE if key in entry["source"]}
            result["skill_values"].append(row)
    if "facts" in data:
        result["facts"] = {key: copy.deepcopy(data["facts"][key]) for key in ("patch", "checkedAt", "sources")
                           if key in data["facts"]}
    return result


def parser():
    interface = argparse.ArgumentParser(description="Частичный автоматический импорт локального билда TLI")
    interface.add_argument("--package", required=True, type=Path, help="Каталог локального экспорта")
    interface.add_argument("--output", required=True, type=Path, help="Новый каталог результата")
    interface.add_argument("--facts", type=Path, default=Path(__file__).parent / "data" / "combat-ss14.json",
                           help="База правил; по умолчанию встроенная SS14")
    interface.add_argument("--native-stats", type=Path, help="Автоматические показатели того же снимка")
    interface.add_argument("--panel-log", type=Path, help="Локальный лог панели с проверяемой привязкой к снимку")
    return interface


def main(argv=None, *, archiver=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.output.exists():
            raise FileExistsError(f"Каталог результата уже существует: {arguments.output}")
        if archiver is None:
            from .archive import archive
            archiver = archive
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".tli-import-", dir=arguments.output.parent) as directory:
            stage = Path(directory)
            inputs = {"native_stats": arguments.native_stats} if arguments.native_stats else {}
            if arguments.panel_log:
                inputs["panel_log"] = arguments.panel_log
            record = snapshot(archiver(arguments.package, None, arguments.facts, stage / "database.sqlite", **inputs))
            (stage / "import.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            (stage / "index.html").write_text(render_import(record), encoding="utf-8")
            if arguments.output.exists():
                raise FileExistsError(f"Каталог результата уже существует: {arguments.output}")
            stage.rename(arguments.output)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as error:
        print(f"Ошибка импорта: {str(error).rstrip('.')}", file=sys.stderr)
        return 1
    print(f"Частичный импорт: {arguments.output}; боевой DPS пока недоступен")
    return 0
