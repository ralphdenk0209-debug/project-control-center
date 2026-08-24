/* ============================================================
   CONTROL API — Zugang zum Project Control Center
   ------------------------------------------------------------
   Einziger Weg der UI zur Projektwahrheit.

   HIER STEHT KEIN GEHEIMNIS.
   Weder ein Agent-Token noch ein Passwort. Beides wird eingegeben
   und bleibt ausschliesslich im Browser dieses Geraets.

   Zwei Anmeldewege:
     1. Anmeldung mit E-Mail und Passwort  (der normale Weg)
     2. Agent-Token                        (fuer Agenten und als Rueckfall)

   Diese Datei enthaelt KEINE Fachlogik. Sie schickt Anfragen,
   reicht Antworten und Fehler unveraendert weiter und entscheidet
   NICHT, ob eine Aktion erlaubt ist. Das macht der Server
   (Abschnitt 41).
   ============================================================ */

'use strict';

const ControlAPI = (function () {

  const BASIS     = 'https://haurbpfkfaaehorirzee.supabase.co';
  const ENDPOINT  = BASIS + '/functions/v1/project-control-agent';
  const AUTH_URL  = BASIS + '/auth/v1';
  const SPEICHER  = 'pcc_sitzung';

  /* Oeffentlicher Schluessel des Anmeldedienstes. Das ist KEIN Geheimnis:
     er steht in jeder Supabase-Anwendung im Browser und erlaubt fuer sich
     genommen keinen Zugriff auf Daten. Ohne ihn nimmt der Anmelde-Endpunkt
     die Anfrage gar nicht erst an. */
  const OEFFENTLICHER_SCHLUESSEL = 'sb_publishable_fssomLkMP88GLADjt8eaKQ_Gq6SN0-e';

  /* ---------- Sitzung: nur im Browser dieses Geraets ----------

     Zwei Ablagen, absichtlich:

     1. Arbeitsspeicher (SITZUNG) — gilt immer, solange die Seite offen ist.
     2. localStorage              — ueberlebt das Neuladen, aber NUR wenn der
                                    Browser ihn zulaesst.

     Warum doppelt: Wird die Seite per Doppelklick geoeffnet (file://), gilt
     sie als "Origin null". Browser behandeln localStorage dort unterschiedlich
     und verwerfen ihn teils sofort wieder. Genau daran ist die Anmeldung am
     24.08. verloren gegangen: angemeldet, ein Aufruf, wieder draussen.
     Ueber eine echte Adresse (https) faellt das weg.
     ------------------------------------------------------------------ */

  let SITZUNG = null;          /* Arbeitsspeicher — die verlaessliche Ablage */

  function speicherVerfuegbar() {
    try {
      const probe = '__pcc_probe__';
      localStorage.setItem(probe, '1');
      const gelesen = localStorage.getItem(probe);
      localStorage.removeItem(probe);
      return gelesen === '1';
    } catch (e) { return false; }
  }

  function sitzungLesen() {
    if (SITZUNG && SITZUNG.bearer) return SITZUNG;
    try {
      const roh = localStorage.getItem(SPEICHER);
      if (!roh) return null;
      SITZUNG = JSON.parse(roh);
      return SITZUNG;
    } catch (e) { return null; }
  }

  function sitzungSchreiben(s) {
    SITZUNG = s;                                   /* gilt in jedem Fall */
    try { localStorage.setItem(SPEICHER, JSON.stringify(s)); } catch (e) { /* dann eben nur im Speicher */ }
    return true;
  }

  function sitzungLoeschen() {
    SITZUNG = null;
    try { localStorage.removeItem(SPEICHER); } catch (e) { /* egal */ }
  }

  function angemeldet() {
    const s = sitzungLesen();
    return !!(s && s.bearer);
  }

  function wer() {
    const s = sitzungLesen();
    if (!s) return null;
    return { art: s.art, email: s.email || null, dauerhaft: speicherVerfuegbar() };
  }

  /* ---------- Anmelden mit E-Mail und Passwort ---------- */

  async function anmelden(email, passwort) {
    let res, body;
    try {
      res = await fetch(AUTH_URL + '/token?grant_type=password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'apikey': OEFFENTLICHER_SCHLUESSEL },
        body: JSON.stringify({ email: String(email || '').trim(), password: String(passwort || '') })
      });
      body = await res.json().catch(() => null);
    } catch (netErr) {
      return { ok: false, error_code: 'network',
               message: 'Der Anmeldedienst ist nicht erreichbar. Internetverbindung prüfen.', http: null };
    }

    if (!res.ok || !body || !body.access_token) {
      const code = (body && (body.error_code || body.error)) || ('http_' + res.status);
      return {
        ok: false, error_code: String(code), http: res.status,
        message: res.status === 400
          ? 'E-Mail oder Passwort stimmt nicht.'
          : (body && body.msg) || 'Anmeldung fehlgeschlagen.'
      };
    }

    sitzungSchreiben({
      art: 'login',
      bearer: body.access_token,
      erneuerung: body.refresh_token || null,
      laeuft_ab: Date.now() + (Number(body.expires_in || 3600) * 1000),
      email: (body.user && body.user.email) || String(email || '').trim()
    });
    return { ok: true, result: { email: (body.user && body.user.email) || email } };
  }

  /* Sitzung verlaengern. Der Server entscheidet, ob das geht. */
  async function erneuern() {
    const s = sitzungLesen();
    if (!s || s.art !== 'login' || !s.erneuerung) return false;
    try {
      const res = await fetch(AUTH_URL + '/token?grant_type=refresh_token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'apikey': OEFFENTLICHER_SCHLUESSEL },
        body: JSON.stringify({ refresh_token: s.erneuerung })
      });
      if (!res.ok) return false;
      const body = await res.json();
      if (!body || !body.access_token) return false;
      sitzungSchreiben({
        art: 'login',
        bearer: body.access_token,
        erneuerung: body.refresh_token || s.erneuerung,
        laeuft_ab: Date.now() + (Number(body.expires_in || 3600) * 1000),
        email: s.email
      });
      return true;
    } catch (e) { return false; }
  }

  /* ---------- Agent-Token als zweiter Weg ---------- */

  function tokenSetzen(wert) {
    const t = String(wert || '').trim();
    if (!t) return false;
    return sitzungSchreiben({ art: 'token', bearer: t, erneuerung: null, laeuft_ab: null, email: null });
  }

  /* ---------- Aufruf ---------- */

  /* Liefert immer:
       { ok: true,  result: <Serverantwort> }
       { ok: false, error_code, message, http }
     Wirft nicht. Der Aufrufer muss nichts abfangen. */
  async function call(action, payload, schonErneuert) {
    const s = sitzungLesen();
    if (!s || !s.bearer) {
      return { ok: false, error_code: 'nicht_angemeldet', message: 'Nicht angemeldet.', http: null };
    }

    /* Abgelaufene Anmeldung vorher erneuern, statt in einen 401 zu laufen. */
    if (s.art === 'login' && s.laeuft_ab && Date.now() > s.laeuft_ab - 30000 && !schonErneuert) {
      if (await erneuern()) return call(action, payload, true);
    }

    /* Nach einer moeglichen Erneuerung neu lesen — aber null-sicher.
       Vorher stand hier sitzungLesen().bearer; war die Sitzung zwischendurch
       weg, stuerzte der Aufruf mit einem TypeError ab, statt sauber zu melden. */
    const aktuell = sitzungLesen();
    if (!aktuell || !aktuell.bearer) {
      return { ok: false, error_code: 'nicht_angemeldet',
               message: 'Die Anmeldung ist verloren gegangen. Bitte neu anmelden.', http: null };
    }

    let res;
    try {
      res = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + aktuell.bearer },
        body: JSON.stringify(Object.assign({ action: action }, payload || {}))
      });
    } catch (netErr) {
      return { ok: false, error_code: 'network',
               message: 'Der Server ist nicht erreichbar. Internetverbindung prüfen.',
               detail: String(netErr && netErr.message || netErr), http: null };
    }

    let body = null;
    try { body = await res.json(); } catch (e) { body = null; }

    /* Einmalig erneuern, falls die Sitzung abgelaufen ist. */
    if (res.status === 401 && s.art === 'login' && !schonErneuert) {
      if (await erneuern()) return call(action, payload, true);
    }

    if (!res.ok || !body || body.ok !== true) {
      const code = (body && (body.error || body.error_code)) || ('http_' + res.status);
      return { ok: false, error_code: String(code), message: erklaeren(code, res.status, body),
               http: res.status, raw: body };
    }

    /* Manche RPCs melden ihre eigene Ablehnung im Ergebnis. */
    const r = body.result;
    if (r && typeof r === 'object' && r.ok === false) {
      const grund = String(r.reason || 'abgelehnt');
      return { ok: false, error_code: grund, message: erklaeren(grund, res.status, r),
               http: res.status, raw: r };
    }

    return { ok: true, result: r, project: body.project, agent: body.agent, via: body.via };
  }

  /* Uebersetzt Servercodes in Saetze. Reine Textzuordnung — keine Entscheidung.
     Unbekannte Codes werden unveraendert durchgereicht, nicht geraten. */
  const TEXTE = {
    nicht_angemeldet:            'Nicht angemeldet.',
    network:                     'Der Server ist nicht erreichbar.',
    'missing bearer token':      'Die Anmeldung fehlt in der Anfrage.',
    'invalid or expired token':  'Die Anmeldung ist abgelaufen oder ungültig. Bitte neu anmelden.',
    'scope denied':              'Diese Anmeldung darf diese Aktion nicht ausführen.',
    'unknown action':            'Diese Aktion kennt der Server nicht.',
    'control api failure':       'Im Server ist ein Fehler aufgetreten.',
    'work not found in project': 'Dieses Work Item gehört nicht zu diesem Projekt.',
    'lease not owned by agent':  'Der Lease gehört einem anderen Agenten.',
    project_or_agent_not_found:  'Projekt oder Agent wurde nicht gefunden.',
    work_not_open:               'Das Work Item ist nicht offen.',
    active_claim_required:       'Für diese Aktion muss das Work Item aktiv übernommen sein.',
    dependency_open:             'Eine Abhängigkeit ist noch nicht erfüllt.',
    owned_by_other_agent:        'Ein anderer Agent ist bereits zuständig.',
    resource_locked:             'Eine benötigte Ressource ist gesperrt.',
    invalid_lock:                'Die Lock-Angabe ist unvollständig.',
    invalid_lease_minutes:       'Die Lease-Dauer liegt außerhalb des erlaubten Bereichs.',
    work_claimed:                'Das Work Item ist aktiv übernommen — die Zuständigkeit kann nicht gewechselt werden.',
    work_leased:                 'Ein aktiver Lease verhindert den Wechsel der Zuständigkeit.'
  };

  function erklaeren(code, status, body) {
    const bekannt = TEXTE[code];
    if (bekannt) {
      const zusatz = [];
      if (body && body.resource_key)  zusatz.push(body.resource_key);
      if (body && body.resource_type) zusatz.push(body.resource_type);
      if (body && body.action)        zusatz.push('Aktion: ' + body.action);
      return bekannt + (zusatz.length ? ' (' + zusatz.join(', ') + ')' : '');
    }
    if (status === 401) return 'Nicht angemeldet oder Anmeldung abgelaufen.';
    if (status === 403) return 'Nicht erlaubt.';
    if (status === 404) return 'Nicht gefunden.';
    if (status >= 500)  return 'Serverfehler.';
    return 'Der Server hat abgelehnt: ' + code;
  }

  /* ---------- Was die UI kennt ---------- */

  return {
    endpoint:   ENDPOINT,
    angemeldet: angemeldet,
    wer:        wer,

    anmelden:   anmelden,
    abmelden:   sitzungLoeschen,
    tokenSetzen: tokenSetzen,

    bootstrap:  ()                  => call('bootstrap'),
    status:     ()                  => call('status'),
    getWork:    (id)                => call('get_work',    { work_id: Number(id) }),
    listLocks:  ()                  => call('list_locks'),
    nextWork:   ()                  => call('next_work'),
    assignWork: (id, ownerSlug)     => call('assign_work', { work_id: Number(id), owner_agent_slug: String(ownerSlug) }),
    resolveDecision: (id, wahl, warum) =>
      call('resolve_decision', { decision_id: Number(id), resolution: String(wahl), rationale: String(warum || '') }),

    /* Regelwerk. Lesen darf jeder, ändern nur wer den Scope hat —
       das entscheidet der Server, nicht diese Datei. */
    listRules:         ()               => call('list_rules'),
    listRuleTemplates: ()               => call('list_rule_templates'),
    applyStandardRules:()               => call('apply_standard_rules'),
    addRuleFromTemplate:(code)          => call('add_rule_from_template', { code: String(code) }),
    updateRule:        (code, aenderung)=> call('update_rule', Object.assign({ code: String(code) }, aenderung || {})),
    createRule:        (regel)          => call('create_rule', regel),

    raw: call
  };
})();
