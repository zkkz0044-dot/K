#!/bin/bash
set -euo pipefail
CTL=/root/K/FK/tools/providerctl.py
python3 "$CTL" disable openai
systemctl stop kk-model-host-relay.service 2>/dev/null || true
echo 'OPENAI_PROVIDER_REMOVED=PASS'
