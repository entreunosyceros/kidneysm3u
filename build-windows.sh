#!/bin/bash
# Genera dist/kidneysm3u.exe con PyInstaller. Se puede lanzar desde Linux o Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
  PYTHON="$ROOT/.venv/Scripts/python.exe"
else
  PYTHON="${PYTHON:-python3}"
fi

"$PYTHON" -m pip install -q pyinstaller
"$PYTHON" -m PyInstaller --noconfirm --clean kidneysm3u.spec
echo "Listo: $ROOT/dist/kidneysm3u.exe"
