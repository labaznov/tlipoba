import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.witnessbundle import BundleError, read, summary


def digest(data):
    return hashlib.sha256(data).hexdigest()


def flags():
    return {'currentness': 'unknown', 'atomicity': 'unknown', 'identity': 'unknown_identity',
            'coverage': 'visible_rows_only', 'correspondence': 'observation_only',
            'effectiveLevel': None, 'arithmeticReady': False}


def descriptor(status):
    result = dict.fromkeys(('file version witnessFormat witnessVersion status error sha256 sourceSha256 sourceBytes '
                            'packetFile packetSha256 packetBytes eventIndex framedSha256 targets logJoins '
                            'fieldComparisons verification flags').split())
    result.update(file=None if status == 'not_requested' else 'selected-build-witness.json', version='0.1.1',
                  witnessFormat='tli-selected-build-witness-v0', witnessVersion='0.1.1', status=status,
                  verification={'bytes': 'consumer_verifiable', 'joins': 'producer_reported'}, flags=flags())
    return result


def persisted(root):
    source = b'{"synthetic": true}'
    (root / 'source.json').write_bytes(source)
    lines = ['[2000.01.01-00.00.00:000][  0]TLNetGame: Display: [Game]', '+private [SYNTHETIC-CANARY]']
    packet = {'format': 'tli-log-table-event-v1', 'source': {'file': 'private.log'},
              'limitRecordsPerEvent': 50000, 'events': [{'firstLine': 7, 'lastLine': 8,
                  'records': [{'line': 7 + index, 'text': text} for index, text in enumerate(lines)]}]}
    raw = json.dumps(packet).encode()
    (root / 'state-log-packet.json').write_bytes(raw)
    framed = digest(b''.join(len(line.encode()).to_bytes(4, 'big') + line.encode() for line in lines))
    joins = {code: int(code == 'exact_id_text') for code in (
        'exact_id_text', 'not_visible_elided', 'not_visible', 'ambiguous', 'id_not_text', 'table_absent', 'not_attempted')}
    comparisons = {name: {'equal': 1, 'different': 0, 'unobserved': 0} for name in ('Level', 'SkillItemLevel')}
    artifact = {'format': 'tli-selected-build-witness-bundle-v0', 'version': '0.1.1', 'status': 'diagnostic',
        'witnessFormat': 'tli-selected-build-witness-v0', 'witnessVersion': '0.1.1',
        'source': {'file': 'source.json', 'sha256': digest(source), 'bytes': len(source)},
        'packet': {'file': 'state-log-packet.json', 'sha256': digest(raw), 'bytes': len(raw),
                   'format': packet['format'], 'events': 1},
        'event': {'index': 0, 'framedSha256': framed, 'framing': 'sha256(4-byte big-endian UTF-8 length + UTF-8 bytes, per record text)',
                  'lines': 2, 'parseStatus': 'complete', 'rootElided': False, 'elisions': 0},
        'selection': {'policy': 'distinct_observed_config_base_ids', 'targets': 1, 'eventIndex': 'caller_declared'},
        'logTable': {'status': 'printed_complete', 'visibleRows': 1, 'idTextRows': 1},
        'targets': [{'skillId': 91837, 'client': 'unique', 'native': {'join': 'exact_instance', 'binding': 'revalidated'},
                     'log': {'join': 'exact_id_text'}, 'fields': {name: {'native': 'int', 'log': 'int', 'comparison': 'equal'}
                                                               for name in comparisons}}],
        'counts': {'targets': 1, 'logJoins': joins, 'fieldComparisons': comparisons},
        'verification': {'bytes': 'consumer_verifiable', 'joins': 'producer_reported'}, 'flags': flags()}
    record = descriptor('diagnostic')
    record.update(sourceSha256=digest(source), sourceBytes=len(source), packetFile='state-log-packet.json',
                  packetSha256=digest(raw), packetBytes=len(raw), eventIndex=0, framedSha256=framed,
                  targets=1, logJoins=joins, fieldComparisons=comparisons)
    save(root, artifact, record)
    return artifact, record, digest(source)


def save(root, artifact, record):
    data = json.dumps(artifact).encode()
    (root / 'selected-build-witness.json').write_bytes(data)
    record['sha256'] = digest(data)


def failed(root, code='packet_copy_mismatch'):
    observed, _, source = persisted(root)
    artifact = {key: copy.deepcopy(observed[key]) for key in (
        'version', 'status', 'witnessFormat', 'witnessVersion', 'source', 'flags')}
    artifact.update(format='tli-selected-build-witness-bundle-error-v0', status='error', error=code,
                    packet={key: observed['packet'][key] for key in ('file', 'sha256', 'bytes')})
    record = descriptor('error')
    record.update(error=code, sourceSha256=source, sourceBytes=observed['source']['bytes'],
                  packetFile='state-log-packet.json', packetSha256=artifact['packet']['sha256'],
                  packetBytes=artifact['packet']['bytes'])
    save(root, artifact, record)
    return artifact, record, source


class WitnessBundleTest(unittest.TestCase):
    """Verify byte references and safe producer diagnostics without re-running native or log joins."""

    def test_known_unavailable_native_sections_remain_diagnostic(self):
        for state in ('section_not_decoded', 'section_not_available'):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                artifact, record, source = persisted(root)
                artifact['targets'][0]['native'] = {'join': state, 'binding': 'not_applicable'}
                artifact['targets'][0]['log']['join'] = 'not_attempted'
                for field in artifact['targets'][0]['fields'].values():
                    field.update(native='unavailable', log='not_joined', comparison='unobserved')
                artifact['counts']['logJoins'].update(exact_id_text=0, not_attempted=1)
                for field in artifact['counts']['fieldComparisons'].values():
                    field.update(equal=0, unobserved=1)
                save(root, artifact, record)
                self.assertEqual(read(root, record, source)[0]['status'], 'diagnostic')

    def test_elided_tables_can_have_empty_entries_outside_visible_row_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact, record, source = persisted(root)
            artifact['logTable'].update(status='elided_at_limit', visibleRows=29)
            artifact['event'].update(parseStatus='elided', elisions=1)
            save(root, artifact, record)
            self.assertEqual(read(root, record, source)[0]['status'], 'diagnostic')

    def test_selected_event_limits_do_not_apply_to_unselected_packet_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact, record, source = persisted(root)
            packet = json.loads((root / 'state-log-packet.json').read_bytes())
            packet['events'].append({'firstLine': 17, 'lastLine': 17, 'records': [{'line': 17, 'text': 'x' * 5001}]})
            raw = json.dumps(packet).encode()
            (root / 'state-log-packet.json').write_bytes(raw)
            artifact['packet'].update(sha256=digest(raw), bytes=len(raw), events=2)
            record.update(packetSha256=digest(raw), packetBytes=len(raw))
            save(root, artifact, record)
            self.assertEqual(read(root, record, source)[0]['status'], 'diagnostic')

    def test_json_numbers_are_bounded_before_conversion(self):
        for token in ('1' * 65, '0.' + '1' * 63):
            with self.subTest(token=token[:2]), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                _, record, source = persisted(root)
                raw = ('{"number":' + token + '}').encode()
                (root / 'selected-build-witness.json').write_bytes(raw)
                record['sha256'] = digest(raw)
                with self.assertRaisesRegex(BundleError, 'resource_limit'):
                    read(root, record, source)

    def test_field_classes_must_agree_with_join_availability(self):
        for change in ('native', 'log'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                artifact, record, source = persisted(root)
                target = artifact['targets'][0]
                if change == 'native':
                    target['native'] = {'join': 'section_not_decoded', 'binding': 'not_applicable'}
                    target['log']['join'] = 'not_attempted'
                    for field in target['fields'].values():
                        field.update(log='not_joined', comparison='unobserved')
                    artifact['counts']['logJoins'].update(exact_id_text=0, not_attempted=1)
                else:
                    for field in target['fields'].values():
                        field.update(log='not_joined', comparison='unobserved')
                for field in artifact['counts']['fieldComparisons'].values():
                    field.update(equal=0, unobserved=1)
                save(root, artifact, record)
                with self.assertRaises(BundleError):
                    read(root, record, source)

    def test_not_requested_needs_no_source_or_packet_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(read(Path(folder), descriptor('not_requested'), 'a' * 64)[0]['status'], 'not_requested')

    def test_copy_failure_accepts_error_artifact_without_claiming_packet_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, record, source = failed(root)
            (root / 'state-log-packet.json').unlink()
            self.assertEqual(summary(read(root, record, source)[0])['integrity']['references'], 'artifact_verified')

    def test_error_envelopes_require_matching_hashes_flags_and_null_counts(self):
        for change in ('hash', 'flag', 'count', 'code', 'extra'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                artifact, record, source = failed(root)
                if change == 'hash':
                    record['sha256'] = 'f' * 64
                else:
                    if change == 'flag':
                        artifact['flags']['arithmeticReady'] = True
                    elif change == 'count':
                        record['targets'] = 0
                    elif change == 'code':
                        artifact['error'] = record['error'] = 'SYNTHETIC-CANARY'
                    else:
                        artifact['privateId'] = 'SYNTHETIC-CANARY'
                    save(root, artifact, record)
                with self.assertRaises(BundleError):
                    read(root, record, source)

    def test_source_load_errors_can_have_no_source_or_packet_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact, record, source = failed(root, 'source_unreadable')
            artifact['source'].update(sha256=None, bytes=None)
            artifact['packet'].update(file=None, sha256=None, bytes=None)
            record.update(sourceSha256=None, sourceBytes=None, packetFile=None, packetSha256=None, packetBytes=None)
            save(root, artifact, record)
            self.assertEqual(read(root, record, source)[0]['status'], 'error')

    def test_saturated_packet_events_cannot_be_admitted_as_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact, record, source = persisted(root)
            packet = json.loads((root / 'state-log-packet.json').read_bytes())
            packet['limitRecordsPerEvent'] = 2
            raw = json.dumps(packet).encode()
            (root / 'state-log-packet.json').write_bytes(raw)
            artifact['packet'].update(sha256=digest(raw), bytes=len(raw))
            record.update(packetSha256=digest(raw), packetBytes=len(raw))
            save(root, artifact, record)
            with self.assertRaises(BundleError):
                read(root, record, source)

    def test_duplicate_json_members_are_refused_even_with_matching_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, record, source = persisted(root)
            raw = b'{"version":"0.1.1","version":"0.1.1"}'
            (root / 'selected-build-witness.json').write_bytes(raw)
            record['sha256'] = digest(raw)
            with self.assertRaises(BundleError):
                read(root, record, source)

    def test_detached_summary_cannot_change_source_or_promote_verification(self):
        for change in ('source', 'joins', 'references', 'fields'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                _, record, source = persisted(root)
                value = read(root, record, source)[0]
                if change == 'source':
                    value['source_sha256'] = 'f' * 64
                elif change == 'fields':
                    value['artifact']['targets'][0]['fields']['Level']['comparison'] = 'different'
                else:
                    value['integrity'][change] = 'runtime_verified'
                with self.assertRaises(BundleError):
                    summary(value)

    def test_diagnostic_verifies_references_and_keeps_joins_producer_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, record, source = persisted(root)
            self.assertEqual(read(root, record, source)[0]['integrity']['joins'], 'producer_reported')

    def test_private_packet_text_never_enters_canonical_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, record, source = persisted(root)
            self.assertNotIn('CANARY', json.dumps(summary(read(root, record, source)[0])))

    def test_all_descriptor_duplicates_must_match_the_artifact(self):
        for key, value in (('eventIndex', 1), ('packetBytes', 1), ('targets', 2), ('sourceBytes', 1),
                           ('framedSha256', 'f' * 64)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                _, record, source = persisted(root)
                record[key] = value
                with self.assertRaises(BundleError):
                    read(root, record, source)

    def test_actual_packet_and_source_bytes_must_match(self):
        for filename in ('source.json', 'state-log-packet.json', 'selected-build-witness.json'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                _, record, source = persisted(root)
                (root / filename).write_bytes(b'{}')
                with self.assertRaises(BundleError):
                    read(root, record, source)

    def test_event_framing_is_recomputed_from_the_selected_packet(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact, record, source = persisted(root)
            artifact['event']['framedSha256'] = record['framedSha256'] = 'f' * 64
            save(root, artifact, record)
            with self.assertRaises(BundleError):
                read(root, record, source)

    def test_promoted_flags_and_dynamic_keys_are_refused(self):
        for change in ('flag', 'extra', 'target'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                artifact, record, source = persisted(root)
                if change == 'flag':
                    artifact['flags']['effectiveLevel'] = 29
                elif change == 'extra':
                    artifact['SYNTHETIC-CANARY'] = 'private'
                else:
                    artifact['targets'][0]['native']['instance'] = 'SYNTHETIC-CANARY'
                save(root, artifact, record)
                with self.assertRaises(BundleError):
                    read(root, record, source)

    def test_equal_requires_both_exact_joins_and_integer_classes(self):
        for change in ('join', 'binding', 'type'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                artifact, record, source = persisted(root)
                if change == 'join':
                    artifact['targets'][0]['log']['join'] = 'ambiguous'
                elif change == 'binding':
                    artifact['targets'][0]['native']['binding'] = 'mismatch'
                else:
                    artifact['targets'][0]['fields']['Level']['log'] = 'bool'
                save(root, artifact, record)
                with self.assertRaises(BundleError):
                    read(root, record, source)

    def test_counts_are_recomputed_from_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact, record, source = persisted(root)
            artifact['counts']['fieldComparisons']['Level']['equal'] = 2
            record['fieldComparisons'] = copy.deepcopy(artifact['counts']['fieldComparisons'])
            save(root, artifact, record)
            with self.assertRaises(BundleError):
                read(root, record, source)

    def test_descriptor_counts_cannot_use_booleans(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, record, source = persisted(root)
            record['logJoins'] = copy.deepcopy(record['logJoins'])
            record['logJoins']['ambiguous'] = False
            with self.assertRaises(BundleError):
                read(root, record, source)

    def test_absent_table_cannot_report_an_exact_join(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact, record, source = persisted(root)
            artifact['logTable'] = {'status': 'absent', 'visibleRows': 0, 'idTextRows': 0}
            save(root, artifact, record)
            with self.assertRaises(BundleError):
                read(root, record, source)

    def test_unknown_versions_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, record, source = persisted(root)
            record['version'] = '9.0.0'
            with self.assertRaises(BundleError):
                read(root, record, source)

    def test_summary_is_detached_and_does_not_promote_unknowns(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, record, source = persisted(root)
            value = read(root, record, source)[0]
            clone = summary(value)
            clone['artifact']['flags']['effectiveLevel'] = 17
            self.assertIsNone(summary(value)['artifact']['flags']['effectiveLevel'])
