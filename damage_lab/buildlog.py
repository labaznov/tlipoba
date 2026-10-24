"""Bounded offline snapshots of printed trees in an ordinary saved game log.

Only the caller's explicit path is opened. Parsed lexical trees stay private and
describe printed structure, never a complete build, native stats or runtime identity.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .logtables import HEADER, LIMITS as PARSER_LIMITS, LogTableError, parse_event

FORMAT = 'tli-build-log-v1'
VERSION = '0.1.3'
MESSAGE = re.compile(HEADER.pattern + r' ----Socket (Recv|Send)Message STT----([A-Za-z][A-Za-z0-9_]{0,63})----(?:SynId = [0-9]{1,10})?', re.ASCII)
LIMITS = {'max_source_bytes': 1 << 30, 'max_lines': 20_000_000,
          'max_line_bytes': 512, 'max_events': 512, 'max_event_lines': 20_000,
          'max_event_bytes': 16 << 20, 'max_retained_bytes': 32 << 20, 'chunk_bytes': 1 << 16}


class BuildLogError(ValueError):
    """A fixed snapshot failure code and physical line number without source text."""

    def __init__(self, code, line):
        super().__init__(f'build log error {code} at line {line}')
        self.code, self.line = code, line


def lines(handle, size, digest, limit, chunk):
    """Yield bounded prefixes while hashing every byte of the initial file extent."""
    remaining, number, length, prefix, last = size, 0, 0, bytearray(), None
    while remaining:
        block = handle.read(min(chunk, remaining))
        if not block:
            raise BuildLogError('source_shrank', number + 1)
        remaining -= len(block)
        digest.update(block)
        offset = 0
        while offset < len(block):
            end = block.find(b'\n', offset)
            stop = len(block) if end < 0 else end
            count = stop - offset
            if count:
                prefix.extend(block[offset:offset + min(count, max(0, limit + 1 - len(prefix)))])
                last = block[stop - 1]
                length += count
            if end < 0:
                break
            number += 1
            content = length - (last == 13)
            data = bytes(prefix[:content])
            yield number, data, content, length + 1, True
            length, prefix, last = 0, bytearray(), None
            offset = end + 1
    if length:
        yield number + 1, bytes(prefix), length, length, False


def snapshot(path: Path, *, max_source_bytes=LIMITS['max_source_bytes'],
             max_lines=LIMITS['max_lines'], max_line_bytes=LIMITS['max_line_bytes'],
             max_events=LIMITS['max_events'], max_event_lines=LIMITS['max_event_lines'],
             max_event_bytes=LIMITS['max_event_bytes'],
             max_retained_bytes=LIMITS['max_retained_bytes'], chunk_bytes=LIMITS['chunk_bytes']) -> dict:
    """Read one fixed-size file prefix and return independent diagnostic tree events."""
    limits = {'max_source_bytes': max_source_bytes, 'max_lines': max_lines,
              'max_line_bytes': max_line_bytes, 'max_events': max_events,
              'max_event_lines': max_event_lines, 'max_event_bytes': max_event_bytes,
              'max_retained_bytes': max_retained_bytes, 'chunk_bytes': chunk_bytes}
    if any(type(value) is not int or value < 1 for value in limits.values()):
        raise BuildLogError('limits', 0)
    try:
        path = Path(path)
        location = str(path.resolve())
    except (OSError, RuntimeError, TypeError, ValueError):
        raise BuildLogError('path', 0) from None
    digest, events, rejected, active = hashlib.sha256(), [], [], None
    previous = None
    source = {'kind': 'ordinary_log', 'path': location, 'lines': 0,
              'ignoredLines': 0, 'oversizedLines': 0, 'retainedEventBytes': 0,
              'incompleteFinalLine': None}

    def reject(code, line):
        if active.get('code') is None:
            active.update(code=code, line=line)
        active['lines'].clear()

    def finish(boundary):
        nonlocal active
        if active is None:
            return
        context = {'start_line': active['start_line'], 'end_line': active['end_line'],
                   'boundary': boundary, 'header_trailing_space': active['header_trailing_space']}
        if active.get('code') is not None:
            rejected.append({**context, 'code': active['code'], 'line': active['line']})
            active = None
            return
        try:
            tree = parse_event(active['lines'], max_lines=max_event_lines,
                               max_line_length=max_line_bytes,
                               max_depth=PARSER_LIMITS['max_depth'], max_nodes=PARSER_LIMITS['max_nodes'])
        except LogTableError as error:
            rejected.append({**context, 'code': f'grammar_{error.code}',
                             'line': active['start_line'] + error.line})
        else:
            if source['retainedEventBytes'] + active['bytes'] > max_retained_bytes:
                raise BuildLogError('retained_limit', active['start_line'])
            source['retainedEventBytes'] += active['bytes']
            events.append({**context, 'tree': tree, 'message': active['message']})
        active = None

    try:
        with path.open('rb') as handle:
            size = os.fstat(handle.fileno()).st_size
            if size > max_source_bytes:
                raise BuildLogError('source_limit', 0)
            source.update(snapshotBytes=size, bytesRead=size)
            for number, data, length, raw, complete in lines(handle, size, digest, max_line_bytes, chunk_bytes):
                source['lines'] = number
                if number > max_lines:
                    raise BuildLogError('line_limit', number)
                source['oversizedLines'] += length > max_line_bytes
                if not complete:
                    previous = None
                    source['incompleteFinalLine'] = {'line': number, 'bytes': raw}
                    if active is not None:
                        active['end_line'] = number
                        reject('incomplete_final_line', number)
                    continue
                if data.startswith(b'['):
                    finish('next_record')
                text = data.decode('ascii', 'replace')
                header = length <= max_line_bytes and HEADER.fullmatch(text)
                framing = False
                if not header and length <= max_line_bytes and text.endswith(' ') and HEADER.fullmatch(text[:-1]):
                    text, header, framing = text[:-1], HEADER.fullmatch(text[:-1]), True
                if header:
                    if len(events) + len(rejected) >= max_events:
                        raise BuildLogError('event_limit', number)
                    active = {'start_line': number, 'end_line': number, 'lines': [], 'bytes': 0,
                              'header_trailing_space': framing,
                              'message': previous if previous is not None
                              and previous['logTimeText'][:20] == header.group(1)[:20]
                              and previous['logTimeText'] <= header.group(1)
                              and previous['frame'] == int(header.group(2)) else None}
                marker = MESSAGE.fullmatch(text) if length <= max_line_bytes else None
                previous = ({'name': marker.group(4), 'direction': marker.group(3).lower(), 'line': number,
                             'logTimeText': marker.group(1), 'frame': int(marker.group(2))} if marker else None)
                if active is not None:
                    active['end_line'] = number
                    active['bytes'] += raw
                    if length > max_line_bytes:
                        reject('event_line_limit', number)
                    elif number - active['start_line'] + 1 > max_event_lines:
                        reject('event_lines_limit', number)
                    elif active['bytes'] > max_event_bytes:
                        reject('event_bytes_limit', number)
                    elif active.get('code') is None:
                        active['lines'].append(text)
                else:
                    source['ignoredLines'] += 1
            if os.fstat(handle.fileno()).st_size < size:
                raise BuildLogError('source_shrank', source['lines'])
    except OSError:
        raise BuildLogError('read', source['lines']) from None
    finish('snapshot_boundary')
    return {'format': FORMAT, 'version': VERSION, 'status': 'diagnostic',
            'scope': 'printed_tree_only', 'import_complete': False,
            'identity': 'unknown', 'runtime': 'unknown', 'freshness': 'unknown',
            'selected_skill': 'unknown', 'build_code': 'unknown', 'limits': limits,
            'source': {**source, 'sha256': digest.hexdigest()},
            'events': events, 'rejected': rejected}
