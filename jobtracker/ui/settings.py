"""Settings: your profile, goals and the categorisation rules."""

from __future__ import annotations

import streamlit as st
import yaml

from jobtracker.categorise import Categoriser
from jobtracker.dimensions import DimensionInferer

from .common import CATEGORIES_YAML, DIMENSIONS_YAML, Ctx


def page(ctx: Ctx) -> None:
    st.title("Settings")
    tab1, tab2, tab3 = st.tabs(["Profile & goals", "Job family & location rules", "Dimension & skill rules"])
    with tab1:
        profile(ctx)
    with tab2:
        category_rules(ctx)
    with tab3:
        dimension_rules(ctx)


def profile(ctx: Ctx) -> None:
    s = ctx.settings
    st.subheader("Your skills")
    st.caption("Used to score how well each job description matches you. Saved only in your local database, "
               "never in the repo.")
    known = sorted(ctx.inferer.skill_groups, key=str.lower)
    current = [x for x in s["my_skills"] if x in known]
    extra_now = [x for x in s["my_skills"] if x not in known]
    with st.form("profile"):
        picked = st.multiselect("Skills from the list", known, default=current)
        extra = st.text_input("Other skills (comma-separated)", ", ".join(extra_now),
                              help="Terms not in the list. To have them detected in job descriptions too, add them "
                                   "to the skills list under Dimension & skill rules.")
        st.subheader("Goals and reminders")
        c1, c2 = st.columns(2)
        goal = c1.number_input("Weekly application goal", 1, 100, int(s["weekly_goal"]))
        too_new = c2.number_input("Days before an unanswered application counts in the scorecard", 0, 90,
                                  int(s["too_new_days"]))
        fu = c1.number_input("Suggest a follow-up after (days idle)", 3, 60, int(s["follow_up_after"]))
        gh = c2.number_input("Suggest 'ghosted' after (days with no reply)", 14, 180, int(s["ghost_after"]))
        if st.form_submit_button("Save", type="primary"):
            skills = picked + [x.strip() for x in extra.split(",") if x.strip()]
            for k, v in {"my_skills": skills, "weekly_goal": goal, "too_new_days": too_new,
                         "follow_up_after": fu, "ghost_after": gh}.items():
                ctx.store.set_setting(k, v)
            st.session_state["flash"] = "Settings saved"
            st.rerun()


def category_rules(ctx: Ctx) -> None:
    st.write("Job family and location group come from keyword rules on the job title and location. Rules are "
             "checked top to bottom and the first match wins. You can also override a single application.")
    edited = st.text_area("categories.yaml", CATEGORIES_YAML.read_text(encoding="utf-8"), height=420, key="cat_yaml")
    try:
        trial = Categoriser.from_dict(yaml.safe_load(edited) or {})
    except Exception as e:  # noqa: BLE001
        st.error(f"Can't read these rules: {e}")
        return
    df = ctx.df
    if not df.empty:
        prev = df[["position", "role_area"]].copy()
        prev["new"] = prev["position"].map(trial.role_area)
        changed = prev[prev["role_area"] != prev["new"]]
        other = prev[prev["new"] == trial.default_role_area]
        c1, c2 = st.columns(2)
        c1.metric("Titles that would change job family", len(changed))
        c2.metric(f"Titles left in '{trial.default_role_area}'", len(other))
        if not other.empty:
            with st.expander(f"Uncategorised titles ({len(other)}): add keywords for these"):
                st.dataframe(other[["position"]].drop_duplicates(), hide_index=True, width="stretch")
    if st.button("Save job family rules", type="primary"):
        from jobtracker.categorise import save_yaml
        save_yaml(trial, CATEGORIES_YAML)
        st.session_state["flash"] = "Rules saved"
        st.rerun()


def dimension_rules(ctx: Ctx) -> None:
    st.write("Rules for seniority, industry, company size, work permit, language, work mode and the skills list. "
             "Add companies you apply to often under `industries` and `company_size`.")
    edited = st.text_area("dimensions.yaml", DIMENSIONS_YAML.read_text(encoding="utf-8"), height=480, key="dim_yaml")
    try:
        cfg = yaml.safe_load(edited) or {}
        trial = DimensionInferer(cfg)
    except Exception as e:  # noqa: BLE001
        st.error(f"Can't read these rules: {e}")
        return
    df = ctx.df
    if not df.empty:
        unknown = df[[trial.industry(c, j) == "Unknown" for c, j in zip(df["company"], df["job_description"])]]
        st.metric("Companies with unknown industry", unknown["company"].nunique())
        if not unknown.empty:
            with st.expander("Companies to add to the industry list"):
                st.dataframe(unknown["company"].value_counts().rename_axis("Company").reset_index(name="Applications"),
                             hide_index=True, width="stretch")
    if st.button("Save dimension rules", type="primary"):
        DIMENSIONS_YAML.write_text(edited, encoding="utf-8")
        st.session_state["flash"] = "Rules saved"
        st.rerun()
