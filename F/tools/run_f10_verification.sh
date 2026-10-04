#!/bin/bash
set -u
cd /root/K/F
python3 -m unittest tests.test_f10_process_preflight -v > evidence/f10/test-round1-isolated.txt 2>&1
printf '%s\n' "$?" > evidence/f10/test-round1-isolated.exit
python3 -m unittest discover -s tests -v > evidence/f10/test-round2-full.txt 2>&1
printf '%s\n' "$?" > evidence/f10/test-round2-full.exit
python3 -m py_compile src/kk_f/*.py tests/test_f10_process_preflight.py > evidence/f10/pycompile.txt 2>&1
printf '%s\n' "$?" > evidence/f10/pycompile.exit
