"""Keep automatically decoded structural numbers separate from character identities and combat stats."""

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from damage_lab.rawattrbundle import read, summary


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result + bytes([value]))


def message(field, payload):
    return varint(field * 8 + 2) + varint(len(payload)) + payload


def source(folder, payload):
    path = Path(folder) / "source.json"
    raw = json.dumps({"sections": {"ServerSource": {"data": {"attrInfo":
        ["rpc.ViewPlayerAttrInfo", {"bytesHex": payload.hex()}], "PlayerId": "PRIVATE-PLAYER-CANARY"}}}}).encode()
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


class RawAttrBundleTests(unittest.TestCase):
    """Import only bounded typed protocol evidence without retaining opaque identity payloads."""

    def test_read_automatically_keeps_typed_attributes_with_the_verified_source(self):
        entry = b"\x08" + varint(137) + b"\x11" + struct.pack("<d", 37.125)
        payload = message(1, b"\x0d" + struct.pack("<f", 19.25) + message(9, entry))
        with tempfile.TemporaryDirectory() as folder:
            path, digest = source(folder, payload)
            data = read(path, digest)
            self.assertEqual((data["status"], data["source"], data["players"][0]["scalars"][0]["bits_hex"],
                              data["players"][0]["entries"][0]["keys"][0]["raw_u64"],
                              data["players"][0]["entries"][0]["values"][0]["bits_hex"],
                              data["protocol_verified"], data["dps"], data["import_complete"]),
                             ("decoded", {"sha256": digest, "section": "sections.ServerSource.data.attrInfo"},
                              struct.pack("<f", 19.25).hex(), "137", struct.pack("<d", 37.125).hex(),
                              False, "unknown", False))

    def test_opaque_known_and_unknown_fields_cannot_disclose_account_payloads(self):
        canary = b"OPAQUE-ACCOUNT-CANARY"
        payload = message(1, message(13, canary) + message(39, canary)) + message(43, canary)
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, payload))
            text = json.dumps(data)
            self.assertEqual((canary.decode() in text, canary.hex() in text, "PRIVATE-PLAYER-CANARY" in text,
                              data["counts"]["omitted_records"]), (False, False, False, 3))

    def test_repeated_player_wrappers_and_entry_fields_remain_separate(self):
        entry = b"\x08\x13\x08\x1d\x11" + struct.pack("<d", -0.0) + b"\x11" + struct.pack("<d", 41.75)
        player = message(9, entry) + message(9, b"")
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, message(1, player) + message(1, b"")))
            self.assertEqual((len(data["players"]), len(data["players"][0]["entries"]),
                              [row["raw_u64"] for row in data["players"][0]["entries"][0]["keys"]],
                              [row["class"] for row in data["players"][0]["entries"][0]["values"]],
                              data["players"][1]["entries"]),
                             (2, 2, ["19", "29"], ["negative_zero", "finite"], []))

    def test_empty_serialization_is_decoded_without_default_character_values(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, b""))
            self.assertEqual((data["status"], data["players"], data["counts"]["records"]), ("decoded", [], 0))

    def test_absent_and_legacy_attribute_shapes_are_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            statuses = []
            for document in ({"sections": {}}, {"sections": {"ServerSource": {"data": {"attrInfo": {"legacy": 17}}}}}):
                raw = json.dumps(document).encode()
                path.write_bytes(raw)
                statuses.append(read(path, hashlib.sha256(raw).hexdigest())["status"])
            self.assertEqual(statuses, ["absent", "unsupported"])

    def test_source_digest_mismatch_refuses_before_projection(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _ = source(folder, b"")
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                read(path, "a" * 64)

    def test_recognized_malformed_hex_has_only_a_fixed_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            raw = b'{"sections":{"ServerSource":{"data":{"attrInfo":["rpc.ViewPlayerAttrInfo",{"bytesHex":"PRIVATE-BAD-HEX"}]}}}}'
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                read(path, hashlib.sha256(raw).hexdigest())

    def test_recognized_truncated_wire_has_only_a_fixed_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path, digest = source(folder, b"\x0a\x7fPRIVATE-TRUNCATED-CANARY")
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                read(path, digest)

    def test_duplicate_json_members_refuse_before_selecting_a_source_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            raw = b'{"sections":{},"sections":{"private":"DUPLICATE-CANARY"}}'
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                read(path, hashlib.sha256(raw).hexdigest())

    def test_nonfinite_source_numbers_refuse_without_echoing_them(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            raw = b'{"sections":{},"private":NaN}'
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                read(path, hashlib.sha256(raw).hexdigest())

    def test_payload_byte_limit_is_checked_before_decoding(self):
        with tempfile.TemporaryDirectory() as folder:
            path, digest = source(folder, b"x" * 65537)
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                read(path, digest)

    def test_source_byte_limit_refuses_an_oversized_real_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            with path.open("wb") as stream:
                stream.truncate(64 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                read(path, "e" * 64)

    def test_wrong_wire_types_and_opaque_nested_bytes_do_not_become_numeric_values(self):
        player = b"\x09" + b"PRIVATE!" + message(13, b"\xff\x00\x80")
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, message(1, player)))
            self.assertEqual((data["players"][0]["scalars"], data["counts"]["omitted_records"],
                              data["counts"]["type_mismatches"]), ([], 2, 1))

    def test_summary_cannot_promote_protocol_or_combat_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, b""))
            data["protocol_verified"] = True
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                summary(data)

    def test_summary_is_detached_and_drops_arbitrary_private_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, message(1, b"\x50\x17")))
            data["opaque"] = "SUMMARY-PRIVATE-CANARY"
            result = summary(data)
            result["players"][0]["scalars"][0]["raw_u64"] = "29"
            self.assertEqual(("SUMMARY-PRIVATE-CANARY" in json.dumps(result),
                              data["players"][0]["scalars"][0]["raw_u64"]), (False, "23"))

    def test_summary_refuses_a_forged_float_class(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, message(1, b"\x0d" + struct.pack("<f", 17.75))))
            data["players"][0]["scalars"][0]["class"] = "nan"
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                summary(data)

    def test_summary_refuses_a_forged_canonical_key(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, message(1, message(9, b"\x08\x1f"))))
            data["players"][0]["entries"][0]["keys"][0]["int32"] = 47
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                summary(data)

    def test_summary_refuses_counts_that_disagree_with_value_free_gaps(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, message(1, message(13, b"OPAQUE-CANARY"))))
            data["counts"]["omitted_records"] = 0
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                summary(data)

    def test_summary_binds_the_evidence_to_the_enclosing_import_source(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, b""))
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                summary(data, "d" * 64)

    def test_summary_refuses_children_moved_across_a_later_wrapper_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            data = read(*source(folder, message(1, b"") + message(1, b"\x50\x17")))
            data["players"][0]["scalars"] = data["players"][1]["scalars"]
            data["players"][1]["scalars"] = []
            with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                summary(data)

    def test_summary_refuses_string_subclasses_that_spoof_copied_enums(self):
        class Token(str):
            """Expose private text behind equality that accepts declared enum values."""

            def __eq__(self, value):
                return True

        with tempfile.TemporaryDirectory() as folder:
            for field in ("status", "kind"):
                with self.subTest(field=field):
                    data = read(*source(folder, b"" if field == "status" else message(1, b"\x0d" + struct.pack("<f", 7.75))))
                    if field == "status":
                        data["status"] = Token("PRIVATE-ENUM-CANARY")
                    else:
                        data["players"][0]["scalars"][0]["kind"] = Token("PRIVATE-ENUM-CANARY")
                    with self.assertRaisesRegex(ValueError, "^Raw attribute evidence requires a bounded source contract$"):
                        summary(data)
