"""Inspect XLUA11 function framing as data without executing instructions."""

import math
import struct
import time

from .clientlua import LABELS


class _Cursor:
    """A byte cursor records nested function spans without expanding instructions."""

    def __init__(self, data, functions):
        if type(functions) is not int or not 1 <= functions <= 8192:
            raise ValueError('XLUA outline function budget must be an integer from 1 to 8192')
        self.functions = functions
        try:
            self.data = memoryview(data).cast('B')
        except (TypeError, ValueError):
            raise ValueError('XLUA outline requires a contiguous byte-addressable buffer') from None
        if self.data.nbytes > 2097152:
            raise ValueError('XLUA outline input exceeds the diagnostic byte cap')
        self.position = 0
        self.index = []
        self.instructions = 0
        self.records = 0
        self.strings = 0
        self.deadline = time.monotonic() + 2

    def checkpoint(self):
        if time.monotonic() > self.deadline:
            raise ValueError('XLUA outline exceeded the soft processing deadline')

    def span(self, size):
        self.checkpoint()
        end = self.position + size
        if size < 0 or end > self.data.nbytes:
            raise ValueError('XLUA outline field exceeds the input boundary')
        value = self.data[self.position:end]
        self.position = end
        return value

    def byte(self):
        return self.span(1)[0]

    def integer(self):
        return struct.unpack('<i', self.span(4))[0]

    def count(self):
        value = self.integer()
        if not 0 <= value <= 65536:
            raise ValueError('XLUA outline list count exceeds the diagnostic range')
        return value

    def retention(self):
        count = self.count()
        self.records += count
        if self.records > 131072:
            raise ValueError('XLUA outline retained records exceed the diagnostic cap')
        return count

    def string(self, retained=True):
        length = self.byte()
        if length == 255:
            length = self.integer()
        if length:
            length -= 10
        if not 0 <= length <= 65536:
            raise ValueError('XLUA outline string length exceeds the diagnostic range')
        if retained:
            self.strings += length
            if self.strings > 2097152:
                raise ValueError('XLUA outline retained strings exceed the diagnostic cap')
            return self.span(length).tobytes()
        self.span(length)

    def constant(self):
        tag = self.byte()
        if tag == 0:
            return {'tag': tag, 'value': None}
        if tag == 1:
            value = self.byte()
            if value not in (0, 1):
                raise ValueError('XLUA outline boolean constant has an unadmitted byte')
            return {'tag': tag, 'value': bool(value)}
        if tag in (3, 19):
            raw = self.span(8).tobytes()
            value = struct.unpack('<d' if tag == 3 else '<q', raw)[0]
            if tag == 3 and not math.isfinite(value):
                raise ValueError('XLUA outline nonfinite constant is outside the diagnostic subset')
            return {'tag': tag, 'value': value, 'bits': raw.hex()}
        if tag in (4, 20):
            return {'tag': tag, 'value': self.string()}
        raise ValueError('XLUA outline constant tag is outside the diagnostic grammar')

    def function(self, path, depth):
        if depth > 16 or len(self.index) >= self.functions:
            raise ValueError('XLUA outline function tree exceeds the diagnostic cap')
        row = {'path': path, 'begin': self.position, 'source': self.string(),
               'lineBegin': self.integer(), 'lineEnd': self.integer(),
               'parameters': self.byte(), 'vararg': self.byte(), 'stack': self.byte()}
        self.index.append(row)
        count = self.count()
        row['codeOffset'], row['codeCount'] = self.position, count
        self.instructions += count
        if self.instructions > 131072:
            raise ValueError('XLUA outline aggregate instructions exceed the diagnostic cap')
        for word, in struct.iter_unpack('<I', self.span(count * 4)):
            self.checkpoint()
            if word >> 26 >= len(LABELS):
                raise ValueError('XLUA outline opcode is outside the archived label map')
        row['constants'] = [self.constant() for index in range(self.retention())]
        row['upvalues'] = []
        for index in range(self.retention()):
            raw, slot = self.byte(), self.byte()
            row['upvalues'].append({'instack': bool(raw), 'raw': raw, 'index': slot})
        row['children'] = []
        for index in range(self.count()):
            child = f'{path}.{index}'
            row['children'].append(child)
            self.function(child, depth + 1)
        row['debugLines'] = self.count()
        self.span(row['debugLines'] * 4)
        row['debugLocals'] = self.count()
        for index in range(row['debugLocals']):
            self.string(retained=False)
            self.span(8)
        count = self.count()
        if count > len(row['upvalues']):
            raise ValueError('XLUA outline upvalue name count exceeds its records')
        row['upvalueNames'] = [self.string() for index in range(count)]
        row['end'] = self.position


def outline(data, *, functions=2048):
    """Return original byte spans and retained data for a diagnostic function tree."""
    cursor = _Cursor(data, functions)
    if cursor.span(9) != b'\1XDI\x11\r\n\x1a\n':
        raise ValueError('XLUA outline signature differs from the diagnostic grammar')
    upvalues = cursor.byte()
    cursor.function('main', 0)
    if upvalues != len(cursor.index[0]['upvalues']):
        raise ValueError('XLUA outline main upvalue counts differ')
    if cursor.position != cursor.data.nbytes:
        raise ValueError('XLUA outline input contains trailing bytes')
    result = {'format': 'xlua11-outline', 'version': '0.1.0', 'bytes': cursor.position,
              'functions': len(cursor.index), 'instructions': cursor.instructions,
              'executed': False, 'index': cursor.index}
    cursor.checkpoint()
    return result
