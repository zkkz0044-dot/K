#!/bin/bash
cd /root/K/F
python3 -m unittest tests.test_f08_restart_ledger -v > evidence/f08/test-round1-failed.txt 2>&1
printf '%s\n' "$?" > evidence/f08/test-round1-failed.exit
