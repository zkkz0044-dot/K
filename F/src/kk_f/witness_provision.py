"""FH03 root-only provisioning of monotonic witness anchors from durable local F state."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .checkpoint import checkpoint_checksum
from .evidence import GENESIS_HASH, verify as verify_evidence
from .frozen_authority import load_frozen_authority
from .monotonic_witness import WitnessError, save_state, seed_state
from .production_daemon import load_runtime_config
from .restart_ledger import read_ledger


class WitnessProvisionError(RuntimeError):
    pass


def _ledger_binding(directory: str, max_attempts: int) -> dict:
    path = Path(directory) / "checkpoint.json"
    if path.exists():
        ledger = read_ledger(directory)
        payload = {
            "ledger_version": "0.2",
            "attempts": ledger["attempts"],
            "max_attempts": ledger["max_attempts"],
            "last_decision": ledger["last_decision"],
            "last_attempt_at": ledger["last_attempt_at"],
        }
        digest = checkpoint_checksum(ledger["generation"], ledger["status"], payload)
        return {"generation": ledger["generation"], "digest": digest}
    payload = {
        "ledger_version": "0.2",
        "attempts": 0,
        "max_attempts": max_attempts,
        "last_decision": "NO_ACTION",
        "last_attempt_at": None,
    }
    return {"generation": 0, "digest": checkpoint_checksum(0, "READY", payload)}


def _evidence_binding(directory: str) -> dict:
    root = Path(directory)
    if (root / "evidence.jsonl").exists() or (root / "HEAD.json").exists():
        state = verify_evidence(directory)
        return {"generation": state["count"], "digest": state["last_hash"]}
    return {"generation": 0, "digest": GENESIS_HASH}


def provision(authority_path: str, runtime_path: str, state_path: str) -> dict:
    if os.geteuid() != 0:
        raise WitnessProvisionError("witness provisioning requires root")
    target = Path(state_path)
    if target.exists() or target.is_symlink():
        raise WitnessProvisionError("existing witness state must never be overwritten")
    authority = load_frozen_authority(authority_path)
    cfg = load_runtime_config(runtime_path)
    if cfg.authority_path != authority_path:
        raise WitnessProvisionError("runtime authority path mismatch")
    bindings = {
        "restart_ledger": _ledger_binding(cfg.ledger_directory, authority["max_restart_attempts"]),
        "evidence": _evidence_binding(cfg.evidence_directory),
    }
    try:
        state = seed_state(bindings)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chown(target.parent, 0, 0)
        os.chmod(target.parent, 0o700)
        save_state(target, state)
    except (OSError, WitnessError, ValueError) as exc:
        raise WitnessProvisionError("witness provisioning failed") from exc
    return state


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--authority", required=True)
    p.add_argument("--runtime", required=True)
    p.add_argument("--state", required=True)
    a = p.parse_args(argv)
    provision(a.authority, a.runtime, a.state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
