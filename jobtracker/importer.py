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
    "date_posted": ["date posted", "posted", "posting date", "posted on", "date listed", "job posted"],
    "job_description": ["job description", "description", "jd", "job ad"],
    "seniority": ["seniority", "level", "seniority level"],
    "industry": ["industry", "sector"],
    "company_size": ["company size", "size"],
    "work_mode": ["work mode", "workplace", "remote/hybrid", "on-site/remote"],
    "cv_version": ["cv version", "cv", "resume", "resume version"],
    "fit_rating": ["fit", "fit rating", "fit (1-5)"],
    "salary": ["salary", "pay", "compensation"],
}

PASSTHROUGH = ["location", "contact", "url", "notes", "job_description", "seniority", "industry",
               "company_size", "work_mode", "cv_version", "salary"]

STATUS_MAP = {
    "submitted": "Applied", "applied": "Applied", "followed up": "Applied", "pending": "Applied",
    "in progress": "Screening", "screening": "Screening", "phone screen": "Screening", "assessment": "Screening",
    "interview": "Interview", "interviewing": "Interview", "final interview": "Final interview",
    "offer": "Offer", "accepted": "Accepted",
    "rejected": "Rejected", "declined": "Rejected", "unsuccessful": "Rejected",
    "ghosted": "Ghosted", "no response": "Ghosted",
    "withdrawn": "Withdrawn", "withdrew": "Withdrawn",
}


def parse_dates(values) -> pd.Series:
    """Parse dates: ISO (2026-03-01) first, then day-first formats (01.03.2026, 01/03/2026)."""
    s = pd.Series(values)
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    iso = pd.to_datetime(s, errors="coerce", format="ISO8601")
    rest = iso.isna() & s.notna()
    if rest.any():
        iso[rest] = pd.to_datetime(s[rest].astype(str), errors="coerce", dayfirst=True, format="mixed")
    return iso


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
    tidy["date_applied"] = parse_dates(tidy["date_applied"]) if "date_applied" in tidy else pd.NaT
    if "date_posted" in tidy:
        tidy["date_posted"] = parse_dates(tidy["date_posted"])
    if "fit_rating" in tidy:
        tidy["fit_rating"] = pd.to_numeric(tidy["fit_rating"], errors="coerce").clip(1, 5)
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
            source=get("source") or default_source,
            date_posted=row.get("date_posted") if "date_posted" in row and pd.notna(row.get("date_posted")) else None,
            fit_rating=int(row["fit_rating"]) if "fit_rating" in row and pd.notna(row.get("fit_rating")) else None,
            **{k: get(k) for k in PASSTHROUGH},
        )
        n += 1
    return n


EXPORT_COLUMNS = {
    "id": "ID", "company": "Company", "position": "Position", "date_posted": "Date Posted",
    "date_applied": "Date Applied", "status": "Application Status", "furthest_stage": "Furthest Stage",
    "location": "Location", "region": "Region", "role_area": "Job Family", "seniority": "Seniority",
    "industry": "Industry", "company_size": "Company Size", "work_authorization": "Work Permit",
    "language": "Language", "work_mode": "Work Mode", "source": "Source", "cv_version": "CV Version",
    "fit_rating": "Fit (1-5)", "salary": "Salary", "contact": "Contact", "url": "Link", "notes": "Notes",
    "job_description": "Job Description",
}


def export_excel(df: pd.DataFrame, events: pd.DataFrame) -> bytes:
    """Excel workbook with your applications and their stage history. Re-importable."""
    import io

    buf = io.BytesIO()
    cols = [c for c in EXPORT_COLUMNS if c in df]
    out = df[cols].rename(columns=EXPORT_COLUMNS).copy()
    for c in ("Date Posted", "Date Applied"):
        if c in out:
            out[c] = pd.to_datetime(out[c]).dt.date
    hist = events.merge(df[["id", "company", "position"]], left_on="application_id", right_on="id", how="left")
    hist = hist[["application_id", "company", "position", "date", "stage", "note"]].rename(columns=str.title)
    hist["Date"] = pd.to_datetime(hist["Date"]).dt.date
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        out.to_excel(xw, sheet_name="Applications", index=False)
        hist.to_excel(xw, sheet_name="Stage history", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in list(col)[:200])
                ws.column_dimensions[col[0].column_letter].width = min(45, max(10, width + 2))
    return buf.getvalue()
