"""Werkzeuge (Faehigkeiten) des Agenten.

Copilot ruft ein Werkzeug auf, indem er einen Block schreibt:

```werkzeug
mails_suchen
suche: Rechnung
tage: 14
```

Neues Werkzeug hinzufuegen: Funktion schreiben und mit @werkzeug(...) markieren.
"""

import collections
import datetime

import kalender as kal
import mail

WERKZEUGE: dict = {}          # name -> (beschreibung, funktion, schreibend)
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def werkzeug(name: str, beschreibung: str, schreibend: bool = False):
    """schreibend=True: aendert etwas -> der Agent fragt IMMER vorher nach."""
    def markieren(funktion):
        WERKZEUGE[name] = (beschreibung, funktion, schreibend)
        return funktion
    return markieren


def ist_schreibend(name: str) -> bool:
    return name in WERKZEUGE and WERKZEUGE[name][2]


def beschreibungen() -> str:
    return "\n".join(f"- {name}: {beschr}" for name, (beschr, _, _) in WERKZEUGE.items())


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


# ---------------------------------------------------------------- Kalender

def _zeile(t: dict) -> str:
    s, e = t["start"], t["ende"]
    zeit = f"{WOCHENTAGE[s.weekday()]} {s:%d.%m.%Y %H:%M}-{e:%H:%M}" if s.date() == e.date() \
        else f"{s:%d.%m.%Y %H:%M} bis {e:%d.%m.%Y %H:%M}"
    extra = [x for x in (t["ort"], "Serie" if t["serie"] else "",
                         f"{len(t['teilnehmer'])} Teilnehmer" if t["teilnehmer"] else "") if x]
    return f"[ID {t['id']}] {zeit} | {t['betreff']}" + (f" | {' | '.join(extra)}" if extra else "")


@werkzeug("termine_anzeigen",
          "Termine im Kalender auflisten (Serien sind aufgeloest). Parameter: von_datum, bis_datum "
          "(JJJJ-MM-TT, Standard: heute + 7 Tage), suche (Text im Betreff, optional).")
def termine_anzeigen(config, von_datum="", bis_datum="", suche=""):
    von, bis = kal.zeitraum(von_datum, bis_datum)
    liste = kal.kalender(config).termine(von, bis, suche.strip())
    if not liste:
        return f"Keine Termine zwischen {von:%d.%m.%Y} und {bis:%d.%m.%Y %H:%M}."
    return f"{len(liste)} Termine:\n" + "\n".join(_zeile(t) for t in liste)


@werkzeug("termin_details", "Alle Details eines Termins inkl. Teilnehmer und Antworten. Parameter: id.")
def termin_details(config, id):
    t = kal.kalender(config).details(id.strip())
    personen = "\n".join(f"  - {p['name']} <{p['adresse']}> ({p['art']}, {p['antwort']})" for p in t["teilnehmer"])
    return (f"{_zeile(t)}\nOrganisator: {t['organisator']} | Ich organisiere: "
            f"{'ja' if t['ich_organisiere'] else 'nein'}\nTeilnehmer:\n{personen or '  (keine)'}\n\n{t['text'][:3000]}")


@werkzeug("termin_erstellen",
          "Neuen Termin oder Besprechung anlegen. Parameter: betreff, start (JJJJ-MM-TT HH:MM), "
          "ende ODER dauer_minuten (Standard 60), teilnehmer (E-Mails mit ; getrennt -> Einladung wird "
          "gesendet), ort, text, teams (ja/nein).", schreibend=True)
def termin_erstellen(config, betreff, start, ende="", dauer_minuten="60", teilnehmer="", ort="", text="", teams="nein"):
    beginn = kal.zeitpunkt(start)
    schluss = kal.zeitpunkt(ende) if ende else beginn + datetime.timedelta(minutes=int(dauer_minuten))
    if schluss <= beginn:
        return "Fehler: Ende liegt vor dem Start."
    return kal.kalender(config).erstellen(betreff, beginn, schluss, kal.teilnehmer_liste(teilnehmer),
                                          ort, text, kal.ja_nein(teams))


@werkzeug("termin_verschieben",
          "Termin verschieben. Parameter: id, start (neu), ende (optional; sonst bleibt die Dauer), "
          "ganze_serie (ja/nein, Standard nein = nur dieser eine Termin).", schreibend=True)
def termin_verschieben(config, id, start, ende="", ganze_serie="nein"):
    k = kal.kalender(config)
    beginn = kal.zeitpunkt(start)
    if ende:
        schluss = kal.zeitpunkt(ende)
    else:
        alt = k.details(id.strip())
        schluss = beginn + (alt["ende"] - alt["start"])
    return k.verschieben(id.strip(), beginn, schluss, kal.ja_nein(ganze_serie))


@werkzeug("termin_loeschen",
          "Termin aus dem eigenen Kalender loeschen (ohne Nachricht an andere). Fuer Besprechungen "
          "besser termin_absagen. Parameter: id, ganze_serie (ja/nein).", schreibend=True)
def termin_loeschen(config, id, ganze_serie="nein"):
    return kal.kalender(config).loeschen(id.strip(), kal.ja_nein(ganze_serie))


@werkzeug("termin_absagen",
          "Termin absagen: als Organisator wird die Besprechung fuer alle abgesagt, als Teilnehmer wird "
          "die Einladung abgelehnt. Parameter: id, nachricht (optional), ganze_serie (ja/nein).", schreibend=True)
def termin_absagen(config, id, nachricht="", ganze_serie="nein"):
    return kal.kalender(config).absagen(id.strip(), nachricht, kal.ja_nein(ganze_serie))


@werkzeug("termin_antworten",
          "Auf eine Einladung antworten. Parameter: id, antwort (zusagen/vorlaeufig/absagen), nachricht (optional).",
          schreibend=True)
def termin_antworten(config, id, antwort, nachricht=""):
    antwort = antwort.strip().lower()
    if antwort not in ("zusagen", "vorlaeufig", "absagen"):
        return "antwort muss zusagen, vorlaeufig oder absagen sein."
    return kal.kalender(config).antworten(id.strip(), antwort, nachricht)


@werkzeug("freie_zeiten_finden",
          "Freie Zeiten fuer einen Termin finden, auch gemeinsam mit Kollegen (werktags). Parameter: "
          "dauer_minuten (Standard 60), von_datum, bis_datum (Standard: naechste 7 Tage), teilnehmer "
          "(E-Mails mit ;), tag_start (Std, Standard 8), tag_ende (Std, Standard 17).")
def freie_zeiten_finden(config, dauer_minuten="60", von_datum="", bis_datum="", teilnehmer="",
                        tag_start="8", tag_ende="17"):
    von, bis = kal.zeitraum(von_datum, bis_datum)
    von = max(von, datetime.datetime.now())
    frei = kal.freie_zeiten(kal.kalender(config), von, bis, int(dauer_minuten),
                            kal.teilnehmer_liste(teilnehmer), int(tag_start), int(tag_ende))
    if not frei:
        return "Keine gemeinsame freie Zeit gefunden. Tipp: Zeitraum vergroessern."
    return "Freie Zeiten:\n" + "\n".join(f"- {WOCHENTAGE[a.weekday()]} {a:%d.%m.%Y %H:%M}-{b:%H:%M}" for a, b in frei)


@werkzeug("termine_auswerten",
          "Termine zusammenzaehlen: Anzahl, Gesamtdauer und alle Teilnehmer. Entweder eine Serie "
          "(id eines Serientermins) oder alle Termine mit suche im Betreff. Parameter: id ODER suche, "
          "von_datum, bis_datum (Standard: dieses Jahr).")
def termine_auswerten(config, id="", suche="", von_datum="", bis_datum=""):
    if not id and not suche:
        return "Bitte id (Serie) oder suche (Betreff) angeben."
    jahr = datetime.date.today().year
    von, bis = kal.zeitraum(von_datum or f"{jahr}-01-01", bis_datum or f"{jahr}-12-31")
    k = kal.kalender(config)
    liste = k.serie(id.strip(), von, bis) if id else k.termine(von, bis, suche.strip())
    if not liste:
        return "Keine passenden Termine gefunden."
    minuten = sum((t["ende"] - t["start"]).total_seconds() / 60 for t in liste)
    personen, antworten = collections.Counter(), {}
    for t in liste:
        for p in t["teilnehmer"]:
            schluessel = p["adresse"] or p["name"]
            personen[schluessel] += 1
            antworten[schluessel] = (p["name"], p["antwort"])
    zeilen = [f"Auswertung {von:%d.%m.%Y} bis {bis - datetime.timedelta(minutes=1):%d.%m.%Y}:",
              f"Anzahl Termine: {len(liste)}", f"Gesamtdauer: {kal.dauer_text(minuten)}",
              f"Teilnehmer insgesamt: {len(personen)}"]
    for schluessel, anzahl in personen.most_common():
        name, antwort = antworten[schluessel]
        zeilen.append(f"  - {name} <{schluessel}>: in {anzahl} von {len(liste)} Terminen (zuletzt: {antwort})")
    zeilen.append("Termine:")
    zeilen += [f"  - {WOCHENTAGE[t['start'].weekday()]} {t['start']:%d.%m.%Y %H:%M}-{t['ende']:%H:%M} "
               f"({kal.dauer_text((t['ende'] - t['start']).total_seconds() / 60)}) {t['betreff']}" for t in liste]
    return "\n".join(zeilen)
