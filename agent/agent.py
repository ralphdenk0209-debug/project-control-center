"""Standalone-Agent: nutzt die installierte GitHub-Copilot-CLI als Gehirn.

- Wissen:     alle .md/.txt-Dateien im Ordner "wissen" neben dem Programm
- Befehle:    Copilot fuehrt sie selbst aus; erlaubt ist nur, was in config.json steht
- Start:      python agent.py   (oder die gebaute agent.exe)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

AUFTRAG_DATEI = ".agent-auftrag.md"
MAX_VERLAUF = 3          # so viele letzte Fragen/Antworten werden mitgegeben
MAX_ZEICHEN = 2000       # pro alter Antwort (Kuerzung)

STANDARD_CONFIG = {
    "copilot_befehl": "copilot",
    "arbeitsordner": ".",
    "modell": None,
    "alles_erlauben": False,
    "erlaubte_tools": ["shell(git)"],
    "verbotene_tools": ["shell(git push)"],
    "extra_argumente": [],
}


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
    ordner = basis / "wissen"
    teile = []
    for datei in sorted(ordner.glob("*")):
        if datei.suffix.lower() in (".md", ".txt") and datei.is_file():
            teile.append(f"### {datei.name}\n{datei.read_text(encoding='utf-8', errors='replace')}")
    return "\n\n".join(teile) or "(Die Wissensdatenbank ist leer.)"


def copilot_argumente(config: dict) -> list[str]:
    programm = shutil.which(config["copilot_befehl"])
    if not programm:
        sys.exit(
            f"'{config['copilot_befehl']}' wurde nicht gefunden.\n"
            "Ist die GitHub-Copilot-CLI installiert und im PATH? "
            "Sonst in config.json bei copilot_befehl den vollen Pfad eintragen."
        )
    args = [programm]
    if config.get("modell"):
        args += ["--model", config["modell"]]
    if config.get("alles_erlauben"):
        args.append("--allow-all-tools")
    else:
        for tool in config.get("erlaubte_tools", []):
            args += ["--allow-tool", tool]
    for tool in config.get("verbotene_tools", []):
        args += ["--deny-tool", tool]
    args += config.get("extra_argumente", [])
    return args


def baue_auftrag(wissen: str, verlauf: list[tuple[str, str]], frage: str) -> str:
    teile = [
        "# Auftrag fuer den Agenten",
        "Du bist ein hilfreicher Agent. Antworte auf Deutsch, kurz und klar.",
        "Nutze die Wissensdatenbank unten. Wenn dort etwas fehlt, sag das ehrlich.",
        "Du darfst Befehle ausfuehren, wenn sie fuer die Aufgabe noetig sind.",
        "",
        "## Wissensdatenbank",
        wissen,
    ]
    if verlauf:
        teile += ["", "## Bisheriges Gespraech"]
        for f, a in verlauf[-MAX_VERLAUF:]:
            teile += [f"**Nutzer:** {f}", f"**Agent:** {a[:MAX_ZEICHEN]}", ""]
    teile += ["", "## Aktuelle Frage", frage]
    return "\n".join(teile)


def frage_copilot(args: list[str], arbeitsordner: Path, auftrag: str) -> str:
    # Der Auftrag kommt in eine Datei: so gibt es keine Probleme mit Laenge,
    # Zeilenumbruechen oder Sonderzeichen auf der Kommandozeile (v. a. Windows).
    datei = arbeitsordner / AUFTRAG_DATEI
    datei.write_text(auftrag, encoding="utf-8")
    kurz_prompt = (
        f"Lies die Datei {AUFTRAG_DATEI} in diesem Ordner vollstaendig "
        "und erledige den Auftrag darin. Gib nur deine Antwort an den Nutzer aus."
    )
    try:
        ergebnis = subprocess.run(
            args + ["-p", kurz_prompt],
            cwd=arbeitsordner,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        datei.unlink(missing_ok=True)
    if ergebnis.returncode != 0:
        return f"[Fehler von Copilot, Code {ergebnis.returncode}]\n{ergebnis.stderr.strip()}"
    return ergebnis.stdout.strip()


def main() -> None:
    basis = basis_ordner()
    (basis / "wissen").mkdir(exist_ok=True)
    config = lade_config(basis)
    arbeitsordner = (basis / config["arbeitsordner"]).resolve()
    args = copilot_argumente(config)

    print("Agent bereit (Copilot). 'exit' beendet, 'neu' leert den Verlauf.")
    print(f"Arbeitsordner: {arbeitsordner}")
    verlauf: list[tuple[str, str]] = []
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
            verlauf.clear()
            print("Verlauf geleert.")
            continue
        wissen = lade_wissen(basis)          # jedes Mal neu: Aenderungen wirken sofort
        antwort = frage_copilot(args, arbeitsordner, baue_auftrag(wissen, verlauf, frage))
        print(f"\nAgent: {antwort}")
        verlauf.append((frage, antwort))


if __name__ == "__main__":
    main()
