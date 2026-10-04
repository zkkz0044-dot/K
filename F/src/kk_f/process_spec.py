"""F09 strict process launch contract; validation only, no process execution."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

PROCESS_SPEC_VERSION = "0.1"
PROCESS_SPEC_KEYS = frozenset({"version", "executable", "argv", "cwd", "env", "sha256"})
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DANGEROUS_ENV_KEYS = frozenset(
    {
        "BASH_ENV",
        "ENV",
        "GCONV_PATH",
        "NODE_OPTIONS",
        "PERL5LIB",
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "RUBYLIB",
    }
)
DANGEROUS_ENV_PREFIXES = ("LD_", "DYLD_")
MAX_PATH_CHARS = 4096
MAX_ARGV_ITEMS = 128
MAX_ARG_CHARS = 4096
MAX_ENV_ITEMS = 128
MAX_ENV_VALUE_CHARS = 16384


class ProcessSpecError(ValueError):
    """Raised when a launch specification is not exact and safe-by-contract."""


def _clean_string(value: object, where: str, *, absolute: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ProcessSpecError(f"{where}: non-empty NUL-free string required")
    if len(value) > (MAX_PATH_CHARS if absolute else MAX_ARG_CHARS):
        raise ProcessSpecError(f"{where}: string exceeds limit")
    if absolute:
        if not value.startswith("/") or (value != "/" and (value.endswith("/") or "//" in value)):
            raise ProcessSpecError(f"{where}: canonical absolute POSIX path required")
        path = PurePosixPath(value)
        if (
            not path.parts
            or path.parts[0] != "/"
            or any(part in ("", ".", "..") for part in path.parts[1:])
            or path.as_posix() != value
        ):
            raise ProcessSpecError(f"{where}: canonical absolute POSIX path required")
    return value


def validate_process_spec(value: object) -> dict:
    if not isinstance(value, dict):
        raise ProcessSpecError("process spec: object required")
    if frozenset(value) != PROCESS_SPEC_KEYS:
        raise ProcessSpecError("process spec: exact keys required")
    if value["version"] != PROCESS_SPEC_VERSION:
        raise ProcessSpecError("process spec: unsupported version")
    _clean_string(value["executable"], "executable", absolute=True)
    _clean_string(value["cwd"], "cwd", absolute=True)
    if not isinstance(value["sha256"], str) or not HEX64_RE.fullmatch(value["sha256"]):
        raise ProcessSpecError("sha256: lowercase SHA-256 required")

    argv = value["argv"]
    if not isinstance(argv, list):
        raise ProcessSpecError("argv: list required")
    if len(argv) > MAX_ARGV_ITEMS:
        raise ProcessSpecError("argv: too many items")
    for index, arg in enumerate(argv):
        _clean_string(arg, f"argv[{index}]")

    env = value["env"]
    if not isinstance(env, dict):
        raise ProcessSpecError("env: object required")
    if len(env) > MAX_ENV_ITEMS:
        raise ProcessSpecError("env: too many variables")
    for key, item in env.items():
        if not isinstance(key, str) or len(key) > 128 or not ENV_KEY_RE.fullmatch(key):
            raise ProcessSpecError("env: invalid variable name")
        if key in DANGEROUS_ENV_KEYS or key.startswith(DANGEROUS_ENV_PREFIXES):
            raise ProcessSpecError("env: loader/interpreter control variable forbidden")
        if not isinstance(item, str) or "\x00" in item:
            raise ProcessSpecError("env: string values without NUL required")
        if len(item) > MAX_ENV_VALUE_CHARS:
            raise ProcessSpecError("env: value exceeds limit")
    return value
