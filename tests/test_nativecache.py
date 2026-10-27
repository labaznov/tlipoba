import unittest

from damage_lab.nativecache import Header


class NativeCacheTests(unittest.TestCase):
    """Check bounded candidate-header plans using synthetic source bytes."""

    def test_code_request_preserves_the_existing_anchor_plan(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        self.assertEqual(header.code(), {"address": 0x195730123, "size": 8})

    def test_guard_request_uses_the_exact_source_interval(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        self.assertEqual(header.guard(), {"address": 0x195730617, "size": 3})

    def test_slot_requires_the_matching_stored_function(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        with self.assertRaisesRegex(ValueError, "guard"):
            header.slot(bytes.fromhex("488b0527030000c3"), b"\x39\x73\xc3")

    def test_slot_preserves_the_signed_anchor_displacement(self):
        header = Header(0x195730000, 0x7000, 0x4B2,
                        bytes.fromhex("488b0578fdffffc3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        self.assertEqual(header.slot(bytes.fromhex("488b0578fdffffc3"), b"\x39\x72\xc3"),
                         {"address": 0x195730231, "size": 8})

    def test_header_requests_only_the_sixteen_byte_candidate_interval(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        self.assertEqual(header.header(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                       (0x2619230).to_bytes(8, "little")),
                         {"address": 0x2619358, "size": 16})

    def test_header_checks_the_guard_before_interpreting_a_candidate(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        with self.assertRaisesRegex(ValueError, "guard"):
            header.header(bytes.fromhex("488b0527030000c3"), b"\x39\x73\xc3", b"")

    def test_header_refuses_a_null_candidate(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        with self.assertRaisesRegex(ValueError, "candidate"):
            header.header(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3", bytes(8))

    def test_header_can_end_exactly_at_the_address_limit(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        self.assertEqual(header.header(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                       (0x800000000000 - 0x138).to_bytes(8, "little")),
                         {"address": 0x800000000000 - 16, "size": 16})

    def test_header_cannot_cross_the_address_limit(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        with self.assertRaisesRegex(ValueError, "candidate"):
            header.header(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                          (0x800000000000 - 0x137).to_bytes(8, "little"))

    def test_guard_source_requires_immutable_bounded_nonempty_bytes(self):
        for body in (b"", b"\x13" * 1025, bytearray(b"\x17")):
            with self.subTest(body=type(body).__name__), self.assertRaisesRegex(ValueError, "guard"):
                Header(0x195730000, 0x7000, 0x123,
                       bytes.fromhex("488b0527030000c3"), 0x617, body, 0x800000000000)

    def test_guard_interval_requires_an_exact_integer_inside_the_module(self):
        for offset in (True, -1, 0.0, 0x6FFE):
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "guard"):
                Header(0x195730000, 0x7000, 0x123,
                       bytes.fromhex("488b0527030000c3"), offset, b"\x39\x72\xc3", 0x800000000000)

    def test_observation_preserves_reserved_bytes_and_source_shaped_candidates(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        observed = header.observation(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                      (0x2619230).to_bytes(8, "little"),
                                      bytes.fromhex("0123456789abcdef7591b3d7a5030000"))
        self.assertEqual((observed["bucket_candidate_hex"], observed["count_candidate"],
                          observed["reserved_hex"], observed["header_hex"]),
                         ("0xefcdab8967452301", 933, "7591b3d7", "0123456789abcdef7591b3d7a5030000"))

    def test_observation_keeps_all_identity_and_readiness_claims_false(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        self.assertEqual(header.observation(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                            (0x2619230).to_bytes(8, "little"), bytes(16))["claims"],
                         {"module_identity": False, "manager_identity": False, "actor_identity": False,
                          "selected_build": False, "currentness": False, "atomicity": False,
                          "dps": False, "cache_layout": False, "model_readiness": False})

    def test_observation_requires_exactly_sixteen_immutable_header_bytes(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        for data in (bytes(15), bytes(17), bytearray(16)):
            with self.subTest(data=type(data).__name__), self.assertRaisesRegex(ValueError, "header"):
                header.observation(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                   (0x2619230).to_bytes(8, "little"), data)

    def test_slot_cannot_accept_a_different_getter_with_a_matching_guard(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        with self.assertRaisesRegex(ValueError, "getter"):
            header.slot(bytes.fromhex("488b0528030000c3"), b"\x39\x72\xc3")

    def test_slot_cannot_accept_a_mutable_matching_guard(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        with self.assertRaisesRegex(ValueError, "guard"):
            header.slot(bytes.fromhex("488b0527030000c3"), bytearray(b"\x39\x72\xc3"))

    def test_header_requires_exactly_eight_immutable_candidate_bytes(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        for word in (bytes(7), bytes(9), bytearray(8)):
            with self.subTest(word=type(word).__name__), self.assertRaisesRegex(ValueError, "field"):
                header.header(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3", word)

    def test_guard_can_use_the_full_budget_and_end_at_the_module_boundary(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x6C00, b"\x39" * 1024, 0x800000000000)
        self.assertEqual(header.guard(), {"address": 0x195736C00, "size": 1024})

    def test_header_arithmetic_can_end_at_the_exclusive_uint64_boundary(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 2 ** 64)
        self.assertEqual(header.header(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                       (2 ** 64 - 0x138).to_bytes(8, "little")),
                         {"address": 2 ** 64 - 16, "size": 16})

    def test_observation_preserves_a_large_count_without_claiming_a_valid_cache(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        self.assertEqual(header.observation(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                            (0x2619230).to_bytes(8, "little"),
                                            bytes(12) + b"\xff" * 4)["count_candidate"], 2 ** 32 - 1)

    def test_anchor_domain_validation_is_preserved_by_composition(self):
        with self.assertRaisesRegex(ValueError, "bounds"):
            Header(0x195730000, 0x7000, 0x123,
                   bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", True)

    def test_observation_distinguishes_stored_code_equality_from_owner_identity(self):
        header = Header(0x195730000, 0x7000, 0x123,
                        bytes.fromhex("488b0527030000c3"), 0x617, b"\x39\x72\xc3", 0x800000000000)
        observed = header.observation(bytes.fromhex("488b0527030000c3"), b"\x39\x72\xc3",
                                      (0x2619230).to_bytes(8, "little"), bytes(16))
        self.assertEqual((observed["stored_function_source_match"],
                          "Stored-function code equality does not show that the candidate uses that function"
                          in observed["limitations"]), (True, True))
