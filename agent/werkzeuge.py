"""Werkzeuge (Faehigkeiten) des Agenten.

Copilot ruft ein Werkzeug auf, indem er einen Block schreibt:

```werkzeug
mails_suchen
suche: Rechnung
tage: 14
```

Neues Werkzeug hinzufuegen: Funktion schreiben und mit @werkzeug(...) markieren.
"""

import mail

WERKZEUGE: dict = {}          # name -> (beschreibung, funktion)


def werkzeug(name: str, beschreibung: str):
    def markieren(funktion):
        WERKZEUGE[name] = (beschreibung, funktion)
        return funktion
    return markieren


def beschreibungen() -> str:
    return "\n".join(f"- {name}: {beschr}" for name, (beschr, _) in WERKZEUGE.items())


def ausfuehren(name: str, parameter: dict, config: dict) -> str:
    if name not in WERKZEUGE:
        return f"Unbekanntes Werkzeug '{name}'. Verfuegbar: {', '.join(WERKZEUGE)}"
    try:
        return WERKZEUGE[name][1](config, **parameter)
    except TypeError as fehler:
        return f"Falsche Parameter fuer {name}: {fehler}"
    except Exception as fehler:          # Fehler an Copilot melden statt abzustuerzen
        return f"Fehler in {name}: {type(fehler).__name__}: {fehler}"


# ---------------------------------------------------------------- E-Mail

@werkzeug("mails_suchen",
          "E-Mails suchen. Parameter: suche (Text, optional), von (Absender, optional), "
          "tage (Standard 7), ordner (Standard Posteingang), anzahl (Standard 20). "
          "Liefert ID, Datum, Absender, Betreff und eine Vorschau.")
def mails_suchen(config, suche="", von="", tage=7, ordner="Posteingang", anzahl=20):
    treffer = mail.postfach(config).suchen(suche.strip(), von.strip(), int(tage), ordner, int(anzahl))
    if not treffer:
        return "Keine passenden E-Mails gefunden."
    zeilen = [f"{len(treffer)} Treffer (neueste zuerst):"]
    for t in treffer:
        zeilen.append(f"\n[ID {t['id']}] {t['datum']}\nVon: {t['von']}\n"
                      f"Betreff: {t['betreff']}\nVorschau: {t['vorschau']}")
    return "\n".join(zeilen)


@werkzeug("mail_lesen",
          "Eine E-Mail komplett lesen. Parameter: id (aus mails_suchen), ordner (wie bei der Suche).")
def mail_lesen(config, id, ordner="Posteingang"):
    n = mail.postfach(config).lesen(id.strip(), ordner)
    return (f"Datum: {n['datum']}\nVon: {n['von']}\nAn: {n['an']}\nBetreff: {n['betreff']}\n"
            f"Anhaenge: {', '.join(n['anhaenge']) or 'keine'}\n\n{n['text'][:8000]}")


@werkzeug("mail_ordner", "Alle E-Mail-Ordner auflisten (z. B. Gesendet, Archiv). Keine Parameter.")
def mail_ordner(config):
    return "Ordner: " + ", ".join(mail.postfach(config).ordner_liste())
