#!/usr/bin/env bash
# Start fuer Mac/Linux: .txt -> .py umbenennen und Agent starten
cd "$(dirname "$0")"
for f in agent mail kalender werkzeuge mcp_client; do
  [ -f "$f.txt" ] && mv -f "$f.txt" "$f.py"
done
python3 -c "import sys; sys.exit(sys.version_info < (3, 10))" || { echo "Python 3.10 oder neuer noetig."; exit 1; }
python3 agent.py
