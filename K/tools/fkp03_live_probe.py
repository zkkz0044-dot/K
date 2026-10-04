from __future__ import annotations
import os
from kk_k.human_ingress import parse_console_line
from kk_k.chat_runtime import run_turn

AUDIT_ADDRESS = "\0kk-fkp03-audit-test2"


def main() -> int:
    message = parse_console_line("\u4f60\u597dK")
    print("uid=" + str(os.geteuid()))
    print("INPUT=" + message.text)
    print("MODE=" + message.mode)
    reply = run_turn(message, audit_address=AUDIT_ADDRESS)
    print("K_REPLY=" + reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
