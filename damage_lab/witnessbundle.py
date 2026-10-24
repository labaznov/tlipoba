"""Verify local witness byte references while retaining joins as producer-reported observations."""

import copy
import hashlib
import json
import math
from pathlib import Path
import re
import stat


VERSION = '0.1.1'
FORMAT = 'tli-selected-build-witness-bundle-v0'
ERROR_FORMAT = 'tli-selected-build-witness-bundle-error-v0'
CANONICAL = 'tli-selected-build-witness-canonical-v1'
FILE = 'selected-build-witness.json'
PACKET = 'state-log-packet.json'
FRAMING = 'sha256(4-byte big-endian UTF-8 length + UTF-8 bytes, per record text)'
FLAGS = {'currentness': 'unknown', 'atomicity': 'unknown', 'identity': 'unknown_identity',
         'coverage': 'visible_rows_only', 'correspondence': 'observation_only',
         'effectiveLevel': None, 'arithmeticReady': False}
VERIFICATION = {'bytes': 'consumer_verifiable', 'joins': 'producer_reported'}
JOINS = 'exact_id_text not_visible_elided not_visible ambiguous id_not_text table_absent not_attempted'.split()
FIELDS = ('Level', 'SkillItemLevel')
COMPARISONS = ('equal', 'different', 'unobserved')
DESCRIPTOR = ('file version witnessFormat witnessVersion status error sha256 sourceSha256 sourceBytes packetFile '
              'packetSha256 packetBytes eventIndex framedSha256 targets logJoins fieldComparisons verification flags').split()
BASE = 'format version status witnessFormat witnessVersion source packet flags'.split()
DIAGNOSTIC = BASE + 'event selection logTable targets counts verification'.split()
UNREAD = ('source_missing', 'source_unreadable', 'source_too_large')
LOAD = 'type too_large digest_format digest_mismatch depth_limit not_json duplicate_key nonfinite_number number_limit node_limit'.split()
GRAMMAR = 'input limit empty header whitespace non_ascii interleaved segment value elision parent child_of_scalar duplicate_key render_mismatch'.split()
ERRORS = set(('source_missing source_unreadable source_too_large witness_version_unreviewed packet_missing '
    'packet_unreadable packet_not_regular packet_outside_repository packet_too_large packet_copy_mismatch inventory_failed '
    'client_layer_absent client_layer_invalid client_layer_not_captured no_targets targets_out_of_range output_limit '
    'witness_unlisted witness_report_inconsistent artifact_limit').split())
ERRORS.update(f'witness_{side}_{code}' for side in ('source', 'packet') for code in LOAD)
ERRORS.update(f'witness_event_grammar_{code}' for code in GRAMMAR)
ERRORS.update('witness_' + code for code in ('source_schema packet_format packet_schema packet_events_limit '
    'event_index_invalid event_capture_limit event_too_many_lines event_line_too_long event_too_many_bytes '
    'event_lines_not_contiguous event_not_one_span targets_invalid client_tabs_limit client_positions_limit '
    'server_slots_limit skills_rows_limit instance_oversized').split())
REJECTIONS = {'schema', 'resource_limit', 'unsupported_version', 'flag_promotion', 'binding_failed', 'integrity_failed',
              'artifact_missing', 'packet_missing', 'source_missing', 'io_failed'}


class BundleError(ValueError):
    """A controlled companion rejection with a fixed code that never contains input data."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(condition, code='schema'):
    if not condition:
        raise BundleError(code)


def _object(value, keys):
    _need(type(value) is dict and set(value) == set(keys))


def _integer(value, low, high):
    _need(type(value) is int and low <= value <= high)


def _hash(value):
    _need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None)


def _fixed(value, expected, code='schema'):
    _object(value, expected)
    _need(all(type(value[key]) is type(item) and value[key] == item for key, item in expected.items()), code)


def _tree(value, private=False):
    limit = 2000000 if private else 200000
    length = 16 * 2 ** 20 if private else 4096
    stack, seen, count = [(value, 0)], set(), 0
    while stack:
        item, depth = stack.pop()
        count += 1
        _need(count <= limit and depth <= 64, 'resource_limit')
        if type(item) in (dict, list):
            _need(id(item) not in seen and count + len(stack) + len(item) <= limit, 'resource_limit')
            seen.add(id(item))
            if type(item) is dict:
                _need(all(type(key) is str and len(key) <= length for key in item), 'resource_limit')
            stack.extend((child, depth + 1) for child in (item.values() if type(item) is dict else item))
        elif type(item) is str:
            _need(len(item) <= length, 'resource_limit')
            try:
                item.encode('utf-8')
            except UnicodeError:
                raise BundleError('schema') from None
        elif type(item) is int:
            _need(item.bit_length() <= 220, 'resource_limit')
        else:
            _need(item is None or type(item) is bool or (type(item) is float and math.isfinite(item)))


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        _need(key not in value)
        value[key] = item
    return value


def _constant(_):
    raise BundleError('schema')


def _integer_token(token):
    _need(len(token) <= 64, 'resource_limit')
    return int(token)


def _float_token(token):
    _need(len(token) <= 64, 'resource_limit')
    value = float(token)
    _need(math.isfinite(value))
    return value


def _json(data, private=False):
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant,
                           parse_int=_integer_token, parse_float=_float_token)
    except BundleError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise BundleError('schema') from None
    _tree(value, private=private)
    return value


def _bytes(path, limit, missing):
    try:
        info = path.lstat()
        _need(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode))
        _need(info.st_size <= limit, 'resource_limit')
        with path.open('rb') as stream:
            data = stream.read(limit + 1)
    except FileNotFoundError:
        raise BundleError(missing) from None
    except OSError:
        raise BundleError('io_failed') from None
    _need(len(data) <= limit, 'resource_limit')
    return data


def _version(value):
    _need(value['version'] == VERSION and value['witnessVersion'] == '0.1.1'
          and value['witnessFormat'] == 'tli-selected-build-witness-v0', 'unsupported_version')
    _fixed(value['flags'], FLAGS, 'flag_promotion')


def _reference(value, file, nullable=False):
    _object(value, ('file', 'sha256', 'bytes'))
    _need(value['file'] == file)
    if nullable and value['sha256'] is None:
        _need(value['bytes'] is None)
    else:
        _hash(value['sha256'])
        _integer(value['bytes'], 0, 16 * 2 ** 20)


def _targets(value):
    _need(type(value) is list and 1 <= len(value) <= 64)
    ids, joins = [], dict.fromkeys(JOINS, 0)
    counts = {name: dict.fromkeys(COMPARISONS, 0) for name in FIELDS}
    native = ('not_resolved target_unavailable exact_instance section_absent section_invalid section_not_captured '
              'section_unrecognized section_not_decoded section_not_available collection_limit no_instance ambiguous_instance no_skills_row').split()
    for row in value:
        _object(row, ('skillId', 'client', 'native', 'log', 'fields'))
        _integer(row['skillId'], 1, 1000000000)
        ids.append(row['skillId'])
        _need(row['client'] in ('unique', 'not_installed', 'ambiguous'))
        _object(row['native'], ('join', 'binding'))
        _need(row['native']['join'] in native and row['native']['binding'] in ('not_applicable', 'revalidated', 'mismatch'))
        _object(row['log'], ('join',))
        _need(row['log']['join'] in JOINS)
        if row['client'] != 'unique':
            _need(row['native'] == {'join': 'not_resolved', 'binding': 'not_applicable'})
        joined = row['log']['join'] == 'exact_id_text'
        if row['native']['join'] == 'exact_instance':
            _need(row['client'] == 'unique' and row['native']['binding'] in ('revalidated', 'mismatch'))
        else:
            _need(row['native']['binding'] == 'not_applicable' and row['log']['join'] == 'not_attempted')
        if row['log']['join'] != 'not_attempted':
            _need(row['client'] == 'unique' and row['native'] == {'join': 'exact_instance', 'binding': 'revalidated'})
        if row['native']['binding'] == 'revalidated':
            _need(row['log']['join'] != 'not_attempted')
        _object(row['fields'], FIELDS)
        for name, field in row['fields'].items():
            _object(field, ('native', 'log', 'comparison'))
            _need(field['native'] in ('unavailable', 'missing', 'invalid', 'int'))
            _need(field['log'] in ('not_joined', 'absent', 'int', 'bool', 'float', 'text', 'table', 'empty', 'elided'))
            _need(field['comparison'] in COMPARISONS)
            if row['native']['join'] != 'exact_instance':
                _need(field['native'] == 'unavailable')
            if joined:
                _need(field['log'] != 'not_joined')
            if field['comparison'] != 'unobserved':
                _need(joined and field['native'] == field['log'] == 'int')
            if not joined:
                _need(field['log'] == 'not_joined' and field['comparison'] == 'unobserved')
            counts[name][field['comparison']] += 1
        joins[row['log']['join']] += 1
    _need(len(set(ids)) == len(ids) and ids == sorted(ids))
    return joins, counts


def _counts(joins, fields):
    _object(joins, JOINS)
    _object(fields, FIELDS)
    for count in joins.values():
        _integer(count, 0, 64)
    for field in fields.values():
        _object(field, COMPARISONS)
        for count in field.values():
            _integer(count, 0, 64)


def _artifact(value, source):
    _need(type(value) is dict and value.get('status') in ('diagnostic', 'error'))
    diagnostic = value['status'] == 'diagnostic'
    _object(value, DIAGNOSTIC if diagnostic else BASE + ['error'])
    _version(value)
    _need(value['format'] == (FORMAT if diagnostic else ERROR_FORMAT))
    _reference(value['source'], 'source.json', nullable=not diagnostic)
    if value['source']['sha256'] is not None:
        _need(value['source']['sha256'] == source, 'binding_failed')
    if not diagnostic:
        _need(type(value['error']) is str and value['error'] in ERRORS)
        _need((value['source']['sha256'] is None) == (value['error'] in UNREAD))
        _object(value['packet'], ('file', 'sha256', 'bytes'))
        _reference(value['packet'], None if value['packet']['file'] is None else PACKET, nullable=True)
        _need((value['packet']['file'] is None) == (value['packet']['sha256'] is None))
        return
    _object(value['packet'], ('file', 'sha256', 'bytes', 'format', 'events'))
    _reference({key: value['packet'][key] for key in ('file', 'sha256', 'bytes')}, PACKET)
    _need(value['packet']['format'] == 'tli-log-table-event-v1')
    _integer(value['packet']['events'], 1, 20)
    event = value['event']
    _object(event, ('index', 'framedSha256', 'framing', 'lines', 'parseStatus', 'rootElided', 'elisions'))
    _integer(event['index'], 0, value['packet']['events'] - 1)
    _hash(event['framedSha256'])
    _need(event['framing'] == FRAMING and event['parseStatus'] in ('complete', 'elided') and type(event['rootElided']) is bool)
    _integer(event['lines'], 2, 20000)
    _integer(event['elisions'], 0, 200000)
    _need((event['elisions'] == 0) == (event['parseStatus'] == 'complete')
          and (not event['rootElided'] or event['elisions'] > 0))
    table = value['logTable']
    _object(table, ('status', 'visibleRows', 'idTextRows'))
    _need(table['status'] in ('absent', 'printed_complete', 'elided_at_limit'))
    _integer(table['visibleRows'], 0, 30)
    _integer(table['idTextRows'], 0, table['visibleRows'])
    if table['status'] == 'absent':
        _need(table['visibleRows'] == table['idTextRows'] == 0)
    if table['status'] == 'elided_at_limit':
        _need(event['elisions'] > 0)
    joins, fields = _targets(value['targets'])
    _need(joins['exact_id_text'] <= table['idTextRows'])
    for target in value['targets']:
        join = target['log']['join']
        if join != 'not_attempted':
            _need((join == 'table_absent') == (table['status'] == 'absent'))
        if join == 'not_visible_elided':
            _need(table['status'] == 'elided_at_limit')
        if join == 'not_visible':
            _need(table['status'] == 'printed_complete')
    _fixed(value['selection'], {'policy': 'distinct_observed_config_base_ids', 'targets': len(value['targets']),
                                 'eventIndex': 'caller_declared'})
    _object(value['counts'], ('targets', 'logJoins', 'fieldComparisons'))
    _integer(value['counts']['targets'], 1, 64)
    _need(value['counts']['targets'] == len(value['targets']))
    _counts(value['counts']['logJoins'], value['counts']['fieldComparisons'])
    _need(value['counts']['logJoins'] == joins and value['counts']['fieldComparisons'] == fields)
    _fixed(value['verification'], VERIFICATION)


def _packet(data, artifact):
    packet = _json(data, private=True)
    _object(packet, ('format', 'source', 'limitRecordsPerEvent', 'events'))
    _need(packet['format'] == 'tli-log-table-event-v1' and type(packet['source']) is dict)
    _integer(packet['limitRecordsPerEvent'], 1, 10 ** 64 - 1)
    _need(type(packet['events']) is list and len(packet['events']) == artifact['packet']['events'], 'binding_failed')
    for event in packet['events']:
        _object(event, ('firstLine', 'lastLine', 'records'))
        _need(type(event['firstLine']) is int and type(event['lastLine']) is int)
        _need(type(event['records']) is list)
        for record in event['records']:
            _object(record, ('line', 'text'))
            _need(type(record['line']) is int and type(record['text']) is str)
    event = packet['events'][artifact['event']['index']]
    records = event['records']
    _need(len(records) <= 20000 and all(len(row['text']) <= 512 for row in records), 'resource_limit')
    _need(len(records) == artifact['event']['lines'] and len(records) < packet['limitRecordsPerEvent'], 'binding_failed')
    _need(event['lastLine'] == event['firstLine'] + len(records) - 1
          and all(row['line'] == event['firstLine'] + index for index, row in enumerate(records)), 'binding_failed')
    framed, size = hashlib.sha256(), 0
    for record in records:
        encoded = record['text'].encode('utf-8')
        size += len(encoded) + 1
        _need(size <= 8 * 2 ** 20, 'resource_limit')
        framed.update(len(encoded).to_bytes(4, 'big'))
        framed.update(encoded)
    _need(framed.hexdigest() == artifact['event']['framedSha256'], 'binding_failed')


def _envelope(status, source, artifact, digest=None, size=None, reason=None):
    references = {'diagnostic': 'verified', 'error': 'artifact_verified', 'not_requested': 'not_requested',
                  'rejected': 'not_verified'}[status]
    return {'format': CANONICAL, 'version': VERSION, 'status': status, 'source_sha256': source,
            'artifact': copy.deepcopy(artifact), 'reason': reason,
            'integrity': {'sha256': digest, 'bytes': size, 'references': references,
                          'joins': 'producer_reported' if status == 'diagnostic' else 'not_attempted'}}


def rejected(code, source_sha256):
    """A visible fixed rejection, carrying no unvalidated producer payload."""
    _hash(source_sha256)
    _need(type(code) is str and code in REJECTIONS)
    return _envelope('rejected', source_sha256, None, reason=code)


def read(package, descriptor, source_sha256):
    """Return a canonical diagnostic and artifact origin after checking the declared byte references."""
    _hash(source_sha256)
    _tree(descriptor)
    _object(descriptor, DESCRIPTOR)
    _version(descriptor)
    _fixed(descriptor['verification'], VERIFICATION)
    status = descriptor['status']
    _need(status in ('not_requested', 'diagnostic', 'error'))
    if status == 'not_requested':
        _need(all(descriptor[key] is None for key in DESCRIPTOR if key not in (
            'version', 'witnessFormat', 'witnessVersion', 'status', 'verification', 'flags')))
        return _envelope(status, source_sha256, None), None
    _need(descriptor['file'] == FILE)
    _hash(descriptor['sha256'])
    path = Path(package) / FILE
    data = _bytes(path, 2 ** 20, 'artifact_missing')
    _need(hashlib.sha256(data).hexdigest() == descriptor['sha256'], 'integrity_failed')
    artifact = _json(data)
    _artifact(artifact, source_sha256)
    _need(artifact['status'] == status)
    for key, value in {'sourceSha256': artifact['source']['sha256'], 'sourceBytes': artifact['source']['bytes'],
                       'packetFile': artifact['packet']['file'], 'packetSha256': artifact['packet']['sha256'],
                       'packetBytes': artifact['packet']['bytes']}.items():
        _need(type(descriptor[key]) is type(value) and descriptor[key] == value, 'binding_failed')
    if artifact['source']['sha256'] is not None:
        source = _bytes(Path(package) / 'source.json', 16 * 2 ** 20, 'source_missing')
        _need(hashlib.sha256(source).hexdigest() == source_sha256 and len(source) == artifact['source']['bytes'], 'binding_failed')
    if status == 'diagnostic':
        _need(descriptor['error'] is None)
        _counts(descriptor['logJoins'], descriptor['fieldComparisons'])
        duplicated = {'eventIndex': artifact['event']['index'], 'framedSha256': artifact['event']['framedSha256'],
                      'targets': artifact['counts']['targets'], 'logJoins': artifact['counts']['logJoins'],
                      'fieldComparisons': artifact['counts']['fieldComparisons']}
        for key, value in duplicated.items():
            _need(type(descriptor[key]) is type(value) and descriptor[key] == value, 'binding_failed')
        packet = _bytes(Path(package) / PACKET, 16 * 2 ** 20, 'packet_missing')
        _need(len(packet) == artifact['packet']['bytes'] and hashlib.sha256(packet).hexdigest() == artifact['packet']['sha256'], 'binding_failed')
        _packet(packet, artifact)
    else:
        _need(descriptor['error'] == artifact['error'] and all(descriptor[key] is None for key in (
            'eventIndex', 'framedSha256', 'targets', 'logJoins', 'fieldComparisons')))
    result = _envelope(status, source_sha256, artifact, descriptor['sha256'], len(data))
    return result, (str(path.resolve()), descriptor['sha256'], len(data), 1)


def summary(canonical):
    """Revalidate detached safe diagnostics without claiming a fresh byte check or producer execution."""
    _tree(canonical)
    _object(canonical, ('format', 'version', 'status', 'source_sha256', 'artifact', 'reason', 'integrity'))
    _need(canonical['format'] == CANONICAL and canonical['version'] == VERSION, 'unsupported_version')
    _hash(canonical['source_sha256'])
    status = canonical['status']
    _need(status in ('diagnostic', 'error', 'not_requested', 'rejected'))
    integrity = canonical['integrity']
    _object(integrity, ('sha256', 'bytes', 'references', 'joins'))
    if status in ('diagnostic', 'error'):
        _artifact(canonical['artifact'], canonical['source_sha256'])
        _need(canonical['artifact']['status'] == status and canonical['reason'] is None)
        _hash(integrity['sha256'])
        _integer(integrity['bytes'], 1, 2 ** 20)
    else:
        _need(canonical['artifact'] is None and integrity['sha256'] is None and integrity['bytes'] is None)
        _need((type(canonical['reason']) is str and canonical['reason'] in REJECTIONS)
              if status == 'rejected' else canonical['reason'] is None)
    expected = _envelope(status, canonical['source_sha256'], canonical['artifact'], integrity['sha256'],
                         integrity['bytes'], canonical['reason'])
    _need(canonical == expected)
    return copy.deepcopy(canonical)
