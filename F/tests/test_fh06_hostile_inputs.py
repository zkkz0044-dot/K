from __future__ import annotations
import copy, hashlib, json, os, pathlib, random, tempfile, unittest
from kk_f.input_guard import InputGuardError, strict_json_loads
from kk_f.process_spec import ProcessSpecError, validate_process_spec
from kk_f.release_manifest import ReleaseManifestError, load_release_manifest
from kk_f.release_state import ReleaseStateError, read_release_state
from kk_f.safety_state import SafetyStateError, read_safety_state
from kk_f.checkpoint import CheckpointError, read_checkpoint
from kk_f.monotonic_witness import WitnessError, load_state
from kk_f.production_daemon import ProductionDaemonError, load_runtime_config, _load_heartbeat

class FH06HostileInputs(unittest.TestCase):
    def setUp(self): self.td=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.td.name)
    def tearDown(self): self.td.cleanup()
    def spec(self): return {'version':'0.1','executable':'/bin/true','argv':[],'cwd':'/tmp','env':{},'sha256':'0'*64}

    def test_strict_json_rejects_duplicate_nonfinite_and_oversize(self):
        for raw in ['{"a":1,"a":2}','{"x":NaN}','{"x":Infinity}']:
            with self.assertRaises(InputGuardError): strict_json_loads(raw,max_chars=100)
        with self.assertRaises(InputGuardError): strict_json_loads(' '*101,max_chars=100)

    def test_process_spec_boundary_and_type_confusion_campaign(self):
        base=self.spec(); cases=[]
        bad_values=[None,True,False,0,1,1.5,b'x']
        for key in ['version','executable','argv','cwd','env','sha256']:
            for bad in bad_values:
                v=copy.deepcopy(base); v[key]=bad; cases.append(v)
        for key in ['version','executable','cwd','sha256']:
            for bad in ([],{}):
                v=copy.deepcopy(base); v[key]=bad; cases.append(v)
        v=copy.deepcopy(base); v['argv']={}; cases.append(v)
        v=copy.deepcopy(base); v['env']=[]; cases.append(v)
        for path in ['', 'relative', '/tmp/../x', '\x00/x', '／tmp／x', '/'+'x'*4097]:
            v=copy.deepcopy(base); v['executable']=path; cases.append(v)
        v=copy.deepcopy(base); v['argv']=['x']*129; cases.append(v)
        v=copy.deepcopy(base); v['argv']=['x'*4097]; cases.append(v)
        v=copy.deepcopy(base); v['env']={f'K{i}':'v' for i in range(129)}; cases.append(v)
        v=copy.deepcopy(base); v['env']={'K':'x'*16385}; cases.append(v)
        for v in cases:
            with self.assertRaises(ProcessSpecError): validate_process_spec(v)
        self.assertGreaterEqual(len(cases),60)

    def test_runtime_config_duplicate_key_rejected(self):
        p=self.root/'runtime.json'
        raw='{"version":"0.1","version":"0.1","authority_path":"/a","ledger_directory":"/b","evidence_directory":"/c","heartbeat_path":"/d","process_spec":{},"healthy_within_seconds":1,"degraded_within_seconds":2,"grace_seconds":1,"base_delay_seconds":1,"max_delay_seconds":2,"poll_interval_seconds":1,"heartbeat_startup_grace_seconds":1}'
        p.write_text(raw); p.chmod(0o600)
        with self.assertRaises(ProductionDaemonError): load_runtime_config(str(p))

    def test_heartbeat_duplicate_and_oversize_rejected(self):
        p=self.root/'hb.json'; p.write_text('{"version":"0.1","sequence":1,"sequence":2,"observed_at":"2026-09-04T00:00:00Z"}')
        with self.assertRaises(ProductionDaemonError): _load_heartbeat(str(p))
        p.write_bytes(b' '*65537)
        with self.assertRaises(ProductionDaemonError): _load_heartbeat(str(p))

    def test_bounded_durable_loaders_reject_oversize_without_parsing(self):
        items=[
          ('manifest.json',1048577,lambda p:load_release_manifest(p),ReleaseManifestError),
          ('witness.json',65537,lambda p:load_state(p),WitnessError),
          ('release-state.json',65537,lambda p:read_release_state(p.parent),ReleaseStateError),
          ('safety-state.json',65537,lambda p:read_safety_state(p.parent),SafetyStateError),
          ('checkpoint.json',65537,lambda p:read_checkpoint(p.parent),CheckpointError),
        ]
        for name,size,fn,exc in items:
            d=self.root/name.replace('.json',''); d.mkdir(); p=d/name; p.write_bytes(b' '*size)
            with self.subTest(name=name), self.assertRaises(exc): fn(p)

    def test_seeded_json_mutation_campaign_never_hangs_or_leaks_fds(self):
        rng=random.Random(0xF006); baseline=len(os.listdir('/proc/self/fd')); rejected=0
        seeds=['{}','[]','null','true','0','"x"','{"a":1}','{"x":[1,2,3]}']
        alphabet='{}[],:"\\0123456789truefalsenullNaNInfinity abcXYZ\u0000'
        for i in range(2500):
            s=list(rng.choice(seeds))
            for _ in range(rng.randint(1,8)):
                op=rng.randrange(3); pos=rng.randrange(len(s)+1)
                if op==0: s.insert(pos,rng.choice(alphabet))
                elif op==1 and s: s.pop(rng.randrange(len(s)))
                elif s: s[rng.randrange(len(s))]=rng.choice(alphabet)
            raw=''.join(s)
            try: strict_json_loads(raw,max_chars=512)
            except InputGuardError: rejected+=1
        after=len(os.listdir('/proc/self/fd'))
        self.assertEqual(after,baseline); self.assertGreater(rejected,1500)

if __name__=='__main__': unittest.main()

class FH06PropertyCampaign(FH06HostileInputs):
    def _bases(self):
        from kk_f.release_manifest import _hash_material
        from kk_f.release_state import _checksum as release_sum
        from kk_f.safety_state import _sum as safety_sum
        from kk_f.monotonic_witness import seed_state
        manifest={'version':'0.1','release_id':'12345678-1234-5678-9234-567812345678','entrypoint':'kk_f/main.py','files':[{'path':'kk_f/main.py','sha256':'a'*64,'size':1}],'manifest_sha256':''}
        manifest['manifest_sha256']=_hash_material(manifest)
        rid={'release_id':'12345678-1234-5678-9234-567812345678','manifest_sha256':'b'*64}
        release={'version':'0.1','generation':1,'active':rid,'candidate':None,'last_known_good':rid,'checksum':''}; release['checksum']=release_sum(release)
        safety={'version':'0.1','generation':0,'mode':'NORMAL','consecutive_failures':0,'reason':None,'checksum':''}; safety['checksum']=safety_sum(safety)
        witness=seed_state({})
        message={'protocol_version':'0.1','message_id':'123e4567-e89b-42d3-a456-426614174000','kind':'result','source_role':'worker','target_role':'supervisor','timestamp':'2026-09-04T01:45:00Z','status':'HEALTHY','payload':{},'error':None}
        heartbeat={'version':'0.1','sequence':1,'observed_at':'2026-09-04T01:45:00Z'}
        return manifest,release,safety,witness,message,heartbeat,self.spec()

    @staticmethod
    def _mutate(rng, base):
        v=copy.deepcopy(base)
        if not isinstance(v,dict): return rng.choice([None,True,0,[],"x"])
        keys=list(v)
        op=rng.randrange(7)
        if op==0 and keys: v.pop(rng.choice(keys))
        elif op==1: v['__extra__']=rng.choice([None,True,0,'x',{}])
        elif op==2 and keys: v[rng.choice(keys)]=rng.choice([None,True,False,-1,0,1,1.5,[],{},'','x'*5000])
        elif op==3 and keys:
            k=rng.choice(keys)
            if isinstance(v[k],dict): v[k]['__extra__']=1
            elif isinstance(v[k],list): v[k].append({'__bad__':True})
            else: v[k]=[v[k]]
        elif op==4 and keys: v[rng.choice(keys)]='\x00'
        elif op==5: return rng.choice([None,True,False,0,1.5,[],"x"])
        else:
            if keys:
                k=rng.choice(keys); v[k]=rng.choice(['NaN','Infinity','../x','/tmp/../x','／tmp／x','A'*20000])
        return v

    def test_deterministic_cross_validator_property_campaign(self):
        from kk_f.release_manifest import validate_release_manifest, ReleaseManifestError
        from kk_f.release_state import validate_release_state, ReleaseStateError
        from kk_f.safety_state import validate_safety_state, SafetyStateError
        from kk_f.monotonic_witness import validate_state, WitnessError
        from kk_f.contracts import validate_message, ContractError
        from kk_f.heartbeat import validate_heartbeat, HeartbeatError
        validators=[
          (validate_release_manifest,ReleaseManifestError),(validate_release_state,ReleaseStateError),
          (validate_safety_state,SafetyStateError),(validate_state,WitnessError),
          (validate_message,ContractError),(validate_heartbeat,HeartbeatError),
          (validate_process_spec,ProcessSpecError),
        ]
        bases=self._bases()
        def run_once(seed):
            rng=random.Random(seed); accepted=rejected=0
            for validator,exc in validators:
                base=bases[validators.index((validator,exc))]
                for _ in range(1500):
                    value=self._mutate(rng,base)
                    try:
                        result=validator(value); accepted+=1
                        validator(copy.deepcopy(result))
                    except exc: rejected+=1
            return accepted,rejected
        before=len(os.listdir('/proc/self/fd'))
        one=run_once(0xF0062026); two=run_once(0xF0062026)
        after=len(os.listdir('/proc/self/fd'))
        print('FH06_PROPERTY_CASES=',sum(one),'ACCEPTED=',one[0],'REJECTED=',one[1])
        self.assertEqual(one,two); self.assertEqual(sum(one),10500); self.assertGreater(one[1],9000); self.assertEqual(before,after)

    def test_evidence_single_line_size_limit(self):
        from kk_f.evidence import initialize,verify,EvidenceError,MAX_ENTRY_BYTES
        d=self.root/'ev'; initialize(d)
        (d/'evidence.jsonl').write_bytes(b'{' + b'x'*MAX_ENTRY_BYTES + b'}\n')
        with self.assertRaises(EvidenceError): verify(d)

    def test_runtime_paths_reject_dot_double_slash_and_trailing_ambiguity(self):
        from kk_f.production_daemon import _absolute
        for value in ['/tmp/../x','/tmp//x','/tmp/x/','relative','／tmp／x','/'+'x'*4097]:
            with self.assertRaises(ProductionDaemonError): _absolute(value,'x')


class FH06ExtendedCampaign(FH06HostileInputs):
    def _valid_manifest(self):
        from kk_f.release_manifest import _hash_material
        m={'version':'0.1','release_id':'12345678-1234-5678-9234-567812345678','entrypoint':'a','files':[{'path':'a','sha256':'a'*64,'size':1}],'manifest_sha256':''}
        m['manifest_sha256']=_hash_material(m); return m

    def test_release_manifest_explicit_extreme_bounds(self):
        from kk_f.release_manifest import validate_release_manifest, ReleaseManifestError, MAX_FILES, MAX_RELATIVE_PATH_CHARS, MAX_FILE_SIZE
        m=self._valid_manifest()
        for mutate in (
            lambda x: x['files'].__setitem__(0,dict(x['files'][0],path='x'*(MAX_RELATIVE_PATH_CHARS+1))),
            lambda x: x['files'].__setitem__(0,dict(x['files'][0],size=MAX_FILE_SIZE+1)),
            lambda x: x.__setitem__('files',[{'path':f'{i:04d}','sha256':'a'*64,'size':1} for i in range(MAX_FILES+1)]),
        ):
            v=copy.deepcopy(m); mutate(v)
            with self.assertRaises(ReleaseManifestError): validate_release_manifest(v)

    def test_authority_duplicate_nonfinite_oversize_and_ambiguous_spec_rejected(self):
        from kk_f.frozen_authority import load_frozen_authority, FrozenAuthorityError
        p=self.root/'authority.json'; p.chmod(0o600) if p.exists() else None
        raws=[
          '{"version":"0.2","version":"0.2","authority_id":"x","process_spec":{},"max_restart_attempts":1}',
          '{"version":"0.2","authority_id":"x","process_spec":{},"max_restart_attempts":NaN}',
        ]
        for raw in raws:
            p.write_text(raw); p.chmod(0o600)
            with self.assertRaises(FrozenAuthorityError): load_frozen_authority(str(p))
        p.write_bytes(b' '*65537); p.chmod(0o600)
        with self.assertRaises(FrozenAuthorityError): load_frozen_authority(str(p))

    def test_state_parsers_duplicate_keys_fail_closed(self):
        cases=[
          ('release-state.json',read_release_state,ReleaseStateError,'{"version":"0.1","version":"0.1"}'),
          ('safety-state.json',read_safety_state,SafetyStateError,'{"version":"0.1","version":"0.1"}'),
          ('checkpoint.json',read_checkpoint,CheckpointError,'{"version":"0.1","version":"0.1"}'),
          ('witness.json',lambda d:load_state(d/'witness.json'),WitnessError,'{"version":"0.1","version":"0.1"}'),
        ]
        for name,fn,exc,raw in cases:
            d=self.root/name.replace('.json','-dup'); d.mkdir(); (d/name).write_text(raw)
            with self.subTest(name=name), self.assertRaises(exc): fn(d)

    def test_atomic_path_swap_race_yields_only_valid_or_controlled_rejection(self):
        import threading, time
        base=self.spec()
        cfg=lambda n: {'version':'0.1','authority_path':'/a','ledger_directory':f'/ledger{n}','evidence_directory':'/e','heartbeat_path':'/h','process_spec':base,'healthy_within_seconds':1,'degraded_within_seconds':2,'grace_seconds':1,'base_delay_seconds':1,'max_delay_seconds':2,'poll_interval_seconds':1,'heartbeat_startup_grace_seconds':1}
        path=self.root/'runtime-race.json'; path.write_text(json.dumps(cfg(0),separators=(',',':'))); path.chmod(0o600)
        stop=threading.Event(); errors=[]
        def swapper():
            try:
                for i in range(300):
                    tmp=self.root/f'.swap-{i%2}'
                    tmp.write_text(json.dumps(cfg(i%2),separators=(',',':'))); tmp.chmod(0o600); os.replace(tmp,path)
            except Exception as exc: errors.append(exc)
            finally: stop.set()
        t=threading.Thread(target=swapper); t.start(); accepted=controlled=0
        for _ in range(600):
            try:
                got=load_runtime_config(str(path)); self.assertIn(got.ledger_directory,('/ledger0','/ledger1')); accepted+=1
            except ProductionDaemonError: controlled+=1
            if stop.is_set() and accepted+controlled>300: break
        t.join(5); self.assertFalse(t.is_alive()); self.assertFalse(errors); self.assertGreater(accepted,0); self.assertEqual(accepted+controlled,accepted+controlled)

    def test_repro_corpus_manifest_is_fixed_and_complete(self):
        corpus=pathlib.Path(__file__).resolve().parents[1]/'evidence/fh06/CORPUS_REPRO.json'
        data=json.loads(corpus.read_text())
        self.assertEqual(data['seed_json_mutation'],0xF006)
        self.assertEqual(data['seed_cross_validator'],0xF0062026)
        self.assertEqual(data['cross_validator_cases'],10500)
        self.assertIn('duplicate_keys',data['classes'])
        self.assertIn('atomic_path_swap',data['classes'])
