"""Dashboard: headline numbers, takeaways, funnel, flow and pace."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from jobtracker import analysis as A

from .common import ACCENT, OUTCOME_COLORS, OUTCOME_ORDER, STAGE_COLORS, Ctx, pct, plot_layout


def _filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.expander("Filters", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        dmin, dmax = df["date_applied"].min().date(), df["date_applied"].max().date()
        rng = c1.date_input("Applied between", (dmin, dmax), min_value=dmin, max_value=dmax, key="dash_rng")
        fams = c2.multiselect("Job family", sorted(df["role_area"].unique()), key="dash_fam")
        sen = c3.multiselect("Seniority", sorted(df["seniority"].unique()), key="dash_sen")
        reg = c4.multiselect("Location", sorted(df["region"].unique()), key="dash_reg")
    d = df
    if isinstance(rng, tuple) and len(rng) == 2:
        d = d[(d["date_applied"].dt.date >= rng[0]) & (d["date_applied"].dt.date <= rng[1])]
    for col, sel in [("role_area", fams), ("seniority", sen), ("region", reg)]:
        if sel:
            d = d[d[col].isin(sel)]
    return d


def takeaways(ctx: Ctx, d: pd.DataFrame) -> list[str]:
    lines = A.insights(d)[:1]
    j = A.judged(d, ctx.settings["too_new_days"])
    if len(j) >= 10:
        card = A.scorecard_all(j, metric="positive")
        best, worst = A.strengths_and_gaps(card)
        if not best.empty:
            b = best.iloc[0]
            lines.append(f"Best segment so far: **{b['dimension_label']} = {b['value']}**, "
                         f"{int(b['successes'])} positive replies from {int(b['applied'])} "
                         f"({pct(b['rate'])} vs your {pct(b['overall'])} overall).")
        if not worst.empty:
            w = worst.iloc[0]
            lines.append(f"Weakest: **{w['dimension_label']} = {w['value']}**, "
                         f"{int(w['successes'])} of {int(w['applied'])}.")
    f = A.funnel_with_dropoff(d)
    steps = f[(f["from_previous"].notna()) & (f["count"].shift(1) > 0)]
    if not steps.empty:
        worst_step = steps.sort_values("from_previous").iloc[0]
        prev_step = f["step"].iloc[steps.index[steps["step"] == worst_step["step"]][0] - 1]
        lines.append(f"Biggest drop-off: **{prev_step} → {worst_step['step']}** "
                     f"(only {pct(worst_step['from_previous'])} make it through).")
    rt = d["days_to_response"].dropna()
    if len(rt) >= 5:
        lines.append(f"Replies usually come within **{rt.median():.0f} days** (based on {len(rt)} dated replies).")
    known = d["days_to_apply"].notna().sum()
    if known >= 10:
        lines.append(f"You apply a median **{d['days_to_apply'].median():.0f} days** after a job is posted. "
                     "See the Scorecard for how timing affects your results.")
    return lines


def page(ctx: Ctx) -> None:
    st.title("Dashboard")
    d = _filters(ctx.df)
    if d.empty:
        st.warning("No applications match these filters.")
        return

    goal = int(ctx.settings["weekly_goal"])
    wk = A.weekly_counts(d, 12)
    this_week = int(wk["applied"].iloc[-1])
    m = st.columns(6)
    m[0].metric("Applications", len(d))
    m[1].metric("Any reply", pct(d["responded"].mean()), help="Any reply, including rejections.")
    m[2].metric("Positive replies", int(d["positive"].sum()),
                help="Reached screening, interview or further, even if rejected later.")
    m[3].metric("Interviews", int(d["reached_interview"].sum()))
    m[4].metric("Still open", int(d["active"].sum()))
    m[5].metric("This week", f"{this_week} / {goal}", help="Applications sent this week vs your weekly goal "
                "(change it in Settings).")

    st.subheader("Takeaways")
    for line in takeaways(ctx, d):
        st.markdown(f"- {line}")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Funnel")
        f = A.funnel_with_dropoff(d)
        fig = go.Figure(go.Funnel(
            y=f["step"], x=f["count"], textinfo="value+percent initial",
            marker=dict(color=["#4a78c2", "#5b9bd5", "#6fb3c9", "#3aa17e", "#2b8f6b", ACCENT]),
            connector=dict(line=dict(color="#d0d6e2", width=1)),
        ))
        st.plotly_chart(plot_layout(fig, 340), width="stretch")
        conv = f.iloc[1:][["step", "count", "from_previous", "lost"]].rename(
            columns={"step": "Step", "count": "Reached", "from_previous": "Conversion from previous step",
                     "lost": "Lost at this step"})
        conv["Conversion from previous step"] = conv["Conversion from previous step"].map(pct)
        st.dataframe(conv, hide_index=True, width="stretch")
    with c2:
        st.subheader("Where applications go")
        links = A.flow_links(d, ctx.events)
        if links.empty:
            st.caption("No data yet.")
        else:
            nodes = list(dict.fromkeys(list(links["source"]) + list(links["target"])))
            idx = {n: i for i, n in enumerate(nodes)}
            fig = go.Figure(go.Sankey(
                arrangement="snap",
                node=dict(label=[f"{n}" for n in nodes], pad=18, thickness=16,
                          color=[STAGE_COLORS.get(n, "#999") for n in nodes]),
                link=dict(source=links["source"].map(idx), target=links["target"].map(idx), value=links["count"],
                          color="rgba(120,140,170,0.25)"),
            ))
            st.plotly_chart(plot_layout(fig, 340), width="stretch")
            st.caption("Each band is a group of applications moving between stages. Record stages as they happen "
                       "(Applications page) to see where you drop out.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Applications per month")
        mo = A.monthly(d)
        cols = [c for c in OUTCOME_ORDER if c in mo.columns]
        long = mo.melt(id_vars="month", value_vars=cols, var_name="outcome", value_name="n")
        fig = px.bar(long, x="month", y="n", color="outcome", color_discrete_map=OUTCOME_COLORS,
                     category_orders={"outcome": OUTCOME_ORDER}, labels={"n": "Applications", "month": ""})
        st.plotly_chart(plot_layout(fig), width="stretch")
    with c2:
        st.subheader("Weekly pace")
        fig = go.Figure()
        fig.add_bar(x=wk["week"], y=wk["applied"], marker_color=["#4a78c2"] * (len(wk) - 1) + [ACCENT],
                    name="Applications", hovertemplate="Week of %{x|%b %d}: %{y}<extra></extra>")
        fig.add_hline(y=goal, line_dash="dash", line_color="#8e8e99", annotation_text=f"Goal {goal}/week",
                      annotation_position="top left")
        st.plotly_chart(plot_layout(fig, showlegend=False, xaxis_tickformat="%b %d"), width="stretch")

    rt = A.response_time_stats(d, "role_area")
    if not rt.empty:
        st.subheader("How long replies take")
        st.dataframe(rt.round(1).rename(columns={"role_area": "Job family"}), hide_index=True, width="stretch")
        st.caption("Only counts stages recorded with their real date; imported history has no reply dates.")

