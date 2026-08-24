/* ============================================================
   PROJECT CONTROL CENTER — Oberfläche
   ------------------------------------------------------------
   Diese Datei ist DARSTELLUNG. Sie besitzt keine fachliche
   Projektlogik und trifft keine Berechtigungsentscheidungen
   (Regel ARCH-02).

   Sie berechnet NICHT: Fortschritt, Benchmark, Jetzt, Danach,
   Blockiert, Agentenzustand, Locks, Build. Alles kommt fertig
   aus pcc_project_status (Regel ARCH-01).

   ZWEI ANSICHTEN, mehr nicht:
     Dashboard  — alles, was der Projektmanager sehen muss,
                  einschließlich Zuständigkeit und Entscheidungen
     Regelwerk  — die Regeln dieses Projekts

   Work-Liste, Abhängigkeitsgraph und eine eigene Entscheidungs-
   Ansicht gab es einmal. Sie sind entfernt: dieselben Work Items
   dreimal anders sortiert sind keine drei Ansichten, sondern eine.
   ============================================================ */

'use strict';

/* Build-Nummer dieser Auslieferung. Das Deploy-Skript liest sie und zieht
   damit die ?v=-Angaben in index.html sowie build.txt nach. Ohne sie liefert
   der Browser nach einem Deploy weiter die alten Dateien aus.
   Vor jedem Deploy hochzählen. */
const APP_BUILD = "2026-08-24-2130";

/* ---------- Zustand der Anzeige ---------- */

let MODE = 'live';        /* 'live' | 'demo' */
let STATUS = null;        /* Antwort von pcc_project_status */
let LOCKS = [];           /* Antwort von pcc_list_locks */
let WORKS = new Map();    /* work_id -> Kurzeintrag aus status */
let DETAILS = new Map();  /* work_id -> Antwort von pcc_get_work */
let AGENT_ORDER = [];     /* Reihenfolge der Agentenspalten */

const UNASSIGNED = '__none__';

/* ---------- Helfer ---------- */

const $ = (sel) => document.querySelector(sel);

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}
function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }
function emptyLi(text) { const li = el('li'); li.appendChild(el('span', 'empty', text)); return li; }

function shortTime(iso) {
  if (!iso) return '–';
  const d = new Date(iso);
  return isNaN(d) ? String(iso) : d.toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
}

/* Prioritätsband liefert der Server in get_work. In den Kurzlisten fehlt es;
   dort steht nur die Zahl. Die UI bildet keine eigenen Bandgrenzen (ARCH-04). */
function bandOf(workId) {
  const d = DETAILS.get(String(workId));
  return d && d.priority_band ? d.priority_band : null;
}

function agentName(slug) {
  if (!slug) return 'ohne Owner';
  const a = (STATUS.agents || {})[slug];
  return a && a.name ? a.name : slug;
}

/* ============================================================
   FEHLER — Serverantworten sichtbar machen
   ============================================================ */

function showError(res, was) {
  $('#err-title').textContent = was || 'Der Server hat abgelehnt';
  $('#err-msg').textContent = res && res.message ? res.message : 'Unbekannter Fehler.';
  /* HTTP-Status nur nennen, wenn er selbst den Fehler meldet. Eine fachliche
     Ablehnung kommt mit HTTP 200 — die Zahl würde einen technischen Fehler
     suggerieren, den es nicht gibt. */
  $('#err-code').textContent = res && res.error_code
    ? res.error_code + (res.http >= 400 ? ' · HTTP ' + res.http : '')
    : '';
  $('#errbar').hidden = false;
  console.warn('[control-center] Serverantwort:', res);
}
function hideError() { $('#errbar').hidden = true; }

/* ============================================================
   LADEN
   ============================================================ */

async function loadLive() {
  $('#loading').hidden = false;
  hideError();

  const st = await ControlAPI.status();
  if (!st.ok) {
    $('#loading').hidden = true;
    showError(st, 'Projektstand konnte nicht geladen werden');
    if (st.error_code === 'nicht_angemeldet' || st.http === 401) { zeigeAnmeldung(); showView('token'); }
    return false;
  }
  STATUS = st.result;

  const lk = await ControlAPI.listLocks();
  LOCKS = lk.ok && Array.isArray(lk.result) ? lk.result : [];
  if (!lk.ok) showError(lk, 'Locks konnten nicht geladen werden');

  indexWorks();
  MODE = 'live';
  renderAll();
  $('#loading').hidden = true;
  ladeRegeln();                 /* läuft nebenher, blockiert die Anzeige nicht */
  console.info('[control-center] LIVE:', WORKS.size, 'Work Items,',
    Object.keys(STATUS.agents || {}).length, 'Agenten,', LOCKS.length, 'Locks.');
  return true;
}

/* Demo ohne Anmeldung. Wird ins API-Format übersetzt, damit es nur EINEN
   Anzeigeweg gibt. Demo-Daten sind keine Projektwahrheit (Regel WAHRHEIT-05). */
function loadDemo() {
  const d = window.PROJECT_STATE;
  if (!d) { showError({ message: 'project-state.js fehlt.', error_code: 'no_demo' }); return false; }

  const byId = new Map((d.work_items || []).map((w) => [String(w.work_id), w]));
  const slug = (s) => s ? String(s).toLowerCase().replace(/\s+/g, '') : null;
  const kurz = (w) => ({ work_id: w.work_id, title: w.title, priority: w.priority,
                         owner: slug(w.owner), status: w.status });

  STATUS = {
    project: { slug: 'demo', name: d.project.name, status: 'active',
               health: d.project.health, goal: d.project.goal },
    progress: d.project_status.progress,
    benchmark: { current: d.project_status.benchmark, scale_max: 100 },
    now:     (d.project_status.now  || []).map((id) => kurz(byId.get(id))).filter(Boolean),
    next:    (d.project_status.next || []).map((id) => kurz(byId.get(id))).filter(Boolean),
    blocked: (d.project_status.blocked || []).map((id) => {
               const w = byId.get(id);
               return w ? { work_id: w.work_id, title: w.title, blocker: w.blocker } : null;
             }).filter(Boolean),
    decisions: (d.decisions || []).filter((x) => x.status === 'open').map((x) => ({
                 decision_id: x.decision_id, work_id: x.work_id, title: x.title,
                 question: x.question, recommendation: x.recommendation, options: x.options })),
    agents: Object.fromEntries((d.agents || []).map((a) =>
               [slug(a.name), { name: a.name, state: a.state, work_id: a.current_work }])),
    builds: {}, conflicts: []
  };

  LOCKS = (d.locks || []).map((l) => ({
    work_id: l.work_id, agent: slug(l.agent), agent_name: l.agent,
    resource_type: l.resource_type, resource_key: l.resource, expires_at: l.expires_at }));

  DETAILS = new Map((d.work_items || []).map((w) => [String(w.work_id), {
    work_id: w.work_id, title: w.title, goal: w.goal, description: w.description,
    status: w.status, priority: w.priority, priority_band: w.priority_band,
    owner: slug(w.owner), risk_level: w.risk_level, path: w.path_id,
    parent_work_id: w.parent_work_id, depends_on: w.depends_on, blocks: [],
    blocker_note: w.blocker, result_note: w.result,
    definition_of_done: w.definition_of_done, affected_systems: w.affected_systems,
    affected_resources: w.affected_resources, required_evidence: [],
    verification_required: false,
    evidence: (w.evidence || []).map((e) => ({ type: e.type, title: e.title, passed: e.passed }))
  }]));

  indexWorks();
  MODE = 'demo';
  renderAll();
  ladeRegeln();
  console.info('[control-center] DEMO (keine Projektwahrheit):', WORKS.size, 'Work Items.');
  return true;
}

/* Der Server liefert keine vollständige Work-Liste, sondern die drei Sichten
   now / next / blocked. Hier werden sie nur zusammengeführt — ohne Auswahl,
   ohne Bewertung, ohne Ergänzung. */
function indexWorks() {
  WORKS = new Map();
  const add = (w) => {
    if (!w || w.work_id == null) return;
    const id = String(w.work_id);
    WORKS.set(id, Object.assign({}, WORKS.get(id) || {}, w));
  };
  (STATUS.now     || []).forEach(add);
  (STATUS.next    || []).forEach(add);
  (STATUS.blocked || []).forEach((w) => add(Object.assign({ status: 'blocked' }, w)));
  AGENT_ORDER = Object.keys(STATUS.agents || {});
}

async function ensureDetail(workId) {
  const id = String(workId);
  if (DETAILS.has(id)) return DETAILS.get(id);
  if (MODE === 'demo') return null;
  const res = await ControlAPI.getWork(id);
  if (!res.ok) { showError(res, 'Work Item konnte nicht geladen werden'); return null; }
  DETAILS.set(id, res.result);
  return res.result;
}

function renderAll() {
  $('#src-badge').textContent = MODE === 'live' ? 'LIVE' : 'DEMO-DATEN';
  $('#src-badge').className = 'src ' + (MODE === 'live' ? 'src-live' : 'src-demo');
  document.title = (MODE === 'live' ? '' : 'DEMO · ') + 'Project Control Center';
  renderDashboard();
  renderBoard();
}

/* ============================================================
   DASHBOARD
   ============================================================ */

function renderDashboard() {
  const p = STATUS.project || {};
  $('#project-name').textContent = p.name || '–';
  $('#project-goal').textContent = p.goal || '(kein Ziel hinterlegt)';

  const h = $('#health');
  const map = { healthy: ['ok', 'SYSTEM HEALTHY'], warning: ['warn', 'SYSTEM WARNING'], critical: ['bad', 'SYSTEM CRITICAL'] };
  const hit = map[p.health] || (p.health ? ['warn', String(p.health).toUpperCase()] : ['warn', 'HEALTH NICHT GESETZT']);
  h.className = 'health ' + hit[0];
  h.textContent = hit[1];

  setBar('#bar-progress', '#val-progress', num(STATUS.progress));
  const b = STATUS.benchmark;
  const bVal = b && b.current != null ? Number(b.current) : null;
  const bMax = b && b.scale_max ? Number(b.scale_max) : 100;
  setBar('#bar-benchmark', '#val-benchmark',
         bVal == null ? null : (bVal / bMax) * 100,
         bVal == null ? 'nicht gemessen' : null);

  renderNow();
  renderNext();
  renderBlocked();
  renderEntscheidungen();
  renderAgents();
  renderLocks();
  renderBuild();
}

function num(v) { const n = Number(v); return isFinite(n) ? n : null; }

function setBar(barSel, valSel, pct, ersatzText) {
  $(barSel).style.width = (pct == null ? 0 : Math.max(0, Math.min(100, pct))) + '%';
  $(valSel).textContent = ersatzText ? ersatzText
    : (pct == null ? '–' : Math.round(pct * 10) / 10 + ' %');
}

function workButton(w, meta) {
  const btn = el('button', 'item');
  btn.type = 'button';
  btn.appendChild(el('span', 'item-id', '#' + w.work_id));
  btn.appendChild(el('span', 'item-title', w.title || '(ohne Titel)'));
  const band = bandOf(w.work_id);
  if (band) btn.appendChild(el('span', 'band band-' + band, band));
  else if (w.priority != null) btn.appendChild(el('span', 'item-meta', 'Prio ' + w.priority));
  if (meta) btn.appendChild(el('span', 'item-meta', meta));
  btn.addEventListener('click', () => openWork(w.work_id));
  return btn;
}

function renderNow() {
  const ul = $('#now-list'); clear(ul);
  const rows = STATUS.now || [];
  if (!rows.length) { ul.appendChild(emptyLi('Nichts läuft gerade.')); return; }
  rows.forEach((w) => { const li = el('li'); li.appendChild(workButton(w, agentName(w.owner))); ul.appendChild(li); });
}

function renderNext() {
  const ol = $('#next-list'); clear(ol);
  const rows = STATUS.next || [];
  if (!rows.length) { ol.appendChild(emptyLi('Nichts steht bereit.')); return; }
  rows.forEach((w, i) => { const li = el('li'); li.appendChild(workButton(w, (i + 1) + '.')); ol.appendChild(li); });
}

function renderBlocked() {
  const ul = $('#blocked-list'); clear(ul);
  const rows = STATUS.blocked || [];
  $('#blocked-count').textContent = rows.length;
  if (!rows.length) { ul.appendChild(emptyLi('Nichts blockiert.')); return; }
  rows.forEach((w) => {
    const li = el('li');
    li.appendChild(workButton(w));
    if (w.blocker) li.appendChild(el('div', 'item-sub', w.blocker));
    ul.appendChild(li);
  });
}

/* Entscheidungen stehen im Dashboard und werden dort aufgeklappt und
   getroffen. Eine eigene Ansicht dafür wäre ein zweiter Ort für dieselbe
   Sache. */
function renderEntscheidungen() {
  const ul = $('#decision-list'); clear(ul);
  const rows = STATUS.decisions || [];
  $('#decision-count').textContent = rows.length;
  if (!rows.length) { ul.appendChild(emptyLi('Keine offene Entscheidung.')); return; }

  rows.forEach((d) => {
    const li = el('li');

    const kopf = el('button', 'item');
    kopf.type = 'button';
    kopf.appendChild(el('span', 'item-id', 'DEC-' + d.decision_id));
    kopf.appendChild(el('span', 'item-title', d.title));
    kopf.appendChild(el('span', 'item-meta', 'öffnen'));
    li.appendChild(kopf);

    const feld = el('div', 'dec-inline');
    feld.hidden = true;

    if (d.question) feld.appendChild(el('p', 'dec-frage', d.question));

    let gewaehlt = null;
    const knoepfe = [];
    (d.options || []).forEach((o) => {
      const key   = (o && typeof o === 'object') ? String(o.key || '') : '';
      const label = (o && typeof o === 'object') ? String(o.label || '') : String(o);
      const b = el('button', 'opt');
      b.type = 'button';
      b.dataset.option = key;
      b.appendChild(el('span', 'opt-mark', '○'));
      b.appendChild(el('span', 'opt-text', key ? key + ' — ' + label : label));
      if (d.recommendation && key && String(d.recommendation).trim().startsWith(key)) {
        b.appendChild(el('span', 'opt-rec', 'EMPFOHLEN'));
      }
      if (MODE === 'live' && key) {
        b.addEventListener('click', () => {
          gewaehlt = key;
          knoepfe.forEach((x) => {
            const an = x.dataset.option === key;
            x.classList.toggle('is-chosen', an);
            x.querySelector('.opt-mark').textContent = an ? '●' : '○';
          });
        });
      } else { b.disabled = true; }
      knoepfe.push(b);
      feld.appendChild(b);
    });

    if (d.recommendation) feld.appendChild(el('div', 'dec-empfehlung', 'Empfehlung: ' + d.recommendation));

    if (MODE === 'live') {
      const ta = el('textarea', 'dec-inline-why');
      ta.placeholder = 'Begründung — sie wird mitgespeichert und später gelesen.';
      feld.appendChild(ta);

      const senden = el('button', 'btn-primary', 'Entscheidung festhalten');
      senden.addEventListener('click', async () => {
        if (!gewaehlt) {
          showError({ message: 'Bitte zuerst eine Option wählen.', error_code: 'keine_auswahl' }, 'Noch nichts gewählt');
          return;
        }
        senden.disabled = true;
        const res = await ControlAPI.resolveDecision(d.decision_id, gewaehlt, ta.value);
        senden.disabled = false;
        if (!res.ok) { showError(res, 'Entscheidung konnte nicht gespeichert werden'); return; }
        await loadLive();
      });
      feld.appendChild(senden);
    } else {
      feld.appendChild(el('div', 'empty', 'Entscheiden geht nur mit Anmeldung.'));
    }

    kopf.addEventListener('click', () => { feld.hidden = !feld.hidden; });
    li.appendChild(feld);
    ul.appendChild(li);
  });
}

function renderAgents() {
  const ul = $('#agent-list'); clear(ul);
  const agents = STATUS.agents || {};
  const slugs = Object.keys(agents);
  if (!slugs.length) { ul.appendChild(emptyLi('Keine Agenten.')); return; }
  slugs.forEach((slug) => {
    const a = agents[slug];
    const li = el('li');
    li.appendChild(el('span', 'agent-name', a.name || slug));
    li.appendChild(el('span', 'agent-state st-' + a.state, a.state));
    if (a.work_id != null) {
      const w = WORKS.get(String(a.work_id));
      li.appendChild(el('span', 'agent-work', '#' + a.work_id + (w ? ' · ' + w.title : '')));
    }
    ul.appendChild(li);
  });
}

function renderLocks() {
  const ul = $('#lock-list'); clear(ul);
  $('#lock-count').textContent = LOCKS.length;
  if (!LOCKS.length) { ul.appendChild(emptyLi('Keine aktiven Locks.')); return; }
  LOCKS.forEach((l) => {
    const li = el('li');
    li.appendChild(el('div', 'lock-res', l.resource_key || '–'));
    li.appendChild(el('div', 'lock-meta',
      (l.agent_name || l.agent || '?') + ' · #' + l.work_id + ' · ' + (l.resource_type || '?') +
      ' · läuft ab ' + shortTime(l.expires_at)));
    ul.appendChild(li);
  });
}

function renderBuild() {
  const grid = $('#build-grid'); clear(grid);
  const builds = STATUS.builds || {};
  const envs = Object.keys(builds);
  const drift = $('#build-drift');

  if (!envs.length) {
    grid.appendChild(el('div', 'empty', 'Noch kein Build-Stand gemeldet.'));
    drift.className = 'drift';
    drift.textContent = 'Ohne gemeldeten Build lässt sich kein Drift feststellen. Es wird nichts vermutet.';
    return;
  }
  envs.forEach((env) => {
    const b = builds[env] || {};
    const box = el('div');
    box.appendChild(el('span', 'build-label', env));
    box.appendChild(el('span', 'build-val', b.version != null ? b.version : '–'));
    if (b.measured_at) box.appendChild(el('span', 'build-when', shortTime(b.measured_at)));
    grid.appendChild(box);
  });
  /* Der Server meldet keinen Drift-Wert. Die UI leitet ihn NICHT ab (ARCH-01). */
  drift.className = 'drift';
  drift.textContent = 'Drift wird vom Server nicht gemeldet. Die Oberfläche leitet ihn nicht selbst ab.';
}

/* ============================================================
   ZUSTÄNDIGKEIT — steht im Dashboard
   ============================================================ */

function renderBoard() {
  const board = $('#board'); clear(board);
  const agents = STATUS.agents || {};
  AGENT_ORDER.forEach((slug) => board.appendChild(buildColumn(slug, agents[slug])));
  board.appendChild(buildColumn(UNASSIGNED, null));

  $('#board-mode').textContent = MODE === 'live'
    ? 'Karte auf eine andere Spalte ziehen, oder antippen und im Detail umstellen. Der Server entscheidet, ob es erlaubt ist.'
    : 'Demo-Ansicht: Verschieben ist abgeschaltet, weil kein Server da ist, der es entscheiden könnte.';
}

function buildColumn(slug, agent) {
  const col = el('div', 'column' + (slug === UNASSIGNED ? ' is-unassigned' : ''));
  col.dataset.owner = slug;

  const head = el('div', 'col-head');
  head.appendChild(el('span', 'col-name', slug === UNASSIGNED ? 'Nicht zugewiesen' : (agent && agent.name) || slug));
  if (agent) head.appendChild(el('span', 'agent-state st-' + agent.state, agent.state));

  const cards = [...WORKS.values()]
    .filter((w) => (w.owner || UNASSIGNED) === slug)
    .sort((a, b) => (b.priority || 0) - (a.priority || 0) || a.work_id - b.work_id);
  head.appendChild(el('span', 'col-count', cards.length));
  col.appendChild(head);

  if (!cards.length) {
    col.appendChild(el('div', 'col-empty', slug === UNASSIGNED ? 'Alles zugewiesen' : 'Keine Aufgabe'));
  } else {
    cards.forEach((w) => col.appendChild(buildCard(w)));
  }

  if (MODE === 'live') {
    col.addEventListener('dragover', (e) => { e.preventDefault(); col.classList.add('is-over'); });
    col.addEventListener('dragleave', () => col.classList.remove('is-over'));
    col.addEventListener('drop', (e) => {
      e.preventDefault();
      col.classList.remove('is-over');
      const id = e.dataTransfer.getData('text/plain');
      if (id) requestAssign(id, slug);
    });
  }
  return col;
}

function buildCard(w) {
  const band = bandOf(w.work_id);
  const card = el('div', 'card' + (band ? ' band-edge-' + band : ''));
  card.dataset.workId = w.work_id;
  card.draggable = MODE === 'live';

  const top = el('div', 'card-top');
  top.appendChild(el('span', 'card-id', '#' + w.work_id));
  if (band) top.appendChild(el('span', 'band band-' + band, band));
  else if (w.priority != null) top.appendChild(el('span', 'item-meta', 'Prio ' + w.priority));
  card.appendChild(top);

  card.appendChild(el('div', 'card-title', w.title || '(ohne Titel)'));

  const bottom = el('div', 'card-bottom');
  if (w.status) bottom.appendChild(el('span', 'status status-' + w.status, w.status));
  card.appendChild(bottom);

  if (w.blocker) card.appendChild(el('div', 'card-blocker', w.blocker));

  const lock = LOCKS.find((l) => String(l.work_id) === String(w.work_id));
  if (lock) card.appendChild(el('div', 'card-lock', 'Lock: ' + (lock.agent_name || lock.agent)));

  if (MODE === 'live') {
    card.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', String(w.work_id));
      e.dataTransfer.effectAllowed = 'move';
      card.classList.add('is-dragging');
    });
    card.addEventListener('dragend', () => card.classList.remove('is-dragging'));
  }
  card.addEventListener('click', () => openWork(w.work_id));
  return card;
}

/* Wunsch senden, Antwort zeigen. KEINE Vorabprüfung — nicht auf Lock,
   nicht auf Status, nicht auf Rechte (Regel ARCH-02). */
async function requestAssign(workId, ownerSlug) {
  if (MODE !== 'live') return;
  hideError();
  $('#loading').hidden = false;

  const res = await ControlAPI.assignWork(workId, ownerSlug === UNASSIGNED ? '' : ownerSlug);

  if (!res.ok) {
    /* Erst neu lesen, DANN die Ablehnung zeigen — sonst räumt loadLive()
       die Meldung sofort wieder weg. */
    await loadLive();
    $('#loading').hidden = true;
    showError(res, 'Zuständigkeit konnte nicht geändert werden');
    return;
  }
  DETAILS.delete(String(workId));
  await loadLive();
  console.info('[control-center] assign_work angenommen:', workId, '->', ownerSlug);
}

/* ============================================================
   REGELWERK
   ============================================================ */

let REGELN = [];
let KATALOG = [];
let REGELN_SCHREIBBAR = false;

async function ladeRegeln() {
  if (MODE !== 'live') { REGELN = []; REGELN_SCHREIBBAR = false; renderRegeln(); return; }

  const res = await ControlAPI.listRules();
  if (!res.ok) {
    REGELN = [];
    if (res.error_code !== 'scope denied') showError(res, 'Regelwerk konnte nicht geladen werden');
    renderRegeln();
    return;
  }
  REGELN = Array.isArray(res.result) ? res.result : [];

  /* Was erlaubt ist, sagt der Server in jeder Antwort mit. Es wird NICHT
     probeweise geschrieben, um das herauszufinden. */
  REGELN_SCHREIBBAR = ControlAPI.darf('update_rule');
  renderRegeln();
}

function renderRegeln() {
  const wrap = $('#regel-liste'); clear(wrap);
  $('#regel-nur-lesen').hidden = REGELN_SCHREIBBAR || MODE !== 'live';
  ['#regel-standard', '#regel-katalog-btn'].forEach((s) => { $(s).hidden = !REGELN_SCHREIBBAR; });

  const z = $('#regel-zahlen'); clear(z);
  if (MODE !== 'live') {
    z.appendChild(el('span', 'empty', 'Regeln gibt es nur mit Anmeldung — sie stehen im Server.'));
    return;
  }

  const aktiv = REGELN.filter((r) => r.active).length;
  const abw   = REGELN.filter((r) => r.abweichend).length;
  [[aktiv, 'aktiv'], [REGELN.length - aktiv, 'abgeschaltet'], [abw, 'angepasst']].forEach(([n, t]) => {
    const s = el('span', 'regel-zahl');
    s.appendChild(el('strong', null, n));
    s.appendChild(document.createTextNode(' ' + t));
    z.appendChild(s);
  });

  const suche   = $('#regel-suche').value.trim().toLowerCase();
  const nurAb   = $('#regel-nur-abweichend').checked;
  const auchAus = $('#regel-auch-inaktive').checked;

  const sichtbar = REGELN.filter((r) => {
    if (!auchAus && !r.active) return false;
    if (nurAb && !r.abweichend) return false;
    if (suche && !((r.code + ' ' + r.title + ' ' + (r.description || '')).toLowerCase().includes(suche))) return false;
    return true;
  });

  if (!sichtbar.length) {
    const p = el('div', 'panel');
    p.appendChild(el('div', 'empty', REGELN.length ? 'Keine Regel passt zu diesen Filtern.' : 'Noch kein Regelwerk. Standard-Set anwenden.'));
    wrap.appendChild(p);
    return;
  }

  const gruppen = new Map();
  sichtbar.forEach((r) => {
    const g = r.gruppe || 'Ohne Gruppe';
    if (!gruppen.has(g)) gruppen.set(g, []);
    gruppen.get(g).push(r);
  });

  gruppen.forEach((regeln, gruppe) => {
    const kasten = el('section', 'panel');
    const h = el('h2', null, gruppe);
    h.appendChild(el('span', 'count', regeln.length));
    kasten.appendChild(h);
    regeln.forEach((r) => kasten.appendChild(buildRegel(r)));
    wrap.appendChild(kasten);
  });
}

function buildRegel(r) {
  const box = el('div', 'regel' + (r.active ? '' : ' ist-aus') + (r.abweichend ? ' ist-abweichend' : ''));

  const kopf = el('div', 'regel-kopf');
  kopf.appendChild(el('span', 'regel-code', r.code));
  kopf.appendChild(el('span', 'schwere schwere-' + r.severity, r.severity));
  if (r.abweichend) kopf.appendChild(el('span', 'regel-flag', 'ANGEPASST'));
  if (!r.active)    kopf.appendChild(el('span', 'regel-flag regel-flag-aus', 'ABGESCHALTET'));
  box.appendChild(kopf);

  box.appendChild(el('div', 'regel-titel', r.title));
  if (r.description) box.appendChild(el('div', 'regel-text', r.description));
  if (r.begruendung) box.appendChild(el('div', 'regel-warum', 'Warum: ' + r.begruendung));

  if (!REGELN_SCHREIBBAR) return box;

  const werkzeuge = el('div', 'regel-aktionen');

  const schwere = el('select');
  schwere.setAttribute('aria-label', 'Schweregrad von ' + r.code);
  ['muss', 'soll', 'hinweis'].forEach((s) => { const o = el('option', null, s); o.value = s; schwere.appendChild(o); });
  schwere.value = r.severity;
  schwere.addEventListener('change', () => regelAendern(r.code, { severity: schwere.value }));
  werkzeuge.appendChild(schwere);

  const anAus = el('button', 'btn-reset', r.active ? 'Abschalten' : 'Einschalten');
  anAus.addEventListener('click', () => regelAendern(r.code, { active: !r.active }));
  werkzeuge.appendChild(anAus);

  const bearbeiten = el('button', 'btn-reset', 'Wortlaut ändern');
  bearbeiten.addEventListener('click', () => {
    if (box.querySelector('.regel-editor')) return;
    const ed = el('div', 'regel-editor');
    const ta = el('textarea');
    ta.value = r.description || '';
    ta.setAttribute('aria-label', 'Regeltext von ' + r.code);
    ed.appendChild(ta);
    const speichern = el('button', 'btn-primary', 'Speichern');
    speichern.addEventListener('click', () => regelAendern(r.code, { description: ta.value }));
    const abbrechen = el('button', 'btn-reset', 'Abbrechen');
    abbrechen.addEventListener('click', () => ed.remove());
    const leiste = el('div', 'regel-editor-fuss');
    leiste.appendChild(speichern); leiste.appendChild(abbrechen);
    ed.appendChild(leiste);
    box.appendChild(ed);
    ta.focus();
  });
  werkzeuge.appendChild(bearbeiten);

  box.appendChild(werkzeuge);
  return box;
}

async function regelAendern(code, aenderung) {
  hideError();
  const res = await ControlAPI.updateRule(code, aenderung);
  if (!res.ok) { showError(res, 'Regel konnte nicht geändert werden'); return; }
  const neu = await ControlAPI.listRules();
  if (neu.ok) REGELN = neu.result || [];
  renderRegeln();
  console.info('[control-center] Regel geändert:', code, aenderung);
}

async function zeigeKatalog() {
  const res = await ControlAPI.listRuleTemplates();
  if (!res.ok) { showError(res, 'Baukasten konnte nicht geladen werden'); return; }
  KATALOG = Array.isArray(res.result) ? res.result : [];

  const wrap = $('#katalog-liste'); clear(wrap);
  const vorhanden = new Set(REGELN.map((r) => r.code));

  const gruppen = new Map();
  KATALOG.forEach((t) => {
    if (!gruppen.has(t.gruppe)) gruppen.set(t.gruppe, []);
    gruppen.get(t.gruppe).push(t);
  });

  gruppen.forEach((bausteine, gruppe) => {
    const s = section(gruppe);
    bausteine.forEach((t) => {
      const zeile = el('div', 'baustein');
      const kopf = el('div', 'regel-kopf');
      kopf.appendChild(el('span', 'regel-code', t.code));
      kopf.appendChild(el('span', 'schwere schwere-' + t.severity, t.severity));
      if (!t.im_standard) kopf.appendChild(el('span', 'regel-flag', 'ZUSATZ'));
      zeile.appendChild(kopf);
      zeile.appendChild(el('div', 'regel-titel', t.title));
      zeile.appendChild(el('div', 'regel-text', t.description));

      if (vorhanden.has(t.code)) {
        zeile.appendChild(el('div', 'baustein-drin', 'Bereits im Regelwerk'));
      } else {
        const knopf = el('button', 'btn-reset', 'Zuschalten');
        knopf.addEventListener('click', async () => {
          knopf.disabled = true;
          const r = await ControlAPI.addRuleFromTemplate(t.code);
          if (!r.ok) { showError(r, 'Baustein konnte nicht zugeschaltet werden'); knopf.disabled = false; return; }
          const neu = await ControlAPI.listRules();
          if (neu.ok) REGELN = neu.result || [];
          renderRegeln();
          zeigeKatalog();
        });
        zeile.appendChild(knopf);
      }
      s.appendChild(zeile);
    });
    wrap.appendChild(s);
  });

  $('#katalog').hidden = false;
  document.body.style.overflow = 'hidden';
}

/* ============================================================
   WORK-DETAIL — kein Reiter, öffnet über Klick
   ============================================================ */

async function openWork(workId) {
  const body = $('#drawer-body');
  clear(body);
  body.appendChild(el('div', 'loading-inline', 'Lade #' + workId + ' …'));
  $('#overlay').hidden = false;
  document.body.style.overflow = 'hidden';

  const w = await ensureDetail(workId);
  clear(body);

  if (!w) {
    body.appendChild(el('h2', 'd-title', 'Work #' + workId));
    body.appendChild(el('p', 'empty', 'Detail konnte nicht geladen werden.'));
    return;
  }

  const head = el('div', 'd-head');
  head.appendChild(el('span', 'd-id', '#' + w.work_id));
  if (w.priority_band) head.appendChild(el('span', 'band band-' + w.priority_band, w.priority_band + ' · ' + w.priority));
  head.appendChild(el('span', 'status status-' + w.status, w.status));
  if (w.verification_required) head.appendChild(el('span', 'chip', 'Prüfung durch zweiten Agenten nötig'));
  body.appendChild(head);

  body.appendChild(el('h2', 'd-title', w.title));
  if (w.goal) body.appendChild(el('p', 'd-goal', w.goal));

  if (w.blocker_note) {
    const s = section('Blockiert durch');
    s.appendChild(el('div', 'd-blocker', w.blocker_note));
    body.appendChild(s);
  }

  const own = section('Zuständig');
  const pick = el('div', 'owner-pick');
  const sel = el('select');
  sel.setAttribute('aria-label', 'Zuständigen Agenten wählen');
  const on = el('option', null, 'nicht zugewiesen'); on.value = UNASSIGNED; sel.appendChild(on);
  AGENT_ORDER.forEach((slug) => { const o = el('option', null, agentName(slug)); o.value = slug; sel.appendChild(o); });
  sel.value = w.owner || UNASSIGNED;
  sel.disabled = MODE !== 'live';
  sel.addEventListener('change', async () => {
    const ziel = sel.value;
    closeDrawer();
    await requestAssign(w.work_id, ziel);
  });
  pick.appendChild(sel);
  if (MODE !== 'live') pick.appendChild(el('span', 'owner-warn', 'In der Demo-Ansicht nicht änderbar.'));
  own.appendChild(pick);
  body.appendChild(own);

  const facts = section('Einordnung');
  const grid = el('div', 'd-facts');
  [['Hauptpfad', w.path || '–'], ['Risiko', w.risk_level || '–'],
   ['Parent', w.parent_work_id != null ? '#' + w.parent_work_id : '–'],
   ['Projekt', w.project || '–']].forEach(([k, v]) => {
    const f = el('div', 'd-fact');
    f.appendChild(el('span', 'd-fact-k', k));
    f.appendChild(el('span', 'd-fact-v', v));
    grid.appendChild(f);
  });
  facts.appendChild(grid);
  body.appendChild(facts);

  if (w.description) { const s = section('Beschreibung'); s.appendChild(el('p', null, w.description)); body.appendChild(s); }

  const dodSec = section('Definition of Done');
  const dod = el('ul', 'd-dod' + (['done', 'verified'].includes(w.status) ? ' is-done' : ''));
  (w.definition_of_done || []).forEach((t) => dod.appendChild(el('li', null, t)));
  if (!(w.definition_of_done || []).length) dod.appendChild(el('li', 'empty', 'Nicht definiert.'));
  dodSec.appendChild(dod);
  body.appendChild(dodSec);

  body.appendChild(chips('Wartet auf', (w.depends_on || []).map((x) => '#' + x), 'Keine Abhängigkeiten.'));
  body.appendChild(chips('Blockiert', (w.blocks || []).map((x) => '#' + x), 'Blockiert nichts.'));
  body.appendChild(chips('Pflicht-Evidence', w.required_evidence, 'Keine gefordert.'));
  body.appendChild(chips('Betroffene Ressourcen', w.affected_resources, 'Keine benannt.'));

  const myLocks = LOCKS.filter((l) => String(l.work_id) === String(w.work_id));
  const ls = section('Locks');
  if (!myLocks.length) ls.appendChild(el('div', 'empty', 'Keine aktiven Locks.'));
  else myLocks.forEach((l) => {
    const d = el('div', 'd-ev');
    d.appendChild(el('span', 'd-ev-type', l.resource_type));
    d.appendChild(el('span', null, l.resource_key));
    d.appendChild(el('span', 'd-ev-type', (l.agent_name || l.agent) + ' · bis ' + shortTime(l.expires_at)));
    ls.appendChild(d);
  });
  body.appendChild(ls);

  const es = section('Evidence');
  const evs = w.evidence || [];
  if (!evs.length) es.appendChild(el('div', 'empty', 'Noch keine Evidence. Ohne Evidence kein "done".'));
  else evs.forEach((e) => {
    const d = el('div', 'd-ev');
    d.appendChild(el('span', 'd-ev-mark ' + (e.passed ? 'pass' : 'fail'), e.passed ? '✓' : '✗'));
    d.appendChild(el('span', 'd-ev-type', e.type));
    d.appendChild(el('span', null, e.title));
    es.appendChild(d);
  });
  body.appendChild(es);

  if (w.result_note) { const s = section('Ergebnis'); s.appendChild(el('p', null, w.result_note)); body.appendChild(s); }

  $('#drawer-close').focus();
}

function section(title) { const s = el('section', 'd-section'); s.appendChild(el('h3', null, title)); return s; }

function chips(title, values, leerText) {
  const s = section(title);
  if (!values || !values.length) { s.appendChild(el('div', 'empty', leerText)); return s; }
  const wrap = el('div', 'd-chips');
  values.forEach((v) => wrap.appendChild(el('span', 'chip', String(v))));
  s.appendChild(wrap);
  return s;
}

function schliesseKatalog() { $('#katalog').hidden = true; document.body.style.overflow = ''; }
function closeDrawer()      { $('#overlay').hidden = true; document.body.style.overflow = ''; }

/* ============================================================
   Ansichten und Bedienung
   ============================================================ */

/* Drei Ansichten: Zugang, Dashboard, Regelwerk. Zwei davon haben einen
   Reiter — der Zugang öffnet sich über das Zahnrad. */
const VIEWS = ['token', 'dashboard', 'rules'];

function showView(name) {
  VIEWS.forEach((v) => { const n = $('#view-' + v); if (n) n.hidden = v !== name; });
}

function activateTab(name) {
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('is-active', t.dataset.view === name));
  showView(name);
  document.documentElement.scrollTop = 0;
}

function wireUi() {
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => activateTab(tab.dataset.view));
  });

  $('#drawer-close').addEventListener('click', closeDrawer);
  $('#overlay').addEventListener('click', (e) => { if (e.target === $('#overlay')) closeDrawer(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeDrawer(); schliesseKatalog(); } });
  $('#err-close').addEventListener('click', hideError);
  $('#reload-btn').addEventListener('click', () => { if (MODE === 'live') loadLive(); else loadDemo(); });

  /* Regelwerk */
  ['#regel-suche', '#regel-nur-abweichend', '#regel-auch-inaktive'].forEach((sel) => {
    $(sel).addEventListener('input', renderRegeln);
  });
  $('#regel-standard').addEventListener('click', async () => {
    const res = await ControlAPI.applyStandardRules();
    if (!res.ok) { showError(res, 'Standard-Set konnte nicht angewendet werden'); return; }
    const neu = await ControlAPI.listRules();
    if (neu.ok) REGELN = neu.result || [];
    renderRegeln();
  });
  $('#regel-katalog-btn').addEventListener('click', zeigeKatalog);
  $('#katalog-close').addEventListener('click', schliesseKatalog);
  $('#katalog').addEventListener('click', (e) => { if (e.target === $('#katalog')) schliesseKatalog(); });

  /* Zugang */
  $('#token-btn').addEventListener('click', () => {
    $('#token-endpoint').textContent = ControlAPI.endpoint;
    zeigeAnmeldung();
    showView('token');
  });

  $('#login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const mail = $('#login-mail').value.trim();
    const pw = $('#login-pw').value;
    if (!mail || !pw) return;

    const btn = $('#login-btn');
    btn.disabled = true; btn.textContent = 'Melde an …';
    const res = await ControlAPI.anmelden(mail, pw);
    btn.disabled = false; btn.textContent = 'Anmelden';
    $('#login-pw').value = '';                 /* Passwort nicht stehen lassen */

    if (!res.ok) { showError(res, 'Anmeldung fehlgeschlagen'); return; }
    hideError();
    zeigeAnmeldung();
    activateTab('dashboard');
    await loadLive();
  });

  $('#logout-btn').addEventListener('click', () => {
    ControlAPI.abmelden();
    zeigeAnmeldung();
    loadDemo();
    showView('token');
  });

  $('#token-save').addEventListener('click', async () => {
    const v = $('#token-input').value.trim();
    if (!v) return;
    ControlAPI.tokenSetzen(v);
    $('#token-input').value = '';
    zeigeAnmeldung();
    activateTab('dashboard');
    await loadLive();
  });

  $('#token-demo').addEventListener('click', () => { activateTab('dashboard'); loadDemo(); });
}

function zeigeAnmeldung() {
  const box = $('#angemeldet-als');
  const w = ControlAPI.wer();
  if (!w) { box.hidden = true; return; }
  box.hidden = false;
  clear(box);
  box.appendChild(el('span', 'angemeldet-punkt', '●'));
  box.appendChild(el('span', null, w.art === 'login'
    ? 'Angemeldet als ' + (w.email || 'unbekannt')
    : 'Angemeldet über Agent-Token'));

  /* Ehrlich sagen, wenn die Anmeldung das Neuladen nicht überlebt. */
  if (!w.dauerhaft) {
    box.appendChild(el('span', 'angemeldet-warn',
      '— nur bis zum Neuladen. Dieser Browser speichert für lokal geöffnete Dateien nichts.'));
  }
}

async function boot() {
  wireUi();
  $('#token-endpoint').textContent = ControlAPI.endpoint;
  zeigeAnmeldung();

  const bn = $('#build-nr');
  if (bn) bn.textContent = APP_BUILD;
  console.info('[control-center] Build', APP_BUILD);

  if (ControlAPI.angemeldet()) {
    /* Das Dashboard steht im HTML auf "versteckt" — ohne diesen Aufruf
       bliebe die Seite nach der Anmeldung leer. */
    activateTab('dashboard');
    const ok = await loadLive();
    if (!ok && !STATUS) loadDemo();
    return;
  }
  loadDemo();
  showView('token');
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
