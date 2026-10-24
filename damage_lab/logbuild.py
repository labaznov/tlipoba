"""Project one saved printed tree into lexical composition evidence without combat effects."""

import re

from .buildlog import LIMITS as READER_LIMITS
from .logtables import LIMITS as TREE_LIMITS, MEANING


FORMAT = "tli-log-build-domains-v1"
AFFIXES = {"base_attr": "BaseAttrAffix", "fixed_base": "FixedBaseAffix", "prefix": "Prefix",
           "suffix": "Suffix", "enchant": "EnchantAffixs", "base": "BaseAffix"}


def _affixes(prefix, memory=False):
    return {name + "_" + field: prefix + "." + native + ".#." + source
            for name, native in AFFIXES.items() if memory or name != "base"
            for field, source in (("id", "Id"), ("version", "Version"), ("source", "source"), ("args", "DynArgs.#"))}


DOMAINS = {
    "equipment": ("bag.wearItems", {"page_id": "PageId", "index": "Index", "base_id": "Item.BaseId",
                   "level": "Item.Level", "rarity": "Item.RareValue", "corroded": "Item.Corrode",
                   "affix_num": "Item.AffixNum", **_affixes("Item")}),
    "memories": ("heroCharacterv3OverView.reminiscenceOverView.reminiscence",
                 {"index": "index", "state": "state", "base_id": "detail.BaseId", "level": "detail.Level",
                  "fixed_level": "detail.ReminiscenceFixedLevel", "enhance_level": "detail.ReminiscenceFixedLevelFromEnhance",
                  "memory_level": "detail.ReminiscenceLevel", **_affixes("detail", True)}),
    "traits": ("heroCharacterv3OverView.pointOverView.activeId", {"trait_id": ""}),
    "slates": ("bag.dressingTalentBlocks", {"page_id": "PageId", "index": "Index", "base_id": "Item.BaseId",
               "level": "Item.Level", "rarity": "Item.RareValue", "shape_id": "Item.ShapeId", "direction": "Item.Direction",
               "enhance_id": "Item.EnhanceId", "enhanced_times": "Item.EnhancedTimes", "influence_id": "Item.InfluenceId",
               "base_talents": "Item.BaseTalentList.#", "enchant_talents": "Item.EnchantTalentList.#",
               "slot_color": "Item.talentSlotList.#.color", "slot_talent": "Item.talentSlotList.#.talentId"}),
    "influence": ("talentBlockInfluence", {"effect_talents": "value.EffectTalentIds.#", "devoured": "value.TalentIdDevour.#",
                  "influenced_talents": "value.TalentIdInfluence.#"}),
    "pacts": ("ContractInfosV2.ContractDatas", {"area_id": "areaId", "servant_id": "servantId"}),
    "skill_layout": ("skillLayout.slots", {"slot_key": "key"}),
    "skill_items": ("skills.skills", {"base_id": "BaseId", "level": "Level",
                    "skill_item_level": "SkillItemLevel", "rarity": "RareValue"}),
    "dressed_skill_items": ("bag.dressSkillItems", {"page_id": "PageId", "index": "Index",
                            "base_id": "Item.BaseId", "level": "Item.Level",
                            "skill_item_level": "Item.SkillItemLevel", "rarity": "Item.RareValue"}),
    "pact_points": ("ContractInfosV2.pointDatas", None),
    "pact_roster": ("ServantInfos.servantData", None), "talents": ("geniusInfos", None), "stats": ("attrInfo", None),
    "season": ("SP3Base.TalentTree", None)}


def _error():
    raise ValueError("Log build projection requires a supported bounded saved-tree contract")


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        _error()


def _integer(value, maximum, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        _error()


def _envelope(snapshot, digest):
    _object(snapshot, ("format", "version", "status", "scope", "import_complete", "identity", "runtime", "freshness",
                       "selected_skill", "build_code", "source", "events", "rejected", "limits"))
    if (snapshot["format"] != "tli-build-log-v1" or snapshot["version"] != "0.1.2" or snapshot["status"] != "diagnostic"
            or snapshot["scope"] != "printed_tree_only" or snapshot["import_complete"] is not False
            or any(snapshot[key] != "unknown" for key in ("identity", "runtime", "freshness", "selected_skill", "build_code"))):
        _error()
    _object(snapshot["limits"], tuple(READER_LIMITS))
    for key, maximum in READER_LIMITS.items():
        _integer(snapshot["limits"][key], maximum, 1)
    source = snapshot["source"]
    _object(source, ("kind", "sha256", "snapshotBytes", "bytesRead", "lines", "ignoredLines", "oversizedLines",
                     "retainedEventBytes", "incompleteFinalLine"))
    if (type(digest) is not str or not re.fullmatch("[0-9a-f]{64}", digest)
            or source["sha256"] != digest or source["kind"] != "ordinary_log"):
        _error()
    for field, limit in (("snapshotBytes", "max_source_bytes"), ("bytesRead", "max_source_bytes"),
                         ("lines", "max_lines"), ("ignoredLines", "max_lines"), ("oversizedLines", "max_lines"),
                         ("retainedEventBytes", "max_retained_bytes")):
        _integer(source[field], snapshot["limits"][limit])
    if (source["bytesRead"] != source["snapshotBytes"] or source["lines"] > source["snapshotBytes"]
            or source["retainedEventBytes"] > source["snapshotBytes"]
            or any(source[key] > source["lines"] for key in ("ignoredLines", "oversizedLines"))):
        _error()
    if type(snapshot["events"]) is not list or type(snapshot["rejected"]) is not list:
        _error()
    _integer(len(snapshot["events"]) + len(snapshot["rejected"]), snapshot["limits"]["max_events"])
    if source["retainedEventBytes"] > len(snapshot["events"]) * snapshot["limits"]["max_event_bytes"]:
        _error()
    return source


def _snapshot(snapshot, index, digest):
    source = _envelope(snapshot, digest)
    _integer(index, len(snapshot["events"]) - 1)
    event = snapshot["events"][index]
    _object(event, ("start_line", "end_line", "boundary", "header_trailing_space", "tree"))
    _integer(event["start_line"], source["lines"], 1)
    _integer(event["end_line"], source["lines"], event["start_line"])
    if (event["boundary"] not in ("next_record", "snapshot_boundary") or type(event["header_trailing_space"]) is not bool
            or event["end_line"] - event["start_line"] + 1 > snapshot["limits"]["max_event_lines"]
            or (event["boundary"] == "next_record" and event["end_line"] == source["lines"])
            or (event["boundary"] == "snapshot_boundary" and event["end_line"] != source["lines"])):
        _error()
    tail = source["incompleteFinalLine"]
    if tail is not None:
        _object(tail, ("line", "bytes"))
        _integer(tail["bytes"], source["snapshotBytes"], 1)
        if tail["line"] != source["lines"] or type(tail["line"]) is not int or event["end_line"] >= tail["line"]:
            _error()
    return event


def _class(text):
    if text in ("true", "false"):
        return "bool"
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", text, re.ASCII):
        return "int"
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", text, re.ASCII):
        return "float"
    return "text"


def _tree(tree, event, limits):
    _object(tree, ("format", "version", "status", "meaning", "root", "header", "counts", "elisions"))
    if tree["format"] != "tli-log-table-v0" or tree["version"] != "0.2.0" or tree["meaning"] != MEANING:
        _error()
    header = tree["header"]
    _object(header, ("logTimeText", "frame", "timezone"))
    if (type(header["logTimeText"]) is not str or not re.fullmatch(
            r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}-[0-9]{2}\.[0-9]{2}\.[0-9]{2}:[0-9]{3}", header["logTimeText"])
            or header["timezone"] != "unknown"):
        _error()
    _integer(header["frame"], 9999999999)
    _object(tree["root"], ("t",))
    if tree["root"]["t"] != "table":
        _error()
    stack, nodes, maximum, leaves, empties, elisions = [(tree["root"], [], 0)], 0, 0, 0, 0, []
    scalars = {key: 0 for key in ("bool", "int", "float", "text")}
    while stack:
        node, path, depth = stack.pop()
        _object(node, ("t",))
        if node["t"] not in ("table", "scalar", "empty", "elided"):
            _error()
        nodes += bool(path)
        maximum = max(maximum, depth)
        if nodes > TREE_LIMITS["max_nodes"] or depth > TREE_LIMITS["max_depth"]:
            _error()
        length = sum(len(key) + 1 for key in path)
        if node["t"] == "table":
            _object(node, ("entries",))
            if type(node["entries"]) is not list or not node["entries"] or len(node["entries"]) > TREE_LIMITS["max_nodes"]:
                _error()
            seen, tables = set(), 0
            children = []
            for index, entry in enumerate(node["entries"]):
                if type(entry) is not list or len(entry) != 2:
                    _error()
                key, child = entry
                if type(key) is not str or len(key) > limits["max_line_bytes"] or not re.fullmatch("[A-Za-z0-9]+", key) or key in seen:
                    _error()
                _object(child, ("t",))
                seen.add(key)
                if child["t"] in ("table", "empty"):
                    tables += 1
                    if tables > 30:
                        _error()
                if child["t"] == "elided":
                    if index != len(node["entries"]) - 1 or tables != 30:
                        _error()
                children.append((child, path + [key], depth + 1))
            stack.extend(reversed(children))
        else:
            leaves += 1
            empties += node["t"] == "empty"
            if node["t"] == "scalar":
                _object(node, ("text", "class"))
                text = node["text"]
                if (type(text) is not str or len(text) > limits["max_line_bytes"] or any(not " " <= char <= "~" or char in "[]" for char in text)
                        or node["class"] != _class(text)):
                    _error()
                scalars[node["class"]] += 1
                length += len(text) + 3
            elif node["t"] == "elided":
                length += 4
                elisions.append({"path": path[:-1], "printedTableEntries": 30})
            if length > limits["max_line_bytes"]:
                _error()
    counts = tree["counts"]
    expected = {"lines": leaves, "leaves": leaves, "emptyTables": empties, "elisions": len(elisions),
                "nodes": nodes, "maxDepth": maximum}
    _object(counts, (*expected, "scalars"))
    for key, value in expected.items():
        _integer(counts[key], TREE_LIMITS["max_nodes"])
        if counts[key] != value:
            _error()
    _object(counts["scalars"], tuple(scalars))
    if any(type(counts["scalars"][key]) is not int or counts["scalars"][key] != value for key, value in scalars.items()):
        _error()
    if (not leaves or leaves != event["end_line"] - event["start_line"]
            or tree["status"] != ("elided" if elisions else "complete") or type(tree["elisions"]) is not list
            or len(tree["elisions"]) > TREE_LIMITS["max_nodes"]):
        _error()
    projected = []
    for row in tree["elisions"]:
        _object(row, ("path", "printedTableEntries"))
        if type(row["path"]) is not list or type(row["printedTableEntries"]) is not int:
            _error()
        projected.append({"path": row["path"], "printedTableEntries": row["printedTableEntries"]})
    if projected != elisions:
        _error()
    return {key: header[key] for key in ("logTimeText", "frame", "timezone")}


def _array(node):
    if node["t"] == "empty":
        return []
    if node["t"] != "table":
        _error()
    for index, (key, child) in enumerate(node["entries"]):
        if key != str(index + 1):
            _error()
    return [(key, child) for key, child in node["entries"] if child["t"] != "elided"]


def _gather(root, path, pattern):
    states, missing, elided, empty = [(path, root)], [], [], []
    for index, key in enumerate(pattern):
        following = []
        for location, node in states:
            if node["t"] == "elided":
                elided.append(location)
            elif node["t"] == "empty" and key == "#":
                empty.append(location)
            elif node["t"] == "empty":
                missing.append(location + pattern[index:])
            elif node["t"] != "table":
                _error()
            elif key == "#":
                for name, child in _array(node):
                    following.append((location + [name], child))
                if any(child["t"] == "elided" for name, child in node["entries"]):
                    elided.append(location)
                if not node["entries"]:
                    empty.append(location)
            else:
                child = dict(node["entries"]).get(key)
                if child is None:
                    missing.append(location + pattern[index:])
                else:
                    following.append((location + [key], child))
        states = following
    return states, missing, elided, empty


def _field(node, path, pattern):
    states, missing, elided, empty = _gather(node, path, pattern.split(".") if pattern else [])
    values = []
    for location, child in states:
        if child["t"] == "scalar":
            values.append({"path": location, "text": child["text"], "class": child["class"]})
        elif child["t"] == "empty":
            empty.append(location)
        elif child["t"] == "elided":
            elided.append(location)
        else:
            _error()
    return {"status": "elided" if elided else "complete" if values or empty else "not_printed",
            "values": values, "missing_paths": missing, "elided_paths": elided, "empty_paths": empty}


def _at(root, path):
    for key in path:
        if root["t"] != "table":
            return None
        root = dict(root["entries"]).get(key)
        if root is None:
            return None
    return root


def _elided(root):
    stack = [root]
    while stack:
        node = stack.pop()
        if node["t"] == "elided":
            return True
        if node["t"] == "table":
            stack.extend(child for key, child in node["entries"])
    return False


def _domain(root, name, path, fields):
    node = _at(root, path)
    result = {"path": path, "status": "not_printed", "node_kind": None, "visible_entries": None,
              "total_entries": None, "rows": [], "gaps": []}
    if node is None:
        result["gaps"].append({"path": list(path), "reason": "not_printed"})
        return result
    if node["t"] not in ("table", "empty", "elided"):
        _error()
    result.update(status="elided" if _elided(node) else "complete", node_kind=node["t"],
                  visible_entries=sum(child["t"] != "elided" for key, child in node.get("entries", [])))
    if result["status"] == "elided":
        result["gaps"].append({"path": list(path), "reason": "subtree_elided"})
    if node["t"] == "empty":
        result["gaps"].append({"path": list(path), "reason": "empty_container_type_unknown"})
    if fields is None or node["t"] == "elided":
        return result
    for index, (key, child) in enumerate(_array(node)):
        location = path + [key]
        row = {"alias": f"{name}[{index}]", "path": location,
               "fields": {field: _field(child, location, pattern) for field, pattern in fields.items()}}
        if name in ("equipment", "memories"):
            prefix = "Item" if name == "equipment" else "detail"
            row["conditions"] = {
                field.lower(): "printed_unmapped" if any(_gather(child, location, [prefix, native, "#", field])[0]
                    for affix, native in AFFIXES.items() if name == "memories" or affix != "base") else "not_printed"
                for field in ("Condition", "Filter", "Behavior")}
        result["rows"].append(row)
    return result


def project(snapshot, event_index, source_sha256):
    """Return only allowlisted lexical facts from one explicitly selected saved event."""
    event = _snapshot(snapshot, event_index, source_sha256)
    tree = event["tree"]
    header = _tree(tree, event, snapshot["limits"])
    if not _candidate(tree["root"]):
        _error()
    domains = {name: _domain(tree["root"], name, path.split("."), fields) for name, (path, fields) in DOMAINS.items()}
    return {"format": FORMAT, "scope": "printed_subtree_only", "import_complete": False,
            **{key: "unknown" for key in ("identity", "runtime", "freshness", "selected_skill", "build_code")},
            "source": {"sha256": snapshot["source"]["sha256"], "snapshot_bytes": snapshot["source"]["snapshotBytes"]},
            "event": {"index": event_index, "start_line": event["start_line"], "end_line": event["end_line"],
                      "boundary": event["boundary"], "header": header},
            "domains": domains,
            "counts": {"domains": len(domains), "rows": sum(len(row["rows"]) for row in domains.values()),
                       "lexical_values": sum(len(field["values"]) for domain in domains.values()
                                             for row in domain["rows"] for field in row["fields"].values())}}


def _candidate(root):
    for path in ("bag.wearItems", "heroCharacterv3OverView", "skillLayout"):
        node = _at(root, path.split("."))
        if node is None or node["t"] not in ("table", "empty"):
            return False
    return True


def candidates(snapshot, source_sha256):
    """Enumerate structural candidate indexes without selecting or joining any event."""
    _envelope(snapshot, source_sha256)
    result = []
    for index in range(len(snapshot["events"])):
        event = _snapshot(snapshot, index, source_sha256)
        _tree(event["tree"], event, snapshot["limits"])
        if _candidate(event["tree"]["root"]):
            result.append(index)
    return result
