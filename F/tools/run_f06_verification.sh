#!/bin/bash
set -u
cd /root/K/F
python3 -m unittest tests.test_f06_heartbeat_stream -v > evidence/f06/test-round1-isolated.txt 2>&1
printf '%s\n' "$?" > evidence/f06/test-round1-isolated.exit
python3 -m unittest discover -s tests -v > evidence/f06/test-round2-full.txt 2>&1
printf '%s\n' "$?" > evidence/f06/test-round2-full.exit
python3 -m py_compile src/kk_f/*.py tests/test_f06_heartbeat_stream.py > evidence/f06/pycompile.txt 2>&1
printf '%s\n' "$?" > evidence/f06/pycompile.exit
