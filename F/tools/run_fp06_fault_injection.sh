#!/bin/bash
set -euo pipefail
ROOT=$(mktemp -d /run/kk-f-fp06.XXXXXX)
EXECROOT=$(mktemp -d /var/lib/kk-f-fp06-exec.XXXXXX)
chmod 0755 "$EXECROOT"
UNIT=kk-f-fp06-$$.service
cleanup(){ systemctl stop "$UNIT" >/dev/null 2>&1 || true; rm -f "/run/systemd/system/$UNIT"; systemctl daemon-reload >/dev/null 2>&1 || true; rm -rf "$ROOT" "$EXECROOT"; }
trap cleanup EXIT
mkdir -p "$ROOT/app/src" "$ROOT/work" "$ROOT/state" "$ROOT/evidence" "$ROOT/runtime"
cp -a /root/K/F/src/kk_f "$ROOT/app/src/"
find "$ROOT/app" -type d -exec chmod 0755 {} +
find "$ROOT/app" -type f -exec chmod 0644 {} +
cat > "$EXECROOT/worker.py" <<'PY'
#!/usr/bin/python3
import datetime,json,os,pathlib,time
hb=pathlib.Path(os.environ['HEARTBEAT']); ctl=pathlib.Path(os.environ['CONTROL']); log=pathlib.Path(os.environ['PIDLOG'])
with log.open('a') as f: f.write(str(os.getpid())+'\n'); f.flush(); os.fsync(f.fileno())
seq=0
while True:
    if ctl.exists():
        try: ctl.unlink()
        except FileNotFoundError: pass
        raise SystemExit(17)
    seq+=1
    now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
    tmp=hb.with_suffix('.tmp'); tmp.write_text(json.dumps({'version':'0.1','sequence':seq,'observed_at':now},separators=(',',':'))); tmp.replace(hb)
    time.sleep(0.03)
PY
chmod 0755 "$EXECROOT/worker.py"
DIGEST=$(sha256sum "$EXECROOT/worker.py" | awk '{print $1}')
cat > "$ROOT/authority.json" <<EOF
{"version":"0.2","authority_id":"fp06-prod","process_spec":{"version":"0.1","executable":"$EXECROOT/worker.py","argv":[],"cwd":"$ROOT/work","env":{"HEARTBEAT":"$ROOT/runtime/heartbeat.json","CONTROL":"$ROOT/runtime/crash","PIDLOG":"$ROOT/runtime/pids.log"},"sha256":"$DIGEST"},"max_restart_attempts":2}
EOF
cat > "$ROOT/runtime.json" <<EOF
{"version":"0.1","authority_path":"$ROOT/authority.json","ledger_directory":"$ROOT/state/ledger","evidence_directory":"$ROOT/evidence/store","heartbeat_path":"$ROOT/runtime/heartbeat.json","process_spec":{"version":"0.1","executable":"$EXECROOT/worker.py","argv":[],"cwd":"$ROOT/work","env":{"HEARTBEAT":"$ROOT/runtime/heartbeat.json","CONTROL":"$ROOT/runtime/crash","PIDLOG":"$ROOT/runtime/pids.log"},"sha256":"$DIGEST"},"healthy_within_seconds":1,"degraded_within_seconds":2,"grace_seconds":0.1,"base_delay_seconds":10.0,"max_delay_seconds":12.0,"poll_interval_seconds":0.05,"heartbeat_startup_grace_seconds":3.0}
EOF
chown root:root "$ROOT/authority.json" "$ROOT/runtime.json" "$EXECROOT/worker.py"
chmod 0644 "$ROOT/authority.json" "$ROOT/runtime.json"; chmod 0755 "$EXECROOT/worker.py"; chmod 0755 "$ROOT"
chown nobody:nogroup "$ROOT/work" "$ROOT/state" "$ROOT/evidence" "$ROOT/runtime"
chmod 0700 "$ROOT/work" "$ROOT/state" "$ROOT/evidence" "$ROOT/runtime"
cat > "/run/systemd/system/$UNIT" <<EOF
[Unit]
Description=KK F FP06 transient production acceptance
After=local-fs.target
[Service]
Type=simple
User=nobody
Group=nogroup
WorkingDirectory=$ROOT/work
Environment=PYTHONPATH=$ROOT/app/src
ExecStart=/usr/bin/python3 -m kk_f.production_daemon --config $ROOT/runtime.json
Restart=on-failure
RestartSec=0.2s
KillMode=control-group
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
ReadOnlyPaths=$ROOT/app $ROOT/authority.json $ROOT/runtime.json $EXECROOT/worker.py
ReadWritePaths=$ROOT/work $ROOT/state $ROOT/evidence $ROOT/runtime
UMask=0077
EOF
systemctl daemon-reload
systemctl start "$UNIT"
for i in $(seq 1 100); do [ -s "$ROOT/runtime/pids.log" ] && break; sleep 0.05; done
[ -s "$ROOT/runtime/pids.log" ] || { echo 'FAIL cold start no worker'; exit 1; }
echo "COLD_START_PID=$(head -1 "$ROOT/runtime/pids.log")"
systemctl is-active --quiet "$UNIT"; echo SYSTEMD_NONROOT_ACTIVE=1
# Duplicate supervisor must fail on the explicit lock.
set +e
systemd-run --quiet --wait --pipe --collect --uid=nobody --gid=nogroup --setenv=PYTHONPATH="$ROOT/app/src" /usr/bin/python3 -m kk_f.production_daemon --config "$ROOT/runtime.json" --stop-after-cycles 1 >/dev/null 2>&1
DUP=$?
set -e
[ "$DUP" -ne 0 ] || { echo 'FAIL duplicate supervisor unexpectedly succeeded'; exit 1; }
echo DUPLICATE_LOCK_DENIED=1
# Crash 1: immediate first approved replacement.
touch "$ROOT/runtime/crash"
for i in $(seq 1 100); do [ "$(wc -l < "$ROOT/runtime/pids.log")" -ge 2 ] && break; sleep 0.05; done
[ "$(wc -l < "$ROOT/runtime/pids.log")" -eq 2 ] || { echo 'FAIL first replacement'; exit 1; }
echo "REPLACEMENT1_PID=$(sed -n '2p' "$ROOT/runtime/pids.log")"
# Crash 2: backoff must prevent immediate third worker.
touch "$ROOT/runtime/crash"
sleep 0.15
C=$(wc -l < "$ROOT/runtime/pids.log")
[ "$C" -eq 2 ] || { echo "FAIL backoff premature replacement count=$C"; exit 1; }
echo BACKOFF_BLOCKED_EARLY_RETRY=1
for i in $(seq 1 300); do [ "$(wc -l < "$ROOT/runtime/pids.log")" -ge 3 ] && break; sleep 0.05; done
[ "$(wc -l < "$ROOT/runtime/pids.log")" -eq 3 ] || { echo 'FAIL second replacement after deadline'; exit 1; }
echo "REPLACEMENT2_PID=$(sed -n '3p' "$ROOT/runtime/pids.log")"
# Crash 3: budget exhausted, no fourth worker and stable HOLD_FAILED.
touch "$ROOT/runtime/crash"
sleep 1.1
C=$(wc -l < "$ROOT/runtime/pids.log")
[ "$C" -eq 3 ] || { echo "FAIL budget allowed extra worker count=$C"; exit 1; }
PYTHONPATH="$ROOT/app/src" python3 - <<PY
from kk_f.restart_ledger import read_ledger
from kk_f.evidence import verify
l=read_ledger('$ROOT/state/ledger'); e=verify('$ROOT/evidence/store')
print('LEDGER_ATTEMPTS='+str(l['attempts']), 'LAST_DECISION='+l['last_decision'], 'GEN='+str(l['generation']), 'EVIDENCE='+str(e['count']))
assert l['attempts']==2 and l['last_decision']=='HOLD_FAILED'
PY
GEN1=$(PYTHONPATH="$ROOT/app/src" python3 -c "from kk_f.restart_ledger import read_ledger; print(read_ledger('$ROOT/state/ledger')['generation'])")
# Supervisor restart must preserve exhausted budget and not mutate repeatedly.
systemctl restart "$UNIT"; sleep 0.6
[ "$(wc -l < "$ROOT/runtime/pids.log")" -eq 3 ] || { echo 'FAIL restart reset budget'; exit 1; }
GEN2=$(PYTHONPATH="$ROOT/app/src" python3 -c "from kk_f.restart_ledger import read_ledger; print(read_ledger('$ROOT/state/ledger')['generation'])")
[ "$GEN1" = "$GEN2" ] || { echo "FAIL HOLD_FAILED churn gen $GEN1->$GEN2"; exit 1; }
echo SUPERVISOR_RESTART_PRESERVED_BUDGET=1
systemctl stop "$UNIT"
# Network namespace: fresh independent root, no network available.
NET="$ROOT/net"; mkdir -p "$NET/work" "$NET/runtime"; ND=$(sha256sum "$EXECROOT/worker.py"|awk '{print $1}')
cat > "$NET/authority.json" <<EOF
{"version":"0.2","authority_id":"fp06-net","process_spec":{"version":"0.1","executable":"$EXECROOT/worker.py","argv":[],"cwd":"$NET/work","env":{"HEARTBEAT":"$NET/runtime/heartbeat.json","CONTROL":"$NET/runtime/crash","PIDLOG":"$NET/runtime/pids.log"},"sha256":"$ND"},"max_restart_attempts":2}
EOF
cat > "$NET/runtime.json" <<EOF
{"version":"0.1","authority_path":"$NET/authority.json","ledger_directory":"$NET/ledger","evidence_directory":"$NET/evidence","heartbeat_path":"$NET/runtime/heartbeat.json","process_spec":{"version":"0.1","executable":"$EXECROOT/worker.py","argv":[],"cwd":"$NET/work","env":{"HEARTBEAT":"$NET/runtime/heartbeat.json","CONTROL":"$NET/runtime/crash","PIDLOG":"$NET/runtime/pids.log"},"sha256":"$ND"},"healthy_within_seconds":1,"degraded_within_seconds":2,"grace_seconds":0.1,"base_delay_seconds":0.5,"max_delay_seconds":1.0,"poll_interval_seconds":0.05,"heartbeat_startup_grace_seconds":3.0}
EOF
chown root:root "$NET/authority.json" "$NET/runtime.json"; chmod 0644 "$NET/authority.json" "$NET/runtime.json"
PYTHONPATH="$ROOT/app/src" unshare -n /usr/bin/python3 -m kk_f.production_daemon --config "$NET/runtime.json" --stop-after-cycles 80
PYTHONPATH="$ROOT/app/src" python3 - <<PY
from kk_f.evidence import verify
v=verify('$NET/evidence'); print('NETNS_EVIDENCE='+str(v['count'])); assert v['count']>=1
PY
echo NETWORK_NAMESPACE_PASS=1
