#!/bin/bash
set -euo pipefail
KEY=/root/K/FK/secrets/openai_api_key
CFG=/root/K/FK/config/openai-model.env
CTL=/root/K/FK/tools/providerctl.py
[ -f "$KEY" ] || { echo 'BLOCKED: API key missing' >&2; exit 2; }
[ "$(stat -c %a "$KEY")" = 600 ] || { echo 'BLOCKED: API key permission is not 600' >&2; exit 3; }
[ -f "$CFG" ] || { echo 'BLOCKED: model config missing' >&2; exit 4; }
. "$CFG"
[[ "${OPENAI_MODEL:-}" == gpt-* ]] || { echo 'BLOCKED: non-GPT model config' >&2; exit 5; }
systemctl start kk-model-host-relay.service
for _ in $(seq 1 20); do
  [ -S /root/K/FK/runtime/model-ipc/host-relay.sock ] && break
  sleep 0.25
done
[ -S /root/K/FK/runtime/model-ipc/host-relay.sock ] || { echo 'BLOCKED: relay socket missing' >&2; exit 6; }
python3 "$CTL" enable openai
echo "OPENAI_PROVIDER_INSERTED=$OPENAI_MODEL"
