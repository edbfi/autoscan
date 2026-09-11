#!/usr/bin/env bash
set -euo pipefail
bash tools/base-smoke.sh "$1" "$2"
python3 tools/runtime_check.py "$1" "$2"
