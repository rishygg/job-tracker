"""Job Tracker — Streamlit app.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

from jobtracker import analysis as A
from jobtracker.categorise import DEFAULT_CONFIG, Categoriser, save_yaml
from jobtracker.importer import import_into, list_sheets, read_tracker
from jobtracker.storage import SOURCES, STAGES, Store

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("JOBTRACKER_DB", ROOT / "data" / "tracker.db"))
SAMPLE = ROOT / "sample_data" / "sample_applications.csv"

OUTCOME_COLORS = {
    "Offer": "#1b7f5c", "Interviewed": "#3aa17e", "Rejected": "#b8b8c4",
    "Ghosted": "#e0a43a", "Waiting": "#4a78c2", "Withdrawn": "#8e8e99",
}
OUTCOME_ORDER = ["Offer", "Interviewed", "Rejected", "Ghosted", "Withdrawn", "Waiting"]
GROUP_LABELS = {"role_area": "Role area", "region": "Location", "source": "Source", "company": "Company"}

st.set_page_config(page_title="Job Tracker", page_icon="📋", layout="wide")


# ---------------------------------------------------------------- data ----
@st.cache_resource
def get_store() -> Store:
    return Store(DB_PATH)


def get_categoriser() -> Categoriser:
    return Categoriser.from_yaml(DEFAULT_CONFIG)


def load() -> pd.DataFrame:
    store = get_store()
    return A.enrich(store.applications(), store.events(), get_categoriser(), date.today())


def txt(v) -> str:
    """Display-safe string: missing values (None/NaN) become ''."""
    return "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)


def pct(x) -> str:
    return "–" if pd.isna(x) else f"{x:.0%}"


store = get_store()
cat = get_categoriser()

# ------------------------------------------------------------- sidebar ----
st.sidebar.title("📋 Job Tracker")
page = st.sidebar.radio(
    "Go to", ["Dashboard", "Applications", "Add application", "Follow-ups", "Import", "Categories"],
    label_visibility="collapsed",
)
st.sidebar.divider()
follow_up_after = st.sidebar.number_input("Follow up after (days)", 3, 60, 10)
ghost_after = st.sidebar.number_input("Suggest 'ghosted' after (days)", 14, 180, 42)
st.sidebar.caption(f"Data file: `{DB_PATH.relative_to(ROOT) if DB_PATH.is_relative_to(ROOT) else DB_PATH}`")

df = load()

if df.empty and page not in ("Import", "Add application", "Categories"):
    st.title("Welcome 👋")
    st.write("You have no applications yet. Import your existing tracker, add one by hand, "
             "or load the sample data to look around.")
    c1, c2 = st.columns(2)
    if c1.button("Load sample data", type="primary"):
        tidy = read_tracker(SAMPLE)
        import_into(store, tidy)
        st.rerun()
    c2.info("Use **Import** in the sidebar to bring in your Excel or CSV tracker.")
    st.stop()


# ----------------------------------------------------------- dashboard ----
def page_dashboard(df: pd.DataFrame) -> None:
    st.title("Dashboard")

    with st.expander("Filters", expanded=False):
        c1, c2, c3 = st.columns(3)
        dmin, dmax = df["date_applied"].min().date(), df["date_applied"].max().date()
        rng = c1.date_input("Applied between", (dmin, dmax), min_value=dmin, max_value=dmax)
        areas = c2.multiselect("Role area", sorted(df["role_area"].unique()))
        regions = c3.multiselect("Location", sorted(df["region"].unique()))
    d = df
    if isinstance(rng, tuple) and len(rng) == 2:
        d = d[(d["date_applied"].dt.date >= rng[0]) & (d["date_applied"].dt.date <= rng[1])]
    if areas:
        d = d[d["role_area"].isin(areas)]
    if regions:
        d = d[d["region"].isin(regions)]
    if d.empty:
        st.warning("No applications match these filters.")
        return

    m = st.columns(5)
    m[0].metric("Applications", len(d))
    m[1].metric("Got a response", pct(d["responded"].mean()))
    m[2].metric("Reached interview", int(d["reached_interview"].sum()),
                help="Applications that got to an interview or further, even if later rejected.")
    m[3].metric("Ghosted", int((d["status"] == "Ghosted").sum()))
    m[4].metric("Still active", int(d["active"].sum()))

    st.subheader("Takeaways")
    for line in A.insights(d):
        st.markdown(f"- {line}")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Funnel")
        f = A.funnel(d)
        fig = go.Figure(go.Funnel(y=f["step"], x=f["count"], textinfo="value+percent initial",
                                  marker_color="#4a78c2"))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Applications per month")
        mo = A.monthly(d)
        cols = [c for c in OUTCOME_ORDER if c in mo.columns]
        long = mo.melt(id_vars="month", value_vars=cols, var_name="outcome", value_name="n")
        fig = px.bar(long, x="month", y="n", color="outcome", color_discrete_map=OUTCOME_COLORS,
                     category_orders={"outcome": OUTCOME_ORDER}, labels={"n": "Applications", "month": ""})
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320, legend_title_text="")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Where you're getting traction")
    by = st.radio("Break down by", list(GROUP_LABELS), format_func=GROUP_LABELS.get, horizontal=True)
    b = A.breakdown(d, by)
    if by == "company":
        b = b[b["applied"] >= 2]
    c1, c2 = st.columns([3, 2])
    with c1:
        show = b.copy()
        for col in ["response_rate", "interview_rate", "ghost_rate"]:
            show[col] = show[col].map(pct)
        show["interview 95% range"] = [f"{lo:.0%}–{hi:.0%}" for lo, hi in
                                      zip(b["interview_rate_low"], b["interview_rate_high"])]
        show = show.rename(columns={by: GROUP_LABELS[by]})[
            [GROUP_LABELS[by], "applied", "responses", "response_rate", "interviews", "interview_rate",
             "interview 95% range", "ghosted", "ghost_rate", "waiting"]]
        st.dataframe(show, hide_index=True, width="stretch")
        st.caption("Response rate = any reply (incl. rejections) ÷ applied. Ghost rate = ghosted ÷ applications "
                   "no longer active. The 95% range shows how uncertain the interview rate is with few applications.")
    with c2:
        top = b.sort_values("applied", ascending=False).head(12).sort_values("response_rate")
        fig = go.Figure()
        fig.add_bar(y=top[by], x=top["response_rate"], name="Response rate", orientation="h",
                    marker_color="#b8c9e8")
        fig.add_bar(y=top[by], x=top["interview_rate"], name="Interview rate", orientation="h",
                    marker_color="#1b7f5c")
        fig.update_layout(barmode="group", height=max(260, 34 * len(top)), margin=dict(l=0, r=0, t=10, b=0),
                          xaxis_tickformat=".0%", legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, width="stretch")

    rt = A.response_time_stats(d, "role_area")
    if not rt.empty:
        st.subheader("How long replies take")
        st.dataframe(rt.round(1), hide_index=True, width="stretch")
        st.caption("Only counts stage changes you logged with their real date (imported history has no reply dates).")


# -------------------------------------------------------- applications ----
def page_applications(df: pd.DataFrame) -> None:
    st.title("Applications")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q = c1.text_input("Search", placeholder="Company, role, location…")
    status = c2.multiselect("Status", STAGES)
    area = c3.multiselect("Role area", sorted(df["role_area"].unique()))
    region = c4.multiselect("Location", sorted(df["region"].unique()))
    d = df
    if q:
        hay = (d["company"].fillna("") + " " + d["position"].fillna("") + " " + d["location"].fillna("")).str.lower()
        d = d[hay.str.contains(q.lower(), regex=False)]
    if status:
        d = d[d["status"].isin(status)]
    if area:
        d = d[d["role_area"].isin(area)]
    if region:
        d = d[d["region"].isin(region)]

    st.caption(f"{len(d)} of {len(df)} applications")
    view = d[["id", "date_applied", "company", "position", "status", "furthest_stage", "role_area", "region",
              "location", "source", "days_since_activity"]].rename(columns={"days_since_activity": "days idle"})
    event = st.dataframe(view, hide_index=True, width="stretch", on_select="rerun",
                         selection_mode="single-row",
                         column_config={"date_applied": st.column_config.DateColumn("applied")})
    rows = event.selection.rows if event and event.selection else []
    if not rows:
        st.info("Select a row to see its history and edit it.")
        return
    app = d.iloc[rows[0]]
    edit_application(app)


def edit_application(app: pd.Series) -> None:
    app_id = int(app["id"])
    st.divider()
    st.subheader(f"{app['position']} · {app['company']}")
    left, right = st.columns([3, 2])
    with left, st.form(f"edit-{app_id}"):
        c1, c2 = st.columns(2)
        company = c1.text_input("Company", app["company"])
        position = c2.text_input("Position", app["position"])
        location = c1.text_input("Location", txt(app["location"]))
        applied = c2.date_input("Date applied", app["date_applied"].date())
        src_opts = [""] + SOURCES
        source = c1.selectbox("Source", src_opts, index=src_opts.index(app["source"]) if app["source"] in src_opts else 0)
        contact = c2.text_input("Contact", txt(app["contact"]))
        url = st.text_input("Link", txt(app["url"]))
        notes = st.text_area("Notes", txt(app["notes"]))
        st.markdown("**Category overrides** (leave on *Auto* to use your keyword rules)")
        c1, c2 = st.columns(2)
        ra_opts = ["Auto"] + cat.role_area_names
        rg_opts = ["Auto"] + cat.region_names
        ra = c1.selectbox("Role area", ra_opts, index=ra_opts.index(app["role_area_override"])
                          if app["role_area_override"] in ra_opts else 0)
        rg = c2.selectbox("Location group", rg_opts, index=rg_opts.index(app["region_override"])
                          if app["region_override"] in rg_opts else 0)
        if st.form_submit_button("Save changes", type="primary"):
            store.update_application(app_id, company=company, position=position, location=location or None,
                                     date_applied=applied, source=source or None, contact=contact or None,
                                     url=url or None, notes=notes or None,
                                     role_area_override=None if ra == "Auto" else ra,
                                     region_override=None if rg == "Auto" else rg)
            st.toast("Saved")
            st.rerun()
    with right:
        st.markdown(f"**Current status:** {app['status']}  \n**Furthest stage:** {app['furthest_stage']}")
        with st.form(f"stage-{app_id}"):
            c1, c2 = st.columns(2)
            stage = c1.selectbox("Move to stage", STAGES, index=STAGES.index(app["status"]))
            when = c2.date_input("On", date.today())
            note = st.text_input("Note (optional)")
            if st.form_submit_button("Record stage"):
                store.move_stage(app_id, stage, when, note or None)
                st.toast(f"Moved to {stage}")
                st.rerun()
        hist = store.events(app_id)[["date", "stage", "note"]]
        hist["date"] = hist["date"].dt.date
        st.dataframe(hist, hide_index=True, width="stretch")
        if st.button("Delete application", key=f"del-{app_id}"):
            st.session_state[f"confirm-{app_id}"] = True
        if st.session_state.get(f"confirm-{app_id}"):
            st.warning("Delete this application and its history?")
            if st.button("Yes, delete", key=f"yes-{app_id}", type="primary"):
                store.delete_application(app_id)
                st.session_state.pop(f"confirm-{app_id}")
                st.rerun()


# ----------------------------------------------------------------- add ----
def page_add() -> None:
    st.title("Add application")
    with st.form("add", clear_on_submit=True):
        c1, c2 = st.columns(2)
        company = c1.text_input("Company *")
        position = c2.text_input("Position *")
        location = c1.text_input("Location", placeholder="e.g. Basel")
        applied = c2.date_input("Date applied", date.today())
        source = c1.selectbox("Source", [""] + SOURCES)
        contact = c2.text_input("Contact / hiring manager")
        url = st.text_input("Link to posting or portal")
        notes = st.text_area("Notes")
        if position:
            st.caption(f"Will be categorised as **{cat.role_area(position)}** · **{cat.region(location)}**")
        if st.form_submit_button("Add", type="primary"):
            if not company.strip() or not position.strip():
                st.error("Company and position are required.")
            else:
                store.add_application(company, position, applied, location=location or None,
                                      source=source or None, contact=contact or None, url=url or None,
                                      notes=notes or None)
                st.success(f"Added {position} at {company} ({cat.role_area(position)}).")


# ----------------------------------------------------------- follow-ups ----
def page_follow_ups(df: pd.DataFrame) -> None:
    st.title("Follow-ups")
    st.caption(f"Active applications with no activity for {follow_up_after}+ days. "
               f"Applications with no reply after {ghost_after}+ days are suggested as ghosted.")
    fu = A.follow_ups(df, follow_up_after, ghost_after)
    if fu.empty:
        st.success("Nothing to chase right now.")
        return
    ghost = fu[fu["action"] == "Mark as ghosted"]
    chase = fu[fu["action"] == "Follow up"]
    for title, part in [("Worth a follow-up", chase), ("Probably ghosted", ghost)]:
        if part.empty:
            continue
        c1, c2 = st.columns([3, 1])
        c1.subheader(f"{title} ({len(part)})")
        if title == "Probably ghosted" and c2.button(f"Mark all {len(part)} as ghosted"):
            for i in part["id"]:
                store.move_stage(int(i), "Ghosted", date.today(), "No reply")
            st.rerun()
        for _, r in part.iterrows():
            c1, c2, c3, c4 = st.columns([4, 1.2, 1.2, 1.2])
            c1.markdown(f"**{r['company']}** · {r['position']}  \n"
                        f"<small>{r['status']} · {int(r['days_since_activity'])} days idle"
                        f"{' · ' + txt(r['contact']) if txt(r['contact']) else ''}</small>", unsafe_allow_html=True)
            if c2.button("Followed up", key=f"fu-{r['id']}"):
                store.move_stage(int(r["id"]), r["status"], date.today(), "Followed up")
                st.rerun()
            if c3.button("Rejected", key=f"rj-{r['id']}"):
                store.move_stage(int(r["id"]), "Rejected", date.today())
                st.rerun()
            if c4.button("Ghosted", key=f"gh-{r['id']}"):
                store.move_stage(int(r["id"]), "Ghosted", date.today())
                st.rerun()


# --------------------------------------------------------------- import ----
def page_import() -> None:
    st.title("Import")
    st.write("Bring in an existing Excel or CSV tracker. The header row and common column names "
             "(Company, Position/Role, Date Applied, Status, Location, …) are detected automatically.")
    up = st.file_uploader("Tracker file", type=["xlsx", "xls", "csv", "tsv"])
    if not up:
        return
    sheet = None
    if up.name.lower().endswith((".xlsx", ".xls")):
        sheets = list_sheets(up)
        sheet = st.selectbox("Sheet", sheets, index=next((i for i, s in enumerate(sheets) if "job" in s.lower()), 0))
        up.seek(0)
    try:
        tidy = read_tracker(up, sheet, filename=up.name)
    except ValueError as e:
        st.error(str(e))
        return
    preview = tidy.copy()
    preview["role_area"] = preview["position"].map(cat.role_area)
    preview["region"] = preview["location"].map(cat.region) if "location" in preview else cat.default_region
    st.write(f"Found **{len(tidy)}** applications. Columns detected: {', '.join(tidy.columns)}")
    st.dataframe(preview.head(50), hide_index=True, width="stretch")
    missing_dates = int(tidy["date_applied"].isna().sum())
    if missing_dates:
        st.warning(f"{missing_dates} rows have no date applied; today's date will be used.")
    replace = st.checkbox("Replace everything currently in the tracker", value=store.count() == 0)
    if st.button(f"Import {len(tidy)} applications", type="primary"):
        if replace:
            store.clear()
        n = import_into(store, tidy)
        st.success(f"Imported {n} applications.")
        st.balloons()


# ----------------------------------------------------------- categories ----
def page_categories(df: pd.DataFrame) -> None:
    st.title("Categories")
    st.write("Applications are grouped by keyword rules on the job title (role area) and location. "
             "Rules are checked top to bottom and the first match wins. Edit them below; "
             "you can also override a single application on the Applications page.")
    text = DEFAULT_CONFIG.read_text(encoding="utf-8")
    edited = st.text_area("categories.yaml", text, height=420)
    try:
        trial = Categoriser.from_dict(yaml.safe_load(edited) or {})
        ok = True
    except Exception as e:  # noqa: BLE001
        st.error(f"Can't read these rules: {e}")
        ok = False
    if ok and not df.empty:
        prev = df[["position", "location", "role_area"]].copy()
        prev["new role area"] = prev["position"].map(trial.role_area)
        changed = prev[prev["role_area"] != prev["new role area"]]
        c1, c2 = st.columns(2)
        c1.metric("Titles that would change category", len(changed))
        other = prev[prev["new role area"] == trial.default_role_area]
        c2.metric(f"Titles left in '{trial.default_role_area}'", len(other))
        if not other.empty:
            with st.expander(f"Uncategorised titles ({len(other)}) — add keywords for these"):
                st.dataframe(other[["position"]].drop_duplicates(), hide_index=True, width="stretch")
        if not changed.empty:
            with st.expander("Preview changes"):
                st.dataframe(changed, hide_index=True, width="stretch")
    if ok and st.button("Save rules", type="primary"):
        save_yaml(trial, DEFAULT_CONFIG)
        st.success("Saved. Categories are updated everywhere.")
        st.rerun()


# ---------------------------------------------------------------- router ----
if page == "Dashboard":
    page_dashboard(df)
elif page == "Applications":
    page_applications(df)
elif page == "Add application":
    page_add()
elif page == "Follow-ups":
    page_follow_ups(df)
elif page == "Import":
    page_import()
elif page == "Categories":
    page_categories(df)
