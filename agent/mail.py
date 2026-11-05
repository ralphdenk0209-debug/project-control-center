"""Zugriff auf E-Mails - nur lesend. Drei Wege:

- "outlook": klassisches Outlook-Programm auf Windows (kein Admin noetig, braucht pywin32)
- "m365":    Microsoft 365 ueber Microsoft Graph (neues Outlook / Web; App-Registrierung noetig)
- "imap":    andere Anbieter (Yahoo, Gmail, GMX ...)
- "auto":    Outlook, wenn vorhanden -> sonst M365, wenn eingerichtet -> sonst IMAP
"""

import datetime
import email
import getpass
import html
import imaplib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from email import policy
from pathlib import Path

ORDNER_NAMEN = {   # gaengige Namen -> (Outlook-Nummer, Graph-Name)
    "inbox": (6, "inbox"), "posteingang": (6, "inbox"),
    "sent": (5, "sentitems"), "gesendet": (5, "sentitems"), "gesendete elemente": (5, "sentitems"),
    "drafts": (16, "drafts"), "entwuerfe": (16, "drafts"), "entwürfe": (16, "drafts"),
    "junk": (23, "junkemail"), "spam": (23, "junkemail"), "junk-e-mail": (23, "junkemail"),
    "deleted": (3, "deleteditems"), "geloescht": (3, "deleteditems"), "gelöschte elemente": (3, "deleteditems"),
    "archiv": (None, "archive"), "archive": (None, "archive"),
}


def html_zu_text(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _stichtag(tage) -> datetime.datetime:
    return datetime.datetime.now() - datetime.timedelta(days=int(tage))


# ---------------------------------------------------------------- Klassisches Outlook (COM)

class OutlookPostfach:
    name = "Outlook (Programm)"
    MAX_DURCHSUCHT = 3000      # Schutz bei riesigen Ordnern

    def __init__(self, config: dict):
        try:
            import win32com.client   # nur auf Windows mit pywin32 vorhanden
            self.app = win32com.client.Dispatch("Outlook.Application")
            self.ns = self.app.GetNamespace("MAPI")
            self.ns.GetDefaultFolder(6)   # Test: wirft Fehler, wenn Outlook nicht nutzbar ist
        except Exception as fehler:
            raise RuntimeError("Klassisches Outlook nicht nutzbar (nur Windows mit installiertem "
                               f"Outlook-Programm; das neue Outlook geht so nicht). Details: {fehler}")

    def _ordner(self, ordner: str):
        bekannt = ORDNER_NAMEN.get(ordner.strip().lower())
        if bekannt and bekannt[0]:
            return self.ns.GetDefaultFolder(bekannt[0])

        def suche(ordnerliste):
            for o in ordnerliste:
                if o.Name.lower() == ordner.lower():
                    return o
                treffer = suche(o.Folders)
                if treffer:
                    return treffer
            return None
        gefunden = suche(self.ns.Folders)
        if not gefunden:
            raise LookupError(f"Ordner '{ordner}' nicht gefunden.")
        return gefunden

    @staticmethod
    def _zeit(item) -> datetime.datetime:
        # pywin32 liefert Ortszeit (teils faelschlich mit Zeitzone) -> ohne Zeitzone vergleichen
        z = item.ReceivedTime
        return datetime.datetime(z.year, z.month, z.day, z.hour, z.minute, z.second)

    @staticmethod
    def _wert(item, feld: str) -> str:
        try:
            return str(getattr(item, feld) or "")
        except Exception:
            return ""

    def suchen(self, suche, von, tage, ordner, anzahl):
        items = self._ordner(ordner).Items
        items.Sort("[ReceivedTime]", True)        # neueste zuerst
        grenze, treffer, gezaehlt = _stichtag(tage), [], 0
        suche_k, von_k = suche.lower(), von.lower()
        item = items.GetFirst()
        while item is not None and gezaehlt < self.MAX_DURCHSUCHT and len(treffer) < anzahl:
            gezaehlt += 1
            try:
                if self._zeit(item) < grenze:
                    break
            except Exception:
                item = items.GetNext()
                continue
            absender = f"{self._wert(item, 'SenderName')} <{self._wert(item, 'SenderEmailAddress')}>"
            betreff, text = self._wert(item, "Subject"), self._wert(item, "Body")
            if (not von_k or von_k in absender.lower()) and \
               (not suche_k or suche_k in f"{betreff}\n{text}\n{absender}".lower()):
                treffer.append({"id": self._wert(item, "EntryID"), "datum": str(self._zeit(item)),
                                "von": absender, "betreff": betreff,
                                "vorschau": re.sub(r"\s+", " ", text)[:300]})
            item = items.GetNext()
        return treffer

    def lesen(self, id, ordner):
        item = self.ns.GetItemFromID(id)
        anh = [item.Attachments.Item(i).FileName for i in range(1, item.Attachments.Count + 1)]
        return {"datum": str(self._zeit(item)),
                "von": f"{self._wert(item, 'SenderName')} <{self._wert(item, 'SenderEmailAddress')}>",
                "an": self._wert(item, "To"), "betreff": self._wert(item, "Subject"),
                "anhaenge": anh, "text": self._wert(item, "Body")}

    def ordner_liste(self):
        namen = []

        def sammeln(ordnerliste, tiefe):
            for o in ordnerliste:
                namen.append(o.Name)
                if tiefe < 2:
                    sammeln(o.Folders, tiefe + 1)
        sammeln(self.ns.Folders, 0)
        return namen


# ---------------------------------------------------------------- Microsoft 365 (Graph)

class M365Postfach:
    name = "Microsoft 365"
    GRAPH = "https://graph.microsoft.com/v1.0"
    SCOPE = "Mail.Read Calendars.ReadWrite User.Read offline_access"

    def __init__(self, config: dict):
        m = config.get("email", {})
        self.client_id = m.get("m365_client_id", "")
        self.tenant = m.get("m365_tenant") or "organizations"
        self.zeitzone = config.get("zeitzone") or "W. Europe Standard Time"
        if not self.client_id:
            raise RuntimeError("Microsoft 365 ist nicht eingerichtet (config.json -> email -> m365_client_id).")
        self.token_datei = Path.home() / ".copilot-agent" / "m365-token.json"
        self.token = None

    # --- Anmeldung (Geraetecode: Anmeldung im Browser, kein Passwort im Programm)
    def _post(self, pfad: str, daten: dict) -> dict:
        url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/{pfad}"
        anfrage = urllib.request.Request(url, data=urllib.parse.urlencode(daten).encode())
        try:
            with urllib.request.urlopen(anfrage, timeout=30) as antwort:
                return json.load(antwort)
        except urllib.error.HTTPError as fehler:
            return json.load(fehler)

    def _speichern(self, antwort: dict) -> None:
        self.token = antwort["access_token"]
        if antwort.get("refresh_token"):
            self.token_datei.parent.mkdir(parents=True, exist_ok=True)
            self.token_datei.write_text(json.dumps({"refresh_token": antwort["refresh_token"]}))

    def _anmelden(self) -> None:
        if self.token_datei.exists():
            alt = json.loads(self.token_datei.read_text())
            antwort = self._post("token", {"client_id": self.client_id, "grant_type": "refresh_token",
                                           "refresh_token": alt.get("refresh_token", ""), "scope": self.SCOPE})
            if "access_token" in antwort:
                return self._speichern(antwort)
        code = self._post("devicecode", {"client_id": self.client_id, "scope": self.SCOPE})
        if "device_code" not in code:
            raise RuntimeError(f"Anmeldung nicht moeglich: {code.get('error_description', code)}")
        print(f"\n   Microsoft-Anmeldung: Oeffne {code['verification_uri']} und gib den Code "
              f"{code['user_code']} ein.")
        webbrowser.open(code["verification_uri"])
        warte, ende = int(code.get("interval", 5)), time.time() + int(code.get("expires_in", 900))
        while time.time() < ende:
            time.sleep(warte)
            antwort = self._post("token", {"client_id": self.client_id, "device_code": code["device_code"],
                                           "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
            if "access_token" in antwort:
                print("   Angemeldet.")
                return self._speichern(antwort)
            if antwort.get("error") == "slow_down":
                warte += 5
            elif antwort.get("error") != "authorization_pending":
                raise RuntimeError(f"Anmeldung fehlgeschlagen: {antwort.get('error_description', antwort)}")
        raise RuntimeError("Anmeldung abgelaufen. Bitte nochmal versuchen.")

    def _anfrage(self, methode: str, pfad: str, parameter: dict | None = None,
                 daten: dict | None = None, erneut: bool = True) -> dict:
        if not self.token:
            self._anmelden()
        url = self.GRAPH + pfad + ("?" + urllib.parse.urlencode(parameter) if parameter else "")
        kopf = {"Authorization": f"Bearer {self.token}",
                "Prefer": f'outlook.body-content-type="text", outlook.timezone="{self.zeitzone}"'}
        inhalt = None
        if daten is not None:
            inhalt = json.dumps(daten).encode()
            kopf["Content-Type"] = "application/json"
        anfrage = urllib.request.Request(url, data=inhalt, headers=kopf, method=methode)
        try:
            with urllib.request.urlopen(anfrage, timeout=60) as antwort:
                roh = antwort.read()
                return json.loads(roh) if roh else {}
        except urllib.error.HTTPError as fehler:
            if fehler.code == 401 and erneut:           # Token abgelaufen -> neu anmelden
                self.token = None
                return self._anfrage(methode, pfad, parameter, daten, erneut=False)
            raise RuntimeError(f"Microsoft Graph Fehler {fehler.code}: {fehler.read()[:300]!r}")

    def _get(self, pfad: str, parameter: dict | None = None) -> dict:
        return self._anfrage("GET", pfad, parameter)

    @staticmethod
    def _ordner(ordner: str) -> str:
        bekannt = ORDNER_NAMEN.get(ordner.strip().lower())
        return bekannt[1] if bekannt else urllib.parse.quote(ordner)

    @staticmethod
    def _absender(nachricht: dict) -> str:
        a = (nachricht.get("from") or {}).get("emailAddress") or {}
        return f"{a.get('name', '')} <{a.get('address', '')}>"

    def suchen(self, suche, von, tage, ordner, anzahl):
        felder = "id,receivedDateTime,from,subject,bodyPreview"
        pfad = f"/me/mailFolders/{self._ordner(ordner)}/messages"
        grenze = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=int(tage))).strftime("%Y-%m-%dT%H:%M:%SZ")
        if suche or von:
            # $search laesst sich nicht mit $filter kombinieren -> Datum danach pruefen
            kql = " ".join(([f"from:{von}"] if von else []) + ([suche] if suche else []))
            daten = self._get(pfad, {"$search": f'"{kql}"', "$top": 50, "$select": felder})
            liste = [n for n in daten.get("value", []) if n.get("receivedDateTime", "") >= grenze]
            liste.sort(key=lambda n: n.get("receivedDateTime", ""), reverse=True)
        else:
            daten = self._get(pfad, {"$filter": f"receivedDateTime ge {grenze}",
                                     "$orderby": "receivedDateTime desc", "$top": anzahl, "$select": felder})
            liste = daten.get("value", [])
        return [{"id": n["id"], "datum": n.get("receivedDateTime", ""), "von": self._absender(n),
                 "betreff": n.get("subject", ""), "vorschau": n.get("bodyPreview", "")[:300]}
                for n in liste[:anzahl]]

    def lesen(self, id, ordner):
        n = self._get(f"/me/messages/{urllib.parse.quote(id)}",
                      {"$select": "subject,from,toRecipients,receivedDateTime,body,hasAttachments"})
        anh = []
        if n.get("hasAttachments"):
            anh = [a.get("name", "") for a in
                   self._get(f"/me/messages/{urllib.parse.quote(id)}/attachments", {"$select": "name"}).get("value", [])]
        text = (n.get("body") or {}).get("content", "")
        if (n.get("body") or {}).get("contentType") == "html":
            text = html_zu_text(text)
        an = ", ".join(r["emailAddress"].get("address", "") for r in n.get("toRecipients", []))
        return {"datum": n.get("receivedDateTime", ""), "von": self._absender(n), "an": an,
                "betreff": n.get("subject", ""), "anhaenge": anh, "text": text}

    def ordner_liste(self):
        return [o["displayName"] for o in
                self._get("/me/mailFolders", {"$top": 100, "$select": "displayName"}).get("value", [])]


# ---------------------------------------------------------------- IMAP (Yahoo, Gmail, GMX ...)

class ImapPostfach:
    name = "IMAP"
    _passwoerter: dict = {}

    def __init__(self, config: dict):
        self.m = config.get("email") or {}
        if not self.m.get("server") or not self.m.get("benutzer"):
            raise RuntimeError("IMAP ist nicht eingerichtet (config.json -> email: server, benutzer).")

    def _verbinden(self) -> imaplib.IMAP4_SSL:
        variable = self.m.get("passwort_umgebungsvariable", "AGENT_EMAIL_PASSWORT")
        passwort = os.environ.get(variable) or self._passwoerter.get(self.m["benutzer"])
        if not passwort:
            passwort = getpass.getpass(f"   App-Passwort fuer {self.m['benutzer']}: ")
            self._passwoerter[self.m["benutzer"]] = passwort      # nur fuer diese Sitzung
        imap = imaplib.IMAP4_SSL(self.m["server"], int(self.m.get("port", 993)))
        imap.login(self.m["benutzer"], passwort)
        return imap

    @staticmethod
    def _text(nachricht) -> str:
        teil = nachricht.get_body(preferencelist=("plain", "html"))
        if teil is None:
            return ""
        text = teil.get_content()
        return html_zu_text(text) if teil.get_content_type() == "text/html" else re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _imap_ordner(ordner: str) -> str:
        return "INBOX" if ORDNER_NAMEN.get(ordner.strip().lower(), (0,))[0] == 6 else ordner

    def _holen(self, imap, uid):
        status, teile = imap.uid("FETCH", uid, "(BODY.PEEK[])")      # PEEK: nicht als gelesen markieren
        if status != "OK" or not teile or not isinstance(teile[0], tuple):
            return None
        return email.message_from_bytes(teile[0][1], policy=policy.default)

    def suchen(self, suche, von, tage, ordner, anzahl):
        imap = self._verbinden()
        try:
            status, _ = imap.select(f'"{self._imap_ordner(ordner)}"', readonly=True)
            if status != "OK":
                raise LookupError(f"Ordner '{ordner}' nicht gefunden.")
            tag = _stichtag(tage)
            monate = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()   # IMAP will englische Namen
            kriterien = ["SINCE", f"{tag.day:02d}-{monate[tag.month - 1]}-{tag.year}"]
            if von:
                kriterien += ["FROM", f'"{von}"']
            if suche and not suche.isascii():                 # Umlaute: als UTF-8-Literal senden
                imap.literal = suche.encode("utf-8")
                status, daten = imap.uid("SEARCH", "CHARSET", "UTF-8", *kriterien, "TEXT")
            else:
                status, daten = imap.uid("SEARCH", *(kriterien + (["TEXT", f'"{suche}"'] if suche else [])))
            ids = daten[0].split() if status == "OK" and daten and daten[0] else []
            treffer = []
            for uid in reversed(ids[-anzahl:]):
                n = self._holen(imap, uid)
                if n is not None:
                    treffer.append({"id": uid.decode(), "datum": str(n["date"]), "von": str(n["from"]),
                                    "betreff": str(n["subject"]), "vorschau": self._text(n)[:300]})
            return treffer
        finally:
            imap.logout()

    def lesen(self, id, ordner):
        imap = self._verbinden()
        try:
            imap.select(f'"{self._imap_ordner(ordner)}"', readonly=True)
            n = self._holen(imap, str(id))
            if n is None:
                raise LookupError(f"E-Mail mit ID {id} nicht gefunden.")
            return {"datum": str(n["date"]), "von": str(n["from"]), "an": str(n["to"]),
                    "betreff": str(n["subject"]), "text": self._text(n),
                    "anhaenge": [a.get_filename() for a in n.iter_attachments() if a.get_filename()]}
        finally:
            imap.logout()

    def ordner_liste(self):
        imap = self._verbinden()
        try:
            _, liste = imap.list()
            namen = []
            for zeile in liste or []:
                text = zeile.decode(errors="replace")
                t = re.search(r'"([^"]*)"\s*$', text) or re.search(r"(\S+)\s*$", text)
                if t:
                    namen.append(t.group(1))
            return namen
        finally:
            imap.logout()


# ---------------------------------------------------------------- Auswahl

_postfach = None


def postfach(config: dict):
    """Liefert das passende Postfach (wird pro Sitzung einmal ermittelt)."""
    global _postfach
    if _postfach is not None:
        return _postfach
    typ = (config.get("email") or {}).get("typ", "auto")
    wege = {"outlook": OutlookPostfach, "m365": M365Postfach, "imap": ImapPostfach}
    if typ in wege:
        _postfach = wege[typ](config)
        return _postfach
    fehler = []
    for name in ("outlook", "m365", "imap"):
        try:
            _postfach = wege[name](config)
            print(f"   E-Mail ueber: {_postfach.name}")
            return _postfach
        except Exception as f:
            fehler.append(f"{name}: {f}")
    raise RuntimeError("Kein E-Mail-Zugang gefunden.\n" + "\n".join(fehler))
