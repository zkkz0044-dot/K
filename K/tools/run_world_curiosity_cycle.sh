#!/bin/bash
set -euo pipefail
RUN=/run/kk-world-curiosity
PICK=$RUN/pick.json
BATCH=$RUN/batch.json
COGNITION=$RUN/cognition.json
mkdir -p "$RUN"
rm -f "$RUN"/*.json

/usr/bin/python3 /root/K/K/tools/world_curiosity.py pick > "$PICK"
STATUS=$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$PICK")
if [ "$STATUS" = NOOP ]; then
  REASON=$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["reason"])' "$PICK")
  /usr/bin/python3 -c 'import json,sys; print(json.dumps({"schema":"K.WORLD.CURIOSITY.CYCLE.1","status":"NOOP","reason":sys.argv[1]},sort_keys=True,separators=(",",":")))' "$REASON"
  exit 0
fi
[ "$STATUS" = READY ] || { echo 'invalid curiosity pick status' >&2; exit 65; }
QID=$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["question_id"])' "$PICK")
/usr/bin/python3 /root/K/K/tools/world_curiosity.py mark "$PICK" >/dev/null
PYTHONPATH=/root/K/K/src /usr/bin/python3 /root/K/K/tools/world_curiosity.py search "$PICK" > "$BATCH"
FREC=$(/usr/bin/python3 /root/K/K/tools/world_followup_ingest.py "$BATCH")
RAWFILE=$(printf '%s' "$FREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["file"])')
EVID=$(printf '%s' "$FREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence_file"])')
BASE=$(basename "$EVID")
DELIVERY=/root/K/K/world/sensory_inbox/curiosity-$BASE
RECEIPT=/root/K/K/world/sensory_receipts/curiosity-$BASE
DREC=$(/usr/bin/python3 /root/K/FK/tools/world_exact_dedup.py prepare "$EVID" "$DELIVERY" "$RECEIPT")
DELIVERED=$(printf '%s' "$DREC" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["delivered_items"])')
if [ "$DELIVERED" -eq 0 ]; then
  /usr/bin/python3 /root/K/K/tools/world_retention_finalize.py duplicate "$EVID" "$DELIVERY" "$RECEIPT" >/dev/null
  case "$RAWFILE" in /root/K/K/world/followups/*.json) rm -f -- "$RAWFILE" ;; *) echo 'invalid curiosity raw path' >&2; exit 66;; esac
  /usr/bin/python3 /root/K/K/tools/world_current_model.py >/dev/null
  /usr/bin/python3 -c 'import json,sys; print(json.dumps({"schema":"K.WORLD.CURIOSITY.CYCLE.1","status":"PASS","result":"DUPLICATE_OR_EMPTY","question_id":sys.argv[1],"delivered":0},sort_keys=True,separators=(",",":")))' "$QID"
  exit 0
fi
KK_WORLD_MAX_FOLLOWUP_DEPTH=0 /root/K/K/tools/run_world_cognition_cycle.sh "$DELIVERY" "$EVID" "$RAWFILE" > "$COGNITION"
/usr/bin/python3 /root/K/FK/tools/world_exact_dedup.py commit "$DELIVERY" >/dev/null
FIN=$(/usr/bin/python3 /root/K/K/tools/world_retention_finalize.py cognized "$EVID" "$DELIVERY" "$RECEIPT")
CLASS=$(printf '%s' "$FIN" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["result"])')
/usr/bin/python3 /root/K/K/tools/world_current_model.py >/dev/null
/usr/bin/python3 -c 'import json,sys; print(json.dumps({"schema":"K.WORLD.CURIOSITY.CYCLE.1","status":"PASS","result":sys.argv[3],"question_id":sys.argv[1],"delivered":int(sys.argv[2])},sort_keys=True,separators=(",",":")))' "$QID" "$DELIVERED" "$CLASS"
