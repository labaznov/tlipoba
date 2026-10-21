"""Offline harvester for the stat-panel dump the game writes to UE_game.log.

Each time the attribute panel opens, the client logs pairs of lines:
  ...RoleAttrMgr@Attri.Id  <name>  <id>
  ...RoleAttrMgr@[1] = <value>, [2] = <value>
A header binds only to the next panel line, and only within the same frame and
second. Every other log line is counted and dropped. Parsing does not tie a cohort
to a build code, character or account.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

FORMAT = 'tli-panel-log-v1'
VERSION = '0.2.0'
CHUNK = 1 << 16
MARKER = 'RoleAttrMgr@'
LINE = re.compile(r'^\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]\[\s*(\d+)\]'
                  r'TLLua: Display: \[Game\] RoleAttrMgr@(.*)$')
HEADER = re.compile(r'^Attri\.Id\s+(.+?)\s+(\d+)\s*$')
VALUES = re.compile(r'^\[\d+\] = [^,]*(?:, \[\d+\] = [^,]*)*$')
ITEM = re.compile(r'\[(\d+)\] = ([^,]*)')
NUMBER = re.compile(r'-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
WINDOW = timedelta(seconds=1)
GAPS = ['Cohorts are not bound to a build code, character or account by parsing; identity is unverified.',
        'Panel lines carry no benchmark DPS, hit, cast or buff events.',
        'Attribute names are as logged; ids are not mapped to other id spaces (native attrInfo, catalogs).']


def numbers(tokens):
    """Finite int/float values for decimal tokens; None with a reason otherwise."""
    result = []
    for token in tokens:
        if not NUMBER.fullmatch(token):
            return None, f'unparseable value {token!r}'
        try:
            value = int(token) if re.fullmatch(r'-?\d+', token) else float(token)
            if not math.isfinite(value):
                return None, 'non-finite numeric value'
            if value == 0 and Decimal(token) != 0:
                return None, 'numeric value is below supported range'
        except (OverflowError, ValueError):
            return None, 'numeric value exceeds supported range'
        result.append(value)
    return result, None


def entries(records):
    for index, record in enumerate(records, 1):
        if isinstance(record, str):
            yield index, record
        elif (isinstance(record, dict) and type(record.get('line')) is int and record['line'] >= 1
              and isinstance(record.get('text'), str)):
            yield record['line'], record['text']
        else:
            raise ValueError(f'Record {index} is not a log line or a {{line, text}} object.')


def harvest(records):
    """Group panel header/value pairs into cohorts; see the module docstring for the rules."""
    cohorts, rejected = [], []
    stats = {'lines': 0, 'panelLines': 0, 'ignoredLines': 0}
    current, pending = None, None

    def add(cohort, row):
        same = [other for other in cohort['attributes'] if other['id'] == row['id']]
        cohort['attributes'].append(row)
        if same:
            for other in same + [row]:
                other.update(status='unresolved', values=None, issue='duplicate attribute id in cohort')
            cohort['issues'].append(f'Attribute {row["id"]} appears more than once.')

    def unresolved(header, issue, line_numbers):
        add(header['cohort'], {'id': header['id'], 'name': header['name'], 'status': 'unresolved', 'values': None,
                               'raw_values': [], 'line_numbers': line_numbers, 'issue': issue})

    for number, text in entries(records):
        stats['lines'] += 1
        if MARKER not in text:
            stats['ignoredLines'] += 1
            continue
        match = LINE.match(text)
        if match is None:
            if pending is not None:
                unresolved(pending, 'unrecognized intervening panel line', [pending['line']])
                pending = None
            rejected.append({'line': number, 'reason': 'unrecognized panel line'})
            continue
        stats['panelLines'] += 1
        *clock, frame, body = match.groups()
        year, month, day, hour, minute, second, milli = map(int, clock)
        moment = datetime(year, month, day, hour, minute, second, milli * 1000, tzinfo=timezone.utc)
        frame = int(frame)
        if HEADER.match(body):
            if pending is not None:
                unresolved(pending, 'missing values', [pending['line']])
            if (current is None or current['frame'] != frame or moment < current['last']
                    or moment - current['last'] > WINDOW):
                current = {'timestamp': moment.strftime('%Y-%m-%dT%H:%M:%S.') + f'{milli:03d}Z', 'frame': frame,
                           'last': moment, 'attributes': [], 'issues': []}
                cohorts.append(current)
            current['last'] = max(current['last'], moment)
            name, stat = HEADER.match(body).groups()
            pending = {'id': stat, 'name': name, 'line': number, 'frame': frame, 'moment': moment, 'cohort': current}
        elif VALUES.match(body):
            if pending is None:
                rejected.append({'line': number, 'reason': 'values without header'})
                continue
            if (frame != pending['frame'] or moment < pending['moment']
                    or moment - pending['moment'] > WINDOW):
                unresolved(pending, f'frame or timestamp mismatch with values line {number}', [pending['line']])
                rejected.append({'line': number, 'reason': 'values frame or timestamp mismatch'})
                pending = None
                continue
            items = ITEM.findall(body)
            raw = [token.strip() for _, token in items]
            row = {'id': pending['id'], 'name': pending['name'], 'status': 'resolved', 'values': None,
                   'raw_values': raw, 'line_numbers': [pending['line'], number]}
            if [int(index) for index, _ in items] != list(range(1, len(items) + 1)):
                row.update(status='unresolved', issue='value index order is not 1..n')
            else:
                parsed, issue = numbers(raw)
                if issue:
                    row.update(status='unresolved', issue=issue)
                else:
                    row['values'] = parsed
            add(pending['cohort'], row)
            pending['cohort']['last'] = max(pending['cohort']['last'], moment)
            pending = None
        else:
            if pending is not None:
                unresolved(pending, 'unrecognized intervening panel line', [pending['line']])
                pending = None
            rejected.append({'line': number, 'reason': 'unrecognized panel line'})
    if pending is not None:
        unresolved(pending, 'missing values', [pending['line']])
    for cohort in cohorts:
        del cohort['last']
        cohort['attributeCount'] = len(cohort['attributes'])
        cohort['status'] = ('resolved' if not cohort['issues']
                            and all(row['status'] == 'resolved' for row in cohort['attributes']) else 'partial')
    return {'format': FORMAT, 'tool': 'tlipoba/panellog', 'version': VERSION,
            'source': {'sha256': None, 'kind': 'records', **stats},
            'identity': {'status': 'unverified', 'reason': GAPS[0]},
            'cohorts': cohorts, 'rejected': rejected, 'gaps': list(GAPS)}


def read(path, digest, meta):
    """Yield the lines of one snapshot: the bytes present when the file was opened.

    A log the game keeps appending to is read only up to its size at open. The digest
    covers exactly the bytes read. A final line without a newline at the boundary may
    be cut mid-token, so it is reported in meta['incompleteFinalLine'] and not parsed.
    Text logs yield lines; .jsonl files yield {line, text} records.
    """
    jsonl = path.suffix.lower() in ('.jsonl', '.json')
    with open(path, 'rb') as handle:
        size = os.fstat(handle.fileno()).st_size
        meta.update(snapshotBytes=size, bytesRead=0, incompleteFinalLine=None)
        remaining, carry, number = size, b'', 0
        while remaining:
            block = handle.read(min(CHUNK, remaining))
            if not block:
                raise ValueError(f'Source shrank during read: {size - remaining} of {size} snapshot bytes were available.')
            remaining -= len(block)
            digest.update(block)
            meta['bytesRead'] += len(block)
            *complete, carry = (carry + block).split(b'\n')
            for raw in complete:
                number += 1
                text = raw.decode('utf-8', 'replace').rstrip('\r')
                if not jsonl:
                    yield text
                elif text.strip():
                    try:
                        yield json.loads(text)
                    except json.JSONDecodeError as error:
                        raise ValueError(f'Line {number} is not JSON: {error.msg}.') from None
        if os.fstat(handle.fileno()).st_size < size:
            raise ValueError(f'Source shrank during read below its {size}-byte snapshot.')
        if carry:
            meta['incompleteFinalLine'] = {'line': number + 1, 'bytes': len(carry)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Harvest stat-panel dumps from a saved UE_game.log or filtered JSONL.')
    parser.add_argument('source', type=Path, help='saved log text, or .jsonl with {line, text} records')
    parser.add_argument('output', type=Path, help='new JSON file; an existing file is never replaced')
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f'Refusing to overwrite {args.output}', file=sys.stderr)
        return 2
    digest, meta = hashlib.sha256(), {}
    try:
        result = harvest(read(args.source, digest, meta))
        result['source'].update(sha256=digest.hexdigest(), **meta,
                                kind='jsonl' if args.source.suffix.lower() in ('.jsonl', '.json') else 'log')
        if meta['incompleteFinalLine']:
            result['gaps'].append(f'Final line {meta["incompleteFinalLine"]["line"]} was unterminated at the '
                                  'snapshot boundary and was not parsed.')
        text = json.dumps(result, ensure_ascii=False, indent=1, allow_nan=False)
    except (OSError, ValueError) as error:
        print(f'panellog: {str(error).rstrip(chr(46))}', file=sys.stderr)
        return 1
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'x', encoding='utf-8') as handle:
            handle.write(text)
    except FileExistsError:
        print(f'Refusing to overwrite {args.output}', file=sys.stderr)
        return 2
    except OSError as error:
        print(f'panellog: {str(error).rstrip(chr(46))}', file=sys.stderr)
        return 1
    print(f'{len(result["cohorts"])} cohorts, {len(result["rejected"])} rejected lines -> {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
