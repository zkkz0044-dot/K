#!/usr/bin/env python3
"""Restore executable entry points after a web upload or ZIP extraction."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
restored = 0
for path in root.rglob("*"):
    if path.is_symlink() or not path.is_file() or ".git" in path.relative_to(root).parts:
        continue
    with path.open("rb") as stream:
        executable = stream.read(2) == b"#!"
    if executable:
        path.chmod(path.stat().st_mode | 0o100)
        restored += 1
print(f"EXECUTABLE_ENTRY_POINTS_RESTORED={restored}")
