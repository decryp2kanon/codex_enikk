"""Opt-in systemd smoke test; fake audio, isolated state, no production Codex."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_voice_process import ProcessTests, wait

fixture=ProcessTests('test_disconnect_cancels_voice_without_exiting_service')
fixture.setUp()
unit='enikk-tts-isolation-test-'+uuid.uuid4().hex[:10]+'.service'
env=os.environ|{'XDG_RUNTIME_DIR':'/run/user/'+str(os.getuid()),
                'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/'+str(os.getuid())+'/bus'}
control=lambda *args: subprocess.run(['systemctl','--user',*args,unit],env=env,check=True,capture_output=True,text=True)
try:
    args=['systemd-run','--user','--unit='+unit,'--property=KillMode=control-group',
          '--property=Restart=no','--property=TimeoutStopSec=8']
    for name in ('ENIKK_TTS_STATE','ENIKK_TTS_SOCKET','CODEX_ENIKK_CHATTERBOX_HOME','CODEX_HOME','PATH'):
        args.append('--setenv='+name+'='+fixture.env[name])
    args += ['/usr/bin/python3','-B',str(fixture.code/'independent_service.py')]
    wrapper=fixture.root/'wrapper.py'
    wrapper.write_text('import sys,subprocess\nsys.path.insert(0,'+repr(str(ROOT))+')\nimport enikk\nwith enikk.owned_processes():\n    subprocess.run('+repr(args)+',check=True)\n')
    subprocess.run(['/usr/bin/python3',str(wrapper)],env=env,check=True)
    # The wrapper has exited and run its subreaper cleanup; unit must survive.
    first=wait(lambda:fixture.status() if fixture.status().get('state')=='ready' else False)
    assert control('is-active').stdout.strip()=='active'
    control('start')
    assert fixture.status()['pid']==first['pid']
    worker=json.loads((Path(first['run'])/'model-ready.json').read_text())['pid']
    cgroup=Path('/proc',str(first['pid']),'cgroup').read_text()
    assert unit in cgroup
    control('stop')
    assert (Path(first['run'])/'cancelled').exists()
    assert not Path('/proc',str(worker)).exists()
    subprocess.run(args,env=env,check=True,capture_output=True)
    second=wait(lambda:fixture.status() if fixture.status().get('state')=='ready' and fixture.status().get('generation')!=first['generation'] else False)
    control('kill','--kill-who=main','--signal=SIGKILL')
    wait(lambda:not Path('/proc',str(second['pid'])).exists())
    subprocess.run(['systemctl','--user','reset-failed',unit],env=env,capture_output=True)
    subprocess.run(args,env=env,check=True,capture_output=True)
    third=wait(lambda:fixture.status() if fixture.status().get('state')=='ready' and fixture.status().get('generation')!=second['generation'] else False)
    fixture.stop.set();fixture.heartbeat.join(2)
    wait(lambda:fixture.status().get('state')=='waiting_for_core',8)
    assert control('is-active').stdout.strip()=='active'
    print(json.dumps({'status':'PASS','unit':unit,'wrapper_cleanup':'voice_survived',
        'stop':'voice_children_gone','crash_restart':'new_generation','core_absent':'service_waits',
        'generations':[first['generation'],second['generation'],third['generation']]},indent=2))
finally:
    subprocess.run(['systemctl','--user','stop',unit],env=env,capture_output=True)
    subprocess.run(['systemctl','--user','reset-failed',unit],env=env,capture_output=True)
    fixture.doCleanups()
