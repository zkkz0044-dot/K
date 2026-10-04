#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 -m compileall -q /root/K/K/src /root/K/F/src /root/K/FK/model_runtime
run_suite() {
  name=$1; dir=$2; path=$3
  echo "=== $name PASS 1 ==="
  (cd "$dir" && PYTHONPATH="$path" pytest -q)
  echo "=== $name PASS 2 ==="
  (cd "$dir" && PYTHONPATH="$path" pytest -q)
}
run_suite K /root/K/K /root/K/K/src:/root/K/F/src
run_suite F /root/K/F /root/K/F/src:/root/K/K/src
run_suite FK /root/K/FK /root/K/F/src:/root/K/K/src
