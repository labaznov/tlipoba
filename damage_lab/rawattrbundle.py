"""Import typed protocol numbers while omitting opaque character and account payloads."""

import hashlib
import json
import math
from pathlib import Path
import re
import struct

from .supportbundle import _pairs, _float, _constant


FORMAT = "tli-raw-attribute-evidence-v1"
SECTION = "sections.ServerSource.data.attrInfo"
MAX_BYTES = 64 * 1024 * 1024
UNKNOWN = ("runtime", "identity", "freshness", "attribute_ids", "units", "native_mapping", "getters", "effective_level", "dps")


def _error():
    raise ValueError("Raw attribute evidence requires a bounded source contract") from None


def _pick(row, *fields):
    return {key: row[key] for key in fields if key in row}


def _counts(data):
    entries = [entry for player in data["players"] for entry in player["entries"]]
    result = {"players": len(data["players"]), "entries": len(entries),
              "scalars": sum(len(player["scalars"]) for player in data["players"]),
              "keys": sum(len(entry["keys"]) for entry in entries),
              "values": sum(len(entry["values"]) for entry in entries), "omitted_records": len(data["gaps"])}
    result["records"] = sum(result.values())
    result.update({name: sum(row["reason"] == reason for row in data["gaps"])
                   for name, reason in (("unknown_records", "unknown_field"), ("type_mismatches", "type_mismatch"),
                                        ("known_opaque_records", "known_opaque"))})
    return result


def _base(status, digest):
    return {"format": FORMAT, "status": status, "source": {"sha256": digest, "section": SECTION},
            "protocol_verified": False, "import_complete": False, "semantics": "none",
            **{key: "unknown" for key in UNKNOWN}, "players": [], "gaps": []}


def _gap(data, row, path, fields):
    reason = ("unknown_field" if row["field"] not in fields else
              "type_mismatch" if row["wire_type"] != fields[row["field"]] else "known_opaque")
    data["gaps"].append({"index": row["index"], "path": list(path), "field": row["field"],
                         "wire_type": row["wire_type"], "reason": reason})


def _entry(data, row, path):
    result = {"index": row["index"], "keys": [], "values": []}
    for child in row["children"]:
        if child["field"] == 1 and child["wire_type"] == 0:
            result["keys"].append(_pick(child, "index", "raw_u64", "int32_form", "int32", "low32_signed"))
        elif child["field"] == 2 and child["wire_type"] == 1:
            result["values"].append(_pick(child, "index", "bits_hex", "class"))
        else:
            _gap(data, child, path + [row["index"]], {1: 0, 2: 1})
    return result


def _player(data, row):
    result = {"index": row["index"], "scalars": [], "entries": []}
    for child in row["children"]:
        if child["field"] in range(1, 9) and child["wire_type"] == 5:
            result["scalars"].append({**_pick(child, "index", "field", "bits_hex", "class"), "kind": "float32"})
        elif child["field"] in (10, 11) and child["wire_type"] == 0:
            result["scalars"].append({**_pick(child, "index", "field", "raw_u64"), "kind": "uint64"})
        elif child["field"] == 9 and child["wire_type"] == 2:
            result["entries"].append(_entry(data, child, [row["index"]]))
        else:
            _gap(data, child, [row["index"]], {**{field: 5 for field in range(1, 9)}, 9: 2, 10: 0, 11: 0, 12: 2, 13: 2})
    return result


def read(path, source_sha256):
    """Read the exact saved wrapper automatically without exposing opaque wire records."""
    if type(source_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", source_sha256, re.ASCII) is None:
        _error()
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        _error()
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != source_sha256:
        _error()
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)
        if type(value) is not dict:
            _error()
        status = "decoded"
        for key in ("sections", "ServerSource", "data", "attrInfo"):
            if type(value) is not dict:
                status = "unsupported"
                break
            if key not in value:
                status = "absent"
                break
            value = value[key]
        data = _base(status, source_sha256)
        if status == "decoded":
            if type(value) is not list or len(value) != 2 or value[0] != "rpc.ViewPlayerAttrInfo" or type(value[1]) is not dict:
                data["status"] = "unsupported"
            else:
                text = value[1].get("bytesHex")
                if (type(text) is not str or len(text) > 131072 or len(text) % 2
                        or re.fullmatch(r"[0-9a-fA-F]*", text, re.ASCII) is None):
                    _error()
                from .rawattrs import decode_view_player_attr
                decoded = decode_view_player_attr(bytes.fromhex(text))
                for row in decoded["records"]:
                    if row["field"] == 1 and row["wire_type"] == 2:
                        data["players"].append(_player(data, row))
                    else:
                        _gap(data, row, [], {1: 2})
        data["counts"] = _counts(data)
        return summary(data)
    except (ValueError, KeyError, TypeError, RecursionError):
        _error()


def summary(data, source_sha256=None):
    """Return a detached privacy projection for the enclosing import."""
    try:
        if (type(data) is not dict or data["format"] != FORMAT or type(data["status"]) is not str
                or data["status"] not in ("decoded", "absent", "unsupported")
                or data["protocol_verified"] is not False or data["import_complete"] is not False
                or data["semantics"] != "none" or any(data[key] != "unknown" for key in UNKNOWN)):
            _error()
        if type(data["source"]) is not dict:
            _error()
        digest = data["source"]["sha256"]
        if (type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest, re.ASCII) is None
                or data["source"]["section"] != SECTION
                or source_sha256 is not None and (type(source_sha256) is not str or source_sha256 != digest)):
            _error()
        result = _base(data["status"], digest)
        seen, parents = {}, {}
        for player in _rows(data["players"]):
            index = _record(seen, player, [])
            parents[index] = []
            target = {"index": index, "scalars": [], "entries": []}
            for scalar in _rows(player["scalars"]):
                entry = {"index": _record(seen, scalar, [index]), "field": scalar["field"], "kind": scalar["kind"]}
                if type(scalar["field"]) is not int or type(scalar["kind"]) is not str:
                    _error()
                if scalar["field"] in range(1, 9) and scalar["kind"] == "float32":
                    entry.update(_bits(scalar, 4))
                elif scalar["field"] in (10, 11) and scalar["kind"] == "uint64":
                    _u64(scalar)
                    entry["raw_u64"] = scalar["raw_u64"]
                else:
                    _error()
                target["scalars"].append(entry)
            for entry in _rows(player["entries"]):
                position = _record(seen, entry, [index])
                parents[position] = [index]
                item = {"index": position, "keys": [], "values": []}
                for key in _rows(entry["keys"]):
                    item["keys"].append({"index": _record(seen, key, [index, position]), **_key(key)})
                for value in _rows(entry["values"]):
                    item["values"].append({"index": _record(seen, value, [index, position]), **_bits(value, 8)})
                target["entries"].append(item)
            result["players"].append(target)
        for gap in _rows(data["gaps"]):
            path = gap["path"]
            if (type(path) is not list or len(path) > 2 or any(type(value) is not int for value in path)
                    or path and (path[-1] not in parents or parents[path[-1]] != path[:-1])):
                _error()
            index = _record(seen, gap, path)
            field, wire = gap["field"], gap["wire_type"]
            if type(field) is not int or not 1 <= field < 1 << 29 or type(wire) is not int or wire not in (0, 1, 2, 5):
                _error()
            fields = ({1: 2} if not path else {1: 0, 2: 1} if len(path) == 2 else
                      {**{number: 5 for number in range(1, 9)}, 9: 2, 10: 0, 11: 0, 12: 2, 13: 2})
            if field not in fields:
                reason = "unknown_field"
            elif wire != fields[field]:
                reason = "type_mismatch"
            elif len(path) == 1 and field in (12, 13):
                reason = "known_opaque"
            else:
                _error()
            if gap["reason"] != reason:
                _error()
            result["gaps"].append({"index": index, "path": list(path), "field": field, "wire_type": wire, "reason": reason})
        if set(seen) != set(range(len(seen))) or data["status"] != "decoded" and seen:
            _error()
        context = []
        for index in range(len(seen)):
            path = seen[index]
            if len(path) > len(context) or context[:len(path)] != path:
                _error()
            context = list(path)
            if index in parents:
                context.append(index)
        result["counts"] = _counts(result)
        if type(data["counts"]) is not dict or any(type(data["counts"].get(key)) is not int
                or data["counts"][key] != value for key, value in result["counts"].items()):
            _error()
        return result
    except (ValueError, KeyError, TypeError, RecursionError):
        _error()


def _rows(rows):
    if type(rows) is not list or len(rows) > 4096:
        _error()
    previous = -1
    for row in rows:
        if type(row) is not dict or type(row.get("index")) is not int or row["index"] <= previous:
            _error()
        previous = row["index"]
    return rows


def _record(seen, row, path):
    index = row["index"]
    if (type(index) is not int or not 0 <= index < 4096 or index in seen or len(seen) >= 4096
            or path and index <= path[-1]):
        _error()
    seen[index] = list(path)
    return index


def _u64(row):
    text = row["raw_u64"]
    if type(text) is not str or re.fullmatch(r"0|[1-9][0-9]{0,19}", text, re.ASCII) is None or int(text) >= 1 << 64:
        _error()
    return int(text)


def _key(row):
    value = _u64(row)
    if value < 1 << 31:
        expected = {"int32_form": "canonical_nonnegative", "int32": value}
    elif value >= (1 << 64) - (1 << 31):
        expected = {"int32_form": "canonical_negative", "int32": value - (1 << 64)}
    else:
        expected = {"int32_form": "zero_extended_32bit" if value < 1 << 32 else "other_high_bits",
                    "low32_signed": (value & 0xFFFFFFFF) - (1 << 32 if value & 0x80000000 else 0)}
    if (row["int32_form"] != expected["int32_form"] or any(type(row.get(key)) is not int or row[key] != number
            for key, number in expected.items() if key != "int32_form")
            or "int32" in row and "int32" not in expected or "low32_signed" in row and "low32_signed" not in expected):
        _error()
    return {"raw_u64": row["raw_u64"], **expected}


def _bits(row, size):
    bits = row["bits_hex"]
    if type(bits) is not str or re.fullmatch(r"[0-9a-f]{" + str(size * 2) + "}", bits, re.ASCII) is None:
        _error()
    value = struct.unpack("<f" if size == 4 else "<d", bytes.fromhex(bits))[0]
    sign = "negative" if math.copysign(1, value) < 0 else "positive"
    kind = "nan" if math.isnan(value) else sign + "_infinity" if math.isinf(value) else sign + "_zero" if value == 0 else "finite"
    if row["class"] != kind:
        _error()
    return {"bits_hex": bits, "class": kind}
