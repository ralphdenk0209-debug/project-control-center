"""MCP-Anbindung: der Agent startet MCP-Server (z. B. fuer Outlook/M365) und
stellt ihre Werkzeuge Copilot zur Verfuegung - in BEIDEN Modi.

Woher kommen die Server?
1. config.json -> "mcp_server": {"name": {"command": "...", "args": [...], "cwd": "ordner", "env": {...}}}
2. Wenn dort nichts steht: automatisch gesucht in Unterordnern des Agenten nach
   mcp.json, .vscode/mcp.json, mcp-config.json, claude_desktop_config.json

Unterstuetzt werden lokale Server (stdio = "command"). Server im Internet ("url") nicht.
Anmeldemeldungen des Servers (z. B. "Gehe zu ... und gib Code ... ein") erscheinen im Fenster.
"""

import atexit
import itertools
import json
import os
import queue
import re
import shutil
import subprocess
import threading
from pathlib import Path

import werkzeuge

KONFIG_DATEIEN = ("mcp.json", ".vscode/mcp.json", "mcp-config.json", ".mcp.json", "claude_desktop_config.json")
LESE_WOERTER = ("list", "get", "search", "read", "find", "query", "fetch", "show", "count", "lese", "such")
ZEIT_START, ZEIT_AUFRUF = 120, 600      # Sekunden (Aufruf lang wegen moeglicher Anmeldung)


class McpServer:
    def __init__(self, name: str, eintrag: dict, ordner: Path):
        self.name = name
        self.ids = itertools.count(1)
        self.antworten: queue.Queue = queue.Queue()
        befehl = eintrag["command"]
        umgebung = dict(os.environ, **{k: str(v) for k, v in (eintrag.get("env") or {}).items()})
        programm = shutil.which(befehl, path=umgebung.get("PATH")) or shutil.which(str(ordner / befehl)) or befehl
        arbeitsordner = (ordner / eintrag["cwd"]).resolve() if eintrag.get("cwd") else ordner
        self.prozess = subprocess.Popen(
            [programm, *[str(a) for a in eintrag.get("args", [])]], cwd=arbeitsordner, env=umgebung,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,     # stderr: Anmeldehinweise sichtbar
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        threading.Thread(target=self._lesen, daemon=True).start()
        self._anfrage("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "copilot-agent", "version": "1.0"}}, ZEIT_START)
        self._senden({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _lesen(self):
        for zeile in self.prozess.stdout:
            zeile = zeile.strip()
            if not zeile.startswith("{"):
                continue                       # manche Server schreiben Text auf stdout -> ignorieren
            try:
                self.antworten.put(json.loads(zeile))
            except json.JSONDecodeError:
                pass
        self.antworten.put(None)               # Server beendet

    def _senden(self, nachricht: dict):
        self.prozess.stdin.write(json.dumps(nachricht, ensure_ascii=False) + "\n")
        self.prozess.stdin.flush()

    def _anfrage(self, methode: str, parameter: dict, zeit: int) -> dict:
        nummer = next(self.ids)
        self._senden({"jsonrpc": "2.0", "id": nummer, "method": methode, "params": parameter})
        while True:
            try:
                n = self.antworten.get(timeout=zeit)
            except queue.Empty:
                raise TimeoutError(f"MCP-Server '{self.name}' antwortet nicht ({methode}).")
            if n is None:
                raise RuntimeError(f"MCP-Server '{self.name}' wurde beendet.")
            if n.get("id") == nummer and ("result" in n or "error" in n):
                if "error" in n:
                    raise RuntimeError(f"MCP-Fehler: {n['error'].get('message', n['error'])}")
                return n["result"]
            if "method" in n and "id" in n:    # Anfrage vom Server an uns
                antwort = {"result": {}} if n["method"] == "ping" else \
                          {"error": {"code": -32601, "message": "nicht unterstuetzt"}}
                self._senden({"jsonrpc": "2.0", "id": n["id"], **antwort})

    def werkzeuge(self) -> list[dict]:
        liste, weiter = [], None
        while True:
            ergebnis = self._anfrage("tools/list", {"cursor": weiter} if weiter else {}, ZEIT_START)
            liste += ergebnis.get("tools", [])
            weiter = ergebnis.get("nextCursor")
            if not weiter:
                return liste

    def aufrufen(self, werkzeug: str, argumente: dict) -> str:
        ergebnis = self._anfrage("tools/call", {"name": werkzeug, "arguments": argumente}, ZEIT_AUFRUF)
        teile = []
        for inhalt in ergebnis.get("content", []):
            if inhalt.get("type") == "text":
                teile.append(inhalt.get("text", ""))
            elif inhalt.get("type") == "resource":
                teile.append((inhalt.get("resource") or {}).get("text", "[Datei]"))
            else:
                teile.append(f"[{inhalt.get('type')}]")
        if not teile and ergebnis.get("structuredContent") is not None:
            teile.append(json.dumps(ergebnis["structuredContent"], ensure_ascii=False, indent=1))
        text = "\n".join(teile) or "(kein Inhalt)"
        return f"FEHLER vom Server: {text}" if ergebnis.get("isError") else text

    def beenden(self):
        try:
            self.prozess.terminate()
        except Exception:
            pass


# ---------------------------------------------------------------- Parameter umwandeln

def _wert(text: str, schema: dict):
    typ = schema.get("type", "string")
    if isinstance(typ, list):
        typ = next((t for t in typ if t != "null"), "string")
    s = text.strip()
    try:
        if typ == "integer":
            return int(s)
        if typ == "number":
            return float(s)
        if typ == "boolean":
            return s.lower() in ("ja", "j", "true", "1", "yes")
        if typ == "array":
            if s.startswith("["):
                return json.loads(s)
            return [_wert(x, schema.get("items") or {}) for x in re.split(r"\s*[;,]\s*", s) if x]
        if typ == "object":
            return json.loads(s)
    except (ValueError, json.JSONDecodeError):
        pass
    return text


def _beschreibung(tool: dict) -> str:
    schema = tool.get("inputSchema") or {}
    pflicht = set(schema.get("required", []))
    params = []
    for name, info in (schema.get("properties") or {}).items():
        typ = info.get("type", "")
        params.append(f"{name} ({typ}{', Pflicht' if name in pflicht else ''})"
                      + (f": {info['description'][:120]}" if info.get("description") else ""))
    text = (tool.get("description") or "").strip().replace("\n", " ")[:400]
    return f"{text} Parameter: {'; '.join(params) or 'keine'}."


def _ist_lesend(tool: dict, config: dict) -> bool:
    if tool["name"] in config.get("mcp_nur_lesend", []):
        return True
    hinweis = (tool.get("annotations") or {}).get("readOnlyHint")
    if hinweis is not None:
        return bool(hinweis)
    return tool["name"].lower().replace("-", "_").split("_")[0] in LESE_WOERTER


# ---------------------------------------------------------------- Server finden und starten

def finde_server(config: dict, basis: Path) -> dict:
    """Liefert {name: (eintrag, ordner)}."""
    basis = basis.resolve()
    eigene = config.get("mcp_server") or {}
    if eigene:
        return {n: (e, basis) for n, e in eigene.items()}
    gefunden = {}
    for unterordner in [basis] + sorted(p for p in basis.iterdir() if p.is_dir() and p.name not in ("wissen", "dist", "build")):
        for name in KONFIG_DATEIEN:
            datei = unterordner / name
            if not datei.is_file():
                continue
            try:
                daten = json.loads(re.sub(r"^\s*//.*$", "", datei.read_text(encoding="utf-8"), flags=re.M))
            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"   MCP: {datei} ist kein gueltiges JSON - uebersprungen.")
                continue
            server = daten.get("servers") or daten.get("mcpServers") or (daten.get("mcp") or {}).get("servers") or {}
            for sname, eintrag in server.items():
                if "command" not in eintrag:
                    print(f"   MCP: '{sname}' ist ein Internet-Server (url) - wird nicht unterstuetzt.")
                    continue
                text = json.dumps(eintrag).replace("${workspaceFolder}", str(unterordner).replace("\\", "\\\\"))
                gefunden[sname] = (json.loads(text), unterordner)
    return gefunden


_laufend: list[McpServer] = []


def starten(config: dict, basis: Path) -> None:
    for name, (eintrag, ordner) in finde_server(config, basis).items():
        try:
            print(f"   MCP: starte '{name}' ...")
            server = McpServer(name, eintrag, ordner)
            _laufend.append(server)
            tools = server.werkzeuge()
        except Exception as fehler:
            print(f"   MCP: '{name}' konnte nicht starten: {fehler}")
            continue
        for tool in tools:
            def aufruf(config, _s=server, _t=tool, **parameter):
                eigenschaften = (_t.get("inputSchema") or {}).get("properties") or {}
                argumente = {k: _wert(v, eigenschaften.get(k, {})) for k, v in parameter.items()}
                return _s.aufrufen(_t["name"], argumente)
            werkzeuge.registrieren(f"{name}.{tool['name']}", _beschreibung(tool), aufruf,
                                   schreibend=not _ist_lesend(tool, config))
        print(f"   MCP: '{name}' bereit, {len(tools)} Werkzeuge.")


@atexit.register
def _alle_beenden():
    for server in _laufend:
        server.beenden()
