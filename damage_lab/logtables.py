"""Strict parser of the ASCII table dumps found in an ordinary saved UE_game.log (offline, pure).

Grammar (docs/research/passive-log-import.md): one header line
`[<log time>][<frame>]TLNetGame: Display: [Game]`, then body lines `PREFIX SEGMENT+ [" [" RAW "]"]`
where each line is one leaf path, `+KEY` children start right after their parent's key, `|` marks
every ancestor column and `+<k>+...` closes a table after exactly 30 table-valued entries.

The text is untrusted data: nothing is evaluated, recursion is avoided, every size is bounded and
diagnostics are fixed codes plus a line index, never the input text. Scalars keep their exact
lexical text with an inferred class; no ServerSource or native-stat types are inferred. A parsed
event that is structurally complete is not a complete or current build: freshness, the selected
skill and code identity stay unknown, and events are never merged.
"""
from __future__ import annotations

import re

FORMAT = 'tli-log-table-v0'
VERSION = '0.2.0'
TABLE_ENTRY_LIMIT = 30          # measured dumper rule: a table is cut after this many table-valued entries
LIMITS = {'max_lines': 20000, 'max_line_length': 512, 'max_depth': 32, 'max_nodes': 200000}
HEADER = re.compile(r'\[([0-9]{4}\.[0-9]{2}\.[0-9]{2}-[0-9]{2}\.[0-9]{2}\.[0-9]{2}:[0-9]{3})\]\[ *([0-9]{1,10})\]'
                    r'TLNetGame: Display: \[Game\]', re.ASCII)
SEGMENTS = re.compile(r'([ |]*)((?:\+(?:[A-Za-z0-9]+|\.\.\.))+)')
VALUE = re.compile(r' \[([^\[\]]*)\]')
KEY = re.compile(r'\+([A-Za-z0-9]+|\.\.\.)')
INT = re.compile(r'-?(?:0|[1-9][0-9]*)')
FLOAT = re.compile(r'-?[0-9]+\.[0-9]+')
MEANING = 'structural completeness of the printed tree only; not import completeness, freshness or identity'


class LogTableError(ValueError):
    """A grammar or limit violation; carries a fixed code and the line index, never the line text."""

    def __init__(self, code, line):
        super().__init__(f'log table error {code} at line {line}')
        self.code, self.line = code, line


def _lines(lines):
    if not isinstance(lines, (list, tuple)) or not all(isinstance(line, str) for line in lines):
        raise LogTableError('input', 0)
    return lines


def _class(text):
    if text in ('true', 'false'):
        return 'bool'
    if INT.fullmatch(text):
        return 'int'
    if FLOAT.fullmatch(text):
        return 'float'
    return 'text'


def _header(line):
    """The header match of a printable-ASCII line, or None (Unicode digits never count as digits)."""
    if any(not ' ' <= ch <= '~' for ch in line):
        return None
    return HEADER.fullmatch(line)


def _check_text(line, index, max_length):
    if len(line) > max_length:
        raise LogTableError('limit', index)
    if '\t' in line or '\r' in line or line.endswith(' '):
        raise LogTableError('whitespace', index)
    if any(not ' ' <= ch <= '~' for ch in line):
        raise LogTableError('non_ascii', index)
    if line.startswith('['):
        raise LogTableError('interleaved', index)


def _split_line(line, index):
    match = SEGMENTS.match(line)
    if not match:
        raise LogTableError('segment', index)
    rest = line[match.end():]
    if rest and not rest.startswith(' ['):
        raise LogTableError('segment', index)
    value = None
    if rest:
        found = VALUE.fullmatch(rest)
        if not found:
            raise LogTableError('value', index)
        value = found.group(1)
    keys = KEY.findall(match.group(2))
    if '...' in keys and (keys.index('...') != len(keys) - 1 or len(keys) < 2 or value is not None):
        raise LogTableError('elision', index)
    return len(match.group(1)), keys, value


def _render(root):
    """Lines of the tree in the dump grammar (iterative)."""
    out, current = [], ''
    stack = [(root['entries'], 0, 0, ())]
    while stack:
        entries, i, col, bars = stack.pop()
        if i >= len(entries):
            continue
        key, node = entries[i]
        stack.append((entries, i + 1, col, bars))
        if i:
            current = ''.join('|' if c in bars else ' ' for c in range(col))
        segment = '+' + key
        if node['t'] == 'table':
            current += segment
            stack.append((node['entries'], 0, col + len(segment), bars + (col,)))
        elif node['t'] == 'scalar':
            out.append(f'{current}{segment} [{node["text"]}]')
        elif node['t'] == 'empty':
            out.append(current + segment)
        else:
            out.append(current + segment + '+...')
    return out


def parse_event(lines, *, max_lines=LIMITS['max_lines'], max_line_length=LIMITS['max_line_length'],
                max_depth=LIMITS['max_depth'], max_nodes=LIMITS['max_nodes']):
    """One event (header line + body lines) -> detached tagged tree with header text, counts and elisions."""
    for limit in (max_lines, max_line_length, max_depth, max_nodes):
        if type(limit) is not int or limit < 1:
            raise ValueError('limits must be positive integers')
    lines = _lines(lines)
    if len(lines) > max_lines:
        raise LogTableError('limit', max_lines)
    if not lines:
        raise LogTableError('empty', 0)
    if len(lines[0]) > max_line_length:
        raise LogTableError('limit', 0)
    header = _header(lines[0])
    if not header:
        raise LogTableError('header', 0)
    if len(lines) == 1:
        raise LogTableError('empty', 0)
    root = {'t': 'table', 'entries': []}
    # Frames: child column, node, depth, path, kind; a closed table id set marks elided tables.
    stack = [(0, root, 0, (), 'table')]
    keys_of, tables_of = {id(root): set()}, {id(root): 0}     # keys and table-valued entry count per table
    closed, elisions = set(), []
    nodes = empty_tables = max_seen = 0
    scalars = {'bool': 0, 'int': 0, 'float': 0, 'text': 0}
    for index in range(1, len(lines)):
        line = lines[index]
        _check_text(line, index, max_line_length)
        column, keys, value = _split_line(line, index)
        while stack[-1][0] > column:
            stack.pop()
        child_column, parent, depth, path, kind = stack[-1]
        if child_column != column:
            raise LogTableError('parent', index)
        if kind == 'scalar':
            raise LogTableError('child_of_scalar', index)
        if kind != 'table':
            raise LogTableError('parent', index)
        if id(parent) in closed:
            raise LogTableError('elision', index)
        segment_column = column
        names = [key for key in keys if key != '...']
        elided = keys[-1] == '...'
        for position, key in enumerate(names):
            if key in keys_of[id(parent)]:
                raise LogTableError('duplicate_key', index)
            depth += 1
            nodes += 1
            if depth > max_depth or nodes > max_nodes:
                raise LogTableError('limit', index)
            max_seen = max(max_seen, depth)
            last = position == len(names) - 1
            if not last:
                node, node_kind = {'t': 'table', 'entries': []}, 'table'
            elif elided:
                node, node_kind = {'t': 'elided'}, 'elided'
            elif value is not None:
                node, node_kind = {'t': 'scalar', 'text': value, 'class': _class(value)}, 'scalar'
                scalars[node['class']] += 1
            else:
                node, node_kind = {'t': 'empty'}, 'empty'
                empty_tables += 1
            printed = tables_of[id(parent)]
            if node_kind in ('table', 'empty') and printed >= TABLE_ENTRY_LIMIT:
                # The measured dumper never prints a 31st table-valued entry: such a table is outside the grammar.
                raise LogTableError('elision', index)
            if node_kind == 'elided':
                if printed != TABLE_ENTRY_LIMIT:
                    raise LogTableError('elision', index)
                elisions.append({'path': list(path), 'printedTableEntries': printed})
                closed.add(id(parent))
            keys_of[id(parent)].add(key)
            tables_of[id(parent)] += node_kind in ('table', 'empty')
            parent['entries'].append([key, node])
            child_column = segment_column + 1 + len(key)
            path = path + (key,)
            if node_kind == 'table':
                keys_of[id(node)], tables_of[id(node)] = set(), 0
            stack.append((child_column, node, depth, path, node_kind))
            segment_column, parent = child_column, node
    rendered = _render(root)
    body = list(lines[1:])
    for offset, (got, want) in enumerate(zip(rendered, body)):
        if got != want:
            raise LogTableError('render_mismatch', offset + 1)
    if len(rendered) != len(body):
        raise LogTableError('render_mismatch', min(len(rendered), len(body)) + 1)
    return {'format': FORMAT, 'version': VERSION,
            'header': {'logTimeText': header.group(1), 'frame': int(header.group(2)), 'timezone': 'unknown'},
            'root': root, 'status': 'elided' if elisions else 'complete', 'meaning': MEANING, 'elisions': elisions,
            'counts': {'lines': len(body), 'leaves': len(body), 'emptyTables': empty_tables, 'elisions': len(elisions),
                       'nodes': nodes, 'maxDepth': max_seen, 'scalars': scalars}}


def split_events(lines, *, max_lines=10_000_000):
    """Half-open (start, end) index spans: a header line plus every following line not starting with '['."""
    if type(max_lines) is not int or max_lines < 1:
        raise ValueError('max_lines must be a positive integer')
    lines = _lines(lines)
    if len(lines) > max_lines:
        raise LogTableError('limit', max_lines)
    spans, index = [], 0
    while index < len(lines):
        if _header(lines[index]):
            end = index + 1
            while end < len(lines) and not lines[end].startswith('['):
                end += 1
            spans.append((index, end))
            index = end
        else:
            index += 1
    return spans
