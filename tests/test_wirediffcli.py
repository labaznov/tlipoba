"""Local diagnostic publication uses synthetic reports and real temporary files."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.__main__ import main
from test_wirediff import artifact


class WireDiffCliTest(unittest.TestCase):
    """Publish a private counts-only diagnostic without modifying the input sources."""

    def test_native_diff_command_publishes_counts_json_and_passive_html(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            before, after = b'first synthetic source', b'second synthetic source'
            (root / 'a.json').write_bytes(before)
            (root / 'b.json').write_bytes(after)
            (root / 'diff.json').write_text(json.dumps(artifact(before, after)), encoding='utf-8')
            code = main(['native-diff', '--artifact', str(root / 'diff.json'), '--source-a', str(root / 'a.json'),
                         '--source-b', str(root / 'b.json'), '--output', str(root / 'result')])
            result = json.loads((root / 'result/summary.json').read_text(encoding='utf-8'))
            self.assertEqual((code, result['counts']['rows'], sorted(path.name for path in (root / 'result').iterdir())),
                             (0, 1, ['index.html', 'summary.json']))

    def test_existing_output_is_preserved_before_missing_inputs_are_read(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()) as errors:
            root = Path(directory)
            (root / 'result').write_bytes(b'preserve this file')
            code = main(['native-diff', '--artifact', str(root / 'missing'), '--source-a', str(root / 'a'),
                         '--source-b', str(root / 'b'), '--output', str(root / 'result')])
            self.assertEqual((code, (root / 'result').read_bytes(), 'уже существует' in errors.getvalue()),
                             (1, b'preserve this file', True))

    def test_missing_required_arguments_return_a_private_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            code = main(['native-diff', '--artifact', 'private-path-canary'])
        self.assertEqual((code, 'private-path-canary' in errors.getvalue()), (1, False))

    def test_unknown_arguments_cannot_echo_private_values(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            code = main(['native-diff', '--unknown', 'private-path-canary'])
        self.assertEqual((code, 'private-path-canary' in errors.getvalue()), (1, False))

    def test_invalid_reports_cannot_echo_private_contents_or_create_output(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()) as errors:
            root = Path(directory)
            (root / 'artifact').write_bytes(b'private-payload-canary')
            (root / 'a').write_bytes(b'left source')
            (root / 'b').write_bytes(b'right source')
            code = main(['native-diff', '--artifact', str(root / 'artifact'), '--source-a', str(root / 'a'),
                         '--source-b', str(root / 'b'), '--output', str(root / 'result')])
            self.assertEqual((code, (root / 'result').exists(), 'private-payload-canary' in errors.getvalue()),
                             (1, False, False))

    def test_publication_preserves_all_three_inputs(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            before, after = b'original amber source', b'original jade source'
            report = json.dumps(artifact(before, after)).encode()
            for name, raw in (('artifact', report), ('a', before), ('b', after)):
                (root / name).write_bytes(raw)
            main(['native-diff', '--artifact', str(root / 'artifact'), '--source-a', str(root / 'a'),
                  '--source-b', str(root / 'b'), '--output', str(root / 'result')])
            self.assertEqual(tuple((root / name).read_bytes() for name in ('artifact', 'a', 'b')),
                             (report, before, after))

    def test_html_contains_no_raw_row_or_source_canary(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            before, after = b'private-amber-source', b'private-jade-source'
            (root / 'artifact').write_text(json.dumps(artifact(before, after)), encoding='utf-8')
            (root / 'a').write_bytes(before)
            (root / 'b').write_bytes(after)
            main(['native-diff', '--artifact', str(root / 'artifact'), '--source-a', str(root / 'a'),
                  '--source-b', str(root / 'b'), '--output', str(root / 'result')])
            page = (root / 'result/index.html').read_text(encoding='utf-8')
            self.assertFalse(any(text in page for text in ('private-amber', 'private-jade', '<script', '1.3')))

    def test_failed_publication_leaves_no_temporary_result(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            root = Path(directory)
            before, after = b'amber', b'jade'
            (root / 'artifact').write_text(json.dumps(artifact(before, after)), encoding='utf-8')
            (root / 'a').write_bytes(before)
            (root / 'b').write_bytes(after)
            (root / 'parent').write_bytes(b'ordinary file')
            code = main(['native-diff', '--artifact', str(root / 'artifact'), '--source-a', str(root / 'a'),
                         '--source-b', str(root / 'b'), '--output', str(root / 'parent/result')])
            self.assertEqual((code, sorted(path.name for path in root.iterdir())),
                             (1, ['a', 'artifact', 'b', 'parent']))

    def test_summary_refusals_show_only_the_fixed_reason(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()) as errors:
            root = Path(directory)
            before, after = b'left source', b'right source'
            report = artifact(before, after)
            report['version'] = 'private-version-canary'
            (root / 'artifact').write_text(json.dumps(report), encoding='utf-8')
            (root / 'a').write_bytes(before)
            (root / 'b').write_bytes(after)
            code = main(['native-diff', '--artifact', str(root / 'artifact'), '--source-a', str(root / 'a'),
                         '--source-b', str(root / 'b'), '--output', str(root / 'result')])
            self.assertEqual((code, errors.getvalue()), (1, 'Ошибка диагностики: producer_unsupported\n'))

    def test_oversized_artifacts_are_refused_without_publication(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()) as errors:
            root = Path(directory)
            (root / 'artifact').write_bytes(b' ' * (1024 * 1024 + 13))
            (root / 'a').write_bytes(b'amber')
            (root / 'b').write_bytes(b'jade')
            code = main(['native-diff', '--artifact', str(root / 'artifact'), '--source-a', str(root / 'a'),
                         '--source-b', str(root / 'b'), '--output', str(root / 'result')])
            self.assertEqual((code, (root / 'result').exists(), errors.getvalue()),
                             (1, False, 'Ошибка диагностики: artifact_too_large\n'))

    def test_html_preserves_omission_and_privacy_suppression_counts(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            before, after = b'amber', b'jade'
            report = artifact(before, after)
            report['counts']['privacySuppressedKeys'] = 17
            report['counts']['omitted']['b']['free text string'] = 23
            (root / 'artifact').write_text(json.dumps(report), encoding='utf-8')
            (root / 'a').write_bytes(before)
            (root / 'b').write_bytes(after)
            main(['native-diff', '--artifact', str(root / 'artifact'), '--source-a', str(root / 'a'),
                  '--source-b', str(root / 'b'), '--output', str(root / 'result')])
            page = (root / 'result/index.html').read_text(encoding='utf-8')
            self.assertTrue('privacySuppressedKeys' in page and 'free text string' in page
                            and '17' in page and '23' in page)
