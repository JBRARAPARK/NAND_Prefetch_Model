#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; fi
"$PYTHON" -m unittest -v
"$PYTHON" experiments/run_axi_sweep.py
"$PYTHON" experiments/summarize_axi.py
