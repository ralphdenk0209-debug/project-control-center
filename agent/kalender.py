"""Kalender: lesen, setzen, verschieben, loeschen, absagen, planen, auswerten.

Zwei Wege (wie bei E-Mail):
- klassisches Outlook (COM, Windows)
- Microsoft 365 (Graph; Recht Calendars.ReadWrite noetig)

Alle Zeiten sind Ortszeit ohne Zeitzone (datetime ohne tzinfo).
"""

import datetime
import locale
import re

import mail

SLOT = 30   # Minuten je Frei/Belegt-Feld


# ---------------------------------------------------------------- Hilfen

def zeitpunkt(text: str) -> datetime.datetime:
    """Versteht 2026-11-10 14:00, 2026-11-10T14:00, 10.11.2026 14:00, 10.11.2026, 2026-11-10."""
    text = str(text).strip()
    for format in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                   "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, format)
        except ValueError:
            pass
    raise ValueError(f"Datum '{text}' nicht verstanden. Bitte als JJJJ-MM-TT HH:MM.")


def ja_nein(wert) -> bool:
    return str(wert).strip().lower() in ("ja", "j", "true", "1", "yes")


def zeitraum(von_datum, bis_datum, standard_tage=7):
    von = zeitpunkt(von_datum) if von_datum else datetime.datetime.combine(datetime.date.today(), datetime.time())
    bis = zeitpunkt(bis_datum) if bis_datum else von + datetime.timedelta(days=standard_tage)
    if bis.time() == datetime.time() and bis_datum and len(str(bis_datum).strip()) <= 10:
        bis += datetime.timedelta(days=1)          # "bis 30.11." heisst: einschliesslich 30.11.
    return von, bis


def dauer_text(minuten: float) -> str:
    stunden, rest = divmod(int(round(minuten)), 60)
    return f"{stunden} Std {rest:02d} Min"


def teilnehmer_liste(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"[;,\s]+", text or "") if "@" in t]


ANTWORT = {0: "keine Antwort", 1: "Organisator", 2: "vorlaeufig", 3: "zugesagt", 4: "abgesagt",
           5: "keine Antwort", "none": "keine Antwort", "organizer": "Organisator",
           "tentativelyAccepted": "vorlaeufig", "accepted": "zugesagt", "declined": "abgesagt",
           "notResponded": "keine Antwort"}


# ---------------------------------------------------------------- Outlook (COM)

class OutlookKalender:
    name = "Outlook (Programm)"

    def __init__(self, postfach):
        self.app, self.ns = postfach.app, postfach.ns

    @staticmethod
    def _zeit(z) -> datetime.datetime:
        return datetime.datetime(z.year, z.month, z.day, z.hour, z.minute)

    @staticmethod
    def _filterzeit(z: datetime.datetime, us: bool = False) -> str:
        if us:
            return z.strftime("%m/%d/%Y %I:%M %p")
        try:
            locale.setlocale(locale.LC_TIME, "")      # Outlook erwartet das Datumsformat von Windows
        except locale.Error:
            pass
        return z.strftime("%x %H:%M")

    def _id(self, item) -> str:
        # Einzeltermine einer Serie haben dieselbe EntryID -> Startzeit anhaengen
        if getattr(item, "RecurrenceState", 0) in (2, 3):
            return f"{item.EntryID}|{self._zeit(item.Start):%Y-%m-%d %H:%M}"
        return item.EntryID

    def _hole(self, id: str, ganze_serie: bool = False):
        eintrag, _, start = id.partition("|")
        item = self.ns.GetItemFromID(eintrag)
        if start and not ganze_serie:
            muster, ursprung = item.GetRecurrencePattern(), zeitpunkt(start)
            try:
                return muster.GetOccurrence(ursprung)
            except Exception:
                pass
            try:                                   # schon verschobener Einzeltermin (Ausnahme)
                for i in range(1, muster.Exceptions.Count + 1):
                    ausnahme = muster.Exceptions.Item(i)
                    if not ausnahme.Deleted and ursprung in (self._zeit(ausnahme.OriginalDate),
                                                             self._zeit(ausnahme.AppointmentItem.Start)):
                        return ausnahme.AppointmentItem
            except Exception:
                pass
            raise LookupError("Termin nicht gefunden (evtl. schon verschoben). "
                              "Bitte mit termine_anzeigen die aktuelle ID holen.")
        return item

    def _eintrag(self, item) -> dict:
        teilnehmer = []
        for i in range(1, item.Recipients.Count + 1):
            r = item.Recipients.Item(i)
            teilnehmer.append({"name": r.Name, "adresse": getattr(r, "Address", ""),
                               "art": {1: "erforderlich", 2: "optional", 3: "Raum"}.get(r.Type, ""),
                               "antwort": ANTWORT.get(r.MeetingResponseStatus, "")})
        return {"id": self._id(item), "betreff": item.Subject, "start": self._zeit(item.Start),
                "ende": self._zeit(item.End), "ort": item.Location or "", "organisator": item.Organizer,
                "serie": item.RecurrenceState in (1, 2, 3), "serien_schluessel": item.GlobalAppointmentID,
                "ich_organisiere": item.MeetingStatus in (0, 1), "frei": item.BusyStatus == 0,
                "teilnehmer": teilnehmer, "text": item.Body or ""}

    def termine(self, von, bis, suche="", max_anzahl=500):
        items = self.ns.GetDefaultFolder(9).Items          # 9 = Kalender
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        try:
            gefiltert = items.Restrict(f"[Start] < '{self._filterzeit(bis)}' AND [End] > '{self._filterzeit(von)}'")
        except Exception:
            gefiltert = items.Restrict(f"[Start] < '{self._filterzeit(bis, True)}' AND [End] > '{self._filterzeit(von, True)}'")
        ergebnis, item = [], gefiltert.GetFirst()
        while item is not None and len(ergebnis) < max_anzahl:
            if not suche or suche.lower() in (item.Subject or "").lower():
                ergebnis.append(self._eintrag(item))
            item = gefiltert.GetNext()
        return ergebnis

    def details(self, id):
        return self._eintrag(self._hole(id))

    def serie(self, id, von, bis):
        item = self._hole(id)
        schluessel = item.GlobalAppointmentID
        return [t for t in self.termine(von, bis) if t["serien_schluessel"] == schluessel]

    def erstellen(self, betreff, start, ende, teilnehmer, ort, text, teams):
        item = self.app.CreateItem(1)                      # 1 = Termin
        item.Subject, item.Start, item.End = betreff, start, ende
        item.Location, item.Body = ort, text
        if teilnehmer:
            item.MeetingStatus = 1                          # Besprechung
            for adresse in teilnehmer:
                item.Recipients.Add(adresse).Type = 1
            item.Recipients.ResolveAll()
            item.Send()
            hinweis = f"Einladung an {len(teilnehmer)} Teilnehmer gesendet."
        else:
            item.Save()
            hinweis = "Termin gespeichert."
        if teams:
            hinweis += " (Teams-Link bitte in Outlook hinzufuegen - geht ueber das Programm nicht automatisch.)"
        return hinweis

    def _absenden_oder_speichern(self, item) -> str:
        if item.MeetingStatus == 1 and item.Recipients.Count > 0:
            item.Send()
            return "Aenderung an Teilnehmer gesendet."
        item.Save()
        return "Gespeichert."

    def verschieben(self, id, start, ende, ganze_serie):
        item = self._hole(id, ganze_serie)
        if ganze_serie and item.RecurrenceState == 1:
            muster = item.GetRecurrencePattern()
            muster.StartTime, muster.EndTime = start, ende
        else:
            item.Start, item.End = start, ende
        return self._absenden_oder_speichern(item)

    def loeschen(self, id, ganze_serie):
        self._hole(id, ganze_serie).Delete()
        return "Geloescht."

    def absagen(self, id, nachricht, ganze_serie):
        item = self._hole(id, ganze_serie)
        if item.MeetingStatus == 1:                        # ich bin Organisator
            item.MeetingStatus = 5                         # abgesagt
            if nachricht:
                item.Body = f"{nachricht}\n\n{item.Body or ''}"
            item.Send()
            item.Delete()
            return "Besprechung abgesagt, Teilnehmer informiert."
        if item.MeetingStatus == 3:                        # ich bin eingeladen
            antwort = item.Respond(4, True)                # 4 = Absage
            if nachricht:
                antwort.Body = nachricht
            antwort.Send()
            return "Einladung abgelehnt, Organisator informiert."
        item.Delete()
        return "Termin (ohne Teilnehmer) geloescht."

    def antworten(self, id, art, nachricht):
        item = self._hole(id)
        antwort = item.Respond({"zusagen": 3, "vorlaeufig": 2, "absagen": 4}[art], True)
        if nachricht:
            antwort.Body = nachricht
        antwort.Send()
        return f"Antwort '{art}' gesendet."

    def belegt(self, adressen, start, tage):
        ergebnis = {}
        for adresse in adressen:
            r = self.ns.CreateRecipient(adresse)
            r.Resolve()
            ergebnis[adresse] = r.FreeBusy(start, SLOT, True)[: tage * 24 * 60 // SLOT]
        return ergebnis


# ---------------------------------------------------------------- Microsoft 365 (Graph)

class M365Kalender:
    name = "Microsoft 365"
    FELDER = ("id,subject,start,end,location,organizer,attendees,isOrganizer,type,"
              "seriesMasterId,showAs,bodyPreview,responseStatus")

    def __init__(self, postfach):
        self.p = postfach

    def _zeit(self, wert: dict) -> datetime.datetime:
        return datetime.datetime.fromisoformat(wert["dateTime"][:19])

    def _zeitfeld(self, z: datetime.datetime) -> dict:
        return {"dateTime": z.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": self.p.zeitzone}

    def _eintrag(self, e: dict) -> dict:
        teilnehmer = [{"name": a["emailAddress"].get("name", ""), "adresse": a["emailAddress"].get("address", ""),
                       "art": {"required": "erforderlich", "optional": "optional", "resource": "Raum"}.get(a.get("type"), ""),
                       "antwort": ANTWORT.get((a.get("status") or {}).get("response"), "")}
                      for a in e.get("attendees", [])]
        return {"id": e["id"], "betreff": e.get("subject", ""), "start": self._zeit(e["start"]),
                "ende": self._zeit(e["end"]), "ort": (e.get("location") or {}).get("displayName", ""),
                "organisator": ((e.get("organizer") or {}).get("emailAddress") or {}).get("name", ""),
                "serie": e.get("type") in ("occurrence", "exception", "seriesMaster"),
                "serien_schluessel": e.get("seriesMasterId") or e["id"],
                "ich_organisiere": e.get("isOrganizer", False), "frei": e.get("showAs") == "free",
                "teilnehmer": teilnehmer, "text": e.get("bodyPreview", "")}

    def _liste(self, pfad, von, bis, max_anzahl=500):
        parameter = {"startDateTime": von.strftime("%Y-%m-%dT%H:%M:%S"),
                     "endDateTime": bis.strftime("%Y-%m-%dT%H:%M:%S"),
                     "$select": self.FELDER, "$top": 100}
        daten, ergebnis = self.p._get(pfad, parameter), []
        while True:
            ergebnis += [self._eintrag(e) for e in daten.get("value", [])]
            weiter = daten.get("@odata.nextLink")
            if not weiter or len(ergebnis) >= max_anzahl:
                return sorted(ergebnis, key=lambda t: t["start"])[:max_anzahl]
            daten = self.p._get(weiter.replace(self.p.GRAPH, ""))

    def termine(self, von, bis, suche="", max_anzahl=500):
        liste = self._liste("/me/calendarView", von, bis, max_anzahl)
        return [t for t in liste if not suche or suche.lower() in t["betreff"].lower()]

    def details(self, id):
        return self._eintrag(self.p._get(f"/me/events/{id}", {"$select": self.FELDER}))

    def _master_id(self, id) -> str:
        e = self.p._get(f"/me/events/{id}", {"$select": "type,seriesMasterId"})
        return id if e.get("type") == "seriesMaster" else (e.get("seriesMasterId") or id)

    def serie(self, id, von, bis):
        return self._liste(f"/me/events/{self._master_id(id)}/instances", von, bis)

    def erstellen(self, betreff, start, ende, teilnehmer, ort, text, teams):
        daten = {"subject": betreff, "start": self._zeitfeld(start), "end": self._zeitfeld(ende),
                 "location": {"displayName": ort}, "body": {"contentType": "text", "content": text},
                 "attendees": [{"emailAddress": {"address": a}, "type": "required"} for a in teilnehmer]}
        if teams:
            daten.update({"isOnlineMeeting": True, "onlineMeetingProvider": "teamsForBusiness"})
        self.p._anfrage("POST", "/me/events", daten=daten)
        return (f"Einladung an {len(teilnehmer)} Teilnehmer gesendet." if teilnehmer else "Termin gespeichert.") + \
               (" Mit Teams-Link." if teams else "")

    def verschieben(self, id, start, ende, ganze_serie):
        ziel = self._master_id(id) if ganze_serie else id
        self.p._anfrage("PATCH", f"/me/events/{ziel}", daten={"start": self._zeitfeld(start), "end": self._zeitfeld(ende)})
        return "Verschoben (Teilnehmer werden automatisch informiert)."

    def loeschen(self, id, ganze_serie):
        self.p._anfrage("DELETE", f"/me/events/{self._master_id(id) if ganze_serie else id}")
        return "Geloescht."

    def absagen(self, id, nachricht, ganze_serie):
        ziel = self._master_id(id) if ganze_serie else id
        e = self.p._get(f"/me/events/{ziel}", {"$select": "isOrganizer,attendees"})
        if e.get("isOrganizer") and e.get("attendees"):
            self.p._anfrage("POST", f"/me/events/{ziel}/cancel", daten={"comment": nachricht})
            return "Besprechung abgesagt, Teilnehmer informiert."
        if not e.get("isOrganizer"):
            self.p._anfrage("POST", f"/me/events/{ziel}/decline", daten={"comment": nachricht, "sendResponse": True})
            return "Einladung abgelehnt, Organisator informiert."
        self.p._anfrage("DELETE", f"/me/events/{ziel}")
        return "Termin (ohne Teilnehmer) geloescht."

    def antworten(self, id, art, nachricht):
        aktion = {"zusagen": "accept", "vorlaeufig": "tentativelyAccept", "absagen": "decline"}[art]
        self.p._anfrage("POST", f"/me/events/{id}/{aktion}", daten={"comment": nachricht, "sendResponse": True})
        return f"Antwort '{art}' gesendet."

    def belegt(self, adressen, start, tage):
        daten = self.p._anfrage("POST", "/me/calendar/getSchedule", daten={
            "schedules": adressen, "startTime": self._zeitfeld(start),
            "endTime": self._zeitfeld(start + datetime.timedelta(days=tage)), "availabilityViewInterval": SLOT})
        return {s["scheduleId"]: s.get("availabilityView", "") for s in daten.get("value", [])}


# ---------------------------------------------------------------- Auswahl

_kalender = None


def kalender(config: dict):
    global _kalender
    if _kalender is None:
        p = mail.postfach(config)
        if isinstance(p, mail.OutlookPostfach):
            _kalender = OutlookKalender(p)
        elif isinstance(p, mail.M365Postfach):
            _kalender = M365Kalender(p)
        else:
            raise RuntimeError("Kalender geht nur mit Outlook oder Microsoft 365 (nicht mit IMAP).")
    return _kalender


def freie_zeiten(k, von, bis, dauer, teilnehmer, tag_start, tag_ende, anzahl=10):
    """Sucht gemeinsame freie Zeiten (werktags, innerhalb der Arbeitszeit)."""
    start0 = datetime.datetime.combine(von.date(), datetime.time())
    tage = max(1, (bis.date() - von.date()).days + 1)
    felder = tage * 24 * 60 // SLOT
    belegt = [False] * felder
    for t in k.termine(start0, start0 + datetime.timedelta(days=tage)):      # eigener Kalender
        if t["frei"]:
            continue
        a = max(0, int((t["start"] - start0).total_seconds() // 60 // SLOT))
        b = min(felder, int(-(-(t["ende"] - start0).total_seconds() // 60 // SLOT)))
        for i in range(a, b):
            belegt[i] = True
    if teilnehmer:                                                            # andere Personen
        for adresse, ansicht in k.belegt(teilnehmer, start0, tage).items():
            for i, zeichen in enumerate(ansicht[:felder]):
                if zeichen in "123":                                          # vorlaeufig/belegt/abwesend
                    belegt[i] = True
    noetig, frei = -(-int(dauer) // SLOT), []
    i = 0
    while i + noetig <= felder and len(frei) < anzahl:
        beginn = start0 + datetime.timedelta(minutes=i * SLOT)
        ende = beginn + datetime.timedelta(minutes=int(dauer))
        im_rahmen = (beginn >= von and ende <= bis and beginn.weekday() < 5
                     and beginn.hour >= tag_start and (ende.hour < tag_ende or (ende.hour == tag_ende and ende.minute == 0))
                     and ende.date() == beginn.date())
        if im_rahmen and not any(belegt[i:i + noetig]):
            frei.append((beginn, ende))
            i += noetig
        else:
            i += 1
    return frei
