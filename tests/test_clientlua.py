import struct
import unittest

from damage_lab.clientlua import decode


def text(value):
    return bytes([len(value) + 10]) + value


def chunk(name, constants, upvalues, children):
    return (text(name) + struct.pack('<iiBBB', 13, 29, 2, 0, 9)
            + struct.pack('<iI', 1, (21 << 26) | (1 << 17))
            + struct.pack('<i', len(constants)) + b''.join(constants)
            + struct.pack('<i', len(upvalues)) + b''.join(upvalues)
            + struct.pack('<i', len(children)) + b''.join(children)
            + struct.pack('<ii', 1, 17)
            + struct.pack('<i', 1) + text(b'local') + struct.pack('<ii', 0, 1)
            + struct.pack('<i', len(upvalues)) + b''.join(text(b'capture') for row in upvalues))


def program(count, children):
    body = chunk(b'large', [], [], children)
    offset = len(text(b'large')) + 11
    return (body[:offset] + struct.pack('<i', count)
            + struct.pack('<I', (21 << 26) | (1 << 17)) * count + body[offset + 8:])


class HiddenLength(bytearray):
    """A buffer advertises a length smaller than its actual byte storage."""

    def __len__(self):
        return 0


class ClientLuaTest(unittest.TestCase):
    """The source-derived diagnostic grammar preserves data and refuses unadmitted framing."""

    def test_function_data_and_constants_are_preserved(self):
        body = chunk(b'@synthetic', [b'\0', b'\1\1', b'\3' + struct.pack('<d', 8.75),
                     b'\x13' + struct.pack('<q', -37), b'\4' + text(b'abc'),
                     b'\x14' + text(b'\xc3\xa9')], [b'\3\7'], [])
        result = decode(b'\1XDI\x11\r\n\x1a\n\1' + body)
        self.assertEqual((result['function']['source'], result['function']['parameters'],
                          [row['value'] for row in result['function']['constants']],
                          result['function']['upvalues'], result['function']['code'][0]['label']),
                         (b'@synthetic', 2, [None, True, 8.75, -37, b'abc', b'\xc3\xa9'],
                          [{'instack': True, 'raw': 3, 'index': 7}], 'RETURN'))

    def test_nested_function_data_is_preserved(self):
        result = decode(b'\1XDI\x11\r\n\x1a\n\0' +
                        chunk(b'root', [], [], [chunk(b'child', [], [], [])]))
        self.assertEqual(result['function']['functions'][0]['source'], b'child')

    def test_extended_string_data_is_preserved(self):
        value = b'irregular' * 31
        result = decode(b'\1XDI\x11\r\n\x1a\n\0' +
                        chunk(b'root', [b'\4\xff' + struct.pack('<i', len(value) + 10) + value], [], []))
        self.assertEqual(result['function']['constants'][0]['value'], value)

    def test_zero_string_length_does_not_consume_a_terminator(self):
        body = chunk(b'', [], [], [])
        self.assertEqual(decode(b'\1XDI\x11\r\n\x1a\n\0\0' + body[1:])['function']['source'], b'')

    def test_cannot_accept_trailing_bytes(self):
        with self.assertRaisesRegex(ValueError, 'trailing'):
            decode(b'\1XDI\x11\r\n\x1a\n\0' + chunk(b'x', [], [], []) + b'extra')

    def test_cannot_iterate_a_negative_list_count(self):
        body = chunk(b'', [], [], [])
        with self.assertRaisesRegex(ValueError, 'count'):
            decode(b'\1XDI\x11\r\n\x1a\n\0' + body[:12] + struct.pack('<i', -7) + body[16:])

    def test_cannot_accept_a_negative_reduced_string_length(self):
        body = chunk(b'', [], [], [])
        with self.assertRaisesRegex(ValueError, 'string length'):
            decode(b'\1XDI\x11\r\n\x1a\n\0\x09' + body[1:])

    def test_cannot_accept_a_wrong_main_upvalue_count(self):
        with self.assertRaisesRegex(ValueError, 'upvalue'):
            decode(b'\1XDI\x11\r\n\x1a\n\7' + chunk(b'x', [], [], []))

    def test_cannot_name_an_upvalue_without_a_record(self):
        body = chunk(b'orphan', [], [], [])
        with self.assertRaisesRegex(ValueError, 'upvalue name'):
            decode(b'\1XDI\x11\r\n\x1a\n\0' + body[:-4] + struct.pack('<i', 1) + text(b'missing'))

    def test_cannot_hide_an_oversized_buffer_behind_its_reported_length(self):
        body = chunk(b'root', [b'\4\xff' + struct.pack('<i', 65546) + b'x' * 65536], [], [])
        with self.assertRaisesRegex(ValueError, 'byte cap'):
            decode(HiddenLength(b'\1XDI\x11\r\n\x1a\n\0' + body))

    def test_an_explicit_larger_byte_budget_preserves_large_saved_data(self):
        value = b'irregular' * 7193
        body = chunk(b'root', [b'\4\xff' + struct.pack('<i', len(value) + 10) + value] * 6, [], [])
        result = decode(b'\1XDI\x11\r\n\x1a\n\0' + body, maximum=524288)
        self.assertEqual([row['value'] for row in result['function']['constants']], [value] * 6)

    def test_an_explicit_larger_record_budget_preserves_instruction_fields(self):
        result = decode(b'\1XDI\x11\r\n\x1a\n\0' + program(16993, []),
                        maximum=131072, limit=32768)
        self.assertEqual((result['instructions'], result['function']['code'][-1]['pc']), (16993, 16992))

    def test_a_larger_byte_budget_does_not_implicitly_raise_the_record_budget(self):
        with self.assertRaisesRegex(ValueError, 'list count'):
            decode(b'\1XDI\x11\r\n\x1a\n\0' + program(16993, []), maximum=131072)

    def test_the_explicit_record_budget_still_bounds_aggregate_instructions(self):
        body = program(1, [program(17001, []), program(17003, [])])
        with self.assertRaisesRegex(ValueError, 'aggregate instructions'):
            decode(b'\1XDI\x11\r\n\x1a\n\0' + body, maximum=262144, limit=32768)

    def test_cannot_request_an_unadmitted_byte_budget(self):
        refused = []
        for value in (0, 524289, True, 1.5, '524288'):
            try:
                decode(b'', maximum=value)
            except ValueError as error:
                if str(error).startswith('XLUA byte budget'):
                    refused.append(value)
        self.assertEqual(refused, [0, 524289, True, 1.5, '524288'])

    def test_cannot_request_an_unadmitted_record_budget(self):
        refused = []
        for value in (0, 32769, True, 2.5, '32768'):
            try:
                decode(b'', limit=value)
            except ValueError as error:
                if str(error).startswith('XLUA record budget'):
                    refused.append(value)
        self.assertEqual(refused, [0, 32769, True, 2.5, '32768'])
