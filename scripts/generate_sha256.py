#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SHA256SUMS.txt"
SKIP_PARTS = {".git", "__pycache__", ".pytest_cache"}

def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == OUTPUT:
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        yield path, rel.as_posix()

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

lines = [f"{digest(path)}  {rel}" for path, rel in iter_files()]
OUTPUT.write_text("\n".join(sorted(lines)) + "\n", encoding="utf-8", newline="\n")
print(f"SHA256_GENERATED={len(lines)}")
