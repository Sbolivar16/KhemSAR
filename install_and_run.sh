#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo "   KhemSAR - Setup & Launcher (macOS/Linux)"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v conda >/dev/null 2>&1; then
  echo "[KhemSAR] Conda detected."
  if ! conda env list | grep -qE '^khemsar\s'; then
    echo "[KhemSAR] Creating conda environment 'khemsar'..."
    conda env create -f environment.yml
  fi
  echo "[KhemSAR] Launching KhemSAR at http://127.0.0.1:8765 ..."
  conda run --no-capture-output -n khemsar python -m khemsar.main
elif command -v uv >/dev/null 2>&1; then
  echo "[KhemSAR] uv detected."
  if [ ! -d ".venv" ]; then
    uv venv --python 3.11 .venv
  fi
  source .venv/bin/activate
  uv pip install -e ".[ml,dev]" || uv pip install -e ".[dev]"
  echo "[KhemSAR] Launching KhemSAR at http://127.0.0.1:8765 ..."
  python -m khemsar.main
else
  echo "[KhemSAR] Using system Python..."
  PY_BIN="$(command -v python3.11 || command -v python3.12 || command -v python3.10 || command -v python3)"
  if [ ! -d ".venv" ]; then
    "$PY_BIN" -m venv .venv
  fi
  source .venv/bin/activate
  python -m pip install --upgrade pip
  pip install -e ".[ml,dev]" || pip install -e ".[dev]"
  echo "[KhemSAR] Launching KhemSAR at http://127.0.0.1:8765 ..."
  python -m khemsar.main
fi
