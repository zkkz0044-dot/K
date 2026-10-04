#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHA256SUMS.txt"
SKIP_PARTS = {".git", "__pycache__", ".pytest_cache"}

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

expected = {}
for line in MANIFEST.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    sha, rel = line.split("  ", 1)
    expected[rel] = sha

actual = {}
for path in ROOT.rglob("*"):
    if not path.is_file() or path == MANIFEST:
        continue
    rel = path.relative_to(ROOT)
    if any(part in SKIP_PARTS for part in rel.parts):
        continue
    actual[rel.as_posix()] = digest(path)

missing = sorted(set(expected) - set(actual))
extra = sorted(set(actual) - set(expected))
changed = sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])
if missing or extra or changed:
    print("SHA256_VERIFY=FAIL")
    for label, items in (("missing", missing), ("extra", extra), ("changed", changed)):
        for item in items:
            print(f"{label}: {item}")
    raise SystemExit(1)

print(f"SHA256_VERIFY=PASS FILES={len(actual)}")
