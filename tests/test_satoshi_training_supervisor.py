import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('satoshi_supervisor', ROOT/'satoshi_training_supervisor.py')
SUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUP)

class SatoshiSupervisorTests(unittest.TestCase):
    def test_extract_all_twelve_parts(self):
        text = '# Intro\nintro\n' + '\n'.join(f'## {i}. H{i}\nbody{i}' for i in range(1,11)) + '\n## 에필로그\nepilogue\n'
        self.assertIn('Intro', SUP.extract_part(text,1))
        self.assertTrue(SUP.extract_part(text,2).startswith('## 1. H1'))
        self.assertTrue(SUP.extract_part(text,11).startswith('## 10. H10'))
        self.assertTrue(SUP.extract_part(text,12).startswith('## 에필로그'))

    def test_receipt_requires_all_parts_played(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'job'
            played=path.with_name('.played-'+path.name)
            played.write_text('{"delivery":{"parts":["a","b"],"terminal":{"0":"PLAYED","1":"PLAYED"}}}')
            result=SUP.receipt(path)
            self.assertTrue(result[0])
            played.write_text('{"delivery":{"parts":["a","b"],"terminal":{"0":"PLAYED","1":"FAILED_EXPLICITLY"}}}')
            result=SUP.receipt(path)
            self.assertFalse(result[0])

    def test_failed_receipt_never_passes(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'job'
            failed=path.with_name('.failed-'+path.name)
            failed.write_text('{"delivery":{"parts":["a"],"terminal":{"0":"FAILED_EXPLICITLY"}}}')
            result=SUP.receipt(path)
            self.assertEqual(result[1],'FAILED')
            self.assertFalse(result[0])

    def test_checkpoint_retries_only_failed_parts_until_success(self):
        data={'delivery':{'parts':['a','b','c'],'terminal':{'0':'PLAYED','1':'FAILED_EXPLICITLY','2':'PLAYED'}}}
        state={}
        with tempfile.TemporaryDirectory() as td:
            state_path=Path(td)/'state.json'
            calls=[]
            outcomes=[(False,'FAILED',Path(td)/'f1',{'delivery':{'parts':['b'],'terminal':{'0':'FAILED_EXPLICITLY'}}}),
                      (True,'PLAYED',Path(td)/'p2',{'delivery':{'parts':['b'],'terminal':{'0':'PLAYED'}}})]
            def fake_publish(run,part,text,attempt):
                calls.append((part,text,attempt)); return Path(td)/'job'
            with patch.object(SUP,'publish',side_effect=fake_publish), patch.object(SUP,'wait_receipt',side_effect=outcomes), patch.object(SUP.time,'sleep'):
                result=SUP.retry_failed_parts(Path(td),2,data,10,state_path,state)
            self.assertEqual([c[1] for c in calls],['b','b'])
            self.assertEqual(result['parts'],3)
            self.assertEqual(result['completed_parts'],3)
            self.assertEqual(result['targeted_attempts'],2)

if __name__ == '__main__':
    unittest.main()
