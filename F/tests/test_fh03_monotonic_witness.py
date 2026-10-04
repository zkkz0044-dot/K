from __future__ import annotations

import json
import multiprocessing
import os
import pathlib
import socket
import tempfile
import time
import unittest

from kk_f.monotonic_witness import (
    WitnessError, commit, empty_state, load_state, prepare, recover, save_state, seed_state, validate_state, verify,
)
from kk_f.witness_client import WitnessClientError, verify as client_verify
from kk_f.witness_daemon import run_server

A = "a" * 64
B = "b" * 64
C = "c" * 64


def _server(state, sock):
    run_server(state, sock, allowed_uid=65534, allowed_gid=65534)


def _nobody_client(sock, queue):
    try:
        os.setgid(65534); os.setuid(65534)
        client_verify(sock, "restart_ledger", 5, A)
        queue.put("OK")
    except Exception as exc:
        queue.put(type(exc).__name__ + ":" + str(exc))



def _child_verify(sock):
    try:
        client_verify(sock, "restart_ledger", 5, A)
        return "ACCEPT"
    except Exception as exc:
        return "REJECT:"+type(exc).__name__+":"+str(exc)

class FH03WitnessTests(unittest.TestCase):
    def test_empty_state_exact_channels(self):
        state = empty_state()
        self.assertEqual(set(state["channels"]), {"restart_ledger","evidence","release_state","safety_state"})
        validate_state(state)

    def test_seed_and_exact_verify(self):
        state = seed_state({"restart_ledger":{"generation":5,"digest":A}})
        verify(state,"restart_ledger",5,A)
        with self.assertRaises(WitnessError): verify(state,"restart_ledger",4,A)
        with self.assertRaises(WitnessError): verify(state,"restart_ledger",5,B)

    def test_prepare_requires_exact_current_and_strict_advance(self):
        state=seed_state({"restart_ledger":{"generation":5,"digest":A}})
        for gen,digest,newgen in ((4,A,6),(5,B,6),(5,A,5),(5,A,4)):
            with self.assertRaises(WitnessError): prepare(state,"restart_ledger",gen,digest,newgen,B)
        p=prepare(state,"restart_ledger",5,A,6,B)
        self.assertEqual(p["channels"]["restart_ledger"]["pending"],{"generation":6,"digest":B})

    def test_commit_only_exact_pending(self):
        p=prepare(seed_state({"restart_ledger":{"generation":5,"digest":A}}),"restart_ledger",5,A,6,B)
        with self.assertRaises(WitnessError): commit(p,"restart_ledger",6,C)
        c=commit(p,"restart_ledger",6,B)
        verify(c,"restart_ledger",6,B)

    def test_recover_exact_old_aborts_pending(self):
        p=prepare(seed_state({"evidence":{"generation":3,"digest":A}}),"evidence",3,A,4,B)
        r=recover(p,"evidence",3,A)
        verify(r,"evidence",3,A)
        self.assertIsNone(r["channels"]["evidence"]["pending"])

    def test_recover_exact_new_commits_pending(self):
        p=prepare(seed_state({"evidence":{"generation":3,"digest":A}}),"evidence",3,A,4,B)
        r=recover(p,"evidence",4,B)
        verify(r,"evidence",4,B)

    def test_recover_third_state_fails_closed(self):
        p=prepare(seed_state({"evidence":{"generation":3,"digest":A}}),"evidence",3,A,4,B)
        with self.assertRaises(WitnessError): recover(p,"evidence",4,C)

    def test_unknown_channel_and_type_confusion_rejected(self):
        s=empty_state()
        for channel in ("x",None,1):
            with self.assertRaises(WitnessError): verify(s,channel,0,"0"*64)
        for bad in (True,1.0,"1",-1):
            with self.assertRaises(WitnessError): verify(s,"evidence",bad,"0"*64)

    def test_checksum_and_duplicate_json_tamper_rejected(self):
        s=empty_state(); s["channels"]["evidence"]["generation"]=9
        with self.assertRaises(WitnessError): validate_state(s)
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/"w.json"; p.write_text('{"version":"0.1","version":"0.1"}')
            with self.assertRaises(WitnessError): load_state(p)

    def test_root_state_persistence_is_0600_and_atomic(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/"witness.json"
            state=seed_state({"restart_ledger":{"generation":5,"digest":A}})
            save_state(p,state)
            st=p.stat(); self.assertEqual(st.st_uid,0); self.assertEqual(st.st_mode & 0o777,0o600)
            self.assertEqual(load_state(p),state)
            self.assertFalse((p.with_name(p.name+".tmp")).exists())

    def test_real_socket_peer_uid_authorized_and_root_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); root.chmod(0o755)
            state_path=root/"witness.json"; save_state(state_path,seed_state({"restart_ledger":{"generation":5,"digest":A}}))
            socket_path=root/"sockdir"/"witness.sock"
            proc=multiprocessing.Process(target=_server,args=(str(state_path),str(socket_path))); proc.start()
            try:
                deadline=time.monotonic()+3
                while not socket_path.exists() and time.monotonic()<deadline: time.sleep(0.02)
                self.assertTrue(socket_path.exists())
                with self.assertRaises(WitnessClientError): client_verify(str(socket_path),"restart_ledger",5,A)
                q=multiprocessing.Queue(); child=multiprocessing.Process(target=_nobody_client,args=(str(socket_path),q)); child.start(); child.join(5)
                self.assertEqual(child.exitcode,0); self.assertEqual(q.get(timeout=1),"OK")
            finally:
                proc.terminate(); proc.join(5)


    def test_pinned_controller_rejects_same_uid_same_cgroup_child(self):
        import multiprocessing, pathlib, tempfile, time
        from kk_f.witness_daemon import run_server, _peer_cgroup
        from kk_f.witness_client import verify as client_verify
        current=_peer_cgroup(os.getpid())
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); state=root/'witness.json'; sock=root/'sock'/'witness.sock'
            save_state(state, seed_state({'restart_ledger':{'generation':5,'digest':A}}))
            proc=multiprocessing.Process(target=run_server,args=(str(state),str(sock)),kwargs={'allowed_uid':os.getuid(),'allowed_gid':os.getgid(),'allowed_cgroup':current}); proc.start()
            try:
                deadline=time.monotonic()+3
                while not sock.exists() and time.monotonic()<deadline: time.sleep(.02)
                client_verify(str(sock),'restart_ledger',5,A)
                q=multiprocessing.Queue()
                child=multiprocessing.Process(target=lambda q,s: q.put(_child_verify(s)), args=(q,str(sock))); child.start(); child.join(5)
                self.assertEqual(child.exitcode,0); self.assertTrue(q.get(timeout=1).startswith('REJECT:'))
            finally:
                proc.terminate(); proc.join(5)

if __name__ == "__main__": unittest.main()

class FH03WitnessCgroupTests(unittest.TestCase):
    def test_peer_cgroup_exact_match_and_mismatch(self):
        import multiprocessing, pathlib, tempfile, time
        from kk_f.witness_daemon import run_server, _peer_cgroup
        from kk_f.witness_client import verify as client_verify, WitnessClientError
        current = _peer_cgroup(os.getpid())
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); state=root/'witness.json'; sock=root/'sock'/'witness.sock'
            save_state(state, seed_state({'restart_ledger':{'generation':5,'digest':A}}))
            proc=multiprocessing.Process(target=run_server,args=(str(state),str(sock)),kwargs={'allowed_uid':os.getuid(),'allowed_gid':os.getgid(),'allowed_cgroup':current}); proc.start()
            try:
                deadline=time.monotonic()+3
                while not sock.exists() and time.monotonic()<deadline: time.sleep(.02)
                client_verify(str(sock),'restart_ledger',5,A)
            finally:
                proc.terminate(); proc.join(5)
            badsock=root/'sock2'/'witness.sock'
            proc=multiprocessing.Process(target=run_server,args=(str(state),str(badsock)),kwargs={'allowed_uid':os.getuid(),'allowed_gid':os.getgid(),'allowed_cgroup':'/definitely-not-this-cgroup'}); proc.start()
            try:
                deadline=time.monotonic()+3
                while not badsock.exists() and time.monotonic()<deadline: time.sleep(.02)
                with self.assertRaises(WitnessClientError): client_verify(str(badsock),'restart_ledger',5,A)
            finally:
                proc.terminate(); proc.join(5)
