"""HTTP API for the Job Tracker web app (FastAPI). The built React app is served from jobtracker/web."""

from __future__ import annotations

import io
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
from .categorise import Categoriser, save_yaml
from .dimensions import DimensionInferer
from .importer import export_excel, import_into, list_sheets, read_tracker
from .service import CATEGORIES_YAML, DIMENSIONS_YAML, SAMPLE, Service, apply_filters
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
            "settings": s.settings,
        }

    # -------------------------------------------------------- applications
    @app.get("/api/applications")
    def list_applications(request: Request):
        d = filtered(request).sort_values(["date_applied", "id"], ascending=False)
        return {"items": records(d, LIST_FIELDS), "total": int(len(snap().df))}

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
        svc.store.move_stage(app_id, body.stage, body.date or date.today(), body.note or None)
        changed()
        return get_application(app_id)


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


    @app.post("/api/parse")
    def parse(body: ParseIn):
        """Live preview of what will be inferred for a new application."""
        s = snap()
        inf = s.inferer.infer_all(body.position, body.company, body.job_description)
        mine = {x.lower() for x in s.settings["my_skills"]}
        skills = inf["jd_skills"]
        work_mode = "Remote" if "remote" in (body.location or "").lower() else inf["work_mode"]
        df = s.df
        dup = df[(df["company"].str.lower() == (body.company or "").strip().lower())
                 & (df["position"].str.lower() == (body.position or "").strip().lower())] if body.company else df.iloc[0:0]
        prev = df[df["company"].str.lower() == (body.company or "").strip().lower()] if body.company else df.iloc[0:0]
        guess = guess_title_company(body.job_description or "")
        return {
            "role_area": s.cat.role_area(body.position) if body.position else None,
            "region": s.cat.region(body.location) if body.location else None,
            "seniority": inf["seniority"], "industry": inf["industry"], "company_size": inf["company_size"],
            "work_authorization": inf["work_authorization"], "language": inf["language"], "work_mode": work_mode,
            "min_years": inf["min_years"],
            "skills": [{"skill": k, "have": k.lower() in mine} for k in skills],
            "match": (sum(k.lower() in mine for k in skills) / len(skills)) if (skills and mine) else None,
            "duplicate": records(dup, ["id", "position", "status", "date_applied"]),
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
            svc.store.move_stage(item["application_id"], "Ghosted", date.today(), "No reply")
        elif body.action == "followed_up":
            row = get_app_row(item["application_id"])
            svc.store.move_stage(item["application_id"], row["status"], date.today(), "Followed up")
        elif body.action == "done":
            if item["kind"] == "reminder":
                svc.store.update_reminder(item["reminder_id"], done=True)
            else:
                svc.store.snooze_notification(body.key, None, dismiss=True)
        else:
            raise HTTPException(422, "Unknown action")
        changed()
        return {"ok": True}

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
        for k, v in body.items():
            if k in svc.settings():
                svc.store.set_setting(k, v)
        changed()
        return svc.settings()

    @app.get("/api/rules/{name}")
    def get_rules(name: str):
        path = {"categories": CATEGORIES_YAML, "dimensions": DIMENSIONS_YAML}.get(name)
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
def guess_title_company(jd: str) -> dict:
    import re

    lines = [ln.strip(" \t•-–|") for ln in jd.strip().splitlines() if ln.strip()][:8]
    title = company = None
    for ln in lines:
        m = re.match(r"^(?:job title|position|role|title)\s*[:\-]\s*(.+)$", ln, re.I)
        if m and not title:
            title = m.group(1).strip()
        m = re.match(r"^(?:company|employer|organisation|organization)\s*[:\-]\s*(.+)$", ln, re.I)
        if m and not company:
            company = m.group(1).strip()
    if not title and lines and len(lines[0]) <= 90 and not lines[0].endswith("."):
        title = lines[0]
    patterns = [
        r"^([A-Z][\w&.'\- ]{1,40}?)\s+(?:is|are)\s+(?:hiring|looking|seeking|searching|recruiting)\b",
        r"^About\s+([A-Z][\w&.'\- ]{1,40}?)\s*$",
        r"\b(?:at|join|joining)\s+([A-Z][\w&.'\-]+(?: [A-Z][\w&.'\-]+){0,3})(?:[,.!]| is | as | we | and | to |$)",
    ]
    for pat in patterns:
        if company:
            break
        m = re.search(pat, jd, re.M)
        if m:
            company = m.group(1).strip()
    return {"position": title, "company": company}
