"""SQLite storage for applications and their stage history."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd

# Ordered pipeline. Index = how far an application got.
PIPELINE = ["Applied", "Screening", "Interview", "Final interview", "Offer", "Accepted"]
CLOSED = ["Rejected", "Ghosted", "Withdrawn"]
STAGES = PIPELINE + CLOSED
INTERVIEW_STAGES = {"Interview", "Final interview", "Offer", "Accepted"}
ACTIVE_STAGES = {"Applied", "Screening", "Interview", "Final interview", "Offer"}

SOURCES = ["Job portal", "Company website", "LinkedIn", "Referral", "Recruiter", "Cold email", "Career fair", "Other"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    position TEXT NOT NULL,
    location TEXT,
    date_applied TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Applied',
    source TEXT,
    contact TEXT,
    url TEXT,
    notes TEXT,
    role_area_override TEXT,
    region_override TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    due_date TEXT NOT NULL,
    note TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    position TEXT NOT NULL,
    location TEXT,
    url TEXT,
    source TEXT,
    job_description TEXT,
    deadline TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'saved',
    application_id INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    ref_id INTEGER NOT NULL,
    task TEXT NOT NULL,
    method TEXT,
    model TEXT,
    input_hash TEXT,
    result TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_ref ON ai_results(kind, ref_id, task);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'cv',
    section TEXT,
    context TEXT,
    text TEXT NOT NULL,
    kind TEXT,
    metrics TEXT,
    skills TEXT,
    stakeholders TEXT,
    industry TEXT,
    did TEXT,
    outcome TEXT,
    note TEXT,
    confirmed INTEGER NOT NULL DEFAULT 0,
    hidden INTEGER NOT NULL DEFAULT 0,
    enriched INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_state (
    key TEXT PRIMARY KEY,
    snoozed_until TEXT,
    dismissed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    date TEXT NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_app ON stage_events(application_id);
CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    company TEXT,
    position TEXT,
    date TEXT NOT NULL,
    round TEXT,
    format TEXT,
    interviewers TEXT,
    went_well TEXT,
    struggled TEXT,
    feedback TEXT,
    next_steps TEXT,
    rating INTEGER,
    outcome TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interview_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    question TEXT NOT NULL,
    category TEXT,
    competencies TEXT,
    rating INTEGER,
    answer_notes TEXT,
    story_id INTEGER REFERENCES stories(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    situation TEXT,
    task TEXT,
    action TEXT,
    result TEXT,
    competencies TEXT,
    skills TEXT,
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS practice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    category TEXT,
    source TEXT,
    ref TEXT,
    answer TEXT,
    rating INTEGER,
    feedback TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section TEXT NOT NULL,
    title TEXT,
    org TEXT,
    location TEXT,
    start TEXT,
    "end" TEXT,
    details TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inbox (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    text TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    industry TEXT,
    company TEXT,
    title TEXT NOT NULL,
    body TEXT,
    tags TEXT,
    link TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Career development tables: editable columns, and which of them hold JSON lists/objects.
CAREER = {
    "interviews": (["application_id", "company", "position", "date", "round", "format", "interviewers", "went_well",
                    "struggled", "feedback", "next_steps", "rating", "outcome"], set()),
    "interview_questions": (["interview_id", "position", "question", "category", "competencies", "rating",
                             "answer_notes", "story_id"], {"competencies"}),
    "stories": (["title", "situation", "task", "action", "result", "competencies", "skills", "evidence_id"],
                {"competencies", "skills"}),
    "practice": (["question", "category", "source", "ref", "answer", "rating", "feedback"], {"feedback"}),
    "notes": (["industry", "company", "title", "body", "tags", "link"], {"tags"}),
    "entries": (["section", "title", "org", "location", "start", "end", "details", "position"], set()),
}

# Columns added after the first release. Existing databases are migrated on start-up.
NEW_COLUMNS = {
    "date_posted": "TEXT",
    "job_description": "TEXT",
    "seniority": "TEXT",          # NULL = infer automatically
    "industry": "TEXT",
    "company_size": "TEXT",
    "work_authorization": "TEXT",
    "language": "TEXT",
    "work_mode": "TEXT",
    "cv_version": "TEXT",
    "fit_rating": "INTEGER",      # your own 1-5 rating of how well you fit the role
    "salary": "TEXT",
    "workload": "TEXT",           # e.g. "80–100%"
    "contract": "TEXT",           # Permanent / Fixed-term / Internship / Freelance
}
OPP_NEW_COLUMNS = {"workload": "TEXT", "contract": "TEXT"}

APP_FIELDS = ["company", "position", "location", "date_applied", "status", "source", "contact",
              "url", "notes", "role_area_override", "region_override", *NEW_COLUMNS]
DATE_FIELDS = {"date_applied", "date_posted"}


def _iso_or_none(d) -> str | None:
    if d is None or d == "" or (not isinstance(d, str) and pd.isna(d)):
        return None
    return _iso(d)


def _clean(v):
    """Convert pandas/numpy missing values and numpy scalars to plain Python for SQLite."""
    if v is None:
        return None
    if not isinstance(v, str) and pd.isna(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, str) and not v.strip():
        return None
    return v


def _iso(d) -> str:
    if d is None or (isinstance(d, float) and pd.isna(d)):
        return date.today().isoformat()
    if isinstance(d, (datetime, pd.Timestamp)):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return pd.to_datetime(str(d)).date().isoformat()


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)
            have = {r["name"] for r in c.execute("PRAGMA table_info(applications)")}
            for col, typ in NEW_COLUMNS.items():
                if col not in have:
                    c.execute(f"ALTER TABLE applications ADD COLUMN {col} {typ}")
            have_o = {r["name"] for r in c.execute("PRAGMA table_info(opportunities)")}
            for col, typ in OPP_NEW_COLUMNS.items():
                if col not in have_o:
                    c.execute(f"ALTER TABLE opportunities ADD COLUMN {col} {typ}")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- writes -------------------------------------------------------
    def add_application(self, company: str, position: str, date_applied=None, status: str = "Applied",
                        history: list[tuple[str, object, str | None]] | None = None, **fields) -> int:
        """Add an application.

        `history` is an optional list of (stage, date, note) events. If omitted, an
        "Applied" event is created, plus one for `status` if it differs.
        """
        if status not in STAGES:
            raise ValueError(f"Unknown status {status!r}; expected one of {STAGES}")
        d = _iso(date_applied)
        row = {k: _clean(fields.get(k)) for k in APP_FIELDS}
        row["date_posted"] = _iso_or_none(fields.get("date_posted"))
        row.update(company=company.strip(), position=position.strip(), date_applied=d, status=status)
        with self._conn() as c:
            cur = c.execute(
                f"INSERT INTO applications ({', '.join(APP_FIELDS)}, created_at) "
                f"VALUES ({', '.join('?' * len(APP_FIELDS))}, ?)",
                [row[k] for k in APP_FIELDS] + [datetime.now().isoformat(timespec="seconds")],
            )
            app_id = cur.lastrowid
            if history is None:
                history = [("Applied", d, None)]
                if status != "Applied":
                    history.append((status, d, None))
            for stage, when, note in history:
                c.execute("INSERT INTO stage_events (application_id, stage, date, note) VALUES (?, ?, ?, ?)",
                          (app_id, stage, _iso(when), note))
        return app_id

    def update_application(self, app_id: int, **fields) -> None:
        fields = {k: _clean(v) for k, v in fields.items() if k in APP_FIELDS and k != "status"}
        if not fields:
            return
        if "date_applied" in fields:
            fields["date_applied"] = _iso(fields["date_applied"])
        if "date_posted" in fields:
            fields["date_posted"] = _iso_or_none(fields["date_posted"])
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self._conn() as c:
            c.execute(f"UPDATE applications SET {sets} WHERE id = ?", [*fields.values(), app_id])

    @staticmethod
    def _sync_status(c, app_id: int) -> None:
        """Current status = the stage of the most recent event (by date, then entry order)."""
        row = c.execute("SELECT stage FROM stage_events WHERE application_id = ? ORDER BY date DESC, id DESC LIMIT 1",
                        (app_id,)).fetchone()
        if row:
            c.execute("UPDATE applications SET status = ? WHERE id = ?", (row["stage"], app_id))

    def move_stage(self, app_id: int, stage: str, when=None, note: str | None = None) -> int:
        """Record a stage for an application. The latest-dated stage becomes the current status."""
        if stage not in STAGES:
            raise ValueError(f"Unknown stage {stage!r}")
        with self._conn() as c:
            cur = c.execute("INSERT INTO stage_events (application_id, stage, date, note) VALUES (?, ?, ?, ?)",
                            (app_id, stage, _iso(when), note))
            self._sync_status(c, app_id)
            return cur.lastrowid

    def update_event(self, event_id: int, stage: str | None = None, when=None, note: str | None = None) -> None:
        with self._conn() as c:
            row = c.execute("SELECT application_id FROM stage_events WHERE id = ?", (event_id,)).fetchone()
            if not row:
                raise KeyError(event_id)
            if stage is not None:
                if stage not in STAGES:
                    raise ValueError(f"Unknown stage {stage!r}")
                c.execute("UPDATE stage_events SET stage = ? WHERE id = ?", (stage, event_id))
            if when is not None:
                c.execute("UPDATE stage_events SET date = ? WHERE id = ?", (_iso(when), event_id))
            if note is not None:
                c.execute("UPDATE stage_events SET note = ? WHERE id = ?", (note or None, event_id))
            self._sync_status(c, row["application_id"])

    def delete_event(self, event_id: int) -> None:
        with self._conn() as c:
            row = c.execute("SELECT application_id FROM stage_events WHERE id = ?", (event_id,)).fetchone()
            if not row:
                raise KeyError(event_id)
            n = c.execute("SELECT COUNT(*) FROM stage_events WHERE application_id = ?",
                          (row["application_id"],)).fetchone()[0]
            if n <= 1:
                raise ValueError("An application needs at least one stage.")
            c.execute("DELETE FROM stage_events WHERE id = ?", (event_id,))
            self._sync_status(c, row["application_id"])

    def delete_application(self, app_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM ai_results WHERE kind = 'application' AND ref_id = ?", (app_id,))
            c.execute("DELETE FROM applications WHERE id = ?", (app_id,))

    def clear(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM ai_results WHERE kind = 'application'")
            c.execute("UPDATE opportunities SET application_id = NULL, status = 'saved' WHERE status = 'applied'")
            c.execute("DELETE FROM reminders")
            c.execute("DELETE FROM notification_state")
            c.execute("DELETE FROM stage_events")
            c.execute("DELETE FROM applications")

    # ---- reads --------------------------------------------------------
    def applications(self) -> pd.DataFrame:
        with self._conn() as c:
            df = pd.read_sql_query("SELECT * FROM applications ORDER BY date_applied DESC, id DESC", c)
        df["date_applied"] = pd.to_datetime(df["date_applied"])
        df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
        return df

    def events(self, app_id: int | None = None) -> pd.DataFrame:
        q = "SELECT * FROM stage_events"
        args: tuple = ()
        if app_id is not None:
            q += " WHERE application_id = ?"
            args = (app_id,)
        with self._conn() as c:
            df = pd.read_sql_query(q + " ORDER BY date, id", c, params=args)
        df["date"] = pd.to_datetime(df["date"])
        return df

    def count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

    # ---- settings -----------------------------------------------------
    def get_setting(self, key: str, default=None):
        import json
        with self._conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_setting(self, key: str, value) -> None:
        import json
        with self._conn() as c:
            c.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, json.dumps(value)))

    # ---- reminders ----------------------------------------------------
    def reminders(self, include_done: bool = False) -> pd.DataFrame:
        q = ("SELECT r.*, a.company, a.position FROM reminders r LEFT JOIN applications a ON a.id = r.application_id"
             + ("" if include_done else " WHERE r.done = 0") + " ORDER BY r.due_date, r.id")
        with self._conn() as c:
            df = pd.read_sql_query(q, c)
        df["due_date"] = pd.to_datetime(df["due_date"])
        return df

    def add_reminder(self, title: str, due_date, application_id: int | None = None, note: str | None = None) -> int:
        with self._conn() as c:
            cur = c.execute("INSERT INTO reminders (application_id, title, due_date, note, done, created_at) "
                            "VALUES (?, ?, ?, ?, 0, ?)",
                            (application_id, title.strip(), _iso(due_date), _clean(note),
                             datetime.now().isoformat(timespec="seconds")))
            return cur.lastrowid

    def update_reminder(self, reminder_id: int, **fields) -> None:
        allowed = {"title", "due_date", "note", "done", "application_id"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if "due_date" in fields:
            fields["due_date"] = _iso(fields["due_date"])
        if "done" in fields:
            fields["done"] = int(bool(fields["done"]))
        if not fields:
            return
        with self._conn() as c:
            c.execute(f"UPDATE reminders SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                      [*fields.values(), reminder_id])

    def delete_reminder(self, reminder_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))

    # ---- notification state ------------------------------------------
    def notification_state(self) -> dict[str, dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM notification_state").fetchall()
        return {r["key"]: {"snoozed_until": r["snoozed_until"], "dismissed": bool(r["dismissed"])} for r in rows}

    def snooze_notification(self, key: str, until=None, dismiss: bool = False) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO notification_state (key, snoozed_until, dismissed) VALUES (?, ?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET snoozed_until = excluded.snoozed_until, "
                      "dismissed = excluded.dismissed", (key, _iso_or_none(until), int(dismiss)))

    # ---- opportunities (saved jobs not applied to yet) ----------------
    OPP_FIELDS = ("company", "position", "location", "url", "source", "job_description", "deadline", "notes", "workload", "contract", "status",
                  "application_id")

    def opportunities(self, status: str | None = None) -> pd.DataFrame:
        q, args = "SELECT * FROM opportunities", ()
        if status:
            q, args = q + " WHERE status = ?", (status,)
        with self._conn() as c:
            df = pd.read_sql_query(q + " ORDER BY created_at DESC, id DESC", c, params=args)
        df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")
        return df

    def add_opportunity(self, company: str, position: str, **fields) -> int:
        row = {k: _clean(fields.get(k)) for k in self.OPP_FIELDS if k not in ("status", "application_id")}
        row["deadline"] = _iso_or_none(fields.get("deadline"))
        with self._conn() as c:
            cur = c.execute(
                f"INSERT INTO opportunities (company, position, {', '.join(row)}, status, created_at) "
                f"VALUES (?, ?, {', '.join('?' * len(row))}, 'saved', ?)",
                [company.strip(), position.strip(), *row.values(), datetime.now().isoformat(timespec="seconds")])
            return cur.lastrowid

    def update_opportunity(self, opp_id: int, **fields) -> None:
        fields = {k: _clean(v) for k, v in fields.items() if k in self.OPP_FIELDS}
        if "deadline" in fields:
            fields["deadline"] = _iso_or_none(fields["deadline"])
        if not fields:
            return
        with self._conn() as c:
            c.execute(f"UPDATE opportunities SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                      [*fields.values(), opp_id])

    def delete_opportunity(self, opp_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM opportunities WHERE id = ?", (opp_id,))
            c.execute("DELETE FROM ai_results WHERE kind = 'opportunity' AND ref_id = ?", (opp_id,))

    # ---- AI / analysis results -----------------------------------------
    def save_result(self, kind: str, ref_id: int, task: str, result: dict, method: str | None = None,
                    model: str | None = None, input_hash: str | None = None) -> None:
        import json
        with self._conn() as c:
            c.execute("DELETE FROM ai_results WHERE kind = ? AND ref_id = ? AND task = ?", (kind, ref_id, task))
            c.execute("INSERT INTO ai_results (kind, ref_id, task, method, model, input_hash, result, created_at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (kind, ref_id, task, method, model, input_hash, json.dumps(result),
                       datetime.now().isoformat(timespec="seconds")))

    def get_result(self, kind: str, ref_id: int, task: str) -> dict | None:
        import json
        with self._conn() as c:
            r = c.execute("SELECT * FROM ai_results WHERE kind = ? AND ref_id = ? AND task = ? ORDER BY id DESC LIMIT 1",
                          (kind, ref_id, task)).fetchone()
        if not r:
            return None
        return {"result": json.loads(r["result"]), "method": r["method"], "model": r["model"],
                "input_hash": r["input_hash"], "created_at": r["created_at"]}

    def results(self, kind: str, task: str) -> dict[int, dict]:
        import json
        with self._conn() as c:
            rows = c.execute("SELECT * FROM ai_results WHERE kind = ? AND task = ?", (kind, task)).fetchall()
        return {r["ref_id"]: {"result": json.loads(r["result"]), "input_hash": r["input_hash"],
                              "created_at": r["created_at"], "method": r["method"]} for r in rows}

    def move_results(self, kind: str, ref_id: int, new_kind: str, new_ref: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE ai_results SET kind = ?, ref_id = ? WHERE kind = ? AND ref_id = ?",
                      (new_kind, new_ref, kind, ref_id))

    # ---- evidence bank ---------------------------------------------------
    EVIDENCE_EDITABLE = ("section", "context", "text", "kind", "did", "outcome", "note", "confirmed", "hidden",
                         "metrics", "skills", "stakeholders", "industry")

    def evidence(self, include_hidden: bool = True) -> list[dict]:
        import json
        q = "SELECT * FROM evidence" + ("" if include_hidden else " WHERE hidden = 0") + " ORDER BY position, id"
        with self._conn() as c:
            rows = [dict(r) for r in c.execute(q).fetchall()]
        for r in rows:
            for k in ("metrics", "skills", "stakeholders"):
                r[k] = json.loads(r[k]) if r[k] else []
            for k in ("confirmed", "hidden", "enriched"):
                r[k] = bool(r[k])
        return rows

    def replace_cv_evidence(self, records: list[dict]) -> None:
        """Replace records that came from the CV, keeping edits on records whose wording didn't change."""
        import json
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            old = {r["text"]: dict(r) for r in c.execute("SELECT * FROM evidence WHERE source = 'cv'").fetchall()}
            c.execute("DELETE FROM evidence WHERE source = 'cv'")
            for i, r in enumerate(records):
                prev = old.get(r["text"], {})
                c.execute(
                    "INSERT INTO evidence (position, source, section, context, text, kind, metrics, skills, stakeholders, "
                    "industry, did, outcome, note, confirmed, hidden, enriched, updated_at) "
                    "VALUES (?, 'cv', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (i, r.get("section"), r.get("context"), r["text"], prev.get("kind") if prev.get("confirmed") else r.get("kind"),
                     json.dumps(r.get("metrics", [])), json.dumps(r.get("skills", [])), json.dumps(r.get("stakeholders", [])),
                     r.get("industry"), r.get("did") or prev.get("did"), r.get("outcome") or prev.get("outcome"),
                     prev.get("note"), int(prev.get("confirmed") or 0),
                     int(prev["hidden"]) if prev and r.get("kind") != "personal" else int(bool(r.get("hidden"))),
                     int(bool(r.get("enriched") or prev.get("enriched"))), now))

    def add_evidence(self, text: str, **fields) -> int:
        import json
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            pos = (c.execute("SELECT COALESCE(MAX(position), 0) FROM evidence").fetchone()[0] or 0) + 1
            cur = c.execute(
                "INSERT INTO evidence (position, source, section, context, text, kind, metrics, skills, stakeholders, "
                "industry, did, outcome, note, confirmed, hidden, enriched, updated_at) "
                "VALUES (?, 'manual', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?)",
                (pos, fields.get("section") or "Added by you", fields.get("context"), text.strip(), fields.get("kind") or "achievement",
                 json.dumps(fields.get("metrics", [])), json.dumps(fields.get("skills", [])),
                 json.dumps(fields.get("stakeholders", [])), fields.get("industry"), fields.get("did"),
                 fields.get("outcome"), fields.get("note"), now))
            return cur.lastrowid

    def update_evidence(self, ev_id: int, **fields) -> None:
        import json
        fields = {k: v for k, v in fields.items() if k in self.EVIDENCE_EDITABLE}
        for k in ("metrics", "skills", "stakeholders"):
            if k in fields:
                fields[k] = json.dumps(fields[k] or [])
        for k in ("confirmed", "hidden"):
            if k in fields:
                fields[k] = int(bool(fields[k]))
        if not fields:
            return
        fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(f"UPDATE evidence SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?", [*fields.values(), ev_id])

    def delete_evidence(self, ev_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM evidence WHERE id = ?", (ev_id,))

    def evidence_version(self) -> str:
        """Changes whenever any record's content changes (used to mark builder results as outdated)."""
        import hashlib
        h = hashlib.sha256()
        with self._conn() as c:
            for r in c.execute("SELECT id, text, kind, note, did, outcome, confirmed, hidden FROM evidence ORDER BY id"):
                h.update(repr(tuple(r)).encode())
        return h.hexdigest()[:12]

    # ---- career development (journal, questions, stories, practice, notes) --------
    def rows(self, table: str, where: str = "", params: tuple = (), order: str = "id") -> list[dict]:
        import json
        cols, js = CAREER[table]
        with self._conn() as c:
            out = [dict(r) for r in c.execute(f"SELECT * FROM {table} {('WHERE ' + where) if where else ''} ORDER BY {order}",
                                              params).fetchall()]
        for r in out:
            for k in js:
                r[k] = json.loads(r[k]) if r.get(k) else ([] if k != "feedback" else None)
        return out

    def _prep(self, table: str, fields: dict) -> dict:
        import json
        cols, js = CAREER[table]
        out = {}
        for k, v in fields.items():
            if k not in cols:
                continue
            if k in js:
                v = json.dumps(v) if v not in (None, "") else None
            elif k == "date":
                v = _iso(v) if v else None
            else:
                v = _clean(v)
                if isinstance(v, str):
                    v = v.strip() or None
            out[k] = v
        return out

    def add_row(self, table: str, **fields) -> int:
        f = self._prep(table, fields)
        if table != "interview_questions":
            now = datetime.now().isoformat(timespec="seconds")
            f.update(created_at=now, updated_at=now)
        with self._conn() as c:
            cur = c.execute(f"INSERT INTO {table} ({', '.join(chr(34) + k + chr(34) for k in f)}) VALUES ({', '.join('?' * len(f))})",
                            list(f.values()))
            return cur.lastrowid

    def update_row(self, table: str, row_id: int, **fields) -> None:
        f = self._prep(table, fields)
        if not f:
            return
        if table != "interview_questions":
            f["updated_at"] = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(f"UPDATE {table} SET {', '.join(chr(34) + k + chr(34) + ' = ?' for k in f)} WHERE id = ?", [*f.values(), row_id])

    def delete_row(self, table: str, row_id: int) -> None:
        with self._conn() as c:
            c.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))

    def set_questions(self, interview_id: int, questions: list[dict]) -> None:
        """Replace an interview's questions (keeps ids of questions that were kept, so story links survive)."""
        keep = {int(q["id"]) for q in questions if q.get("id")}
        with self._conn() as c:
            for (qid,) in c.execute("SELECT id FROM interview_questions WHERE interview_id = ?", (interview_id,)).fetchall():
                if qid not in keep:
                    c.execute("DELETE FROM interview_questions WHERE id = ?", (qid,))
        for i, q in enumerate(questions):
            data = {**q, "interview_id": interview_id, "position": i}
            if q.get("id"):
                self.update_row("interview_questions", int(q["id"]), **data)
            else:
                self.add_row("interview_questions", **data)

    # ---- inbox: job postings sent from the browser bookmark ---------------------
    def add_inbox(self, item_id: str, title: str | None, url: str | None, text: str | None) -> None:
        now = datetime.now()
        with self._conn() as c:
            c.execute("DELETE FROM inbox WHERE created_at < ?", ((now - pd.Timedelta(days=7)).isoformat(),))
            c.execute("INSERT OR REPLACE INTO inbox (id, title, url, text, created_at) VALUES (?, ?, ?, ?, ?)",
                      (item_id, title, url, text, now.isoformat(timespec="seconds")))

    def get_inbox(self, item_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM inbox WHERE id = ?", (item_id,)).fetchone()
        return dict(r) if r else None

    def replace_entry_evidence(self, records: list[dict]) -> None:
        """Evidence derived from your entries (source 'entry'); keeps notes/confirmations on unchanged lines.
        Once entries exist, evidence read from an uploaded CV is no longer used."""
        import json
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            old = {r["text"]: dict(r) for r in c.execute("SELECT * FROM evidence WHERE source IN ('entry', 'cv')").fetchall()}
            c.execute("DELETE FROM evidence WHERE source IN ('entry', 'cv')")
            for i, r in enumerate(records):
                prev = old.get(r["text"], {})
                c.execute(
                    "INSERT INTO evidence (position, source, section, context, text, kind, metrics, skills, stakeholders, "
                    "industry, did, outcome, note, confirmed, hidden, enriched, updated_at) "
                    "VALUES (?, 'entry', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (i, r.get("section"), r.get("context"), r["text"], r.get("kind"), json.dumps(r.get("metrics", [])),
                     json.dumps(r.get("skills", [])), json.dumps(r.get("stakeholders", [])), r.get("industry"),
                     prev.get("did"), prev.get("outcome"), prev.get("note"), int(prev.get("confirmed") or 0),
                     int(prev.get("hidden") or 0), now))
