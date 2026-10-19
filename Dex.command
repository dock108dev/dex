#!/bin/zsh
set -e
DEX_REPO="${0:A:h}"
exec /usr/bin/python3 "$DEX_REPO/scripts/start_local.py"
