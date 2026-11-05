"""Werkzeuge (Faehigkeiten) des Agenten.

Copilot ruft ein Werkzeug auf, indem er einen Block schreibt:

```werkzeug
mails_suchen
suche: Rechnung
tage: 14
```

Neues Werkzeug hinzufuegen: Funktion schreiben und mit @werkzeug(...) markieren.
"""

import datetime
import email
import getpass
import html
import imaplib
import os
import re
from email import policy

WERKZEUGE: dict = {}          # name -> (beschreibung, funktion)
_passwort_cache: dict = {}


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


# ---------------------------------------------------------------- E-Mail (IMAP)

def _verbinden(config: dict) -> imaplib.IMAP4_SSL:
    mail = config.get("email") or {}
    if not mail.get("server") or not mail.get("benutzer"):
        raise RuntimeError("E-Mail ist nicht eingerichtet (config.json -> email: server, benutzer).")
    variable = mail.get("passwort_umgebungsvariable", "AGENT_EMAIL_PASSWORT")
    passwort = os.environ.get(variable) or _passwort_cache.get(mail["benutzer"])
    if not passwort:
        passwort = getpass.getpass(f"   App-Passwort fuer {mail['benutzer']}: ")
        _passwort_cache[mail["benutzer"]] = passwort      # nur fuer diese Sitzung
    imap = imaplib.IMAP4_SSL(mail["server"], int(mail.get("port", 993)))
    imap.login(mail["benutzer"], passwort)
    return imap


def _text_aus_mail(nachricht) -> str:
    teil = nachricht.get_body(preferencelist=("plain", "html"))
    if teil is None:
        return ""
    text = teil.get_content()
    if teil.get_content_type() == "text/html":
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _suchkriterien(imap, suche: str, von: str, tage: int):
    tag = datetime.date.today() - datetime.timedelta(days=int(tage))
    monate = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()   # IMAP will englische Namen
    seit = f"{tag.day:02d}-{monate[tag.month - 1]}-{tag.year}"
    kriterien = ["SINCE", seit]
    if von:
        kriterien += ["FROM", f'"{von}"']
    if suche:
        if suche.isascii():
            kriterien += ["TEXT", f'"{suche}"']
        else:                                  # Umlaute: als UTF-8-Literal senden
            imap.literal = suche.encode("utf-8")
            return imap.uid("SEARCH", "CHARSET", "UTF-8", *kriterien, "TEXT")
    return imap.uid("SEARCH", *kriterien)


@werkzeug("mails_suchen",
          "E-Mails suchen. Parameter: suche (Text, optional), von (Absender, optional), "
          "tage (Standard 7), ordner (Standard INBOX), anzahl (Standard 20). "
          "Liefert ID, Datum, Absender, Betreff und eine Vorschau.")
def mails_suchen(config, suche="", von="", tage=7, ordner="INBOX", anzahl=20):
    imap = _verbinden(config)
    try:
        status, _ = imap.select(f'"{ordner}"', readonly=True)   # readonly: nichts wird als gelesen markiert
        if status != "OK":
            return f"Ordner '{ordner}' nicht gefunden. Tipp: Werkzeug mail_ordner nutzen."
        status, daten = _suchkriterien(imap, suche, von, tage)
        ids = daten[0].split() if status == "OK" and daten and daten[0] else []
        if not ids:
            return "Keine passenden E-Mails gefunden."
        zeilen = [f"{len(ids)} Treffer, die neuesten {min(len(ids), int(anzahl))}:"]
        for uid in reversed(ids[-int(anzahl):]):
            status, teile = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if status != "OK" or not teile or not isinstance(teile[0], tuple):
                continue
            nachricht = email.message_from_bytes(teile[0][1], policy=policy.default)
            vorschau = _text_aus_mail(nachricht)[:300]
            zeilen.append(f"\n[ID {uid.decode()}] {nachricht['date']}\n"
                          f"Von: {nachricht['from']}\nBetreff: {nachricht['subject']}\n"
                          f"Vorschau: {vorschau}")
        return "\n".join(zeilen)
    finally:
        imap.logout()


@werkzeug("mail_lesen",
          "Eine E-Mail komplett lesen. Parameter: id (aus mails_suchen), ordner (Standard INBOX).")
def mail_lesen(config, id, ordner="INBOX"):
    imap = _verbinden(config)
    try:
        imap.select(f'"{ordner}"', readonly=True)
        status, teile = imap.uid("FETCH", str(id), "(BODY.PEEK[])")
        if status != "OK" or not teile or not isinstance(teile[0], tuple):
            return f"E-Mail mit ID {id} nicht gefunden."
        n = email.message_from_bytes(teile[0][1], policy=policy.default)
        anhaenge = [a.get_filename() for a in n.iter_attachments() if a.get_filename()]
        return (f"Datum: {n['date']}\nVon: {n['from']}\nAn: {n['to']}\nBetreff: {n['subject']}\n"
                f"Anhaenge: {', '.join(anhaenge) or 'keine'}\n\n{_text_aus_mail(n)[:8000]}")
    finally:
        imap.logout()


@werkzeug("mail_ordner", "Alle E-Mail-Ordner auflisten (z. B. Gesendet, Spam). Keine Parameter.")
def mail_ordner(config):
    imap = _verbinden(config)
    try:
        status, liste = imap.list()
        namen = []
        for zeile in liste or []:
            text = zeile.decode(errors="replace")
            treffer = re.search(r'"([^"]*)"\s*$', text) or re.search(r"(\S+)\s*$", text)
            if treffer:
                namen.append(treffer.group(1))
        return "Ordner: " + ", ".join(namen)
    finally:
        imap.logout()
