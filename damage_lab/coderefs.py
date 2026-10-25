"""Find bounded lexical x64 address-reference shapes without native proof.

Patterns do not establish instruction boundaries, address-size prefixes, control
flow, class registration, ownership, types or storage.
"""

import re


SHAPE = re.compile(rb'(?=[\x48-\x4f]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d].{4})', re.DOTALL)


def candidates(data, *, section_rva, target_rva, max_bytes=96 * 1024 ** 2, max_matches=32):
    """Return byte-pattern candidates; boundaries and native registration remain unknown."""
    if (type(data) is not bytes
            or any(type(value) is not int for value in (section_rva, target_rva, max_bytes, max_matches))
            or not 1 <= max_bytes <= 96 * 1024 ** 2 or not 1 <= max_matches <= 64
            or not 0 <= section_rva < 2 ** 32 or not 0 <= target_rva < 2 ** 32
            or len(data) > max_bytes or section_rva + len(data) > 2 ** 32):
        raise ValueError('Code reference candidates require bounded bytes and unsigned RVA inputs')
    matches, complete = [], True
    for match in SHAPE.finditer(data):
        offset = match.start()
        if section_rva + offset + 7 + int.from_bytes(data[offset + 3:offset + 7], 'little', signed=True) == target_rva:
            if len(matches) == max_matches:
                complete = False
                break
            matches.append({'offset': offset, 'rva': section_rva + offset, 'instruction_boundary': 'unknown'})
    return {'format': 'tli-code-reference-candidates-v1', 'kind': 'rexw_lea_rip_shape',
            'source_bytes': len(data), 'section_rva': section_rva, 'target_rva': target_rva,
            'matches': matches, 'scan_complete': complete, 'possibly_capped': not complete,
            'registration_proven': False, 'owner_proven': False}
