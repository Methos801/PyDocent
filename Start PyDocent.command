#!/bin/bash
# Double-click after following the source setup in README.md.
APP_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR" || exit 1
if [ ! -x .venv/bin/python ]; then
    echo "First create .venv and install requirements.txt; see README.md."
    read -r -p "Press Enter to close..."
    exit 1
fi
echo "Starting PyDocent. Use Quit in the app when finished."
exec .venv/bin/python app.py
