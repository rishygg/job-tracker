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
CREATE TABLE IF NOT EXISTS stage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    date TEXT NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_app ON stage_events(application_id);
"""

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
}

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

    def move_stage(self, app_id: int, stage: str, when=None, note: str | None = None) -> None:
        """Record a new stage for an application and make it the current status."""
        if stage not in STAGES:
            raise ValueError(f"Unknown stage {stage!r}")
        with self._conn() as c:
            c.execute("INSERT INTO stage_events (application_id, stage, date, note) VALUES (?, ?, ?, ?)",
                      (app_id, stage, _iso(when), note))
            c.execute("UPDATE applications SET status = ? WHERE id = ?", (stage, app_id))

    def delete_application(self, app_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM applications WHERE id = ?", (app_id,))

    def clear(self) -> None:
        with self._conn() as c:
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
