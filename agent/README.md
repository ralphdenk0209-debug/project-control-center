# Agent mit Copilot

Ein kleiner Agent, der deine **Wissensdatenbank** nutzt, **E-Mails und Kalender** bearbeitet und **Befehle ausführt**.
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

Der Agent sucht sich den Weg selbst (`email` → `typ`: `auto`). Er probiert der Reihe nach:

### 1. Klassisches Outlook (ohne Admin)
- Geht, wenn auf dem Windows-PC das **klassische Outlook-Programm** installiert und angemeldet ist.
- Es muss nichts eingerichtet werden. Outlook sollte dabei laufen.
- Mit dem **neuen** Outlook geht das nicht.

### 2. Microsoft 365 (neues Outlook, Web, jeder PC)
Ein Admin richtet das **einmal** für die ganze Firma ein:
1. Im Microsoft Entra Admin Center unter **App-Registrierungen** → **Neue Registrierung**. Name: `Copilot-Agent`, nur dieses Verzeichnis.
2. Unter **Authentifizierung**: Plattform **Mobile und Desktopanwendungen** hinzufügen und **Öffentliche Clientflows zulassen = Ja** setzen.
3. Unter **API-Berechtigungen** → Microsoft Graph → **Delegiert**: `Mail.Read`, `Calendars.ReadWrite`, `User.Read`, `offline_access`. Danach **Administratorzustimmung erteilen**.
4. Die **Anwendungs-ID (Client)** und die **Verzeichnis-ID (Mandant)** in `config.json` eintragen:
   `"m365_client_id": "..."`, `"m365_tenant": "..."`

Beim ersten Mail-Zugriff öffnet sich der Browser. Dort gibst du den angezeigten Code ein und meldest dich normal an.
Die Anmeldung bleibt in `~/.copilot-agent/m365-token.json` gespeichert. Datei löschen = abmelden.

### 3. IMAP (andere Anbieter wie Yahoo, Gmail, GMX)
In `config.json` bei `email` den `server` und den `benutzer` eintragen. Das App-Passwort fragt der Agent beim ersten Zugriff ab.

**Gut zu wissen:**
- Der Agent liest nur. Er löscht und verschiebt nichts und markiert nichts als gelesen.
- Vor jedem Zugriff fragt er nach. Ohne Nachfrage geht es, wenn du den Namen in `werkzeuge_ohne_nachfrage` einträgst, z. B. `["mails_suchen"]`.
- Die gefundenen Mails gehen zum Zusammenfassen an Copilot, also an Microsoft oder GitHub.

**Werkzeuge:** `mails_suchen`, `mail_lesen`, `mail_ordner`. Neue Werkzeuge kommen in `werkzeuge.py`, danach die Datei neu bauen.

## Kalender

Geht mit dem klassischen Outlook und mit Microsoft 365, also auf denselben Wegen wie E-Mail. Mit IMAP geht es nicht.

| Werkzeug | Was es kann |
|---|---|
| `termine_anzeigen` | Termine in einem Zeitraum, Serien einzeln aufgelöst |
| `termin_details` | Alle Teilnehmer mit Zusage oder Absage |
| `termin_erstellen` | Termin oder Besprechung mit Einladung, bei M365 auch mit Teams-Link |
| `termin_verschieben` | Einen Termin oder die ganze Serie |
| `termin_absagen` | Als Organisator: für alle absagen. Als Gast: ablehnen |
| `termin_antworten` | Zusagen, vorläufig oder absagen |
| `termin_loeschen` | Aus dem eigenen Kalender entfernen |
| `freie_zeiten_finden` | Gemeinsame freie Zeiten mit Kollegen finden |
| `termine_auswerten` | Serie oder Suche: Anzahl, **Gesamtdauer**, **alle Teilnehmer** |

Beispiele:
- *„Wie viele Stunden hatte der Jour fixe dieses Jahr, und wer war eingeladen?“*
- *„Finde nächste Woche 1 Stunde mit anna@firma.de und lade sie zum Kickoff ein.“*
- *„Sag meinen Termin morgen um 14 Uhr ab, Grund: krank.“*

**Sicherheit:** Alles, was etwas ändert, fragt **immer** nach („Wirklich ausführen?“). Das gilt auch, wenn das Werkzeug in `werkzeuge_ohne_nachfrage` steht.

**Hinweise:**
- Ein Teams-Link wird nur über Microsoft 365 automatisch erstellt. Mit dem Outlook-Programm musst du ihn in Outlook selbst hinzufügen.
- Die Zeitzone stellst du in `config.json` bei `zeitzone` ein (Standard: Deutschland).

## Alternative: MCP-Server (z. B. vom Kollegen)

Im **GitHub-Modus** kann die Copilot-CLI zusätzlich MCP-Server nutzen. Dazu den Server des Kollegen in der Copilot-CLI hinzufügen (interaktiv mit `copilot` starten, dann `/mcp add`). Danach kann Copilot ihn auch hier nutzen. Das ist nicht getestet.
Im **manuellen Modus** (normaler Copilot) geht MCP nicht. Dort helfen nur die eingebauten Werkzeuge oben.

## Einstellungen (`config.json`)

| Feld | Bedeutung |
|---|---|
| `modus` | `auto`, `github` oder `manuell` |
| `copilot_url` | Seite, die im manuellen Modus geöffnet wird (leer = keine) |
| `email` | Mail-Zugang: `typ` (auto/outlook/m365/imap), M365-IDs, IMAP-Daten |
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
