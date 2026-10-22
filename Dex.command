#!/bin/zsh
set -e
DEX_REPO="${0:A:h}"
DEX_PYTHON="${DEX_APP_PYTHON:-$DEX_REPO/.local/runtime/bin/python}"
if [[ ! -x "$DEX_PYTHON" ]]; then
  print -u2 "Configure DEX_APP_PYTHON or .local/runtime before opening Dex. See docs/local-development.md."
  exit 1
fi
exec "$DEX_PYTHON" -I "$DEX_REPO/scripts/start_local.py"
