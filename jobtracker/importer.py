"""Import applications from an existing Excel or CSV tracker.

Column names are matched loosely, and the header row is found automatically,
so most home-made trackers import without changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

import pandas as pd

from .analysis import IMPORTED_NOTE
from .storage import STAGES, Store

COLUMN_SYNONYMS: dict[str, list[str]] = {
    "company": ["company", "employer", "organisation", "organization", "company name"],
    "position": ["position", "role", "job title", "title", "job", "position title"],
    "date_applied": ["date applied", "applied on", "application date", "date", "applied"],
    "status": ["application status", "status", "stage", "current status"],
    "final_status": ["final status", "outcome", "result"],
    "location": ["location", "city", "country", "details", "place"],
    "contact": ["hiring manager", "contact", "recruiter", "contact person"],
    "url": ["applicant portal", "url", "link", "job link", "portal", "posting"],
    "notes": ["notes", "comments", "remarks"],
    "source": ["source", "channel", "found via", "via"],
    "follow_up": ["date followed up", "followed up", "follow up date"],
}

STATUS_MAP = {
    "submitted": "Applied", "applied": "Applied", "followed up": "Applied", "pending": "Applied",
    "in progress": "Screening", "screening": "Screening", "phone screen": "Screening", "assessment": "Screening",
    "interview": "Interview", "interviewing": "Interview", "final interview": "Final interview",
    "offer": "Offer", "accepted": "Accepted",
    "rejected": "Rejected", "declined": "Rejected", "unsuccessful": "Rejected",
    "ghosted": "Ghosted", "no response": "Ghosted",
    "withdrawn": "Withdrawn", "withdrew": "Withdrawn",
}


def normalise_status(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().lower()
    if s in STATUS_MAP:
        return STATUS_MAP[s]
    for stage in STAGES:
        if s == stage.lower():
            return stage
    return None


def _find_header(raw: pd.DataFrame) -> int:
    """Index of the first row that looks like a header (has a company and a position column)."""
    for i in range(min(len(raw), 50)):
        cells = {str(c).strip().lower() for c in raw.iloc[i].tolist() if pd.notna(c)}
        if cells & set(COLUMN_SYNONYMS["company"]) and cells & set(COLUMN_SYNONYMS["position"]):
            return i
    raise ValueError("Couldn't find a header row with a company and a position/role column.")


def _map_columns(columns) -> dict[str, str]:
    mapping: dict[str, str] = {}
    lowered = {str(c).strip().lower(): c for c in columns if pd.notna(c)}
    for field, names in COLUMN_SYNONYMS.items():
        for name in names:
            if name in lowered and lowered[name] not in mapping.values():
                mapping[field] = lowered[name]
                break
    return mapping


def list_sheets(file: str | Path | IO) -> list[str]:
    return pd.ExcelFile(file).sheet_names


def read_tracker(file: str | Path | IO, sheet: str | None = None, filename: str | None = None) -> pd.DataFrame:
    """Read a tracker into a tidy DataFrame with standard column names."""
    name = (filename or getattr(file, "name", None) or str(file)).lower()
    if name.endswith((".csv", ".tsv")):
        raw = pd.read_csv(file, header=None, sep="\t" if name.endswith(".tsv") else ",")
    else:
        raw = pd.read_excel(file, sheet_name=sheet or 0, header=None)
    h = _find_header(raw)
    body = raw.iloc[h + 1:].copy()
    body.columns = raw.iloc[h].tolist()
    mapping = _map_columns(body.columns)
    tidy = pd.DataFrame({field: body[col] for field, col in mapping.items()})
    tidy = tidy.dropna(subset=["company", "position"])
    tidy = tidy[tidy["company"].astype(str).str.strip() != ""]
    tidy["date_applied"] = pd.to_datetime(tidy.get("date_applied"), errors="coerce", dayfirst=True)
    for col in ["status", "final_status"]:
        if col in tidy:
            tidy[col] = tidy[col].map(normalise_status)
    return tidy.reset_index(drop=True)


def build_history(row: pd.Series) -> tuple[str, list[tuple[str, object, str | None]]]:
    """Turn a tracker row into (current status, stage events)."""
    def clean(v):
        return None if v is None or (not isinstance(v, str) and pd.isna(v)) else v

    applied = row.get("date_applied")
    status = clean(row.get("status")) or "Applied"
    final = clean(row.get("final_status"))
    history: list[tuple[str, object, str | None]] = [("Applied", applied, None)]
    if status != "Applied":
        history.append((status, applied, IMPORTED_NOTE))
    if final and final != status:
        history.append((final, applied, IMPORTED_NOTE))
        status = final
    return status, history


def import_into(store: Store, tidy: pd.DataFrame, default_source: str | None = None) -> int:
    """Insert tidy rows into the store. Returns the number imported."""
    n = 0
    for _, row in tidy.iterrows():
        status, history = build_history(row)
        get = lambda k: (None if pd.isna(row.get(k)) else str(row.get(k)).strip()) if k in row else None  # noqa: E731
        store.add_application(
            company=str(row["company"]), position=str(row["position"]),
            date_applied=row["date_applied"] if pd.notna(row.get("date_applied")) else None,
            status=status, history=history,
            location=get("location"), contact=get("contact"), url=get("url"), notes=get("notes"),
            source=get("source") or default_source,
        )
        n += 1
    return n
