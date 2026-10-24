import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from damage_lab.buildlog import BuildLogError, snapshot


def event(*lines, frame=17):
    """A synthetic saved table event with its transport line endings."""
    header = f'[2000.01.03-05.07.11:013][ {frame}]TLNetGame: Display: [Game]'
    return ('\r\n'.join((header, *lines)) + '\r\n').encode('ascii')


def saved(directory, data):
    """One caller-owned ordinary log in a real temporary directory."""
    path = Path(directory) / 'ordinary.log'
    path.write_bytes(data)
    return path


def message(name='GetPlayerData', direction='Recv', frame=17):
    """A fictional exact socket marker with no payload or private identifiers."""
    return (f'[2000.01.03-05.07.11:013][ {frame}]TLNetGame: Display: [Game] '
            f'----Socket {direction}Message STT----{name}----\n').encode('ascii')


class ChangingDigest:
    """Hash real bytes and perform one deterministic real file mutation after reading begins."""

    def __init__(self, digest, change):
        self.digest, self.change = digest, change

    def update(self, data):
        self.digest.update(data)
        if self.change is not None:
            change, self.change = self.change, None
            change()

    def hexdigest(self):
        return self.digest.hexdigest()


class SnapshotTest(unittest.TestCase):
    """Read exact saved prefixes without promoting printed trees to build identity."""

    def test_new_snapshot_retains_explicit_unknown_message(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, event('+amount [001]')))
        self.assertEqual((result['version'], result['events'][0].get('message', 'absent')), ('0.1.4', None))

    def test_reference_snapshot_roundtrips_as_new_writer_without_resolving_nodes(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message() + event('+first+leaf [73]', '+again {.first}')))
        restored = json.loads(json.dumps(result))
        self.assertEqual((restored['version'], restored['events'][0]['tree']['version'],
                          restored['events'][0]['tree']['root']['entries'][-1], restored['events'][0]['message']['name']),
                         ('0.1.4', '0.3.0', ['again', {'t': 'reference', 'path': ['first']}], 'GetPlayerData'))

    def test_adjacent_matching_socket_marker_is_bound_without_its_raw_text(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message() + event('+amount [001]')))
        self.assertEqual(result['events'][0]['message'], {'name': 'GetPlayerData', 'direction': 'recv', 'line': 1,
                         'logTimeText': '2000.01.03-05.07.11:013', 'frame': 17})

    def test_exact_optional_socket_synid_suffix_is_not_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message()[:-1] + b'SynId = 7\n' + event('+a [1]')))
        self.assertEqual(result['events'][0]['message'], {'name': 'GetPlayerData', 'direction': 'recv', 'line': 1,
                         'logTimeText': '2000.01.03-05.07.11:013', 'frame': 17})

    def test_adjacent_same_second_and_frame_allow_nondecreasing_milliseconds(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message().replace(b':013', b':007')
                                    + event('+a [1]').replace(b':013', b':015')))
        self.assertEqual((result['events'][0]['message'], result['events'][0]['tree']['header']['logTimeText']),
                         ({'name': 'GetPlayerData', 'direction': 'recv', 'line': 1,
                           'logTimeText': '2000.01.03-05.07.11:007', 'frame': 17}, '2000.01.03-05.07.11:015'))

    def test_temporal_policy_is_same_second_not_a_fitted_millisecond_window(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message().replace(b':013', b':000')
                                    + event('+a [1]').replace(b':013', b':999')))
        self.assertEqual(result['events'][0]['message']['logTimeText'], '2000.01.03-05.07.11:000')

    def test_cross_second_and_backward_timestamps_do_not_bind(self):
        for marker in (message().replace(b':013', b':014'),
                       message().replace(b'11:013', b'10:999'),
                       message().replace(b'11:013', b'12:000')):
            with self.subTest(length=len(marker)), tempfile.TemporaryDirectory() as directory:
                result = snapshot(saved(directory, marker + event('+a [1]')))
            self.assertIsNone(result['events'][0]['message'])

    def test_socket_synid_suffix_has_exact_bounded_decimal_grammar(self):
        for suffix in (b'SynId = -7', b'SynId = +7', b'SynId = ', b'SynId = 12345678901',
                       b'SynId=7', b'SynId = 7 ', b' SynId = 7', b'SynId = 7token', b'Private = 7'):
            with self.subTest(length=len(suffix)), tempfile.TemporaryDirectory() as directory:
                result = snapshot(saved(directory, message()[:-1] + suffix + b'\n' + event('+a [1]')))
            self.assertIsNone(result['events'][0]['message'])

    def test_socket_synid_decimal_boundaries_preserve_only_message_name(self):
        for suffix in (b'SynId = 0', b'SynId = 1234567890'):
            with self.subTest(length=len(suffix)), tempfile.TemporaryDirectory() as directory:
                result = snapshot(saved(directory, message()[:-1] + suffix + b'\n' + event('+a [1]')))
            self.assertEqual(set(result['events'][0]['message']), {'name', 'direction', 'line', 'logTimeText', 'frame'})

    def test_send_and_unrelated_messages_are_typed_without_player_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message(direction='Send') + event('+a [1]')
                                    + message(name='Other_2', frame=29) + event('+b [2]', frame=29)))
        self.assertEqual([(row['message']['direction'], row['message']['name']) for row in result['events']],
                         [('send', 'GetPlayerData'), ('recv', 'Other_2')])

    def test_intervening_or_oversized_physical_lines_clear_a_marker(self):
        for intervening in (b'\n', b'foreign\n', b'x' * 1000 + b'\n'):
            with self.subTest(intervening=len(intervening)), tempfile.TemporaryDirectory() as directory:
                result = snapshot(saved(directory, message() + intervening + event('+a [1]')))
            self.assertIsNone(result['events'][0]['message'])

    def test_mismatching_timestamp_frame_or_marker_grammar_cannot_bind(self):
        for marker in (message(frame=19), message().replace(b'013', b'014'),
                       message(name='9bad'), message(name='a' * 65), message()[:-1] + b' \n',
                       message().replace(b'RecvMessage', b'recvMessage'), message().replace(b'GetPlayerData', b'PRIVATEMARKER\xff'),
                       message().replace(b'TLNetGame', b'OtherGame'), message()[:-1] + b'x' * 1000 + b'\n'):
            with self.subTest(marker=marker[:0]), tempfile.TemporaryDirectory() as directory:
                result = snapshot(saved(directory, marker + event('+a [1]')))
            self.assertIsNone(result['events'][0]['message'])

    def test_marker_does_not_leak_to_a_later_event(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message() + event('+a [1]') + event('+b [2]')))
        self.assertEqual([row['message'] is None for row in result['events']], [False, True])

    def test_unterminated_marker_is_only_an_incomplete_foreign_line(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message()[:-1]))
        self.assertEqual((result['events'], result['source']['incompleteFinalLine']['line']), ([], 1))

    def test_crlf_socket_line_and_framed_header_keep_adjacency(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, message().replace(b'\n', b'\r\n')
                                    + event('+a [1]').replace(b'[Game]\r\n', b'[Game] \r\n')))
        self.assertEqual((result['events'][0]['message']['line'], result['events'][0]['header_trailing_space']), (1, True))

    def test_snapshot_hash_covers_ignored_bytes_and_preserves_lexical_values(self):
        data = b'ignored\r\n' + event('+amount [001]') + b'[foreign record]\r\n'
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data))
        self.assertEqual(
            (result['source']['sha256'], result['source']['snapshotBytes'],
             result['source']['bytesRead'], result['events'][0]['start_line'],
             result['events'][0]['end_line'], result['events'][0]['boundary'],
             result['events'][0]['header_trailing_space'], result['events'][0]['tree']['root']['entries']),
            (hashlib.sha256(data).hexdigest(), len(data), len(data), 2, 3,
             'next_record', False, [['amount', {'t': 'scalar', 'text': '001', 'class': 'text'}]]))

    def test_unterminated_snapshot_tail_rejects_the_active_event(self):
        data = event('+amount [13]') + b'+other [2'
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=7)
        self.assertEqual(
            (result['events'], result['rejected'], result['source']['incompleteFinalLine'],
             result['source']['sha256']),
            ([], [{'start_line': 1, 'end_line': 3, 'boundary': 'snapshot_boundary',
                   'header_trailing_space': False, 'code': 'incomplete_final_line', 'line': 3}],
             {'line': 3, 'bytes': 9}, hashlib.sha256(data).hexdigest()))

    def test_oversized_foreign_line_is_skipped_before_the_next_tree(self):
        data = b'x' * (2 << 20) + b'\r\n' + event('+n [7]')
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=31)
        self.assertEqual(
            (result['source']['sha256'], result['source']['oversizedLines'],
             result['source']['ignoredLines'], len(result['events']), result['rejected']),
            (hashlib.sha256(data).hexdigest(), 1, 1, 1, []))

    def test_oversized_active_line_rejects_only_its_event(self):
        data = event('+before [3]') + b'+' + b'x' * (1 << 20) + b'\n' + event('+after [5]', frame=29)
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=43)
        self.assertEqual(
            ([(r['start_line'], r['end_line'], r['boundary']) for r in result['events']],
             result['rejected'], result['source']['sha256']),
            ([(4, 5, 'snapshot_boundary')],
             [{'start_line': 1, 'end_line': 3, 'boundary': 'next_record',
               'header_trailing_space': False, 'code': 'event_line_limit', 'line': 3}], hashlib.sha256(data).hexdigest()))

    def test_event_size_limit_clears_the_event_and_resumes_at_next_header(self):
        data = event('+a [3]', '+b [7]', '+c [11]') + event('+n [5]', frame=31)
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), max_event_bytes=len(event('+a [3]')),
                              chunk_bytes=11)
        self.assertEqual(
            ([(r['start_line'], r['end_line']) for r in result['events']], result['rejected']),
            ([(5, 6)], [{'start_line': 1, 'end_line': 4, 'boundary': 'next_record',
                        'header_trailing_space': False, 'code': 'event_bytes_limit', 'line': 3}]))

    def test_event_line_limit_rejects_without_losing_the_next_event(self):
        data = event('+a [1]', '+b [2]', '+c [3]') + event('+z [7]', frame=41)
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), max_event_lines=2, chunk_bytes=19)
        self.assertEqual(
            (len(result['events']), result['rejected']),
            (1, [{'start_line': 1, 'end_line': 4, 'boundary': 'next_record',
                  'header_trailing_space': False, 'code': 'event_lines_limit', 'line': 3}]))

    def test_event_count_limit_includes_previously_rejected_events(self):
        data = event('malformed PRIVATEMARKER') + event('+n [7]', frame=43)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(BuildLogError) as caught:
                snapshot(saved(directory, data), max_events=1)
        self.assertEqual((caught.exception.code, caught.exception.line,
                          str(caught.exception)),
                         ('event_limit', 3, 'build log error event_limit at line 3'))

    def test_two_events_keep_independent_trees_and_boundary_kinds(self):
        data = event('+first [-3]', frame=19) + event('+second [1.70]', frame=53)
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=1)
        self.assertEqual(
            [(r['start_line'], r['end_line'], r['boundary'],
              r['tree']['header']['frame'], r['tree']['root']['entries']) for r in result['events']],
            [(1, 2, 'next_record', 19, [['first', {'t': 'scalar', 'text': '-3', 'class': 'int'}]]),
             (3, 4, 'snapshot_boundary', 53, [['second', {'t': 'scalar', 'text': '1.70', 'class': 'float'}]])])

    def test_malformed_event_has_a_fixed_rejection_without_source_text(self):
        data = b'ignored\n' + event('+a [1]', 'PRIVATEMARKER77') + b'[other]\n'
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data))
        self.assertEqual(
            (result['events'], result['rejected'], result['source']['sha256']),
            ([], [{'start_line': 2, 'end_line': 4, 'boundary': 'next_record',
                   'header_trailing_space': False, 'code': 'grammar_segment', 'line': 4}], hashlib.sha256(data).hexdigest()))

    def test_only_one_cr_is_removed_from_crlf_transport(self):
        data = event('+n [7]').replace(b'+n [7]\r\n', b'+n [7]\r\r\n')
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=2)
        self.assertEqual(
            (result['events'], result['rejected'], result['source']['sha256']),
            ([], [{'start_line': 1, 'end_line': 2, 'boundary': 'snapshot_boundary',
                   'header_trailing_space': False, 'code': 'grammar_whitespace', 'line': 2}], hashlib.sha256(data).hexdigest()))

    def test_header_recognition_requires_exact_ascii_grammar(self):
        normal = event('+bad [1]')
        headers = [normal.replace(b'[ 17]', '[ １７]'.encode('utf-8')),
                   normal.replace(b'[Game]\r\n', b'[Game]  \r\n'),
                   normal.replace(b'TLNetGame:', b'TLNetGames:')]
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, b''.join(headers) + event('+good [3]')))
        self.assertEqual((len(result['events']), result['events'][0]['start_line'],
                          result['source']['ignoredLines']), (1, 7, 6))

    def test_oversized_bracket_line_closes_a_previous_valid_event(self):
        data = event('+a [1]') + b'[' + b'x' * 1703 + b'\n' + event('+b [2]')
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=13)
        self.assertEqual((len(result['events']), result['events'][0]['boundary'],
                          result['source']['oversizedLines'], result['source']['ignoredLines']),
                         (2, 'next_record', 1, 1))

    def test_no_events_does_not_claim_runtime_or_build_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, b'[unrelated]\nforeign\n'))
        self.assertEqual(
            (result['events'], result['rejected'], result['status'], result['scope'],
             result['import_complete'], result['identity'], result['runtime'],
             result['freshness'], result['selected_skill'], result['build_code']),
            ([], [], 'diagnostic', 'printed_tree_only', False,
             'unknown', 'unknown', 'unknown', 'unknown', 'unknown'))

    def test_empty_file_has_the_empty_prefix_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, b''))
        self.assertEqual(
            (result['source']['sha256'], result['source']['snapshotBytes'],
             result['source']['bytesRead'], result['source']['lines'],
             result['source']['incompleteFinalLine'], result['events']),
            (hashlib.sha256(b'').hexdigest(), 0, 0, 0, None, []))

    def test_source_and_global_line_limits_fail_without_returning_partial_events(self):
        data = event('+n [1]') + b'[foreign]\n'
        outcomes = []
        with tempfile.TemporaryDirectory() as directory:
            path = saved(directory, data)
            for limits in ({'max_source_bytes': len(data) - 1}, {'max_lines': 2}):
                with self.assertRaises(BuildLogError) as caught:
                    snapshot(path, **limits)
                outcomes.append((caught.exception.code, caught.exception.line))
        self.assertEqual(outcomes, [('source_limit', 0), ('line_limit', 3)])

    def test_all_limits_require_positive_integers(self):
        outcomes = []
        with tempfile.TemporaryDirectory() as directory:
            path = saved(directory, b'')
            for name in ('max_source_bytes', 'max_lines', 'max_line_bytes', 'max_events',
                         'max_event_lines', 'max_event_bytes', 'max_retained_bytes', 'chunk_bytes'):
                for value in (0, -3, True, 2.5, '17', None):
                    with self.assertRaises(BuildLogError) as caught:
                        snapshot(path, **{name: value})
                    outcomes.append((caught.exception.code, caught.exception.line))
        self.assertEqual(set(outcomes), {('limits', 0)})

    def test_source_size_at_the_limit_is_allowed(self):
        data = event('+n [11]')
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), max_source_bytes=len(data))
        self.assertEqual(len(result['events']), 1)

    def test_growth_after_open_is_excluded_from_the_snapshot_and_hash(self):
        data = event('+first [11]')
        with tempfile.TemporaryDirectory() as directory:
            path = saved(directory, data)

            def grow():
                with path.open('ab') as handle:
                    handle.write(event('+second [19]', frame=61))

            digest = ChangingDigest(hashlib.sha256(), grow)
            with patch('damage_lab.buildlog.hashlib.sha256', lambda: digest):
                result = snapshot(path, chunk_bytes=7)
            outcome = (result['source']['sha256'], result['source']['snapshotBytes'],
                       result['source']['bytesRead'], len(result['events']), path.stat().st_size > len(data))
        self.assertEqual(outcome, (hashlib.sha256(data).hexdigest(), len(data), len(data), 1, True))

    def test_shrinking_during_read_is_a_fixed_controlled_failure(self):
        data = event('+first [11]') + b'[foreign]\n' * 1000
        with tempfile.TemporaryDirectory() as directory:
            path = saved(directory, data)
            digest = ChangingDigest(hashlib.sha256(), lambda: path.write_bytes(b''))
            with patch('damage_lab.buildlog.hashlib.sha256', lambda: digest):
                with self.assertRaises(BuildLogError) as caught:
                    snapshot(path, chunk_bytes=7)
        self.assertEqual(caught.exception.code, 'source_shrank')

    def test_non_ascii_body_is_rejected_with_its_physical_line(self):
        data = event('+first [11]') + '+text [пример]\n'.encode('utf-8')
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data))
        self.assertEqual(result['rejected'], [
            {'start_line': 1, 'end_line': 3, 'boundary': 'snapshot_boundary',
             'header_trailing_space': False, 'code': 'grammar_non_ascii', 'line': 3}])

    def test_invalid_path_is_a_fixed_failure_without_a_private_payload(self):
        with self.assertRaises(BuildLogError) as caught:
            snapshot(None)
        self.assertEqual(str(caught.exception), 'build log error path at line 0')

    def test_single_header_framing_space_is_explicit_without_changing_source_hash(self):
        data = event('+number [17]').replace(b'[Game]\r\n', b'[Game] \r\n')
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=5)
        self.assertEqual(
            (len(result['events']), result['events'][0]['header_trailing_space'],
             result['events'][0]['tree']['root']['entries'], result['source']['sha256']),
            (1, True, [['number', {'t': 'scalar', 'text': '17', 'class': 'int'}]],
             hashlib.sha256(data).hexdigest()))

    def test_header_framing_does_not_normalize_trailing_body_whitespace(self):
        data = event('+number [17] ').replace(b'[Game]\r\n', b'[Game] \r\n')
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data))
        self.assertEqual(
            (result['events'], result['rejected'], result['source']['sha256']),
            ([], [{'start_line': 1, 'end_line': 2, 'boundary': 'snapshot_boundary',
                   'header_trailing_space': True, 'code': 'grammar_whitespace', 'line': 2}],
             hashlib.sha256(data).hexdigest()))

    def test_two_header_spaces_or_tab_are_not_logging_framing(self):
        normal = event('+number [17]')
        data = b''.join(normal.replace(b'[Game]\r\n', ending)
                        for ending in (b'[Game]  \r\n', b'[Game]\t\r\n', b'[Game] \t\r\n'))
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data))
        self.assertEqual((result['events'], result['rejected'], result['source']['ignoredLines']),
                         ([], [], 6))

    def test_default_event_limit_allows_more_than_sixty_four_small_events(self):
        data = b''.join(event('+number [17]', frame=number) for number in range(71))
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), chunk_bytes=37)
        self.assertEqual((len(result['events']), result['source']['retainedEventBytes']),
                         (71, len(data)))

    def test_retained_byte_budget_rejects_the_aggregate_without_a_partial_document(self):
        data = event('+number [17]') + event('+other [23]', frame=29)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(BuildLogError) as caught:
                snapshot(saved(directory, data), max_retained_bytes=len(data) - 1)
        self.assertEqual((caught.exception.code, caught.exception.line,
                          str(caught.exception)),
                         ('retained_limit', 3, 'build log error retained_limit at line 3'))

    def test_exact_retained_budget_includes_raw_framing_and_excludes_foreign_records(self):
        first = event('+number [17]').replace(b'[Game]\r\n', b'[Game] \r\n')
        second = event('+other [23]', frame=29)
        data = b'ignored\n' + first + b'[foreign]\r\nignored\n' + second
        with tempfile.TemporaryDirectory() as directory:
            result = snapshot(saved(directory, data), max_retained_bytes=len(first) + len(second))
        self.assertEqual((len(result['events']), result['source']['retainedEventBytes']),
                         (2, len(first) + len(second)))

    def test_rejected_events_dont_consume_the_retained_budget(self):
        first, last = event('+a [1]'), event('+b [2]', frame=41)
        outcomes = []
        with tempfile.TemporaryDirectory() as directory:
            for broken in (event('malformed'), event('+long [' + 'x' * 139 + ']')):
                result = snapshot(saved(directory, first + broken + last),
                                  max_retained_bytes=len(first) + len(last), max_event_bytes=200)
                outcomes.append((len(result['events']), len(result['rejected']),
                                 result['source']['retainedEventBytes']))
        self.assertEqual(outcomes, [(2, 1, len(first) + len(last))] * 2)
