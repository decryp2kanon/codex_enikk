#!/usr/bin/env python3
"""Automatic restart/graduation gate for satoshi.md TTS training parts."""
import argparse, hashlib, importlib.util, json, os, signal, subprocess, time
from pathlib import Path

STATE = Path.home()/'.local/state/codex_enikk'
TRAIN = STATE/'satoshi-training'
TTS = STATE/'tts'
SOURCE = Path.home()/'git/codex_enikk'
INSTALL = Path.home()/'.local/lib/codex_enikk'

def extract_part(text, part):
    lines=text.splitlines()
    heads=[i for i,x in enumerate(lines) if x.startswith('## ')]
    if part == 1:
        end=heads[0] if heads else len(lines)
        return '\n'.join(lines[:end]).strip()
    i=part-2
    if i < 0 or i >= len(heads):
        raise ValueError(f'part {part} boundary missing')
    start=heads[i]
    end=heads[i+1] if i+1 < len(heads) else len(lines)
    return '\n'.join(lines[start:end]).strip()

def proc_env(pid):
    out={}
    try:
        for item in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0'):
            if b'=' in item:
                k,v=item.split(b'=',1); out[k.decode(errors='replace')]=v.decode(errors='replace')
    except OSError: pass
    return out

def alive(pid, born=None):
    try:
        f=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return f[0] not in ('Z','X') and (born is None or f[19] == born)
    except (OSError,ValueError,IndexError):
        return False

def wrappers(exclude=()):
    result=[]; excluded=set(exclude)
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) in excluded: continue
        try:
            cmd=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
            if any(x.endswith('/enikk.py') for x in cmd) and '--tts-debug' in cmd:
                born=(p/'stat').read_text().rsplit(')',1)[1].split()[19]
                result.append((int(p.name),born))
        except (OSError,ValueError,IndexError): pass
    return result

def latest_run(after_ns):
    runs=TTS/'runs'; found=[]
    if runs.is_dir():
        for p in runs.iterdir():
            try:
                if p.is_dir() and p.stat().st_mtime_ns >= after_ns: found.append((p.stat().st_mtime_ns,p))
            except OSError: pass
    return max(found,default=(0,None))[1]

def wait_ready(after_ns, timeout=120):
    end=time.monotonic()+timeout
    while time.monotonic() < end:
        run=latest_run(after_ns)
        if run:
            try:
                if (run/'model-ready.json').is_file() and 'tts_mode=streaming reason=ready' in (run/'runtime.log').read_text(errors='replace'):
                    return run
            except OSError: pass
        time.sleep(.5)
    raise RuntimeError('TTS ready timeout')

def clean_text(text, run):
    old=os.environ.get('CODEX_ENIKK_TTS_STATE')
    os.environ['CODEX_ENIKK_TTS_STATE']=str(run)
    try:
        spec=importlib.util.spec_from_file_location('satoshi_notify',INSTALL/'tts/yuki-codex-notify.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod.clean_text(text)
    finally:
        if old is None: os.environ.pop('CODEX_ENIKK_TTS_STATE',None)
        else: os.environ['CODEX_ENIKK_TTS_STATE']=old

def epoch(run):
    try: return json.loads((run/'epoch.json').read_text())
    except (OSError,ValueError): return {}

def publish(run, part, text, attempt):
    jobs=run/'jobs'; jobs.mkdir(mode=0o700,parents=True,exist_ok=True)
    key=hashlib.sha256(f'satoshi-{part}-{attempt}-{text}'.encode()).hexdigest()
    name=f'{time.time_ns():020d}-{key}'
    item={'id':key[:12],'stream_key':key,'text':text,'run_id':run.name,
          'queued_ns':time.monotonic_ns(),'sentence_complete_ns':time.monotonic_ns(),
          'filename':name,'source':{'thread':'satoshi-training','turn':f'part-{part:02d}',
          'item':f'graduation-{attempt}','start':0,'end':len(text)}}
    ep=epoch(run)
    if ep:
        item['epoch']=ep.get('epoch'); item['source']['thread']=ep.get('thread'); item['source']['turn']=ep.get('turn')
    tmp=jobs/('.graduation-'+key)
    tmp.write_text(json.dumps(item,ensure_ascii=False),encoding='utf-8')
    os.replace(tmp,jobs/name)
    return jobs/name

def receipt(path):
    for prefix,kind in (('.played-','PLAYED'),('.failed-','FAILED'),('.stale-','STALE')):
        p=path.with_name(prefix+path.name)
        if p.is_file():
            d=json.loads(p.read_text()); delivery=d.get('delivery',{})
            parts=delivery.get('parts',[]); term=delivery.get('terminal',{})
            expected={str(i) for i in range(len(parts))}
            ok=kind=='PLAYED' and set(term)==expected and all(term.get(str(i))=='PLAYED' for i in range(len(parts)))
            return ok,kind,p,d
    return None

def wait_receipt(path, timeout):
    end=time.monotonic()+timeout
    while time.monotonic() < end:
        r=receipt(path)
        if r is not None: return r
        time.sleep(.25)
    raise RuntimeError('graduation delivery timeout')

def retry_failed_parts(run, part, data, timeout, state_path, state):
    delivery=data.get('delivery',{})
    parts=delivery.get('parts',[])
    terminal=delivery.get('terminal',{})
    pending=[i for i in range(len(parts)) if terminal.get(str(i)) != 'PLAYED']
    completed=len(parts)-len(pending)
    targeted_attempts=0
    state.update(status='CHECKPOINT_RETRY', total_parts=len(parts), completed_parts=completed,
                 pending_parts=pending, targeted_attempts=0)
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    for index in pending:
        text=parts[index]
        local_attempt=0
        while True:
            local_attempt += 1
            targeted_attempts += 1
            job=publish(run,part,text,f'checkpoint-{index}-{local_attempt}')
            ok,kind,rp,retry_data=wait_receipt(job,timeout)
            state.update(status='CHECKPOINT_RETRY', total_parts=len(parts), completed_parts=completed,
                         pending_parts=[i for i in pending if i >= index], targeted_attempts=targeted_attempts,
                         current_part=index, current_attempt=local_attempt, last_result=kind)
            state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
            if ok:
                completed += 1
                break
            time.sleep(1)
    return {'parts':len(parts),'targeted_attempts':targeted_attempts,'completed_parts':completed}


def git(*args):
    return subprocess.check_output(['git','-C',str(SOURCE),*args],text=True).strip()

def restart(old_pid):
    env=proc_env(old_pid) if old_pid and alive(old_pid) else {}
    if old_pid and alive(old_pid):
        os.kill(old_pid,signal.SIGTERM); end=time.monotonic()+20
        while alive(old_pid) and time.monotonic() < end: time.sleep(.1)
        if alive(old_pid): raise RuntimeError('old wrapper did not terminate')
    start_ns=time.time_ns(); launch=os.environ.copy()
    for k in ('DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR','HOME','PATH'):
        if env.get(k): launch[k]=env[k]
    launch.setdefault('DISPLAY',':1')
    launch.setdefault('XAUTHORITY',f'/run/user/{os.getuid()}/gdm/Xauthority')
    launch.setdefault('DBUS_SESSION_BUS_ADDRESS',f'unix:path=/run/user/{os.getuid()}/bus')
    launch.setdefault('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}')
    cmd='cd "$HOME"; exec "$HOME/.local/bin/codex_enikk" --tts-debug'
    subprocess.run(['gnome-terminal','--window','--title=Enikk','--','bash','-lc',cmd],env=launch,check=True)
    end=time.monotonic()+30
    while time.monotonic() < end:
        found=wrappers({old_pid})
        if found: return max(found)[0],start_ns
        time.sleep(.25)
    raise RuntimeError('new wrapper missing')

def verify_parity():
    rel=Path('tts/yuki-text-normalization-overrides.py')
    a=hashlib.sha256((SOURCE/rel).read_bytes()).hexdigest(); b=hashlib.sha256((INSTALL/rel).read_bytes()).hexdigest()
    if a!=b: raise RuntimeError('source/install normalization mismatch')

def update_report(part, details):
    report=SOURCE/f'tts/reports/satoshi-part{part:02d}.md'; report.parent.mkdir(parents=True,exist_ok=True)
    text=report.read_text(encoding='utf-8') if report.exists() else f'# satoshi.md training — Part {part:02d}/12\n'
    if '## Automated production graduation' in text: text=text.split('## Automated production graduation',1)[0].rstrip()+'\n'
    text += f"""
## Automated production graduation

- Status: PASS
- Production wrapper PID: {details['pid']}
- Production run: {details['run']}
- Loaded code revision before report finalization: {details['loaded']}
- Custom normalization path: confirmed
- Graduation attempt: {details['attempt']}
- Graduation receipt parts: {details['parts']} accounted as PLAYED; final failures 0
- Targeted checkpoint retries: {details.get('targeted_attempts',0)}
- Graduation cleaned characters: {details['chars']}
- Production ready observed automatically after restart.
"""
    report.write_text(text,encoding='utf-8')
    subprocess.run(['git','-C',str(SOURCE),'add',str(report.relative_to(SOURCE))],check=True)
    if subprocess.run(['git','-C',str(SOURCE),'diff','--cached','--quiet']).returncode:
        subprocess.run(['git','-C',str(SOURCE),'commit','-m',f'docs(tts): finalize satoshi part {part:02d} production graduation'],check=True)
        subprocess.run(['git','-C',str(SOURCE),'push','origin','main'],check=True)
    return git('rev-parse','HEAD')

def marker(part, values):
    TRAIN.mkdir(mode=0o700,parents=True,exist_ok=True)
    p=TRAIN/f'part{part:02d}-production-verified'; tmp=p.with_suffix('.tmp')
    tmp.write_text('\n'.join(f'{k}={v}' for k,v in values.items())+'\n',encoding='utf-8'); os.replace(tmp,p); return p

def run(args):
    TRAIN.mkdir(mode=0o700,parents=True,exist_ok=True)
    state_path=TRAIN/f'part{args.part:02d}-postprocess.json'
    state={'part':args.part,'task_id':args.task_id,'status':'STARTING','started_at':time.time()}
    state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    try:
        loaded=git('rev-parse','HEAD')
        if git('rev-parse','origin/main') != loaded: raise RuntimeError('main/origin mismatch')
        verify_parity()
        pid,start_ns=restart(args.wrapper_pid); run_state=wait_ready(start_ns)
        raw=Path(args.satoshi).read_text(encoding='utf-8'); spoken=clean_text(extract_part(raw,args.part),run_state)
        state.update(status='GRADUATION_FULL_READ',run=str(run_state),pid=pid)
        state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        job=publish(run_state,args.part,spoken,'full')
        ok,kind,rp,data=wait_receipt(job,args.timeout)
        parts=len(data.get('delivery',{}).get('parts',[]))
        if ok:
            passed={'attempt':'full','parts':parts,'receipt':str(rp),'targeted_attempts':0}
        else:
            checkpoint=retry_failed_parts(run_state,args.part,data,args.timeout,state_path,state)
            passed={'attempt':'checkpoint','parts':checkpoint['parts'],'receipt':str(rp),
                    'targeted_attempts':checkpoint['targeted_attempts']}
        report_rev=update_report(args.part,{'pid':pid,'run':run_state.name,'loaded':loaded,
                   'attempt':passed['attempt'],'parts':passed['parts'],'chars':len(spoken),
                   'targeted_attempts':passed['targeted_attempts']})
        m=marker(args.part,{'PART':f'{args.part:02d}','STATUS':'PASS','PID':pid,
                  'LOADED_REVISION':loaded,'REPORT_REVISION':report_rev,'RUN':run_state,'GRADUATION_ATTEMPT':passed['attempt'],'GRADUATION_PARTS':passed['parts'],
                  'TARGETED_RETRIES':passed['targeted_attempts']})
        state.update(status='PASS',pid=pid,run=str(run_state),marker=str(m),finished_at=time.time(),graduation=passed)
        state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8'); return 0
    except Exception as e:
        state.update(status='FAILED',error=f'{type(e).__name__}: {e}',finished_at=time.time())
        state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8'); return 1

def main():
    p=argparse.ArgumentParser(); p.add_argument('--part',type=int,required=True,choices=range(1,13))
    p.add_argument('--task-id',required=True); p.add_argument('--wrapper-pid',type=int,required=True)
    p.add_argument('--satoshi',default=str(Path.home()/'satoshi.md')); p.add_argument('--max-attempts',type=int,default=6)
    p.add_argument('--timeout',type=int,default=1200)
    return run(p.parse_args())

if __name__=='__main__':
    raise SystemExit(main())
