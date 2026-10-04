#!/usr/bin/python3
from pathlib import Path
import json, os, stat, sys
ROOT=Path("/root/K/F")
checks={
    "project_state": ROOT.joinpath("PROJECT_STATE.json").is_file(),
    "frozen_authority": ROOT.joinpath("src/kk_f/frozen_authority.py").is_file(),
    "process_preflight": ROOT.joinpath("src/kk_f/process_preflight.py").is_file(),
    "process_executor": ROOT.joinpath("src/kk_f/process_executor.py").is_file(),
    "runtime_cycle": ROOT.joinpath("src/kk_f/runtime_cycle.py").is_file(),
}
print(json.dumps({"schema":"FK04.SMOKE.1","checks":checks},sort_keys=True,separators=(",",":")))
raise SystemExit(0 if all(checks.values()) else 7)
