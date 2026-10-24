import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from damage_lab.skillbundle import read


def saved(directory, artifact, descriptor):
    raw = json.dumps(artifact, allow_nan=False).encode('utf-8')
    (directory / 'installed-skills.json').write_bytes(raw)
    descriptor['sha256'] = hashlib.sha256(raw).hexdigest()


def fixture(directory):
    from test_installedskills import document

    if not (directory / 'source.json').exists():
        (directory / 'source.json').write_bytes(b'{}')
    source = hashlib.sha256((directory / 'source.json').read_bytes()).hexdigest()
    artifact = document()
    artifact['source']['sha256'] = source
    descriptor = {
        'file': 'installed-skills.json', 'status': 'diagnostic', 'version': '0.1.2', 'sourceSha256': source,
        'runtimeVerified': False, 'identityVerified': False, 'importComplete': False,
        'clientRows': artifact['domains']['client']['rows'],
        'serverReconciled': artifact['domains']['server']['reconciled'],
        'relationships': len(artifact['relationships']), 'issues': len(artifact['issues'])}
    saved(directory, artifact, descriptor)
    return artifact, descriptor


def attached(directory, *, failure=False):
    """Add a synthetic installation descriptor to an existing synthetic package."""
    artifact, descriptor = error(directory, 'source_shape') if failure else fixture(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    manifest['installedSkills'] = descriptor
    (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return artifact, descriptor


def error(directory, code, *, unbound=False):
    _, descriptor = fixture(directory)
    artifact = {'format': 'tli-support-inventory-error-v1', 'version': '0.1.0', 'status': 'error', 'error': code,
                'source': {'file': 'source.json', 'sha256': None if unbound else descriptor['sourceSha256']},
                'runtimeVerified': False, 'identityVerified': False, 'importComplete': False}
    descriptor.update(status='error', error=code)
    if unbound:
        descriptor['sourceSha256'] = None
    for field in ('clientRows', 'serverReconciled', 'relationships', 'issues'):
        descriptor[field] = None
    saved(directory, artifact, descriptor)
    return artifact, descriptor


class SkillBundleTest(unittest.TestCase):
    """Bind an installation-only inventory to saved package bytes without promoting its gates."""

    def test_diagnostic_bundle_keeps_its_source_binding_and_unverified_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor = fixture(directory)
            data, origin = read(directory, descriptor, descriptor['sourceSha256'])
            self.assertEqual((data['source']['sha256'], data['runtime']['activation'], origin[1], origin[-1]),
                             (descriptor['sourceSha256'], 'unknown', descriptor['sha256'], 1))

    def test_descriptor_file_version_source_and_flags_are_strict(self):
        for field, value in (('file', '../installed-skills.json'), ('version', '0.1.1'), ('sourceSha256', 'e' * 64),
                             ('runtimeVerified', 0), ('identityVerified', True), ('importComplete', True),
                             ('status', 'ready')):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor = fixture(directory)
                source = descriptor['sourceSha256']
                descriptor[field] = value
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source)

    def test_artifact_hash_and_rehashed_source_mismatch_are_rejected(self):
        for change in ('bytes', 'source'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor = fixture(directory)
                if change == 'bytes':
                    with (directory / 'installed-skills.json').open('ab') as handle:
                        handle.write(b' ')
                else:
                    artifact['source']['sha256'] = 'd' * 64
                    saved(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, descriptor['sourceSha256'])

    def test_counts_match_the_validated_inventory_without_bool_or_zero_fallbacks(self):
        for field, value in (('clientRows', True), ('serverReconciled', -1), ('relationships', 700), ('issues', None)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor = fixture(directory)
                descriptor[field] = value
                with self.assertRaises(ValueError):
                    read(directory, descriptor, descriptor['sourceSha256'])

    def test_source_bound_producer_error_is_a_gap_without_inventory_or_zero_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor = error(directory, 'source_too_large')
            data, origin = read(directory, descriptor, descriptor['sourceSha256'])
            self.assertEqual((data, origin[-1]), (None, 0))

    def test_only_unread_source_errors_can_lack_a_source_hash(self):
        for code in ('source_missing', 'source_unreadable'):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor = error(directory, code, unbound=True)
                self.assertIsNone(read(directory, descriptor, hashlib.sha256(b'{}').hexdigest())[0])

    def test_error_contract_rejects_inconsistent_codes_counts_claims_and_sources(self):
        for change in ('code', 'count', 'verification', 'source', 'version', 'unbound'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor = error(directory, 'source_not_json', unbound=change == 'unbound')
                if change == 'code':
                    artifact['error'] = 'private arbitrary error'
                elif change == 'count':
                    descriptor['clientRows'] = 0
                elif change == 'verification':
                    artifact['runtimeVerified'] = True
                elif change == 'source':
                    artifact['source']['file'] = '../source.json'
                elif change == 'version':
                    artifact['version'] = '0.1.2'
                saved(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, hashlib.sha256(b'{}').hexdigest())

    def test_bounded_strict_json_rejects_duplicate_nonfinite_and_oversize_inputs(self):
        for tail in (b',"private":1,"private":2}', b',"private":NaN}', b',"private":1e400}'):
            with self.subTest(tail=tail), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor = fixture(directory)
                path = directory / 'installed-skills.json'
                raw = path.read_bytes()[:-1] + tail
                path.write_bytes(raw)
                descriptor['sha256'] = hashlib.sha256(raw).hexdigest()
                with self.assertRaises(ValueError):
                    read(directory, descriptor, descriptor['sourceSha256'])
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor = fixture(directory)
            with self.assertRaisesRegex(ValueError, 'size'):
                read(directory, descriptor, descriptor['sourceSha256'], max_bytes=17)

    def test_byte_limits_are_positive_integers_before_file_access(self):
        for limit in (True, 0, -1, 1.5, None, float('nan'), float('inf'), 64 * 2 ** 20 + 1, 10 ** 400):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                read(Path('unread'), {}, 'a' * 64, max_bytes=limit)
