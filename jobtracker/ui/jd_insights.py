"""Job description insights: what employers ask for, and where your profile falls short."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from jobtracker import analysis as A

from .common import ACCENT, MUTED, Ctx, pct, plot_layout


def page(ctx: Ctx) -> None:
    st.title("Job description insights")
    df = ctx.df
    with_jd = df[df["has_jd"]]
    st.caption(f"Based on the {len(with_jd)} of {len(df)} applications that have a job description saved.")
    if len(with_jd) < 3:
        st.info("Paste job descriptions when you add applications (or in the details panel on the Applications "
                "page). With a handful saved, this page shows the skills employers ask for most, which ones are "
                "missing from your profile, and how language and work permit requirements affect your results.")
        return
    if not ctx.my_skills:
        st.warning("Add your skills in **Settings** to see your match score and skill gaps.")

    metric = A.METRICS["Positive response (screening or further)"]
    table = A.skills_table(with_jd, ctx.my_skills, ctx.inferer.skill_groups, metric)
    if table.empty:
        st.caption("No known skills found in your job descriptions yet.")
    else:
        top = table.head(25).sort_values("postings")
        top["status"] = top["you_have_it"].map({True: "In your profile", False: "Not in your profile"})
        fig = px.bar(top, x="share_of_postings", y="skill", color="status", orientation="h",
                     color_discrete_map={"In your profile": ACCENT, "Not in your profile": MUTED},
                     custom_data=["postings", "group"],
                     labels={"share_of_postings": "Share of postings", "skill": ""})
        fig.update_traces(hovertemplate="<b>%{y}</b> (%{customdata[1]})<br>%{customdata[0]} postings, "
                                        "%{x:.0%}<extra></extra>")
        fig.update_xaxes(tickformat=".0%")
        st.subheader("Most requested skills")
        st.plotly_chart(plot_layout(fig, max(320, 22 * len(top) + 60)), width="stretch")

        if ctx.my_skills:
            gap = table[~table["you_have_it"]].head(10)
            if not gap.empty:
                st.subheader("Skill gaps worth closing")
                st.write("Requested often but not in your profile. If you have them, add them in Settings and "
                         "make them visible on your CV; if not, they're candidates to learn.")
                st.dataframe(gap[["skill", "group", "postings", "share_of_postings"]].assign(
                    share_of_postings=gap["share_of_postings"].map(pct)).rename(columns={
                        "skill": "Skill", "group": "Area", "postings": "Postings",
                        "share_of_postings": "Share of postings"}), hide_index=True, width="stretch")

        st.subheader("Skills and your results")
        st.caption("Positive-reply rate for postings that mention each skill (at least 3 postings).")
        res = table[table["postings"] >= 3].sort_values("success_rate", ascending=False)
        st.dataframe(res[["skill", "postings", "successes", "success_rate", "you_have_it"]].assign(
            success_rate=res["success_rate"].map(pct)).rename(columns={
                "skill": "Skill", "postings": "Postings", "successes": "Positive replies",
                "success_rate": "Rate", "you_have_it": "In profile"}), hide_index=True, width="stretch")

    st.subheader("Requirements in your postings")
    c1, c2, c3 = st.columns(3)
    for col, dim, label in [(c1, "language", "Language"), (c2, "work_authorization", "Work permit"),
                            (c3, "jd_match_bucket", "Skills match")]:
        sc = A.scorecard(with_jd, dim, metric, min_n=3)
        col.markdown(f"**{label}**")
        col.dataframe(sc[["value", "applied", "successes", "rate"]].assign(rate=sc["rate"].map(pct)).rename(
            columns={"value": label, "applied": "Applied", "successes": "Positive", "rate": "Rate"}),
            hide_index=True, width="stretch")

    yrs = with_jd.dropna(subset=["min_years"])
    if len(yrs) >= 3:
        st.subheader("Experience asked for")
        fig = px.histogram(yrs, x="min_years", color="outcome", nbins=12,
                           labels={"min_years": "Minimum years asked", "count": "Postings"})
        st.plotly_chart(plot_layout(fig, 280), width="stretch")
