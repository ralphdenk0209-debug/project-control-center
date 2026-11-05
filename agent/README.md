# Agent mit Copilot

Ein kleiner Agent, der deine **Wissensdatenbank** nutzt, **Werkzeuge** wie E-Mail benutzt und **Befehle ausführt**.
Er läuft mit **jedem Copilot**.

## Zwei Modi

| Modus | Für wen | Wie |
|---|---|---|
| **GitHub** | Wer die GitHub-Copilot-CLI hat | Läuft automatisch. Copilot führt erlaubte Befehle selbst aus. |
| **Manuell** | Jeder Copilot (Windows, Browser, Microsoft 365) | Kopieren und Einfügen. Befehle laufen erst nach deinem „j“. |

Bei `"modus": "auto"` (Standard) nimmt der Agent die GitHub-CLI, wenn sie installiert ist, sonst den manuellen Modus.

**Warum manuell?** Der normale Microsoft Copilot hat keine Schnittstelle für eigene Programme.

## Starten

```
python agent.py
```

- `exit` beendet den Agenten.
- `neu` startet ein neues Gespräch. Im manuellen Modus dann auch in Copilot einen neuen Chat öffnen.
- `merke: ...` speichert neues Wissen in `wissen/gelernt.md`.

## Ablauf im manuellen Modus

1. Du stellst eine Frage.
2. Copilot öffnet sich im Browser, und der Auftrag liegt in der Zwischenablage.
3. In Copilot mit **Strg+V** einfügen und absenden.
4. Die Antwort von Copilot **kopieren**, dann im Agenten **Enter** drücken.
5. Schlägt Copilot einen Befehl vor, fragt der Agent: `Ausführen? (j/n)`.
6. Das Ergebnis geht wieder in die Zwischenablage. Weiter bei Schritt 3.

Falls die Zwischenablage nicht geht: Der Auftrag steht auch in `copilot-auftrag.txt`. Die Antwort fügst du dann direkt ein und beendest sie mit einer Zeile `ENDE`.

## Wissensdatenbank

- Lege `.md`- oder `.txt`-Dateien in den Ordner `wissen/`.
- Sie werden bei **jeder Frage neu** gelesen.

## E-Mails durchsuchen und zusammenfassen

Beispiele: *„Fasse meine Mails der letzten Woche zusammen“*, *„Suche Rechnungen von den Stadtwerken“*.

**Einrichten (einmalig):**
1. Beim Mail-Anbieter ein **App-Passwort** erstellen. Bei Yahoo: Kontosicherheit → App-Passwort erstellen.
2. In `config.json` bei `email` den `server` und den `benutzer` (deine Mail-Adresse) eintragen.
3. Das Passwort fragt der Agent beim ersten Zugriff ab. Gespeichert wird es nicht.
   Alternativ: als Umgebungsvariable `AGENT_EMAIL_PASSWORT` setzen.

| Anbieter | Server |
|---|---|
| Yahoo | `imap.mail.yahoo.com` |
| Gmail | `imap.gmail.com` |
| GMX | `imap.gmx.net` |
| web.de | `imap.web.de` |
| T-Online | `secureimap.t-online.de` |

**Gut zu wissen:**
- Der Agent liest nur. Er löscht und verschiebt nichts und markiert nichts als gelesen.
- Vor jedem Zugriff fragt er nach. Ohne Nachfrage geht es, wenn du den Namen in `werkzeuge_ohne_nachfrage` einträgst, z. B. `["mails_suchen"]`.
- Die gefundenen Mails gehen zum Zusammenfassen an Copilot, also an Microsoft oder GitHub.
- Outlook.com und Microsoft 365 gehen so **nicht**, weil Microsoft dort die Anmeldung per Passwort gesperrt hat.

**Werkzeuge:** `mails_suchen`, `mail_lesen`, `mail_ordner`. Neue Werkzeuge kommen in `werkzeuge.py`, danach die Datei neu bauen.

## Einstellungen (`config.json`)

| Feld | Bedeutung |
|---|---|
| `modus` | `auto`, `github` oder `manuell` |
| `copilot_url` | Seite, die im manuellen Modus geöffnet wird (leer = keine) |
| `email` | Mail-Zugang: server, port, benutzer |
| `werkzeuge_ohne_nachfrage` | Werkzeuge, die ohne Rückfrage laufen dürfen |
| `verbotene_befehle` | Manuell: Befehle mit diesen Wörtern werden nie ausgeführt |
| `erlaubte_tools` | GitHub: Was Copilot ohne Nachfrage darf, z. B. `"shell(git)"` |
| `verbotene_tools` | GitHub: Was immer verboten ist |
| `alles_erlauben` | GitHub: `true` erlaubt **alle** Befehle. Vorsicht! |
| `arbeitsordner` | Ordner, in dem Befehle laufen (Standard: der Programmordner) |
| `modell` | GitHub: optional ein bestimmtes Modell |
| `copilot_befehl` | GitHub: Name oder Pfad der Copilot-CLI |
| `extra_argumente` | GitHub: weitere Optionen, z. B. `["--silent"]` |

## Als Programm bauen (eigenständige Datei)

- **Windows:** `build.bat` doppelklicken → `dist\agent\agent.exe`
- **Mac/Linux:** `./build.sh` → `dist/agent/agent`

Gib den **ganzen Ordner** `dist/agent` weiter (Programm + `wissen/` + `config.json`).
Auf dem Ziel-PC muss Python nicht installiert sein. Pro Betriebssystem musst du einmal bauen.
