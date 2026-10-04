#!/bin/bash
set -u
cd /root/K/F
python3 -m unittest tests.test_f13_managed_process -v > evidence/f13/test-round2-isolated.txt 2>&1
printf '%s\n' "$?" > evidence/f13/test-round2-isolated.exit
python3 -m unittest discover -s tests -v > evidence/f13/test-round3-full.txt 2>&1
printf '%s\n' "$?" > evidence/f13/test-round3-full.exit
python3 -m py_compile src/kk_f/*.py tests/test_f13_managed_process.py > evidence/f13/pycompile.txt 2>&1
printf '%s\n' "$?" > evidence/f13/pycompile.exit
