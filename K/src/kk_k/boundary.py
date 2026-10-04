from __future__ import annotations

from typing import Callable

from .action_registry import ActionRegistryError, get_action_spec


class BoundaryError(RuntimeError):
    pass


def submit_action(action_id: object, transport: Callable[[str], object]) -> object:
    """K-side sealed boundary contract. Real F transport is attached only during FK."""
    try:
        spec = get_action_spec(action_id)
    except ActionRegistryError as exc:
        raise BoundaryError("action denied by registry") from exc
    if not callable(transport):
        raise BoundaryError("boundary transport unavailable")
    # Only the pre-approved action ID crosses the boundary. No params/payload/spec.
    return transport(spec.action_id)
