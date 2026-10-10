import os,sys,json,socket,threading,time,pty,subprocess,select,fcntl,termios,struct,re,signal
from pathlib import Path
sys.path.insert(0,'/src')
from trigger_transport import accept_websocket
from trigger_service import check_continuity_request,ContinuityBlocked,continuity_error
ROOT=Path('/experiment');TID='11111111-1111-4111-8111-111111111111'
thread={'id':TID,'sessionId':TID,'cliVersion':'0.160.0','createdAt':1791570000,'updatedAt':1791570000,'cwd':'/experiment','ephemeral':True,'modelProvider':'openai','preview':'Isolated fixture','projectId':None,'source':'cli','status':{'type':'idle'},'turns':[{'id':'seed','status':'completed','items':[{'type':'agentMessage','id':'seed-message','text':'ISOLATED_READY','phase':'final_answer'}]}]}
resume={'thread':thread,'cwd':'/experiment','model':'gpt-6.1-sol','modelProvider':'openai','approvalPolicy':'never','approvalsReviewer':'user','sandbox':{'type':'readOnly'}}
def run(cmd):
    root=ROOT/('case-'+cmd.strip('/').replace(' ','-'));root.mkdir(exist_ok=True)
    home=root/'home';home.mkdir(exist_ok=True)
    (home/'config.toml').write_text('check_for_update_on_startup = false\n')
    sockpath=root/'mock.sock';sockpath.unlink(missing_ok=True)
    listener=socket.socket(socket.AF_UNIX);listener.bind(str(sockpath));listener.listen();listener.settimeout(.1)
    stopped=threading.Event();events=[];output=bytearray();connections=[]
    def handle(sock):
        try:
            ws=accept_websocket(sock);connections.append(ws)
            while not stopped.is_set():
                ev=json.loads(ws.recv());method=ev.get('method');params=ev.get('params') or {}
                events.append({'method':method,'params':params})
                if 'id' not in ev:continue
                try:check_continuity_request(ev,TID,{"features":{"realtime_conversation":True,"personality":True}})
                except ContinuityBlocked as exc:
                    events[-1]['blocked']=True
                    ws.send(json.dumps({'id':ev['id'],'error':continuity_error(ev,exc)}));continue
                if method=='initialize':result={'codexHome':str(home),'userAgent':'isolated-mock','platformFamily':'unix','platformOs':'linux'}
                elif method=='thread/resume':result=resume
                elif method=='thread/read':result={'thread':thread | {'id':params.get('threadId',TID)}}
                elif method=='config/read':result={'config':{'features':{'realtime_conversation':True}},'origins':{}}
                elif method=='configRequirements/read':result={'requirements':None}
                elif method=='account/read':result={'account':{'type':'chatgpt','email':'fixture@example.invalid','planType':'pro'},'requiresOpenaiAuth':False}
                elif method=='account/rateLimits/read':result={'rateLimits':{'limitId':'codex','limitName':'Codex','primary':None,'secondary':None,'credits':None,'planType':None}}
                elif method=='model/list':result={'data':[{'id':'gpt-6.1-sol','model':'gpt-6.1-sol','displayName':'Fixture','description':'offline fixture','hidden':False,'supportsPersonality':True,'isDefault':True,'defaultReasoningEffort':'low','supportedReasoningEfforts':[{'reasoningEffort':'low','description':'test'}]}]}
                elif method in ('thread/list','thread/loaded/list'):result={'data':[thread] if method=='thread/list' else [TID],'nextCursor':None}
                elif method=='thread/items/list':result={'data':[],'nextCursor':None}
                elif method=='thread/turns/list':result={'data':thread['turns'],'nextCursor':None}
                elif method=='turn/start':
                    turn={'id':'probe-turn','status':'inProgress','items':[]};result={'turn':turn}
                    ws.send(json.dumps({'id':ev['id'],'result':result}))
                    ws.send(json.dumps({'method':'turn/started','params':{'threadId':TID,'turn':turn}}))
                    item={'type':'agentMessage','id':'reply','text':'PROBE_OK','phase':'final_answer'}
                    ws.send(json.dumps({'method':'item/completed','params':{'threadId':TID,'turnId':'probe-turn','item':item}}))
                    ws.send(json.dumps({'method':'turn/completed','params':{'threadId':TID,'turn':{'id':'probe-turn','status':'completed','items':[item]}}}));continue
                elif method in ('mcpServerStatus/list','experimentalFeature/list','plugin/list','app/list','skills/list'):result={'data':[],'nextCursor':None}
                elif method=='account/workspaceMessages/read':result={'messages':[]}
                elif method=='collaborationMode/list':result={'data':[]}
                elif method=='hooks/list':result={'hooks':[]}
                elif method=='thread/goal/get':result={'goal':None}
                else:result={}
                ws.send(json.dumps({'id':ev['id'],'result':result}))
        except Exception as e:events.append({'connection_error':str(e)})
    def accept():
        while not stopped.is_set():
            try:s,_=listener.accept();threading.Thread(target=handle,args=(s,),daemon=True).start()
            except socket.timeout:continue
            except OSError:return
    threading.Thread(target=accept,daemon=True).start()
    master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
    env={'HOME':str(home),'CODEX_HOME':str(home),'XDG_CONFIG_HOME':str(home/'config'),'XDG_STATE_HOME':str(home/'state'),'XDG_CACHE_HOME':str(home/'cache'),'PATH':'/usr/bin:/bin','TERM':'xterm-256color','LANG':'C.UTF-8'}
    previous_suspend=signal.signal(signal.SIGTSTP,signal.SIG_IGN)
    p=subprocess.Popen(['/codex','-c','check_for_update_on_startup=false','resume',TID,'--remote','unix://'+str(sockpath),'--no-alt-screen'],stdin=slave,stdout=slave,stderr=slave,env=env,cwd='/experiment',start_new_session=True);os.close(slave)
    def pump(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if not select.select([master],[],[],.05)[0]:continue
            try:data=os.read(master,65536)
            except OSError:break
            if not data:break
            output.extend(data)
            for query,answer in [(b'\x1b[6n',b'\x1b[1;1R'),(b'\x1b]11;?',b'\x1b]11;rgb:0000/0000/0000\x1b\\'),(b'\x1b]10;?',b'\x1b]10;rgb:ffff/ffff/ffff\x1b\\')]:
                if query in data:os.write(master,answer)
    try:
        pump(2)
        if cmd=='ctrl-z':
            import base64
            fixture=root/'pixel.png'
            import zlib
            def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
            fixture.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00\xff'))+chunk(b'IEND',b''))
            os.write(master,b'DRAFT_BEFORE_SUSPEND ');pump(.3)
            os.write(master,b'\x1b[200~'+str(fixture).encode()+b'\x1b[201~');pump(.5)
        os.write(master,b'\x1a' if cmd=='ctrl-z' else cmd.encode());pump(.3)
        if cmd!='ctrl-z':os.write(master,b'\r')
        pump(1.5)
        if cmd in ('/delete','/archive'):
            os.write(master,b'\x1b[A');pump(.2);os.write(master,b'\r');pump(1)
        if cmd in ('/personality','/memories'):
            os.write(master,b'\x1b[B');pump(.2);os.write(master,b'\r');pump(.7);os.write(master,b'\x1b');pump(.2)
        if cmd=='/model':
            os.write(master,b'\r');pump(.4);os.write(master,b'\r');pump(.8)
        if cmd in ('/plugins','/experimental','/agents','/subagents','/model'):
            os.write(master,b'\x1b');pump(.3)
        before=len(events);os.write(master,b'PROBE_AFTER_BLOCK');pump(.3);os.write(master,b'\r');pump(1.5)
        result={'command':cmd,'alive':p.poll() is None,'exit':p.poll(),'blocked':[e['method'] for e in events if e.get('blocked')],'after_methods':[e.get('method') for e in events[before:]],'probe_turn':any(e.get('method')=='turn/start' and e.get('params',{}).get('threadId')==TID and 'PROBE_AFTER_BLOCK' in json.dumps(e) for e in events[before:]),'reply_seen':b'PROBE_OK' in output,'methods':[e.get('method') for e in events]}
        if cmd=='ctrl-z':
            inputs=[e.get('params',{}).get('input',[]) for e in events[before:] if e.get('method')=='turn/start']
            result['draft_preserved']='DRAFT_BEFORE_SUSPEND' in json.dumps(inputs)
            result['attachment_preserved']=any(i.get('type') in ('localImage','image') for items in inputs for i in items)
        (root/'events.json').write_text(json.dumps(events,indent=2));(root/'terminal.bin').write_bytes(output)
        clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',output.decode(errors='replace'))
        (root/'terminal.txt').write_text(clean)
        (root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    finally:
        signal.signal(signal.SIGTSTP,previous_suspend)
        p.terminate()
        try:p.wait(2)
        except subprocess.TimeoutExpired:p.kill();p.wait()
        stopped.set();listener.close()
        for ws in connections:ws.close()
        os.close(master)
for cmd in sys.argv[1:] or ['/fork']:run(cmd)
