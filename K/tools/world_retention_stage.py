#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, os, pathlib, subprocess

ROOT = pathlib.Path('/root/K/K/world')
DIGESTS = ROOT / 'digests'
RETAINED = ROOT / 'retained_evidence'
PENDING = ROOT / 'retention_pending'
CONFIG = pathlib.Path('/root/K/K/config/world_retention.json')
POLICY = {'observed_is_believed': False, 'search_result_is_long_term_memory': False}

class RetentionError(ValueError):
    pass

def load_json(path, max_bytes=262144):
    p = pathlib.Path(path)
    raw = p.read_bytes()
    if not raw or len(raw) > max_bytes:
        raise RetentionError(f'invalid size: {p}')
    try:
        obj = json.loads(raw)
    except Exception as exc:
        raise RetentionError(f'invalid JSON: {p}') from exc
    if not isinstance(obj, dict):
        raise RetentionError(f'object required: {p}')
    return obj, raw, hashlib.sha256(raw).hexdigest()

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    tmp = path.parent / f'.{path.name}.tmp'
    tmp.write_bytes(raw)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return hashlib.sha256(raw).hexdigest()

def validate_evidence(path):
    d, raw, sha = load_json(path)
    if set(d) != {'schema','observed_at','authority','policy','items'}:
        raise RetentionError('invalid evidence envelope')
    if d.get('schema') != 'K.WORLD.EVIDENCE.SET.1' or d.get('authority') != 'EVIDENCE_ONLY' or d.get('policy') != POLICY:
        raise RetentionError('invalid evidence policy')
    for x in d.get('items', []):
        if not isinstance(x, dict) or x.get('status') != 'OBSERVED_UNVERIFIED' or x.get('memory_eligible') is not False:
            raise RetentionError('evidence trust escalation')
    return d, sha

def validate_think(path):
    d, raw, sha = load_json(path, 65536)
    need = {'schema','thought_at','source_evidence_sha256','authority','memory_eligible','thought'}
    if set(d) != need or d.get('schema') != 'K.WORLD.THINK.RUN.1':
        raise RetentionError('invalid think run')
    if d.get('authority') != 'COGNITIVE_NOTE_ONLY' or d.get('memory_eligible') is not False:
        raise RetentionError('invalid think policy')
    t = d.get('thought')
    if not isinstance(t, dict) or set(t) != {'schema','assessment','notable_evidence_ids','follow_up_queries'} or t.get('schema') != 'K.WORLD.THINK.1':
        raise RetentionError('invalid thought')
    if not isinstance(t['notable_evidence_ids'], list):
        raise RetentionError('invalid notable ids')
    return d, sha

def load_config():
    d, _, _ = load_json(CONFIG, 32768)
    if d.get('schema') != 'K.WORLD.RETENTION.CONFIG.1':
        raise RetentionError('invalid retention config')
    days = int(d.get('digest_ttl_days', 14))
    if days < 1 or days > 365:
        raise RetentionError('invalid digest ttl')
    return d

def within_world(path):
    p = pathlib.Path(path).resolve()
    root = ROOT.resolve()
    try:
        p.relative_to(root)
    except ValueError as exc:
        raise RetentionError(f'path outside world: {p}') from exc
    return str(p)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base_evidence')
    ap.add_argument('initial_think')
    ap.add_argument('final_evidence')
    ap.add_argument('final_think')
    ap.add_argument('--ephemeral', action='append', default=[])
    ap.add_argument('--source-path')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    cfg = load_config()
    base, bsha = validate_evidence(a.base_evidence)
    initial, _ = validate_think(a.initial_think)
    final, fsha = validate_evidence(a.final_evidence)
    last, lsha = validate_think(a.final_think)
    if initial['source_evidence_sha256'] != bsha:
        raise RetentionError('initial source mismatch')
    if last['source_evidence_sha256'] != fsha:
        raise RetentionError('final source mismatch')

    by_id = {x.get('evidence_id'): x for x in final['items']}
    notable = list(dict.fromkeys(initial['thought']['notable_evidence_ids'] + last['thought']['notable_evidence_ids']))
    if any(x not in by_id for x in notable):
        raise RetentionError('notable id missing from final evidence')

    now = datetime.now(timezone.utc)
    stamp = now.strftime('%Y%m%dT%H%M%SZ')
    did = hashlib.sha256((bsha + lsha).encode()).hexdigest()[:12]
    durable = []
    mode = 'TEMPORARY_DIGEST'

    if notable:
        mode = 'LONG_TERM_NOTABLE'
        retained_obj = {
            'schema': 'K.WORLD.RETAINED.EVIDENCE.1',
            'retained_at': now.isoformat(),
            'observed_at': final['observed_at'],
            'authority': 'EVIDENCE_ONLY',
            'retention_reason': 'K_NOTABLE_EVIDENCE_SELECTION',
            'source_evidence_sha256': fsha,
            'notable_evidence_ids': notable,
            'items': [by_id[x] for x in notable],
        }
        retained_path = RETAINED / f'{stamp}-{did}.json'
        durable.append(str(retained_path))
        if not a.dry_run:
            atomic_json(retained_path, retained_obj)
            proc = subprocess.run(
                ['/usr/bin/python3','/root/K/K/tools/world_experience_ingest.py',
                 a.base_evidence,a.initial_think,a.final_evidence,a.final_think],
                check=True, capture_output=True, text=True
            )
            rec = json.loads(proc.stdout)
            durable.append(rec['file'])
            evproc = subprocess.run(
                ['/usr/bin/python3','/root/K/K/tools/world_event_update.py',str(retained_path)],
                check=True, capture_output=True, text=True
            )
            evrec = json.loads(evproc.stdout)
            durable.extend(evrec.get('updates', []))
            durable.extend(evrec.get('graph_updates', []))
    else:
        expires = now + timedelta(days=int(cfg['digest_ttl_days']))
        digest_obj = {
            'schema': 'K.WORLD.DIGEST.1',
            'observed_at': base['observed_at'],
            'digested_at': now.isoformat(),
            'expires_at': expires.isoformat(),
            'authority': 'COGNITIVE_NOTE_ONLY',
            'memory_eligible': False,
            'retention_class': 'TEMPORARY',
            'source_evidence_sha256': fsha,
            'assessment': str(last['thought']['assessment'])[:6000],
            'notable_evidence_ids': [],
        }
        digest_path = DIGESTS / f'{stamp}-{did}.json'
        durable.append(str(digest_path))
        if not a.dry_run:
            atomic_json(digest_path, digest_obj)

    base_path = within_world(a.base_evidence)
    source_path = within_world(a.source_path) if a.source_path else base_path
    final_path = within_world(a.final_evidence)
    ephemerals = []
    for p in a.ephemeral:
        rp = within_world(p)
        if rp not in ephemerals:
            ephemerals.append(rp)
    if final_path != base_path and final_path not in ephemerals:
        ephemerals.append(final_path)

    pending_obj = {
        'schema': 'K.WORLD.RETENTION.PENDING.1',
        'created_at': now.isoformat(),
        'source_evidence_path': source_path,
        'source_evidence_sha256': bsha,
        'retention_class': mode,
        'durable_paths': durable,
        'ephemeral_paths': ephemerals,
        'final_think_sha256': lsha,
    }
    pending_path = PENDING / (pathlib.Path(source_path).name + '.json')
    if not a.dry_run:
        atomic_json(pending_path, pending_obj)
    print(json.dumps({
        'status':'PASS','dry_run':a.dry_run,'retention_class':mode,
        'notable_count':len(notable),'durable_paths':durable,
        'pending':str(pending_path),'ephemeral_count':len(ephemerals)
    }, ensure_ascii=False, sort_keys=True))

if __name__ == '__main__':
    main()
