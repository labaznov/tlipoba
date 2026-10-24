import json
import unittest


from damage_lab.rawattrs import decode_view_player_attr

ERROR = "Raw player-attribute payload does not satisfy the bounded protobuf contract"
HASHES = {"rpc.ViewPlayerAttrInfo": "683791136b4cde5022cd2ec6caffdd46b2bed15656f45a456f22154f25cdf500",
          "rpc.CPlayerData": "907e2d40d61f9c2cf9c2c91ff2ab66e75ff164c9349dfd39ad2103b5c8d8e099",
          "rpc.CPlayerData.AttrsEntry": "9225112b19d070ccb8fb125104b5175bf3455a5a18ff8ad96ac877e67d4d4a24"}
ONE = bytes.fromhex("000000000000f03f")


def varint(value):
    """Encode a synthetic minimal varint independently of the decoder."""
    out = bytearray()
    while True:
        byte, value = value & 0x7F, value >> 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def key(field, wire):
    return varint(field << 3 | wire)


def nested(field, payload):
    return key(field, 2) + varint(len(payload)) + payload


def entry(*parts):
    return nested(9, b"".join(parts))


def wrap(*parts):
    return nested(1, b"".join(parts))


def rebuild(records):
    """Rebuild bytes from the documented record rule, without calling decoder internals."""
    out = []
    for record in records:
        out.append(record["tag_hex"])
        if "raw_hex" in record:
            out.append(record["raw_hex"])
        elif "bits_hex" in record:
            out.append(record["bits_hex"])
        else:
            out.append(record["length_hex"])
            out.append(bytes(rebuild(record["children"])).hex() if "children" in record else record["payload_hex"])
    return bytes.fromhex("".join(out))


class RawPlayerAttrsTest(unittest.TestCase):
    """Decode synthetic wire bytes into a lossless record tree without semantic mapping."""

    def test_an_empty_payload_keeps_a_fixed_envelope_and_an_absent_player_attr(self):
        self.assertEqual(decode_view_player_attr(b""), {
            "format": "tli-raw-player-attr-v1", "encoding_assumption": "standard_protobuf_unverified",
            "descriptor_raw_sha256": HASHES, "input_bytes": 0, "original_presence_discipline": "unknown",
            "schema_coverage": {"unknown_fields": [], "declared_type_mismatches": []},
            "encoding_form": {"non_minimal_varints": {"count": 0, "locations": []}, "repeated_singular": []},
            "records": [],
            "views": {"messages": [{"path": [], "message": "rpc.ViewPlayerAttrInfo",
                                    "singular_fields": [{"field": 1, "state": "absent", "records": []}]}],
                      "duplicate_keys": []},
            "semantics": "none", "attribute_ids": "unknown", "units": "unknown", "getters": "unknown",
            "effective_level": "unknown", "native_mapping": "unknown", "dps": "unknown"})

    def test_one_entry_becomes_a_preorder_record_tree_with_exact_bytes(self):
        payload = wrap(entry(key(1, 0) + b"\x05", key(2, 1) + ONE))
        self.assertEqual(decode_view_player_attr(payload)["records"], [
            {"index": 0, "offset": 0, "field": 1, "wire_type": 2, "tag_hex": "0a", "length_hex": "0d", "length": 13,
             "children": [{"index": 1, "offset": 0, "field": 9, "wire_type": 2, "tag_hex": "4a", "length_hex": "0b",
                           "length": 11, "children": [
                               {"index": 2, "offset": 0, "field": 1, "wire_type": 0, "tag_hex": "08", "raw_hex": "05",
                                "raw_u64": "5", "minimal": True, "int32_form": "canonical_nonnegative", "int32": 5},
                               {"index": 3, "offset": 2, "field": 2, "wire_type": 1, "tag_hex": "11",
                                "bits_hex": ONE.hex(), "class": "finite"}]}]}])

    def test_every_decoded_message_lists_its_declared_singular_fields_without_values(self):
        absent = [{"field": field, "state": "absent", "records": []} for field in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13)]
        result = decode_view_player_attr(wrap(entry(key(1, 0) + b"\x05", key(2, 1) + ONE)))
        self.assertEqual(result["views"]["messages"], [
            {"path": [], "message": "rpc.ViewPlayerAttrInfo",
             "singular_fields": [{"field": 1, "state": "present", "records": [0]}]},
            {"path": [0], "message": "rpc.CPlayerData", "singular_fields": absent},
            {"path": [0, 1], "message": "rpc.CPlayerData.AttrsEntry",
             "singular_fields": [{"field": 1, "state": "present", "records": [2]},
                                 {"field": 2, "state": "present", "records": [3]}]}])

    def test_the_record_tree_rebuilds_the_input_byte_for_byte(self):
        payload = wrap(entry(key(2, 1) + ONE, key(1, 0) + b"\x05"), key(10, 0) + varint(7), key(1, 5) + b"\x00\x00\x80\x3f")
        self.assertEqual(rebuild(decode_view_player_attr(payload)["records"]), payload)

    def test_non_minimal_tags_lengths_and_payloads_are_reported_by_component(self):
        inner = key(1, 0) + b"\x85\x00" + key(2, 1) + ONE
        payload = b"\x0a\x90\x00" + b"\xca\x00\x8c\x00" + inner
        self.assertEqual(decode_view_player_attr(payload)["encoding_form"]["non_minimal_varints"], {"count": 4, "locations": [
            {"record_index": 0, "component": "length"}, {"record_index": 1, "component": "tag"},
            {"record_index": 1, "component": "length"}, {"record_index": 2, "component": "payload"}]})

    def test_non_minimal_bytes_at_both_wrapper_levels_still_rebuild_exactly(self):
        payload = b"\x0a\x90\x00" + b"\xca\x00\x8c\x00" + key(1, 0) + b"\x85\x00" + key(2, 1) + ONE
        self.assertEqual(rebuild(decode_view_player_attr(payload)["records"]), payload)

    def test_unknown_fields_are_valid_forward_compatible_records(self):
        result = decode_view_player_attr(wrap(key(99, 0) + b"\x2a"))
        self.assertEqual(result["schema_coverage"]["unknown_fields"],
                         [{"path": [0], "field": 99, "wire_type": 0, "record_index": 1}])

    def test_a_known_field_on_the_wrong_wire_type_is_a_raw_mismatch(self):
        result = decode_view_player_attr(wrap(key(9, 0) + b"\x01"))
        self.assertEqual(result["schema_coverage"]["declared_type_mismatches"],
                         [{"path": [0], "field": 9, "expected_wire_type": 2, "wire_type": 0, "record_index": 1}])

    def test_unknown_or_mismatched_fixed_width_data_has_bits_but_no_float_class(self):
        result = decode_view_player_attr(wrap(key(98, 1) + ONE, key(1, 1) + ONE))
        self.assertEqual(result["records"][0]["children"], [
            {"index": 1, "offset": 0, "field": 98, "wire_type": 1, "tag_hex": "9106", "bits_hex": ONE.hex()},
            {"index": 2, "offset": 10, "field": 1, "wire_type": 1, "tag_hex": "09", "bits_hex": ONE.hex()}])

    def test_a_wrong_wire_singular_field_is_present_without_a_typed_value(self):
        result = decode_view_player_attr(wrap(key(1, 0) + b"\x07"))
        self.assertEqual((result["views"]["messages"][1]["singular_fields"][0], result["records"][0]["children"]),
                         ({"field": 1, "state": "present", "records": [1]},
                          [{"index": 1, "offset": 0, "field": 1, "wire_type": 0, "tag_hex": "08", "raw_hex": "07",
                            "raw_u64": "7", "minimal": True}]))

    def test_opaque_len_fields_stay_opaque_even_when_their_bytes_look_malformed(self):
        result = decode_view_player_attr(wrap(nested(12, b"\xff\xff"), nested(13, b"\x0b"), nested(77, b"\x08"))
                                         + nested(5, b"\x80"))
        self.assertEqual([(record["index"], record["field"], record.get("payload_hex"), "children" in record)
                          for record in [*result["records"][0]["children"], result["records"][1]]],
                         [(1, 12, "ffff", False), (2, 13, "0b", False), (3, 77, "08", False), (4, 5, "80", False)])

    def test_repeated_singular_fields_are_wire_observations_in_message_preorder(self):
        f = b"\x00\x00\x80\x3f"
        payload = wrap(key(2, 5) + f, key(1, 5) + f, key(2, 5) + f, key(1, 0) + b"\x01") + wrap()
        self.assertEqual(decode_view_player_attr(payload)["encoding_form"]["repeated_singular"],
                         [{"path": [], "field": 1, "records": [0, 5]}, {"path": [0], "field": 1, "records": [2, 4]},
                          {"path": [0], "field": 2, "records": [1, 3]}])

    def test_two_player_attr_wrappers_are_decoded_as_separate_messages(self):
        payload = wrap(entry(key(1, 0) + b"\x05")) + wrap(entry(key(1, 0) + b"\x06"))
        self.assertEqual([(view["path"], view["message"]) for view in decode_view_player_attr(payload)["views"]["messages"]],
                         [([], "rpc.ViewPlayerAttrInfo"), ([0], "rpc.CPlayerData"), ([0, 1], "rpc.CPlayerData.AttrsEntry"),
                          ([3], "rpc.CPlayerData"), ([3, 4], "rpc.CPlayerData.AttrsEntry")])

    def test_int32_keys_report_their_exact_varint_form_and_minimality(self):
        forms = ["05", "8500", "ffffffff07", "80808080f8ffffffff01", "ffffffffffffffffff01", "ffffffff0f", "8080808008",
                 "8080808010"]
        result = decode_view_player_attr(wrap(*[entry(key(1, 0) + bytes.fromhex(form)) for form in forms]))
        self.assertEqual([{name: value for name, value in item["children"][0].items()
                           if name in ("int32_form", "int32", "low32_signed", "minimal")}
                          for item in result["records"][0]["children"]],
                         [{"int32_form": "canonical_nonnegative", "int32": 5, "minimal": True},
                          {"int32_form": "canonical_nonnegative", "int32": 5, "minimal": False},
                          {"int32_form": "canonical_nonnegative", "int32": 2147483647, "minimal": True},
                          {"int32_form": "canonical_negative", "int32": -2147483648, "minimal": True},
                          {"int32_form": "canonical_negative", "int32": -1, "minimal": True},
                          {"int32_form": "zero_extended_32bit", "low32_signed": -1, "minimal": True},
                          {"int32_form": "zero_extended_32bit", "low32_signed": -2147483648, "minimal": True},
                          {"int32_form": "other_high_bits", "low32_signed": 0, "minimal": True}])

    def test_declared_floats_and_doubles_keep_exact_bits_and_a_class(self):
        doubles = ["0000000000000000", "0000000000000080", "000000000000f07f", "000000000000f0ff", "000000000000f87f",
                   "010000000000f07f", "0100000000000000"]
        floats = ["00000000", "00000080", "0000807f", "0100c0ff"]
        result = decode_view_player_attr(wrap(*[key(1, 5) + bytes.fromhex(bits) for bits in floats],
                                              *[entry(key(2, 1) + bytes.fromhex(bits)) for bits in doubles]))
        children = result["records"][0]["children"]
        self.assertEqual([(item["bits_hex"], item["class"]) for item in children[:4]]
                         + [(item["children"][0]["bits_hex"], item["children"][0]["class"]) for item in children[4:]],
                         list(zip(floats, ["positive_zero", "negative_zero", "positive_infinity", "nan"]))
                         + list(zip(doubles, ["positive_zero", "negative_zero", "positive_infinity", "negative_infinity",
                                              "nan", "nan", "finite"])))

    def test_nonfinite_results_are_strict_json_without_a_decimal_display(self):
        result = decode_view_player_attr(wrap(entry(key(2, 1) + bytes.fromhex("000000000000f87f")), key(1, 5) + bytes(4)))
        text = json.dumps(result, allow_nan=False)
        self.assertEqual(('"decimal"' in text, json.loads(text) == result), (False, True))

    def test_the_maximum_uint64_stays_a_decimal_string_without_an_int32_view(self):
        record = decode_view_player_attr(wrap(key(10, 0) + bytes.fromhex("ffffffffffffffffff01")))["records"][0]["children"][0]
        self.assertEqual(record, {"index": 1, "offset": 0, "field": 10, "wire_type": 0, "tag_hex": "50",
                                  "raw_hex": "ffffffffffffffffff01", "raw_u64": "18446744073709551615", "minimal": True})

    def test_equal_keys_in_distinct_entries_form_one_wire_order_group(self):
        result = decode_view_player_attr(wrap(*[entry(key(1, 0) + b"\x07") for _ in range(1000)]))
        self.assertEqual(result["views"]["duplicate_keys"], [{"path": [0], "groups": [
            {"raw_u64": "7", "int32_form": "canonical_nonnegative", "entries": list(range(1, 2000, 2))}]}])

    def test_distinct_keys_in_one_entry_each_count_that_entry_once(self):
        payload = wrap(entry(key(1, 0) + b"\x05", key(1, 0) + b"\x06"), entry(key(1, 0) + b"\x06"), entry(key(1, 0) + b"\x05"))
        self.assertEqual(decode_view_player_attr(payload)["views"]["duplicate_keys"][0]["groups"], [
            {"raw_u64": "5", "int32_form": "canonical_nonnegative", "entries": [1, 6]},
            {"raw_u64": "6", "int32_form": "canonical_nonnegative", "entries": [1, 4]}])

    def test_a_key_repeated_inside_one_entry_cannot_create_a_group_alone(self):
        payload = wrap(entry(key(1, 0) + b"\x05", key(1, 0) + b"\x05"), entry(key(1, 0) + b"\x06"))
        self.assertEqual(decode_view_player_attr(payload)["views"]["duplicate_keys"], [{"path": [0], "groups": []}])

    def test_separate_player_data_wrappers_never_share_key_groups(self):
        payload = wrap(entry(key(1, 0) + b"\x05")) + wrap(entry(key(1, 0) + b"\x05"))
        self.assertEqual(decode_view_player_attr(payload)["views"]["duplicate_keys"],
                         [{"path": [0], "groups": []}, {"path": [3], "groups": []}])

    def test_mismatched_keys_and_different_int32_forms_are_not_grouped(self):
        payload = wrap(entry(nested(1, b"")), entry(nested(1, b"")), entry(key(1, 0) + bytes.fromhex("ffffffff0f")),
                       entry(key(1, 0) + bytes.fromhex("ffffffffffffffffff01")))
        self.assertEqual(decode_view_player_attr(payload)["views"]["duplicate_keys"], [{"path": [0], "groups": []}])

    def test_duplicate_key_output_grows_linearly_with_the_input(self):
        payload = wrap(*[entry(key(1, 0) + b"\x07") for _ in range(1000)])
        self.assertLess(len(json.dumps(decode_view_player_attr(payload))), 200 * len(payload))

    def test_structural_failures_and_limits_share_one_fixed_refusal_without_payload_text(self):
        canary = b"PRIVATECANARY"
        cases = [b"\x0a\x0d" + canary[:3], b"\x0a\x04\x4a\x02\x11" + canary[:1], b"\x08" + b"\xff" * 10 + b"\x01",
                 b"\x08" + b"\xff" * 9 + b"\x02", bytes.fromhex("8080808010") + b"\x00", b"\x00\x00", b"\x0b", b"\x0c",
                 b"\x0e", b"\x0f", nested(99, canary) + b"\x88", bytes(65537), b"\x98\x06\x00" * 4097,
                 bytearray(b""), memoryview(b""), "", None]
        messages = []
        for payload in cases:
            try:
                decode_view_player_attr(payload)
            except ValueError as error:
                messages.append(str(error))
            else:
                messages.append(None)
        self.assertEqual(messages, [ERROR] * len(cases))

    def test_the_exact_byte_and_record_limits_are_accepted(self):
        limit_bytes = nested(99, bytes(65531))
        limit_records = b"\x98\x06\x00" * 4096
        self.assertEqual([(len(limit_bytes), decode_view_player_attr(limit_bytes)["input_bytes"]),
                          len(decode_view_player_attr(limit_records)["records"])], [(65536, 65536), 4096])

    def test_an_explicit_zero_key_is_present_and_an_omitted_key_is_absent(self):
        result = decode_view_player_attr(wrap(entry(key(1, 0) + b"\x00"), entry(key(2, 1) + ONE)))
        self.assertEqual([view["singular_fields"][0] for view in result["views"]["messages"][2:]],
                         [{"field": 1, "state": "present", "records": [2]}, {"field": 1, "state": "absent", "records": []}])

    def test_unusual_but_valid_wire_shapes_all_rebuild_exactly(self):
        payload = (wrap() + b"\x0a\x80\x00" + wrap(key(19000, 0) + b"\x01", entry(key(2, 1) + ONE, key(1, 0) + b"\x05"),
                                                    key(10, 0) + bytes.fromhex("ffffffffffffffffff01"),
                                                    entry(key(1, 0) + bytes.fromhex("80808080f8ffffffff01")),
                                                    key(1, 5) + bytes.fromhex("00000080"), nested(12, b"\xff"))
                   + key(55, 5) + bytes(4))
        self.assertEqual(rebuild(decode_view_player_attr(payload)["records"]), payload)

    def test_results_are_detached_and_repeat_identically(self):
        payload = wrap(entry(key(1, 0) + b"\x05"), entry(key(1, 0) + b"\x05"))
        first = decode_view_player_attr(payload)
        expected = json.loads(json.dumps(first))
        first["views"]["duplicate_keys"][0]["groups"][0]["entries"].append(99)
        first["descriptor_raw_sha256"].clear()
        first["records"][0]["children"].clear()
        self.assertEqual(decode_view_player_attr(payload), expected)


if __name__ == "__main__":
    unittest.main()
