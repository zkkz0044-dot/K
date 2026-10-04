#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
PYTEST_ARGS=(-q -p no:cacheprovider)

echo "[1/3] K"
(
  cd "$ROOT/K"
  PYTHONPATH=src pytest "${PYTEST_ARGS[@]}"
)

echo "[2/3] F"
(
  cd "$ROOT/F"
  PYTHONPATH="src:$ROOT/K/src" pytest "${PYTEST_ARGS[@]}"
)

echo "[3/3] FK"
(
  cd "$ROOT/FK"
  PYTHONPATH="$ROOT/F/src:$ROOT/K/src:." pytest "${PYTEST_ARGS[@]}"
)

echo "[public] Panel and release regressions"
PYTHONPATH="$ROOT/K/src:$ROOT/F/src:$ROOT/FK" pytest "${PYTEST_ARGS[@]}" "$ROOT/scripts/tests"
echo "ALL_TESTS_PASS"
