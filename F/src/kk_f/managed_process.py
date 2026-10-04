"""F13 managed long-running local process primitive."""

from __future__ import annotations

import subprocess

from .execution_status import classify_execution
from .launch_guard import LaunchGuardError, open_verified_launch


class ManagedProcessError(RuntimeError):
    """Raised when managed-process lifecycle operations fail closed."""


def _positive_seconds(value: object, where: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or value <= 0:
        raise ManagedProcessError(f"{where} must be a positive number")
    return float(value)


class ManagedProcess:
    def __init__(self, process: subprocess.Popen, verified_sha256: str):
        self._process = process
        self.verified_sha256 = verified_sha256

    @property
    def pid(self) -> int:
        return self._process.pid

    def observe(self) -> dict:
        exit_code = self._process.poll()
        status = classify_execution(exit_code=exit_code, timed_out=False)
        return {"pid": self.pid, "exit_code": exit_code, "status": status}

    def stop(self, *, grace_seconds: object) -> dict:
        grace = _positive_seconds(grace_seconds, "grace_seconds")
        if self._process.poll() is not None:
            return {
                "pid": self.pid,
                "exit_code": self._process.returncode,
                "forced": False,
                "status": "STOPPED",
            }
        self._process.terminate()
        forced = False
        try:
            self._process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            forced = True
        return {
            "pid": self.pid,
            "exit_code": self._process.returncode,
            "forced": forced,
            "status": "STOPPED",
        }


def launch_managed(spec: object) -> ManagedProcess:
    try:
        verified = open_verified_launch(spec)
    except LaunchGuardError as exc:
        raise ManagedProcessError("process preflight failed") from exc
    try:
        process = subprocess.Popen(
            [verified.spec["executable"], *verified.spec["argv"]],
            executable=verified.executable_ref,
            cwd=verified.cwd_ref,
            env=dict(verified.spec["env"]),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
            pass_fds=verified.pass_fds,
        )
    except (OSError, ValueError) as exc:
        raise ManagedProcessError("managed process launch failed") from exc
    finally:
        verified.close()
    return ManagedProcess(process, verified.sha256)
