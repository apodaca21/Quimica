#!/usr/bin/env bash
# Abre la vista en vivo de la FLIR USB (no la cámara del Mac).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo "No está el entorno .venv. Crea primero:"
  echo "  /opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
exec .venv/bin/python -u scripts/captura_flir.py
