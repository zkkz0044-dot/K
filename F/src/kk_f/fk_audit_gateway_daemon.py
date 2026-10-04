from __future__ import annotations

import os
from pathlib import Path

from .fk_audit_gateway import DEFAULT_INDEX_PATH, serve_forever

PID_PATH = Path("/root/K/FK/runtime/fk-audit-witness.pid")


def main() -> int:
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()) + "\n", encoding="ascii")
    os.chmod(PID_PATH, 0o600)
    serve_forever(allowed_cgroup_unit="kk-k-runtime.service", index_path=DEFAULT_INDEX_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
