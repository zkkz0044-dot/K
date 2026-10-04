#!/bin/bash
set -euo pipefail
ROOT=$(mktemp -d /run/kk-f-fp05.XXXXXX)
cleanup(){ rm -rf "$ROOT"; }
trap cleanup EXIT
mkdir -p "$ROOT/app/src" "$ROOT/work" "$ROOT/state" "$ROOT/evidence" "$ROOT/run"
cp -a /root/K/F/src/kk_f "$ROOT/app/src/"
find "$ROOT/app" -type d -exec chmod 0755 {} +
find "$ROOT/app" -type f -exec chmod 0644 {} +
cat > "$ROOT/worker.py" <<'PY'
#!/usr/bin/python3
import time
time.sleep(0.2)
PY
chmod 0755 "$ROOT/worker.py"
DIGEST=$(sha256sum "$ROOT/worker.py" | awk '{print $1}')
cat > "$ROOT/authority.json" <<EOF
{"version":"0.1","authority_id":"fp05-systemd","executable":"$ROOT/worker.py","sha256":"$DIGEST","max_restart_attempts":3}
EOF
chown root:root "$ROOT/authority.json" "$ROOT/worker.py"
chmod 0644 "$ROOT/authority.json"
chmod 0755 "$ROOT/worker.py"
chown nobody:nogroup "$ROOT/work" "$ROOT/state" "$ROOT/evidence" "$ROOT/run"
chmod 0700 "$ROOT/work" "$ROOT/state" "$ROOT/evidence" "$ROOT/run"
chmod 0755 "$ROOT"
CODE="import os,sys; sys.path.insert(0,'$ROOT/app/src'); from kk_f.frozen_authority import authorize_process; from kk_f.restart_ledger import initialize,read_ledger; from kk_f.evidence import initialize as ei,verify; from kk_f.instance_lock import acquire_instance_lock; spec={'version':'0.1','executable':'$ROOT/worker.py','argv':[],'cwd':'$ROOT/work','env':{},'sha256':'$DIGEST'}; a=authorize_process('$ROOT/authority.json',spec); initialize('$ROOT/state/ledger',3); ei('$ROOT/evidence/store'); lock=acquire_instance_lock('$ROOT/run/f.lock'); print('UID='+str(os.geteuid()), 'AUTH='+a['authority_id'], 'LEDGER='+str(read_ledger('$ROOT/state/ledger')['max_attempts']), 'EVIDENCE='+str(verify('$ROOT/evidence/store')['count']), 'LOCK='+str(lock.released)); lock.release()"
systemd-run --quiet --wait --pipe --collect --uid=nobody --gid=nogroup \
  -p NoNewPrivileges=yes -p PrivateTmp=yes \
  /usr/bin/python3 -c "$CODE"
# Non-root must not be able to modify Frozen Authority.
if runuser -u nobody -- sh -c "echo x >> '$ROOT/authority.json'" 2>/dev/null; then
  echo 'ERROR: non-root modified authority' >&2; exit 1
fi
stat -c 'AUTH_OWNER=%u:%g AUTH_MODE=%a' "$ROOT/authority.json"
stat -c 'STATE_OWNER=%u:%g STATE_MODE=%a' "$ROOT/state"
