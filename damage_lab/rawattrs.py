"""Losslessly decode a bounded ViewPlayerAttrInfo wire payload into a record tree, without semantic mapping."""

ERROR = "Raw player-attribute payload does not satisfy the bounded protobuf contract"
HASHES = {"rpc.ViewPlayerAttrInfo": "683791136b4cde5022cd2ec6caffdd46b2bed15656f45a456f22154f25cdf500",
          "rpc.CPlayerData": "907e2d40d61f9c2cf9c2c91ff2ab66e75ff164c9349dfd39ad2103b5c8d8e099",
          "rpc.CPlayerData.AttrsEntry": "9225112b19d070ccb8fb125104b5175bf3455a5a18ff8ad96ac877e67d4d4a24"}
MAX_BYTES, MAX_RECORDS = 65536, 4096
WIRE = {"float": 5, "double": 1, "uint64": 0, "int32": 0, "message": 2}
# Structural descriptor labels from the accepted saved projection: field -> (type, decoded message, repeated).
MESSAGES = {
    "rpc.ViewPlayerAttrInfo": {1: ("message", "rpc.CPlayerData", False)},
    "rpc.CPlayerData": {**{field: ("float", None, False) for field in range(1, 9)},
                        9: ("message", "rpc.CPlayerData.AttrsEntry", True), 10: ("uint64", None, False),
                        11: ("uint64", None, False), 12: ("message", None, True), 13: ("message", None, False)},
    "rpc.CPlayerData.AttrsEntry": {1: ("int32", None, False), 2: ("double", None, False)}}


def _error():
    raise ValueError(ERROR)


def _varint(data, position, end):
    value = 0
    for count in range(10):
        if position + count >= end:
            _error()
        byte = data[position + count]
        if count == 9 and byte > 1:
            _error()
        value |= (byte & 0x7F) << (7 * count)
        if not byte & 0x80:
            return value, position + count + 1
    _error()


def _minimal(value, start, end):
    return end - start == max(1, -(-value.bit_length() // 7))


class _Decoder:
    """Own the bounded parse state of one structural message tree."""

    def __init__(self, data):
        self.data, self.count, self.messages, self.player_data, self.non_minimal = data, 0, [], [], []
        self.unknown, self.mismatches = [], []

    def message(self, name, start, end, path):
        view = {"path": list(path), "message": name, "singular_fields": []}
        self.messages.append(view)
        keys = None
        if name == "rpc.CPlayerData":
            keys = {"path": list(path), "groups": []}
            self.player_data.append(keys)
        fields, records, position = MESSAGES[name], [], start
        while position < end:
            records.append(self.record(fields, start, position, end, path))
            position = self.position
        if keys is not None:
            keys["groups"] = _groups(records)
        seen = {}
        for record in records:
            seen.setdefault(record["field"], []).append(record["index"])
        view["singular_fields"] = [{"field": field, "state": _state(len(seen.get(field, ()))), "records": seen.get(field, [])}
                                   for field, (_, _, repeated) in sorted(fields.items()) if not repeated]
        return records

    def record(self, fields, start, position, end, path):
        data = self.data
        tag, after = _varint(data, position, end)
        field, wire = tag >> 3, tag & 7
        if tag >= 1 << 32 or not field or wire in (3, 4, 6, 7) or self.count >= MAX_RECORDS:
            _error()
        record = {"index": self.count, "offset": position - start, "field": field, "wire_type": wire,
                  "tag_hex": data[position:after].hex()}
        self.count += 1
        self.form(record, tag, position, after, "tag")
        kind, target, _ = fields.get(field, (None, None, None))
        matched = kind is not None and WIRE[kind] == wire
        if kind is None:
            self.unknown.append({"path": list(path), "field": field, "wire_type": wire, "record_index": record["index"]})
        elif not matched:
            self.mismatches.append({"path": list(path), "field": field, "expected_wire_type": WIRE[kind],
                                    "wire_type": wire, "record_index": record["index"]})
        if wire == 0:
            value, self.position = _varint(data, after, end)
            record.update(raw_hex=data[after:self.position].hex(), raw_u64=str(value),
                          minimal=self.form(record, value, after, self.position, "payload"))
            if matched and kind == "int32":
                record.update(_int32(value))
        elif wire in (1, 5):
            self.position = after + (8 if wire == 1 else 4)
            if self.position > end:
                _error()
            bits = data[after:self.position]
            record["bits_hex"] = bits.hex()
            if matched:
                record["class"] = _class(bits)
        else:
            length, body = _varint(data, after, end)
            if body + length > end:
                _error()
            record.update(length_hex=data[after:body].hex(), length=length)
            self.form(record, length, after, body, "length")
            if matched and target is not None:
                record["children"] = self.message(target, body, body + length, path + [record["index"]])
            else:
                record["payload_hex"] = data[body:body + length].hex()
            self.position = body + length
        return record

    def form(self, record, value, start, end, component):
        minimal = _minimal(value, start, end)
        if not minimal:
            self.non_minimal.append({"record_index": record["index"], "component": component})
        return minimal


def _groups(records):
    """Group distinct matching-wire entry keys seen in at least two entries, without choosing a winner."""
    groups = {}
    for record in records:
        if record["field"] != 9 or "children" not in record:
            continue
        seen = set()
        for child in record["children"]:
            if child["field"] == 1 and child["wire_type"] == 0 and child["raw_u64"] not in seen:
                seen.add(child["raw_u64"])
                groups.setdefault(child["raw_u64"], {"raw_u64": child["raw_u64"], "int32_form": child["int32_form"],
                                                     "entries": []})["entries"].append(record["index"])
    return [group for group in groups.values() if len(group["entries"]) > 1]


def _int32(value):
    low = (value & 0xFFFFFFFF) - ((value & 0x80000000) << 1)
    if value < 1 << 31:
        return {"int32_form": "canonical_nonnegative", "int32": value}
    if value >= (1 << 64) - (1 << 31):
        return {"int32_form": "canonical_negative", "int32": value - (1 << 64)}
    return {"int32_form": "zero_extended_32bit" if value < 1 << 32 else "other_high_bits", "low32_signed": low}


def _state(count):
    return "absent" if not count else "present" if count == 1 else "repeated"


def _class(bits):
    value, exponent = int.from_bytes(bits, "little"), (8, 11)[len(bits) == 8]
    mantissa = len(bits) * 8 - 1 - exponent
    sign, fraction = value >> (len(bits) * 8 - 1), value & ((1 << mantissa) - 1)
    power = (value >> mantissa) & ((1 << exponent) - 1)
    if power == (1 << exponent) - 1:
        return "nan" if fraction else ("positive_infinity", "negative_infinity")[sign]
    if not power and not fraction:
        return ("positive_zero", "negative_zero")[sign]
    return "finite"


def _bytes(records):
    out = bytearray()
    for record in records:
        out += bytes.fromhex(record["tag_hex"])
        if "raw_hex" in record or "bits_hex" in record:
            out += bytes.fromhex(record.get("raw_hex", record.get("bits_hex")))
        else:
            out += bytes.fromhex(record["length_hex"])
            out += _bytes(record["children"]) if "children" in record else bytes.fromhex(record["payload_hex"])
    return bytes(out)


def decode_view_player_attr(payload):
    """Return the exact record tree, coverage axes and presence views of one synthetic or saved payload."""
    if type(payload) is not bytes or len(payload) > MAX_BYTES:
        _error()
    decoder = _Decoder(payload)
    records = decoder.message("rpc.ViewPlayerAttrInfo", 0, len(payload), [])
    if _bytes(records) != payload:
        _error()
    return {"format": "tli-raw-player-attr-v1", "encoding_assumption": "standard_protobuf_unverified",
            "descriptor_raw_sha256": dict(HASHES), "input_bytes": len(payload), "original_presence_discipline": "unknown",
            "schema_coverage": {"unknown_fields": decoder.unknown, "declared_type_mismatches": decoder.mismatches},
            "encoding_form": {"non_minimal_varints": {"count": len(decoder.non_minimal), "locations": decoder.non_minimal},
                              "repeated_singular": [{"path": list(view["path"]), "field": item["field"],
                                                     "records": list(item["records"])}
                                                    for view in decoder.messages for item in view["singular_fields"]
                                                    if item["state"] == "repeated"]},
            "records": records,
            "views": {"messages": decoder.messages, "duplicate_keys": decoder.player_data},
            "semantics": "none", **{name: "unknown" for name in
                                    ("attribute_ids", "units", "getters", "effective_level", "native_mapping", "dps")}}
