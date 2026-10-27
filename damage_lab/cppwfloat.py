"""Interpret externally bound CppWFloat payload bits without field, player or unit proof."""

import struct


def decode(data):
    """Read binary64 bits only after external binding establishes the input payload."""
    if type(data) is not bytes or len(data) != 8:
        raise ValueError('CppWFloat decoding requires exactly eight bytes')
    return struct.unpack('<d', data)[0]
