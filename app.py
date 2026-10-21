"""Job Tracker — Streamlit app.

Run with:  python -m streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Job Tracker", page_icon="📋", layout="wide")

from jobtracker.importer import import_into, read_tracker  # noqa: E402
from jobtracker.ui import (  # noqa: E402
    add, applications, dashboard, data, followups, jd_insights, scorecard, settings,
)
from jobtracker.ui.common import DB_PATH, ROOT, SAMPLE, build_ctx  # noqa: E402

PAGES = {
    "Dashboard": dashboard.page,
    "Scorecard": scorecard.page,
    "Applications": applications.page,
    "Add application": add.page,
    "Follow-ups": followups.page,
    "Job descriptions": jd_insights.page,
    "Import & export": data.page,
    "Settings": settings.page,
}
NEEDS_DATA = {"Dashboard", "Scorecard", "Applications", "Follow-ups", "Job descriptions"}

ctx = build_ctx()

st.sidebar.title("📋 Job Tracker")
fu_count = 0
if not ctx.df.empty:
    from jobtracker import analysis as A

    fu_count = len(A.follow_ups(ctx.df, int(ctx.settings["follow_up_after"]), int(ctx.settings["ghost_after"])))
labels = {p: (f"{p} ({fu_count})" if p == "Follow-ups" and fu_count else p) for p in PAGES}
page = st.sidebar.radio("Go to", list(PAGES), format_func=labels.get, label_visibility="collapsed", key="nav")
st.sidebar.divider()
try:
    shown = DB_PATH.relative_to(ROOT)
except ValueError:
    shown = DB_PATH
st.sidebar.caption(f"{len(ctx.df)} applications · data in `{shown}`")

if msg := st.session_state.pop("flash", None):
    st.toast(msg)

if ctx.df.empty and page in NEEDS_DATA:
    st.title("Welcome 👋")
    st.write("No applications yet. Import your existing tracker, add one by hand, or load fictional sample data "
             "to look around.")
    if st.button("Load sample data", type="primary"):
        import_into(ctx.store, read_tracker(SAMPLE))
        st.rerun()
    st.info("Use **Import & export** in the sidebar to bring in your Excel or CSV tracker.")
    st.stop()

PAGES[page](ctx)
