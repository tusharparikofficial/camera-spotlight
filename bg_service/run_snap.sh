#!/bin/bash
cd "$(dirname "$0")"
export PLAYWRIGHT_BROWSERS_PATH="/home/tusharparik/.cache/ms-playwright"
exec ./venv/bin/python snap_server.py "$@"
