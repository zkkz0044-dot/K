from __future__ import annotations
import os
from kk_k.human_ingress import parse_console_line
from kk_k.chat_runtime import run_turn

AUDIT_ADDRESS="\0kk-fkp03-audit-repeat5"
MESSAGES=(
    "\u4f60\u597dK",
    "/ask \u4f60\u662f\u8c01",
    "/ask \u4f60\u548c\u6a21\u578b\u662f\u4ec0\u4e48\u5173\u7cfb",
    "/ask \u4f60\u80fd\u76f4\u63a5\u6267\u884c\u547d\u4ee4\u5417",
    "/remember FKP03\u5185\u90e8\u9a8c\u6536\u6807\u8bb0",
)


def main()->int:
    print("uid="+str(os.geteuid()))
    for i,text in enumerate(MESSAGES,1):
        msg=parse_console_line(text)
        reply=run_turn(msg,audit_address=AUDIT_ADDRESS)
        print(f"TURN={i} MODE={msg.mode} INPUT={msg.text}")
        print(f"REPLY={reply}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
