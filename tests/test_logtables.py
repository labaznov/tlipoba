import unittest

from damage_lab.logtables import FORMAT, LogTableError, parse_event, split_events

HEADER = '[2000.01.01-00.00.00:000][  0]TLNetGame: Display: [Game]'
ELIDED = object()
MARK = 'PRIVATEMARKER77'


def render(entries, col=0, bars=()):
    """Test-side renderer of the grammar: the first piece continues the parent line."""
    pieces = []
    for index, (key, value) in enumerate(entries):
        segment = '+' + key
        if value is ELIDED:
            lines = [segment + '+...']
        elif value is None:
            lines = [segment]
        elif isinstance(value, str):
            lines = [f'{segment} [{value}]']
        else:
            inner = render(value, col + len(segment), bars + (col,))
            lines = [segment + inner[0]] + inner[1:]
        if index:
            lines[0] = ''.join('|' if c in bars else ' ' for c in range(col)) + lines[0]
        pieces.extend(lines)
    return pieces


def event(entries):
    return [HEADER] + render(entries)


F1 = [('alpha', [('list', [('1', [('id', '7'), ('rate', '1.5')]), ('2', [('id', '-8')])]),
                 ('flag', 'true'), ('name', 'Example text'), ('none', None)]),
      ('beta', [('x', '0')]), ('gamma', 'word')]


def tables(count, start=1):
    return [(str(i), [('n', str(i))]) for i in range(start, start + count)]


class ParseTest(unittest.TestCase):
    """Check supported printed trees and lexical values with synthetic data."""

    def test_f1_valid_minimum(self):
        lines = event(F1)
        result = parse_event(lines)
        self.assertEqual(result['format'], FORMAT)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['header'], {'logTimeText': '2000.01.01-00.00.00:000', 'frame': 0, 'timezone': 'unknown'})
        self.assertEqual(result['counts']['leaves'], len(lines) - 1)
        self.assertEqual(result['counts']['emptyTables'], 1)
        self.assertEqual(result['counts']['elisions'], 0)
        alpha = dict(result['root']['entries'])['alpha']
        first = dict(dict(dict(alpha['entries'])['list']['entries'])['1']['entries'])
        self.assertEqual(first['id'], {'t': 'scalar', 'text': '7', 'class': 'int'})
        self.assertEqual(first['rate'], {'t': 'scalar', 'text': '1.5', 'class': 'float'})
        self.assertEqual(dict(alpha['entries'])['flag']['class'], 'bool')
        self.assertEqual(dict(alpha['entries'])['name']['class'], 'text')
        self.assertEqual(dict(alpha['entries'])['none'], {'t': 'empty'})
        second = dict(dict(alpha['entries'])['list']['entries'])['2']
        self.assertEqual(dict(second['entries'])['id']['text'], '-8')
        self.assertEqual([key for key, _ in result['root']['entries']], ['alpha', 'beta', 'gamma'])

    def test_f2_per_table_elision_and_scalars_without_cap(self):
        many = [(str(i), str(i)) for i in range(1, 41)]
        result = parse_event(event([('big', tables(30) + [('31', ELIDED)]), ('many', many)]))
        self.assertEqual(result['status'], 'elided')
        self.assertEqual(result['elisions'], [{'path': ['big'], 'printedTableEntries': 30}])
        self.assertEqual(len(dict(result['root']['entries'])['many']['entries']), 40)

    def test_f3_root_elision(self):
        result = parse_event(event(tables(30) + [('scalar', '1'), ('next', ELIDED)]))
        self.assertEqual(result['elisions'], [{'path': [], 'printedTableEntries': 30}])
        self.assertEqual(result['root']['entries'][-1], ['next', {'t': 'elided'}])

    def test_f4_lexical_retention_and_ambiguity(self):
        result = parse_event(event([('a', '123456789012345678'), ('b', '-9223372036854775808'), ('BaseId', '100'),
                                    ('t', 'true'), ('lead', '007'), ('exp', '1e5'), ('neg0', '-0'), ('blank', '')]))
        values = {key: node for key, node in result['root']['entries']}
        self.assertEqual((values['a']['text'], values['a']['class']), ('123456789012345678', 'int'))
        self.assertEqual((values['b']['text'], values['b']['class']), ('-9223372036854775808', 'int'))
        self.assertEqual(values['BaseId'], {'t': 'scalar', 'text': '100', 'class': 'int'})
        self.assertEqual(values['t']['class'], 'bool')
        self.assertEqual((values['lead']['class'], values['exp']['class'], values['neg0']['class'], values['blank']['class']),
                         ('text', 'text', 'int', 'text'))

    def test_marker_needs_exactly_thirty_table_entries(self):
        for count in (29, 31):
            with self.subTest(count=count), self.assertRaises(LogTableError) as caught:
                parse_event(event([('big', tables(count) + [(str(count + 1), ELIDED)])]))
            self.assertEqual(caught.exception.code, 'elision')

    def test_uncapped_table_without_marker_is_unsupported(self):
        # The measured dumper cuts a table after 30 table-valued entries; a 31st printed one is outside the grammar.
        for name, entries in (('nested', [('big', tables(31))]), ('root', tables(31)),
                              ('nested with empty tables', [('big', tables(29) + [('e1', None), ('e2', None)])]),
                              ('root with an empty table', tables(30) + [('e', None)])):
            with self.subTest(name):
                with self.assertRaises(LogTableError) as caught:
                    parse_event(event(entries))
                self.assertEqual(caught.exception.code, 'elision')
        # Up to 30 table-valued entries without a marker are accepted, as printed structure only.
        many = [(f's{i}', str(i)) for i in range(1, 41)]
        for name, entries in (('nested 30', [('big', tables(30))]), ('root 30', tables(30)),
                              ('29 tables and an empty table', [('big', tables(29) + [('e', None)])]),
                              ('40 scalars', [('many', many)]), ('30 tables and 40 scalars at the root', tables(30) + many)):
            with self.subTest(name):
                result = parse_event(event(entries))
                self.assertEqual((result['status'], result['counts']['elisions']), ('complete', 0))

    def test_header_digits_must_be_ascii(self):
        arabic = '[٢٠٠٠.٠١.٠١-٠٠.٠٠.٠٠:٠٠٠][  ٠]TLNetGame: Display: [Game]'
        for name, header in (('arabic-indic digits', arabic), ('arabic frame', HEADER.replace('[  0]', '[  ٠]')),
                             ('fullwidth year', HEADER.replace('2000', '２０００'))):
            with self.subTest(name):
                lines = [header] + render(F1)
                with self.assertRaises(LogTableError) as caught:
                    parse_event(lines)
                self.assertEqual((caught.exception.code, caught.exception.line), ('header', 0))
                self.assertEqual(split_events(lines), [])
        self.assertEqual(split_events(event(F1)), [(0, len(event(F1)))])


def malformed():
    base = event(F1)
    cases = {}
    cases['header'] = (['[2000.01.01-00.00.00:000][  0]TLOther: Display: [Game]'] + base[1:], 'header')
    removed = list(base)
    removed[2] = ' ' + removed[2][1:]                      # remove the bar under 'alpha'
    cases['bar removed'] = (removed, 'render_mismatch')
    shifted = list(base)
    shifted[2] = shifted[2][:6] + ' ' + shifted[2][6:]      # a sibling one column too far right
    cases['shifted sibling'] = (shifted, 'parent')
    cases['missing ]'] = (base[:-1] + ['+gamma [word'], 'value')
    cases['] inside value'] = (base[:-1] + ['+gamma [wo]rd]'], 'value')
    cases['duplicate key'] = (base + ['+gamma [again]'], 'duplicate_key')
    cases['child of scalar'] = (base + ['      +x [1]'], 'child_of_scalar')
    cases['foreign line'] = (base[:3] + ['[2000.01.01-00.00.01:000][  1]LogTemp: Display: other'] + base[3:], 'interleaved')
    elided = event([('big', tables(30) + [('31', ELIDED)])])
    cases['marker not last'] = (elided[:-1] + [elided[-1] + '+x'], 'elision')
    cases['marker with value'] = (elided[:-1] + [elided[-1] + ' [1]'], 'elision')
    cases['marker with sibling'] = (elided + ['|   +32 [1]'], 'elision')
    cases['header only'] = ([HEADER], 'empty')
    cases['trailing space'] = (base[:-1] + [base[-1] + ' '], 'whitespace')
    cases['trailing CR'] = (base[:-1] + [base[-1] + '\r'], 'whitespace')
    cases['non-ASCII'] = (base[:-1] + ['+gamma [wörd]'], 'non_ascii')
    cases['tab'] = (base[:-1] + ['+gamma\t[word]'], 'whitespace')
    cases['marker first segment'] = (base + ['+...'], 'elision')
    cases['bad key'] = (base + ['+ga-mma [1]'], 'segment')
    return cases


class MalformedTest(unittest.TestCase):
    """Reject malformed trees and bounded-input violations without echoing text."""

    def test_each_case_has_one_fixed_code_and_never_echoes_input(self):
        for name, (lines, code) in malformed().items():
            with self.subTest(name):
                lines = [line.replace('word', MARK) for line in lines]
                with self.assertRaises(LogTableError) as caught:
                    parse_event(lines)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn(MARK, str(caught.exception))
                self.assertIsInstance(caught.exception.line, int)

    def test_limits_are_enforced(self):
        lines = event(F1)
        for limits, code in (({'max_lines': 3}, 'limit'), ({'max_line_length': 10}, 'limit'),
                             ({'max_depth': 2}, 'limit'), ({'max_nodes': 4}, 'limit')):
            with self.subTest(limits=limits), self.assertRaises(LogTableError) as caught:
                parse_event(lines, **limits)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(ValueError):
            parse_event(lines, max_depth=0)

    def test_inputs_must_be_text_lines(self):
        for bad in ('one string', [HEADER, 5], None):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(LogTableError):
                parse_event(bad)


class SplitTest(unittest.TestCase):
    """Preserve event spans without merging their independent trees."""

    def test_spans_are_half_open_and_bounded(self):
        foreign = '[2000.01.01-00.00.01:000][  1]LogTemp: Display: other'
        lines = ['noise', foreign] + event(F1) + [foreign] + event([('z', '1')])
        spans = split_events(lines)
        first = len(event(F1))
        self.assertEqual(spans, [(2, 2 + first), (3 + first, 3 + first + 2)])
        # a following non-'[' line belongs to the span; parsing then rejects it, never split_events
        self.assertEqual(split_events([HEADER, '+z [1]', 'tail'])[0], (0, 3))
        for start, end in spans:
            self.assertEqual(parse_event(lines[start:end])['status'], 'complete')
        self.assertEqual(split_events([HEADER]), [(0, 1)])
        self.assertEqual(split_events([]), [])
        with self.assertRaises(LogTableError) as caught:
            split_events(lines, max_lines=3)
        self.assertEqual(caught.exception.code, 'limit')

    def test_results_are_detached(self):
        lines = event(F1)
        first = parse_event(lines)
        first['root']['entries'].clear()
        self.assertEqual(len(parse_event(lines)['root']['entries']), 3)


if __name__ == '__main__':
    unittest.main()
