import base64
import unittest
import uuid

from damage_lab.sharecode import decode


class SharecodeTests(unittest.TestCase):
    """Check record-key decoding without asserting a game server contract."""

    def test_decodes_a_synthetic_record_key_without_verifying_its_transport(self):
        self.assertEqual(decode(base64.b64encode(uuid.UUID(
            "9db7f03a-76d9-4f50-b3a8-12af427e809c",
        ).bytes).decode("ascii")), {
            "format": "tli-record-key",
            "record_key_hex": "9db7f03a76d94f50b3a812af427e809c",
            "record_uuid": "9db7f03a-76d9-4f50-b3a8-12af427e809c",
            "transport_verified": False,
        })

    def test_empty_code_has_a_safe_validation_error(self):
        with self.assertRaisesRegex(ValueError, r"\AShare code must be canonical standard Base64 for a 16-byte record key\Z"):
            decode("")

    def test_code_cannot_have_nonzero_unused_padding_bits(self):
        code = base64.b64encode(uuid.UUID("9db7f03a-76d9-4f50-b3a8-12af427e809c").bytes).decode("ascii")
        with self.assertRaises(ValueError):
            decode(code[:-3] + "B==")

    def test_accepts_a_synthetic_version_one_uuid_as_a_mechanical_candidate(self):
        self.assertEqual(decode(base64.b64encode(uuid.UUID(
            "8d67a2e0-e83c-11ee-98ad-0242ac120003",
        ).bytes).decode("ascii"))["record_uuid"], "8d67a2e0-e83c-11ee-98ad-0242ac120003")

    def test_code_cannot_have_missing_padding(self):
        with self.assertRaises(ValueError):
            decode(base64.b64encode(uuid.UUID("9db7f03a-76d9-4f50-b3a8-12af427e809c").bytes).decode("ascii").rstrip("="))

    def test_code_cannot_have_superfluous_padding(self):
        with self.assertRaises(ValueError):
            decode(base64.b64encode(uuid.UUID("9db7f03a-76d9-4f50-b3a8-12af427e809c").bytes).decode("ascii") + "=")

    def test_record_key_cannot_be_shorter_than_sixteen_bytes(self):
        with self.assertRaises(ValueError):
            decode(base64.b64encode(uuid.UUID("9db7f03a-76d9-4f50-b3a8-12af427e809c").bytes[:-1]).decode("ascii"))

    def test_record_key_cannot_be_longer_than_sixteen_bytes(self):
        with self.assertRaises(ValueError):
            decode(base64.b64encode(uuid.UUID("9db7f03a-76d9-4f50-b3a8-12af427e809c").bytes + b"\x83").decode("ascii"))

    def test_code_cannot_use_the_urlsafe_alphabet(self):
        with self.assertRaises(ValueError):
            decode(base64.urlsafe_b64encode(uuid.UUID("ffffffff-ffff-4fff-bfff-ffffffffffff").bytes).decode("ascii"))

    def test_code_cannot_include_whitespace(self):
        code = base64.b64encode(uuid.UUID("9db7f03a-76d9-4f50-b3a8-12af427e809c").bytes).decode("ascii")
        with self.assertRaises(ValueError):
            decode(code[:9] + "\n" + code[9:])

    def test_code_cannot_be_a_url(self):
        with self.assertRaises(ValueError):
            decode("https://example.invalid/?code=" + base64.b64encode(
                uuid.UUID("9db7f03a-76d9-4f50-b3a8-12af427e809c").bytes,
            ).decode("ascii"))

    def test_non_ascii_code_has_a_safe_validation_error(self):
        with self.assertRaisesRegex(ValueError, r"\AShare code must be canonical standard Base64 for a 16-byte record key\Z"):
            decode("\u0416" * 22 + "==")

    def test_control_characters_have_a_safe_validation_error(self):
        with self.assertRaisesRegex(ValueError, r"\AShare code must be canonical standard Base64 for a 16-byte record key\Z"):
            decode("\x00" * 24)

    def test_code_cannot_be_an_unbounded_payload(self):
        with self.assertRaises(ValueError):
            decode("Y" * 1000000)
