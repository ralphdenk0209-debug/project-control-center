"""Erstellt dist/agent-paket.zip: alle .py als .txt + start.bat/start.sh.

Fuer PCs oder E-Mail-Filter, die .py-Dateien blockieren.
Auf dem Ziel-PC: entpacken, ggf. MCP-Ordner hineinkopieren, start.bat doppelklicken.
"""

import shutil
from pathlib import Path

MODULE = ["agent", "mail", "kalender", "werkzeuge", "mcp_client"]   # gleiche Liste wie in start.bat
DATEIEN = ["start.bat", "start.sh", "config.json", "requirements.txt", "README.md"]

basis = Path(__file__).resolve().parent
ziel = basis / "dist" / "agent-paket"
shutil.rmtree(ziel, ignore_errors=True)
ziel.mkdir(parents=True)
for name in MODULE:
    shutil.copyfile(basis / f"{name}.py", ziel / f"{name}.txt")
for name in DATEIEN:
    shutil.copyfile(basis / name, ziel / name)
shutil.copytree(basis / "wissen", ziel / "wissen")
archiv = shutil.make_archive(str(basis / "dist" / "agent-paket"), "zip", ziel.parent, ziel.name)
print(f"Fertig: {archiv}")
