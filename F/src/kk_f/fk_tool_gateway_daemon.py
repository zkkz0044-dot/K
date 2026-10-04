"""Persistent daemon entrypoint for the F-owned FK external-tool gateway."""

from __future__ import annotations

from .fk_tool_gateway import ALLOWED_TOOL_CLIENT_UNITS, serve_forever_multi


def main() -> None:
    serve_forever_multi(allowed_cgroup_units=ALLOWED_TOOL_CLIENT_UNITS)


if __name__ == "__main__":
    main()
