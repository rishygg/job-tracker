"""Import, export and backup."""

from __future__ import annotations

from datetime import date

import streamlit as st

from jobtracker.importer import export_excel, import_into, list_sheets, read_tracker

from .common import DB_PATH, SAMPLE, Ctx


def page(ctx: Ctx) -> None:
    st.title("Import & export")
    tab1, tab2, tab3 = st.tabs(["Import", "Export", "Sample data"])
    with tab1:
        import_tab(ctx)
    with tab2:
        st.write("Download everything as an Excel workbook: one sheet of applications (with inferred job family, "
                 "seniority, industry, ...) and one with every stage change. The file can be imported again.")
        st.download_button("Download Excel", export_excel(ctx.df, ctx.events),
                           file_name=f"job-applications-{date.today():%Y-%m-%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           type="primary", disabled=ctx.df.empty)
        st.write("Or download the database file itself as a backup. Put it back in the `data/` folder to restore.")
        if DB_PATH.exists():
            st.download_button("Download backup (tracker.db)", DB_PATH.read_bytes(), file_name="tracker.db")
    with tab3:
        st.write("Fictional applications so you can try the app without your own data.")
        if st.button("Load sample data"):
            import_into(ctx.store, read_tracker(SAMPLE))
            st.session_state["flash"] = "Sample data loaded"
            st.rerun()
        st.divider()
        st.write("Remove all applications from the tracker.")
        if st.button("Delete all applications"):
            st.session_state["confirm_clear"] = True
        if st.session_state.get("confirm_clear"):
            st.warning(f"This deletes all {len(ctx.df)} applications and their history. Download a backup first.")
            if st.button("Yes, delete everything", type="primary"):
                ctx.store.clear()
                st.session_state.pop("confirm_clear")
                st.session_state["flash"] = "All applications deleted"
                st.rerun()


def import_tab(ctx: Ctx) -> None:
    st.write("Bring in an existing Excel or CSV tracker. The header row and common column names (Company, "
             "Position/Role, Date Applied, Date Posted, Status, Location, Job Description, …) are detected "
             "automatically.")
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
    preview.insert(2, "job family", preview["position"].map(ctx.cat.role_area))
    preview.insert(3, "seniority", [ctx.inferer.seniority(p) for p in preview["position"]])
    st.write(f"Found **{len(tidy)}** applications. Columns detected: {', '.join(tidy.columns)}")
    st.dataframe(preview.head(50), hide_index=True, width="stretch")
    missing = int(tidy["date_applied"].isna().sum())
    if missing:
        st.warning(f"{missing} rows have no date applied; today's date will be used.")
    replace = st.checkbox("Replace everything currently in the tracker", value=ctx.store.count() == 0)
    if st.button(f"Import {len(tidy)} applications", type="primary"):
        if replace:
            ctx.store.clear()
        n = import_into(ctx.store, tidy)
        st.session_state["flash"] = f"Imported {n} applications"
        st.rerun()
