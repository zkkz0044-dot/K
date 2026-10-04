#!/usr/bin/python3
from __future__ import annotations
import json, os, subprocess, threading, time, secrets
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path('/root/K'); PANEL=ROOT/'PANEL-v0.1'
ROOT_STATE=ROOT/'PROJECT_STATE.json'; K_STATE=ROOT/'K/PROJECT_STATE.json'; F_STATE=ROOT/'F/PROJECT_STATE.json'
UPGRADE_STATE=ROOT/'UPGRADE-v0.3/state/current.json'
AUDIT_HEAD=ROOT/'F/evidence/fk/k_audit_witness_v2.json'; AUDIT_LOG=ROOT/'F/evidence/fk/k_audit_events_v2.jsonl'
SERVICES=('kk-fk-gateway.service','kk-fk-audit-witness.service','kk-k-model-gateway.service')
MAX_EVENTS=80; MAX_FILE=2_000_000; MAX_BODY=64_000_000; CHAT_LOCK=threading.Lock()
MAX_AUDIT_TAIL=256_000

class LocalHTTPServer(ThreadingHTTPServer):
    """Bound simultaneous requests before allocating request bodies/threads."""
    daemon_threads=True
    def __init__(self,*args,**kwargs):
        self.request_slots=threading.BoundedSemaphore(2)
        super().__init__(*args,**kwargs)
    def process_request(self,request,client_address):
        if not self.request_slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request,client_address)
        except BaseException:
            self.request_slots.release()
            raise
    def process_request_thread(self,request,client_address):
        try:
            super().process_request_thread(request,client_address)
        finally:
            self.request_slots.release()
RUNS={}; RUNS_LOCK=threading.Lock(); MAX_RUNS=32
K_RUNNER_CODE=r'''import json,sys,time
from kk_k.chat_runtime import ChatRuntimeError,run_turn
from kk_k.human_ingress import HumanIngressError,MAX_TEXT_BYTES,parse_console_line,parse_paste_text
def progress(code,state,detail=''):
 print(json.dumps({"type":"progress","code":code,"state":state,"detail":detail,"mono":time.monotonic()},ensure_ascii=False,separators=(",",":")),flush=True)
try:
 raw=sys.stdin.read()
 env=json.loads(raw)
 if not isinstance(env,dict) or set(env)!={'text','media','device'} or not isinstance(env.get('text'),str) or not isinstance(env.get('media'),list): raise ValueError('invalid envelope')
 text=env['text']; media=env['media']; device=env.get('device')
 progress('ingress','START','接收并校验输入')
 msg=parse_paste_text(text) if len(text.encode("utf-8"))>MAX_TEXT_BYTES else parse_console_line(text)
 progress('ingress','DONE',f'已接收 {len(text.encode("utf-8"))} bytes，附件 {len(media)} 个')
 answer=run_turn(msg,progress=progress,media=media,device_context=device)
 print(json.dumps({"type":"result","status":"PASS","answer":answer},ensure_ascii=False,separators=(",",":")),flush=True)
except (HumanIngressError,ChatRuntimeError) as exc:
 print(json.dumps({"type":"result","status":"FAIL","error":type(exc).__name__,"detail":str(exc)},ensure_ascii=False,separators=(",",":")),flush=True)
 raise SystemExit(2)
'''

def read_json(path:Path)->dict:
    with path.open('rb') as fh:
        raw=fh.read(MAX_FILE+1)
    if len(raw)>MAX_FILE: raise ValueError('oversize')
    val=json.loads(raw.decode('utf-8'))
    if not isinstance(val,dict): raise ValueError('not-object')
    return val

def service_status(name:str)->dict:
    props=['ActiveState','SubState','MainPID','NRestarts','UnitFileState','FragmentPath']
    cp=subprocess.run(['systemctl','show',name]+[f'-p{x}' for x in props],text=True,capture_output=True,timeout=2,check=False)
    d={'name':name,'ok':False}
    for line in cp.stdout.splitlines():
        if '=' in line:
            k,v=line.split('=',1); d[k]=v
    d['ok']=d.get('ActiveState')=='active' and d.get('SubState')=='running'
    return d

def recent_events()->list[dict]:
    if not AUDIT_LOG.exists(): return []
    with AUDIT_LOG.open('rb') as fh:
        size=fh.seek(0,2)
        start=max(0,size-MAX_AUDIT_TAIL)
        fh.seek(start)
        raw=fh.read(MAX_AUDIT_TAIL)
    if start:
        raw=raw.partition(b'\n')[2]
    lines=raw.decode('utf-8',errors='replace').splitlines()[-MAX_EVENTS:]; out=[]
    for raw in lines:
        try: e=json.loads(raw)
        except Exception: continue
        if not isinstance(e,dict): continue
        summary=e.get('summary','')
        if not isinstance(summary,str): summary=''
        out.append({'sequence':e.get('sequence'),'kind':e.get('kind',''),'subject':e.get('subject',''),'summary':summary[:1600],'event_id':e.get('event_id',''),'entry_sha256':e.get('entry_sha256','')})
    return out

def snapshot()->dict:
    root=read_json(ROOT_STATE); ks=read_json(K_STATE); fs=read_json(F_STATE); audit=read_json(AUDIT_HEAD); services=[service_status(x) for x in SERVICES]
    try: upgrade=read_json(UPGRADE_STATE)
    except Exception: upgrade={'schema':'K.UPGRADE.STATE.1','version':'0.3','phase':'UNAVAILABLE','active_candidate':None,'install_enabled':False,'auto_install':False}
    return {'schema':'KK.PANEL.STATUS.2','merge':root.get('formal_merge_status','UNKNOWN'),'merge_acceptance':root.get('merge_acceptance','UNKNOWN'),'tests':{'K':root.get('k_tests') or ks.get('k_tests') or 'UNKNOWN','F':root.get('f_tests') or fs.get('f_tests') or 'UNKNOWN','FK':root.get('fk_tests') or 'UNKNOWN'},'services':services,'audit':{'generation':audit.get('generation'),'digest':audit.get('digest',''),'events':len(recent_events())},'a03':root.get('a03_network') or root.get('A03') or 'HUMAN_GATED','f_status':fs.get('status','UNKNOWN'),'f_acceptance':fs.get('final_acceptance','UNKNOWN'),'k_status':ks.get('status','UNKNOWN'),'chat_busy':CHAT_LOCK.locked(),'upgrade':upgrade,'events':recent_events()}

def run_k_turn(text:str)->dict:
    if len(text.encode('utf-8'))>60_000: return {'status':'FAIL','error':'INPUT_TOO_LARGE'}
    if subprocess.run(['systemctl','is-active','--quiet','kk-k-runtime.service'],check=False).returncode==0:
        return {'status':'BUSY','error':'K_RUNTIME_BUSY'}
    cmd=['systemd-run','--pipe','--wait','--collect','--quiet','--unit=kk-k-runtime.service',
      '--property=DynamicUser=yes','--property=RefuseManualStop=yes','--property=NoNewPrivileges=yes','--property=ProtectSystem=strict','--property=ProtectHome=tmpfs','--property=PrivateTmp=yes','--property=RestrictSUIDSGID=yes','--property=LockPersonality=yes','--property=RestrictAddressFamilies=AF_UNIX','--property=IPAddressDeny=any','--property=MemoryMax=256M','--property=TasksMax=64','--property=UMask=0077','--property=BindReadOnlyPaths=/root/K/K:/run/kk-k-ro','--property=BindReadOnlyPaths=/root/K/FK/runtime/model-ipc:/run/kk-model-ipc','--setenv=PYTHONPATH=/run/kk-k-ro/src','/usr/bin/python3','-c',K_RUNNER_CODE]
    cp=subprocess.run(cmd,input=json.dumps({'text':text,'media':[],'device':None},ensure_ascii=False,separators=(',',':')),text=True,capture_output=True,timeout=150,check=False)
    lines=[x for x in cp.stdout.splitlines() if x.strip()]
    if lines:
        try: result=json.loads(lines[-1])
        except json.JSONDecodeError: result={'status':'FAIL','error':'K_RUNTIME_OUTPUT'}
    else: result={'status':'FAIL','error':'K_RUNTIME_NO_OUTPUT'}
    if cp.returncode!=0 and result.get('status')=='PASS': result={'status':'FAIL','error':'K_RUNTIME_EXIT'}
    return result


def _append_run_event(run_id:str,event:dict)->None:
    with RUNS_LOCK:
        run=RUNS.get(run_id)
        if not run: return
        item=dict(event); item['seq']=run['next_seq']; run['next_seq']+=1; item['server_ts']=time.time()
        run['events'].append(item); run['updated']=time.time()

def _finish_run(run_id:str,result:dict)->None:
    with RUNS_LOCK:
        run=RUNS.get(run_id)
        if not run: return
        run['status']='COMPLETE' if result.get('status')=='PASS' else result.get('status','FAIL')
        run['answer']=result.get('answer',''); run['error']=result.get('error',''); run['updated']=time.time()

def _run_chat_job(run_id:str,text:str,media:list[dict],device:dict|None)->None:
    proc=None; watchdog=None
    try:
        if subprocess.run(['systemctl','is-active','--quiet','kk-k-runtime.service'],check=False).returncode==0:
            _finish_run(run_id,{'status':'BUSY','error':'K_RUNTIME_BUSY'}); return
        cmd=['systemd-run','--pipe','--wait','--collect','--quiet','--unit=kk-k-runtime.service','--property=RuntimeMaxSec=150s',
          '--property=DynamicUser=yes','--property=RefuseManualStop=yes','--property=NoNewPrivileges=yes','--property=ProtectSystem=strict','--property=ProtectHome=tmpfs','--property=PrivateTmp=yes','--property=RestrictSUIDSGID=yes','--property=LockPersonality=yes','--property=RestrictAddressFamilies=AF_UNIX','--property=IPAddressDeny=any','--property=MemoryMax=256M','--property=TasksMax=64','--property=UMask=0077','--property=BindReadOnlyPaths=/root/K/K:/run/kk-k-ro','--property=BindReadOnlyPaths=/root/K/FK/runtime/model-ipc:/run/kk-model-ipc','--setenv=PYTHONPATH=/run/kk-k-ro/src','/usr/bin/python3','-u','-c',K_RUNNER_CODE]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        # Drain stderr so a full pipe cannot block stdout or process exit.
        def drain_errors():
            try:
                while proc.stderr.read(4096):
                    pass
            except (OSError,ValueError):
                pass
        threading.Thread(target=drain_errors,daemon=True).start()
        watchdog=threading.Timer(160,proc.kill)
        watchdog.daemon=True; watchdog.start()
        proc.stdin.write(json.dumps({'text':text,'media':media,'device':device},ensure_ascii=False,separators=(',',':'))); proc.stdin.close(); final=None
        for raw in proc.stdout:
            raw=raw.strip()
            if not raw: continue
            try: obj=json.loads(raw)
            except json.JSONDecodeError: continue
            if obj.get('type')=='progress': _append_run_event(run_id,obj)
            elif obj.get('type')=='result': final=obj
        rc=proc.wait(timeout=160)
        if final is None: final={'status':'FAIL','error':'K_RUNTIME_NO_OUTPUT'}
        if rc!=0 and final.get('status')=='PASS': final={'status':'FAIL','error':'K_RUNTIME_EXIT'}
        _finish_run(run_id,final)
    except Exception as exc:
        _finish_run(run_id,{'status':'FAIL','error':type(exc).__name__})
    finally:
        if watchdog is not None: watchdog.cancel()
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: pass
            for stream in (proc.stdin,proc.stdout,proc.stderr):
                if stream is not None: stream.close()
        CHAT_LOCK.release()

def _validate_media_http(value:object)->list[dict]:
    if value in (None,[]): return []
    if not isinstance(value,list) or len(value)>12: raise ValueError('MEDIA_COUNT')
    out=[]; total=0; images=0; files=0; audios=0
    for item in value:
        if not isinstance(item,dict): raise ValueError('MEDIA_FORMAT')
        kind=item.get('kind'); name=item.get('name','attachment')
        if not isinstance(name,str) or not name or len(name.encode('utf-8'))>240 or '\x00' in name: raise ValueError('MEDIA_NAME')
        if kind=='image':
            images+=1
            if images>6: raise ValueError('IMAGE_COUNT')
            data=item.get('data_url'); source=item.get('source','image')
            if not isinstance(data,str) or not data.startswith('data:image/') or len(data)>2_200_000: raise ValueError('IMAGE_SIZE')
            if source not in {'image','video_frame'}: raise ValueError('IMAGE_SOURCE')
            clean={'kind':'image','name':name,'data_url':data,'source':source}
            if source=='video_frame' and isinstance(item.get('frame_time'),(int,float)): clean['frame_time']=max(0.0,float(item['frame_time']))
            total+=len(data); out.append(clean)
        elif kind=='file':
            files+=1
            if files>5: raise ValueError('FILE_COUNT')
            data=item.get('data_b64'); mime=item.get('mime','application/octet-stream')
            if not isinstance(data,str) or not data or len(data)>42_500_000: raise ValueError('FILE_SIZE')
            if not isinstance(mime,str) or not mime or len(mime)>160: raise ValueError('FILE_MIME')
            total+=len(data); out.append({'kind':'file','name':name,'mime':mime,'data_b64':data})
        elif kind=='audio':
            audios+=1
            if audios>1: raise ValueError('AUDIO_COUNT')
            data=item.get('data_b64'); mime=item.get('mime','audio/mp4')
            if not isinstance(data,str) or not data or len(data)>28_000_000: raise ValueError('AUDIO_SIZE')
            if not isinstance(mime,str) or not mime.startswith('audio/') or len(mime)>160: raise ValueError('AUDIO_MIME')
            total+=len(data); out.append({'kind':'audio','name':name,'mime':mime,'data_b64':data})
        else: raise ValueError('MEDIA_KIND')
        if total>55_000_000: raise ValueError('MEDIA_TOTAL')
    return out

def _num(v,lo,hi):
    if v is None: return None
    if not isinstance(v,(int,float)) or isinstance(v,bool): raise ValueError('DEVICE_NUMBER')
    v=float(v)
    if not (lo<=v<=hi): raise ValueError('DEVICE_RANGE')
    return round(v,6)

def _vec(v):
    if v is None: return None
    if not isinstance(v,dict): raise ValueError('DEVICE_VECTOR')
    return {k:_num(v.get(k),-500.0,500.0) for k in ('x','y','z')}

def _validate_device_http(value:object)->dict|None:
    if value is None: return None
    if not isinstance(value,dict) or value.get('schema')!='K.DEVICE.SNAPSHOT.1': raise ValueError('DEVICE_FORMAT')
    ts=value.get('captured_at_ms')
    if not isinstance(ts,(int,float)) or isinstance(ts,bool): raise ValueError('DEVICE_TIME')
    out={'schema':'K.DEVICE.SNAPSHOT.1','captured_at_ms':int(ts),'terminal':None,'location':None,'orientation':None,'motion':None,'stability':None}
    term=value.get('terminal')
    if term is not None:
        if not isinstance(term,dict): raise ValueError('DEVICE_TERMINAL')
        did=term.get('device_id'); dname=term.get('device_name'); dmodel=term.get('device_model'); mode=term.get('app_mode'); online=term.get('online')
        if not isinstance(did,str) or not (8<=len(did)<=96) or '\x00' in did: raise ValueError('DEVICE_ID')
        if not isinstance(dname,str) or not dname or len(dname)>80 or '\x00' in dname: raise ValueError('DEVICE_NAME')
        if not isinstance(dmodel,str) or not dmodel or len(dmodel)>80 or '\x00' in dmodel: raise ValueError('DEVICE_MODEL')
        if mode not in {'standalone','browser'} or not isinstance(online,bool): raise ValueError('DEVICE_MODE')
        out['terminal']={'device_id':did,'device_name':dname,'device_model':dmodel,'app_mode':mode,'online':online}
    loc=value.get('location')
    if loc is not None:
        if not isinstance(loc,dict): raise ValueError('DEVICE_LOCATION')
        out['location']={'latitude':_num(loc.get('latitude'),-90,90),'longitude':_num(loc.get('longitude'),-180,180),'accuracy_m':_num(loc.get('accuracy_m'),0,100000),'altitude_m':_num(loc.get('altitude_m'),-1000,100000),'altitude_accuracy_m':_num(loc.get('altitude_accuracy_m'),0,100000),'heading_deg':_num(loc.get('heading_deg'),0,360),'speed_mps':_num(loc.get('speed_mps'),0,1000),'timestamp_ms':int(loc.get('timestamp_ms')) if isinstance(loc.get('timestamp_ms'),(int,float)) and not isinstance(loc.get('timestamp_ms'),bool) else None}
    ori=value.get('orientation')
    if ori is not None:
        if not isinstance(ori,dict): raise ValueError('DEVICE_ORIENTATION')
        out['orientation']={'alpha':_num(ori.get('alpha'),-720,720),'beta':_num(ori.get('beta'),-360,360),'gamma':_num(ori.get('gamma'),-360,360),'absolute':bool(ori.get('absolute',False)),'compass_heading_deg':_num(ori.get('compass_heading_deg'),0,360),'compass_accuracy_deg':_num(ori.get('compass_accuracy_deg'),0,180),'timestamp_ms':int(ori.get('timestamp_ms')) if isinstance(ori.get('timestamp_ms'),(int,float)) and not isinstance(ori.get('timestamp_ms'),bool) else None}
    mot=value.get('motion')
    if mot is not None:
        if not isinstance(mot,dict): raise ValueError('DEVICE_MOTION')
        rr=mot.get('rotation_rate')
        out['motion']={'interval_ms':_num(mot.get('interval_ms'),0,10000),'acceleration':_vec(mot.get('acceleration')),'acceleration_including_gravity':_vec(mot.get('acceleration_including_gravity')),'rotation_rate':None,'timestamp_ms':int(mot.get('timestamp_ms')) if isinstance(mot.get('timestamp_ms'),(int,float)) and not isinstance(mot.get('timestamp_ms'),bool) else None}
        if rr is not None:
            if not isinstance(rr,dict): raise ValueError('DEVICE_ROTATION')
            out['motion']['rotation_rate']={k:_num(rr.get(k),-10000,10000) for k in ('alpha','beta','gamma')}
    st=value.get('stability')
    if st is not None:
        if not isinstance(st,dict) or st.get('state') not in {'stable','moving','active'}: raise ValueError('DEVICE_STABILITY')
        out['stability']={'index_0_100':_num(st.get('index_0_100'),0,100),'state':st.get('state'),'heuristic':True}
    if len(json.dumps(out,separators=(',',':')).encode())>6000: raise ValueError('DEVICE_SIZE')
    return out

def start_chat_run(text:str,media:list[dict]|None=None,device:dict|None=None)->str|None:
    if len(text.encode('utf-8'))>60_000: raise ValueError('INPUT_TOO_LARGE')
    media=_validate_media_http(media)
    device=_validate_device_http(device)
    if not CHAT_LOCK.acquire(blocking=False): return None
    run_id=secrets.token_hex(12); now=time.time()
    with RUNS_LOCK:
        if len(RUNS)>=MAX_RUNS:
            old=sorted(((v['created'],k) for k,v in RUNS.items() if v.get('status')!='RUNNING'))
            if old: RUNS.pop(old[0][1],None)
        RUNS[run_id]={'run_id':run_id,'status':'RUNNING','events':[],'next_seq':0,'answer':'','error':'','created':now,'updated':now}
    threading.Thread(target=_run_chat_job,args=(run_id,text,media,device),daemon=True).start()
    return run_id

def read_chat_run(run_id:str,after:int)->dict|None:
    with RUNS_LOCK:
        run=RUNS.get(run_id)
        if not run: return None
        return {'schema':'KK.PANEL.CHAT.EVENTS.1','run_id':run_id,'status':run['status'],'events':[dict(x) for x in run['events'] if x['seq']>after],'answer':run['answer'] if run['status']=='COMPLETE' else '','error':run['error'] if run['status'] not in {'RUNNING','COMPLETE'} else ''}

class Handler(BaseHTTPRequestHandler):
    server_version='KKPanel/0.2'
    def setup(self):
        super().setup()
        self.connection.settimeout(15)
    def local_request(self):
        allowed_hosts={'127.0.0.1','localhost','[::1]'}
        host=self.headers.get('Host','')
        if host not in {f'{name}:{self.server.server_port}' for name in allowed_hosts}:
            self.send_json(403,{'error':'LOCAL_HOST_REQUIRED'}); return False
        origin=self.headers.get('Origin')
        if origin and origin not in {f'http://{name}:{port}' for name in allowed_hosts for port in (self.server.server_port,8877,8878)}:
            self.send_json(403,{'error':'CROSS_ORIGIN_DENIED'}); return False
        return True
    def log_message(self,_fmt,*_args): return
    def send_bytes(self,code:int,body:bytes,ctype:str):
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer'); self.end_headers(); self.wfile.write(body)
    def send_json(self,code:int,payload:dict): self.send_bytes(code,json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8'),'application/json; charset=utf-8')
    def do_GET(self):
        if not self.local_request(): return
        parts=urlsplit(self.path); route=parts.path
        if route=='/api/status':
            try: self.send_json(200,snapshot())
            except Exception as exc: self.send_json(503,{'schema':'KK.PANEL.ERROR.1','error':type(exc).__name__})
            return
        if route=='/api/chat/events':
            qs=parse_qs(parts.query); run_id=(qs.get('run_id') or [''])[0]
            try: after=int((qs.get('after') or ['-1'])[0])
            except ValueError: after=-1
            payload=read_chat_run(run_id,after)
            if payload is None: self.send_json(404,{'error':'RUN_NOT_FOUND'})
            else: self.send_json(200,payload)
            return
        files={'/':('mobile.html','text/html; charset=utf-8'),'/index.html':('mobile.html','text/html; charset=utf-8'),'/styles.css':('styles.css','text/css; charset=utf-8'),'/app.js':('app.js','application/javascript; charset=utf-8'),'/mobile':('mobile.html','text/html; charset=utf-8'),'/mobile/':('mobile.html','text/html; charset=utf-8'),'/mobile.html':('mobile.html','text/html; charset=utf-8'),'/mobile.css':('mobile.css','text/css; charset=utf-8'),'/mobile.js':('mobile.js','application/javascript; charset=utf-8'),'/manifest.webmanifest':('manifest.webmanifest','application/manifest+json; charset=utf-8'),'/service-worker.js':('service-worker.js','application/javascript; charset=utf-8'),'/icon-180.png':('icon-180.png','image/png'),'/icon-192.png':('icon-192.png','image/png'),'/icon-512.png':('icon-512.png','image/png')}
        if route not in files: self.send_bytes(404,b'not found','text/plain; charset=utf-8'); return
        name,ctype=files[route]; self.send_bytes(200,(PANEL/name).read_bytes(),ctype)
    def do_POST(self):
        if not self.local_request(): return
        route=self.path.split('?',1)[0]
        if route not in {'/api/chat','/api/chat/start'}: self.send_bytes(405,b'read only','text/plain; charset=utf-8'); return
        if 'application/json' not in self.headers.get('Content-Type',''): self.send_json(415,{'error':'JSON_REQUIRED'}); return
        try: n=int(self.headers.get('Content-Length','0'))
        except ValueError: n=0
        if n<=0 or n>MAX_BODY: self.send_json(413,{'error':'BODY_SIZE'}); return
        try:
            payload=json.loads(self.rfile.read(n).decode('utf-8'))
            if not isinstance(payload,dict): raise ValueError('invalid payload')
            text=payload.get('text',''); media=_validate_media_http(payload.get('media',[])); device=_validate_device_http(payload.get('device'))
            if not isinstance(text,str) or '\x00' in text: raise ValueError('invalid text')
            if not text.strip() and not media: raise ValueError('empty input')
            if not text.strip() and media: text='请查看我发送的附件。'
        except (UnicodeDecodeError,json.JSONDecodeError,ValueError): self.send_json(400,{'error':'INPUT_REJECTED'}); return
        if route=='/api/chat/start':
            try: run_id=start_chat_run(text,media,device)
            except ValueError as exc: self.send_json(413,{'error':str(exc)}); return
            if run_id is None: self.send_json(409,{'error':'K_BUSY'}); return
            self.send_json(202,{'schema':'KK.PANEL.CHAT.START.1','run_id':run_id,'status':'RUNNING'}); return
        if not CHAT_LOCK.acquire(blocking=False): self.send_json(409,{'error':'K_BUSY'}); return
        try:
            result=run_k_turn(text)
            if result.get('status')=='PASS': self.send_json(200,{'schema':'KK.PANEL.CHAT.1',**result})
            elif result.get('status')=='BUSY': self.send_json(409,{'schema':'KK.PANEL.CHAT.1',**result})
            else: self.send_json(503,{'schema':'KK.PANEL.CHAT.1',**result})
        except subprocess.TimeoutExpired: self.send_json(504,{'schema':'KK.PANEL.CHAT.1','status':'FAIL','error':'K_TIMEOUT'})
        finally: CHAT_LOCK.release()

def main()->int:
    if os.geteuid()!=0: raise SystemExit('panel server must run as root')
    LocalHTTPServer(('127.0.0.1',8877),Handler).serve_forever(); return 0
if __name__=='__main__': raise SystemExit(main())
