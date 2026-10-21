"""Local SQLite archive of one build with explicit observed or synthetic origins."""

import contextlib
import datetime
import hashlib
import json
import math
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

PACKAGE = {"build": "build.json", "guide": "guide-data.json", "manifest": "manifest.json",
           "transfer": "transfer-report.json", "source": "source.json"}
STORED = ("build", "manifest", "transfer")
REQUIRED_STATS = ("spell_dps", "hit_min", "hit_max", "cast_rate", "crit_chance", "crit_multiplier",
                  "max_tangles", "extra_attachments", "cold_penetration")
BENCHMARK = ("average_dps", "duration", "highest_5s", "average_5s", "survival")
EXPECTED_UNITS = {
    "spell_dps": "damage/s", "hit_min": "damage", "hit_max": "damage", "cast_rate": "casts/s",
    "crit_chance": "fraction", "crit_multiplier": "multiplier", "max_tangles": "count",
    "extra_attachments": "count", "cold_penetration": "fraction",
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


def recorded(data):
    evidence = {key: item["path"] for key, item in data["evidence"].items()}
    rows = [observation(row, "panel", evidence) for row in data["panel"]]
    bench = data["benchmark"]
    rows += [observation({**row, "evidence": bench["evidence"]}, "benchmark", evidence, "benchmark_")
             for row in bench["values"]]
    keys = [row["key"] for row in rows]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Duplicate observations: {', '.join(duplicates)}")
    stats = {row["key"]: row["value"] for row in rows if row["kind"] == "panel"}
    benchmark = {row["key"][len("benchmark_"):]: row["value"] for row in rows if row["kind"] == "benchmark"}
    for name, required, present in (("stats", REQUIRED_STATS, stats), ("benchmark", BENCHMARK, benchmark)):
        missing = [key for key in required if key not in present]
        if missing:
            raise ValueError(f"Missing {name}: {', '.join(missing)}")
    return rows, stats, {key: benchmark[key] for key in BENCHMARK}, evidence


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
                        ("observed", "mapped", "affixesObserved", "affixesMapped") if field in report]
            details += [f"utility: {spirit['name']} rank {spirit['rank']}" for spirit in report.get("utilityPactspirits", [])]
            details += report.get("issues", [])
            if report.get("effectMappingComplete") is False:
                details.append("effect mapping incomplete")
            entries.append({"name": name, "details": details})
    return rows, entries


def archive(package: Path, observations: Path, facts: Path, database: Path) -> dict:
    package, observations, facts, database = (Path(package), Path(observations), Path(facts), Path(database))
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
    observed, facts_data = load(observations), load(facts)
    synthetic = any(document.get("synthetic") is True for document in (observed, guide, manifest))
    rows, stats, benchmark, evidence = recorded(observed)
    loadouts = build["loadouts"]
    if not loadouts["loadouts"]:
        raise ValueError("No loadouts are available in build.json")
    selection = [item for item in loadouts["loadouts"] if item["id"] == loadouts.get("currentLoadoutId")]
    if len(selection) != 1:
        raise ValueError(f"Current loadout {loadouts.get('currentLoadoutId')!r} is not uniquely present in build.json")
    loadout = selection[0]
    character = guide["character"]

    coverage = []
    if synthetic:
        coverage.append("Синтетический пример: состав билда, показатели панели и бенчмарк вымышлены; "
                        "они проверяют арифметику, перенос из игры не выполнялся")
    elif not transfer.get("complete") or not transfer.get("canClaimFullTransfer"):
        coverage.append("Перенос неполный (transfer-report complete=false): перенос и расчёт нельзя называть полными.")
    coverage += [f"transfer-report: {issue}" for issue in transfer.get("issues", [])]
    if manifest.get("status") not in (None, "ready"):
        coverage.append(f"manifest status: {manifest['status']}")
    if not synthetic:
        coverage += [
            "Статпанель агрегирована: игра показывает итог без разложения по источникам; "
            "состояние боя (баффы, стаки, заряды, проклятия) в момент скриншотов неизвестно.",
            "Точное время боя и статпанели неизвестно; время файлов скриншотов — момент сохранения, не боя. "
            f"Совпадение состояния со снимком capturedAt {manifest.get('capturedAt')} не доказано.",
            f"Бенчмарк «{observed['benchmark']['label']}»: подпись цели/окна бенчмарка, "
            f"не уровень персонажа ({character.get('level')}).",
        ]
    coverage += [
        "Округлённые значения панели хранятся с исходной записью и шагом округления; недостающие цифры не выдумывались.",
        "Коэффициенты не подгонялись под бенчмарк: независимое контрольное число не определяет множители модели.",
        "Таланты: только узлы с rank>0 и выбранные core; описания взяты из каталога Compendium и могут быть устаревшими.",
        "source.json и sourceSections остаются локальными: в базе и результате только SHA256 source.json.",
    ]
    truncated = [row["label"] for row in rows if row["label"].endswith(("...", "…"))]
    if truncated and not synthetic:
        coverage.append("Подписи обрезаны игрой, полные названия не восстанавливались: " + ", ".join(truncated) + ".")
    for item in guide["gear"]:
        if any("Lucky Critical Strike" in affix["text"] for affix in item.get("affixes", [])):
            coverage.append(f"Lucky Critical Strike на {item['name']}: crit_chance — исходный шанс панели, "
                            "а не эффективная вероятность двух бросков.")
    evidence_rows = []
    for key, path in evidence.items():
        shot = Path(path)
        if synthetic:
            evidence_rows.append((f"evidence:{key}", path, None, None, None, 0))
        elif shot.is_file():
            digest, size = fingerprint(shot)
            modified = datetime.datetime.fromtimestamp(shot.stat().st_mtime).astimezone().isoformat()
            evidence_rows.append((f"evidence:{key}", path, digest, size, modified, 0))
        else:
            evidence_rows.append((f"evidence:{key}", path, None, None, None, 0))
            coverage.append(f"Скриншот «{key}» больше недоступен: {path}. Значения пользователя сохранены.")

    inventory = {"gear": gear(guide), "skills": skills(guide, loadout),
                 "talents": talents(guide, loadout, coverage),
                 "memories": [{"name": memory["name"],
                               "details": ([f"item level {memory['itemLevel']}"] if "itemLevel" in memory else [])
                               + [line for affix in memory["affixes"] for line in lines(affix)]}
                              for memory in guide["heroMemories"]],
                 "traits": [{"name": trait["name"], "details": [f"unlock level {trait['unlockLevel']}"]}
                            for trait in sorted(character.get("traits", []), key=lambda trait: trait["unlockLevel"])]}
    system_rows, inventory["systems"] = systems(transfer, loadout)
    coverage += observed.get("notes", [])

    result = {
        "synthetic": synthetic,
        "name": manifest.get("identity", {}).get("title") or guide["name"],
        "capturedAt": manifest["capturedAt"],
        "character": f"{character['englishName']} / {character['class']} / {character['trait']}",
        "stats": stats,
        "observations": [{field: row[field] for field in ("key", "label", "value", "unit", "evidence", "precision")}
                         for row in rows],
        "benchmark": benchmark,
        "facts": facts_data,
        "inventory": inventory,
        "coverage": coverage,
        "source_sha256": hashes["source"][0],
    }

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
            connection.executemany("INSERT INTO sources VALUES (?, ?, ?, ?, NULL, 1)", [
                ("observations", str(observations), *fingerprint(observations)),
                ("facts", str(facts), *fingerprint(facts))])
            connection.executemany("INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)", evidence_rows)
            connection.executemany("INSERT INTO documents VALUES (?, ?)", [
                (role, json.dumps(value, ensure_ascii=False))
                for role, value in (*documents.items(), ("observations", observed), ("facts", facts_data))])
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
