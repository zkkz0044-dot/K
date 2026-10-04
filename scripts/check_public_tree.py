#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_LIMIT = 5_000_000

BANNED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pem", ".pfx", ".key", ".log", ".pid", ".sock", ".jsonl"}
IGNORED_PARTS = {".git"}
BANNED_DIR_NAMES = {"__pycache__", ".pytest_cache", "secrets", "runtime"}
PUBLIC_BINARY_FILES = {"PANEL-v0.1/icon-180.png", "PANEL-v0.1/icon-192.png", "PANEL-v0.1/icon-512.png"}
CONTENT_PATTERNS = {
    "OpenAI project key": re.compile(r"sk-proj-[A-Za-z0-9_-]{12,}"),
    "API key": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "private key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "Windows user path": re.compile(r"C:\\Users\\[^\\\s]+", re.I),
    "WSL user path": re.compile(r"/mnt/c/Users/[^/\s]+", re.I),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
}
def scan() -> list[str]:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in rel.parts):
            continue
        if path.is_symlink():
            findings.append(f"symlink needs explicit review: {rel}")
            continue
        if path.is_dir():
            if path.name in BANNED_DIR_NAMES:
                findings.append(f"banned runtime directory: {rel}")
            continue
        if any(part in BANNED_DIR_NAMES for part in rel.parts):
            continue
        if rel.as_posix() == "scripts/check_public_tree.py":
            continue
        if path.suffix.lower() in BANNED_SUFFIXES:
            findings.append(f"banned file type: {rel}")
            continue
        try:
            if path.stat().st_size > TEXT_LIMIT:
                findings.append(f"oversize file needs explicit review: {rel}")
                continue
            if rel.as_posix() in PUBLIC_BINARY_FILES:
                if not path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                    findings.append(f"invalid public PNG: {rel}")
                continue
            text = path.read_bytes().decode("utf-8")
            if '\r\n' in text:
                findings.append(f"noncanonical CRLF text: {rel}")
        except (UnicodeDecodeError, OSError):
            findings.append(f"unreadable/non-UTF8 file needs explicit review: {rel}")
            continue
        for label, pattern in CONTENT_PATTERNS.items():
            matches = list(pattern.finditer(text))
            if label == "email address":
                matches = [
                    m for m in matches
                    if not m.group(0).lower().endswith("@example.com")
                ]
            if matches:
                findings.append(f"{label}: {rel}")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("PUBLIC_TREE_CHECK=FAIL")
        for item in findings:
            print(f"- {item}")
        return 1
    print("PUBLIC_TREE_CHECK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
