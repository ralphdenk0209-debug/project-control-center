#!/usr/bin/env bash
# Baut das Programm fuer Mac/Linux. Danach liegt alles in dist/agent/
set -e
cd "$(dirname "$0")"
python3 -m pip install --upgrade pyinstaller -r requirements.txt
python3 -m PyInstaller --onefile --name agent --distpath dist/agent agent.py
cp -R wissen dist/agent/
cp config.json dist/agent/
echo "Fertig: dist/agent/agent  (Ordner dist/agent komplett weitergeben)"
