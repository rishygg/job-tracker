"""HTTP API for the Job Tracker web app (FastAPI). The built React app is served from jobtracker/web."""

from __future__ import annotations

import io
import re
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analysis as A
from . import notifications
from . import career as CR
from . import fun as FUN
from . import posting as P
from . import entries as EN
from . import prompts as PR
from . import digest as DG
from .cvtext import extract_text
from . import builder as B
from .evidence import extract as extract_evidence
from .fit import analyse_keywords, text_hash
from .llm import Ollama, use_progress
from .aijobs import AIJobs, BATCH, INTERACTIVE
from .categorise import Categoriser
from .dimensions import DimensionInferer
from .importer import export_excel, import_into, list_sheets, read_tracker
from .service import CATEGORIES_YAML, DIMENSIONS_YAML, REACHED_ORDER, SAMPLE, Service, apply_filters
from .storage import CLOSED, PIPELINE, SOURCES, STAGES

WEB_DIR = Path(__file__).resolve().parent / "web"

# Board columns group the detailed stages.
BOARD_COLUMNS = [
    {"id": "applied", "label": "Applied", "stages": ["Applied"], "drop_stage": "Applied"},
    {"id": "screening", "label": "Screening", "stages": ["Screening"], "drop_stage": "Screening"},
    {"id": "interviewing", "label": "Interviewing", "stages": ["Interview", "Final interview"],
     "drop_stage": "Interview"},
    {"id": "offer", "label": "Offer", "stages": ["Offer", "Accepted"], "drop_stage": "Offer"},
    {"id": "closed", "label": "Closed", "stages": ["Rejected", "Ghosted", "Withdrawn"], "drop_stage": None},
]
INFERRED = A.INFERRED

LIST_FIELDS = ["id", "company", "position", "location", "date_applied", "date_posted", "status", "furthest_stage",
               "role_area", "region", "source", "seniority", "industry", "company_size", "work_authorization",
               "language", "work_mode", "cv_version", "fit_rating", "salary", "url", "contact", "notes",
               "days_since_applied", "days_since_activity", "last_activity", "responded", "positive",
               "reached_interview", "active", "outcome", "jd_match", "has_jd", "days_to_apply", "timing",
               "days_to_response"]


class AppIn(BaseModel):
    company: str | None = None
    position: str | None = None
    location: str | None = None
    date_applied: str | None = None
    date_posted: str | None = None
    status: str | None = None
    source: str | None = None
    contact: str | None = None
    url: str | None = None
    notes: str | None = None
    job_description: str | None = None
    cv_version: str | None = None
    fit_rating: int | None = None
    salary: str | None = None
    workload: str | None = None
    contract: str | None = None
    role_area: str | None = None
    region: str | None = None
    seniority: str | None = None
    industry: str | None = None
    company_size: str | None = None
    work_authorization: str | None = None
    language: str | None = None
    work_mode: str | None = None
    reminder_title: str | None = None
    reminder_date: str | None = None


class StageIn(BaseModel):
    stage: str
    date: str | None = None
    note: str | None = None


class EventPatch(BaseModel):
    stage: str | None = None
    date: str | None = None
    note: str | None = None


class ParseIn(BaseModel):
    company: str | None = ""
    position: str | None = ""
    location: str | None = ""
    job_description: str | None = ""


class NotifAction(BaseModel):
    key: str
    action: str
    days: int | None = 7


class ReminderIn(BaseModel):
    title: str | None = None
    due_date: str | None = None
    application_id: int | None = None
    note: str | None = None
    done: bool | None = None


class RulesIn(BaseModel):
    text: str


class FitRun(BaseModel):
    engine: str | None = None


class FitCheck(BaseModel):
    company: str | None = ""
    position: str | None = ""
    location: str | None = ""
    job_description: str
    engine: str | None = None


class BatchIn(BaseModel):
    kind: str = "opportunity"
    engine: str | None = "keywords"
    only_missing: bool = True


class DocRun(BaseModel):
    engine: str | None = None


class OppIn(BaseModel):
    company: str | None = None
    position: str | None = None
    location: str | None = None
    url: str | None = None
    source: str | None = None
    job_description: str | None = None
    deadline: str | None = None
    notes: str | None = None
    workload: str | None = None
    contract: str | None = None
    status: str | None = None
    fit: dict | None = None


class QueueIn(BaseModel):
    items: list[dict]


class InterviewIn(BaseModel):
    application_id: int | None = None
    company: str | None = None
    position: str | None = None
    date: str | None = None
    round: str | None = None
    format: str | None = None
    interviewers: str | None = None
    went_well: str | None = None
    struggled: str | None = None
    feedback: str | None = None
    next_steps: str | None = None
    rating: int | None = None
    outcome: str | None = None
    questions: list[dict] | None = None


class StoryIn(BaseModel):
    title: str | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    competencies: list[str] | None = None
    skills: list[str] | None = None
    evidence_id: int | None = None


class PracticeIn(BaseModel):
    question: str | None = None
    category: str | None = None
    source: str | None = None
    ref: str | None = None
    answer: str | None = None
    rating: int | None = None
    engine: str | None = None


class NoteIn(BaseModel):
    industry: str | None = None
    company: str | None = None
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    link: str | None = None


class EntryIn(BaseModel):
    section: str | None = None
    title: str | None = None
    org: str | None = None
    location: str | None = None
    start: str | None = None
    end: str | None = None
    details: str | None = None
    entries: list[dict] | None = None
    text: str | None = None
    replace: bool | None = None
    ids: list[int] | None = None


class RankIn(BaseModel):
    items: list[dict] | None = None
    text: str | None = None
    goals: str | None = None
    include_ranked: bool = False


class OppBatchIn(BaseModel):
    ids: list[int]
    action: str  # archive | restore | delete | apply


class BatchAppsIn(BaseModel):
    ids: list[int]
    action: str


class UndoIn(BaseModel):
    event_ids: list[int]


class SeenIn(BaseModel):
    ids: list[str]


class AiQuestionsIn(BaseModel):
    application_id: int
    kind: str | None = None


class EvidenceIn(BaseModel):
    text: str | None = None
    kind: str | None = None
    section: str | None = None
    context: str | None = None
    did: str | None = None
    outcome: str | None = None
    note: str | None = None
    confirmed: bool | None = None
    hidden: bool | None = None


def create_app(service: Service | None = None) -> FastAPI:
    svc = service or Service()
    app = FastAPI(title="Job Tracker", version="0.3.0")
    app.state.svc = svc

    # ------------------------------------------------------------- helpers
    def clean(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, (pd.Timestamp, datetime)):
            return None if pd.isna(v) else v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, (np.bool_,)):
            return bool(v)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating, float)):
            return None if math.isnan(v) else float(v)
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, np.ndarray):
            return [clean(x) for x in v.tolist()]
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    def records(df: pd.DataFrame, fields: list[str] | None = None) -> list[dict]:
        cols = [c for c in (fields or list(df.columns)) if c in df]
        return [{c: clean(v) for c, v in zip(cols, row)} for row in df[cols].itertuples(index=False, name=None)]

    def snap():
        return svc.snapshot()

    def filtered(request: Request) -> pd.DataFrame:
        return apply_filters(snap().df, dict(request.query_params))

    _places: list = []

    def places():
        if not _places:
            _places.extend(FUN.load_places())
        return _places

    def get_app_row(app_id: int) -> pd.Series:
        df = snap().df
        rows = df[df["id"] == app_id]
        if rows.empty:
            raise HTTPException(404, "Application not found")
        return rows.iloc[0]

    def changed():
        svc.invalidate()

    # ---------------------------------------------------------------- meta
    @app.get("/api/meta")
    def meta():
        s = snap()
        inf, cat = s.inferer, s.cat
        df = s.df
        return {
            "stages": STAGES, "pipeline": PIPELINE, "closed": CLOSED, "sources": SOURCES,
            "board_columns": BOARD_COLUMNS,
            "options": {
                "role_area": cat.role_area_names, "region": cat.region_names,
                **{d: inf.options(d) for d in INFERRED},
                "source": SOURCES, "status": STAGES,
            },
            "skills": sorted(inf.skill_groups, key=str.lower),
            "dimensions": A.DIMENSIONS,
            "metrics": A.METRICS,
            "count": int(len(df)),
            "cv_versions": sorted({str(v) for v in df.get("cv_version", pd.Series(dtype=str)).dropna() if str(v).strip()}),
            "settings": {k: v for k, v in s.settings.items() if k != "cv_text"}
            | {"cv_chars": len(s.settings.get("cv_text") or "")},
        }

    # -------------------------------------------------------- applications
    @app.get("/api/applications")
    def list_applications(request: Request):
        d = filtered(request).sort_values(["date_applied", "id"], ascending=False)
        items = records(d, LIST_FIELDS)
        ranks = svc.store.results("application", "chat_rank")
        for it in items:
            rk = ranks.get(it["id"])
            it["rank"] = rk["result"] if rk else None
        return {"items": items, "total": int(len(snap().df))}

    @app.get("/api/applications/{app_id}")
    def get_application(app_id: int):
        s = snap()
        row = get_app_row(app_id)
        item = {k: clean(row.get(k)) for k in row.index}
        item["jd_skills"] = clean(row.get("jd_skills") or [])
        stored = svc.store.applications()
        raw = stored[stored["id"] == app_id].iloc[0]
        item["overrides"] = {d: clean(raw.get(d)) for d in INFERRED}
        item["overrides"]["role_area"] = clean(raw.get("role_area_override"))
        item["overrides"]["region"] = clean(raw.get("region_override"))
        item["auto"] = {d: clean(row.get(f"{d}_auto")) for d in INFERRED}
        item["auto"]["role_area"] = s.cat.role_area(row["position"])
        item["auto"]["region"] = s.cat.region(row.get("location"))
        ev = svc.store.events(app_id)
        item["events"] = records(ev, ["id", "stage", "date", "note"])
        rem = svc.store.reminders(include_done=True)
        item["reminders"] = records(rem[rem["application_id"] == app_id], ["id", "title", "due_date", "note", "done"])
        jd = row.get("job_description")
        if isinstance(jd, str) and jd.strip():
            a = s.inferer.analyse_jd(jd)
            mine = {x.lower() for x in s.settings["my_skills"]}
            item["jd_analysis"] = {
                "skills": [{"skill": k, "have": k.lower() in mine, "group": s.inferer.skill_groups.get(k, "")}
                           for k in a.skills],
                "min_years": a.min_years, "language": a.language, "work_authorization": a.work_authorization,
                "work_mode": a.work_mode, "written_in_german": a.written_in_german,
                "match": clean(row.get("jd_match")), "has_profile": bool(mine),
            }
        others = s.df[(s.df["company"].str.lower() == str(row["company"]).lower()) & (s.df["id"] != app_id)]
        item["same_company"] = records(others, ["id", "position", "status", "date_applied"])
        return item


    def _fields(body: AppIn, partial: bool) -> dict:
        data = body.model_dump(exclude_unset=partial)
        out = {}
        for k, v in data.items():
            if k in ("status", "reminder_title", "reminder_date"):
                continue
            if k == "role_area":
                out["role_area_override"] = v or None
            elif k == "region":
                out["region_override"] = v or None
            else:
                out[k] = v if v != "" else None
        return out

    @app.post("/api/applications")
    def create_application(body: AppIn):
        if not (body.company or "").strip() or not (body.position or "").strip():
            raise HTTPException(422, "Company and position are required.")
        f = _fields(body, partial=False)
        company, position = f.pop("company"), f.pop("position")
        applied = f.pop("date_applied", None) or date.today().isoformat()
        status = body.status or "Applied"
        history = [("Applied", applied, None)]
        if status != "Applied":
            history.append((status, date.today().isoformat(), None))
        app_id = svc.store.add_application(company, position, applied, status=status, history=history, **f)
        if body.reminder_title and body.reminder_date:
            svc.store.add_reminder(body.reminder_title, body.reminder_date, app_id)
        changed()
        if body.job_description:
            quick_fit("application", app_id)
        return {"id": app_id}

    @app.patch("/api/applications/{app_id}")
    def update_application(app_id: int, body: AppIn):
        get_app_row(app_id)
        f = _fields(body, partial=True)
        if "company" in f and not f["company"]:
            raise HTTPException(422, "Company can't be empty.")
        if "position" in f and not f["position"]:
            raise HTTPException(422, "Position can't be empty.")
        svc.store.update_application(app_id, **f)
        changed()
        if "job_description" in f:
            quick_fit("application", app_id)
        return get_application(app_id)

    @app.delete("/api/applications/{app_id}")
    def delete_application(app_id: int):
        svc.store.delete_application(app_id)
        changed()
        return {"ok": True}


    @app.post("/api/applications/{app_id}/stages")
    def add_stage(app_id: int, body: StageIn):
        get_app_row(app_id)
        if body.stage not in STAGES:
            raise HTTPException(422, f"Unknown stage {body.stage}")
        eid = svc.store.move_stage(app_id, body.stage, body.date or date.today(), body.note or None)
        changed()
        return {**get_application(app_id), "event_id": eid}


    @app.patch("/api/events/{event_id}")
    def update_event(event_id: int, body: EventPatch):
        try:
            svc.store.update_event(event_id, body.stage, body.date, body.note)
        except KeyError:
            raise HTTPException(404, "Stage not found")
        except ValueError as e:
            raise HTTPException(422, str(e))
        changed()
        return {"ok": True}

    @app.delete("/api/events/{event_id}")
    def delete_event(event_id: int):
        try:
            svc.store.delete_event(event_id)
        except KeyError:
            raise HTTPException(404, "Stage not found")
        except ValueError as e:
            raise HTTPException(422, str(e))
        changed()
        return {"ok": True}


    def seen_before(company: str | None, position: str | None) -> list[dict]:
        """The same role already in the Inbox or skipped earlier."""
        if not (company or "").strip() or not (position or "").strip():
            return []
        o = svc.store.opportunities()
        o = o[(o["status"] != "applied") & (o["company"].str.lower() == company.strip().lower())
              & (o["position"].str.lower() == position.strip().lower())]
        return records(o, ["id", "status", "created_at"])

    @app.post("/api/parse")
    def parse(body: ParseIn):
        """Live preview of what will be inferred for a new application."""
        s = snap()
        inf = s.inferer.infer_all(body.position, body.company, body.job_description)
        mine = {x.lower() for x in s.settings["my_skills"]} | {k.lower() for k in s.inferer.analyse_jd(profile_material()).skills}
        skills = inf["jd_skills"]
        work_mode = "Remote" if "remote" in (body.location or "").lower() else inf["work_mode"]
        df = s.df
        dup = df[(df["company"].str.lower() == (body.company or "").strip().lower())
                 & (df["position"].str.lower() == (body.position or "").strip().lower())] if body.company else df.iloc[0:0]
        prev = df[df["company"].str.lower() == (body.company or "").strip().lower()] if body.company else df.iloc[0:0]
        ex = P.extract(body.job_description or "", None, places())
        cleaned, removed = P.clean(body.job_description or "")
        guess = {k: ex[k] for k in ("position", "company", "location", "workload", "contract", "deadline")}
        return {
            "confidence": ex["confidence"], "posting_language": ex["language"],
            "cleaned": cleaned if sum(removed.values()) >= 3 else None, "removed": removed,
            "role_area": s.cat.role_area(body.position) if body.position else None,
            "region": s.cat.region(body.location) if body.location else None,
            "seniority": inf["seniority"], "industry": inf["industry"], "company_size": inf["company_size"],
            "work_authorization": inf["work_authorization"], "language": inf["language"], "work_mode": work_mode,
            "min_years": inf["min_years"],
            "skills": [{"skill": k, "have": k.lower() in mine} for k in skills],
            "match": (sum(k.lower() in mine for k in skills) / len(skills)) if (skills and mine) else None,
            "duplicate": records(dup, ["id", "position", "status", "date_applied"]),
            "seen": seen_before(body.company, body.position),
            "same_company": records(prev, ["id", "position", "status", "date_applied"])[:5],
            "guess": guess,
            "uncertain": [k for k, v in {"seniority": inf["seniority"] == "Mid / unspecified",
                                         "industry": inf["industry"] == "Unknown",
                                         "company_size": inf["company_size"] == "Unknown"}.items() if v],
        }

    # ------------------------------------------------------------ overview
    @app.get("/api/overview")
    def overview(request: Request):
        s = snap()
        d = filtered(request)
        items = notifications.build(svc.store, s.df, s.settings)
        counts = {c["id"]: int(d["status"].isin(c["stages"]).sum()) for c in BOARD_COLUMNS}
        wk = A.weekly_counts(d, 8)
        ev = s.events
        up = ev[ev["stage"].isin(["Interview", "Final interview"]) & (ev["date"].dt.date >= date.today())]
        names = s.df.set_index("id")
        upcoming = []
        for e in up.sort_values("date").itertuples():
            if e.application_id in names.index:
                a = names.loc[e.application_id]
                upcoming.append({"event_id": int(e.id), "application_id": int(e.application_id), "stage": e.stage,
                                 "date": e.date.date().isoformat(), "note": clean(e.note),
                                 "company": a["company"], "position": a["position"]})
        rem = svc.store.reminders()
        later = rem[rem["due_date"].dt.date > date.today()]
        active = d[d["active"]].sort_values("last_activity", ascending=False)
        return {
            "priorities": items,
            "pipeline": counts,
            "active": records(active.head(8), ["id", "company", "position", "status", "days_since_activity",
                                               "role_area", "last_activity"]),
            "upcoming_interviews": upcoming[:8],
            "upcoming_reminders": records(later.head(8), ["id", "title", "due_date", "company", "position",
                                                          "application_id"]),
            "insights": key_insights(d, s.settings),
            "weekly": {"weeks": [w.date().isoformat() for w in wk["week"]], "counts": wk["applied"].tolist(),
                       "goal": int(s.settings["weekly_goal"])},
            "totals": {"applications": int(len(d)), "active": int(d["active"].sum()) if len(d) else 0,
                       "interviews": int(d["reached_interview"].sum()) if len(d) else 0,
                       "this_week": int(wk["applied"].iloc[-1]) if len(wk) else 0},
            "name": s.settings.get("name") or "",
        }

    def key_insights(d: pd.DataFrame, settings: dict) -> list[dict]:
        out: list[dict] = []
        if len(d) < 5:
            return [{"tone": "info", "text": "Add at least 5 applications to start seeing patterns. With 20+ you can "
                                             "compare job families; with a few interviews you can compare what "
                                             "gets you past screening."}]
        cm = A.conversion_metrics(d, settings["too_new_days"])
        r = cm["application_to_response"]
        out.append({"tone": "info", "text": f"{r['rate']:.0%} of your applications get a reply "
                    f"({r['numerator']} of {r['denominator']}); {cm['application_to_interview']['numerator']} "
                    "reached an interview."})
        j = A.judged(d, settings["too_new_days"])
        if len(j) >= 10:
            card = A.scorecard_all(j, metric="responded" if j["positive"].sum() < 5 else "positive")
            best, worst = A.strengths_and_gaps(card)
            if not best.empty:
                b = best.iloc[0]
                out.append({"tone": "good", "text": f"Strongest: {b['dimension_label']} · {b['value']} "
                            f"({int(b['successes'])}/{int(b['applied'])}, {b['lift']:+.0%} vs your average)."})
            if not worst.empty:
                w = worst.iloc[0]
                out.append({"tone": "warn", "text": f"Weakest: {w['dimension_label']} · {w['value']} "
                            f"({int(w['successes'])}/{int(w['applied'])}, {w['lift']:+.0%} vs your average)."})
        if cm.get("median_days_to_response") is not None and cm["response_time_samples"] >= 5:
            out.append({"tone": "info", "text": f"Employers usually reply within {cm['median_days_to_response']:.0f} days."})
        missing = []
        if d["date_posted"].notna().mean() < 0.3:
            missing.append("posting dates")
        if d["has_jd"].mean() < 0.3:
            missing.append("job descriptions")
        if missing:
            out.append({"tone": "hint", "text": f"Add {' and '.join(missing)} to new applications to unlock timing "
                                                "and skills-match insights."})
        return out

    # ------------------------------------------------------- notifications

    @app.post("/api/priorities/act")
    def act(body: NotifAction):
        s = snap()
        items = {i["key"]: i for i in notifications.build(svc.store, s.df, s.settings)}
        item = items.get(body.key)
        if body.action == "snooze":
            svc.store.snooze_notification(body.key, date.today() + timedelta(days=body.days or 7))
        elif body.action == "dismiss":
            svc.store.snooze_notification(body.key, None, dismiss=True)
        elif item is None:
            raise HTTPException(404, "This item is no longer open.")
        elif body.action == "mark_ghosted":
            eid = svc.store.move_stage(item["application_id"], "Ghosted", date.today(), "No reply")
        elif body.action == "followed_up":
            row = get_app_row(item["application_id"])
            eid = svc.store.move_stage(item["application_id"], row["status"], date.today(), "Followed up")
        elif body.action == "done":
            if item["kind"] == "reminder":
                svc.store.update_reminder(item["reminder_id"], done=True)
            else:
                svc.store.snooze_notification(body.key, None, dismiss=True)
        else:
            raise HTTPException(422, "Unknown action")
        changed()
        return {"ok": True, "event_ids": [eid] if "eid" in locals() else []}

    @app.post("/api/priorities/ghost-all")
    def ghost_all():
        """Mark every 'no reply in N days' item as ghosted at once."""
        s = snap()
        ids = []
        for i in notifications.build(svc.store, s.df, s.settings):
            if i["kind"] == "ghost":
                ids.append(svc.store.move_stage(i["application_id"], "Ghosted", date.today(), "No reply"))
        changed()
        return {"count": len(ids), "event_ids": ids}

    # ------------------------------------------------------------ reminders

    @app.get("/api/reminders")
    def reminders(include_done: bool = False):
        return records(svc.store.reminders(include_done), ["id", "title", "due_date", "note", "done",
                                                           "application_id", "company", "position"])

    @app.post("/api/reminders")
    def add_reminder(body: ReminderIn):
        if not (body.title or "").strip() or not body.due_date:
            raise HTTPException(422, "A reminder needs a title and a date.")
        rid = svc.store.add_reminder(body.title, body.due_date, body.application_id, body.note)
        changed()
        return {"id": rid}

    @app.patch("/api/reminders/{rid}")
    def edit_reminder(rid: int, body: ReminderIn):
        svc.store.update_reminder(rid, **body.model_dump(exclude_unset=True))
        changed()
        return {"ok": True}

    @app.delete("/api/reminders/{rid}")
    def remove_reminder(rid: int):
        svc.store.delete_reminder(rid)
        changed()
        return {"ok": True}

    # ------------------------------------------------------------ analytics
    @app.get("/api/analytics")
    def analytics(request: Request, metric: str = "positive", dim: str = "role_area", rows: str = "role_area",
                  cols: str = "seniority", skip_recent: bool = True):
        s = snap()
        d = filtered(request)
        if d.empty:
            return {"empty": True}
        too_new = s.settings["too_new_days"]
        j = A.judged(d, too_new) if skip_recent else d
        f = A.funnel_with_dropoff(d)
        mo = A.monthly(d)
        card = A.scorecard_all(j, metric=metric) if len(j) >= 5 else pd.DataFrame()
        best, worst = A.strengths_and_gaps(card) if not card.empty else (card, card)
        sc = A.scorecard(j, dim, metric) if len(j) else pd.DataFrame()
        hm_rate, hm_n = A.heatmap(j, rows, cols, metric) if rows != cols and len(j) else (pd.DataFrame(), pd.DataFrame())
        links = A.flow_links(d, s.events)
        return {
            "empty": False,
            "conversion": clean(A.conversion_metrics(d, too_new)),
            "funnel": records(f),
            "flow": records(links),
            "monthly": records(mo.assign(month=mo["month"].dt.strftime("%Y-%m"))) if not mo.empty else [],
            "by_family": records(A.rates_by(d, "role_area", too_new)),
            "by_dim": records(A.rates_by(d, dim, too_new)),
            "response_time": records(A.response_time_by(d, "role_area")),
            "scorecard": records(sc),
            "strengths": records(best), "gaps": records(worst),
            "heatmap": {"rows": [str(x) for x in hm_rate.index], "cols": [str(x) for x in hm_rate.columns],
                        "rate": clean(hm_rate.to_numpy().tolist()) if not hm_rate.empty else [],
                        "n": clean(hm_n.to_numpy().tolist()) if not hm_n.empty else []},
            "judged": int(len(j)), "successes": int(j[metric].sum()) if len(j) else 0,
            "average": clean(j[metric].mean()) if len(j) else None,
            "coverage": {k: clean(v) for k, v in {
                "date_posted": d["date_posted"].notna().mean(), "job_description": d["has_jd"].mean(),
                "source": d["source"].notna().mean(), "cv_version": d["cv_version"].notna().mean(),
                "fit_rating": d["fit_rating"].notna().mean()}.items()},
        }

    # ------------------------------------------------------------- settings
    @app.get("/api/settings")
    def get_settings():
        return snap().settings

    @app.put("/api/settings")
    def put_settings(body: dict):
        old_cv = svc.settings().get("cv_text") or ""
        for k, v in body.items():
            if k in svc.settings():
                svc.store.set_setting(k, v)
        if "cv_text" in body and (body["cv_text"] or "") != old_cv and not svc.store.rows("entries"):
            svc.store.replace_cv_evidence(extract_evidence(body["cv_text"] or "", snap().inferer))
        changed()
        return svc.settings()

    @app.get("/api/rules/{name}")
    def get_rules(name: str):
        path = {"categories": CATEGORIES_YAML, "dimensions": DIMENSIONS_YAML, "ranking": PR.RANKING_YAML}.get(name)
        if not path:
            raise HTTPException(404)
        s = snap()
        unknown_titles, unknown_companies = [], []
        if not s.df.empty:
            unknown_titles = sorted(set(s.df.loc[s.df["role_area"] == s.cat.default_role_area, "position"]))
            unknown_companies = (s.df.loc[s.df["industry"] == "Unknown", "company"].value_counts()
                                 .head(50).index.tolist())
        return {"text": path.read_text(encoding="utf-8"), "unknown_titles": unknown_titles,
                "unknown_companies": unknown_companies}


    @app.put("/api/rules/{name}")
    def put_rules(name: str, body: RulesIn):
        try:
            cfg = yaml.safe_load(body.text) or {}
            if name == "categories":
                Categoriser.from_dict(cfg)
                CATEGORIES_YAML.write_text(body.text, encoding="utf-8")
            elif name == "dimensions":
                DimensionInferer(cfg)
                DIMENSIONS_YAML.write_text(body.text, encoding="utf-8")
            elif name == "ranking":
                PR.ranking_config(body.text)
                PR.RANKING_YAML.write_text(body.text, encoding="utf-8")
            else:
                raise HTTPException(404)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"Can't read these rules: {e}")
        changed()
        return {"ok": True}

    # ------------------------------------------------------- import/export
    @app.post("/api/import/preview")
    async def import_preview(file: UploadFile = File(...), sheet: str | None = Form(None)):
        data = await file.read()
        sheets = None
        if file.filename.lower().endswith((".xlsx", ".xls")):
            sheets = list_sheets(io.BytesIO(data))
            if not sheet:
                sheet = next((x for x in sheets if "job" in x.lower()), sheets[0])
        try:
            tidy = read_tracker(io.BytesIO(data), sheet, filename=file.filename)
        except ValueError as e:
            raise HTTPException(422, str(e))
        prev = tidy.head(8).copy()
        return {"sheets": sheets, "sheet": sheet, "rows": int(len(tidy)), "columns": list(tidy.columns),
                "preview": records(prev), "missing_dates": int(tidy["date_applied"].isna().sum())}

    @app.post("/api/import")
    async def do_import(file: UploadFile = File(...), sheet: str | None = Form(None), replace: bool = Form(False)):
        data = await file.read()
        tidy = read_tracker(io.BytesIO(data), sheet or None, filename=file.filename)
        if replace:
            svc.store.clear()
        n = import_into(svc.store, tidy)
        changed()
        return {"imported": n}

    @app.get("/api/export.xlsx")
    def export():
        s = snap()
        blob = export_excel(s.df, s.events)
        return Response(blob, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="job-applications-{date.today()}.xlsx"'})

    @app.get("/api/backup")
    def backup():
        return FileResponse(svc.db_path, filename="tracker.db")

    @app.post("/api/sample")
    def load_sample():
        n = import_into(svc.store, read_tracker(SAMPLE))
        changed()
        return {"imported": n}

    @app.delete("/api/applications")
    def clear_all(confirm: str = ""):
        if confirm != "DELETE":
            raise HTTPException(422, "Pass confirm=DELETE to delete everything.")
        svc.store.clear()
        changed()
        return {"ok": True}

    # ------------------------------------------------------------ profile, fit and AI
    def ollama_client(s=None) -> Ollama:
        st = svc.settings()
        return Ollama(st.get("ollama_url"), st.get("ollama_model"))

    def ready_client() -> Ollama:
        """The configured Ollama model, or a 503 explaining what's missing."""
        client = ollama_client()
        status = client.status()
        if not (status["available"] and status["model"]):
            raise HTTPException(503, status.get("error") or "Ollama isn't available.")
        client.model = status["model"]
        return client

    def source_for(kind: str, ref_id: int) -> dict:
        s = snap()
        if kind == "application":
            row = get_app_row(ref_id)
            return {"company": row["company"], "position": row["position"], "location": clean(row.get("location")),
                    "jd": clean(row.get("job_description")) or "", "region": row["region"]}
        if kind == "opportunity":
            opp = svc.store.opportunities()
            r = opp[opp["id"] == ref_id]
            if r.empty:
                raise HTTPException(404, "Saved job not found")
            r = r.iloc[0]
            loc = clean(r.get("location"))
            return {"company": r["company"], "position": r["position"], "location": loc,
                    "jd": clean(r.get("job_description")) or "", "region": s.cat.region(loc) if loc else None}
        raise HTTPException(404)

    # Your profile: entries if you have them, otherwise the uploaded CV without contact details.
    def entry_rows() -> list[dict]:
        return svc.store.rows("entries", order="position, id")

    def profile_material() -> str:
        rows = entry_rows()
        if rows:
            return EN.to_text(rows)
        from .evidence import PERSONAL
        cv = svc.settings().get("cv_text") or ""
        return "\n".join(ln for ln in cv.splitlines() if not PERSONAL.search(ln))

    def has_profile() -> bool:
        return len(profile_material().strip()) >= 50

    def sync_evidence() -> None:
        rows = entry_rows()
        if rows:
            svc.store.replace_entry_evidence(EN.evidence(rows, snap().inferer))

    def ensure_evidence() -> list[dict]:
        from .evidence import EXTRACTOR_VERSION
        ev = svc.store.evidence()
        if entry_rows():
            if not ev:
                sync_evidence()
                ev = svc.store.evidence()
            return ev
        cv = svc.settings().get("cv_text") or ""
        outdated = svc.store.get_setting("evidence_extractor", 0) != EXTRACTOR_VERSION
        if (not ev or outdated) and len(cv.strip()) >= 50:
            svc.store.replace_cv_evidence(extract_evidence(cv, snap().inferer))
            svc.store.set_setting("evidence_extractor", EXTRACTOR_VERSION)
            ev = svc.store.evidence()
        return ev

    def fit_inputs_hash(jd: str) -> str:
        st = svc.settings()
        return text_hash("fit-v10", profile_material(), jd, json.dumps(st.get("profile"), sort_keys=True))

    def run_fit(company: str, position: str, jd: str, region: str | None, engine: str | None = None) -> dict:
        """Instant, explainable fit from rules (no AI): requirements, evidence from your profile, blockers."""
        if not has_profile():
            raise HTTPException(422, "Add your experience under Me first.")
        if len((jd or "").strip()) < 80:
            raise HTTPException(422, "Paste the full job description first.")
        res = analyse_keywords(profile_material(), jd, svc.settings()["profile"], snap().inferer, region)
        res["company"], res["position"], res["region"] = company, position, region
        return res

    def quick_fit(kind: str, ref_id: int) -> None:
        """Instant fit so every saved job is ranked right away; also queues background reading. Never raises."""
        try:
            src = source_for(kind, ref_id)
            if len(src["jd"].strip()) < 80:
                return
            if has_profile():
                res = run_fit(src["company"], src["position"], src["jd"], src["region"])
                svc.store.save_result(kind, ref_id, "fit", res, "keywords", None, fit_inputs_hash(src["jd"]))
            if svc.settings().get("digest_auto") and ollama_ok.get("ok"):
                queue_digest([(kind, ref_id)])
        except Exception:  # noqa: BLE001
            pass

    @app.get("/api/ai/status")
    def ai_status():
        st = svc.settings()
        status = ollama_client().status()
        ollama_ok["ok"] = status["available"]
        return {**status, "url": st.get("ollama_url"), "speed": svc.store.get_setting("ai_speed"),
                "has_profile": has_profile(), "has_cv": has_profile(), "cv_filename": st.get("cv_filename"),
                "entries": len(entry_rows()), "digest_auto": bool(st.get("digest_auto"))}

    @app.post("/api/profile/cv")
    async def upload_cv(file: UploadFile = File(...)):
        """Read a CV file. With no entries yet, it's split into entries straight away for you to tidy."""
        data = await file.read()
        try:
            text = extract_text(file.filename, data)
        except ValueError as e:
            raise HTTPException(422, str(e))
        svc.store.set_setting("cv_text", text)
        svc.store.set_setting("cv_filename", file.filename)
        made = 0
        if not entry_rows():
            made = save_entries(EN.from_cv(text, snap().inferer))
        else:
            changed()
        return {"chars": len(text), "filename": file.filename, "entries_created": made}

    # ------------------------------------------------------------- entries (Me)
    def save_entries(items: list[dict]) -> int:
        start = len(entry_rows())
        for i, e in enumerate(items):
            data = {k: e.get(k) for k in ("section", "title", "org", "location", "start", "end", "details")}
            data["section"] = data["section"] if data["section"] in EN.SECTIONS else "other"
            svc.store.add_row("entries", **data, position=start + i)
        sync_evidence()
        changed()
        return len(items)

    @app.get("/api/entries")
    def list_entries():
        st = svc.settings()
        return {"entries": entry_rows(), "sections": EN.SECTIONS, "has_cv": len((st.get("cv_text") or "").strip()) >= 50,
                "cv_filename": st.get("cv_filename")}

    @app.post("/api/entries")
    def add_entry(body: EntryIn):
        data = body.model_dump(exclude={"entries", "text", "replace"})
        if data.get("section") not in EN.SECTIONS:
            raise HTTPException(422, "Unknown section")
        save_entries([data])
        return {"ok": True, "entries": entry_rows()}

    @app.post("/api/entries/bulk")
    def add_entries(body: EntryIn):
        if body.replace:
            for e in entry_rows():
                svc.store.delete_row("entries", e["id"])
        return {"created": save_entries(body.entries or []), "entries": entry_rows()}

    @app.patch("/api/entries/{eid}")
    def edit_entry(eid: int, body: EntryIn):
        svc.store.update_row("entries", eid, **body.model_dump(exclude_unset=True, exclude={"entries", "text", "replace"}))
        sync_evidence()
        changed()
        return {"ok": True}

    @app.delete("/api/entries/{eid}")
    def del_entry(eid: int):
        svc.store.delete_row("entries", eid)
        sync_evidence()
        changed()
        return {"ok": True}

    @app.post("/api/entries/reorder")
    def reorder_entries(body: EntryIn):
        for i, eid in enumerate(body.ids or []):
            svc.store.update_row("entries", int(eid), position=i)
        sync_evidence()
        changed()
        return {"ok": True}

    @app.post("/api/entries/split")
    def split_entries(body: EntryIn):
        """Draft entries from a pasted block; nothing is saved until you confirm."""
        return {"drafts": EN.split_text(body.section or "experience", body.text or "")}

    @app.post("/api/entries/from-cv")
    def entries_from_cv(body: EntryIn):
        cv = svc.settings().get("cv_text") or ""
        if len(cv.strip()) < 50:
            raise HTTPException(422, "Upload a CV first.")
        drafts = EN.from_cv(cv, snap().inferer)
        if body.replace is None:  # preview only
            return {"drafts": drafts}
        if body.replace:
            for e in entry_rows():
                svc.store.delete_row("entries", e["id"])
        return {"created": save_entries(drafts), "entries": entry_rows()}

    @app.get("/api/profile/text")
    def profile_text():
        return {"text": profile_material()}

    # ------------------------------------------------------------- background jobs (Ollama)
    jobs = AIJobs(on_change=lambda: changed())
    ollama_ok: dict = {}

    def save_speed(client: Ollama | None) -> None:
        st = getattr(client, "last_stats", None)
        if not st or not st.get("gen_tps"):
            return
        old = svc.store.get_setting("ai_speed") or {}
        if old.get("model") == st["model"] and old.get("gen_tps"):
            st = {**st, "gen_tps": round(0.6 * st["gen_tps"] + 0.4 * old["gen_tps"], 2)}
            if old.get("prompt_tps") and st.get("prompt_tps"):
                st["prompt_tps"] = round(0.6 * st["prompt_tps"] + 0.4 * old["prompt_tps"], 1)
        svc.store.set_setting("ai_speed", st)

    def submit_ai(key: str, label: str, task, priority: int = INTERACTIVE, group: str = "", meta: dict | None = None,
                  client: Ollama | None = None) -> dict:
        """Queue `task(client, progress)` as a background job using the configured Ollama model."""
        client = client or ready_client()

        def fn(progress):
            with use_progress(progress):
                try:
                    return task(client, progress)
                finally:
                    save_speed(client)
        return jobs.submit(key, label, fn, priority=priority, group=group, meta=meta)

    @app.get("/api/ai/jobs")
    def list_jobs(active: bool = False):
        return {"jobs": jobs.list(active_only=active), "speed": svc.store.get_setting("ai_speed")}

    @app.get("/api/ai/jobs/{job_id}")
    def get_job(job_id: int):
        j = jobs.get(job_id)
        if not j:
            raise HTTPException(404, "This task is no longer known (the app may have restarted).")
        return j

    @app.delete("/api/ai/jobs/{job_id}")
    def cancel_job(job_id: int):
        j = jobs.cancel(job_id)
        if not j:
            raise HTTPException(404)
        return j

    @app.post("/api/ai/benchmark")
    def benchmark():
        """A short generation to measure how fast this computer runs the model."""
        def task(client, progress):
            progress.step("Measuring speed", 1, 1, 120)
            client.chat_json("Answer in JSON.", "List eight common fruits with one short fact each.",
                             {"type": "object", "properties": {"fruits": {"type": "array", "items": {"type": "object",
                              "properties": {"name": {"type": "string"}, "fact": {"type": "string"}}}}}},
                             num_predict=160)
            return client.last_stats
        return submit_ai("benchmark", "Speed test", task)

    # Reading job descriptions in the background: one short summary per description, cached by content.
    def all_jds() -> list[tuple[str, int, str, str]]:
        out = []
        df = snap().df
        if not df.empty:
            for r in df[df["has_jd"]].itertuples():
                out.append(("application", int(r.id), r.company, clean(getattr(r, "job_description", None)) or ""))
        for r in svc.store.opportunities("saved").itertuples():
            jd = clean(r.job_description) or ""
            if len(jd.strip()) >= 80:
                out.append(("opportunity", int(r.id), r.company, jd))
        return out

    def digest_done(kind: str, ref_id: int, jd: str) -> bool:
        r = svc.store.get_result(kind, ref_id, "digest")
        return bool(r and r["input_hash"] == DG.jd_hash(jd))

    def queue_digest(items: list[tuple[str, int]] | None = None) -> int:
        client = ready_client()
        todo = [(k, i, c, jd) for k, i, c, jd in all_jds() if (items is None or (k, i) in items) and not digest_done(k, i, jd)]
        for kind, ref, company, jd in todo:
            def task(cl, progress, kind=kind, ref=ref, jd=jd):
                progress.step("Reading the job description", 1, 1, DG.EXPECTED_TOKENS)
                res = DG.read(jd, cl)
                svc.store.save_result(kind, ref, "digest", res, "ollama", cl.model, DG.jd_hash(jd))
                return {"skills": len(res["skills"])}
            submit_ai(f"digest:{kind}:{ref}", f"Reading · {company}", task, priority=BATCH, group="digest",
                      meta={"kind": kind, "ref_id": ref}, client=client)
        return len(todo)

    def digest_status() -> dict:
        jds = all_jds()
        done = sum(1 for k, i, _, jd in jds if digest_done(k, i, jd))
        active = jobs.list(active_only=True, group="digest")
        sp = svc.store.get_setting("ai_speed") or {}
        per = None
        if sp.get("gen_tps"):
            per = DG.EXPECTED_TOKENS / sp["gen_tps"] + (1200 / sp["prompt_tps"] if sp.get("prompt_tps") else 15)
        left = len(jds) - done
        return {"total": len(jds), "done": done, "queued": len(active), "seconds_each": round(per) if per else None,
                "eta_minutes": round(left * per / 60) if per and left else None,
                "running": next((j["label"] for j in active if j["status"] == "running"), None),
                "auto": bool(svc.settings().get("digest_auto"))}

    @app.get("/api/digest")
    def get_digest():
        return digest_status()

    @app.post("/api/digest/run")
    def run_digest():
        n = queue_digest()
        return {**digest_status(), "queued_now": n}

    @app.delete("/api/digest/run")
    def stop_digest():
        jobs.cancel_group("digest")
        return digest_status()

    # ------------------------------------------------------------- fit
    @app.get("/api/fit/{kind}/{ref_id}")
    def get_fit(kind: str, ref_id: int):
        src = source_for(kind, ref_id)
        cached = svc.store.get_result(kind, ref_id, "fit")
        rank = svc.store.get_result(kind, ref_id, "chat_rank")
        base = {"has_jd": len(src["jd"].strip()) >= 80, "rank": rank["result"] if rank else None}
        if not cached:
            return {"result": None, **base}
        return {**cached, **base, "stale": cached["input_hash"] != fit_inputs_hash(src["jd"])}

    @app.post("/api/fit/{kind}/{ref_id}")
    def post_fit(kind: str, ref_id: int, body: FitRun):
        src = source_for(kind, ref_id)
        res = run_fit(src["company"], src["position"], src["jd"], src["region"])
        svc.store.save_result(kind, ref_id, "fit", res, res["method"], None, fit_inputs_hash(src["jd"]))
        rank = svc.store.get_result(kind, ref_id, "chat_rank")
        return {"result": res, "method": res["method"], "stale": False, "has_jd": True, "rank": rank["result"] if rank else None}

    @app.post("/api/fit/check")
    def fit_check(body: FitCheck):
        s = snap()
        region = s.cat.region(body.location) if body.location else None
        return run_fit(body.company or "", body.position or "", body.job_description, region)

    @app.post("/api/fit/batch")
    def fit_batch(body: BatchIn):
        if body.kind == "opportunity":
            ids = svc.store.opportunities("saved")["id"].tolist()
        else:
            df = snap().df
            ids = df[df["active"] & df["has_jd"]]["id"].tolist()
        done = skipped = 0
        errors = []
        for i in ids:
            src = source_for(body.kind, int(i))
            if len(src["jd"].strip()) < 80:
                skipped += 1
                continue
            cached = svc.store.get_result(body.kind, int(i), "fit")
            if body.only_missing and cached and cached["input_hash"] == fit_inputs_hash(src["jd"]):
                skipped += 1
                continue
            try:
                res = run_fit(src["company"], src["position"], src["jd"], src["region"])
            except HTTPException as e:
                errors.append(str(e.detail))
                break
            svc.store.save_result(body.kind, int(i), "fit", res, res["method"], None, fit_inputs_hash(src["jd"]))
            done += 1
        return {"analysed": done, "skipped": skipped, "errors": errors[:3]}

    # ------------------------------------------------------------- chat assistant: ranking and prompts
    def rank_fields() -> list[dict]:
        try:
            return PR.ranking_config()["fields"]
        except (ValueError, yaml.YAMLError):
            return []  # a broken file never blocks ranking; Settings shows the error when you save it

    @app.get("/api/rank/config")
    def rank_config():
        try:
            cfg = PR.ranking_config()
        except (ValueError, yaml.YAMLError) as e:
            cfg = {"default_criteria": "", "fields": [], "error": str(e)}
        return {**cfg, "goals": svc.settings().get("rank_goals") or ""}

    @app.post("/api/rank/prompt")
    def rank_prompt(body: RankIn):
        if not has_profile():
            raise HTTPException(422, "Add your experience under Me first.")
        inbox = svc.store.opportunities("saved")
        ranks = svc.store.results("opportunity", "chat_rank")
        ranked = sum(1 for i in inbox["id"].tolist() if i in ranks)
        items = body.items or []
        no_description = 0
        if not items:  # default: everything in the Inbox that hasn't been ranked yet
            for r in inbox.itertuples():
                if r.id in ranks and not body.include_ranked:
                    continue
                if len((clean(r.job_description) or "").strip()) < 80:
                    no_description += 1
                    continue
                items.append({"kind": "opportunity", "ref_id": int(r.id)})
        jobs_ = []
        for it in items:
            src = source_for(it["kind"], int(it["ref_id"]))
            jobs_.append({"code": PR.code(it["kind"], int(it["ref_id"])), **src})
        if body.goals is not None:  # your criteria are kept privately in the database, prefilled next time
            svc.store.set_setting("rank_goals", body.goals)
        chunks = PR.split_jobs(jobs_)
        fields = rank_fields()
        parts = []
        for n, chunk in enumerate(chunks, 1):
            text = PR.rank_prompt(profile_material(), svc.settings()["profile"], chunk, body.goals or "", fields, (n, len(chunks)))
            parts.append({"prompt": text, "count": len(chunk), "chars": len(text), "codes": [j["code"] for j in chunk]})
        svc.store.set_setting("rank_parts", [p["codes"] for p in parts])
        svc.store.set_setting("rank_last_codes", [c for p in parts for c in p["codes"]])
        return {"prompt": parts[0]["prompt"] if parts else "", "parts": parts, "count": len(jobs_),
                "chars": sum(p["chars"] for p in parts), "skipped": 0, "ranked": ranked, "no_description": no_description}

    @app.post("/api/rank/import")
    def rank_import(body: RankIn):
        parsed = PR.parse_ranking(body.text or "", rank_fields())
        if not parsed:
            raise HTTPException(422, "Couldn't find any rankings in that text. Paste the assistant's whole reply, "
                                     "including the job codes like S7 or A12.")
        saved, unknown = [], []
        stamp = datetime.now().isoformat(timespec="minutes")
        for p in parsed:
            try:
                src = source_for(p["kind"], p["ref_id"])
            except HTTPException:
                unknown.append(p["code"])
                continue
            svc.store.save_result(p["kind"], p["ref_id"], "chat_rank", {**p, "at": stamp}, "chat", None, None)
            saved.append({**p, "company": src["company"], "position": src["position"]})
        changed()
        got = {p["code"] for p in parsed}
        # Which prompt was this reply for? The part whose job codes it overlaps most (replies come back one part at a time).
        parts = svc.settings().get("rank_parts") or []
        asked = max(parts, key=lambda c: len(set(c) & got), default=[]) if parts else []
        if not (set(asked) & got):
            asked = svc.settings().get("rank_last_codes") or []
        return {"saved": saved, "unknown": unknown, "not_in_reply": [c for c in asked if c not in got],
                "unscored": [p["code"] for p in saved if p["score"] is None]}

    @app.get("/api/prompts/{kind}/{ref_id}/{ptype}")
    def job_prompt(kind: str, ref_id: int, ptype: str):
        if ptype not in PR.CRITIQUES:
            raise HTTPException(404)
        if not has_profile():
            raise HTTPException(422, "Add your experience under Me first.")
        src = source_for(kind, ref_id)
        fit = (svc.store.get_result(kind, ref_id, "fit") or {}).get("result")
        st = svc.settings()
        return {"title": PR.CRITIQUES[ptype][0],
                "prompt": PR.job_prompt(ptype, profile_material(), st["profile"], src, fit, st.get("writing"))}

    @app.get("/api/evidence")
    def list_evidence():
        ev = ensure_evidence()
        return {"items": ev, "has_cv": has_profile()}

    # -------------------------------------------------------- career development
    INTERVIEW_ROUNDS = ["Recruiter screen", "First interview", "Technical interview", "Case interview",
                        "Assessment centre", "Panel", "Final interview", "Informal chat", "Other"]
    FORMATS = ["Phone", "Video", "On-site", "Take-home task", "Recorded video"]

    def interview_list() -> list[dict]:
        ivs = svc.store.rows("interviews", order="date DESC, id DESC")
        qs = svc.store.rows("interview_questions", order="interview_id, position")
        by = {}
        for q in qs:
            by.setdefault(q["interview_id"], []).append(q)
        for i in ivs:
            i["questions"] = by.get(i["id"], [])
        return ivs

    def clean_questions(qs: list[dict] | None) -> list[dict]:
        out = []
        for q in qs or []:
            text = (q.get("question") or "").strip()
            if not text:
                continue
            out.append({"id": q.get("id"), "question": text, "category": q.get("category") or CR.categorise(text),
                        "competencies": q.get("competencies") or CR.competencies(text + " " + (q.get("answer_notes") or "")),
                        "rating": q.get("rating"), "answer_notes": q.get("answer_notes"), "story_id": q.get("story_id")})
        return out

    @app.get("/api/career/meta")
    def career_meta():
        s = snap()
        apps = [{"id": int(r.id), "company": r.company, "position": r.position, "status": r.status}
                for r in s.df.sort_values("date_applied", ascending=False).itertuples()] if not s.df.empty else []
        return {"categories": CR.CATEGORIES, "competencies": list(CR.COMPETENCIES), "rounds": INTERVIEW_ROUNDS,
                "formats": FORMATS, "outcomes": ["Waiting", "Passed", "Rejected", "Withdrew"], "applications": apps,
                "industries": s.inferer.options("industry")}

    @app.post("/api/career/categorise")
    def categorise_q(body: dict):
        text = body.get("question", "")
        return {"category": CR.categorise(text), "competencies": CR.competencies(text)}

    @app.get("/api/career/interviews")
    def list_interviews():
        s = snap()
        ivs = interview_list()
        return {"interviews": ivs, "themes": CR.themes(ivs, [q for i in ivs for q in i["questions"]], svc.store.rows("stories")),
                "to_log": CR.interviews_to_log(s.df, svc.store.events(), ivs)}

    def iv_fill(data: dict) -> dict:
        if data.get("application_id"):
            row = get_app_row(int(data["application_id"]))
            data.setdefault("company", row["company"])
            data.setdefault("position", row["position"])
            data["company"] = data.get("company") or row["company"]
            data["position"] = data.get("position") or row["position"]
        return data

    @app.post("/api/career/interviews")
    def add_interview(body: InterviewIn):
        data = iv_fill(body.model_dump(exclude={"questions"}))
        if not data.get("company"):
            raise HTTPException(422, "Pick the application or type the company.")
        data["date"] = data.get("date") or date.today().isoformat()
        iid = svc.store.add_row("interviews", **data)
        svc.store.set_questions(iid, clean_questions(body.questions))
        changed()
        return {"id": iid}

    @app.patch("/api/career/interviews/{iid}")
    def edit_interview(iid: int, body: InterviewIn):
        data = body.model_dump(exclude_unset=True, exclude={"questions"})
        svc.store.update_row("interviews", iid, **iv_fill(data))
        if body.questions is not None:
            svc.store.set_questions(iid, clean_questions(body.questions))
        changed()
        return {"ok": True}

    @app.delete("/api/career/interviews/{iid}")
    def del_interview(iid: int):
        svc.store.delete_row("interviews", iid)
        changed()
        return {"ok": True}

    # Stories
    @app.get("/api/career/stories")
    def list_stories():
        stories = svc.store.rows("stories", order="updated_at DESC")
        qs = svc.store.rows("interview_questions")
        ivs = {i["id"]: i for i in svc.store.rows("interviews")}
        for st in stories:
            used = [q for q in qs if q.get("story_id") == st["id"]]
            st["used"] = [{"question": q["question"], "company": ivs.get(q["interview_id"], {}).get("company"),
                           "rating": q.get("rating")} for q in used]
            st["tips"] = CR.story_check(st)
        return {"stories": stories, "suggestions": CR.suggest_stories(ensure_evidence(), stories)}

    @app.post("/api/career/stories")
    def add_story(body: StoryIn):
        data = body.model_dump()
        if data.get("evidence_id") and not data.get("title"):
            ev = next((e for e in svc.store.evidence() if e["id"] == data["evidence_id"]), None)
            if ev:
                data["title"] = ev["text"][:80]
                data["action"] = data.get("action") or ev["text"]
                data["situation"] = data.get("situation") or ev.get("context")
                data["result"] = data.get("result") or ev.get("outcome")
                data["competencies"] = data.get("competencies") or CR.competencies(ev["text"])
                data["skills"] = data.get("skills") or ev.get("skills")
        if not (data.get("title") or "").strip():
            raise HTTPException(422, "Give the story a short title.")
        if data.get("competencies") is None:
            data["competencies"] = CR.competencies(" ".join(str(data.get(k) or "") for k in ("title", "situation", "task", "action", "result")))
        sid = svc.store.add_row("stories", **data)
        changed()
        return {"id": sid}

    @app.patch("/api/career/stories/{sid}")
    def edit_story(sid: int, body: StoryIn):
        svc.store.update_row("stories", sid, **body.model_dump(exclude_unset=True))
        changed()
        return {"ok": True}

    @app.delete("/api/career/stories/{sid}")
    def del_story(sid: int):
        svc.store.delete_row("stories", sid)
        changed()
        return {"ok": True}

    # Practice
    def practice_context():
        s = snap()
        ivs = interview_list()
        qs = [q for i in ivs for q in i["questions"]]
        stories = svc.store.rows("stories")
        theme = CR.themes(ivs, qs, stories)
        upcoming = CR.upcoming_interviews(s.df, svc.store.events())
        profiles = {}
        for u in upcoming:
            jd = clean(get_app_row(u["application_id"]).get("job_description")) or ""
            if len(jd) >= 80:
                profiles[u["application_id"]] = B.job_profile(jd, s.inferer)
        return ivs, qs, stories, theme, upcoming, profiles

    @app.get("/api/career/practice")
    def practice():
        ivs, qs, stories, theme, upcoming, profiles = practice_context()
        done = svc.store.rows("practice", order="updated_at DESC")
        suggested = CR.practice_set(ivs, qs, stories, upcoming, profiles, theme, done)
        ai_sets = {}
        for u in upcoming:
            r = svc.store.get_result("application", u["application_id"], "practice_questions")
            if r:
                ai_sets[u["application_id"]] = r["result"]
        return {"suggested": suggested, "history": done[:30], "upcoming": upcoming, "focus": theme["focus"],
                "ai_sets": ai_sets}

    def feedback_for(pid: int, engine: str | None = None):
        p = next((x for x in svc.store.rows("practice") if x["id"] == pid), None)
        if not p:
            raise HTTPException(404)
        if not (p.get("answer") or "").strip():
            raise HTTPException(422, "Write your answer first.")
        rules = CR.answer_feedback(p["question"], p["answer"], p.get("category"))
        svc.store.update_row("practice", pid, feedback=rules)
        return {"feedback": rules}

    @app.post("/api/career/practice")
    def add_practice(body: PracticeIn):
        if not (body.question or "").strip():
            raise HTTPException(422, "Write the question.")
        data = body.model_dump(exclude={"engine"})
        data["category"] = data.get("category") or CR.categorise(data["question"])
        pid = svc.store.add_row("practice", **data)
        out = {"id": pid}
        if (body.answer or "").strip():
            out.update(feedback_for(pid, body.engine))
        changed()
        return out

    @app.patch("/api/career/practice/{pid}")
    def edit_practice(pid: int, body: PracticeIn):
        svc.store.update_row("practice", pid, **body.model_dump(exclude_unset=True, exclude={"engine"}))
        out = {"id": pid}
        if body.answer is not None and body.answer.strip():
            out.update(feedback_for(pid, body.engine))
        changed()
        return out

    @app.delete("/api/career/practice/{pid}")
    def del_practice(pid: int):
        svc.store.delete_row("practice", pid)
        changed()
        return {"ok": True}

    @app.get("/api/career/practice/{pid}")
    def get_practice(pid: int):
        p = next((x for x in svc.store.rows("practice") if x["id"] == pid), None)
        if not p:
            raise HTTPException(404)
        return p

    # Skills report
    @app.get("/api/career/skills")
    def skills_report(request: Request):
        return skills_report_data(dict(request.query_params))

    def skills_report_data(params: dict):
        s = snap()
        st = s.settings
        df = apply_filters(s.df, params) if not s.df.empty else s.df
        jobs_ = []
        for r in df.itertuples():
            jobs_.append({"key": f"application:{r.id}", "company": r.company, "position": r.position, "kind": "application",
                          "jd": clean(getattr(r, "job_description", None)) or "", "date": r.date_applied.date()})
        opp = svc.store.opportunities("saved")
        for r in opp.itertuples():
            created = pd.to_datetime(r.created_at).date() if r.created_at else None
            jobs_.append({"key": f"opportunity:{r.id}", "company": r.company, "position": r.position, "kind": "opportunity",
                          "jd": clean(r.job_description) or "", "date": created})
        have = {x.strip().lower() for x in st.get("my_skills", [])}
        material = profile_material()
        for skill in s.inferer.analyse_jd(material).skills:
            have.add(skill.lower())
        for e in svc.store.evidence(include_hidden=False):
            have.update(x.lower() for x in e.get("skills", []))
        fits = {}
        for kind in ("application", "opportunity"):
            for ref, f in svc.store.results(kind, "fit").items():
                key = f"{kind}:{ref}"
                if any(j["key"] == key for j in jobs_):
                    fits[key] = f["result"]
        digests = 0
        rank = {st_: i for i, st_ in enumerate(REACHED_ORDER)}
        furthest = dict(zip(df["id"], df["furthest_stage"])) if not df.empty else {}
        groups: dict[str, dict[str, dict]] = {"industry": {}, "seniority": {}}
        for j in jobs_:
            kind, ref = j["key"].split(":")
            d = svc.store.get_result(kind, int(ref), "digest")
            if d and d["input_hash"] == DG.jd_hash(j["jd"]):
                j["extra_skills"] = d["result"].get("skills", [])
                digests += 1
                if kind == "application":
                    stage_rank = rank.get(furthest.get(int(ref)), 0)
                    for g in groups:
                        label = (d["result"].get(g) or "").strip() or "Unclear"
                        row = groups[g].setdefault(label, {"label": label, "applied": 0, "responses": 0, "interviews": 0})
                        row["applied"] += 1
                        row["responses"] += stage_rank >= 1
                        row["interviews"] += stage_rank >= 2
        rep = CR.skills_report(jobs_, s.inferer, have, fits, material=material)
        rep["digests"] = digests
        for g, rows in groups.items():
            out = sorted(rows.values(), key=lambda r: (-r["applied"], r["label"]))
            for r in out:
                r["interview_rate"] = r["interviews"] / r["applied"] if r["applied"] else 0
                r["response_rate"] = r["responses"] / r["applied"] if r["applied"] else 0
            rep[f"by_{g}"] = out[:12]
        rep["cv_has_text"] = bool(material)
        return rep

    # Industry notes
    @app.get("/api/career/notes")
    def list_notes():
        s = snap()
        notes = svc.store.rows("notes", order="updated_at DESC")
        stats = {}
        if not s.df.empty:
            for ind, g in s.df.groupby("industry"):
                j = A.judged(g, int(s.settings.get("too_new_days", 21)))
                stats[ind] = {"applications": int(len(g)), "responses": int(g["responded"].sum()),
                              "interviews": int(g["reached_interview"].sum()),
                              "response_rate": round(float(j["responded"].mean()), 2) if len(j) else None}
        return {"notes": notes, "industry_stats": stats}

    @app.post("/api/career/notes")
    def add_note(body: NoteIn):
        if not (body.title or "").strip():
            raise HTTPException(422, "Give the note a title.")
        nid = svc.store.add_row("notes", **body.model_dump())
        changed()
        return {"id": nid}

    @app.patch("/api/career/notes/{nid}")
    def edit_note(nid: int, body: NoteIn):
        svc.store.update_row("notes", nid, **body.model_dump(exclude_unset=True))
        changed()
        return {"ok": True}

    @app.delete("/api/career/notes/{nid}")
    def del_note(nid: int):
        svc.store.delete_row("notes", nid)
        changed()
        return {"ok": True}

    # -------------------------------------------------------- opportunities

    def opp_records(status: str | None = "saved") -> list[dict]:
        opp = svc.store.opportunities(status)
        fits = svc.store.results("opportunity", "fit")
        ranks = svc.store.results("opportunity", "chat_rank")
        out = []
        for r in records(opp):
            f = fits.get(r["id"])
            jd = r.get("job_description") or ""
            r["fit"] = None
            if f:
                res = f["result"]
                r["fit"] = {"score": res.get("score"), "action": res["recommendation"]["action"],
                            "why": res["recommendation"]["why"], "method": f["method"],
                            "blockers": [b for b in res.get("blockers", []) if b["severity"] == "high"],
                            "counts": res.get("counts"), "stale": f["input_hash"] != fit_inputs_hash(jd)}
            r["has_jd"] = len(jd.strip()) >= 80
            rk = ranks.get(r["id"])
            r["rank"] = rk["result"] if rk else None
            r.pop("job_description", None)
            out.append(r)
        return out

    @app.get("/api/opportunities")
    def list_opps(status: str = "saved"):
        return opp_records(None if status == "all" else status)

    @app.get("/api/opportunities/{opp_id}")
    def get_opp(opp_id: int):
        opp = svc.store.opportunities()
        r = opp[opp["id"] == opp_id]
        if r.empty:
            raise HTTPException(404)
        item = records(r)[0]
        item["fit"] = (svc.store.get_result("opportunity", opp_id, "fit") or {}).get("result")
        return item

    @app.post("/api/opportunities")
    def add_opp(body: OppIn):
        if not (body.company or "").strip() or not (body.position or "").strip():
            raise HTTPException(422, "Company and position are required.")
        data = body.model_dump(exclude={"fit", "status"})
        oid = svc.store.add_opportunity(data.pop("company"), data.pop("position"), **data)
        if body.fit:  # keep an analysis that was already run on the Discover page
            svc.store.save_result("opportunity", oid, "fit", body.fit, body.fit.get("method"), body.fit.get("model"),
                                  fit_inputs_hash(body.job_description or ""))
        changed()
        if not body.fit:
            quick_fit("opportunity", oid)
        return {"id": oid}

    @app.patch("/api/opportunities/{opp_id}")
    def edit_opp(opp_id: int, body: OppIn):
        upd = body.model_dump(exclude_unset=True, exclude={"fit"})
        svc.store.update_opportunity(opp_id, **upd)
        changed()
        if "job_description" in upd:
            quick_fit("opportunity", opp_id)
        return get_opp(opp_id)

    @app.delete("/api/opportunities/{opp_id}")
    def del_opp(opp_id: int):
        svc.store.delete_opportunity(opp_id)
        changed()
        return {"ok": True}

    @app.post("/api/opportunities/batch")
    def batch_opps(body: OppBatchIn):
        if body.action not in ("archive", "restore", "delete", "apply"):
            raise HTTPException(422, "Unknown action")
        done = 0
        for oid in body.ids:
            if body.action == "delete":
                svc.store.delete_opportunity(oid)
            elif body.action == "apply":
                apply_opp(oid)
            else:
                svc.store.update_opportunity(oid, status="archived" if body.action == "archive" else "saved")
            done += 1
        changed()
        return {"count": done}

    @app.post("/api/opportunities/{opp_id}/apply")
    def apply_opp(opp_id: int):
        o = get_opp(opp_id)
        app_id = svc.store.add_application(o["company"], o["position"], date.today(), location=o.get("location"),
                                           url=o.get("url"), source=o.get("source"), notes=o.get("notes"),
                                           job_description=o.get("job_description"), workload=o.get("workload"),
                                           contract=o.get("contract"))
        for task in ("fit", "cv_builder", "letter_builder", "practice_questions"):
            r = svc.store.get_result("opportunity", opp_id, task)
            if r:
                svc.store.save_result("application", app_id, task, r["result"], r["method"], r["model"], r["input_hash"])
        svc.store.update_opportunity(opp_id, status="applied", application_id=app_id)
        with svc.store._conn() as c:  # practice answers written for the saved job follow it
            c.execute("UPDATE practice SET ref = ? WHERE ref = ?", (f"application:{app_id}", f"opportunity:{opp_id}"))
        changed()
        return {"application_id": app_id}

    # ------------------------------------------------------------ batch actions and undo
    @app.post("/api/applications/batch")
    def batch_apps(body: BatchAppsIn):
        if body.action == "delete":
            for i in body.ids:
                svc.store.delete_application(i)
            changed()
            return {"count": len(body.ids), "event_ids": []}
        if body.action not in STAGES:
            raise HTTPException(422, "Unknown action")
        eids = []
        for i in body.ids:
            get_app_row(i)
            eids.append(svc.store.move_stage(i, body.action, date.today(), None))
        changed()
        return {"count": len(eids), "event_ids": eids}

    @app.post("/api/events/undo")
    def undo_events(body: UndoIn):
        undone = 0
        for eid in body.event_ids:
            try:
                svc.store.delete_event(eid)
                undone += 1
            except (KeyError, ValueError):
                pass
        changed()
        return {"undone": undone}

    # ------------------------------------------------------------ bookmark inbox
    @app.post("/inbox", include_in_schema=False)
    async def inbox(request: Request):
        """Receives a job posting from the 'Send to Job Tracker' bookmark (a normal form POST, so it works from any site)."""
        form = await request.form()
        import secrets
        iid = secrets.token_urlsafe(8)
        text = str(form.get("text") or "")[:60000]
        svc.store.add_inbox(iid, str(form.get("title") or "")[:300], str(form.get("url") or "")[:1000], text)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"/?inbox={iid}", status_code=303)

    @app.get("/api/inbox/{iid}")
    def get_inbox(iid: str):
        item = svc.store.get_inbox(iid)
        if not item:
            raise HTTPException(404, "This posting has expired. Send it again.")
        raw = clean_posting(item["text"] or "")
        ex = P.extract(raw, item.get("title"), places())
        text, _ = P.clean(raw)
        guess = {k: ex[k] for k in ("position", "company", "location", "workload", "contract", "deadline")}
        return {**item, "text": text, "guess": guess, "confidence": ex["confidence"]}

    @app.get("/api/bookmarklet")
    def bookmarklet(request: Request):
        base = str(request.base_url).rstrip("/")
        js = ("(()=>{const s=String(getSelection()).trim();const t=(s.length>200?s:document.body.innerText).slice(0,60000);"
              "const f=document.createElement('form');f.method='POST';f.action='" + base + "/inbox';f.target='_blank';"
              "f.acceptCharset='utf-8';f.style.display='none';"
              "for(const [k,v] of Object.entries({text:t,title:document.title,url:location.href}))"
              "{const i=document.createElement('textarea');i.name=k;i.value=v;f.appendChild(i);}"
              "document.body.appendChild(f);f.submit();f.remove();})()")
        return {"href": "javascript:" + js, "base": base}

    # ------------------------------------------------------------ momentum, milestones, wrapped, map
    def fun_inputs():
        s = snap()
        ivs = svc.store.rows("interviews")
        return (s, svc.store.events(), ivs, svc.store.rows("interview_questions"), svc.store.rows("practice"),
                svc.store.rows("stories"))

    @app.get("/api/momentum")
    def get_momentum():
        s, ev, ivs, qs, pr, st = fun_inputs()
        return FUN.momentum(s.df, ev, ivs, pr, st, int(s.settings.get("weekly_goal", 5)))

    @app.get("/api/milestones")
    def get_milestones():
        s, ev, ivs, qs, pr, st = fun_inputs()
        mom = FUN.momentum(s.df, ev, ivs, pr, st, int(s.settings.get("weekly_goal", 5)))
        items = FUN.milestones(s.df, ev, ivs, qs, pr, st, mom)
        seen = svc.store.get_setting("milestones_seen")
        achieved = [m["id"] for m in items if m["achieved"]]
        if seen is None:  # first run: don't celebrate everything that already happened
            svc.store.set_setting("milestones_seen", achieved)
            seen = achieved
        return {"items": items, "new": [m for m in items if m["achieved"] and m["id"] not in seen]}

    @app.post("/api/milestones/seen")
    def milestones_seen(body: SeenIn):
        seen = set(svc.store.get_setting("milestones_seen") or [])
        svc.store.set_setting("milestones_seen", sorted(seen | set(body.ids)))
        return {"ok": True}

    @app.get("/api/analytics/companies")
    def companies(request: Request):
        s = snap()
        df = apply_filters(s.df, dict(request.query_params)) if not s.df.empty else s.df
        return FUN.company_replies(df)

    @app.get("/api/map")
    def get_map(request: Request):
        s = snap()
        df = apply_filters(s.df, dict(request.query_params)) if not s.df.empty else s.df
        return FUN.map_points(df)

    # ------------------------------------------------------------ prepare checklist
    INTERVIEW_STATUSES = {"Screening", "Interview", "Final interview", "Offer", "Accepted"}

    @app.get("/api/prepare/{kind}/{ref_id}")
    def prepare_state(kind: str, ref_id: int):
        """Fit → Apply → Interview → Journal for one job."""
        src = source_for(kind, ref_id)
        has_jd = len(src["jd"].strip()) >= 80
        fit = svc.store.get_result(kind, ref_id, "fit")
        rank = svc.store.get_result(kind, ref_id, "chat_rank")
        fres = (fit or {}).get("result") or {}
        steps = [{"id": "fit", "label": "Fit", "done": bool(fit), "stale": bool(fit and fit["input_hash"] != fit_inputs_hash(src["jd"])),
                  "score": fres.get("score"), "action": (fres.get("recommendation") or {}).get("action"),
                  "rank": rank["result"] if rank else None}]
        if kind == "application":
            row = get_app_row(ref_id)
            at_interview = row["status"] in INTERVIEW_STATUSES or clean(row.get("furthest_stage")) in INTERVIEW_STATUSES
            practised = [p for p in svc.store.rows("practice") if p.get("ref") == f"application:{ref_id}"]
            logged = [i for i in svc.store.rows("interviews") if i.get("application_id") == ref_id]
            steps += [{"id": "apply", "label": "Apply", "done": True, "date": str(row["date_applied"])[:10],
                       "cv_version": clean(row.get("cv_version"))},
                      {"id": "interview", "label": "Interview", "done": bool(practised), "relevant": at_interview,
                       "practised": len(practised)},
                      {"id": "journal", "label": "Journal", "done": bool(logged), "relevant": at_interview, "count": len(logged)}]
        else:
            o = get_opp(ref_id)
            practised = [p for p in svc.store.rows("practice") if p.get("ref") == f"opportunity:{ref_id}"]
            steps += [{"id": "apply", "label": "Apply", "done": False, "deadline": o.get("deadline")},
                      {"id": "interview", "label": "Interview", "done": bool(practised), "relevant": False, "practised": len(practised)},
                      {"id": "journal", "label": "Journal", "done": False, "relevant": False, "count": 0}]
        return {"kind": kind, "id": ref_id, "has_jd": has_jd, "steps": steps, "has_profile": has_profile()}

    @app.get("/api/prepare/{kind}/{ref_id}/interview")
    def prepare_interview(kind: str, ref_id: int):
        src = source_for(kind, ref_id)
        ivs, qs, stories, theme, _upcoming, _profiles = practice_context()
        ref = f"{kind}:{ref_id}"
        status = get_app_row(ref_id)["status"] if kind == "application" else "Saved"
        u = {"application_id": ref_id, "company": src["company"], "position": src["position"], "ref": ref,
             "stage": status if status in INTERVIEW_STATUSES else "interview", "date": None, "when": "coming up"}
        profiles = {ref_id: B.job_profile(src["jd"], snap().inferer)} if len(src["jd"]) >= 80 else {}
        done = svc.store.rows("practice", order="updated_at DESC")
        own = [q for q in CR.practice_set(ivs, qs, stories, [u], profiles, theme, [], limit=20) if q.get("ref") == ref][:8]
        return {"suggested": own, "practised": [p for p in done if p.get("ref") == ref],
                "interviews": [i for i in interview_list() if kind == "application" and i.get("application_id") == ref_id],
                "stories": stories}

    # ------------------------------------------------------------ frontend
    if (WEB_DIR / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            target = WEB_DIR / path
            if path and target.is_file():
                return FileResponse(target)
            return FileResponse(WEB_DIR / "index.html")

    return app


# A rough guess at title and company from the first lines of a pasted posting, to save typing.
START_MARKERS = re.compile(r"^\s*(about the job|job description|the role|about the role|role description|your role|"
                           r"stellenbeschreibung|ihre aufgaben|your responsibilities|what you will do|position summary)\s*:?\s*$",
                           re.I | re.M)
END_MARKERS = re.compile(r"^\s*(show less|see less|about the company|similar jobs|people also viewed|more jobs|"
                         r"set alert for similar jobs|report this job|apply now|share this job|jobs you may be interested in|"
                         r"über uns)\s*$", re.I | re.M)


def clean_posting(text: str) -> str:
    """Cut a whole web page down to the job posting when the usual headings are there."""
    t = re.sub(r"\r", "", text or "")
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    m = START_MARKERS.search(t)
    if m and m.start() < len(t) * 0.8:
        t = t[m.start():]
    e = END_MARKERS.search(t, min(200, len(t) // 3))
    if e:
        t = t[:e.start()]
    return t.strip()


def title_guess(title: str) -> dict:
    return P.title_from_page(title)


def guess_title_company(jd: str) -> dict:
    ex = P.extract(jd)
    return {"position": ex["position"], "company": ex["company"]}
