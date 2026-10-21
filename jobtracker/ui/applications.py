"""Applications: spreadsheet-style editing plus a detail panel per application."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from jobtracker.storage import SOURCES, STAGES

from .common import Ctx, pct, txt

DIMS = ["seniority", "industry", "company_size", "work_authorization", "language", "work_mode"]
DIM_LABELS = {
    "role_area": "Job family", "region": "Location group", "seniority": "Seniority", "industry": "Industry",
    "company_size": "Company size", "work_authorization": "Work permit", "language": "Language",
    "work_mode": "Work mode",
}
PLAIN = ["company", "position", "location", "date_applied", "date_posted", "source", "cv_version", "fit_rating",
         "contact", "url", "notes", "salary"]
GRID = ["id", "company", "position", "status", "date_applied", "date_posted", "location", "role_area", "region",
        *DIMS, "source", "cv_version", "fit_rating", "salary", "contact", "url", "notes", "furthest_stage",
        "days_since_activity"]
EDITOR_KEY = "apps_grid"


def _norm(v):
    if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        return v.strip() or None
    return v


def _column_config(ctx: Ctx) -> dict:
    inf = ctx.inferer
    sel = st.column_config.SelectboxColumn
    return {
        "id": st.column_config.NumberColumn("#", disabled=True, width="small"),
        "company": st.column_config.TextColumn("Company", required=True),
        "position": st.column_config.TextColumn("Position", required=True, width="medium"),
        "status": sel("Status", options=STAGES, required=True),
        "date_applied": st.column_config.DateColumn("Applied", format="DD.MM.YYYY"),
        "date_posted": st.column_config.DateColumn("Posted", format="DD.MM.YYYY"),
        "location": st.column_config.TextColumn("Location"),
        "role_area": sel("Job family", options=ctx.cat.role_area_names),
        "region": sel("Location group", options=ctx.cat.region_names),
        **{d: sel(DIM_LABELS[d], options=inf.options(d)) for d in DIMS},
        "source": sel("Channel", options=SOURCES),
        "cv_version": st.column_config.TextColumn("CV version"),
        "fit_rating": st.column_config.NumberColumn("Fit (1–5)", min_value=1, max_value=5, step=1),
        "salary": st.column_config.TextColumn("Salary"),
        "contact": st.column_config.TextColumn("Contact"),
        "url": st.column_config.LinkColumn("Link"),
        "notes": st.column_config.TextColumn("Notes", width="medium"),
        "furthest_stage": st.column_config.TextColumn("Furthest stage", disabled=True),
        "days_since_activity": st.column_config.NumberColumn("Days idle", disabled=True),
    }


def save_grid(ctx: Ctx, original: pd.DataFrame, edited: pd.DataFrame) -> dict:
    """Write the differences between the grid as loaded and as edited. Returns counts."""
    store, cat = ctx.store, ctx.cat
    counts = {"changed": 0, "added": 0, "deleted": 0, "skipped": 0}
    orig = original.set_index("id")
    full = ctx.df.set_index("id")
    kept = set(edited["id"].dropna().astype(int))
    for i in orig.index:
        if int(i) not in kept:
            store.delete_application(int(i))
            counts["deleted"] += 1

    for _, r in edited.iterrows():
        if pd.isna(r.get("id")):
            if not _norm(r.get("company")) or not _norm(r.get("position")):
                if any(_norm(r.get(c)) for c in ("company", "position", "location", "notes")):
                    counts["skipped"] += 1
                continue
            extra = {c: _norm(r.get(c)) for c in PLAIN if c not in ("company", "position", "date_applied")}
            for d in DIMS:
                extra[d] = _norm(r.get(d))
            extra["role_area_override"] = _norm(r.get("role_area"))
            extra["region_override"] = _norm(r.get("region"))
            store.add_application(str(r["company"]), str(r["position"]), _norm(r.get("date_applied")) or date.today(),
                                  status=_norm(r.get("status")) or "Applied", **extra)
            counts["added"] += 1
            continue

        app_id = int(r["id"])
        if app_id not in orig.index:
            continue
        o, base = orig.loc[app_id], full.loc[app_id]
        fields = {}
        for c in PLAIN:
            if c in r and _norm(r[c]) != _norm(o.get(c)):
                fields[c] = _norm(r[c])
        position = fields.get("position", o["position"])
        location = fields.get("location", o.get("location"))
        if _norm(r.get("role_area")) != _norm(o.get("role_area")):
            new = _norm(r.get("role_area"))
            fields["role_area_override"] = None if new in (None, cat.role_area(position)) else new
        if _norm(r.get("region")) != _norm(o.get("region")):
            new = _norm(r.get("region"))
            fields["region_override"] = None if new in (None, cat.region(location)) else new
        for d in DIMS:
            if _norm(r.get(d)) != _norm(o.get(d)):
                new = _norm(r.get(d))
                fields[d] = None if new in (None, base.get(f"{d}_auto")) else new
        if fields.get("company") is None and "company" in fields:
            fields.pop("company")
        if fields.get("position") is None and "position" in fields:
            fields.pop("position")
        if fields:
            store.update_application(app_id, **fields)
        new_status = _norm(r.get("status"))
        if new_status and new_status != o["status"]:
            store.move_stage(app_id, new_status, date.today())
        if fields or (new_status and new_status != o["status"]):
            counts["changed"] += 1
    return counts


def _filters(df: pd.DataFrame) -> pd.DataFrame:
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q = c1.text_input("Search", placeholder="Company, role, location, notes…", key="apps_q")
    status = c2.multiselect("Status", STAGES, key="apps_status")
    fam = c3.multiselect("Job family", sorted(df["role_area"].unique()), key="apps_fam")
    sen = c4.multiselect("Seniority", sorted(df["seniority"].unique()), key="apps_sen")
    d = df
    if q:
        hay = (d["company"].fillna("") + " " + d["position"].fillna("") + " " + d["location"].fillna("") + " "
               + d["notes"].fillna("")).str.lower()
        d = d[hay.str.contains(q.lower(), regex=False)]
    for col, sel in [("status", status), ("role_area", fam), ("seniority", sen)]:
        if sel:
            d = d[d[col].isin(sel)]
    return d


def grid(ctx: Ctx, d: pd.DataFrame) -> None:
    view = d[GRID].reset_index(drop=True)
    st.caption(f"{len(d)} of {len(ctx.df)} applications. Edit cells like a spreadsheet, add rows at the bottom, "
               "or select rows and press Delete. Changing a status records it with today's date. "
               "Save before changing filters.")
    edited = st.data_editor(view, key=EDITOR_KEY, num_rows="dynamic", hide_index=True, width="stretch",
                            height=520, column_config=_column_config(ctx), column_order=GRID)
    state = st.session_state.get(EDITOR_KEY, {})
    n_edits = len(state.get("edited_rows", {})) + len(state.get("added_rows", [])) + len(state.get("deleted_rows", []))
    c1, c2, _ = st.columns([1, 1, 4])
    if c1.button(f"Save changes ({n_edits})" if n_edits else "Save changes", type="primary", disabled=not n_edits):
        counts = save_grid(ctx, view, edited)
        st.session_state.pop(EDITOR_KEY, None)
        msg = ", ".join(f"{v} {k}" for k, v in counts.items() if v and k != "skipped") or "No changes"
        if counts["skipped"]:
            msg += f". {counts['skipped']} new rows skipped: company and position are required"
        st.session_state["flash"] = msg
        st.rerun()
    if c2.button("Discard", disabled=not n_edits):
        st.session_state.pop(EDITOR_KEY, None)
        st.rerun()


def detail(ctx: Ctx, d: pd.DataFrame) -> None:
    st.subheader("Application details")
    if d.empty:
        return
    labels = {int(r.id): f"{r.company} — {r.position} ({r.date_applied:%d %b %Y})" for r in d.itertuples()}
    app_id = st.selectbox("Open", list(labels), format_func=labels.get, key="apps_open")
    app = ctx.df.set_index("id").loc[app_id]
    tab1, tab2, tab3 = st.tabs(["Details", "Stages", "Job description analysis"])
    with tab1:
        details_form(ctx, app_id, app)
    with tab2:
        stages(ctx, app_id, app)
    with tab3:
        jd_analysis(ctx, app)


def _auto_select(col, label: str, options: list[str], current, auto: str, overridden: bool, key: str):
    auto_label = f"Auto: {auto}"
    opts = [auto_label] + [o for o in options]
    idx = opts.index(current) if overridden and current in opts else 0
    choice = col.selectbox(label, opts, index=idx, key=key)
    return None if choice == auto_label else choice


def details_form(ctx: Ctx, app_id: int, app: pd.Series) -> None:
    with st.form(f"details-{app_id}"):
        c1, c2, c3 = st.columns(3)
        company = c1.text_input("Company", app["company"])
        position = c2.text_input("Position", app["position"])
        location = c3.text_input("Location", txt(app["location"]))
        posted = c1.date_input("Date posted", None if pd.isna(app["date_posted"]) else app["date_posted"].date(),
                               format="DD.MM.YYYY")
        applied = c2.date_input("Date applied", app["date_applied"].date(), format="DD.MM.YYYY")
        src_opts = ["—"] + SOURCES
        source = c3.selectbox("Channel", src_opts, index=src_opts.index(app["source"]) if app["source"] in src_opts else 0)
        contact = c1.text_input("Contact / hiring manager", txt(app["contact"]))
        cv = c2.text_input("CV version", txt(app["cv_version"]), help="e.g. 'Data science v3' or the file name")
        fit_opts = ["Not rated", 1, 2, 3, 4, 5]
        fit = c3.selectbox("Your fit (1–5)", fit_opts,
                           index=fit_opts.index(int(app["fit_rating"])) if pd.notna(app["fit_rating"]) else 0)
        url = c1.text_input("Link", txt(app["url"]))
        salary = c2.text_input("Salary", txt(app["salary"]))

        st.markdown("**Role dimensions** · *Auto* uses the job title, company and job description.")
        c = st.columns(4)
        role_override = _auto_select(c[0], "Job family", ctx.cat.role_area_names, app["role_area"],
                                     ctx.cat.role_area(app["position"]), pd.notna(app["role_area_override"])
                                     and bool(app["role_area_override"]), f"ra-{app_id}")
        region_override = _auto_select(c[1], "Location group", ctx.cat.region_names, app["region"],
                                       ctx.cat.region(app["location"]), pd.notna(app["region_override"])
                                       and bool(app["region_override"]), f"rg-{app_id}")
        dims = {}
        stored = ctx.store.applications().set_index("id").loc[app_id]
        for i, dname in enumerate(DIMS):
            dims[dname] = _auto_select(c[(i + 2) % 4], DIM_LABELS[dname], ctx.inferer.options(dname), app[dname],
                                       app[f"{dname}_auto"], bool(txt(stored.get(dname))), f"{dname}-{app_id}")
        notes = st.text_area("Notes", txt(app["notes"]))
        jd = st.text_area("Job description", txt(app["job_description"]), height=220,
                          help="Paste the full posting. It's used to detect skills, seniority, language and "
                               "work permit requirements.")
        if st.form_submit_button("Save", type="primary"):
            ctx.store.update_application(
                app_id, company=company, position=position, location=location, date_posted=posted,
                date_applied=applied, source=None if source == "—" else source, contact=contact, cv_version=cv,
                fit_rating=None if fit == "Not rated" else fit, url=url, salary=salary, notes=notes,
                job_description=jd, role_area_override=role_override, region_override=region_override, **dims)
            st.session_state["flash"] = "Saved"
            st.rerun()


def stages(ctx: Ctx, app_id: int, app: pd.Series) -> None:
    c1, c2 = st.columns([2, 3])
    with c1:
        st.markdown(f"**Current status:** {app['status']}  \n**Furthest stage:** {app['furthest_stage']}")
        with st.form(f"stage-{app_id}"):
            stage = st.selectbox("Move to stage", STAGES, index=STAGES.index(app["status"]))
            when = st.date_input("On", date.today(), format="DD.MM.YYYY")
            note = st.text_input("Note (optional)", placeholder="e.g. Phone screen with HR")
            if st.form_submit_button("Record stage", type="primary"):
                ctx.store.move_stage(app_id, stage, when, note or None)
                st.session_state["flash"] = f"Moved to {stage}"
                st.rerun()
    with c2:
        hist = ctx.store.events(app_id)[["date", "stage", "note"]]
        hist["date"] = hist["date"].dt.strftime("%d %b %Y")
        hist["note"] = hist["note"].replace("imported", "from import")
        st.dataframe(hist.rename(columns=str.title), hide_index=True, width="stretch")
        if st.button("Delete this application", key=f"del-{app_id}"):
            st.session_state[f"confirm-{app_id}"] = True
        if st.session_state.get(f"confirm-{app_id}"):
            st.warning("Delete this application and its history? This can't be undone.")
            if st.button("Yes, delete", key=f"yes-{app_id}", type="primary"):
                ctx.store.delete_application(app_id)
                st.session_state.pop(f"confirm-{app_id}")
                st.session_state["flash"] = "Deleted"
                st.rerun()


def jd_analysis(ctx: Ctx, app: pd.Series) -> None:
    jd = txt(app["job_description"])
    if not jd.strip():
        st.info("Paste the job description in the Details tab to see skills, requirements and how well you match.")
        return
    a = ctx.inferer.analyse_jd(jd)
    mine = {s.lower() for s in ctx.my_skills}
    m = st.columns(4)
    m[0].metric("Skills match", pct(app["jd_match"]) if mine else "–",
                help="Share of skills found in the posting that are in your profile (Settings).")
    m[1].metric("Experience asked", f"{a.min_years}+ years" if a.min_years is not None else "Not stated")
    m[2].metric("Language", (a.language or "None stated").replace(" required", ""))
    m[3].metric("Work permit", a.work_authorization or "Not stated")
    if not mine:
        st.caption("Add your skills in **Settings** to get a match score.")
    if a.skills:
        have = [s for s in a.skills if s.lower() in mine]
        missing = [s for s in a.skills if s.lower() not in mine]
        c1, c2 = st.columns(2)
        c1.markdown("**You have**  \n" + (" · ".join(f"✅ {s}" for s in have) or "—"))
        c2.markdown("**Not in your profile**  \n" + (" · ".join(f"⬜ {s}" for s in missing) or "—"))
    else:
        st.caption("No known skills found. Add terms to the skills list in Settings → Rules.")
    if a.written_in_german:
        st.caption("This posting is written in German, which usually means German is expected.")
    st.caption(f"Inferred: {app['seniority_auto']} · {app['industry_auto']} · {app['work_mode_auto']}")


def page(ctx: Ctx) -> None:
    st.title("Applications")
    d = _filters(ctx.df)
    grid(ctx, d)
    st.divider()
    detail(ctx, d)
