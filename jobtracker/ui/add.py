"""Add an application, with live detection from the job description."""

from __future__ import annotations

from datetime import date

import streamlit as st

from jobtracker.storage import SOURCES

from .common import Ctx, pct

FIELDS = ["company", "position", "location", "posted", "applied", "source", "contact", "url", "cv", "fit",
          "salary", "notes", "jd"]


def _reset() -> None:
    for f in FIELDS:
        st.session_state.pop(f"add_{f}", None)


def page(ctx: Ctx) -> None:
    st.title("Add application")
    if msg := st.session_state.pop("add_done", None):
        st.success(msg)

    left, right = st.columns([3, 2])
    with left:
        c1, c2 = st.columns(2)
        company = c1.text_input("Company *", key="add_company")
        position = c2.text_input("Position *", key="add_position")
        location = c1.text_input("Location", key="add_location", placeholder="e.g. Basel")
        source = c2.selectbox("Channel", ["—"] + SOURCES, key="add_source")
        posted = c1.date_input("Date posted", None, key="add_posted", format="DD.MM.YYYY",
                               help="When the job went up. Used to see whether applying early helps.")
        applied = c2.date_input("Date applied", date.today(), key="add_applied", format="DD.MM.YYYY")
        contact = c1.text_input("Contact / hiring manager", key="add_contact")
        url = c2.text_input("Link to posting", key="add_url")
        cv = c1.text_input("CV version", key="add_cv", placeholder="e.g. Clinical v2")
        fit = c2.select_slider("How well do you fit? (1–5)", ["Not rated", 1, 2, 3, 4, 5], key="add_fit")
        salary = c1.text_input("Salary", key="add_salary")
        notes = c2.text_input("Notes", key="add_notes")
        jd = st.text_area("Job description", key="add_jd", height=260,
                          placeholder="Paste the full job posting here. The app picks out skills, seniority, "
                                      "language and work permit requirements.")

    with right:
        st.markdown("#### Detected")
        if company or position or jd:
            inf = ctx.inferer.infer_all(position, company, jd)
            rows = {
                "Job family": ctx.cat.role_area(position),
                "Location group": ctx.cat.region(location),
                "Seniority": inf["seniority"],
                "Industry": inf["industry"],
                "Company size": inf["company_size"],
                "Work permit": inf["work_authorization"],
                "Language": inf["language"],
                "Work mode": "Remote" if "remote" in (location or "").lower() else inf["work_mode"],
            }
            st.table({"": list(rows.keys()), "Detected": list(rows.values())})
            if inf["min_years"] is not None:
                st.caption(f"Asks for {inf['min_years']}+ years of experience.")
            if inf["jd_skills"]:
                mine = {s.lower() for s in ctx.my_skills}
                if mine:
                    have = [s for s in inf["jd_skills"] if s.lower() in mine]
                    st.metric("Skills match", pct(len(have) / len(inf["jd_skills"])))
                st.caption("Skills found: " + ", ".join(inf["jd_skills"]))
            st.caption("You can correct any of these after saving, on the Applications page.")
        else:
            st.caption("Start typing to see what the app detects.")

        if company and position:
            dup = ctx.df[(ctx.df["company"].str.lower() == company.strip().lower())
                         & (ctx.df["position"].str.lower() == position.strip().lower())]
            if not dup.empty:
                st.warning(f"You already applied to this role on {dup['date_applied'].iloc[0]:%d %b %Y}.")
            prev = ctx.df[ctx.df["company"].str.lower() == company.strip().lower()]
            if not prev.empty and dup.empty:
                st.info(f"{len(prev)} earlier application(s) to {company}: "
                        + ", ".join(f"{r.position} ({r.status})" for r in prev.head(3).itertuples()))

    c1, c2, _ = st.columns([1, 1, 4])
    if c1.button("Add application", type="primary"):
        if not company.strip() or not position.strip():
            st.error("Company and position are required.")
        else:
            ctx.store.add_application(
                company, position, applied, location=location, source=None if source == "—" else source,
                date_posted=posted, contact=contact, url=url, cv_version=cv,
                fit_rating=None if fit == "Not rated" else fit, salary=salary, notes=notes, job_description=jd)
            _reset()
            st.session_state["add_done"] = f"Added {position} at {company}."
            st.rerun()
    if c2.button("Clear"):
        _reset()
        st.rerun()
