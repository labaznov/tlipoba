"""Check bounded lexical code-reference candidates with synthetic bytes."""

import unittest

from damage_lab.coderefs import candidates


class CodeReferencesTest(unittest.TestCase):
    """Keep byte-pattern observations separate from instruction and owner proof."""

    def test_positive_displacement_keeps_only_an_exact_target_candidate(self):
        self.assertEqual(
            candidates(b'\x90\x48\x8d\x0d\x19\x00\x00\x00', section_rva=71, target_rva=104),
            {'format': 'tli-code-reference-candidates-v1', 'kind': 'rexw_lea_rip_shape',
             'source_bytes': 8, 'section_rva': 71, 'target_rva': 104,
             'matches': [{'offset': 1, 'rva': 72, 'instruction_boundary': 'unknown'}],
             'scan_complete': True, 'possibly_capped': False,
             'registration_proven': False, 'owner_proven': False})

    def test_negative_displacement_points_before_the_candidate(self):
        self.assertEqual(
            candidates(b'\x4f\x8d\x3d\xea\xff\xff\xff', section_rva=311, target_rva=296)['matches'],
            [{'offset': 0, 'rva': 311, 'instruction_boundary': 'unknown'}])

    def test_candidate_limit_stops_at_the_first_additional_exact_match(self):
        result = candidates(b'\x48\x8d\x05\x07\x00\x00\x00\x4c\x8d\x15\x00\x00\x00\x00',
                            section_rva=53, target_rva=67, max_matches=1)
        self.assertEqual((result['matches'], result['scan_complete'], result['possibly_capped']),
                         ([{'offset': 0, 'rva': 53, 'instruction_boundary': 'unknown'}], False, True))

    def test_oversized_bytes_cannot_bypass_a_reduced_input_limit(self):
        with self.assertRaisesRegex(ValueError, '^Code reference candidates require bounded bytes and unsigned RVA inputs$'):
            candidates(b'\x00' * 19, section_rva=37, target_rva=41, max_bytes=18)

    def test_boolean_and_malformed_options_cannot_satisfy_the_input_contract(self):
        for options in ({'data': bytearray()}, {'data': None}, {'data': 'PRIVATE'},
                        {'section_rva': True}, {'target_rva': False}, {'max_bytes': True},
                        {'max_matches': False}, {'section_rva': -1}, {'section_rva': 2 ** 32},
                        {'target_rva': -3}, {'target_rva': 2 ** 32}, {'max_bytes': 0},
                        {'max_bytes': 96 * 1024 ** 2 + 1}, {'max_matches': 0}, {'max_matches': 65},
                        {'section_rva': 1.2}, {'target_rva': '4'}, {'max_bytes': None}, {'max_matches': '5'}):
            with self.subTest(options=options), self.assertRaisesRegex(
                    ValueError, '^Code reference candidates require bounded bytes and unsigned RVA inputs$'):
                candidates(**({'data': b'', 'section_rva': 17, 'target_rva': 31} | options))

    def test_a_section_span_cannot_overflow_the_unsigned_rva_space(self):
        with self.assertRaisesRegex(ValueError, '^Code reference candidates require bounded bytes and unsigned RVA inputs$'):
            candidates(b'\x00\x00', section_rva=2 ** 32 - 1, target_rva=47)

    def test_overlapping_shapes_remain_separate_unproved_candidates(self):
        self.assertEqual(
            candidates(b'\x48\x8d\x05\x48\x8d\x05\x45\x8d\x05\x45',
                       section_rva=71, target_rva=0x45058D96)['matches'],
            [{'offset': 0, 'rva': 71, 'instruction_boundary': 'unknown'},
             {'offset': 3, 'rva': 74, 'instruction_boundary': 'unknown'}])

    def test_a_wrong_target_does_not_become_a_candidate(self):
        self.assertEqual(candidates(b'\x48\x8d\x05\x19\x00\x00\x00', section_rva=72, target_rva=103)['matches'], [])

    def test_nonmatching_encodings_and_truncated_tails_are_not_candidates(self):
        for data in (b'\x40\x8d\x05\x19\x00\x00\x00', b'\x48\x8b\x05\x19\x00\x00\x00',
                     b'\x48\x8d\x04\x19\x00\x00\x00', b'\x48\x8d\x45\x19\x00\x00\x00',
                     b'\x48\x8d\x85\x19\x00\x00\x00', b'\x48\x8d\xc5\x19\x00\x00\x00',
                     b'\x48\x8d\x05\x19\x00\x00'):
            with self.subTest(data=data):
                self.assertEqual(candidates(data, section_rva=72, target_rva=104)['matches'], [])

    def test_address_size_prefixes_do_not_claim_instruction_boundaries(self):
        result = candidates(b'\x67\x48\x8d\x05\x19\x00\x00\x00', section_rva=71, target_rva=104)
        self.assertEqual((result['matches'], result['registration_proven'], result['owner_proven']),
                         ([{'offset': 1, 'rva': 72, 'instruction_boundary': 'unknown'}], False, False))

    def test_an_embedded_shape_does_not_claim_an_instruction_boundary(self):
        self.assertEqual(
            candidates(b'\xb8\x32\x48\x8d\x05\x19\x00\x00\x00', section_rva=70, target_rva=104)['matches'],
            [{'offset': 2, 'rva': 72, 'instruction_boundary': 'unknown'}])

    def test_the_exact_candidate_limit_is_complete_if_no_overflow_exists(self):
        result = candidates(b'\x48\x8d\x05\x19\x00\x00\x00\x90', section_rva=72, target_rva=104, max_matches=1)
        self.assertEqual((len(result['matches']), result['scan_complete'], result['possibly_capped']), (1, True, False))

    def test_empty_bytes_are_valid_at_the_highest_unsigned_rva(self):
        result = candidates(b'', section_rva=2 ** 32 - 1, target_rva=0, max_bytes=1, max_matches=64)
        self.assertEqual((result['source_bytes'], result['matches'], result['scan_complete'], result['possibly_capped']),
                         (0, [], True, False))

    def test_a_single_byte_can_end_at_the_unsigned_rva_boundary(self):
        self.assertEqual(candidates(b'\x90', section_rva=2 ** 32 - 1, target_rva=0, max_bytes=1)['matches'], [])

    def test_all_declared_rex_and_register_encodings_use_the_same_shape(self):
        for rex in range(0x48, 0x50):
            for register in range(8):
                with self.subTest(rex=rex, register=register):
                    self.assertEqual(
                        candidates(bytes((rex, 0x8d, register * 8 + 5, 25, 0, 0, 0)),
                                   section_rva=72, target_rva=104)['matches'],
                        [{'offset': 0, 'rva': 72, 'instruction_boundary': 'unknown'}])

    def test_displacement_bytes_can_include_a_line_feed(self):
        self.assertEqual(
            candidates(b'\x48\x8d\x05\x0a\x00\x00\x00', section_rva=19, target_rva=36)['matches'],
            [{'offset': 0, 'rva': 19, 'instruction_boundary': 'unknown'}])
