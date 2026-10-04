from __future__ import annotations
import os
from kk_k.human_ingress import parse_console_line
from kk_k.chat_runtime import run_turn

AUDIT="\0kk-fkp03-audit-final"


def main()->int:
    print("uid="+str(os.geteuid()))
    first=run_turn(parse_console_line("\u4f60\u597dK"),audit_address=AUDIT)
    print("KNOWN_REPLY="+first)
    if "\u6211\u662fK" not in first:
        raise RuntimeError("stable self knowledge failed")
    second=run_turn(parse_console_line("/ask PLC\u662f\u4ec0\u4e48\uff1f\u8bf7\u7528\u4e00\u53e5\u4e2d\u6587\u8bf4\u660e"),audit_address=AUDIT)
    print("OPEN_REPLY="+second)
    if not second.strip():
        raise RuntimeError("open dialogue empty")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
