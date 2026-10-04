#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "test_clean_install.sh requires root (for a private mount namespace)." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$(mktemp -d /tmp/kk-public-test.XXXXXX)"
CREATED_MOUNT_ROOT=0

cleanup() {
  rm -rf "$STAGE"
  if [[ "$CREATED_MOUNT_ROOT" -eq 1 ]]; then
    rmdir /root/K 2>/dev/null || true
  fi
}
trap cleanup EXIT

python3 "$ROOT/scripts/check_public_tree.py"

cp -a "$ROOT/K" "$STAGE/K"
cp -a "$ROOT/F" "$STAGE/F"
cp -a "$ROOT/FK" "$STAGE/FK"
cp -a "$ROOT/PANEL-v0.1" "$STAGE/PANEL-v0.1"
cp -a "$ROOT/scripts" "$STAGE/scripts"

mkdir -p "$STAGE/F/evidence/fk" "$STAGE/FK/.test_tmp"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import json
import sys

stage = Path(sys.argv[1])
tools = ["files.read", "browser.search", "remote.vps.health"]
actions = [
    "A01_READ_PROJECT_STATE",
    "A02_READ_F_STATUS",
    "A03_RUN_F_SMOKE_TEST",
    "A04_WRITE_K_DECISION_LOG",
    "A05_NO_ACTION",
]
k_state = {
    "k_f_boundary": "K_FINAL_DECISION_F_EXECUTION_GUARD",
    "external_tools_enabled": tools,
    "k_cognition_external_tools": {"enabled": tools},
    "external_tool_scope": "ACCEPTED_EXACT_THREE_READONLY",
    "fk_enabled_actions": actions,
    "initial_action_count": 5,
    "dynamic_process_spec_enabled": False,
    "free_form_params_enabled": False,
    "world_observation_cycle": {
        "authority": "EVIDENCE_ONLY",
        "mode": "OBSERVE_ONLY",
        "promotion_policy": "NO_AUTO_TRUTH_NO_EXECUTION_AUTHORITY",
    },
    "human_interface": "PASS_COGNITIVE_ONLY_NO_EXECUTION",
}
f_state = {
    "status": "ACCEPTED",
    "current_phase": "ADVERSARIAL_HARDENING_ACCEPTED",
    "final_acceptance": "ACCEPTED",
}
(stage / "K/PROJECT_STATE.json").write_text(
    json.dumps(k_state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
(stage / "F/PROJECT_STATE.json").write_text(
    json.dumps(f_state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
(stage / "F/evidence/fk/decision_markers.jsonl").write_text("", encoding="utf-8")
PY

chown -R root:root "$STAGE"
chmod -R go-w "$STAGE"
chmod 600   "$STAGE/K/PROJECT_STATE.json"   "$STAGE/F/PROJECT_STATE.json"   "$STAGE/F/evidence/fk/decision_markers.jsonl"
chmod 700 "$STAGE/FK/.test_tmp"

if [[ ! -d /root/K ]]; then
  mkdir /root/K
  CREATED_MOUNT_ROOT=1
fi

export STAGE
unshare -m --propagation private bash <<'NS'
set -euo pipefail
mount --bind "$STAGE" /root/K

export PYTHONDONTWRITEBYTECODE=1
PYTEST_ARGS=(-q -p no:cacheprovider)

echo "[clean 1/4] K"
(
  cd "$STAGE/K"
  PYTHONPATH=src pytest "${PYTEST_ARGS[@]}"
)

echo "[clean 2/4] F"
(
  cd "$STAGE/F"
  PYTHONPATH="src:$STAGE/K/src" pytest "${PYTEST_ARGS[@]}"
)

echo "[clean 3/4] FK"
(
  cd "$STAGE/FK"
  PYTHONPATH="$STAGE/F/src:$STAGE/K/src:." pytest "${PYTEST_ARGS[@]}"
)

echo "[clean 4/4] Public interfaces"
PYTHONPATH="$STAGE/K/src:$STAGE/F/src:$STAGE/FK" pytest "${PYTEST_ARGS[@]}" "$STAGE/scripts/tests"
echo "CLEAN_INSTALL_TESTS_PASS"
NS
