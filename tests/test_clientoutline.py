import struct
import unittest
from unittest.mock import patch

from damage_lab.clientlua import decode
from damage_lab.clientoutline import outline


def string(value):
    return ((bytes([len(value) + 10]) if len(value) < 245
             else b'\xff' + struct.pack('<i', len(value) + 10)) + value)


def function(source, code, constants, upvalues, children, lines, locals, names):
    return (string(source) + struct.pack('<iiBBB', 13, 29, 2, 0, 9)
            + struct.pack('<i', len(code)) + b''.join(struct.pack('<I', word) for word in code)
            + struct.pack('<i', len(constants)) + b''.join(constants)
            + struct.pack('<i', len(upvalues)) + b''.join(upvalues)
            + struct.pack('<i', len(children)) + b''.join(children)
            + struct.pack('<i', len(lines)) + b''.join(struct.pack('<i', line) for line in lines)
            + struct.pack('<i', len(locals))
            + b''.join(string(name) + struct.pack('<ii', begin, end) for name, begin, end in locals)
            + struct.pack('<i', len(names)) + b''.join(string(name) for name in names))


def program(body, upvalues):
    return b'\1XDI\x11\r\n\x1a\n' + bytes([upvalues]) + body


class HiddenLength(bytearray):
    """A buffer exposes storage that its Python length deliberately conceals."""

    def __len__(self):
        return 0


class Clock:
    """A finite clock supplies deterministic processing-deadline observations."""

    def __init__(self, values):
        self.values = iter(values)

    def monotonic(self):
        return next(self.values, 3)


class ClientOutlineTest(unittest.TestCase):
    """Synthetic byte streams define the bounded function index and its refusals."""

    def test_function_spans_and_code_offsets_use_original_byte_positions(self):
        children = [function(name, [], [], [], [], [], [], []) for name in (b'a', b'bc')]
        result = outline(program(function(b'', [(21 << 26) | (1 << 17)], [], [], children,
                                          [], [], []), 0))
        self.assertEqual([(row['path'], row['begin'], row['end'], row['codeOffset'], row['codeCount'])
                          for row in result['index']],
                         [('main', 10, 137, 26, 1), ('main.0', 42, 83, 59, 0),
                          ('main.1', 83, 125, 101, 0)])

    def test_constants_and_function_metadata_preserve_exact_data(self):
        body = function(b'@fictional', [], [b'\0', b'\1\1', b'\3' + struct.pack('<d', 8.75),
                        b'\x13' + struct.pack('<q', -37), b'\4' + string(b'a\0z'),
                        b'\x14' + string(b'\xc3\xa9')], [b'\3\7'], [], [17, 23],
                        [(b'local', 0, 99)], [b'capture'])
        result = outline(program(body, 1))
        self.assertEqual((result['format'], result['version'], result['executed'],
                          result['index'][0]),
                         ('xlua11-outline', '0.1.0', False,
                          {'path': 'main', 'begin': 10, 'end': len(program(body, 1)),
                           'source': b'@fictional', 'lineBegin': 13, 'lineEnd': 29,
                           'parameters': 2, 'vararg': 0, 'stack': 9, 'codeOffset': 36,
                           'codeCount': 0, 'constants': [
                               {'tag': 0, 'value': None}, {'tag': 1, 'value': True},
                               {'tag': 3, 'value': 8.75, 'bits': '0000000000802140'},
                               {'tag': 19, 'value': -37, 'bits': 'dbffffffffffffff'},
                               {'tag': 4, 'value': b'a\0z'}, {'tag': 20, 'value': b'\xc3\xa9'}],
                           'upvalues': [{'instack': True, 'raw': 3, 'index': 7}],
                           'children': [], 'debugLines': 2, 'debugLocals': 1,
                           'upvalueNames': [b'capture']}))

    def test_cannot_admit_a_list_count_outside_the_fixed_range(self):
        body = function(b'', [], [], [], [], [], [], [])
        for count in (-7, 65537):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'list count'):
                outline(program(body[:12] + struct.pack('<i', count) + body[16:], 0))

    def test_cannot_exceed_the_aggregate_instruction_cap(self):
        children = [function(b'', [0] * count, [], [], [], [], [], []) for count in (65536, 1)]
        with self.assertRaisesRegex(ValueError, 'aggregate instructions'):
            outline(program(function(b'', [0] * 65536, [], [], children, [], [], []), 0))

    def test_cannot_skip_an_unadmitted_opcode_in_a_nested_body(self):
        child = function(b'', [47 << 26], [], [], [], [], [], [])
        with self.assertRaisesRegex(ValueError, 'opcode'):
            outline(program(function(b'', [], [], [], [child], [], [], []), 0))

    def test_cannot_exceed_the_combined_constant_and_upvalue_record_cap(self):
        children = [function(b'', [], [], [b'\0\7'] * 65536, [], [], [], []),
                    function(b'', [], [b'\0'], [], [], [], [], [])]
        with self.assertRaisesRegex(ValueError, 'retained records'):
            outline(program(function(b'', [], [b'\0'] * 65536, [], children, [], [], []), 0))

    def test_cannot_exceed_the_function_count_cap(self):
        child = function(b'', [], [], [], [], [], [], [])
        with self.assertRaisesRegex(ValueError, 'function tree'):
            outline(program(function(b'', [], [], [], [child] * 2048, [], [], []), 0))

    def test_cannot_exceed_the_function_depth_cap(self):
        body = function(b'', [], [], [], [], [], [], [])
        for index in range(17):
            body = function(b'', [], [], [], [body], [], [], [])
        with self.assertRaisesRegex(ValueError, 'function tree'):
            outline(program(body, 0))

    def test_cannot_hide_storage_beyond_the_two_mebibyte_cap(self):
        with self.assertRaisesRegex(ValueError, 'byte cap'):
            outline(HiddenLength(b'\0' * 2097153))

    def test_cannot_admit_an_unsupported_or_noncontiguous_buffer(self):
        for value in ('fictional', memoryview(b'irregular' * 7)[::2]):
            with self.subTest(value=type(value).__name__), self.assertRaisesRegex(ValueError, 'buffer'):
                outline(value)

    def test_cannot_retain_a_string_beyond_the_per_string_cap(self):
        with self.assertRaisesRegex(ValueError, 'string length'):
            outline(program(function(b'x' * 65537, [], [], [], [], [], [], []), 0))

    def test_cannot_accept_a_negative_reduced_string_length(self):
        body = function(b'', [], [], [], [], [], [], [])
        with self.assertRaisesRegex(ValueError, 'string length'):
            outline(program(b'\x09' + body[1:], 0))

    def test_cannot_continue_after_the_soft_processing_deadline(self):
        with patch('damage_lab.clientoutline.time', Clock([0, 3]), create=True):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                outline(program(function(b'', [], [], [], [], [], [], []), 0))

    def test_more_than_256_tiny_functions_are_indexed(self):
        child = function(b'fictional', [], [], [], [], [], [], [])
        result = outline(program(function(b'', [], [], [], [child] * 293, [], [], []), 0))
        self.assertEqual((result['functions'], result['index'][-1]['path']), (294, 'main.292'))

    def test_exactly_2048_functions_are_admitted(self):
        child = function(b'', [], [], [], [], [], [], [])
        self.assertEqual(outline(program(function(b'', [], [], [], [child] * 2047,
                                                 [], [], []), 0))['functions'], 2048)

    def test_an_explicit_function_budget_admits_2049_functions(self):
        child = function(b'', [], [], [], [], [], [], [])
        result = outline(program(function(b'', [], [], [], [child] * 2048, [], [], []), 0),
                         functions=4096)
        self.assertEqual(result['functions'], 2049)

    def test_cannot_request_an_unadmitted_function_budget(self):
        data = program(function(b'', [], [], [], [], [], [], []), 0)
        for value in (0, -7, True, False, 1.5, '4096', None, 8193):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^XLUA outline function budget'):
                outline(data, functions=value)

    def test_the_upper_function_budget_is_admitted_without_extra_functions(self):
        self.assertEqual(outline(program(function(b'', [], [], [], [], [], [], []), 0),
                                 functions=8192)['functions'], 1)

    def test_the_minimum_function_budget_admits_one_function(self):
        self.assertEqual(outline(program(function(b'', [], [], [], [], [], [], []), 0),
                                 functions=1)['functions'], 1)

    def test_the_function_budget_is_keyword_only(self):
        with self.assertRaises(TypeError):
            outline(program(function(b'', [], [], [], [], [], [], []), 0), 4096)

    def test_a_larger_function_budget_keeps_the_input_storage_cap(self):
        with self.assertRaisesRegex(ValueError, 'byte cap'):
            outline(HiddenLength(b'\0' * 2097153), functions=8192)

    def test_function_budget_refusal_precedes_input_admission(self):
        with self.assertRaisesRegex(ValueError, '^XLUA outline function budget'):
            outline(None, functions=False)

    def test_function_depth_16_is_admitted(self):
        body = function(b'', [], [], [], [], [], [], [])
        for index in range(16):
            body = function(b'', [], [], [], [body], [], [], [])
        self.assertEqual(outline(program(body, 0))['index'][-1]['path'], 'main' + '.0' * 16)

    def test_a_valid_input_larger_than_512_kib_doesnot_need_expanded_instructions(self):
        constants = [b'\4' + string(b'x' * 60001)] * 9
        result = outline(program(function(b'', [], constants, [], [], [], [], []), 0))
        self.assertEqual((result['bytes'], len(result['index'][0]['constants']),
                          'code' in result['index'][0]), (540113, 9, False))

    def test_the_exact_two_mebibyte_storage_boundary_is_admitted(self):
        constants = [b'\4' + string(b'x' * 65536)] * 31 + [b'\4' + string(b'y' * 65294)]
        self.assertEqual(outline(program(function(b'', [], constants, [], [], [], [], []),
                                         0))['bytes'], 2097152)

    def test_the_exact_aggregate_instruction_boundary_is_admitted(self):
        child = function(b'', [0] * 65536, [], [], [], [], [], [])
        self.assertEqual(outline(program(function(b'', [0] * 65536, [], [], [child],
                                                 [], [], []), 0))['instructions'], 131072)

    def test_the_exact_retained_record_boundary_is_admitted(self):
        child = function(b'', [], [], [b'\0\7'] * 65536, [], [], [], [])
        result = outline(program(function(b'', [], [b'\0'] * 65536, [], [child], [], [], []), 0))
        self.assertEqual((len(result['index'][0]['constants']), len(result['index'][1]['upvalues'])),
                         (65536, 65536))

    def test_retained_record_refusal_precedes_reading_an_excess_constant(self):
        children = [function(b'', [], [], [b'\0\7'] * 65536, [], [], [], []),
                    function(b'', [], [b'\0'], [], [], [], [], [])[:20]]
        with self.assertRaisesRegex(ValueError, 'retained records'):
            outline(program(function(b'', [], [b'\0'] * 65536, [], children, [], [], []), 0))

    def test_the_exact_per_string_boundary_is_admitted(self):
        self.assertEqual(len(outline(program(function(b'z' * 65536, [], [], [], [], [], [], []),
                                             0))['index'][0]['source']), 65536)

    def test_cannot_hide_an_oversized_string_in_discarded_debug_data(self):
        with self.assertRaisesRegex(ValueError, 'string length'):
            outline(program(function(b'', [], [], [], [], [], [(b'z' * 65537, 0, 1)], []), 0))

    def test_a_zero_encoded_string_doesnot_consume_a_terminator(self):
        body = function(b'', [], [], [], [], [], [], [])
        self.assertEqual(outline(program(b'\0' + body[1:], 0))['index'][0]['source'], b'')

    def test_cannot_accept_a_truncated_extended_string(self):
        with self.assertRaisesRegex(ValueError, 'input boundary'):
            outline(program(b'\xff' + struct.pack('<i', 19) + b'abc', 0))

    def test_cannot_accept_an_unknown_constant_tag(self):
        with self.assertRaisesRegex(ValueError, 'constant tag'):
            outline(program(function(b'', [], [b'\2'], [], [], [], [], []), 0))

    def test_cannot_accept_an_unadmitted_boolean_constant(self):
        with self.assertRaisesRegex(ValueError, 'boolean constant'):
            outline(program(function(b'', [], [b'\1\7'], [], [], [], [], []), 0))

    def test_cannot_accept_a_nonfinite_constant(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'nonfinite'):
                outline(program(function(b'', [], [b'\3' + struct.pack('<d', value)], [],
                                         [], [], [], []), 0))

    def test_negative_zero_keeps_its_numeric_bits(self):
        result = outline(program(function(b'', [], [b'\3' + bytes.fromhex('0000000000000080')],
                                          [], [], [], [], []), 0))
        self.assertEqual(result['index'][0]['constants'][0]['bits'], '0000000000000080')

    def test_cannot_skip_truncated_debug_line_data(self):
        body = function(b'', [], [], [], [], [], [], [])
        with self.assertRaisesRegex(ValueError, 'input boundary'):
            outline(program(body[:28] + struct.pack('<ii', 3, 17), 0))

    def test_cannot_skip_truncated_local_boundaries(self):
        body = function(b'', [], [], [], [], [], [], [])
        with self.assertRaisesRegex(ValueError, 'input boundary'):
            outline(program(body[:32] + struct.pack('<i', 1) + string(b'local') + b'\0', 0))

    def test_cannot_name_an_upvalue_without_a_record(self):
        with self.assertRaisesRegex(ValueError, 'upvalue name count'):
            outline(program(function(b'', [], [], [], [], [], [], [b'orphan']), 0))

    def test_upvalue_names_can_be_a_strict_subset_of_records(self):
        result = outline(program(function(b'', [], [], [b'\0\7', b'\x03\x09'], [], [], [], [b'first']), 2))
        self.assertEqual(result['index'][0]['upvalueNames'], [b'first'])

    def test_cannot_accept_a_mismatched_main_upvalue_count(self):
        with self.assertRaisesRegex(ValueError, 'main upvalue counts'):
            outline(program(function(b'', [], [], [b'\0\7'], [], [], [], []), 0))

    def test_cannot_accept_trailing_bytes(self):
        with self.assertRaisesRegex(ValueError, 'trailing'):
            outline(program(function(b'', [], [], [], [], [], [], []), 0) + b'private-looking')

    def test_cannot_accept_an_unadmitted_signature(self):
        with self.assertRaisesRegex(ValueError, 'signature'):
            outline(b'\2XDI\x11\r\n\x1a\n' + b'\0' * 41)

    def test_a_contiguous_multibyte_view_uses_its_byte_storage(self):
        data = program(function(b'ab', [], [], [], [], [], [], []), 0)
        self.assertEqual(outline(memoryview(data).cast('I'))['bytes'], 52)

    def test_returned_strings_are_detached_from_a_mutable_input(self):
        data = bytearray(program(function(b'abc', [], [], [], [], [], [], []), 0))
        result = outline(data)
        data[11] = 120
        self.assertEqual(result['index'][0]['source'], b'abc')

    def test_every_archived_opcode_is_admitted_without_claiming_vm_validation(self):
        self.assertEqual(outline(program(function(b'', [index << 26 for index in range(47)],
                                                 [], [], [], [], [], []), 0))['instructions'], 47)

    def test_a_late_final_checkpoint_doesnot_return_an_index(self):
        with patch('damage_lab.clientoutline.time', Clock([0] * 19 + [3])):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                outline(program(function(b'', [], [], [], [], [], [], []), 0))

    def test_instruction_validation_observes_the_shared_deadline(self):
        with patch('damage_lab.clientoutline.time', Clock([0] * 23 + [3])):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                outline(program(function(b'', [0] * 53, [], [], [], [], [], []), 0))

    def test_a_small_outline_agrees_with_the_existing_diagnostic_grammar(self):
        data = program(function(b'fictional', [0], [b'\x13' + struct.pack('<q', 137)],
                                [b'\3\7'], [], [17, 23], [(b'local', 0, 71)], [b'capture']), 1)
        reference, result = decode(data), outline(data)
        self.assertEqual((result['functions'], result['instructions'],
                          result['index'][0]['source'], result['index'][0]['constants'],
                          result['index'][0]['upvalues'], result['index'][0]['upvalueNames']),
                         (reference['functions'], reference['instructions'],
                          reference['function']['source'], reference['function']['constants'],
                          reference['function']['upvalues'], reference['function']['upvalueNames']))
