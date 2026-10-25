"""Check fixed ordinary-file windows using synthetic temporary data."""

from pathlib import Path
import tempfile
import unittest

from damage_lab.logwindow import collect


class LogWindowTest(unittest.TestCase):
    """Keep bounded source bytes separate from original-file and runtime claims."""

    def test_a_small_file_keeps_all_bytes_and_exact_window_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'abc')
            result = collect(path, budget=7)
            self.assertEqual(result, (b'abc', {
                'format': 'tli-log-window-v1', 'origin_path': str(path.resolve()),
                'opened_bytes': 3, 'read_start': 0, 'read_end': 3, 'bytes_read': 3,
                'discarded_leading_bytes': 0, 'payload_start': 0, 'payload_bytes': 3,
                'payload_sha256': 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
                'original_sha256': None, 'line_scope': 'retained_window', 'atomic': False,
                'currentness': 'unknown'}))

    def test_a_suffix_discards_its_first_line_and_keeps_the_trailing_fragment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'old\nrow\nend\npartial')
            data, metadata = collect(path, budget=13)
        self.assertEqual((data, metadata['opened_bytes'], metadata['read_start'], metadata['read_end'],
                          metadata['bytes_read'], metadata['discarded_leading_bytes'], metadata['payload_start']),
                         (b'end\npartial', 19, 6, 19, 13, 2, 8))

    def test_a_suffix_without_lf_retains_no_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'0123456789')
            data, metadata = collect(path, budget=4)
        self.assertEqual((data, metadata['bytes_read'], metadata['discarded_leading_bytes'],
                          metadata['payload_start'], metadata['payload_bytes']), (b'', 4, 4, 10, 0))

    def test_only_exact_positive_integer_budgets_up_to_two_mib_are_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'x\ny')
            for budget in (True, False, 0, -3, 2 * 1024 ** 2 + 1, 1.5, '7', None):
                with self.subTest(budget=budget), self.assertRaisesRegex(
                        ValueError, '^Log window budget must be a positive integer up to 2 MiB$'):
                    collect(path, budget=budget)

    def test_an_empty_file_is_a_valid_empty_window_at_the_maximum_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'empty.log'
            path.write_bytes(b'')
            data, metadata = collect(path, budget=2 * 1024 ** 2)
        self.assertEqual((data, metadata['opened_bytes'], metadata['bytes_read'], metadata['payload_start'],
                          metadata['payload_sha256']),
                         (b'', 0, 0, 0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'))

    def test_crlf_is_retained_without_normalizing_the_trailing_fragment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'old\r\ncut\r\nkeep\r\nlast')
            data, metadata = collect(path, budget=13)
        self.assertEqual((data, metadata['read_start'], metadata['discarded_leading_bytes'], metadata['payload_start']),
                         (b'keep\r\nlast', 7, 3, 10))

    def test_a_split_utf8_leading_fragment_is_discarded_as_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'head\n\xe2\x82\xac\nkeep\npartial')
            data, metadata = collect(path, budget=15)
        self.assertEqual((data, metadata['read_start'], metadata['discarded_leading_bytes'], metadata['payload_start']),
                         (b'keep\npartial', 6, 3, 9))

    def test_a_complete_leading_line_is_conservatively_discarded_in_a_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'old\nfirst\nsecond\n')
            data, metadata = collect(path, budget=13)
        self.assertEqual((data, metadata['read_start'], metadata['discarded_leading_bytes'], metadata['payload_start']),
                         (b'second\n', 4, 6, 10))

    def test_an_exact_whole_file_budget_does_not_drop_the_first_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'first\nlast')
            data, metadata = collect(path, budget=10)
        self.assertEqual((data, metadata['discarded_leading_bytes']), (b'first\nlast', 0))

    def test_a_large_file_is_admitted_only_for_its_explicit_small_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.log'
            with path.open('wb') as stream:
                stream.write(b'start\n')
                stream.seek(3 * 1024 ** 2)
                stream.write(b'\nkept\npartial')
            data, metadata = collect(path, budget=64)
        self.assertEqual((data, metadata['bytes_read'], metadata['opened_bytes'], metadata['read_end']),
                         (b'kept\npartial', 64, 3 * 1024 ** 2 + 13, 3 * 1024 ** 2 + 13))

    def test_multiple_read_chunks_keep_the_same_fixed_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'prefix\n' + b'x' * 140001 + b'\nretained\nlast')
            data, metadata = collect(path, budget=131100)
        self.assertEqual((data, metadata['bytes_read']), (b'retained\nlast', 131100))

    def test_collection_does_not_change_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'older\nline\npartial')
            collect(path, budget=11)
            self.assertEqual(path.read_bytes(), b'older\nline\npartial')

    def test_a_directory_cannot_be_read_as_an_ordinary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((OSError, ValueError)):
                collect(directory, budget=17)

    def test_the_suffix_hash_identifies_only_the_returned_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.log'
            path.write_bytes(b'old\nskip\nabc')
            data, metadata = collect(path, budget=8)
        self.assertEqual((data, metadata['payload_sha256'], metadata['original_sha256']),
                         (b'abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad', None))
