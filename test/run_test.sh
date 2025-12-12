#!/usr/bin/env bash
set -euo pipefail

# Run tests in Test/ directory. Creates virtualenv, installs deps, runs smoke and monitor tests.
VENV=.venv_test
PY=python3

if [ ! -x "$PY" ]; then
  echo "python3 not found. Install Python 3.8+ and try again." >&2
  exit 1
fi

if [ ! -d "$VENV" ]; then
  $PY -m venv "$VENV"
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install --upgrade pip
pip install requests python-dotenv jq >/dev/null 2>&1 || pip install requests python-dotenv

echo "Running smoke_push.py"
python smoke_push.py || true

echo
echo "Running monitor_test.py (this will configure the monitor and wait for device_is_alive)"
python monitor_test.py || true

echo "Done. Check monitor.html or /api/monitor/events for events."
