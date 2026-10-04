from __future__ import annotations
from dataclasses import dataclass
import re

MODES = frozenset({"CHAT", "ASK", "PLAN", "REMEMBER"})
MAX_TEXT_BYTES = 32768
MAX_PASTE_BYTES = 60000
FORBIDDEN_COMMANDS = frozenset({"approve", "execute", "run", "action", "shell", "sudo"})


class HumanIngressError(ValueError):
    pass


@dataclass(frozen=True)
class HumanMessage:
    mode: str
    text: str


def validate_text(value: object, *, max_bytes: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str):
        raise HumanIngressError("human text must be string")
    if not value.strip():
        raise HumanIngressError("human text cannot be empty")
    if len(value.encode("utf-8")) > max_bytes:
        raise HumanIngressError("human text too large")
    if "\x00" in value:
        raise HumanIngressError("NUL forbidden")
    for ch in value:
        code = ord(ch)
        if code < 32 and ch not in {"\n", "\t"}:
            raise HumanIngressError("control character forbidden")
    return value.strip()


def parse_console_line(line: object) -> HumanMessage:
    text = validate_text(line)
    if not text.startswith("/"):
        return HumanMessage("CHAT", text)
    match = re.match(r"^/([A-Za-z]+)(?:\s+(.*))?$", text, re.S)
    if not match:
        raise HumanIngressError("invalid console command")
    command = match.group(1).lower()
    payload = (match.group(2) or "").strip()
    if command in FORBIDDEN_COMMANDS:
        raise HumanIngressError("execution/approval command unavailable in FKP03")
    mapping = {"chat": "CHAT", "ask": "ASK", "plan": "PLAN", "remember": "REMEMBER"}
    if command not in mapping:
        raise HumanIngressError("unknown cognitive command")
    if not payload:
        raise HumanIngressError("cognitive command requires text")
    return HumanMessage(mapping[command], validate_text(payload))


def parse_paste_text(text: object) -> HumanMessage:
    """Receive one bounded multiline document as one cognitive CHAT message."""
    return HumanMessage("CHAT", validate_text(text, max_bytes=MAX_PASTE_BYTES))
