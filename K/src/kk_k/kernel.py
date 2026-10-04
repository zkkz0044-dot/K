from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .audit import append_jsonl
from .isolation import project_path
from .boundary import submit_action
from .constitution import load_constitution
from .decision import DecisionError, parse_decision
from .verifier import VerificationError, verify_receipt

MAX_INPUT_BYTES = 32768


class KernelError(RuntimeError):
    pass


def _read_bounded(path: str, max_bytes: int = MAX_INPUT_BYTES) -> str:
    data = project_path(path, must_exist=True).read_bytes()
    if len(data) > max_bytes:
        raise KernelError("input file too large")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KernelError("input file must be UTF-8") from exc


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_prompt(constitution: str, goal: str, world_state: str) -> str:
    return (
        "You are K01. Choose exactly one pre-approved action. "
        "Return exactly one JSON object with keys schema and action_id only.\n"
        "Allowed schema: K01.DECISION.1\n"
        "Allowed actions: A01_READ_PROJECT_STATE, A02_READ_F_STATUS, "
        "A03_RUN_F_SMOKE_TEST, A04_WRITE_K_DECISION_LOG, A05_NO_ACTION\n"
        "No params, command, path, env, verifier, retry, or extra fields.\n\n"
        "CONSTITUTION:\n" + constitution + "\n\n"
        "GOAL:\n" + goal + "\n\n"
        "WORLD_STATE:\n" + world_state
    )


def run_once(
    *,
    constitution_path: str,
    goal_path: str,
    world_state_path: str,
    decision_log_path: str,
    execution_log_path: str,
    llm_call: Callable[[str], str],
    f_submit: Callable[[str], object],
) -> dict:
    cycle_id = uuid4().hex
    constitution_obj = load_constitution(constitution_path)
    import json

    constitution = json.dumps(constitution_obj, sort_keys=True, separators=(",", ":"))
    goal = _read_bounded(goal_path, 8192)
    world_state = _read_bounded(world_state_path, 8192)
    prompt = _build_prompt(constitution, goal, world_state)

    raw = llm_call(prompt)
    if not isinstance(raw, str):
        raw = ""
    try:
        decision = parse_decision(raw)
    except DecisionError as exc:
        append_jsonl(
            decision_log_path,
            {
                "cycle_id": cycle_id,
                "status": "REJECTED",
                "llm_output_sha256": _digest(raw),
                "error": type(exc).__name__,
            },
        )
        return {"cycle_id": cycle_id, "status": "DECISION_REJECTED"}

    append_jsonl(
        decision_log_path,
        {
            "cycle_id": cycle_id,
            "status": "SELECTED",
            "action_id": decision.action_id,
            "llm_output_sha256": _digest(raw),
        },
    )
    try:
        receipt = submit_action(decision.action_id, f_submit)
    except Exception as exc:
        append_jsonl(
            execution_log_path,
            {
                "cycle_id": cycle_id,
                "action_id": decision.action_id,
                "status": "GATEWAY_ERROR",
                "error": type(exc).__name__,
            },
        )
        return {"cycle_id": cycle_id, "status": "GATEWAY_ERROR", "action_id": decision.action_id}

    try:
        verified = verify_receipt(decision.action_id, receipt)
    except VerificationError as exc:
        append_jsonl(
            execution_log_path,
            {
                "cycle_id": cycle_id,
                "action_id": decision.action_id,
                "status": "RECEIPT_REJECTED",
                "error": type(exc).__name__,
            },
        )
        return {"cycle_id": cycle_id, "status": "RECEIPT_REJECTED", "action_id": decision.action_id}

    append_jsonl(
        execution_log_path,
        {
            "cycle_id": cycle_id,
            "action_id": decision.action_id,
            "status": verified.result,
        },
    )
    return {"cycle_id": cycle_id, "status": verified.result, "action_id": decision.action_id}
