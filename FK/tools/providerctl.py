#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path

CONFIG=Path("/root/K/FK/model_runtime/cognition-providers.json")
STATE=Path("/root/K/K/config/runtime_cognition_state.json")

def load():
    v=json.loads(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(v,dict) or v.get("schema")!="K.COGNITION.PROVIDERS.2":
        raise SystemExit("ERROR: provider config schema")
    if not isinstance(v.get("providers"),dict) or not isinstance(v.get("routes"),dict):
        raise SystemExit("ERROR: provider config fields")
    return v

def _atomic_json(path: Path, value: dict, prefix: str):
    fd,tmp=tempfile.mkstemp(prefix=prefix,dir=str(path.parent),text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(value,f,ensure_ascii=False,indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp,0o644)
        os.replace(tmp,path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def runtime_state(v):
    default=v["routes"].get("default",[])
    enabled=[]
    for name in default:
        item=v["providers"].get(name)
        if isinstance(item,dict) and item.get("enabled") is True:
            provider_id=item.get("provider_id")
            if not isinstance(provider_id,str) or not provider_id:
                raise SystemExit("ERROR: invalid provider id")
            enabled.append(provider_id)
    if not enabled:
        raise SystemExit("ERROR: no enabled cognition provider")
    return {
        "schema":"K.COGNITION.RUNTIME_STATE.1",
        "provider_chain_id":"replaceable-provider-chain",
        "enabled_provider_ids":enabled,
        "primary_provider_id":enabled[0],
        "description":"replaceable cognition provider chain (enabled: "+", ".join(enabled)+")",
    }

def sync_state(v):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    _atomic_json(STATE,runtime_state(v),".runtime-cognition-state.")

def save(v):
    _atomic_json(CONFIG,v,".cognition-providers.")
    sync_state(v)

def main():
    if len(sys.argv)<2 or sys.argv[1] not in {"status","sync","enable","disable"}:
        raise SystemExit("usage: providerctl.py status | sync | enable NAME | disable NAME")
    v=load()
    cmd=sys.argv[1]
    if cmd=="status":
        out={
            "schema":v["schema"],
            "providers":{
                k:{
                    "enabled":bool(x.get("enabled")),
                    "provider_id":x.get("provider_id"),
                    "socket":x.get("socket"),
                }
                for k,x in v["providers"].items()
            },
            "routes":v["routes"],
        }
        print(json.dumps(out,ensure_ascii=False,separators=(",",":")))
        return
    if cmd=="sync":
        sync_state(v)
        print("RUNTIME_COGNITION_STATE_SYNCED")
        return
    if len(sys.argv)!=3:
        raise SystemExit("ERROR: provider name required")
    name=sys.argv[2]
    if name not in v["providers"]:
        raise SystemExit("ERROR: unknown provider")
    v["providers"][name]["enabled"]=(cmd=="enable")
    save(v)
    print(f"PROVIDER_{cmd.upper()}D={name}")

if __name__=="__main__":
    main()
