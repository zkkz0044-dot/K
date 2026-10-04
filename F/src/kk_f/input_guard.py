"""FH06 deterministic bounded-input primitives; no network or execution."""

from __future__ import annotations
import json, os
from pathlib import Path


class InputGuardError(ValueError):
    pass


def strict_json_loads(raw: str, *, max_chars: int) -> object:
    if not isinstance(raw, str) or type(max_chars) is not int or max_chars < 1:
        raise InputGuardError("invalid strict JSON input contract")
    if len(raw) > max_chars:
        raise InputGuardError("JSON input exceeds size limit")

    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise InputGuardError("duplicate JSON key")
            out[key] = value
        return out

    try:
        return json.loads(
            raw,
            object_pairs_hook=hook,
            parse_constant=lambda _: (_ for _ in ()).throw(
                InputGuardError("non-finite JSON number")
            ),
        )
    except InputGuardError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise InputGuardError("invalid JSON") from exc


def read_bounded_text(path: str | os.PathLike[str], *, max_bytes: int) -> str:
    if type(max_bytes) is not int or max_bytes < 1:
        raise InputGuardError("positive max_bytes required")
    p = Path(path)
    try:
        st = p.stat()
        if st.st_size > max_bytes:
            raise InputGuardError("file exceeds size limit")
        with p.open("rb") as h:
            data = h.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise InputGuardError("file exceeds size limit")
        return data.decode("utf-8")
    except InputGuardError:
        raise
    except UnicodeDecodeError as exc:
        raise InputGuardError("file is not UTF-8") from exc
    except OSError as exc:
        raise InputGuardError("file cannot be read") from exc
