import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DebugTests(unittest.TestCase):
    def test_follows_new_runs_rotation_and_ctrl_c_cleans_only_viewer(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)
            for name in ('one','two'):
                run=state/'runs'/name;run.mkdir(parents=True)
                (run/'notify.log').write_text(name+' initial\n')
            def select(name):
                (state/'status.json').write_text(json.dumps({'state':'ready','generation':name,
                    'run':str(state/'runs'/name),'last_error':None}))
            select('one')
            output=state/'viewer.log'
            with output.open('wb') as out:
                child=subprocess.Popen([sys.executable,'-B',str(ROOT/'enikk_tts'),'--tts-debug'],
                    env=os.environ|{'ENIKK_TTS_STATE':str(state)},stdout=out,stderr=out)
                def wait(text):
                    end=time.monotonic()+5
                    while time.monotonic()<end:
                        if text in output.read_text():return
                        time.sleep(.05)
                    self.fail(output.read_text())
                try:
                    wait('one initial')
                    tail_pids=Path('/proc',str(child.pid),'task',str(child.pid),'children').read_text().split()
                    select('two')
                    wait('two initial')
                    for pid in tail_pids:self.assertFalse(Path('/proc',pid).exists())
                    log=state/'runs/two/notify.log'
                    log.rename(log.with_suffix('.old'))
                    log.write_text('rotated output\n')
                    wait('rotated output')
                    tail_pids=Path('/proc',str(child.pid),'task',str(child.pid),'children').read_text().split()
                    child.send_signal(signal.SIGINT)
                    self.assertEqual(child.wait(5),0)
                    for pid in tail_pids:self.assertFalse(Path('/proc',pid).exists())
                    self.assertEqual(json.loads((state/'status.json').read_text())['generation'],'two')
                finally:
                    if child.poll() is None:
                        child.send_signal(signal.SIGINT);child.wait(5)
