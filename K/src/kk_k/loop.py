from __future__ import annotations

from typing import Callable

from .audit import append_jsonl
from .governance import GovernanceError, govern, validate_policy

RESULT_KEYS = frozenset({"action_id", "mechanical_verdict"})
STOP_VERDICTS = frozenset({"FAIL", "VETO", "REJECTED"})


class LoopError(ValueError):
    pass


def _validate_result(action_id: str, value: object) -> dict:
    if not isinstance(value, dict) or frozenset(value) != RESULT_KEYS:
        raise LoopError("exact cycle result fields required")
    if value["action_id"] != action_id:
        raise LoopError("cycle result action mismatch")
    if value["mechanical_verdict"] not in {"PASS", "FAIL", "VETO", "REJECTED"}:
        raise LoopError("invalid mechanical verdict")
    return dict(value)


def run_bounded_loop(
    *,
    policy: dict,
    proposer: Callable[[int], object],
    executor: Callable[[str], object],
    log_path: str,
    max_cycles: int,
) -> dict:
    validate_policy(policy)
    if type(max_cycles) is not int or not (1 <= max_cycles <= 32):
        raise LoopError("invalid max_cycles")
    if not callable(proposer) or not callable(executor):
        raise LoopError("proposer/executor unavailable")
    history: list[str] = []
    proposed_calls = 0
    executor_calls = 0
    for index in range(1, max_cycles + 1):
        try:
            requested = proposer(index)
            proposed_calls += 1
        except Exception as exc:
            append_jsonl(
                log_path, {"cycle": index, "status": "PROPOSER_ERROR", "error": type(exc).__name__}
            )
            return {
                "status": "PROPOSER_ERROR",
                "cycles": index,
                "proposer_calls": proposed_calls,
                "executor_calls": executor_calls,
            }
        try:
            decision = govern(requested, policy, history)
        except GovernanceError as exc:
            append_jsonl(
                log_path,
                {"cycle": index, "status": "GOVERNANCE_REJECTED", "error": type(exc).__name__},
            )
            return {
                "status": "GOVERNANCE_REJECTED",
                "cycles": index,
                "proposer_calls": proposed_calls,
                "executor_calls": executor_calls,
            }
        if decision.outcome != "ALLOW":
            append_jsonl(
                log_path,
                {
                    "cycle": index,
                    "status": decision.outcome,
                    "action_id": decision.action_id,
                    "reason": decision.reason,
                },
            )
            return {
                "status": decision.outcome,
                "cycles": index,
                "proposer_calls": proposed_calls,
                "executor_calls": executor_calls,
            }
        action_id = decision.action_id
        try:
            executor_calls += 1
            result = _validate_result(action_id, executor(action_id))
        except Exception as exc:
            append_jsonl(
                log_path,
                {
                    "cycle": index,
                    "status": "EXECUTOR_ERROR",
                    "action_id": action_id,
                    "error": type(exc).__name__,
                },
            )
            return {
                "status": "EXECUTOR_ERROR",
                "cycles": index,
                "proposer_calls": proposed_calls,
                "executor_calls": executor_calls,
            }
        history.append(action_id)
        verdict = result["mechanical_verdict"]
        append_jsonl(log_path, {"cycle": index, "status": verdict, "action_id": action_id})
        if action_id == "A05_NO_ACTION":
            return {
                "status": "NO_ACTION",
                "cycles": index,
                "proposer_calls": proposed_calls,
                "executor_calls": executor_calls,
            }
        if verdict in STOP_VERDICTS:
            return {
                "status": verdict,
                "cycles": index,
                "proposer_calls": proposed_calls,
                "executor_calls": executor_calls,
            }
    return {
        "status": "MAX_CYCLES",
        "cycles": max_cycles,
        "proposer_calls": proposed_calls,
        "executor_calls": executor_calls,
    }
