#!/usr/bin/env bash
# AIM Flow — Linux run script
# Usage:  ./run_linux.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Virtual environment not found.  Run ./install_linux.sh first."
  exit 1
fi

exec .venv/bin/python launch_aim_flow_linux.py
