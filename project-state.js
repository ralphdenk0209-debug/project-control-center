/* ============================================================
   PROJECT CONTROL CENTER — DATENQUELLE DES PROTOTYPS
   ------------------------------------------------------------
   Dies ist die EINZIGE Quelle aller sichtbaren Werte (Abschnitt 35).
   Wer Demo-Daten ändern will, ändert nur diese Datei.
   Kein Wert gehört fest in index.html oder app.js.

   Warum .js und nicht .json:
   Browser blockieren fetch() bei file://. Als Script geladen
   braucht der Prototyp keinen HTTP-Server und startet per
   Doppelklick. Ab Stufe 2 ersetzt project_status() der Control
   API diese Datei vollständig.

   DEMO-DATEN. Frei erfunden. KEIN realer Projektstand.
   ============================================================ */

window.PROJECT_STATE =
{
  "_meta": {
    "demo": true,
    "note": "DEMO-DATEN. capabilities und required_capability sind ebenfalls erfunden und dienen nur dazu, die Faehigkeitspruefung aus Abschnitt 11 sichtbar zu machen. Frei erfunden, nur zur Prüfung des Bedienkonzepts in Stufe 1. Enthält KEINEN realen Projektstand. Alle abgeleiteten Werte (progress, benchmark, blocked_by, priority_band, agent state, build drift, conflicts) sind hier so abgelegt, wie sie später von project_status() serverseitig geliefert werden. Das Frontend berechnet sie NICHT.",
    "schema_version": "0.1",
    "generated_for": "10_UI_PROTOTYPE"
  },
  "project": {
    "project_id": "PRJ-DEMO-1",
    "name": "Example Project",
    "goal": "Agent coordination production-ready",
    "health": "healthy",
    "rule_version": 3
  },
  "project_status": {
    "progress": 78,
    "benchmark": 71,
    "benchmark_basis": "Demo-Wert. Messgrundlage in Stufe 2 über benchmark_snapshot.",
    "now": [
      "W-228",
      "W-227"
    ],
    "next": [
      "W-222",
      "W-225",
      "W-223"
    ],
    "blocked": [
      "W-223"
    ],
    "decisions_open": 2,
    "conflicts": [],
    "build_drift": true
  },
  "build_state": {
    "repo": 4385,
    "build": 4385,
    "live": 4382,
    "drift": true,
    "drift_reason": "Live liegt 3 Builds hinter dem Repo-Stand.",
    "measured_at": "2026-08-23T09:12:00Z"
  },
  "main_paths": [
    {
      "path_id": "P1",
      "code": "P1",
      "title": "Control Core",
      "priority": 95,
      "priority_band": "P0",
      "status": "active",
      "sort_order": 1
    },
    {
      "path_id": "P2",
      "code": "P2",
      "title": "Dashboard",
      "priority": 80,
      "priority_band": "P1",
      "status": "active",
      "sort_order": 2
    },
    {
      "path_id": "P3",
      "code": "P3",
      "title": "Datenmodell",
      "priority": 60,
      "priority_band": "P2",
      "status": "planned",
      "sort_order": 3
    },
    {
      "path_id": "P4",
      "code": "P4",
      "title": "Automatisierung",
      "priority": 25,
      "priority_band": "P3",
      "status": "planned",
      "sort_order": 4
    }
  ],
  "agents": [
    {
      "agent_id": "A-CHATGPT",
      "name": "ChatGPT",
      "kind": "llm",
      "state": "working",
      "current_work": "W-228",
      "last_seen": "2026-08-23T09:14:00Z",
      "capabilities": [
        "contract",
        "schema",
        "analysis"
      ]
    },
    {
      "agent_id": "A-CLAUDE",
      "name": "Claude",
      "kind": "llm",
      "state": "working",
      "current_work": "W-227",
      "last_seen": "2026-08-23T09:13:00Z",
      "capabilities": [
        "ui",
        "contract",
        "analysis"
      ]
    },
    {
      "agent_id": "A-VSCODE",
      "name": "VS Code",
      "kind": "tool",
      "state": "idle",
      "current_work": null,
      "last_seen": "2026-08-23T09:10:00Z",
      "capabilities": [
        "code",
        "test"
      ]
    },
    {
      "agent_id": "A-HUMAN",
      "name": "Ralph",
      "kind": "human",
      "state": "waiting",
      "current_work": null,
      "last_seen": "2026-08-23T09:15:00Z",
      "capabilities": [
        "decision"
      ]
    }
  ],
  "locks": [
    {
      "work_id": "W-228",
      "agent": "ChatGPT",
      "resource_type": "api_contract",
      "resource": "00_CONTROL_CONTRACT/API_CONTRACT.md",
      "acquired_at": "2026-08-23T08:40:00Z",
      "expires_at": "2026-08-23T10:40:00Z",
      "conflict": false
    },
    {
      "work_id": "W-227",
      "agent": "Claude",
      "resource_type": "file",
      "resource": "10_UI_PROTOTYPE/app.js",
      "acquired_at": "2026-08-23T08:55:00Z",
      "expires_at": "2026-08-23T10:55:00Z",
      "conflict": false
    }
  ],
  "decisions": [
    {
      "decision_id": "DEC-81",
      "work_id": "W-223",
      "title": "Datenquelle bei Konflikt",
      "question": "Welche Datenquelle gewinnt, wenn zwei Quellen widersprechen?",
      "options": [
        "A: Quelle 1 (schneller, lückenhaft)",
        "B: Quelle 2 (langsamer, vollständig)"
      ],
      "recommendation": "B",
      "resolution": null,
      "rationale": null,
      "requested_by": "ChatGPT",
      "requested_at": "2026-08-22T16:20:00Z",
      "status": "open"
    },
    {
      "decision_id": "DEC-82",
      "work_id": "W-225",
      "title": "Lease-Dauer",
      "question": "Wie lange gilt ein Work Lease, bevor er automatisch verfällt?",
      "options": [
        "A: 30 Minuten",
        "B: 2 Stunden",
        "C: 8 Stunden"
      ],
      "recommendation": "B",
      "resolution": null,
      "rationale": null,
      "requested_by": "Claude",
      "requested_at": "2026-08-23T07:05:00Z",
      "status": "open"
    }
  ],
  "work_items": [
    {
      "work_id": "W-228",
      "path_id": "P1",
      "parent_work_id": null,
      "title": "API Contract festschreiben",
      "goal": "Alle Agenten schreiben über dieselben Funktionen, nicht direkt auf Tabellen.",
      "description": "Definiert die Schreiboperationen der Control API und die Prüfungen, die der Server vor jedem Write durchführt.",
      "status": "in_progress",
      "priority": 96,
      "priority_band": "P0",
      "owner": "ChatGPT",
      "risk_level": "high",
      "definition_of_done": [
        "Alle 14 API-Funktionen beschrieben",
        "Statusübergänge vollständig",
        "Prüfregeln pro Write benannt",
        "Review durch zweiten Agenten"
      ],
      "affected_systems": [
        "Control API",
        "Datenbank"
      ],
      "affected_resources": [
        "00_CONTROL_CONTRACT/API_CONTRACT.md"
      ],
      "depends_on": [],
      "blocked_by": [],
      "blocker": null,
      "evidence": [],
      "result": null,
      "created_at": "2026-08-21T10:00:00Z",
      "updated_at": "2026-08-23T08:40:00Z",
      "required_capability": "contract"
    },
    {
      "work_id": "W-227",
      "path_id": "P2",
      "parent_work_id": null,
      "title": "Dashboard-Startseite",
      "goal": "Der Projektmanager beantwortet 8 Fragen in unter 10 Sekunden.",
      "description": "Startseite des Prototyps. Zeigt Fortschritt, laufende Arbeit, Reihenfolge, Agenten, Blocker, Entscheidungen, Konflikte und Build-Drift.",
      "status": "in_progress",
      "priority": 88,
      "priority_band": "P1",
      "owner": "Claude",
      "risk_level": "low",
      "definition_of_done": [
        "Alle 8 Abnahmefragen aus Abschnitt 37 auf einen Blick beantwortbar",
        "Alle Werte aus project-state.json",
        "Keine Fachlogik im Frontend",
        "Console ohne Fehler"
      ],
      "affected_systems": [
        "UI"
      ],
      "affected_resources": [
        "10_UI_PROTOTYPE/index.html",
        "10_UI_PROTOTYPE/app.js"
      ],
      "depends_on": [],
      "blocked_by": [],
      "blocker": null,
      "evidence": [
        {
          "evidence_id": "EV-441",
          "type": "browser_test",
          "title": "Seite lädt ohne Console-Fehler",
          "passed": true,
          "created_at": "2026-08-23T08:58:00Z"
        }
      ],
      "result": null,
      "created_at": "2026-08-21T11:30:00Z",
      "updated_at": "2026-08-23T08:58:00Z",
      "required_capability": "ui"
    },
    {
      "work_id": "W-222",
      "path_id": "P1",
      "parent_work_id": null,
      "title": "Work-Statusübergänge definieren",
      "goal": "Kein Agent erfindet eigene Statuswerte.",
      "description": "Legt die elf zulässigen Status fest und welche Übergänge der Server erlaubt.",
      "status": "open",
      "priority": 92,
      "priority_band": "P0",
      "owner": null,
      "risk_level": "medium",
      "definition_of_done": [
        "Alle 11 Status dokumentiert",
        "Übergangsmatrix vollständig",
        "Unzulässige Übergänge benannt"
      ],
      "affected_systems": [
        "Control API"
      ],
      "affected_resources": [
        "00_CONTROL_CONTRACT/schema.sql"
      ],
      "depends_on": [
        "W-228"
      ],
      "blocked_by": [],
      "blocker": null,
      "evidence": [],
      "result": null,
      "created_at": "2026-08-21T12:00:00Z",
      "updated_at": "2026-08-22T14:00:00Z",
      "required_capability": "contract"
    },
    {
      "work_id": "W-225",
      "path_id": "P1",
      "parent_work_id": null,
      "title": "Lease und Lock trennen",
      "goal": "Zwei Agenten können denselben Bereich nicht unbemerkt gleichzeitig ändern.",
      "description": "Work Lease und Resource Lock bleiben intern getrennt, list_locks liefert eine flache Sicht für Dashboard und Agenten.",
      "status": "decision_required",
      "priority": 90,
      "priority_band": "P0",
      "owner": null,
      "risk_level": "high",
      "definition_of_done": [
        "Lease-Dauer entschieden",
        "Ablaufverhalten definiert",
        "list_locks liefert flache Sicht"
      ],
      "affected_systems": [
        "Control API",
        "Datenbank"
      ],
      "affected_resources": [
        "00_CONTROL_CONTRACT/schema.sql"
      ],
      "depends_on": [
        "W-228"
      ],
      "blocked_by": [],
      "blocker": "Wartet auf DEC-82 (Lease-Dauer)",
      "evidence": [],
      "result": null,
      "created_at": "2026-08-21T12:15:00Z",
      "updated_at": "2026-08-23T07:05:00Z",
      "required_capability": "schema"
    },
    {
      "work_id": "W-223",
      "path_id": "P3",
      "parent_work_id": null,
      "title": "Quellenpriorität im Datenmodell",
      "goal": "Bei widersprüchlichen Quellen ist eindeutig, welche gewinnt.",
      "description": "Regelt die Auflösung von Quellenkonflikten im Datenmodell.",
      "status": "blocked",
      "priority": 65,
      "priority_band": "P2",
      "owner": null,
      "risk_level": "medium",
      "definition_of_done": [
        "Vorrangregel entschieden",
        "Im Schema abgebildet",
        "Testfall mit widersprüchlichen Quellen besteht"
      ],
      "affected_systems": [
        "Datenbank"
      ],
      "affected_resources": [
        "00_CONTROL_CONTRACT/schema.sql"
      ],
      "depends_on": [
        "W-225"
      ],
      "blocked_by": [
        "W-225"
      ],
      "blocker": "Wartet auf W-225 und auf DEC-81",
      "evidence": [],
      "result": null,
      "created_at": "2026-08-21T13:00:00Z",
      "updated_at": "2026-08-22T16:20:00Z",
      "required_capability": "schema"
    },
    {
      "work_id": "W-219",
      "path_id": "P2",
      "parent_work_id": null,
      "title": "Startweg des Prototyps dokumentieren",
      "goal": "Ein einziger reproduzierbarer Startbefehl, kein Raten.",
      "description": "README_UI.md beschreibt genau einen Weg, den Prototyp lokal über HTTP zu starten.",
      "status": "done",
      "priority": 85,
      "priority_band": "P1",
      "owner": "Claude",
      "risk_level": "low",
      "definition_of_done": [
        "Genau ein Startbefehl dokumentiert",
        "URL genannt",
        "Von zweiter Person nachvollzogen"
      ],
      "affected_systems": [
        "UI"
      ],
      "affected_resources": [
        "10_UI_PROTOTYPE/README_UI.md"
      ],
      "depends_on": [],
      "blocked_by": [],
      "blocker": null,
      "evidence": [
        {
          "evidence_id": "EV-438",
          "type": "browser_test",
          "title": "http://localhost:8000/ liefert index.html",
          "passed": true,
          "created_at": "2026-08-22T18:02:00Z"
        },
        {
          "evidence_id": "EV-439",
          "type": "query_result",
          "title": "project-state.json per HTTP geladen, Status 200",
          "passed": true,
          "created_at": "2026-08-22T18:03:00Z"
        }
      ],
      "result": "Startweg dokumentiert und zweimal reproduziert.",
      "created_at": "2026-08-20T09:00:00Z",
      "updated_at": "2026-08-22T18:05:00Z",
      "required_capability": "ui"
    },
    {
      "work_id": "W-231",
      "path_id": "P4",
      "parent_work_id": null,
      "title": "Build- und Live-Stand automatisch messen",
      "goal": "Kein Agent schließt aus einer lokalen Buildnummer auf den Live-Stand.",
      "description": "Repo-, Build- und Live-Stand werden gemessen statt behauptet. Drift wird sichtbar gemacht.",
      "status": "backlog",
      "priority": 30,
      "priority_band": "P3",
      "owner": null,
      "risk_level": "low",
      "definition_of_done": [
        "Repo-Stand gemessen",
        "Live-Stand gemessen",
        "Drift im Dashboard sichtbar"
      ],
      "affected_systems": [
        "Build",
        "Deploy"
      ],
      "affected_resources": [],
      "depends_on": [
        "W-228"
      ],
      "blocked_by": [],
      "blocker": null,
      "evidence": [],
      "result": null,
      "created_at": "2026-08-22T09:00:00Z",
      "updated_at": "2026-08-22T09:00:00Z",
      "required_capability": "code"
    }
  ]
};
