"""Collect one fixed ordinary-file extent without original-file or runtime proof."""

import hashlib
import os
from pathlib import Path
import stat


def collect(path, *, budget):
    """Return retained bytes and window-relative provenance without following appends."""
    if type(budget) is not int or not 1 <= budget <= 2 * 1024 ** 2:
        raise ValueError('Log window budget must be a positive integer up to 2 MiB')
    origin = Path(path).resolve()
    with origin.open('rb', buffering=0) as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError('Log window input must be a regular file')
        start = max(0, opened.st_size - budget)
        stream.seek(start)
        remaining, parts = opened.st_size - start, []
        while remaining:
            count = min(65536, remaining)
            block = stream.read(count)
            if len(block) != count:
                raise ValueError('Log window source ended before the fixed extent')
            parts.append(block)
            remaining -= count
    payload = b''.join(parts)
    discarded = (payload.find(b'\n') + 1 or len(payload)) if start else 0
    payload = payload[discarded:]
    return payload, {
        'format': 'tli-log-window-v1', 'origin_path': str(origin),
        'opened_bytes': opened.st_size, 'read_start': start, 'read_end': opened.st_size,
        'bytes_read': opened.st_size - start, 'discarded_leading_bytes': discarded,
        'payload_start': start + discarded, 'payload_bytes': len(payload),
        'payload_sha256': hashlib.sha256(payload).hexdigest(), 'original_sha256': None,
        'line_scope': 'retained_window', 'atomic': False, 'currentness': 'unknown'}
