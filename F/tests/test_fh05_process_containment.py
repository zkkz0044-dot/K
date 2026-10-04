from __future__ import annotations
import hashlib, json, os, pathlib, tempfile, time, unittest
from kk_f.managed_process import launch_managed
from kk_f.process_spec import ProcessSpecError, validate_process_spec

ROOT = pathlib.Path(__file__).resolve().parents[1]

class FH05ContainmentTests(unittest.TestCase):
    def test_unit_has_nonroot_capability_and_resource_bounds(self):
        text=(ROOT/'deploy/kk-f.service').read_text()
        required=['User=kk-f','Group=kk-f','NoNewPrivileges=yes','CapabilityBoundingSet=','AmbientCapabilities=',
                  'PrivateDevices=yes','ProtectProc=invisible','RestrictNamespaces=yes','RestrictAddressFamilies=AF_UNIX',
                  'MemoryHigh=192M','MemoryMax=256M','MemorySwapMax=128M','TasksMax=64','CPUQuota=50%','LimitNOFILE=256','LimitCORE=0']
        for token in required: self.assertIn(token,text)
    def test_dangerous_loader_and_interpreter_env_rejected(self):
        base={'version':'0.1','executable':'/bin/true','argv':[],'cwd':'/tmp','env':{},'sha256':'0'*64}
        for key in ['LD_PRELOAD','LD_LIBRARY_PATH','PYTHONPATH','PYTHONHOME','PYTHONINSPECT','NODE_OPTIONS','BASH_ENV','ENV','GCONV_PATH']:
            value=dict(base); value['env']={key:'x'}
            with self.subTest(key=key), self.assertRaises(ProcessSpecError): validate_process_spec(value)
    def test_managed_worker_receives_only_declared_environment_and_no_unintended_fd(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); out=root/'out.json'; script=root/'probe.py'
            script.write_text('#!/usr/bin/python3\nimport json,os\nout=os.environ["OUT"]\nfds=[]\nfor n in range(3,64):\n try: os.fstat(n); fds.append(n)\n except OSError: pass\njson.dump({"env":dict(os.environ),"fds":fds,"uid":os.getuid()},open(out,"w"),sort_keys=True)\n')
            script.chmod(0o700); inherited=os.open(root/'parent-fd',os.O_CREAT|os.O_RDWR,0o600)
            try:
                os.environ['FH05_SHOULD_NOT_LEAK']='secret'
                digest=hashlib.sha256(script.read_bytes()).hexdigest()
                spec={'version':'0.1','executable':str(script),'argv':[],'cwd':str(root),'env':{'OUT':str(out),'DECLARED':'yes'},'sha256':digest}
                proc=launch_managed(spec)
                deadline=time.time()+3
                while not out.exists() and time.time()<deadline: time.sleep(.02)
                proc.stop(grace_seconds=1)
                data=json.loads(out.read_text())
                self.assertEqual(data['env']['DECLARED'],'yes')
                self.assertEqual(data['env']['OUT'],str(out))
                self.assertNotIn('FH05_SHOULD_NOT_LEAK',data['env'])
                self.assertNotIn(inherited,data['fds'])
            finally:
                os.close(inherited); os.environ.pop('FH05_SHOULD_NOT_LEAK',None)

if __name__=='__main__': unittest.main()
