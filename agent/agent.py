"""Standalone-Agent mit Wissensdatenbank, Werkzeugen (z. B. E-Mails) und Befehlen.

Zwei Modi (config.json -> "modus"):
- "github":  nutzt die installierte GitHub-Copilot-CLI automatisch.
- "manuell": funktioniert mit JEDEM Copilot (Windows, Browser, Microsoft 365).
             Der Agent kopiert den Auftrag in die Zwischenablage, du fuegst ihn
             in Copilot ein und kopierst die Antwort zurueck.
- "auto":    GitHub-Copilot-CLI, wenn installiert, sonst "manuell".

Start: python agent.py   (oder die gebaute agent.exe)
"""

import datetime
import json
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

import werkzeuge

AUFTRAG_DATEI = ".agent-auftrag.md"
MAX_VERLAUF = 4            # GitHub-Modus: so viele letzte Runden mitgeben
MAX_ZEICHEN = 3000         # Kuerzung alter Runden
MAX_RUNDEN = 6             # max. Werkzeug-/Befehlsrunden pro Frage
MAX_AUSGABE = 12000        # Kuerzung von Werkzeug- und Befehlsergebnissen
IST_WINDOWS = platform.system() == "Windows"

BEFEHL_MUSTER = re.compile(r"```befehl[ \t]*\r?\n(.*?)```", re.DOTALL)
WERKZEUG_MUSTER = re.compile(r"```werkzeug[ \t]*\r?\n(.*?)```", re.DOTALL)

STANDARD_CONFIG = {
    "modus": "auto",
    "copilot_befehl": "copilot",
    "copilot_url": "https://copilot.microsoft.com",
    "arbeitsordner": ".",
    "modell": None,
    "alles_erlauben": False,
    "erlaubte_tools": ["shell(git)"],
    "verbotene_tools": ["shell(git push)"],
    "verbotene_befehle": ["format", "rm -rf", "del /s", "rd /s", "shutdown", "git push"],
    "werkzeuge_ohne_nachfrage": [],
    "zeitzone": "W. Europe Standard Time",
    "email": {
        "typ": "auto",
        "m365_client_id": "",
        "m365_tenant": "organizations",
        "server": "",
        "port": 993,
        "benutzer": "",
        "passwort_umgebungsvariable": "AGENT_EMAIL_PASSWORT",
    },
    "extra_argumente": [],
}


# ---------------------------------------------------------------- Grundlagen

def basis_ordner() -> Path:
    """Ordner, in dem agent.py bzw. agent.exe liegt."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def lade_config(basis: Path) -> dict:
    datei = basis / "config.json"
    if not datei.exists():
        datei.write_text(json.dumps(STANDARD_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"config.json angelegt: {datei}")
    config = dict(STANDARD_CONFIG)
    config.update(json.loads(datei.read_text(encoding="utf-8")))
    return config


def lade_wissen(basis: Path) -> str:
    teile = []
    for datei in sorted((basis / "wissen").glob("*")):
        if datei.is_file() and datei.suffix.lower() in (".md", ".txt"):
            teile.append(f"### {datei.name}\n{datei.read_text(encoding='utf-8', errors='replace')}")
    return "\n\n".join(teile) or "(Die Wissensdatenbank ist leer.)"


def merke(basis: Path, text: str) -> None:
    """Haengt neues Wissen an wissen/gelernt.md an."""
    if not text:
        print("Bitte so: merke: Rechnungen liegen in C:\\Daten\\Rechnungen")
        return
    datei = basis / "wissen" / "gelernt.md"
    if not datei.exists():
        datei.write_text("# Gelernt (mit 'merke:' hinzugefuegt)\n\n", encoding="utf-8")
    with datei.open("a", encoding="utf-8") as f:
        f.write(f"- {text}\n")
    print(f"Gemerkt in {datei.name}.")


def ja(frage: str) -> bool:
    try:
        return input(f"   {frage} (j/n): ").strip().lower() in ("j", "ja", "y")
    except EOFError:
        return False


def heute_text() -> str:
    jetzt = datetime.datetime.now()
    tage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    return f"Heute ist {tage[jetzt.weekday()]}, {jetzt:%d.%m.%Y}, {jetzt:%H:%M} Uhr."


def anleitung(arbeitsordner: Path, mit_befehlen: bool) -> list[str]:
    teile = [
        "Du bist ein hilfreicher Agent. Antworte auf Deutsch, kurz und klar.",
        heute_text() + " Daten an Werkzeuge immer als JJJJ-MM-TT HH:MM.",
        "Vor Aenderungen (Termine setzen, verschieben, absagen, loeschen) erst mit termine_anzeigen "
        "die richtige ID holen. Bei Unklarheiten nachfragen statt raten.",
        "Nutze die Wissensdatenbank unten. Wenn dort etwas fehlt, sag das ehrlich.",
        "",
        "## Werkzeuge",
        "Du kannst diese Werkzeuge benutzen:",
        werkzeuge.beschreibungen(),
        "",
        "Aufruf: Schreibe einen Block wie diesen und hoere dann auf zu schreiben:",
        "```werkzeug", "mails_suchen", "suche: Rechnung", "tage: 14", "```",
        "Erste Zeile = Name, danach je Zeile 'parameter: wert'. Mehrere Bloecke sind erlaubt.",
        "Du bekommst die Ergebnisse in der naechsten Nachricht und antwortest dann.",
    ]
    if mit_befehlen:
        shell = "Windows-Eingabeaufforderung (cmd)" if IST_WINDOWS else "bash"
        teile += [
            "",
            "## Befehle",
            f"Du kannst Befehle auf meinem PC ausfuehren lassen (System: {platform.system()}, "
            f"Shell: {shell}, Ordner: {arbeitsordner}). Jeder Befehl in einen eigenen Block:",
            "```befehl", "dir" if IST_WINDOWS else "ls", "```",
        ]
    else:
        teile += ["", "Shell-Befehle fuehrst du wie gewohnt selbst aus. "
                      "E-Mails usw. bekommst du NUR ueber die Werkzeuge oben."]
    return teile


# ---------------------------------------------------------------- Modus GitHub

class GithubCopilot:
    """Ruft die GitHub-Copilot-CLI auf. Copilot fuehrt erlaubte Shell-Befehle selbst aus."""

    mit_befehlen = False

    def __init__(self, config: dict, programm: str, arbeitsordner: Path, basis: Path):
        self.arbeitsordner = arbeitsordner
        self.verlauf: list[tuple[str, str]] = []
        self.args = [programm]
        if config.get("modell"):
            self.args += ["--model", config["modell"]]
        if config.get("alles_erlauben"):
            self.args.append("--allow-all-tools")
        else:
            for tool in config.get("erlaubte_tools", []):
                self.args += ["--allow-tool", tool]
        for tool in config.get("verbotene_tools", []):
            self.args += ["--deny-tool", tool]
        self.args += config.get("extra_argumente", [])

    def neu(self) -> None:
        self.verlauf.clear()

    def senden(self, wissen: str, text: str) -> str:
        teile = ["# Auftrag fuer den Agenten", *anleitung(self.arbeitsordner, False),
                 "", "## Wissensdatenbank", wissen]
        if self.verlauf:
            teile += ["", "## Bisheriges Gespraech"]
            for f, a in self.verlauf[-MAX_VERLAUF:]:
                teile += [f"**Nutzer:** {f[:MAX_ZEICHEN]}", f"**Agent:** {a[:MAX_ZEICHEN]}", ""]
        teile += ["", "## Aktuelle Nachricht", text]

        # Auftrag als Datei: keine Probleme mit Laenge oder Sonderzeichen.
        datei = self.arbeitsordner / AUFTRAG_DATEI
        datei.write_text("\n".join(teile), encoding="utf-8")
        kurz = (f"Lies die Datei {AUFTRAG_DATEI} in diesem Ordner vollstaendig "
                "und erledige den Auftrag darin. Gib nur deine Antwort an den Nutzer aus.")
        try:
            erg = subprocess.run(self.args + ["-p", kurz], cwd=self.arbeitsordner,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            datei.unlink(missing_ok=True)
        if erg.returncode != 0:
            antwort = f"[Fehler von Copilot, Code {erg.returncode}]\n{erg.stderr.strip()}"
        else:
            antwort = erg.stdout.strip()
        self.verlauf.append((text, antwort))
        return antwort


# ---------------------------------------------------------------- Modus Manuell

class Zwischenablage:
    """Zwischenablage ueber tkinter (in Python enthalten). Faellt still weg, wenn nicht moeglich."""

    def __init__(self):
        try:
            import tkinter
            self.tk = tkinter.Tk()
            self.tk.withdraw()
        except Exception:
            self.tk = None

    @property
    def geht(self) -> bool:
        return self.tk is not None

    def setzen(self, text: str) -> bool:
        if not self.tk:
            return False
        try:
            self.tk.clipboard_clear()
            self.tk.clipboard_append(text)
            self.tk.update()
            return True
        except Exception:
            return False

    def lesen(self) -> str:
        try:
            return self.tk.clipboard_get() if self.tk else ""
        except Exception:
            return ""


class ManuellerCopilot:
    """Jeder Copilot: Auftrag per Zwischenablage hin, Antwort zurueck."""

    mit_befehlen = True

    def __init__(self, config: dict, arbeitsordner: Path, basis: Path):
        self.config = config
        self.arbeitsordner = arbeitsordner
        self.basis = basis
        self.ablage = Zwischenablage()
        self.erste_nachricht = True
        self.browser_offen = False

    def neu(self) -> None:
        self.erste_nachricht = True
        print("Bitte in Copilot einen NEUEN Chat beginnen.")

    def senden(self, wissen: str, text: str) -> str:
        if self.erste_nachricht:
            text = "\n".join(["# Auftrag fuer dich als Agent", *anleitung(self.arbeitsordner, True),
                              "", "## Wissensdatenbank", wissen, "", "## Meine Frage", text])
            self.erste_nachricht = False
        elif not text.startswith("Ergebnisse deiner Aufrufe"):
            text = f"({heute_text()})\n{text}"
        (self.basis / "copilot-auftrag.txt").write_text(text, encoding="utf-8")
        if not self.browser_offen and self.config.get("copilot_url"):
            webbrowser.open(self.config["copilot_url"])
            self.browser_offen = True
        if self.ablage.setzen(text):
            print("\n>> Auftrag ist in der Zwischenablage. In Copilot einfuegen (Strg+V) und absenden.")
            print(">> Antwort von Copilot kopieren und hier Enter druecken.")
            print("   (Oder Antwort hier einfuegen und mit einer Zeile ENDE abschliessen.)")
        else:
            print(f"\n>> Auftrag steht in: {self.basis / 'copilot-auftrag.txt'}")
            print("   Inhalt kopieren, in Copilot einfuegen und absenden.")
            print(">> Antwort von Copilot hier einfuegen und mit einer Zeile ENDE abschliessen.")
        zeilen = []
        while True:
            try:
                zeile = input()
            except EOFError:
                break
            if zeile.strip() == "ENDE":
                break
            if not zeilen and not zeile.strip() and self.ablage.geht:
                return self.ablage.lesen().strip()
            zeilen.append(zeile)
        return "\n".join(zeilen).strip()


# ---------------------------------------------------------------- Agenten-Schleife

class Agent:
    def __init__(self, backend, config: dict, arbeitsordner: Path):
        self.backend = backend
        self.config = config
        self.arbeitsordner = arbeitsordner

    def werkzeug_ausfuehren(self, block: str) -> str:
        zeilen = [z for z in block.strip().splitlines() if z.strip()]
        if not zeilen:
            return "Leerer Werkzeug-Block."
        name = zeilen[0].strip()
        parameter = {}
        for zeile in zeilen[1:]:
            if ":" in zeile:
                schluessel, wert = zeile.split(":", 1)
                parameter[schluessel.strip()] = wert.strip()
        print(f"\n   Werkzeug: {name}")
        for schluessel, wert in parameter.items():
            print(f"      {schluessel}: {wert[:200]}")
        if werkzeuge.ist_schreibend(name):
            print("   !! Dieses Werkzeug AENDERT etwas (z. B. Kalender, Einladungen).")
            if not ja("Wirklich ausfuehren?"):
                return "Der Nutzer hat diese Aenderung abgelehnt."
        elif name not in self.config.get("werkzeuge_ohne_nachfrage", []) and not ja("Ausfuehren?"):
            return "Der Nutzer hat dieses Werkzeug abgelehnt."
        ergebnis = werkzeuge.ausfuehren(name, parameter, self.config)
        print(f"   -> {len(ergebnis)} Zeichen Ergebnis")
        return ergebnis[:MAX_AUSGABE]

    def befehl_ausfuehren(self, befehl: str) -> str:
        print(f"\n   Befehl: {befehl}")
        if any(v.lower() in befehl.lower() for v in self.config.get("verbotene_befehle", [])):
            print("   -> Verboten (config.json: verbotene_befehle). Nicht ausgefuehrt.")
            return "Dieser Befehl ist verboten und wurde nicht ausgefuehrt."
        if not ja("Ausfuehren?"):
            return "Der Nutzer hat diesen Befehl abgelehnt."
        try:
            erg = subprocess.run(befehl, shell=True, cwd=self.arbeitsordner, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=120)
            ausgabe = f"Exit-Code {erg.returncode}\n" + ((erg.stdout + erg.stderr).strip() or "(keine Ausgabe)")
        except subprocess.TimeoutExpired:
            ausgabe = "Abgebrochen: dauerte laenger als 120 Sekunden."
        print("   " + ausgabe[:500].replace("\n", "\n   "))
        return ausgabe[:MAX_AUSGABE]

    def frage(self, wissen: str, text: str) -> None:
        for _ in range(MAX_RUNDEN):
            antwort = self.backend.senden(wissen, text)
            if not antwort:
                print("Keine Antwort erhalten.")
                return
            aufrufe = WERKZEUG_MUSTER.findall(antwort)
            befehle = BEFEHL_MUSTER.findall(antwort) if self.backend.mit_befehlen else []
            sichtbar = WERKZEUG_MUSTER.sub("[Werkzeug]", BEFEHL_MUSTER.sub("[Befehl]", antwort)).strip()
            print(f"\nAgent: {sichtbar}")
            if not aufrufe and not befehle:
                return
            ergebnisse = [f"Werkzeug:\n{a.strip()}\nErgebnis:\n{self.werkzeug_ausfuehren(a)}" for a in aufrufe]
            ergebnisse += [f"Befehl:\n{b.strip()}\nErgebnis:\n{self.befehl_ausfuehren(b.strip())}"
                           for b in befehle if b.strip()]
            text = "Ergebnisse deiner Aufrufe:\n\n" + "\n\n".join(ergebnisse)
        print(f"(Nach {MAX_RUNDEN} Runden gestoppt.)")


# ---------------------------------------------------------------- Start

def waehle_backend(config: dict, arbeitsordner: Path, basis: Path):
    modus = config.get("modus", "auto")
    programm = shutil.which(config["copilot_befehl"])
    if modus == "github" and not programm:
        sys.exit(f"'{config['copilot_befehl']}' nicht gefunden. GitHub-Copilot-CLI installieren "
                 "oder in config.json \"modus\": \"manuell\" setzen.")
    if modus in ("github", "auto") and programm:
        print("Modus: GitHub-Copilot-CLI (automatisch)")
        return GithubCopilot(config, programm, arbeitsordner, basis)
    print("Modus: Manuell (funktioniert mit jedem Copilot)")
    return ManuellerCopilot(config, arbeitsordner, basis)


def main() -> None:
    basis = basis_ordner()
    (basis / "wissen").mkdir(exist_ok=True)
    config = lade_config(basis)
    arbeitsordner = (basis / config["arbeitsordner"]).resolve()
    agent = Agent(waehle_backend(config, arbeitsordner, basis), config, arbeitsordner)

    print(f"Arbeitsordner: {arbeitsordner}")
    print(f"Werkzeuge: {', '.join(werkzeuge.WERKZEUGE)}")
    print("'exit' beendet, 'neu' startet ein neues Gespraech, 'merke: ...' speichert Wissen.")
    while True:
        try:
            frage = input("\nDu: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not frage:
            continue
        if frage.lower() in ("exit", "quit"):
            break
        if frage.lower() == "neu":
            agent.backend.neu()
            continue
        if frage.lower().startswith("merke:"):
            merke(basis, frage[len("merke:"):].strip())
            continue
        agent.frage(lade_wissen(basis), frage)   # Wissen jedes Mal neu laden


if __name__ == "__main__":
    main()
