from __future__ import annotations
import hashlib, json, os, pathlib, tempfile, unittest

from kk_f import checkpoint, monotonic_witness, release_state, safety_state
from kk_f.checkpoint import read_checkpoint, write_checkpoint
from kk_f.monotonic_witness import load_state, save_state, seed_state
from kk_f.release_activation import _switch, initialize_current
from kk_f.release_recovery import reconcile_release
from kk_f.release_state import declare_candidate, initialize_release_state, read_release_state
from kk_f.release_store_guard import seal_private_stage
from kk_f.safety_state import initialize_safety_state, read_safety_state, _record_failure


def _fork_run(fn):
    pid=os.fork()
    if pid==0:
        try:
            fn(); os._exit(0)
        except BaseException:
            os._exit(99)
    _, status=os.waitpid(pid,0)
    return os.waitstatus_to_exitcode(status)


def _crash_before_replace(module, fn):
    def child():
        module.os.replace=lambda *a,**k: os._exit(71)
        fn()
    return _fork_run(child)


def _crash_after_replace_before_dir_fsync(module, fn):
    def child():
        real=module.os.fsync; calls={'n':0}
        def wrapped(fd):
            real(fd); calls['n']+=1
            if calls['n']==2: os._exit(72)
        module.os.fsync=wrapped
        fn()
    return _fork_run(child)


def _canon(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def _rid(ch): return ch*8+'-'+ch*4+'-4'+ch*3+'-8'+ch*3+'-'+ch*12

def _release(root,rid,data):
    root.mkdir(); p=root/'app'; p.write_bytes(data)
    files=[{'path':'app','sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}]
    m={'version':'0.1','release_id':rid,'entrypoint':'app','files':files,'manifest_sha256':''}
    m['manifest_sha256']=hashlib.sha256(_canon({k:m[k] for k in ('version','release_id','entrypoint','files')})).hexdigest()
    seal_private_stage(root,root.stat().st_dev); return m


class FH07CrashTorture(unittest.TestCase):
    def setUp(self): self.td=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.td.name)
    def tearDown(self): self.td.cleanup()

    def test_checkpoint_pre_replace_crash_recovers_old_and_cleans_temp(self):
        d=self.root/'cp'; write_checkpoint(d,0,'READY',{})
        self.assertEqual(_crash_before_replace(checkpoint,lambda:write_checkpoint(d,1,'FAILED',{'x':1})),71)
        self.assertEqual(read_checkpoint(d)['generation'],0)
        self.assertFalse((d/'checkpoint.json.tmp').exists())

    def test_checkpoint_post_replace_pre_dir_fsync_is_exact_new(self):
        d=self.root/'cp2'; write_checkpoint(d,0,'READY',{})
        self.assertEqual(_crash_after_replace_before_dir_fsync(checkpoint,lambda:write_checkpoint(d,1,'FAILED',{'x':1})),72)
        self.assertEqual(read_checkpoint(d)['generation'],1)
        self.assertFalse((d/'checkpoint.json.tmp').exists())

    def test_witness_pre_replace_crash_does_not_poison_next_write(self):
        p=self.root/'witness.json'; old=seed_state({'restart_ledger':{'generation':0,'digest':'a'*64}}); save_state(p,old)
        new=seed_state({'restart_ledger':{'generation':1,'digest':'b'*64}})
        self.assertEqual(_crash_before_replace(monotonic_witness,lambda:save_state(p,new)),71)
        self.assertEqual(load_state(p),old)
        self.assertFalse((self.root/'witness.json.tmp').exists())
        save_state(p,new); self.assertEqual(load_state(p),new)

    def test_release_state_pre_and_post_replace_converge_old_or_new_no_temp(self):
        d=self.root/'rs'; a={'release_id':_rid('a'),'manifest_sha256':'a'*64}; b={'release_id':_rid('b'),'manifest_sha256':'b'*64}
        initialize_release_state(d,a)
        self.assertEqual(_crash_before_replace(release_state,lambda:declare_candidate(d,b)),71)
        self.assertIsNone(read_release_state(d)['candidate']); self.assertFalse((d/'release-state.json.tmp').exists())
        self.assertEqual(_crash_after_replace_before_dir_fsync(release_state,lambda:declare_candidate(d,b)),72)
        self.assertEqual(read_release_state(d)['candidate'],b); self.assertFalse((d/'release-state.json.tmp').exists())

    def test_safety_state_pre_and_post_replace_converge_old_or_new_no_temp(self):
        d=self.root/'safe'; initialize_safety_state(d)
        self.assertEqual(_crash_before_replace(safety_state,lambda:_record_failure(d,3)),71)
        self.assertEqual(read_safety_state(d)['consecutive_failures'],0); self.assertFalse((d/'safety-state.json.tmp').exists())
        self.assertEqual(_crash_after_replace_before_dir_fsync(safety_state,lambda:_record_failure(d,3)),72)
        self.assertEqual(read_safety_state(d)['consecutive_failures'],1); self.assertFalse((d/'safety-state.json.tmp').exists())

    def test_release_pointer_pre_replace_hard_exit_recovery_cleans_orphan(self):
        store=self.root/'store'; ptr=self.root/'ptr'; state=self.root/'state'; store.mkdir(); ptr.mkdir()
        a,b=_rid('a'),_rid('b'); am=_release(store/a,a,b'A'); bm=_release(store/b,b,b'B'); reg={a:am,b:bm}
        initialize_release_state(state,{'release_id':a,'manifest_sha256':am['manifest_sha256']}); initialize_current(ptr,a); declare_candidate(state,{'release_id':b,'manifest_sha256':bm['manifest_sha256']})
        def child():
            import kk_f.release_activation as ra
            ra.os.replace=lambda *args,**kwargs: os._exit(73)
            _switch(ptr,b)
        self.assertEqual(_fork_run(child),73)
        self.assertTrue(list(ptr.glob('.current-*')))
        r=reconcile_release(store,ptr,state,reg); self.assertEqual(r['action'],'NO_ACTION'); self.assertEqual(os.readlink(ptr/'current'),a)
        self.assertEqual(list(ptr.glob('.current-*')),[])

if __name__=='__main__': unittest.main()

import multiprocessing, time
from kk_f import evidence as evidence_mod, release_activation as activation_mod
from kk_f.evidence import GENESIS_HASH, append as evidence_append, initialize as evidence_initialize, verify as evidence_verify
from kk_f.witness_daemon import run_server

BASE_RECORD={
 'protocol_version':'0.1','message_id':'123e4567-e89b-42d3-a456-426614174000','kind':'result',
 'source_role':'worker','target_role':'supervisor','timestamp':'2026-09-04T01:45:00Z',
 'status':'HEALTHY','payload':{'case':'fh07'},'error':None,
}

class _WitnessHarness:
    def __init__(self,root):
        self.root=root; self.state=root/'witness.json'; self.sock=root/'sock'/'witness.sock'; self.proc=None
        save_state(self.state,seed_state({'evidence':{'generation':0,'digest':GENESIS_HASH}}))
    def start(self):
        self.proc=multiprocessing.Process(target=run_server,args=(str(self.state),str(self.sock)),kwargs={'allowed_uid':os.getuid(),'allowed_gid':os.getgid()}); self.proc.start()
        end=time.monotonic()+3
        while not self.sock.exists() and time.monotonic()<end: time.sleep(.01)
        if not self.sock.exists(): raise RuntimeError('witness did not start')
        os.environ['KK_F_WITNESS_SOCKET']=str(self.sock)
    def stop(self):
        os.environ.pop('KK_F_WITNESS_SOCKET',None)
        if self.proc is not None: self.proc.terminate(); self.proc.join(5); self.proc=None

class FH07EvidenceCrashWindows(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.td.name); self.h=_WitnessHarness(self.root); self.ev=self.root/'ev'; evidence_initialize(self.ev); self.h.start()
    def tearDown(self): self.h.stop(); self.td.cleanup()
    def _append_child(self,configure):
        def child(): configure(); evidence_append(self.ev,dict(BASE_RECORD))
        return _fork_run(child)
    def _assert_exact_new(self):
        got=evidence_verify(self.ev); self.assertEqual(got['count'],1); self.assertFalse((self.ev/'HEAD.json.tmp').exists())
        ws=load_state(self.h.state)['channels']['evidence']; self.assertEqual(ws['generation'],1); self.assertIsNone(ws['pending']); return got
    def test_power_loss_before_log_fsync_can_recover_exact_old(self):
        old=(self.ev/'evidence.jsonl').read_bytes()
        def cfg(): evidence_mod.os.fsync=lambda fd: os._exit(74)
        self.assertEqual(self._append_child(cfg),74)
        # Model the power-loss outcome where the non-fsynced append is lost.
        (self.ev/'evidence.jsonl').write_bytes(old)
        got=evidence_verify(self.ev); self.assertEqual(got['count'],0)
        ws=load_state(self.h.state)['channels']['evidence']; self.assertEqual(ws['generation'],0); self.assertIsNone(ws['pending'])
    def test_crash_after_log_fsync_before_head_write_recovers_exact_new(self):
        def cfg(): evidence_mod._atomic_write=lambda *a,**k: os._exit(75)
        self.assertEqual(self._append_child(cfg),75); self._assert_exact_new()
    def test_crash_after_head_temp_fsync_before_replace_recovers_exact_new_and_temp(self):
        def cfg(): evidence_mod.os.replace=lambda *a,**k: os._exit(76)
        self.assertEqual(self._append_child(cfg),76); self.assertTrue((self.ev/'HEAD.json.tmp').exists()); self._assert_exact_new()
    def test_crash_after_head_replace_before_dir_fsync_recovers_exact_new(self):
        def cfg():
            real=evidence_mod.os.fsync; calls={'n':0}
            def wrapped(fd):
                real(fd); calls['n']+=1
                if calls['n']==3: os._exit(77)
            evidence_mod.os.fsync=wrapped
        self.assertEqual(self._append_child(cfg),77); self._assert_exact_new()

class FH07AdditionalDurableWindows(unittest.TestCase):
    def setUp(self): self.td=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.td.name)
    def tearDown(self): self.td.cleanup()
    def _before_temp_fsync(self,module,fn,code=78):
        def child(): module.os.fsync=lambda fd: os._exit(code); fn()
        return _fork_run(child)
    def test_checkpoint_before_temp_fsync_is_exact_old_and_cleanup(self):
        d=self.root/'cp'; write_checkpoint(d,0,'READY',{})
        self.assertEqual(self._before_temp_fsync(checkpoint,lambda:write_checkpoint(d,1,'FAILED',{})),78)
        self.assertEqual(read_checkpoint(d)['generation'],0); self.assertFalse((d/'checkpoint.json.tmp').exists())
    def test_witness_before_temp_fsync_is_exact_old_and_retryable(self):
        p=self.root/'w'; old=seed_state({'restart_ledger':{'generation':0,'digest':'a'*64}}); new=seed_state({'restart_ledger':{'generation':1,'digest':'b'*64}}); save_state(p,old)
        self.assertEqual(self._before_temp_fsync(monotonic_witness,lambda:save_state(p,new),79),79)
        self.assertEqual(load_state(p),old); save_state(p,new); self.assertEqual(load_state(p),new)
    def test_release_state_before_temp_fsync_is_exact_old(self):
        d=self.root/'rs'; a={'release_id':_rid('a'),'manifest_sha256':'a'*64}; b={'release_id':_rid('b'),'manifest_sha256':'b'*64}; initialize_release_state(d,a)
        self.assertEqual(self._before_temp_fsync(release_state,lambda:declare_candidate(d,b),80),80); self.assertIsNone(read_release_state(d)['candidate']); self.assertFalse((d/'release-state.json.tmp').exists())
    def test_safety_before_temp_fsync_is_exact_old(self):
        d=self.root/'ss'; initialize_safety_state(d)
        self.assertEqual(self._before_temp_fsync(safety_state,lambda:_record_failure(d,3),81),81); self.assertEqual(read_safety_state(d)['consecutive_failures'],0); self.assertFalse((d/'safety-state.json.tmp').exists())

class FH07ReleaseTransactionWindows(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.td.name); self.store=self.root/'store'; self.ptr=self.root/'ptr'; self.state=self.root/'state'; self.store.mkdir(); self.ptr.mkdir(); self.a=_rid('a'); self.b=_rid('b'); self.am=_release(self.store/self.a,self.a,b'A'); self.bm=_release(self.store/self.b,self.b,b'B'); self.reg={self.a:self.am,self.b:self.bm}; initialize_release_state(self.state,{'release_id':self.a,'manifest_sha256':self.am['manifest_sha256']}); initialize_current(self.ptr,self.a); declare_candidate(self.state,{'release_id':self.b,'manifest_sha256':self.bm['manifest_sha256']})
    def tearDown(self): self.td.cleanup()
    def _assert_old(self):
        r=reconcile_release(self.store,self.ptr,self.state,self.reg); s=read_release_state(self.state); self.assertEqual(s['active']['release_id'],self.a); self.assertEqual(os.readlink(self.ptr/'current'),self.a); self.assertEqual(list(self.ptr.glob('.current-*')),[]); return r
    def _assert_new(self):
        r=reconcile_release(self.store,self.ptr,self.state,self.reg); s=read_release_state(self.state); self.assertEqual(s['active']['release_id'],self.b); self.assertEqual(os.readlink(self.ptr/'current'),self.b); self.assertEqual(list(self.ptr.glob('.current-*')),[]); return r
    def test_crash_after_pointer_replace_before_pointer_dir_fsync_converges_old(self):
        def child():
            activation_mod._fsync_dir=lambda p: os._exit(82)
            from kk_f.release_activation import activate_candidate
            activate_candidate(self.store,self.ptr,self.state,self.bm)
        self.assertEqual(_fork_run(child),82); self._assert_old()
    def test_crash_after_pointer_durable_before_state_transaction_converges_old(self):
        def child():
            activation_mod.commit_candidate=lambda *a,**k: os._exit(83)
            from kk_f.release_activation import activate_candidate
            activate_candidate(self.store,self.ptr,self.state,self.bm)
        self.assertEqual(_fork_run(child),83); self._assert_old()
    def test_crash_state_pre_replace_after_pointer_switch_converges_old_and_cleans_temp(self):
        def child():
            release_state.os.replace=lambda *a,**k: os._exit(84)
            from kk_f.release_activation import activate_candidate
            activate_candidate(self.store,self.ptr,self.state,self.bm)
        self.assertEqual(_fork_run(child),84); self._assert_old(); self.assertFalse((self.state/'release-state.json.tmp').exists())
    def test_crash_state_post_replace_pre_dir_fsync_after_pointer_switch_converges_new(self):
        def child():
            real=release_state.os.replace
            def wrapped(src,dst,*args,**kwargs):
                real(src,dst,*args,**kwargs)
                if pathlib.Path(dst).name=='release-state.json': os._exit(85)
            release_state.os.replace=wrapped
            from kk_f.release_activation import activate_candidate
            activate_candidate(self.store,self.ptr,self.state,self.bm)
        self.assertEqual(_fork_run(child),85); self._assert_new()
    def test_hard_exit_after_lkg_state_commit_before_pointer_repair_retries(self):
        from kk_f.release_state import commit_candidate
        commit_candidate(self.state); _switch(self.ptr,self.b); (self.store/self.b/'app').write_bytes(b'BAD')
        import kk_f.release_recovery as rr
        def child(): rr._switch=lambda *a,**k: os._exit(86); rr.reconcile_release(self.store,self.ptr,self.state,self.reg)
        self.assertEqual(_fork_run(child),86)
        s=read_release_state(self.state); self.assertEqual(s['active']['release_id'],self.a); self.assertEqual(os.readlink(self.ptr/'current'),self.b)
        self._assert_old()

class FH07RepeatedKillRestart(unittest.TestCase):
    def test_40_checkpoint_kill_restart_cycles_have_no_temp_or_fd_drift(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td)/'cp'; write_checkpoint(d,0,'READY',{}); before=len(os.listdir('/proc/self/fd'))
            for gen in range(1,41):
                if gen%2:
                    rc=_crash_before_replace(checkpoint,lambda g=gen:write_checkpoint(d,g,'FAILED',{'g':g})); self.assertEqual(rc,71); self.assertEqual(read_checkpoint(d)['generation'],gen-1)
                    write_checkpoint(d,gen,'FAILED',{'g':gen})
                else:
                    rc=_crash_after_replace_before_dir_fsync(checkpoint,lambda g=gen:write_checkpoint(d,g,'FAILED',{'g':g})); self.assertEqual(rc,72); self.assertEqual(read_checkpoint(d)['generation'],gen)
                self.assertFalse((d/'checkpoint.json.tmp').exists())
            self.assertEqual(read_checkpoint(d)['generation'],40); self.assertLessEqual(len(os.listdir('/proc/self/fd')),before+1)

import uuid

def _ridn(n): return str(uuid.uuid5(uuid.NAMESPACE_URL,f'kk-f-fh07-{n}'))

class FH07RepeatedCrossSubsystem(unittest.TestCase):
    def test_witness_post_replace_pre_dir_fsync_is_exact_new(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'witness.json'; old=seed_state({'restart_ledger':{'generation':0,'digest':'a'*64}}); new=seed_state({'restart_ledger':{'generation':1,'digest':'b'*64}}); save_state(p,old)
            self.assertEqual(_crash_after_replace_before_dir_fsync(monotonic_witness,lambda:save_state(p,new)),72)
            self.assertEqual(load_state(p),new); self.assertFalse((p.parent/'witness.json.tmp').exists())

    def test_20_witness_kill_restart_cycles_no_poisoned_temp(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'witness.json'; cur=seed_state({'restart_ledger':{'generation':0,'digest':'0'*64}}); save_state(p,cur); before=len(os.listdir('/proc/self/fd'))
            for n in range(1,21):
                nxt=seed_state({'restart_ledger':{'generation':n,'digest':hashlib.sha256(str(n).encode()).hexdigest()}})
                if n%2:
                    self.assertEqual(_crash_before_replace(monotonic_witness,lambda v=nxt:save_state(p,v)),71); self.assertEqual(load_state(p),cur); save_state(p,nxt)
                else:
                    self.assertEqual(_crash_after_replace_before_dir_fsync(monotonic_witness,lambda v=nxt:save_state(p,v)),72); self.assertEqual(load_state(p),nxt)
                cur=nxt; self.assertFalse((p.parent/'witness.json.tmp').exists())
            self.assertEqual(load_state(p),cur); self.assertLessEqual(len(os.listdir('/proc/self/fd')),before+1)

    def test_20_release_activation_hard_exit_recovery_cycles(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); store=root/'store'; ptr=root/'ptr'; state=root/'state'; store.mkdir(); ptr.mkdir(); a=_ridn(0); am=_release(store/a,a,b'0'); registry={a:am}; initialize_release_state(state,{'release_id':a,'manifest_sha256':am['manifest_sha256']}); initialize_current(ptr,a); active=a; before=len(os.listdir('/proc/self/fd'))
            from kk_f.release_activation import activate_candidate
            for n in range(1,21):
                rid=_ridn(n); m=_release(store/rid,rid,str(n).encode()); registry[rid]=m; declare_candidate(state,{'release_id':rid,'manifest_sha256':m['manifest_sha256']}); old=active
                if n%2:
                    def child(): activation_mod.commit_candidate=lambda *a,**k: os._exit(91); activate_candidate(store,ptr,state,m)
                    self.assertEqual(_fork_run(child),91); reconcile_release(store,ptr,state,registry); self.assertEqual(read_release_state(state)['active']['release_id'],old); activate_candidate(store,ptr,state,m)
                else:
                    def child():
                        real=release_state.os.replace
                        def wrapped(src,dst,*args,**kwargs):
                            real(src,dst,*args,**kwargs)
                            if pathlib.Path(dst).name=='release-state.json': os._exit(92)
                        release_state.os.replace=wrapped; activate_candidate(store,ptr,state,m)
                    self.assertEqual(_fork_run(child),92); reconcile_release(store,ptr,state,registry)
                active=rid; self.assertEqual(read_release_state(state)['active']['release_id'],active); self.assertEqual(os.readlink(ptr/'current'),active); self.assertEqual(list(ptr.glob('.current-*')),[]); self.assertFalse((state/'release-state.json.tmp').exists())
            self.assertLessEqual(len(os.listdir('/proc/self/fd')),before+1)

    def test_12_evidence_witness_hard_exit_restart_cycles(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); h=_WitnessHarness(root); ev=root/'ev'; evidence_initialize(ev); h.start(); before=len(os.listdir('/proc/self/fd'))
            try:
                for n in range(1,13):
                    # Parent may be pinned from prior recovery; restart witness so the crash child is controller.
                    h.stop(); h.start()
                    rec=dict(BASE_RECORD); rec['message_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,f'fh07-evidence-{n}')); rec['payload']={'case':'fh07-repeat','n':n}
                    def child():
                        if n%2: evidence_mod._atomic_write=lambda *a,**k: os._exit(93)
                        else: evidence_mod.os.replace=lambda *a,**k: os._exit(94)
                        evidence_append(ev,rec)
                    self.assertEqual(_fork_run(child),93 if n%2 else 94)
                    got=evidence_verify(ev); self.assertEqual(got['count'],n); self.assertFalse((ev/'HEAD.json.tmp').exists())
                    ws=load_state(h.state)['channels']['evidence']; self.assertEqual(ws['generation'],n); self.assertIsNone(ws['pending'])
                self.assertLessEqual(len(os.listdir('/proc/self/fd')),before+2)
            finally: h.stop()
