#!/bin/bash
set -u
cd /root/K/F
python3 -m unittest tests.test_f11_process_executor -v > evidence/f11/test-round1-isolated.txt 2>&1
printf '%s\n' "$?" > evidence/f11/test-round1-isolated.exit
python3 -m unittest discover -s tests -v > evidence/f11/test-round2-full.txt 2>&1
printf '%s\n' "$?" > evidence/f11/test-round2-full.exit
python3 -m py_compile src/kk_f/*.py tests/test_f11_process_executor.py > evidence/f11/pycompile.txt 2>&1
printf '%s\n' "$?" > evidence/f11/pycompile.exit
