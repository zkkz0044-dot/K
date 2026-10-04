#!/usr/bin/python3
from __future__ import annotations
import argparse, json, sys
sys.path.insert(0,"/root/K/F/src")
from kk_f.fk_approval import issue_a03_approval

def main() -> int:
    parser=argparse.ArgumentParser(description="Issue one FKP01 A03 approval. Run only after explicit human authorization.")
    parser.add_argument("--ttl",type=int,required=True,help="1..300 seconds")
    args=parser.parse_args()
    value=issue_a03_approval(ttl_seconds=args.ttl)
    print(json.dumps(value,sort_keys=True,separators=(",",":")))
    return 0
if __name__=="__main__": raise SystemExit(main())
