from __future__ import annotations
import base64, json, os, socket, struct, sys, urllib.error, urllib.request, uuid
from pathlib import Path

SOCK='/run/kk-model-ipc/host-relay.sock'
ALLOWED_CGROUP='/system.slice/kk-k-model-gateway.service'
API_URL='https://api.openai.com/v1/responses'
TRANSCRIBE_URL='https://api.openai.com/v1/audio/transcriptions'
MAX_FRAME=64_000_000
MAX_RESPONSE=16384
MAX_HTTP_RESPONSE=1048576
TIMEOUT_SECONDS=120
ALLOWED_OUTPUT_TOKENS=frozenset({64,160,384,1024,2048})

class RelayError(RuntimeError): pass

def peer_credentials(conn:socket.socket):
 raw=conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i'))
 return struct.unpack('3i',raw)

def peer_cgroup(pid:int)->str:
 if not isinstance(pid,int) or pid<=0: raise RelayError('PEER_CGROUP_INVALID')
 path=Path('/sys/fs/cgroup')/ALLOWED_CGROUP.lstrip('/')/'cgroup.procs'
 try: members={int(x) for x in path.read_text().splitlines() if x.isdigit()}
 except OSError as exc: raise RelayError('PEER_CGROUP_UNAVAILABLE') from exc
 return ALLOWED_CGROUP if pid in members else ''

def recv_line(conn:socket.socket)->bytes:
 buf=bytearray()
 while b'\n' not in buf:
  chunk=conn.recv(4096)
  if not chunk: break
  buf.extend(chunk)
  if len(buf)>MAX_FRAME: raise RelayError('REQUEST_TOO_LARGE')
 if not buf.endswith(b'\n') or b'\n' in bytes(buf[:-1]): raise RelayError('INVALID_FRAME')
 return bytes(buf[:-1])

def _validate_media(media:object)->list[dict]:
 if not isinstance(media,list) or not (1<=len(media)<=12): raise RelayError('INVALID_MEDIA')
 out=[]; total=0
 for item in media:
  if not isinstance(item,dict): raise RelayError('INVALID_MEDIA')
  kind=item.get('kind'); name=item.get('name')
  if not isinstance(name,str) or not name or len(name.encode('utf-8'))>240 or '\x00' in name: raise RelayError('INVALID_MEDIA_NAME')
  if kind=='image':
   data=item.get('data_url')
   if not isinstance(data,str) or not data.startswith('data:image/') or len(data)>2_200_000: raise RelayError('INVALID_IMAGE_MEDIA')
   total+=len(data); out.append({'kind':'image','name':name,'data_url':data,'source':item.get('source','image'),'frame_time':item.get('frame_time')})
  elif kind=='file':
   data=item.get('data_b64'); mime=item.get('mime','application/octet-stream')
   if not isinstance(data,str) or not data or len(data)>42_500_000: raise RelayError('INVALID_FILE_MEDIA')
   if not isinstance(mime,str) or not mime or len(mime)>160: raise RelayError('INVALID_FILE_MIME')
   total+=len(data); out.append({'kind':'file','name':name,'mime':mime,'data_b64':data})
  elif kind=='audio':
   data=item.get('data_b64'); mime=item.get('mime','audio/mp4')
   if not isinstance(data,str) or not data or len(data)>28_000_000: raise RelayError('INVALID_AUDIO_MEDIA')
   if not isinstance(mime,str) or not mime.startswith('audio/') or len(mime)>160: raise RelayError('INVALID_AUDIO_MIME')
   total+=len(data); out.append({'kind':'audio','name':name,'mime':mime,'data_b64':data})
  else: raise RelayError('INVALID_MEDIA_KIND')
  if total>55_000_000: raise RelayError('MEDIA_TOO_LARGE')
 return out

def strict_request(raw:bytes)->dict:
 try: value=json.loads(raw.decode('utf-8'))
 except Exception as exc: raise RelayError('INVALID_JSON') from exc
 if not isinstance(value,dict): raise RelayError('INVALID_REQUEST')
 schema=value.get('schema')
 if schema=='K.MODEL.RELAY.REQUEST.2':
  if set(value)!={'schema','instructions','input','max_output_tokens'}: raise RelayError('INVALID_REQUEST')
  value['media']=[]
 elif schema=='K.MODEL.RELAY.REQUEST.3':
  if set(value)!={'schema','instructions','input','media','max_output_tokens'}: raise RelayError('INVALID_REQUEST')
  value['media']=_validate_media(value['media'])
 else: raise RelayError('INVALID_REQUEST')
 instructions=value.get('instructions'); prompt=value.get('input'); limit=value.get('max_output_tokens')
 if not isinstance(instructions,str) or not (1<=len(instructions.encode('utf-8'))<=4096): raise RelayError('INVALID_INSTRUCTIONS')
 if not isinstance(prompt,str) or not (1<=len(prompt.encode('utf-8'))<=65536): raise RelayError('INVALID_INPUT')
 if limit not in ALLOWED_OUTPUT_TOKENS: raise RelayError('INVALID_OUTPUT_LIMIT')
 return value

def _credential(name:str)->str:
 root=os.environ.get('CREDENTIALS_DIRECTORY','')
 if not root: raise RelayError('CREDENTIAL_DIRECTORY_MISSING')
 try: value=(Path(root)/name).read_text(encoding='utf-8').strip()
 except OSError as exc: raise RelayError('OPENAI_API_KEY_MISSING') from exc
 if not value: raise RelayError('OPENAI_API_KEY_MISSING')
 return value
def _extract_text(value:object)->str:
 if not isinstance(value,dict): raise RelayError('OPENAI_INVALID_RESPONSE')
 if value.get('error'): raise RelayError('OPENAI_RESPONSE_ERROR')
 output=value.get('output')
 if not isinstance(output,list): raise RelayError('OPENAI_OUTPUT_MISSING')
 parts=[]
 for item in output:
  if not isinstance(item,dict) or item.get('type')!='message': continue
  content=item.get('content')
  if not isinstance(content,list): continue
  for part in content:
   if isinstance(part,dict) and part.get('type')=='output_text' and isinstance(part.get('text'),str):
    parts.append(part['text'])
 text=''.join(parts).strip()
 if not text: raise RelayError('OPENAI_OUTPUT_EMPTY')
 if len(text.encode('utf-8'))>4096 or '\x00' in text: raise RelayError('MODEL_OUTPUT_INVALID')
 return text

def _transcribe_audio(item:dict,key:str)->str:
 model=os.environ.get('OPENAI_TRANSCRIBE_MODEL','gpt-4o-mini-transcribe').strip() or 'gpt-4o-mini-transcribe'
 try: audio=base64.b64decode(item['data_b64'],validate=True)
 except Exception as exc: raise RelayError('AUDIO_BASE64_INVALID') from exc
 if not audio or len(audio)>20*1024*1024: raise RelayError('AUDIO_TOO_LARGE')
 boundary='----KAudio'+uuid.uuid4().hex
 def field(name,value):
  return ('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n').encode()
 head=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="recording"\r\nContent-Type: '+item.get('mime','audio/mp4')+'\r\n\r\n').encode()
 body=field('model',model)+head+audio+b'\r\n'+('--'+boundary+'--\r\n').encode()
 request=urllib.request.Request(TRANSCRIBE_URL,data=body,method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'multipart/form-data; boundary='+boundary})
 try:
  with urllib.request.urlopen(request,timeout=TIMEOUT_SECONDS) as response: raw=response.read(MAX_HTTP_RESPONSE+1)
 except urllib.error.HTTPError as exc:
  if exc.code==401: raise RelayError('OPENAI_AUTH_FAILED') from exc
  if exc.code==429: raise RelayError('OPENAI_RATE_LIMITED') from exc
  if 500<=exc.code<=599: raise RelayError('OPENAI_UPSTREAM_ERROR') from exc
  raise RelayError('OPENAI_TRANSCRIBE_HTTP_'+str(exc.code)) from exc
 except (urllib.error.URLError,TimeoutError,OSError) as exc: raise RelayError('OPENAI_TRANSCRIBE_UNAVAILABLE') from exc
 if len(raw)>MAX_HTTP_RESPONSE: raise RelayError('OPENAI_TRANSCRIBE_RESPONSE_TOO_LARGE')
 try: value=json.loads(raw.decode('utf-8'))
 except Exception as exc: raise RelayError('OPENAI_TRANSCRIBE_INVALID_JSON') from exc
 text=value.get('text') if isinstance(value,dict) else None
 if not isinstance(text,str) or not text.strip() or len(text.encode('utf-8'))>12000: raise RelayError('OPENAI_TRANSCRIBE_EMPTY')
 return text.strip()

def call_openai(req:dict)->str:
 model=os.environ.get('OPENAI_MODEL','').strip()
 if not model: raise RelayError('OPENAI_MODEL_NOT_CONFIGURED')
 key=_credential('OPENAI_API_KEY')
 media=req.get('media') or []
 audio_notes=[]
 for item in media:
  if item['kind']=='audio': audio_notes.append(_transcribe_audio(item,key))
 prompt=req['input']
 if audio_notes:
  prompt += '\n[AUDIO_TRANSCRIPT_FROM_USER_MICROPHONE]\n'+'\n'.join(audio_notes)+'\n[/AUDIO_TRANSCRIPT_FROM_USER_MICROPHONE]'
 if media:
  content=[{'type':'input_text','text':prompt}]
  for item in media:
   if item['kind']=='image': content.append({'type':'input_image','image_url':item['data_url'],'detail':'auto'})
   elif item['kind']=='file': content.append({'type':'input_file','filename':item['name'],'file_data':'data:'+item.get('mime','application/octet-stream')+';base64,'+item['data_b64']})
  api_input=[{'role':'user','content':content}]
 else:
  api_input=prompt
 payload={'model':model,'instructions':req['instructions'],'input':api_input,
          'max_output_tokens':req['max_output_tokens'],'store':False}
 if req['max_output_tokens']==64:
  payload['reasoning']={'effort':'none'}
 body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
 request=urllib.request.Request(API_URL,data=body,method='POST',headers={
  'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=TIMEOUT_SECONDS) as response:
   raw=response.read(MAX_HTTP_RESPONSE+1)
 except urllib.error.HTTPError as exc:
  if exc.code==401: raise RelayError('OPENAI_AUTH_FAILED') from exc
  if exc.code==429: raise RelayError('OPENAI_RATE_LIMITED') from exc
  if 500<=exc.code<=599: raise RelayError('OPENAI_UPSTREAM_ERROR') from exc
  raise RelayError('OPENAI_HTTP_'+str(exc.code)) from exc
 except (urllib.error.URLError,TimeoutError,OSError) as exc:
  raise RelayError('OPENAI_UNAVAILABLE') from exc
 if len(raw)>MAX_HTTP_RESPONSE: raise RelayError('OPENAI_RESPONSE_TOO_LARGE')
 try: value=json.loads(raw.decode('utf-8'))
 except Exception as exc: raise RelayError('OPENAI_INVALID_JSON') from exc
 usage=value.get('usage',{}) if isinstance(value,dict) else {}
 if isinstance(usage,dict):
  print('OPENAI_USAGE model='+model+' input_tokens='+str(usage.get('input_tokens','?'))+' output_tokens='+str(usage.get('output_tokens','?'))+' total_tokens='+str(usage.get('total_tokens','?')),file=sys.stderr,flush=True)
 return _extract_text(value)

def send(conn:socket.socket,value:dict)->None:
 raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
 if len(raw)>MAX_RESPONSE: raise RelayError('RESPONSE_TOO_LARGE')
 conn.sendall(raw)

def handle(conn:socket.socket)->None:
 try:
  pid,uid,_gid=peer_credentials(conn)
  if uid==0 or peer_cgroup(pid)!=ALLOWED_CGROUP:
   raise RelayError('PEER_AUTH_DENY')
  req=strict_request(recv_line(conn))
  send(conn,{'schema':'K.MODEL.RELAY.RESPONSE.2','status':'PASS','provider_id':'OPENAI_RESPONSES_API','text':call_openai(req)})
 except RelayError as exc:
  print('RELAY_ERROR '+str(exc),file=sys.stderr,flush=True)
  try: send(conn,{'schema':'K.MODEL.RELAY.RESPONSE.2','status':'FAIL','reason_code':str(exc)})
  except (RelayError,OSError): pass
def main()->int:
 if os.geteuid()==0: raise RelayError('MODEL_RELAY_MUST_BE_NONROOT')
 server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
 try: os.unlink(SOCK)
 except FileNotFoundError: pass
 server.bind(SOCK); os.chmod(SOCK,0o666); server.listen(8)
 while True:
  conn,_=server.accept()
  with conn: handle(conn)

if __name__=='__main__': raise SystemExit(main())
