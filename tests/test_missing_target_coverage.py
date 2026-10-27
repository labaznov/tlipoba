"""Synthetic coverage regressions, stale-panel-json-warning clause 19."""
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from test_damage_archive import facts, game, native, package
from damage_lab.importer import main

class MissingTargetEndToEnd(unittest.TestCase):
    def test_newer_resolved_cohort_without_10103_reaches_all_outputs_as_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pkg=package(root);source=game(root,'43721.25')
            prefix='[2001.02.03-04.05.09:000][715]TLLua: Display: [Game] RoleAttrMgr@'
            with source.open('a',encoding='utf8') as stream:
                stream.write(prefix+'Attri.Id Cold Penetration 11000\n'+prefix+'[1] = 55\n')
            out=root/'out'
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                code=main(['--package',str(pkg),'--output',str(out),'--facts',str(facts(root)),
                           '--native-stats',str(native(root,pkg)),'--game-log',str(source)])
            record=json.loads((out/'import.json').read_text(encoding='utf8'))
            page=(out/'index.html').read_text(encoding='utf8')
            with contextlib.closing(sqlite3.connect(out/'database.sqlite')) as db:
                docs=dict(db.execute('select role,json from documents'))
            selected=json.loads(docs['panel_log_selection'])
            raw=json.loads(docs['panel_log'])
            self.assertEqual((code, raw['cohorts'][-1]['status'],
                              [x['id'] for x in raw['cohorts'][-1]['attributes']],
                              record['panel_log']['newer_state_conflict'],
                              selected['summary']['newer_state_conflict'],
                              'current-state comparison is unknown' in page,
                              record['panel_log']['identity_verified']),
                             (0,'resolved',['11000'],None,None,True,False))

class MissingTargetSelection(unittest.TestCase):
    def test_a_tied_resolved_missing_target_is_unknown(self):
        import copy
        from test_logstats import document
        from damage_lab.logstats import select
        data=document();later=copy.deepcopy(data['cohorts'][0]);later['attributes']=[a for a in later['attributes'] if a['id']!='10103'];data['cohorts'].append(later)
        self.assertIsNone(select(data,3217)['summary']['newer_state_conflict'])

    def test_a_strictly_older_resolved_missing_target_does_not_block(self):
        import copy
        from test_logstats import document
        from damage_lab.logstats import select
        data=document();older=copy.deepcopy(data['cohorts'][0]);older.update(timestamp='2026-10-19T13:16:38.731Z');older['attributes']=[a for a in older['attributes'] if a['id']!='10103'];data['cohorts'].append(older)
        self.assertIs(select(data,3217)['summary']['newer_state_conflict'],False)

    def test_a_proven_newer_conflict_remains_true_despite_missing_target(self):
        import copy
        from test_logstats import document
        from damage_lab.logstats import select
        data=document();missing=copy.deepcopy(data['cohorts'][0]);missing.update(timestamp='2026-10-19T13:18:38.731Z');missing['attributes']=[a for a in missing['attributes'] if a['id']!='10103']
        conflict=copy.deepcopy(data['cohorts'][0]);conflict.update(timestamp='2026-10-19T13:19:38.731Z');conflict['attributes'][0].update(raw_values=['9999'],values=[9999.0]);data['cohorts'].extend([missing,conflict])
        self.assertIs(select(data,3217)['summary']['newer_state_conflict'],True)
