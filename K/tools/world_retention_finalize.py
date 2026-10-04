#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import argparse, json, os, pathlib

ROOT = pathlib.Path('/root/K/K/world')
PENDING = ROOT / 'retention_pending'
LIFECYCLE = ROOT / 'lifecycle'
STATE = ROOT / 'retention_state'

class FinalizeError(ValueError):
    pass

def load(path, max_bytes=262144):
    p = pathlib.Path(path)
    raw = p.read_bytes()
    if not raw or len(raw) > max_bytes:
        raise FinalizeError(f'invalid size: {p}')
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise FinalizeError('object required')
    return obj

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    tmp = path.parent / f'.{path.name}.tmp'
    tmp.write_bytes(raw)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)

def allowed(path, roots):
    p = pathlib.Path(path).resolve()
    for r in roots:
        try:
            p.relative_to((ROOT / r).resolve())
            return p
        except ValueError:
            continue
    raise FinalizeError(f'deletion path not allowed: {p}')

def unlink_if_file(path, deleted, dry):
    p = pathlib.Path(path)
    if p.exists():
        if not p.is_file():
            raise FinalizeError(f'not a file: {p}')
        if not dry:
            p.unlink()
        deleted.append(str(p))

def lifecycle_for(source):
    return LIFECYCLE / (pathlib.Path(source).name + '.json')

def prune_expired_digests(dry):
    now = datetime.now(timezone.utc)
    removed = []
    ddir = ROOT / 'digests'
    if not ddir.exists():
        return removed
    for p in ddir.glob('*.json'):
        try:
            d = load(p, 32768)
            if d.get('schema') != 'K.WORLD.DIGEST.1':
                continue
            exp = datetime.fromisoformat(d['expires_at'])
            if exp.tzinfo is None:
                continue
            if exp <= now:
                if not dry:
                    p.unlink()
                removed.append(str(p))
        except Exception:
            continue
    return removed

def duplicate_mode(source, delivery, receipt, dry):
    rec = load(receipt, 262144)
    if rec.get('schema') != 'K.WORLD.EXACT.DEDUP.RECEIPT.1':
        raise FinalizeError('invalid dedup receipt')
    if rec.get('delivered_items') != 0 or rec.get('source_items') != rec.get('exact_duplicates'):
        raise FinalizeError('duplicate cleanup requires 100% exact duplicates')
    deleted = []
    life = lifecycle_for(source)
    if life.exists():
        m = load(life, 32768)
        if m.get('schema') != 'K.WORLD.LIFECYCLE.1' or m.get('evidence_path') != str(pathlib.Path(source)):
            raise FinalizeError('lifecycle mismatch')
        unlink_if_file(allowed(m['observation_path'], ['observations']), deleted, dry)
    unlink_if_file(allowed(source,['evidence','followup_evidence']), deleted, dry)
    unlink_if_file(allowed(delivery,['sensory_inbox']), deleted, dry)
    unlink_if_file(allowed(receipt,['sensory_receipts']), deleted, dry)
    if life.exists():
        unlink_if_file(allowed(life,['lifecycle']), deleted, dry)
    return 'DUPLICATE_DISCARDED', deleted

def cognized_mode(source, delivery, receipt, dry):
    pend = PENDING / (pathlib.Path(source).name + '.json')
    if not pend.exists():
        raise FinalizeError('retention pending record missing')
    p = load(pend, 65536)
    if p.get('schema') != 'K.WORLD.RETENTION.PENDING.1' or p.get('source_evidence_path') != str(pathlib.Path(source).resolve()):
        raise FinalizeError('pending mismatch')
    for dp in p.get('durable_paths', []):
        if not pathlib.Path(dp).is_file():
            raise FinalizeError(f'durable output missing: {dp}')
    deleted = []
    life = lifecycle_for(source)
    if life.exists():
        m = load(life, 32768)
        if m.get('schema') != 'K.WORLD.LIFECYCLE.1' or m.get('evidence_path') != str(pathlib.Path(source)):
            raise FinalizeError('lifecycle mismatch')
        unlink_if_file(allowed(m['observation_path'],['observations']), deleted, dry)
    unlink_if_file(allowed(source,['evidence','followup_evidence']), deleted, dry)
    unlink_if_file(allowed(delivery,['sensory_inbox']), deleted, dry)
    unlink_if_file(allowed(receipt,['sensory_receipts']), deleted, dry)
    for ep in p.get('ephemeral_paths', []):
        unlink_if_file(allowed(ep,['followups','followup_evidence','round_context']), deleted, dry)
    if life.exists():
        unlink_if_file(allowed(life,['lifecycle']), deleted, dry)
    if pend.exists():
        unlink_if_file(allowed(pend,['retention_pending']), deleted, dry)
    return p.get('retention_class','UNKNOWN'), deleted

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['duplicate','cognized'])
    ap.add_argument('source')
    ap.add_argument('delivery')
    ap.add_argument('receipt')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if a.mode == 'duplicate':
        result, deleted = duplicate_mode(a.source,a.delivery,a.receipt,a.dry_run)
    else:
        result, deleted = cognized_mode(a.source,a.delivery,a.receipt,a.dry_run)
    expired = prune_expired_digests(a.dry_run)
    out = {
        'schema':'K.WORLD.RETENTION.FINALIZE.1','at':datetime.now(timezone.utc).isoformat(),
        'status':'PASS','mode':a.mode,'result':result,'dry_run':a.dry_run,
        'deleted_paths':deleted,'expired_digests':expired
    }
    if not a.dry_run:
        atomic_json(STATE/'latest.json', out)
    print(json.dumps(out,ensure_ascii=False,sort_keys=True))

if __name__ == '__main__':
    main()
