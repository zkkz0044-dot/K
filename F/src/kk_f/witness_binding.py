"""FH03 optional runtime binding to the privilege-separated monotonic witness."""

from __future__ import annotations

import os

from .witness_client import WitnessClientError, commit, prepare, recover, verify

ENV_SOCKET = "KK_F_WITNESS_SOCKET"


class WitnessBindingError(RuntimeError):
    pass


def socket_path() -> str | None:
    value = os.environ.get(ENV_SOCKET)
    if value is None or value == "":
        return None
    if not value.startswith("/") or "\x00" in value:
        raise WitnessBindingError("invalid witness socket environment")
    return value


def enabled() -> bool:
    return socket_path() is not None


def recover_current(channel: str, generation: int, digest: str) -> None:
    path = socket_path()
    if path is None:
        return
    try:
        recover(path, channel, generation, digest)
    except WitnessClientError as exc:
        raise WitnessBindingError("witness rejected current durable state") from exc


def verify_baseline(channel: str, generation: int, digest: str) -> None:
    path = socket_path()
    if path is None:
        return
    try:
        verify(path, channel, generation, digest)
    except WitnessClientError as exc:
        raise WitnessBindingError("witness baseline mismatch") from exc


def prepare_transition(
    channel: str, current_generation: int, current_digest: str, new_generation: int, new_digest: str
) -> None:
    path = socket_path()
    if path is None:
        return
    try:
        prepare(path, channel, current_generation, current_digest, new_generation, new_digest)
        return
    except WitnessClientError:
        # A lost PREPARE response may have left a pending record. Disk is still old,
        # so exact recovery of the old state safely aborts only that pending transition.
        try:
            recover(path, channel, current_generation, current_digest)
            prepare(path, channel, current_generation, current_digest, new_generation, new_digest)
            return
        except WitnessClientError as exc:
            raise WitnessBindingError("witness prepare failed closed") from exc


def commit_transition(channel: str, generation: int, digest: str) -> None:
    path = socket_path()
    if path is None:
        return
    try:
        commit(path, channel, generation, digest)
        return
    except WitnessClientError:
        # A lost COMMIT response is resolved from the exact state already on disk.
        try:
            recover(path, channel, generation, digest)
            return
        except WitnessClientError as exc:
            raise WitnessBindingError("witness commit/recovery failed closed") from exc
