"""Import available build evidence without requiring manual combat parameters."""

import argparse
import copy
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from .archive import BENCHMARK, OPTIONAL_STATS, REQUIRED_STATS
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
    if "input_kind" in data:
        if data["input_kind"] not in ("game_log", "panel_log"):
            raise ValueError("Panel log input kind must be game_log or panel_log")
        result["input_kind"] = data["input_kind"]
    if "numeric_policy" in data:
        from .logstats import policy
        result["numeric_policy"] = policy(data["numeric_policy"])
    return result


def ranksummary(data):
    """Keep only diagnostic rank fields, without raw instance identifiers."""
    def select(row, fields):
        return {key: copy.deepcopy(row[key]) for key in fields if key in row}

    if data["rule_status"] != "rank_rule_unverified" or any(row["rank"] is not None for row in data["traits"]):
        raise ValueError("Trait rank candidates cannot select or verify a rank")
    result = select(data, ("format", "source_sha256", "rule_status", "memories_without_selected_trait",
                           "gaps", "assumptions"))
    result["traits"] = []
    for entry in data["traits"]:
        row = select(entry, ("trait_id", "index", "rank", "memory_position", "status", "candidates_agree"))
        row["candidates"] = [select(candidate, ("rule", "formula", "inputs", "value", "status"))
                             for candidate in entry["candidates"]]
        result["traits"].append(row)
    result["memories"] = []
    for entry in data["memories"]:
        row = select(entry, ("position", "base_id", "fixed_affix_contribution", "fixed_affix_source", "consistency"))
        row["fields"] = {key: select(entry["fields"][key], ("path", "status", "value"))
                         for key in ("client_fixed", "from_enhance", "server_fixed", "level")}
        row["linkage"] = select(entry["linkage"], ("status", "slot", "server_index", "reason"))
        result["memories"].append(row)
    return result


def staticsummary(data):
    """Keep a partial static ledger bound to this record and its declared catalog inputs."""
    from .staticcombat import summary

    if "static_combat" not in data:
        if "static_combat_provenance" in data:
            raise ValueError("Static combat provenance requires its diagnostic ledger")
        return {}
    ledger = summary(data["static_combat"])
    if ledger["source"]["sha256"] != data.get("source_sha256"):
        raise ValueError("Static combat ledger differs from the record source hash")
    result = {"static_combat": ledger}
    if "static_combat_provenance" in data:
        from .staticbundle import summary
        result["static_combat_provenance"] = summary(data["static_combat_provenance"], ledger)
    return result


def installedsummary(data):
    """Keep observed installation bound to the same record source."""
    if "installed_skills" not in data:
        return {}
    from .installedskills import summary

    installation = summary(data["installed_skills"])
    if installation["source"]["sha256"] != data.get("source_sha256"):
        raise ValueError("Installed skills inventory differs from the record source hash")
    return {"installed_skills": installation}


def supportsummary(data):
    """Keep paired diagnostic support evidence without applying it to damage."""
    if "installed_support_effects" not in data and "installed_support_catalog" not in data:
        return {}
    if "installed_support_effects" not in data or "installed_support_catalog" not in data:
        raise ValueError("Support effect inventory and catalog require paired diagnostic documents")
    from .supportbundle import summary

    inventory, catalog = summary(data["installed_support_effects"], data["installed_support_catalog"])
    if inventory["source"]["sha256"] != data.get("source_sha256"):
        raise ValueError("Support effect inventory differs from the record source hash")
    return {"installed_support_effects": inventory, "installed_support_catalog": catalog}


def profilesummary(data):
    """Keep diagnostic catalog lookups without promoting observed gem levels."""
    if "installed_skill_profiles" not in data:
        return {}
    from .installedprofiles import summary

    profiles = summary(data["installed_skill_profiles"])
    if profiles["source"]["sha256"] != data.get("source_sha256"):
        raise ValueError("Installed skill profiles differ from the record source hash")
    return {"installed_skill_profiles": profiles}


def memorysummary(data):
    """Keep memory definitions bound to this record without assigning combat roles."""
    if "memory_definitions" not in data:
        return {}
    from .memorybundle import summary

    bundle = summary(data["memory_definitions"])
    if bundle["ledger"]["source"]["sha256"] != data.get("source_sha256"):
        raise ValueError("Memory definitions differ from the record source hash")
    return {"memory_definitions": bundle}


def levelsummary(data):
    """Keep diagnostic level candidates bound to the record and its observed installation."""
    if "installed_level_candidates" not in data:
        return {}
    from .levelbundle import summary

    bundle = summary(data["installed_level_candidates"], data.get("installed_skills"))
    if bundle["source"]["sha256"] != data.get("source_sha256"):
        raise ValueError("Installed level candidates differ from the record source hash")
    return {"installed_level_candidates": bundle}


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
    result["stats"] = {key: value for key, value in data["stats"].items() if key in REQUIRED_STATS + OPTIONAL_STATS}
    result["benchmark"] = {key: value for key, value in data["benchmark"].items() if key in BENCHMARK}
    result["inventory"] = {
        section: [{"name": entry["name"], "details": copy.deepcopy(entry["details"])} for entry in entries]
        for section, entries in data["inventory"].items()
        if section in ("gear", "skills", "talents", "memories", "slates", "traits", "systems")
    }
    result["observations"] = []
    for entry in data.get("observations", []):
        if (entry["key"] not in REQUIRED_STATS + OPTIONAL_STATS
                and entry["key"] not in {f"benchmark_{key}" for key in BENCHMARK}):
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
    if "trait_ranks" in data:
        result["trait_ranks"] = ranksummary(data["trait_ranks"])
    if "import_coverage" in data:
        from .importcoverage import summary
        result["import_coverage"] = summary(data["import_coverage"])
    if "build_resolution" in data:
        from .buildresolution import summary
        result["build_resolution"] = summary(data["build_resolution"])
    result.update(staticsummary(data))
    result.update(installedsummary(data))
    result.update(supportsummary(data))
    result.update(profilesummary(data))
    result.update(levelsummary(data))
    result.update(memorysummary(data))
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
    logs = interface.add_mutually_exclusive_group()
    logs.add_argument("--panel-log", type=Path, help="Нормализованный JSON панели для сопоставления с native Spell DPS")
    logs.add_argument("--game-log", type=Path, help="Исходный игровой журнал без промежуточного JSON")
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
            if arguments.game_log:
                inputs["game_log"] = arguments.game_log
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
