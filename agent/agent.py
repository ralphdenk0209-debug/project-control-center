"""Standalone-Agent mit Wissensdatenbank, der Befehle ausfuehren kann.

Zwei Modi (config.json -> "modus"):
- "github":  nutzt die installierte GitHub-Copilot-CLI automatisch.
- "manuell": funktioniert mit JEDEM Copilot (Windows, Browser, Microsoft 365).
             Der Agent kopiert den Auftrag in die Zwischenablage, du fuegst ihn
             in Copilot ein und kopierst die Antwort zurueck.
- "auto":    GitHub-Copilot-CLI, wenn installiert, sonst "manuell".

Start: python agent.py   (oder die gebaute agent.exe)
"""

import json
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

AUFTRAG_DATEI = ".agent-auftrag.md"
MAX_VERLAUF = 3            # GitHub-Modus: so viele letzte Fragen/Antworten mitgeben
MAX_ZEICHEN = 2000         # Kuerzung alter Antworten
MAX_RUNDEN = 5             # Manuell-Modus: max. Befehlsrunden pro Frage
MAX_AUSGABE = 4000         # Kuerzung der Befehlsausgabe
IST_WINDOWS = platform.system() == "Windows"

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


def grundregeln() -> list[str]:
    return [
        "Du bist ein hilfreicher Agent. Antworte auf Deutsch, kurz und klar.",
        "Nutze die Wissensdatenbank unten. Wenn dort etwas fehlt, sag das ehrlich.",
    ]


# ---------------------------------------------------------------- Modus GitHub

class GithubCopilot:
    """Ruft die GitHub-Copilot-CLI auf. Copilot fuehrt erlaubte Befehle selbst aus."""

    def __init__(self, config: dict, programm: str, arbeitsordner: Path):
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

    def frage(self, wissen: str, frage: str) -> None:
        teile = ["# Auftrag fuer den Agenten", *grundregeln(),
                 "Du darfst Befehle ausfuehren, wenn sie fuer die Aufgabe noetig sind.",
                 "", "## Wissensdatenbank", wissen]
        if self.verlauf:
            teile += ["", "## Bisheriges Gespraech"]
            for f, a in self.verlauf[-MAX_VERLAUF:]:
                teile += [f"**Nutzer:** {f}", f"**Agent:** {a[:MAX_ZEICHEN]}", ""]
        teile += ["", "## Aktuelle Frage", frage]

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
        print(f"\nAgent: {antwort}")
        self.verlauf.append((frage, antwort))


# ---------------------------------------------------------------- Modus Manuell

class Zwischenablage:
    """Zwischenablage ueber tkinter (in Python enthalten). Faellt still weg, wenn nicht moeglich."""

    def __init__(self):
        self.tk = None
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
        if not self.tk:
            return ""
        try:
            return self.tk.clipboard_get()
        except Exception:
            return ""


class ManuellerCopilot:
    """Jeder Copilot: Auftrag per Zwischenablage hin, Antwort zurueck, Befehle nach Bestaetigung."""

    BEFEHL_MUSTER = re.compile(r"```befehl\s*\n(.*?)```", re.DOTALL)

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

    def anleitung(self, wissen: str) -> list[str]:
        shell = "Windows-Eingabeaufforderung (cmd)" if IST_WINDOWS else "bash"
        return [
            "# Auftrag fuer dich als Agent", *grundregeln(),
            "",
            "Du kannst Befehle auf meinem PC ausfuehren lassen "
            f"(System: {platform.system()}, Shell: {shell}, Ordner: {self.arbeitsordner}).",
            "Schreibe dazu jeden Befehl in einen eigenen Block, genau so:",
            "```befehl", "dir" if IST_WINDOWS else "ls", "```",
            "Ich fuehre ihn aus und schicke dir das Ergebnis. "
            "Schreibe keine Befehle in andere Bloecke. Ohne Befehl einfach normal antworten.",
            "", "## Wissensdatenbank", wissen,
        ]

    def senden(self, text: str) -> None:
        (self.basis / "copilot-auftrag.txt").write_text(text, encoding="utf-8")
        if not self.browser_offen and self.config.get("copilot_url"):
            webbrowser.open(self.config["copilot_url"])
            self.browser_offen = True
        if self.ablage.setzen(text):
            print("\n>> Auftrag ist in der Zwischenablage. In Copilot einfuegen (Strg+V) und absenden.")
        else:
            print(f"\n>> Auftrag steht in: {self.basis / 'copilot-auftrag.txt'}")
            print("   Inhalt kopieren, in Copilot einfuegen und absenden.")

    def antwort_holen(self) -> str:
        if self.ablage.geht:
            print(">> Antwort von Copilot kopieren und hier Enter druecken.")
            print("   (Oder Antwort hier einfuegen und mit einer Zeile ENDE abschliessen.)")
        else:
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

    def ist_verboten(self, befehl: str) -> bool:
        klein = befehl.lower()
        return any(v.lower() in klein for v in self.config.get("verbotene_befehle", []))

    def ausfuehren(self, befehl: str) -> str:
        if self.ist_verboten(befehl):
            print("   -> Verboten (config.json: verbotene_befehle). Nicht ausgefuehrt.")
            return "Dieser Befehl ist verboten und wurde nicht ausgefuehrt."
        try:
            ok = input("   Ausfuehren? (j/n): ").strip().lower() in ("j", "ja", "y")
        except EOFError:
            ok = False
        if not ok:
            return "Der Nutzer hat diesen Befehl abgelehnt."
        try:
            erg = subprocess.run(befehl, shell=True, cwd=self.arbeitsordner, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=120)
            ausgabe = (erg.stdout + erg.stderr).strip() or "(keine Ausgabe)"
            ausgabe = f"Exit-Code {erg.returncode}\n{ausgabe}"
        except subprocess.TimeoutExpired:
            ausgabe = "Abgebrochen: dauerte laenger als 120 Sekunden."
        print("   " + ausgabe[:500].replace("\n", "\n   "))
        return ausgabe[:MAX_AUSGABE]

    def frage(self, wissen: str, frage: str) -> None:
        if self.erste_nachricht:
            text = "\n".join(self.anleitung(wissen) + ["", "## Meine Frage", frage])
            self.erste_nachricht = False
        else:
            text = frage
        for _ in range(MAX_RUNDEN):
            self.senden(text)
            antwort = self.antwort_holen()
            if not antwort:
                print("Keine Antwort erhalten.")
                return
            befehle = [b.strip() for b in self.BEFEHL_MUSTER.findall(antwort) if b.strip()]
            print(f"\nAgent (Copilot): {self.BEFEHL_MUSTER.sub('[Befehl]', antwort).strip()}")
            if not befehle:
                return
            ergebnisse = []
            for befehl in befehle:
                print(f"\n   Befehl: {befehl}")
                ergebnisse.append(f"Befehl:\n{befehl}\nErgebnis:\n{self.ausfuehren(befehl)}")
            text = "Ergebnisse deiner Befehle:\n\n" + "\n\n".join(ergebnisse)
        print(f"(Nach {MAX_RUNDEN} Befehlsrunden gestoppt.)")


# ---------------------------------------------------------------- Start

def waehle_modus(config: dict, arbeitsordner: Path, basis: Path):
    modus = config.get("modus", "auto")
    programm = shutil.which(config["copilot_befehl"])
    if modus == "github" and not programm:
        sys.exit(f"'{config['copilot_befehl']}' nicht gefunden. GitHub-Copilot-CLI installieren "
                 "oder in config.json \"modus\": \"manuell\" setzen.")
    if modus in ("github", "auto") and programm:
        print("Modus: GitHub-Copilot-CLI (automatisch)")
        return GithubCopilot(config, programm, arbeitsordner)
    print("Modus: Manuell (funktioniert mit jedem Copilot)")
    return ManuellerCopilot(config, arbeitsordner, basis)


def main() -> None:
    basis = basis_ordner()
    (basis / "wissen").mkdir(exist_ok=True)
    config = lade_config(basis)
    arbeitsordner = (basis / config["arbeitsordner"]).resolve()
    agent = waehle_modus(config, arbeitsordner, basis)

    print(f"Arbeitsordner: {arbeitsordner}")
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
            agent.neu()
            continue
        if frage.lower().startswith("merke:"):
            merke(basis, frage[len("merke:"):].strip())
            continue
        agent.frage(lade_wissen(basis), frage)   # Wissen jedes Mal neu laden


if __name__ == "__main__":
    main()
