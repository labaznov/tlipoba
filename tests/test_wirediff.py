"""Synthetic two-source reports exercise the diagnostic consumer without the external exporter."""

import hashlib
import json
import unittest

from damage_lab.wirediff import SummaryError, summary


def artifact(before, after):
    statuses = ('unchanged', 'changed', 'signed_zero_changed', 'type_changed',
                'added_absent_vs_default_unknown', 'removed_absent_vs_default_unknown',
                'ambiguous_repeated_stat', 'ambiguous_repeated_wire', 'opaque_not_compared', 'omitted_not_compared')
    return {
        'format': 'tli-native-wire-diff-v0', 'version': '0.1.0', 'status': 'compared', 'reason': None, 'side': None,
        'sources': {side: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                    for side, raw in (('a', before), ('b', after))},
        'decoder': {'format': 'tli-native-stats-v1', 'version': '0.2.0'},
        'identity': {'author': 'typed_match', 'version': 'equal', 'binding': 'author_only'},
        'counts': {'rows': 1, 'byStatus': {status: int(status == 'changed') for status in statuses},
                   'omitted': {side: {'account identifier': 0, 'free text string': 0} for side in 'ab'},
                   'privacySuppressedKeys': 0},
        'rows': [{'key': {'kind': 'wire', 'path': '1.3'}, 'status': 'changed', 'beforeType': 'varint',
                  'afterType': 'varint', 'before': {'num': '7', 'den': '1'}, 'after': {'num': '9', 'den': '1'},
                  'delta': {'num': '2', 'den': '1'}, 'ratio': {'num': '9', 'den': '7'}}],
        'flags': {'semanticIdentity': 'unknown', 'selection': 'unknown', 'atomicity': 'unknown',
                  'currentness': 'unknown', 'labelsPromoted': False, 'confounding': 'judged_by_input_diff_only'},
    }


class WireDiffTest(unittest.TestCase):
    """Verify two byte references while retaining comparisons only as producer assertions."""

    def test_summary_binds_both_sources_and_keeps_only_aggregate_comparisons(self):
        before, after = b'first synthetic source', b'second synthetic source'
        result = summary(json.dumps(artifact(before, after)).encode(), before, after)
        self.assertEqual((result['counts']['byStatus']['changed'], result['verification'], 'rows' in result),
                         (1, {'sources': 'bytes_match', 'comparisons': 'producer_reported'}, False))

    def test_swapped_source_bytes_are_refused(self):
        before, after = b'source amber', b'source jade'
        with self.assertRaisesRegex(SummaryError, '^source_mismatch$'):
            summary(json.dumps(artifact(before, after)).encode(), after, before)

    def test_changed_counts_must_match_the_rows(self):
        before, after = b'source amber', b'source jade'
        report = artifact(before, after)
        report['counts']['byStatus']['changed'] = 3
        with self.assertRaisesRegex(SummaryError, '^counts_mismatch$'):
            summary(json.dumps(report).encode(), before, after)

    def test_numeric_rows_never_promote_arithmetic_readiness(self):
        before, after = b'source amber', b'source jade'
        report = artifact(before, after)
        report['rows'][0]['delta']['num'] = '519'
        self.assertEqual(summary(json.dumps(report).encode(), before, after)['flags'],
                         {'identity': 'unknown', 'currentness': 'unknown', 'selection': 'unknown',
                          'atomicity': 'unknown', 'labelsPromoted': False, 'arithmeticReady': False})

    def test_noncanonical_wire_paths_are_refused(self):
        before, after = b'source amber', b'source jade'
        report = artifact(before, after)
        report['rows'][0]['key']['path'] = '1.03'
        with self.assertRaisesRegex(SummaryError, '^row_schema$'):
            summary(json.dumps(report).encode(), before, after)

    def test_duplicate_rows_are_refused(self):
        before, after = b'source amber', b'source jade'
        report = artifact(before, after)
        report['rows'] *= 2
        with self.assertRaisesRegex(SummaryError, '^row_schema$'):
            summary(json.dumps(report).encode(), before, after)

    def test_unknown_producer_versions_are_refused(self):
        before, after = b'source amber', b'source jade'
        report = artifact(before, after)
        report['version'] = '0.1.9'
        with self.assertRaisesRegex(SummaryError, '^producer_unsupported$'):
            summary(json.dumps(report).encode(), before, after)

    def test_boolean_lookalikes_cannot_replace_false_flags(self):
        before, after = b'source amber', b'source jade'
        report = artifact(before, after)
        report['flags']['labelsPromoted'] = 0
        with self.assertRaisesRegex(SummaryError, '^artifact_schema$'):
            summary(json.dumps(report).encode(), before, after)

    def test_duplicate_json_keys_are_refused(self):
        with self.assertRaisesRegex(SummaryError, '^artifact_json_malformed$'):
            summary(b'{"status":1,"status":2}', b'a', b'b')

    def test_deep_json_is_refused_before_decoding(self):
        with self.assertRaisesRegex(SummaryError, '^artifact_json_malformed$'):
            summary(b'[' * 65 + b']' * 65, b'a', b'b')

    def test_oversized_sources_are_refused(self):
        with self.assertRaisesRegex(SummaryError, '^source_too_large$'):
            summary(b'{}', b'a' * (16 * 1024 * 1024 + 1), b'b')

    def test_identical_sources_keep_all_selection_evidence_unknown(self):
        report = artifact(b'one source', b'one source')
        report.update(status='identical_sources', rows=[],
                      identity={'author': None, 'version': None, 'binding': 'author_only'})
        report['counts'].update(rows=0, byStatus=dict.fromkeys(report['counts']['byStatus'], 0),
                                omitted={'a': None, 'b': None})
        result = summary(json.dumps(report).encode(), b'one source', b'one source')
        self.assertEqual((result['status'], result['counts']['rows'], result['flags']['selection']),
                         ('identical_sources', 0, 'unknown'))

    def test_private_source_text_cannot_enter_the_summary(self):
        before, after = b'private-source-canary-amber', b'private-source-canary-jade'
        report = artifact(before, after)
        result = json.dumps(summary(json.dumps(report).encode(), before, after))
        self.assertFalse(any(text in result for text in ('private-source-canary', 'statId', 'path', 'delta', 'ratio')))

    def test_mutating_a_summary_cannot_change_the_next_summary(self):
        before, after = b'source amber', b'source jade'
        raw = json.dumps(artifact(before, after)).encode()
        first = summary(raw, before, after)
        first['counts']['byStatus']['changed'] = 71
        self.assertEqual(summary(raw, before, after)['counts']['byStatus']['changed'], 1)
