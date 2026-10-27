import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.conditionalcli import main


def record():
    """An automatic synthetic import with a detected conditional row and unavailable raw pools."""
    from test_buildinputs import record as automatic
    from test_staticcombat import conditional
    from damage_lab.staticcombat import project
    data = automatic()
    data['static_combat'] = project(conditional(), data['source_sha256'])
    return data


def context():
    """Only fight conditions, never manual character damage, critical or cast data."""
    from test_rawcombat import scenario
    data = scenario()
    return {'format': 'tli-conditional-combat-context-v1',
            **{key: data[key] for key in ('topology', 'target', 'uptime', 'gates', 'missing', 'notes')},
            'condition': {'cursed': None, 'evidence': []},
            'coverage': {'status': 'unknown', 'evidence': []}}


class ConditionalCliTests(unittest.TestCase):
    """Run the real automatic importer, assembler and evaluator on fictional input files."""

    def test_automatic_command_saves_a_blocked_result_without_manual_character_stats(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            (root / 'import.json').write_text(json.dumps(record()), encoding='utf-8')
            (root / 'context.json').write_text(json.dumps(context()), encoding='utf-8')
            self.assertEqual(main(['--import', str(root / 'import.json'), '--skill', 'gem[1]',
                                   '--context', str(root / 'context.json'), '--output', str(root / 'result')]), 0)

    def test_output_keeps_automatic_raw_groups_null_and_separate_exact_file_origins(self):
        import hashlib

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            imported = json.dumps(record()).encode('utf-8')
            declared = json.dumps(context()).encode('utf-8')
            (root / 'import.json').write_bytes(imported)
            (root / 'context.json').write_bytes(declared)
            main(['--import', str(root / 'import.json'), '--skill', 'gem[1]', '--context', str(root / 'context.json'),
                  '--output', str(root / 'result')])
            report = json.loads((root / 'result/conditional-combat.json').read_text(encoding='utf-8'))
            spell = report['automatic_inputs']['raw_spell']
            self.assertEqual((report['origins']['import']['sha256'], report['origins']['context']['sha256'],
                              [spell[name] for name in ('damage', 'critical', 'casting', 'double_damage')],
                              report['calculation']['status'], report['calculation']['dps'],
                              report['calculation']['applied_rows'], spell['context']['effective_level']),
                             (hashlib.sha256(imported).hexdigest(), hashlib.sha256(declared).hexdigest(),
                              [None] * 4, 'blocked', None, [], None))

    def test_manual_spell_override_and_missing_alias_or_ledger_are_refused_atomically(self):
        for problem in ('spell', 'alias', 'ledger', 'missing-context'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
                root = Path(folder)
                supplied, declared = record(), context()
                alias = 'gem[1]'
                if problem == 'spell':
                    declared['spell'] = {'damage': 999}
                elif problem == 'alias':
                    alias = 'gem[999]'
                elif problem == 'ledger':
                    del supplied['static_combat']
                (root / 'import.json').write_text(json.dumps(supplied), encoding='utf-8')
                if problem != 'missing-context':
                    (root / 'context.json').write_text(json.dumps(declared), encoding='utf-8')
                code = main(['--import', str(root / 'import.json'), '--skill', alias,
                             '--context', str(root / 'context.json'), '--output', str(root / 'result')])
                self.assertEqual((code, (root / 'result').exists()), (1, False))

    def test_json_duplicates_nonfinite_underflow_and_input_limits_are_refused(self):
        for side, raw in (('import', b'{"x":1,"x":2}'), ('context', b'{"x":NaN}'),
                          ('context', b'{"x":1e-999}'), ('context', b'{"x":1e999}'),
                          ('import', b' ' * (4 * 1024**2 + 1)), ('context', b' ' * (1024**2 + 1))):
            with self.subTest(side=side, bytes=len(raw)), tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
                root = Path(folder)
                (root / 'import.json').write_text(json.dumps(record()), encoding='utf-8')
                (root / 'context.json').write_text(json.dumps(context()), encoding='utf-8')
                (root / (side + '.json')).write_bytes(raw)
                code = main(['--import', str(root / 'import.json'), '--skill', 'gem[1]',
                             '--context', str(root / 'context.json'), '--output', str(root / 'result')])
                self.assertEqual((code, (root / 'result').exists()), (1, False))

    def test_source_mismatch_and_condition_evidence_do_not_leak_private_error_content(self):
        for problem in ('source', 'proof'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                supplied, declared = record(), context()
                supplied['PRIVATE-EXTRA-CANARY'] = 'ignored'
                if problem == 'source':
                    supplied['source_sha256'] = 'b' * 64
                else:
                    declared['condition'] = {'cursed': True, 'evidence': []}
                (root / 'import.json').write_text(json.dumps(supplied), encoding='utf-8')
                (root / 'context.json').write_text(json.dumps(declared), encoding='utf-8')
                error = io.StringIO()
                with contextlib.redirect_stderr(error):
                    code = main(['--import', str(root / 'import.json'), '--skill', 'gem[1]',
                                 '--context', str(root / 'context.json'), '--output', str(root / 'result')])
                self.assertEqual((code, 'PRIVATE-EXTRA-CANARY' in error.getvalue(), (root / 'result').exists()),
                                 (1, False, False))

    def test_existing_outputs_and_dangling_symlinks_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            output = root / 'existing'
            output.mkdir()
            (output / 'foreign').write_text('preserve', encoding='utf-8')
            args = ['--import', str(root / 'absent.json'), '--skill', 'gem[1]', '--context', str(root / 'absent-context.json')]
            code = main(args + ['--output', str(output)])
            self.assertEqual((code, (output / 'foreign').read_text(encoding='utf-8')), (1, 'preserve'))
            link = root / 'dangling'
            try:
                link.symlink_to(root / 'missing', target_is_directory=True)
            except OSError:
                return
            self.assertEqual((main(args + ['--output', str(link)]), link.is_symlink()), (1, True))

    def test_v2_command_publishes_a_spell_blocked_report_with_exact_file_hashes(self):
        import hashlib

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            declared = context()
            declared['format'] = 'tli-conditional-combat-context-v2'
            declared['topology'] = dict(declared['topology'], base=None)
            declared['gates']['hit_topology'] = {'status': 'unknown', 'evidence': []}
            imported = json.dumps(record()).encode('utf-8')
            raw_context = json.dumps(declared).encode('utf-8')
            (root / 'import.json').write_bytes(imported)
            (root / 'context.json').write_bytes(raw_context)
            code = main(['--import', str(root / 'import.json'), '--skill', 'gem[1]',
                         '--context', str(root / 'context.json'), '--output', str(root / 'result')])
            self.assertEqual(code, 0)
            body = json.loads((root / 'result' / 'conditional-combat.json').read_text(encoding='utf-8'))
            page = (root / 'result' / 'index.html').read_text(encoding='utf-8')
            spell = body['automatic_inputs']['raw_spell']
            self.assertEqual((code, body['version'], body['context']['topology']['base'],
                              body['calculation']['scenario']['format'], body['calculation']['scenario']['topology']['base'],
                              body['origins']['import']['sha256'], body['origins']['context']['sha256'],
                              body['calculation']['dps'], [spell[name] for name in ('damage', 'critical', 'casting', 'double_damage')],
                              '<p>База Tangle: неизвестно</p>' in page, (root / 'result' / 'foreign').exists()),
                             (0, '0.1.1', None, 'tli-raw-cold-combat-v2', None,
                              hashlib.sha256(imported).hexdigest(), hashlib.sha256(raw_context).hexdigest(),
                              None, [None] * 4, True, False))

    def test_v2_command_keeps_known_bases_zero_and_two_without_numeric_geometry(self):
        import hashlib

        for base in (0, 2):
            with self.subTest(base=base), tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
                root = Path(folder)
                declared = context()
                declared['format'] = 'tli-conditional-combat-context-v2'
                declared['topology'] = dict(declared['topology'], base=base)
                imported = json.dumps(record()).encode('utf-8')
                raw_context = json.dumps(declared).encode('utf-8')
                (root / 'import.json').write_bytes(imported)
                (root / 'context.json').write_bytes(raw_context)
                code = main(['--import', str(root / 'import.json'), '--skill', 'gem[1]',
                             '--context', str(root / 'context.json'), '--output', str(root / 'result')])
                self.assertEqual(code, 0)
                body = json.loads((root / 'result' / 'conditional-combat.json').read_text(encoding='utf-8'))
                spell = body['automatic_inputs']['raw_spell']
                published = body['context']['topology']['base']
                scenario = body['calculation']['scenario']['topology']['base']
                self.assertEqual((body['version'], type(published) is int, published, type(scenario) is int, scenario,
                                  body['calculation']['scenario']['format'], body['calculation']['dps'],
                                  body['calculation']['result']['topology'], body['calculation']['result']['factors'],
                                  'topology.base: unavailable' in body['calculation']['gaps'],
                                  [spell[name] for name in ('damage', 'critical', 'casting', 'double_damage')],
                                  body['origins']['import']['sha256'], body['origins']['context']['sha256']),
                                 ('0.1.1', True, base, True, base, 'tli-raw-cold-combat-v2', None, None, None, False,
                                  [None] * 4, hashlib.sha256(imported).hexdigest(), hashlib.sha256(raw_context).hexdigest()))

    def test_checked_in_v2_example_keeps_the_unknown_base_and_refuses_overwrite(self):
        import hashlib

        example = Path(__file__).resolve().parents[1] / 'examples' / 'conditional-context-v2.json'
        raw_context = example.read_bytes()
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            imported = json.dumps(record()).encode('utf-8')
            (root / 'import.json').write_bytes(imported)
            code = main(['--import', str(root / 'import.json'), '--skill', 'gem[1]',
                         '--context', str(example), '--output', str(root / 'result')])
            self.assertEqual(code, 0)
            body = json.loads((root / 'result' / 'conditional-combat.json').read_text(encoding='utf-8'))
            spell = body['automatic_inputs']['raw_spell']
            self.assertEqual((body['version'], body['context']['topology']['base'],
                              body['calculation']['scenario']['topology']['base'],
                              'topology.base: unavailable' in body['calculation']['gaps'],
                              body['calculation']['dps'], body['calculation']['result']['topology'],
                              body['calculation']['result']['factors'],
                              [spell[name] for name in ('damage', 'critical', 'casting', 'double_damage')],
                              body['origins']['context']['sha256'], body['origins']['import']['sha256'],
                              body['origins']['context']['bytes']),
                             ('0.1.1', None, None, True, None, None, None, [None] * 4,
                              hashlib.sha256(raw_context).hexdigest(), hashlib.sha256(imported).hexdigest(), len(raw_context)))
            existing = root / 'existing'
            existing.mkdir()
            (existing / 'foreign').write_text('preserve', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                refused = main(['--import', str(root / 'import.json'), '--skill', 'gem[1]',
                                '--context', str(example), '--output', str(existing)])
            self.assertEqual((refused, (existing / 'foreign').read_text(encoding='utf-8')), (1, 'preserve'))
