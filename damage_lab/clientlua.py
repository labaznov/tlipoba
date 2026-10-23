"""Bounded, data-only XLUA11 diagnostic grammar derived from the pinned class metadata.

This inspects bytes; it does not execute Java or game instructions. Limits are
our diagnostic subset, not claims about every file admitted by the archived tool.
"""

import math
import struct
import time


LABELS = ('LOADNIL', 'MUL', 'SETTABLE', 'LE', 'NEWTABLE', 'LOADKX', 'LOADK', 'POW',
          'GETTABLE', 'TESTSET', 'LT', 'EQ', 'MOVE', 'VARARG', 'GETUPVAL', 'LOADBOOL',
          'IDIV', 'DIV', 'GETTABUP', 'SETTABUP', 'BOR', 'RETURN', 'ADD', 'CONCAT', 'CALL',
          'TFORLOOP', 'CLOSURE', 'FORPREP', 'SETLIST', 'TAILCALL', 'FORLOOP', 'BAND',
          'SETUPVAL', 'BXOR', 'JMP', 'MOD', 'NOT', 'SELF', 'BNOT', 'UNM', 'SHR',
          'TFORCALL', 'TEST', 'LEN', 'SUB', 'SHL', 'EXTRAARG')


class Cursor:
    """A byte cursor enforces finite framing and aggregate diagnostic work limits."""

    def __init__(self, data):
        self.data = memoryview(data).cast('B')
        if self.data.nbytes > 65536:
            raise ValueError('XLUA payload exceeds the diagnostic byte cap')
        self.position = 0
        self.functions = 0
        self.instructions = 0
        self.deadline = time.monotonic() + 2

    def span(self, size):
        if time.monotonic() > self.deadline:
            raise ValueError('XLUA diagnostic exceeded the soft processing deadline')
        end = self.position + size
        if size < 0 or end > len(self.data):
            raise ValueError('XLUA field exceeds the captured byte boundary')
        value = self.data[self.position:end].tobytes()
        self.position = end
        return value

    def byte(self):
        return self.span(1)[0]

    def integer(self):
        return struct.unpack('<i', self.span(4))[0]

    def count(self):
        value = self.integer()
        if not 0 <= value <= 16384:
            raise ValueError('XLUA list count exceeds the diagnostic range')
        return value

    def string(self):
        length = self.byte()
        if length == 255:
            length = self.integer()
        if length:
            length -= 10
        if not 0 <= length <= 65536:
            raise ValueError('XLUA string length exceeds the diagnostic range')
        return self.span(length)

    def constant(self):
        tag = self.byte()
        if tag == 0:
            return {'tag': tag, 'value': None}
        if tag == 1:
            value = self.byte()
            if value not in (0, 1):
                raise ValueError('XLUA boolean constant has an unadmitted byte')
            return {'tag': tag, 'value': bool(value)}
        if tag in (3, 19):
            raw = self.span(8)
            value = struct.unpack('<d' if tag == 3 else '<q', raw)[0]
            if tag == 3 and not math.isfinite(value):
                raise ValueError('XLUA nonfinite constant is outside the diagnostic subset')
            return {'tag': tag, 'value': value, 'bits': raw.hex()}
        if tag in (4, 20):
            return {'tag': tag, 'value': self.string()}
        raise ValueError('XLUA constant tag is outside the source-derived grammar')

    def code(self):
        count = self.count()
        self.instructions += count
        if self.instructions > 16384:
            raise ValueError('XLUA aggregate instructions exceed the diagnostic cap')
        values = []
        for index in range(count):
            word = struct.unpack('<I', self.span(4))[0]
            opcode = word >> 26
            if opcode >= len(LABELS):
                raise ValueError('XLUA opcode is outside the archived label map')
            values.append({'pc': index, 'word': word, 'opcode': opcode, 'label': LABELS[opcode],
                           'A': word & 255, 'C': (word >> 8) & 511, 'B': (word >> 17) & 511,
                           'Bx': (word >> 8) & 262143, 'sBx': ((word >> 8) & 262143) - 131071})
        return values

    def function(self, depth):
        self.functions += 1
        if depth > 16 or self.functions > 256:
            raise ValueError('XLUA function tree exceeds the diagnostic cap')
        result = {'source': self.string(), 'lineBegin': self.integer(), 'lineEnd': self.integer(),
                  'parameters': self.byte(), 'vararg': self.byte(), 'stack': self.byte()}
        result['code'] = self.code()
        result['constants'] = [self.constant() for index in range(self.count())]
        result['upvalues'] = []
        for index in range(self.count()):
            raw, slot = self.byte(), self.byte()
            result['upvalues'].append({'instack': bool(raw), 'raw': raw, 'index': slot})
        result['functions'] = [self.function(depth + 1) for index in range(self.count())]
        result['lines'] = [self.integer() for index in range(self.count())]
        result['locals'] = [{'name': self.string(), 'start': self.integer(), 'end': self.integer()}
                            for index in range(self.count())]
        count = self.count()
        if count > len(result['upvalues']):
            raise ValueError('XLUA upvalue name count exceeds its records')
        result['upvalueNames'] = [self.string() for index in range(count)]
        return result


def decode(data):
    cursor = Cursor(data)
    if cursor.span(9) != b'\1XDI\x11\r\n\x1a\n':
        raise ValueError('XLUA fixed signature differs from the source-derived grammar')
    upvalues = cursor.byte()
    function = cursor.function(0)
    if upvalues != len(function['upvalues']):
        raise ValueError('XLUA main upvalue counts differ')
    if cursor.position != len(cursor.data):
        raise ValueError('XLUA payload contains unclassified trailing bytes')
    return {'format': 'xlua11-diagnostic', 'function': function,
            'functions': cursor.functions, 'instructions': cursor.instructions,
            'bytes': cursor.position, 'executed': False}
