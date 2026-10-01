#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; fi
"$PYTHON" -m unittest -v
"$PYTHON" sim.py --config config_tlc.json --out results/baseline
"$PYTHON" sim.py --config config_tlc.json --out results --sweep
"$PYTHON" plot_results.py
