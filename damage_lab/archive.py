"""Local SQLite archive of one build with explicit observed or synthetic origins."""

import contextlib
import datetime
import hashlib
import json
import math
import sqlite3
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .skillvalues import extract

PACKAGE = {"build": "build.json", "guide": "guide-data.json", "manifest": "manifest.json",
           "transfer": "transfer-report.json", "source": "source.json"}
STORED = ("build", "manifest", "transfer")
REQUIRED_STATS = ("spell_dps", "hit_min", "hit_max", "cast_rate", "crit_chance", "crit_multiplier",
                  "max_tangles", "extra_attachments", "cold_penetration")
OPTIONAL_STATS = ("armor_penetration", "max_spell_burst", "double_damage_chance")
BENCHMARK = ("average_dps", "duration", "highest_5s", "average_5s", "survival")
EXPECTED_UNITS = {
    "spell_dps": "damage/s", "hit_min": "damage", "hit_max": "damage", "cast_rate": "casts/s",
    "crit_chance": "fraction", "crit_multiplier": "multiplier", "max_tangles": "count",
    "extra_attachments": "count", "cold_penetration": "fraction",
    "armor_penetration": "fraction", "max_spell_burst": "count", "double_damage_chance": "fraction",
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


def ranked(package, bundle, source):
    """Read one source-bound diagnostic artifact without selecting a rank rule."""
    from .traitranks import project

    if (type(bundle) is not dict or bundle.get("file") != "trait-ranks.json"
            or bundle.get("rankRuleVerified") is not False
            or bundle.get("status") not in ("diagnostic", "error")
            or bundle.get("sourceSha256") != source
            or type(bundle.get("traits")) is not int or bundle["traits"] < 0):
        raise ValueError("Trait ranks manifest has an invalid diagnostic contract")
    path = package / "trait-ranks.json"
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("Trait ranks artifact exceeds the supported size")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != bundle.get("sha256"):
        raise ValueError("Trait ranks artifact hash differs from its manifest")
    document = json.loads(raw.decode("utf-8"))
    if (type(document) is not dict or document.get("format") != "tli-trait-rank-candidates-v1"
            or type(document.get("source")) is not dict or document["source"].get("sha256") != source
            or type(document.get("traits")) is not list or len(document["traits"]) != bundle["traits"]):
        raise ValueError("Trait ranks artifact differs from its source or manifest count")
    if bundle["status"] == "error":
        if document.get("status") != "error" or document["traits"]:
            raise ValueError("Trait ranks error artifact cannot contain candidate claims")
        return None, (str(path.resolve()), digest, len(raw), 0)
    return project(document, source), (str(path.resolve()), digest, len(raw), 1)


def audited(package, bundle, source, guide):
    """Bind an acquisition audit to its persisted inputs without verifying effects."""
    from .importcoverage import project

    fields = {"file", "status", "importComplete", "sha256", "sourceSha256", "guideSha256", "domains"}
    if (type(bundle) is not dict or not fields.issubset(bundle)
            or bundle["file"] != "import-coverage.json" or bundle["importComplete"] is not False
            or bundle["status"] not in ("diagnostic", "error") or bundle["sourceSha256"] != source
            or bundle["guideSha256"] not in (None, guide)
            or type(bundle["domains"]) is not int
            or bundle["domains"] != (9 if bundle["status"] == "diagnostic" else 0)):
        raise ValueError("Import coverage manifest has an invalid diagnostic contract")
    path = package / "import-coverage.json"
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("Import coverage artifact exceeds the supported size")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != bundle["sha256"]:
        raise ValueError("Import coverage artifact hash differs from its manifest")
    document = json.loads(raw.decode("utf-8"))
    if (type(document) is not dict or document.get("format") != "tli-import-coverage-v1"
            or document.get("importComplete") is not False or type(document.get("source")) is not dict
            or document["source"].get("sha256") != source or type(document.get("guide")) is not dict
            or document["guide"].get("sha256") != bundle["guideSha256"]
            or type(document.get("domains")) is not dict or len(document["domains"]) != bundle["domains"]):
        raise ValueError("Import coverage artifact differs from its source, guide or manifest count")
    if bundle["status"] == "error":
        if document.get("status") != "error" or document["domains"]:
            raise ValueError("Import coverage error artifact cannot contain domain claims")
        return None, (str(path.resolve()), digest, len(raw), 0)
    return project(document, source, bundle["guideSha256"]), (str(path.resolve()), digest, len(raw), 1)


def resolved(package, bundle, source):
    """Read a saved-code assessment without establishing transport or identity."""
    from .buildresolution import project

    fields = {"file", "status", "sha256", "sourceSha256", "resolutionStatus",
              "expectedCodeSupplied", "identityVerified", "transportVerified"}
    if (type(bundle) is not dict or not fields.issubset(bundle)
            or bundle["file"] != "build-resolution.json" or bundle["status"] not in ("diagnostic", "error")
            or bundle["sourceSha256"] != source or type(bundle["expectedCodeSupplied"]) is not bool
            or bundle["identityVerified"] is not False or bundle["transportVerified"] is not False):
        raise ValueError("Build resolution manifest has an invalid unverified contract")
    path = package / "build-resolution.json"
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("Build resolution artifact exceeds the supported size")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != bundle["sha256"]:
        raise ValueError("Build resolution artifact hash differs from its manifest")
    document = json.loads(raw.decode("utf-8"))
    if (type(document) is not dict or document.get("format") != "tli-build-resolution-v0"
            or type(document.get("source")) is not dict or document["source"].get("sha256") != source
            or document.get("status") != bundle["resolutionStatus"]):
        raise ValueError("Build resolution artifact differs from its source or manifest status")
    if bundle["status"] == "error":
        if document["status"] != "error":
            raise ValueError("Build resolution error artifact cannot contain assessment claims")
        return None, (str(path.resolve()), digest, len(raw), 0)
    result = project(document, source)
    if not bundle["expectedCodeSupplied"] and result["identity"]["expected_code_matched"] is not None:
        raise ValueError("Build resolution cannot match an expected code that was not supplied")
    return result, (str(path.resolve()), digest, len(raw), 1)


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
    if key == "max_spell_burst" and (numeric < 0 or numeric != numeric.to_integral_value()):
        raise ValueError("max_spell_burst: value must be a nonnegative integer")
    if key == "double_damage_chance" and not 0 <= numeric <= 1:
        raise ValueError("double_damage_chance: displayed chance must be between zero and one")
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
    """Label guide skills and keep each support roll on the producer slot that owns it."""

    def text(skill, rolls):
        parts = [f"level {skill['level']}" if "level" in skill else None,
                 f"rank {skill['rank']}" if "rank" in skill else None]
        label = f"{skill['name']} ({', '.join(part for part in parts if part)})" if any(parts) else skill["name"]
        if rolls:
            label += "; rolls " + "; ".join(", ".join(format(value, "g") for value in values)
                                             for values in rolls.values())
        return label

    def entry(group, annotations):
        supports = group.get("supports") or []
        return {"name": text(group["main"], None),
                "details": [group["kind"]] + [text(support, rolls)
                                               for support, rolls in zip(supports, annotations)]}

    arrays = loadout["skills"]
    if arrays["activeSkills"] == [] and arrays["passiveSkills"] == []:
        return [entry(group, [None] * len(group.get("supports") or [])) for group in guide["skillGroups"]]
    message = "Support rolls cannot be traced to one producer slot"
    placed = {"active": arrays["activeSkills"], "aura": arrays["passiveSkills"]}
    consumed, seen, annotated = set(), set(), []
    for group in guide["skillGroups"]:
        supports = group.get("supports") or []
        if type(supports) is not list:
            raise ValueError(message)
        if not supports:
            kind, tab = group.get("kind"), group.get("sourceTab")
            if type(tab) is int and kind in placed:
                if (kind, tab) in seen:
                    raise ValueError(message)
                seen.add((kind, tab))
            annotated.append([])
            continue
        kind, tab = group.get("kind"), group.get("sourceTab")
        if kind not in placed or type(tab) is not int or (kind, tab) in seen:
            raise ValueError(message)
        seen.add((kind, tab))
        slots = placed[kind]
        index = tab - 1 if kind == "active" else tab - 6
        if not 0 <= index < len(slots):
            raise ValueError(message)
        target, main = slots[index], group.get("main")
        if (type(target) is not dict or target.get("enabled") is not True or type(main) is not dict
                or target.get("skillGuid") != main.get("guid") or target.get("level") != main.get("level")):
            raise ValueError(message)
        gems = target.get("supports")
        if type(gems) is not list:
            raise ValueError(message)
        used, notes = set(), []
        for support in supports:
            slot = support.get("slot") if type(support) is dict else None
            guid = support.get("guid") if type(support) is dict else None
            if type(slot) is not int or not 2 <= slot <= 6 or slot in used or type(guid) is not str or not guid:
                raise ValueError(message)
            used.add(slot)
            offset = slot - 2
            if offset >= len(gems):
                raise ValueError(message)
            gem = gems[offset]
            rolls = gem.get("lineRolls") if type(gem) is dict else None
            if type(gem) is not dict or gem.get("supportGuid") != guid or (rolls is not None and type(rolls) is not dict):
                raise ValueError(message)
            notes.append(rolls or None)
            if rolls:
                consumed.add((kind, index, offset))
        annotated.append(notes)
    for kind, slots in placed.items():
        if type(slots) is not list:
            raise ValueError(message)
        for index, target in enumerate(slots):
            gems = target.get("supports") if type(target) is dict else None
            if gems is None:
                continue
            if type(gems) is not list:
                raise ValueError(message)
            for offset, gem in enumerate(gems):
                if type(gem) is dict and gem.get("lineRolls") and (kind, index, offset) not in consumed:
                    raise ValueError(message)
    return [entry(group, notes) for group, notes in zip(guide["skillGroups"], annotated)]


def consistent(guide, loadout):
    """Refuse a loadout whose enabled main skills are not the guide groups of the same package.

    Both empty arrays are the legacy synthetic shape and prove no current composition.
    """
    message = "Current loadout skills differ between build.json and guide-data.json"
    arrays = loadout["skills"]
    if arrays["activeSkills"] == [] and arrays["passiveSkills"] == []:
        return
    observed, expected = Counter(), Counter()
    for name in ("activeSkills", "passiveSkills"):
        if type(arrays[name]) is not list:
            raise ValueError(message)
        for slot in arrays[name]:
            if type(slot) is not dict or type(slot.get("enabled")) is not bool:
                raise ValueError(message)
            if not slot["enabled"]:
                continue
            if type(slot.get("skillGuid")) is not str or not slot["skillGuid"] or type(slot.get("level")) is not int:
                raise ValueError(message)
            observed[name, slot["skillGuid"], slot["level"]] += 1
    if type(guide.get("skillGroups")) is not list:
        raise ValueError(message)
    for group in guide["skillGroups"]:
        main = group.get("main") if type(group) is dict else None
        if (type(main) is not dict or group.get("kind") not in ("active", "aura") or type(main.get("guid")) is not str
                or not main["guid"] or type(main.get("level")) is not int):
            raise ValueError(message)
        expected["activeSkills" if group["kind"] == "active" else "passiveSkills", main["guid"], main["level"]] += 1
    if observed != expected:
        raise ValueError(message)


def talents(guide, loadout, coverage):
    trees = {tree["id"]: tree for tree in guide["talentTrees"]}
    entries = []
    for slot in loadout["skillTree"]["slots"]:
        if slot["treeId"] is None:
            if (type(slot.get("nodePoints")) is not dict or slot["nodePoints"]
                    or any(value is not None for key, value in slot.items() if key not in ("treeId", "nodePoints"))):
                raise ValueError("Unselected talent slot cannot contain allocations or other state")
            continue
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
        "format", "status", "known", "unknown_attributes", "cohort", "identity_verified", "source_sha256", "numeric_policy",
        "newer_state_conflict", "stale_selection_warning",
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
    coverage.append(f"Panel log selects printed values within 0.5 of native Spell DPS anchor {anchors[0]}; "
                    "this is a selection heuristic, printer rounding is unknown and normalized numbers use binary64")
    return observed, document, selection, coverage


def discovery(source):
    """Describe recorded scan coverage without retaining raw process data."""
    if type(source) is not dict:
        raise ValueError("Memory discovery source must be an object")
    unknown = "Memory discovery completeness is unknown: scan pass evidence is unavailable"
    if "discovery" not in source:
        return [unknown]
    evidence = source["discovery"]
    if type(evidence) is not dict:
        raise ValueError("Memory discovery must be an object")
    if "scanPasses" not in evidence:
        return [unknown]
    passes = evidence["scanPasses"]
    if type(passes) is not list or not passes:
        raise ValueError("Memory discovery scanPasses must be a nonempty array")
    issues = []
    for index, stage in enumerate(passes, 1):
        if (type(stage) is not dict or type(stage.get("complete")) is not bool
                or type(stage.get("readFailures")) is not int or stage["readFailures"] < 0):
            raise ValueError(f"Memory discovery pass {index} has invalid completion evidence")
        if stage["readFailures"]:
            issues.append(f"Memory discovery has read gaps: pass {index} reports {stage['readFailures']} "
                          "read failures; candidate uniqueness is not proven")
        elif not stage["complete"]:
            issues.append(f"Memory discovery is incomplete: pass {index} did not finish; "
                          "candidate uniqueness is not proven")
    if len(passes) != 3:
        issues.append("Memory discovery completeness is unknown: expected three recorded passes; "
                      "candidate uniqueness is not proven")
    return issues or ["Memory discovery completed three recorded chunk passes with zero reported chunk read failures; "
                      "candidate validation coverage, cross-pass atomicity and selected build identity remain unverified"]


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
    # The guide groups must describe the current loadout before any guide-derived extraction
    loadouts = build["loadouts"]
    if not loadouts["loadouts"]:
        raise ValueError("No loadouts are available in build.json")
    selection = [item for item in loadouts["loadouts"] if item["id"] == loadouts.get("currentLoadoutId")]
    if len(selection) != 1:
        raise ValueError(f"Current loadout {loadouts.get('currentLoadoutId')!r} is not uniquely present in build.json")
    loadout = selection[0]
    consistent(guide, loadout)
    documents["skill_values"] = extract(guide)
    developer = load(observations) if observations is not None else {"evidence": {}, "panel": [], "benchmark": {"values": []}}
    facts_data = load(facts)
    observed = developer
    coverage = discovery(load(files["source"]))
    from .rawattrbundle import read as rawattributes
    documents["raw_attribute_evidence"] = rawattributes(files["source"], hashes["source"][0])
    coverage.append("Raw attribute evidence is imported separately without named combat parameters or verified protocol semantics")
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
        observed, documents["native_stats"], issues = automatic(developer, native_stats, hashes["source"][0])
        coverage += issues
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
    ranks = None
    origin = None
    if "traitRanks" in manifest:
        ranks, origin = ranked(package, manifest["traitRanks"], hashes["source"][0])
        if ranks is not None:
            documents["trait_ranks"] = ranks
            coverage.append("Hero trait rank candidates were imported automatically; no rank rule is verified or selected")
        else:
            coverage.append("Hero trait rank bundle failed; automatic rank acquisition remains incomplete")
    else:
        coverage.append("Hero trait rank candidates are unavailable in this legacy package")
    audit = None
    audit_origin = None
    if "importCoverage" in manifest:
        audit, audit_origin = audited(package, manifest["importCoverage"], hashes["source"][0], hashes["guide"][0])
        if audit is not None:
            documents["import_coverage"] = audit
            coverage.append("Automatic import audit separates observed composition from unverified combat effects")
        else:
            coverage.append("Automatic import coverage audit failed; domain acquisition remains unassessed")
    else:
        coverage.append("Automatic import coverage audit is unavailable in this legacy package")
    resolution = None
    resolution_origin = None
    if "buildResolution" in manifest:
        resolution, resolution_origin = resolved(package, manifest["buildResolution"], hashes["source"][0])
        if resolution is not None:
            documents["build_resolution"] = resolution
            coverage.append("Build resolution describes a saved controller claim; payload identity and freshness remain unverified")
        else:
            coverage.append("Saved build resolution assessment failed; code binding remains unassessed")
    else:
        coverage.append("Saved build resolution assessment is unavailable in this legacy package")
    installation = None
    attachment = None
    if "installedSkills" in manifest:
        from .skillbundle import read
        installation, attachment = read(package, manifest["installedSkills"], hashes["source"][0])
        if installation is not None:
            documents["installed_skills"] = installation
            coverage.append("Installed skill membership was imported automatically; activation and effective levels remain unknown")
        else:
            coverage.append("Installed skill inventory failed; support acquisition remains incomplete")
    else:
        coverage.append("Installed skill inventory is unavailable in this legacy package")
    profile = None
    profile_origin = None
    if "installedSkillCatalog" in manifest:
        from .skillcatalogbundle import read
        profile, profile_origin = read(package, manifest["installedSkillCatalog"], hashes["source"][0], installation)
        if profile is not None:
            documents["installed_skill_profiles"] = profile
            coverage.append("Installed skill catalog profiles were looked up at observed gem levels; effective levels and damage applicability remain unknown")
        else:
            coverage.append("Installed skill catalog acquisition failed; missing profiles are not empty or zero damage")
    else:
        coverage.append("Installed skill catalog profiles are unavailable in this legacy package")
    levels = None
    level_origin = None
    if "installedLevelCandidates" in manifest:
        from .levelbundle import read
        levels, level_origin = read(package, manifest["installedLevelCandidates"], hashes["source"][0], installation)
        if levels is not None:
            documents["installed_level_candidates"] = levels
            coverage.append("Installed level candidates were imported automatically; effective levels and eligibility remain unknown; candidates are not added or applied to DPS")
        else:
            coverage.append("Installed level candidate acquisition failed; missing candidates are not empty or zero level grants")
    else:
        coverage.append("Installed level candidates are unavailable in this legacy package")
    witness = None
    witness_origin = None
    if "selectedBuildWitness" in manifest:
        from .witnessbundle import BundleError, read, rejected
        try:
            witness, witness_origin = read(package, manifest["selectedBuildWitness"], hashes["source"][0])
        except BundleError as error:
            witness = rejected(error.code, hashes["source"][0])
        documents["selected_build_witness"] = witness
        coverage.append("Selected build witness: " + witness["status"]
                        + "; byte references do not verify producer joins, selected build identity or effective levels")
    else:
        coverage.append("Selected build witness is unavailable in this legacy package")
    support = None
    catalog = None
    support_origin = None
    if "installedSupportEffects" in manifest:
        from .supportbundle import read
        support, catalog, support_origin = read(package, manifest["installedSupportEffects"], hashes["source"][0])
        if support is not None:
            documents["installed_support_effects"] = support
            documents["installed_support_catalog"] = catalog
            coverage.append("Installed support effect candidates were imported automatically; activation effective levels and arithmetic remain unverified")
        else:
            coverage.append("Installed support effect acquisition failed; missing effects are not empty or zero effects")
    else:
        coverage.append("Installed support effect candidates are unavailable in this legacy package")
    memory = None
    memory_origin = None
    if "memoryDefinitionLedger" in manifest:
        from .memorybundle import read
        memory, memory_origin = read(package, manifest["memoryDefinitionLedger"], hashes["source"][0])
        if memory is not None:
            documents["memory_definitions"] = memory
            coverage.append("Memory definitions were imported automatically; line roles rank scaling activation and arithmetic remain unknown")
        else:
            coverage.append("Memory definition acquisition failed; missing definitions are not empty or zero effects")
    else:
        coverage.append("Memory definitions are unavailable in this legacy package")
    modifiers = None
    modifier_origin = None
    if "staticCombat" in manifest:
        from .staticbundle import read
        modifiers, provenance, modifier_origin = read(package, manifest["staticCombat"], hashes["source"][0])
        if modifiers is not None:
            documents["static_combat"] = modifiers
            documents["static_combat_provenance"] = provenance
            coverage.append("Static gear modifiers were imported as partial source-bound evidence; runtime is unverified and effects are not applied to DPS")
        else:
            coverage.append("Static gear modifier bundle failed; effect acquisition remains incomplete")
    else:
        coverage.append("Static gear modifiers are unavailable in this legacy package")
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
        "source.json и sourceSections остаются локальными: в базе и результате SHA256 и производные данные, без исходного содержимого.",
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
        "raw_attribute_evidence": documents["raw_attribute_evidence"],
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
    if ranks is not None:
        result["trait_ranks"] = ranks
    if audit is not None:
        result["import_coverage"] = audit
    if resolution is not None:
        result["build_resolution"] = resolution
    if modifiers is not None:
        result["static_combat"] = modifiers
        result["static_combat_provenance"] = provenance
    if installation is not None:
        result["installed_skills"] = installation
    if profile is not None:
        result["installed_skill_profiles"] = profile
    if levels is not None:
        result["installed_level_candidates"] = levels
    if witness is not None:
        result["selected_build_witness"] = witness
    if support is not None:
        result["installed_support_effects"] = support
        result["installed_support_catalog"] = catalog
    if memory is not None:
        result["memory_definitions"] = memory

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
    if origin is not None:
        inputs.append(("trait_ranks", *origin))
    if audit_origin is not None:
        inputs.append(("import_coverage", *audit_origin))
    if resolution_origin is not None:
        inputs.append(("build_resolution", *resolution_origin))
    if modifier_origin is not None:
        inputs.append(("static_combat", *modifier_origin))
    if attachment is not None:
        inputs.append(("installed_skills", *attachment))
    if profile_origin is not None:
        inputs.append(("installed_skill_profiles", *profile_origin))
    if level_origin is not None:
        inputs.append(("installed_level_candidates", *level_origin))
    if witness_origin is not None:
        inputs.append(("selected_build_witness", *witness_origin))
    if support_origin is not None:
        inputs.append(("installed_support_effects", *support_origin))
    if memory_origin is not None:
        inputs.append(("memory_definitions", *memory_origin))

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
