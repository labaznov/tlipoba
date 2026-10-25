"""Check the externally bound CppWFloat payload interpretation."""

import math
import unittest

from damage_lab.cppwfloat import decode


class CppWFloatTest(unittest.TestCase):
    """Verify raw payload values without assigning player or combat semantics."""

    def test_a_known_little_endian_payload_retains_its_fraction(self):
        self.assertEqual(decode(bytes.fromhex('0000000000c02a40')), 13.375)

    def test_a_payload_with_the_wrong_width_has_a_fixed_error(self):
        for data in (b'', b'\x13' * 7, b'\x13' * 9):
            with self.subTest(width=len(data)), self.assertRaisesRegex(
                    ValueError, '^CppWFloat decoding requires exactly eight bytes$'):
                decode(data)

    def test_negative_zero_retains_its_sign(self):
        self.assertEqual(math.copysign(1.0, decode(bytes.fromhex('0000000000000080'))), -1.0)

    def test_a_negative_finite_payload_retains_its_value(self):
        self.assertEqual(decode(bytes.fromhex('0000000000c02ac0')), -13.375)

    def test_the_smallest_positive_subnormal_is_not_filtered(self):
        self.assertEqual(decode(bytes.fromhex('0100000000000000')), 5e-324)

    def test_the_largest_finite_payload_is_not_scaled(self):
        self.assertEqual(decode(bytes.fromhex('ffffffffffffef7f')), 1.7976931348623157e308)

    def test_positive_infinity_is_retained(self):
        self.assertEqual(decode(bytes.fromhex('000000000000f07f')), math.inf)

    def test_negative_infinity_is_retained(self):
        self.assertEqual(decode(bytes.fromhex('000000000000f0ff')), -math.inf)

    def test_a_quiet_nan_payload_is_not_filtered(self):
        self.assertTrue(math.isnan(decode(bytes.fromhex('230100000000f87f'))))

    def test_only_builtin_bytes_can_enter_the_payload_decoder(self):
        class Payload(bytes):
            """Represent a nonbuiltin bytes input for strict boundary checks."""

        for data in (bytearray(8), memoryview(b'\x00' * 8), Payload(8), None, 'PRIVATE!', 17, True):
            with self.subTest(kind=type(data).__name__), self.assertRaisesRegex(
                    ValueError, '^CppWFloat decoding requires exactly eight bytes$'):
                decode(data)
