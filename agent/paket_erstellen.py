"""Erstellt dist/agent-paket.zip: alle .py als .txt, start.bat als Start.txt.

Fuer PCs oder E-Mail-Filter, die .py-Dateien blockieren.
Auf dem Ziel-PC: entpacken, ggf. MCP-Ordner hineinkopieren,
Start.txt in Start.bat umbenennen und doppelklicken.
"""

import shutil
from pathlib import Path

MODULE = ["agent", "mail", "kalender", "werkzeuge", "mcp_client"]   # gleiche Liste wie in start.bat
DATEIEN = {"start.bat": "Start.txt", "start.sh": "start.sh", "config.json": "config.json",
           "requirements.txt": "requirements.txt", "README.md": "README.md"}   # Quelle -> Name im Paket

basis = Path(__file__).resolve().parent
ziel = basis / "dist" / "agent-paket"
shutil.rmtree(ziel, ignore_errors=True)
ziel.mkdir(parents=True)
for name in MODULE:
    shutil.copyfile(basis / f"{name}.py", ziel / f"{name}.txt")
for quelle, name in DATEIEN.items():
    shutil.copyfile(basis / quelle, ziel / name)
shutil.copytree(basis / "wissen", ziel / "wissen")
archiv = shutil.make_archive(str(basis / "dist" / "agent-paket"), "zip", ziel.parent, ziel.name)
print(f"Fertig: {archiv}")
