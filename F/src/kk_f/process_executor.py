"""F11 direct non-shell local process executor."""

from __future__ import annotations

import subprocess

from .launch_guard import LaunchGuardError, open_verified_launch


class ProcessExecutionError(RuntimeError):
    """Raised when a verified local candidate cannot be executed safely."""


def _strict_timeout(value: object) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or value <= 0:
        raise ProcessExecutionError("timeout_seconds must be a positive number")
    return float(value)


def execute_and_wait(spec: object, *, timeout_seconds: object) -> dict:
    timeout = _strict_timeout(timeout_seconds)
    try:
        verified = open_verified_launch(spec)
    except LaunchGuardError as exc:
        raise ProcessExecutionError("process preflight failed") from exc

    argv = [verified.spec["executable"], *verified.spec["argv"]]
    env = dict(verified.spec["env"])
    try:
        process = subprocess.Popen(
            argv,
            executable=verified.executable_ref,
            cwd=verified.cwd_ref,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            pass_fds=verified.pass_fds,
            text=False,
        )
    except (OSError, ValueError) as exc:
        raise ProcessExecutionError("process launch failed") from exc
    finally:
        verified.close()

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        timed_out = True

    return {
        "verified_sha256": verified.sha256,
        "pid": process.pid,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
    }
