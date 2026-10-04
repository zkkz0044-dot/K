"""F12 deterministic process-execution outcome to lifecycle status gate."""

from __future__ import annotations

from .contracts import RUNTIME_STATUSES


class ExecutionStatusError(ValueError):
    """Raised when execution outcome input is ambiguous or type-confused."""


def classify_execution(*, exit_code: object, timed_out: object) -> str:
    if type(timed_out) is not bool:
        raise ExecutionStatusError("timed_out must be boolean")
    if exit_code is not None and type(exit_code) is not int:
        raise ExecutionStatusError("exit_code must be integer or null")
    if timed_out and exit_code is None:
        raise ExecutionStatusError("timed-out process must already be reaped")

    if timed_out:
        status = "FAILED"
    elif exit_code is None:
        status = "RUNNING"
    elif exit_code == 0:
        status = "STOPPED"
    else:
        status = "FAILED"

    if status not in RUNTIME_STATUSES:
        raise ExecutionStatusError("internal lifecycle status violation")
    return status
