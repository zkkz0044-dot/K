"""FH07 local crash-recovery helpers for uncommitted transaction artifacts."""

from __future__ import annotations
import os
from pathlib import Path


class TransactionRecoveryError(RuntimeError):
    pass


def discard_stale_fixed_temp(final_path: str | os.PathLike[str]) -> None:
    """Discard only `<final>.tmp`; unlink never follows a symlink.

    Call after the committed final file has been validated, or immediately before a
    single-writer transaction starts. A directory at the temp name fails closed.
    """
    final = Path(final_path)
    parent = final.parent
    name = final.name + ".tmp"
    try:
        dfd = os.open(str(parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise TransactionRecoveryError("transaction directory unavailable") from exc
    try:
        try:
            os.unlink(name, dir_fd=dfd)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise TransactionRecoveryError("stale transaction temp cannot be discarded") from exc
        try:
            os.fsync(dfd)
        except OSError as exc:
            raise TransactionRecoveryError("temp cleanup directory fsync failed") from exc
    finally:
        os.close(dfd)
