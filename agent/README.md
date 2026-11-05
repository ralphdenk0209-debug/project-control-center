# Agent mit GitHub Copilot

Ein kleiner Agent, der deine **Wissensdatenbank** nutzt und **Befehle ausführt**.
Als Gehirn benutzt er die installierte **GitHub-Copilot-CLI**.

## Voraussetzungen (auf jedem PC)

1. GitHub-Copilot-CLI ist installiert und angemeldet.
   Test: `copilot --help` im Terminal funktioniert.
2. Fürs Bauen der .exe zusätzlich: Python 3.10 oder neuer.

## Starten (ohne Bauen)

```
python agent.py
```

- `exit` beendet den Agenten.
- `neu` leert den Gesprächsverlauf.

## Wissensdatenbank

- Lege `.md`- oder `.txt`-Dateien in den Ordner `wissen/`.
- Der Agent liest sie bei **jeder Frage neu**. Ein Neustart ist also nicht nötig.

## Befehle erlauben (`config.json`)

| Feld | Bedeutung |
|---|---|
| `erlaubte_tools` | Was Copilot ohne Nachfrage darf, z. B. `"shell(git)"` |
| `verbotene_tools` | Was immer verboten ist, z. B. `"shell(git push)"` |
| `alles_erlauben` | `true` erlaubt **alle** Befehle. Vorsicht! |
| `arbeitsordner` | Ordner, in dem gearbeitet wird (Standard: der Programmordner) |
| `modell` | Optional ein bestimmtes Copilot-Modell |
| `copilot_befehl` | Name oder voller Pfad zur Copilot-CLI |
| `extra_argumente` | Weitere Copilot-Optionen, z. B. `["--silent"]` |

Was nicht erlaubt ist, wird blockiert. Copilot fragt im Programmodus nicht nach.

## Als Programm bauen (eigenständige Datei)

- **Windows:** `build.bat` doppelklicken → `dist\agent\agent.exe`
- **Mac/Linux:** `./build.sh` → `dist/agent/agent`

Gib den **ganzen Ordner** `dist/agent` weiter (Programm + `wissen/` + `config.json`).
Pro Betriebssystem musst du einmal bauen.

## So funktioniert es

1. Du stellst eine Frage.
2. Der Agent schreibt das Wissen, den Verlauf und die Frage in die Datei `.agent-auftrag.md`.
3. Er ruft `copilot -p "Lies .agent-auftrag.md …"` auf. Copilot antwortet und führt dabei erlaubte Befehle aus.
4. Danach wird die Datei wieder gelöscht.
