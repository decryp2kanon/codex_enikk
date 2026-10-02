import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import check_codex_compat as compat


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='enikk-compat-unit-')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_version_parser(self):
        self.assertEqual(compat.parse_version('codex-cli 0.158.0\n'),'0.158.0')
        self.assertEqual(compat.parse_version('codex-cli 0.160.0-beta.1'),'0.160.0-beta.1')
        with self.assertRaises(compat.Failure):compat.parse_version('unrelated 0.158.0')

    def test_binary_validation(self):
        with self.assertRaises(compat.Failure):compat.validate_binary(self.root/'missing')
        f=self.root/'candidate';f.write_text('test')
        with self.assertRaises(compat.Failure):compat.validate_binary(f)
        f.chmod(0o700);self.assertEqual(compat.validate_binary(f),f)
        with self.assertRaises(compat.Failure):compat.validate_binary(self.root)

    def test_required_cli_options(self):
        compat.validate_cli(' '.join(compat.CLI_OPTIONS))
        with self.assertRaises(compat.Failure):compat.validate_cli('--remote --no-daemon')

    def events(self):
        return [{'method':'item/agentMessage/delta'},
                {'method':'item/completed','params':{'item':{'type':'agentMessage'}}},
                {'method':'turn/completed','params':{'turn':{'status':'completed'}}}]

    def test_event_validation(self):
        compat.validate_stream(self.events(),[(0,{'text':'완료야.'})])

    def test_missing_delta_incompatible(self):
        with self.assertRaises(compat.Failure):compat.validate_stream(self.events()[1:],[(0,{})])

    def test_non_incremental_sentence_incompatible(self):
        with self.assertRaises(compat.Failure):compat.validate_stream(self.events(),[(1,{})])
        with self.assertRaises(compat.Failure):compat.validate_stream(self.events(),[])

    def test_completion_before_rpc_reply_is_not_lost(self):
        client=compat.Client.__new__(compat.Client)
        client.events=[{'method':'turn/completed','params':{'turn':{'id':'t','status':'completed'}}}]
        self.assertEqual(client.finish_turn('t')['status'],'completed')

    def test_missing_required_sqlite_field(self):
        c=sqlite3.connect(':memory:');self.addCleanup(c.close)
        c.execute('create table threads(id)')
        with self.assertRaises(compat.Failure):compat.schema_fields(c,compat.FIELDS['state_5.sqlite'])

    def test_harmless_extra_sqlite_field(self):
        c=sqlite3.connect(':memory:');self.addCleanup(c.close)
        c.execute('create table threads(id, rollout_path, harmless_new_field)')
        result=compat.schema_fields(c,compat.FIELDS['state_5.sqlite'])
        self.assertIn('harmless_new_field',result['threads'])

    def fake(self,body):
        f=self.root/'candidate';f.write_text('#!/usr/bin/env python3\n'+body);f.chmod(0o700);return f

    def args(self,binary,timeout=30):
        return argparse.Namespace(binary=str(binary),auth_file=str(self.root/'no-auth'),model=None,timeout=timeout,json=False)

    def test_failure_cleanup_and_candidate_unchanged(self):
        f=self.fake("import sys\nprint('codex-cli 0.158.0' if '--version' in sys.argv else 'missing options')\n")
        before=f.read_bytes();r=compat.execute(self.args(f))
        self.assertEqual(r['result'],'INCOMPATIBLE')
        self.assertFalse(Path(r['temporary_CODEX_HOME']).parent.exists())
        self.assertEqual(f.read_bytes(),before)
        self.assertEqual(next(x for x in r['checks'] if x['name']=='shutdown/cleanup')['status'],'PASS')

    def test_timeout_and_cleanup(self):
        f=self.fake('import time\ntime.sleep(60)\n')
        r=compat.execute(self.args(f,timeout=1))
        self.assertEqual(r['result'],'INCOMPATIBLE');self.assertIn('TimeoutError',r['failure_reason'])
        self.assertFalse(Path(r['temporary_CODEX_HOME']).parent.exists())
        self.assertLess(r['runtime_seconds'],10)
        self.assertEqual(next(x for x in r['checks'] if x['name']=='shutdown/cleanup')['status'],'PASS')

    def test_json_output_and_exit_code(self):
        result={'result':'INCOMPATIBLE','checks':[],'failure_reason':'fixture','runtime_seconds':0,'slowest_check':'fixture'}
        output=io.StringIO()
        with patch.object(compat,'execute',return_value=result),contextlib.redirect_stdout(output):
            status=compat.main(['/nonexistent','--json'])
        self.assertEqual(status,1);self.assertEqual(json.loads(output.getvalue()),result)

    def test_failure_location_expected_observed(self):
        checks=compat.Checks()
        with self.assertRaises(compat.Failure):
            checks.check('CLI',lambda:compat.validate_cli('no flags'))
        self.assertEqual(checks.checks[0]['name'],'CLI')
        self.assertIn('missing',checks.checks[0]['observed'])
