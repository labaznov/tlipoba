import unittest

from damage_lab.nativeanchor import Anchor


class NativeAnchorTests(unittest.TestCase):
    """Verify source-shaped address planning without a process or real captures."""

    def test_code_read_uses_the_observed_module_base(self):
        anchor = Anchor(0x183450000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        self.assertEqual(anchor.code(), {"address": 0x183450123, "size": 8})

    def test_slot_uses_a_signed_rip_displacement(self):
        anchor = Anchor(0x195730000, 0x7000, 0x4B2,
                        bytes.fromhex("488b0578fdffffc3"), 0x800000000000)
        self.assertEqual(anchor.slot(bytes.fromhex("488b0578fdffffc3")),
                         {"address": 0x195730231, "size": 8})

    def test_slot_cannot_be_requested_for_a_different_getter(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        with self.assertRaisesRegex(ValueError, "getter"):
            anchor.slot(bytes.fromhex("488b0528030000c3"))

    def test_source_requires_the_supported_eight_byte_load_and_return(self):
        with self.assertRaisesRegex(ValueError, "source"):
            Anchor(0x195730000, 0x7000, 0x123,
                   bytes.fromhex("488b0d27030000c3"), 0x800000000000)

    def test_field_cannot_cross_the_declared_module_end(self):
        with self.assertRaisesRegex(ValueError, "bounds"):
            Anchor(0x195730000, 0x458, 0x123,
                   bytes.fromhex("488b0527030000c3"), 0x800000000000)

    def test_observation_preserves_an_unsigned_word_without_identity_claims(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        self.assertEqual(
            anchor.observation(bytes.fromhex("488b0527030000c3"), bytes.fromhex("0123456789abcdef")),
            {"format": "tli-native-anchor-observation-v1", "raw_hex": "0123456789abcdef",
             "value_hex": "0xefcdab8967452301", "state": "outside_domain", "code_match": True,
             "claims": {"module_identity": False, "manager_identity": False, "actor_identity": False,
                        "selected_build": False, "currentness": False, "atomicity": False, "dps": False}})

    def test_observation_requires_exactly_eight_immutable_bytes(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        for data in (b"\x13" * 7, b"\x17" * 9, bytearray(b"\x23" * 8)):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "field"):
                anchor.observation(bytes.fromhex("488b0527030000c3"), data)

    def test_source_refuses_malformed_or_mutable_instructions(self):
        for instruction in (bytes.fromhex("488b0527030000"), bytes.fromhex("488b0527030000c390"),
                            bytes.fromhex("488b052703000090"), bytearray.fromhex("488b0527030000c3")):
            with self.subTest(instruction=instruction), self.assertRaisesRegex(ValueError, "source"):
                Anchor(0x195730000, 0x7000, 0x123, instruction, 0x800000000000)

    def test_module_metadata_requires_exact_bounded_integers(self):
        for base, span, offset, limit in ((True, 0x7000, 0x123, 0x800000000000),
                                          (0, 0x7000, 0x123, 0x800000000000),
                                          (0x195730000, 0, 0x123, 0x800000000000),
                                          (0x195730000, 0x7000, -1, 0x800000000000),
                                          (0x195730000, 0x7000, 0x123, 0x195736FFF),
                                          (0x195730000, 0x7000, 0x123, 2 ** 65),
                                          (0x195730000, 28672.0, 0x123, 0x800000000000)):
            with self.subTest(base=base, span=span, offset=offset, limit=limit), self.assertRaisesRegex(ValueError, "bounds"):
                Anchor(base, span, offset, bytes.fromhex("488b0527030000c3"), limit)

    def test_code_cannot_cross_the_declared_module_end(self):
        with self.assertRaisesRegex(ValueError, "bounds"):
            Anchor(0x195730000, 0x4B9, 0x4B2,
                   bytes.fromhex("488b0578fdffffc3"), 0x800000000000)

    def test_negative_displacement_cannot_leave_the_module(self):
        with self.assertRaisesRegex(ValueError, "bounds"):
            Anchor(0x195730000, 0x7000, 0x123,
                   bytes.fromhex("488b0500f0ffffc3"), 0x800000000000)

    def test_field_can_end_at_the_module_boundary(self):
        anchor = Anchor(0x195730000, 0x459, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        self.assertEqual(anchor.slot(bytes.fromhex("488b0527030000c3")),
                         {"address": 0x195730451, "size": 8})

    def test_slot_refuses_mutable_observed_code(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        with self.assertRaisesRegex(ValueError, "getter"):
            anchor.slot(bytearray.fromhex("488b0527030000c3"))

    def test_observation_checks_the_getter_before_the_field(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        with self.assertRaisesRegex(ValueError, "getter"):
            anchor.observation(bytes.fromhex("488b0528030000c3"), None)

    def test_zero_word_does_not_establish_a_manager(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        self.assertEqual(anchor.observation(bytes.fromhex("488b0527030000c3"), b"\0" * 8)["state"], "zero")

    def test_in_domain_word_remains_only_an_observation(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        self.assertEqual(anchor.observation(bytes.fromhex("488b0527030000c3"),
                                            bytes.fromhex("9f78563412000000"))["state"], "in_domain")

    def test_word_at_the_domain_end_is_outside(self):
        anchor = Anchor(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x800000000000)
        self.assertEqual(anchor.observation(bytes.fromhex("488b0527030000c3"),
                                            bytes.fromhex("0000000000800000"))["state"], "outside_domain")
