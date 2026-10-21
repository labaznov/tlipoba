"""Local SQLite archive of one build with explicit observed or synthetic origins."""

import contextlib
import datetime
import hashlib
import json
import math
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .skillvalues import extract

PACKAGE = {"build": "build.json", "guide": "guide-data.json", "manifest": "manifest.json",
           "transfer": "transfer-report.json", "source": "source.json"}
STORED = ("build", "manifest", "transfer")
REQUIRED_STATS = ("spell_dps", "hit_min", "hit_max", "cast_rate", "crit_chance", "crit_multiplier",
                  "max_tangles", "extra_attachments", "cold_penetration")
OPTIONAL_STATS = ("armor_penetration",)
BENCHMARK = ("average_dps", "duration", "highest_5s", "average_5s", "survival")
EXPECTED_UNITS = {
    "spell_dps": "damage/s", "hit_min": "damage", "hit_max": "damage", "cast_rate": "casts/s",
    "crit_chance": "fraction", "crit_multiplier": "multiplier", "max_tangles": "count",
    "extra_attachments": "count", "cold_penetration": "fraction",
    "armor_penetration": "fraction",
    "benchmark_average_dps": "damage/s", "benchmark_duration": "s",
    "benchmark_highest_5s": "damage/s", "benchmark_average_5s": "damage/s", "benchmark_survival": "survival",
}
UNITS = {"damage/s": "", "damage": "", "casts/s": "/s", "fraction": "%", "multiplier": "%",
         "count": "", "rating": "", "flat": "", "s": "s", "survival": ""}
MAGNITUDES = {"K": Decimal(1000), "M": Decimal(10) ** 6, "B": Decimal(10) ** 9}
CORES = (("selectedNotable12", 12), ("selectedNotable24", 24))
SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sources (role TEXT PRIMARY KEY, path TEXT NOT NULL, sha256 TEXT, bytes INTEGER,
                      modified TEXT, stored INTEGER NOT NULL);
CREATE TABLE documents (role TEXT PRIMARY KEY, json TEXT NOT NULL);
CREATE TABLE observations (key TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
                           display TEXT NOT NULL, value NOT NULL, unit TEXT NOT NULL,
                           precision TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE TABLE inventory (section TEXT NOT NULL, position INTEGER NOT NULL, name TEXT NOT NULL,
                        details TEXT NOT NULL, PRIMARY KEY (section, position));
CREATE TABLE systems (name TEXT PRIMARY KEY, status TEXT NOT NULL, report TEXT, build TEXT);
CREATE TABLE coverage (position INTEGER PRIMARY KEY, text TEXT NOT NULL);
"""


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path):
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def lines(text):
    return [line for line in str(text).split("\n") if line]


def displayed(text, unit):
    """Return the displayed number in value units and half of its last displayed step."""
    raw = text.strip()
    if unit == "s" and raw.count(":") == 2:
        hours, minutes, seconds = (Decimal(part) for part in raw.split(":"))
        return hours * 3600 + minutes * 60 + seconds, Decimal("0.5")
    suffix = UNITS[unit]
    if not raw.endswith(suffix):
        raise ValueError(f"display {text!r} does not end with {suffix!r}")
    raw = raw[:len(raw) - len(suffix)].strip().replace(",", "")
    scale = Decimal("0.01") if suffix == "%" else Decimal(1)
    if raw[-1:] in MAGNITUDES:
        scale, raw = scale * MAGNITUDES[raw[-1]], raw[:-1]
    number = Decimal(raw)
    return number * scale, Decimal(10) ** min(0, number.as_tuple().exponent) * scale / 2


def observation(row, kind, evidence, prefix=""):
    key = prefix + row["key"]
    value, unit, display = row["value"], row["unit"], row["display"]
    if unit not in UNITS:
        raise ValueError(f"{key}: unknown unit {unit!r}")
    if key in EXPECTED_UNITS and unit != EXPECTED_UNITS[key]:
        raise ValueError(f"{key}: unit must be {EXPECTED_UNITS[key]}")
    try:
        if not math.isfinite(value):
            raise ValueError(f"{key}: value must be a finite number")
        numeric = Decimal(str(value))
    except (InvalidOperation, TypeError, OverflowError):
        raise ValueError(f"{key}: value must be a finite number") from None
    try:
        number, half = displayed(display, unit)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{key}: {error}") from None
    if number != numeric:
        raise ValueError(f"{key}: value {value} does not match display {display!r} in {unit}")
    if row.get("evidence") not in evidence:
        raise ValueError(f"{key}: unknown evidence {row.get('evidence')!r}")
    return {"key": key, "kind": kind, "label": row["label"], "display": display, "value": value,
            "unit": unit, "precision": f"display {display}; ±{format(half.normalize(), 'f')} {unit}",
            "evidence": evidence[row["evidence"]]}


def recorded(data, *, partial=False):
    """Normalize available values while requiring complete explicit developer inputs."""
    evidence = {key: item["path"] for key, item in data["evidence"].items()}
    rows = [observation(row, "panel", evidence) for row in data["panel"]]
    bench = data["benchmark"]
    rows += [observation({**row, "evidence": row["evidence"] if "evidence" in row else bench["evidence"]},
                         "benchmark", evidence, "benchmark_")
             for row in bench["values"]]
    keys = [row["key"] for row in rows]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Duplicate observations: {', '.join(duplicates)}")
    stats = {row["key"]: row["value"] for row in rows if row["kind"] == "panel"}
    benchmark = {row["key"][len("benchmark_"):]: row["value"] for row in rows if row["kind"] == "benchmark"}
    for name, required, present in (("stats", REQUIRED_STATS, stats), ("benchmark", BENCHMARK, benchmark)):
        missing = [key for key in required if key not in present]
        if missing and not partial:
            raise ValueError(f"Missing {name}: {', '.join(missing)}")
    return rows, stats, {key: benchmark[key] for key in BENCHMARK if key in benchmark}, evidence


def gear(guide):
    return [{"name": item["name"],
             "details": [" · ".join(str(part) for part in (
                 item.get("slot"), item.get("rarity"),
                 f"item level {item['itemLevel']}" if "itemLevel" in item else None) if part)]
             + [line for affix in item.get("affixes", []) for line in lines(affix["text"])]}
            for item in guide["gear"]]


def skills(guide, loadout):
    rolls = {support["supportGuid"]: support["lineRolls"]
             for group in ("activeSkills", "passiveSkills") for skill in loadout["skills"][group]
             for support in skill.get("supports", []) if support and support.get("lineRolls")}

    def label(skill):
        parts = [f"level {skill['level']}" if "level" in skill else None,
                 f"rank {skill['rank']}" if "rank" in skill else None]
        text = f"{skill['name']} ({', '.join(part for part in parts if part)})" if any(parts) else skill["name"]
        if skill.get("guid") in rolls:
            text += "; rolls " + "; ".join(", ".join(format(value, "g") for value in values)
                                           for values in rolls[skill["guid"]].values())
        return text

    return [{"name": label(group["main"]), "details": [group["kind"]] + [label(support) for support in group["supports"]]}
            for group in guide["skillGroups"]]


def talents(guide, loadout, coverage):
    trees = {tree["id"]: tree for tree in guide["talentTrees"]}
    entries = []
    for slot in loadout["skillTree"]["slots"]:
        tree = trees.get(slot["treeId"])
        if tree is None:
            raise ValueError(f"Talent tree {slot['treeId']} is missing from guide-data.json")
        ranked = {node["guid"]: node for node in tree["nodes"] if node.get("rank", 0) > 0}
        if {guid: node["rank"] for guid, node in ranked.items()} != slot["nodePoints"]:
            raise ValueError(f"Talent ranks of {slot['treeId']} differ between build.json and guide-data.json")
        notables = {notable["guid"]: notable for notable in tree.get("notables", [])}
        details = []
        for field, threshold in CORES:
            guid = slot.get(field)
            if guid is None:
                continue
            if guid not in notables:
                raise ValueError(f"Selected core {guid} of {slot['treeId']} is missing from guide-data.json")
            core = notables[guid]
            details.append(f"core {threshold}: {core['englishName']} — {'; '.join(lines(core['text']))}")
        override = slot.get("prismCoreTalentOverride")
        if override:
            details.append(f"Замена core призмой: {override['name']} — "
                           f"{'; '.join(lines(override.get('description', '')))}")
        elif (slot.get("equippedPrism") or {}).get("replacesCoreTalent"):
            coverage.append(f"{tree['englishName']}: призма заменяет core, описание замены отсутствует в build.json")
        details += [f"{node['rank']}/{node['maxPoints']} {node['type']}: {'; '.join(lines(node['text']))}"
                    for node in ranked.values()]
        entries.append({"name": f"{tree['englishName']} ({tree.get('points', 0)} points)", "details": details})
    return entries


def systems(transfer, loadout):
    reported = transfer.get("systems", {})
    rows, entries = [], []
    for name in list(reported) + [key for key in loadout if key not in reported
                                  and key not in ("id", "name", "order", "hiddenInGuide")]:
        report = reported.get(name)
        rows.append((name, report["status"] if report else "build_only",
                     json.dumps(report, ensure_ascii=False) if report else None,
                     json.dumps(loadout[name], ensure_ascii=False) if name in loadout else None))
        if report:
            details = [f"status: {report['status']}"]
            details += [f"{field}: {report[field]}" for field in
                        ("observed", "mapped", "affixesObserved", "affixesMapped", "decodedEffects") if field in report]
            details += [f"utility: {spirit['name']} rank {spirit['rank']}" for spirit in report.get("utilityPactspirits", [])]
            details += report.get("issues", [])
            if report.get("effectMappingComplete") is False:
                details.append("effect mapping incomplete")
            entries.append({"name": name, "details": details})
    return rows, entries


def slates(transfer):
    """Expose decoded effects without inventing a Divinity board placement."""
    entries = []
    for position, slate in enumerate(transfer.get("systems", {}).get("divinity", {}).get("decodedSlates", [])):
        catalog = slate["catalogBase"] or {}
        details = [
            f"sourceBaseId: {slate['sourceBaseId']}", f"catalogBase: {catalog.get('guid', 'unknown')}",
            f"sourceEncoding: {slate['sourceEncoding']}",
            f"influenceCorroborated: {json.dumps(slate['influenceCorroborated'])}",
            f"unmappedTalentIds: {json.dumps(slate['unmappedTalentIds'])}",
            f"provenance: transfer-report.json / systems.divinity.decodedSlates[{position}]",
            "layout: unknown (shape, direction, board position)",
            "damage application: not applied automatically",
        ]
        details += [f"{effect['list']}[{effect['slotIndex']}] {effect['tlidbId']} / {effect['modGuid']} / "
                    f"{effect['nodeType']} / {effect['slateType']}: "
                    + "; ".join(lines(effect["description"].replace("\\n", "\n")))
                    for effect in slate["effects"]]
        entries.append({"name": catalog.get("name") or f"Unknown divinity slate ({slate['sourceBaseId']})",
                        "details": details})
    return entries


def nativecheck(document, source):
    """Accept only named fields corroborated for the observed attrInfo contract."""
    try:
        if document.get("format") != "tli-native-stats-v1" or document.get("status") != "decoded":
            raise ValueError("Native stats must use decoded tli-native-stats-v1 format")
        if document.get("source", {}).get("sha256") != source:
            raise ValueError("Native stats source sha256 does not match package/source.json")
        if (document["profile"]["name"] != "attrInfo-v1"
                or document["profile"]["message"] != "rpc.ViewPlayerAttrInfo"
                or document["source"]["section"] != "sections.ServerSource.data.attrInfo"):
            raise ValueError("Native stats profile does not match the supported attrInfo contract")
        keys = set()
        for entry in document["known"] + []:
            key = entry["key"]
            if key not in {"spell_dps": "1.10", "survival": "1.11"} or key in keys:
                raise ValueError("Native stats contain an unsupported or duplicate known field")
            keys.add(key)
            if (entry["wire"] != {"spell_dps": "1.10", "survival": "1.11"}[key]
                    or entry["wireType"] != "varint" or entry["evidence"] != "corroborated"
                    or entry["protocolVerified"] is not False
                    or entry["sourcePath"] != "sections.ServerSource.data.attrInfo[1].bytesHex"
                    or not entry["corroboration"].strip()):
                raise ValueError("Native stats known field lacks the exact corroborated wire contract")
            if entry["value"] is True or entry["value"] is False or not 0 <= entry["value"] <= 2**63 - 1:
                raise ValueError("Native stats known value must be a nonnegative signed varint")
            try:
                format(entry["value"], "d")
            except (ValueError, TypeError):
                raise ValueError("Native stats known value must be a nonnegative signed varint") from None
        counts = {"known": len(document["known"]),
                  "unknownStatIds": sum("statId" in row for row in document["unknown"] + []),
                  "unknownEntries": len(document["unknown"]), "omitted": len(document["omitted"] + [])}
        for key, count in counts.items():
            if document["coverage"][key] is True or document["coverage"][key] is False or document["coverage"][key] != count:
                raise ValueError("Native stats coverage counts do not match the decoded entries")
        if sorted(document["coverage"]["missing"] + []) != sorted({"spell_dps", "survival"} - keys):
            raise ValueError("Native stats missing-field coverage does not match the known entries")
        if document["heroTraits"]["levels"] is not None:
            raise ValueError("Native stats hero trait levels are not supported by this profile")
        for gap in document["gaps"] + []:
            if not gap.strip():
                raise ValueError("Native stats gaps must contain nonempty descriptions")
    except (KeyError, TypeError, AttributeError):
        raise ValueError("Native stats document has invalid field structure") from None


def automatic(data, path, source):
    """Merge named native fields while preserving developer evidence for other stats."""
    document = load(path)
    nativecheck(document, source)
    observed = {**data, "panel": [dict(row) for row in data["panel"]],
                "benchmark": {**data["benchmark"], "values": [dict(row) for row in data["benchmark"]["values"]]},
                "evidence": dict(data["evidence"])}
    coverage = [f"Native stats: known: {document['coverage']['known']}; "
                f"unknownStatIds: {document['coverage']['unknownStatIds']}; "
                f"unknownEntries: {document['coverage']['unknownEntries']}; protocolVerified=false",
                "Native stats: missing hero trait levels; no unverified stat IDs were named"]
    coverage += [f"Native stats gap: {gap}" for gap in document["gaps"]]
    if document["coverage"]["missing"]:
        coverage.append("Native stats missing known fields: " + ", ".join(document["coverage"]["missing"]))
    for entry in document["known"]:
        key = entry["key"]
        evidence = f"native_stats:{key}"
        observed["evidence"][evidence] = {"path": str(Path(path).resolve()), "shows": entry["sourcePath"]}
        rows = observed["panel"] if key == "spell_dps" else observed["benchmark"]["values"]
        row = {"key": key, "label": "Spell DPS" if key == "spell_dps" else "My Survival",
               "display": format(entry["value"], "d"), "value": entry["value"],
               "unit": "damage/s" if key == "spell_dps" else "survival", "evidence": evidence}
        matches = [position for position, value in enumerate(rows) if value["key"] == key]
        if len(matches) > 1:
            raise ValueError("Native stats cannot replace duplicate developer observations")
        if matches:
            previous = rows[matches[0]]["value"]
            if previous != entry["value"]:
                coverage.append(f"Native stats conflict: {key}; developer input {previous}; "
                                f"automatic {entry['value']} used from wire {entry['wire']}")
            rows[matches[0]] = row
        else:
            rows.append(row)
        coverage.append(f"Native stats field: {key}; wire {entry['wire']}; {entry['wireType']}; "
                        "evidence=corroborated; protocolVerified=false")
    return observed, document, coverage


def logged(data, path, native, *, raw=False):
    """Enrich native-bound observations with one corroborated log cohort."""
    from .logstats import select
    from .panellog import snapshot

    anchors = [] if native is None else [entry["value"] for entry in native["known"] if entry["key"] == "spell_dps"]
    if len(anchors) != 1:
        raise ValueError("Panel log requires a corroborated native Spell DPS anchor")
    document = snapshot(path) if raw else load(path)
    selection = select(document, anchors[0])
    summary = {key: selection["summary"][key] for key in (
        "format", "status", "known", "unknown_attributes", "cohort", "identity_verified", "source_sha256",
    )}
    summary["cohort"] = {key: summary["cohort"][key] for key in ("timestamp", "frame")}
    summary["input_kind"] = "game_log" if raw else "panel_log"
    if summary["status"] != "corroborated" or summary["identity_verified"] is not False:
        raise ValueError("Panel log must remain corroborated without a verified player identity")
    selection["summary"] = summary
    observed = {**data, "panel": [dict(row) for row in data["panel"]],
                "benchmark": {**data["benchmark"], "values": [dict(row) for row in data["benchmark"]["values"]]},
                "evidence": dict(data["evidence"])}
    coverage = [f"Panel log: known: {summary['known']}; unknown_attributes: {summary['unknown_attributes']}; "
                "identity_verified=false",
                "Panel log corroborates the native Spell DPS state; player identity and combat mechanics remain unverified"]
    coverage += [f"Panel log issue: {issue}" for issue in selection["issues"]]
    for entry in selection["rows"]:
        key = entry["key"]
        if key not in REQUIRED_STATS + OPTIONAL_STATS:
            raise ValueError("Panel log contains an unsupported normalized characteristic")
        evidence = f"panel_log:{key}"
        observed["evidence"][evidence] = {"path": str(Path(path).resolve()), "shows": entry["source"]}
        row = {field: entry[field] for field in ("key", "label", "value", "display", "unit")}
        row["evidence"] = evidence
        matches = [position for position, value in enumerate(observed["panel"]) if value["key"] == key]
        if len(matches) > 1:
            raise ValueError("Panel log cannot replace duplicate observations")
        if matches:
            previous = observed["panel"][matches[0]]["value"]
            if previous != entry["value"]:
                coverage.append(f"Panel log conflict: {key}; previous input {previous}; corroborated log {entry['value']} used")
            observed["panel"][matches[0]] = row
        else:
            observed["panel"].append(row)
    coverage.append(f"Panel log refines rounded native Spell DPS anchor {anchors[0]} with full-precision log values")
    return observed, document, selection, coverage


def archive(package: Path, observations: Path | None, facts: Path, database: Path, *,
            native_stats: Path | None = None, panel_log: Path | None = None,
            game_log: Path | None = None) -> dict:
    """Archive a package with optional developer observations and explicit import gaps."""
    if panel_log is not None and game_log is not None:
        raise ValueError("game_log and panel_log are mutually exclusive")
    package, facts, database = (Path(package), Path(facts), Path(database))
    if observations is not None:
        observations = Path(observations)
    if database.exists():
        raise FileExistsError(f"Database already exists: {database}")
    files = {role: package / name for role, name in PACKAGE.items()}
    for path in files.values():
        if not path.is_file():
            raise FileNotFoundError(f"Package file is missing: {path}")
    hashes = {role: fingerprint(path) for role, path in files.items()}
    documents = {role: load(files[role]) for role in STORED}
    manifest, transfer, build = documents["manifest"], documents["transfer"], documents["build"]
    if manifest.get("buildSha256") != hashes["build"][0]:
        raise ValueError("build.json does not match buildSha256 in manifest.json")
    guide = load(files["guide"])
    guide.pop("sourceSections", None)
    documents["skill_values"] = extract(guide)
    developer = load(observations) if observations is not None else {"evidence": {}, "panel": [], "benchmark": {"values": []}}
    facts_data = load(facts)
    observed = developer
    coverage = []
    bundle = None
    if native_stats is None and "nativeStats" in manifest:
        bundle = manifest["nativeStats"]
        try:
            if bundle.get("file") != "native-stats.json":
                raise ValueError("Native stats manifest file must be exactly native-stats.json")
            if bundle["protocolVerified"] is not False:
                raise ValueError("Native stats manifest has an unsupported protocol verification claim")
            if bundle["status"] == "decoded":
                native_stats = package / "native-stats.json"
            elif bundle["status"] in ("absent", "unsupported", "error"):
                coverage.append(f"Native stats bundle status: {bundle['status']}; "
                                "automatic import is incomplete; "
                                + ("developer input remains in use" if observations is not None
                                   else "no manual observations were provided"))
            else:
                raise ValueError("Native stats manifest status is unsupported")
        except (KeyError, TypeError, AttributeError):
            raise ValueError("Native stats manifest has invalid field structure") from None
    if native_stats is not None:
        observed, documents["native_stats"], coverage = automatic(developer, native_stats, hashes["source"][0])
        if bundle is not None and (bundle.get("known") is True or bundle.get("known") is False
                                   or bundle.get("known") != len(documents["native_stats"]["known"])):
            raise ValueError("Native stats manifest known count differs from its input document")
    panel = None
    if panel_log is not None or game_log is not None:
        observed, documents["panel_log"], panel, issues = logged(
            observed, game_log if game_log is not None else panel_log, documents.get("native_stats"),
            raw=game_log is not None)
        documents["panel_log_selection"] = panel
        coverage += issues
    synthetic = any(document.get("synthetic") is True for document in (observed, guide, manifest))
    rows, stats, benchmark, evidence = recorded(observed, partial=observations is None)
    missing = [key for key in REQUIRED_STATS if key not in stats]
    if native_stats is not None:
        for entry in documents["native_stats"]["known"]:
            key = entry["key"] if entry["key"] == "spell_dps" else "benchmark_survival"
            row = next(row for row in rows if row["key"] == key)
            row["precision"] = f"native varint; exact integer; wire {entry['wire']}; corroborated; protocolVerified=false"
    if panel is not None:
        for entry in panel["rows"]:
            row = next(row for row in rows if row["key"] == entry["key"])
            row["precision"] = entry["precision"]
            row["source"] = {key: entry["source"][key] for key in (
                "attr_id", "index", "raw_value", "timestamp", "frame", "line_numbers",
            )}
            if "raw_values" in entry["source"]:
                row["source"]["raw_values"] = list(entry["source"]["raw_values"])
    if native_stats is not None:
        keys = {entry["key"] for entry in documents["native_stats"]["known"]}
        if panel is not None:
            keys.update(entry["key"] for entry in panel["rows"])
        pending = [key for key in REQUIRED_STATS if key not in keys]
        pending += [key for key in stats if key not in keys and key not in pending]
        coverage.append("Native stats missing automatic fields: " + ", ".join(pending))
    loadouts = build["loadouts"]
    if not loadouts["loadouts"]:
        raise ValueError("No loadouts are available in build.json")
    selection = [item for item in loadouts["loadouts"] if item["id"] == loadouts.get("currentLoadoutId")]
    if len(selection) != 1:
        raise ValueError(f"Current loadout {loadouts.get('currentLoadoutId')!r} is not uniquely present in build.json")
    loadout = selection[0]
    character = guide["character"]

    if synthetic:
        coverage.append("Синтетический пример: состав билда, показатели панели и бенчмарк вымышлены; "
                        "они проверяют арифметику, перенос из игры не выполнялся" if observations is not None
                        else "Синтетический пример: состав пакета вымышлен, импорт из живой игры не выполнялся")
    elif not transfer.get("complete") or not transfer.get("canClaimFullTransfer"):
        coverage.append("Перенос неполный (transfer-report complete=false): перенос и расчёт нельзя называть полными.")
    coverage += [f"transfer-report: {issue}" for issue in transfer.get("issues", [])]
    if manifest.get("status") not in (None, "ready"):
        coverage.append(f"manifest status: {manifest['status']}")
    if observations is not None and not synthetic:
        coverage += [
            "Статпанель агрегирована: игра показывает итог без разложения по источникам; "
            "состояние боя (баффы, стаки, заряды, проклятия) в момент скриншотов неизвестно.",
            "Точное время боя и статпанели неизвестно; время файлов скриншотов — момент сохранения, не боя. "
            f"Совпадение состояния со снимком capturedAt {manifest.get('capturedAt')} не доказано.",
            f"Бенчмарк «{observed['benchmark']['label']}»: подпись цели/окна бенчмарка, "
            f"не уровень персонажа ({character.get('level')}).",
        ]
    if observations is None:
        coverage.append("Автоматический импорт неполный; отсутствуют характеристики: " + ", ".join(missing))
        coverage.append("Missing benchmark fields: " + ", ".join(key for key in BENCHMARK if key not in benchmark))
    else:
        coverage += [
            "Ручные наблюдения observations.json — developer input для разработки; "
            "автоматический импорт итоговых характеристик неполный",
            "Округлённые значения панели хранятся с исходной записью и шагом округления; недостающие цифры не выдумывались.",
            "Коэффициенты не подгонялись под бенчмарк: независимое контрольное число не определяет множители модели.",
        ]
    coverage += [
        "Таланты: только узлы с rank>0 и выбранные core; описания взяты из каталога Compendium и могут быть устаревшими.",
        "source.json и sourceSections остаются локальными: в базе и результате только SHA256 source.json.",
    ]
    truncated = [row["label"] for row in rows if row["label"].endswith(("...", "…"))]
    if truncated and observations is not None and not synthetic:
        coverage.append("Подписи обрезаны игрой, полные названия не восстанавливались: " + ", ".join(truncated) + ".")
    for item in guide["gear"]:
        if "crit_chance" in stats and any("Lucky Critical Strike" in affix["text"] for affix in item.get("affixes", [])):
            coverage.append(f"Lucky Critical Strike на {item['name']}: crit_chance — исходный шанс панели, "
                            "а не эффективная вероятность двух бросков.")
    evidence_rows = []
    for key, path in evidence.items():
        shot = Path(path)
        if game_log is not None and key in [f"panel_log:{entry['key']}" for entry in panel["rows"]]:
            source = documents["panel_log"]["source"]
            evidence_rows.append((f"evidence:{key}", path, source["sha256"], source["bytesRead"], None, 0))
        elif synthetic:
            evidence_rows.append((f"evidence:{key}", path, None, None, None, 0))
        elif shot.is_file():
            digest, size = fingerprint(shot)
            modified = datetime.datetime.fromtimestamp(shot.stat().st_mtime).astimezone().isoformat()
            evidence_rows.append((f"evidence:{key}", path, digest, size, modified, 0))
        else:
            evidence_rows.append((f"evidence:{key}", path, None, None, None, 0))
            coverage.append(f"Скриншот «{key}» больше недоступен: {path}. Значения пользователя сохранены.")

    inventory = {"gear": gear(guide), "skills": skills(guide, loadout), "slates": slates(transfer),
                 "talents": talents(guide, loadout, coverage),
                 "memories": [{"name": memory["name"],
                               "details": ([f"item level {memory['itemLevel']}"] if "itemLevel" in memory else [])
                               + [line for affix in memory["affixes"] for line in lines(affix)]}
                              for memory in guide["heroMemories"]],
                 "traits": [{"name": trait["name"], "details": [f"unlock level {trait['unlockLevel']}"]}
                            for trait in sorted(character.get("traits", []), key=lambda trait: trait["unlockLevel"])]}
    system_rows, inventory["systems"] = systems(transfer, loadout)
    if inventory["slates"]:
        coverage.append(f"Divinity: плит {len(inventory['slates'])}; decodedEffects: "
                        f"{transfer['systems']['divinity'].get('decodedEffects', 'unknown')}; "
                        "форма, направление и расположение не проверены, эффекты автоматически не применяются")
    coverage += observed.get("notes", [])

    result = {
        "synthetic": synthetic,
        "import_status": "partial",
        "missing_stats": missing,
        "name": manifest.get("identity", {}).get("title") or guide["name"],
        "capturedAt": manifest["capturedAt"],
        "character": f"{character['englishName']} / {character['class']} / {character['trait']}",
        "stats": stats,
        "observations": [{**{field: row[field] for field in ("key", "label", "value", "unit", "evidence", "precision")},
                          **({"source": row["source"]} if "source" in row else {})}
                         for row in rows],
        "benchmark": benchmark,
        "facts": facts_data,
        "inventory": inventory,
        "skill_values": documents["skill_values"],
        "coverage": coverage,
        "source_sha256": hashes["source"][0],
    }
    if native_stats is not None:
        document = documents["native_stats"]
        keys = {entry["key"] for entry in document["known"]}
        result["native_stats"] = {
            "format": document["format"], "status": document["status"], "known": len(keys),
            "unknown_stat_ids": document["coverage"]["unknownStatIds"], "source_sha256": hashes["source"][0],
            "protocol_verified": False, "missing_trait_levels": document["heroTraits"]["levels"] is None,
            "missing_automatic_stats": pending,
        }
    if panel is not None:
        result["panel_log"] = panel["summary"]

    inputs = [("facts", str(facts), *fingerprint(facts), 1)]
    documents["facts"] = facts_data
    if observations is not None:
        inputs.append(("observations", str(observations), *fingerprint(observations), 1))
        documents["observations"] = developer
    if native_stats is not None:
        inputs.append(("native_stats", str(Path(native_stats).resolve()), *fingerprint(native_stats), 1))
    if panel_log is not None:
        inputs.append(("panel_log", str(Path(panel_log).resolve()), *fingerprint(panel_log), 1))
    if game_log is not None:
        source = documents["panel_log"]["source"]
        inputs.append(("game_log", str(Path(game_log).resolve()), source["sha256"], source["bytesRead"], 0))

    database.parent.mkdir(parents=True, exist_ok=True)
    open(database, "xb").close()
    try:
        with contextlib.closing(sqlite3.connect(database)) as connection:
            connection.executescript(SCHEMA)
            connection.executemany("INSERT INTO meta VALUES (?, ?)", [
                ("schema", "1"), ("archivedAt", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                ("package", str(package)), ("name", result["name"]), ("capturedAt", result["capturedAt"]),
                ("character", result["character"]), ("level", str(character.get("level"))),
                ("synthetic", json.dumps(synthetic))])
            connection.executemany("INSERT INTO sources VALUES (?, ?, ?, ?, NULL, ?)", [
                (role, str(files[role]), *hashes[role], int(role in STORED)) for role in PACKAGE])
            connection.executemany("INSERT INTO sources VALUES (?, ?, ?, ?, NULL, ?)", inputs)
            connection.executemany("INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)", evidence_rows)
            connection.executemany("INSERT INTO documents VALUES (?, ?)", [
                (role, json.dumps(value, ensure_ascii=False))
                for role, value in documents.items()])
            connection.executemany("INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
                (row["key"], row["kind"], row["label"], row["display"], row["value"], row["unit"],
                 row["precision"], row["evidence"]) for row in rows])
            connection.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?)", [
                (section, position, entry["name"], json.dumps(entry["details"], ensure_ascii=False))
                for section, entries in inventory.items() for position, entry in enumerate(entries)])
            connection.executemany("INSERT INTO systems VALUES (?, ?, ?, ?)", system_rows)
            connection.executemany("INSERT INTO coverage VALUES (?, ?)", enumerate(coverage))
            connection.commit()
    except BaseException:
        database.unlink(missing_ok=True)
        raise
    return result
