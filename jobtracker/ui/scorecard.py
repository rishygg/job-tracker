"""Role Success Scorecard: your personal success rate across role dimensions."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from jobtracker import analysis as A

from .common import ACCENT, VERDICT_STYLE, Ctx, pct, plot_layout

COVERAGE_HINT = {
    "timing": "Add the date a job was posted to see whether applying early helps.",
    "jd_match_bucket": "Paste job descriptions and add your skills in Settings to see whether skills match predicts success.",
    "cv_version": "Note which CV version you sent to compare versions.",
    "fit": "Rate how well you fit each role (1–5) to see whether your gut feeling is right.",
    "company_size": "Set company size for companies the app doesn't recognise.",
    "work_authorization": "Paste job descriptions so the app can detect work permit requirements.",
    "language": "Paste job descriptions so the app can detect language requirements.",
    "work_mode": "Paste job descriptions or set work mode to compare on-site, hybrid and remote roles.",
    "source": "Record where you found each job (LinkedIn, referral, ...) to compare channels.",
}
UNKNOWN_VALUES = {"Not recorded", "Unknown", "Not stated", "Not rated", "Posting date unknown", "No job description"}


def _segment_line(r) -> str:
    icon, _ = VERDICT_STYLE.get(r["verdict"], ("", ""))
    return (f"{icon} **{r['dimension_label']}: {r['value']}** — {int(r['successes'])}/{int(r['applied'])} "
            f"({pct(r['rate'])}), {r['lift']:+.0%} vs your average")


def _dimension_chart(card, label: str):
    c = card.sort_values("smoothed")
    overall = float(c["overall"].iloc[0])
    colors = [VERDICT_STYLE.get(v, ("", "#8e8e99"))[1] for v in c["verdict"]]
    fig = go.Figure()
    fig.add_bar(
        y=c["value"], x=c["rate"], orientation="h", marker_color=colors,
        error_x=dict(type="data", symmetric=False, array=c["ci_high"] - c["rate"],
                     arrayminus=c["rate"] - c["ci_low"], color="#9aa3b5", thickness=1, width=3),
        customdata=c[["successes", "applied", "verdict", "smoothed"]].to_numpy(),
        hovertemplate="<b>%{y}</b><br>%{customdata[0]} of %{customdata[1]} (%{x:.0%})"
                      "<br>Adjusted: %{customdata[3]:.0%}<br>%{customdata[2]}<extra></extra>",
    )
    fig.add_vline(x=overall, line_dash="dash", line_color=ACCENT,
                  annotation_text=f"Your average {overall:.0%}", annotation_position="top")
    fig.update_xaxes(tickformat=".0%", rangemode="tozero", title=None)
    fig = plot_layout(fig, max(240, 36 * len(c) + 80), showlegend=False)
    fig.update_layout(margin=dict(t=36))
    return fig


def page(ctx: Ctx) -> None:
    st.title("Role Success Scorecard")
    st.caption("Your personal success rate for each kind of role, so you can spend your applications where they work.")

    c1, c2 = st.columns([2, 1])
    metric_label = c1.selectbox("Count as success", list(A.METRICS), key="sc_metric")
    metric = A.METRICS[metric_label]
    skip_new = c2.toggle(f"Skip unanswered ones under {ctx.settings['too_new_days']} days old", value=True,
                         key="sc_skip", help="Recent applications haven't had time to get a reply, so counting them "
                                             "would make every group look worse.")
    df = A.judged(ctx.df, ctx.settings["too_new_days"]) if skip_new else ctx.df
    if len(df) < 5:
        st.info("Add a few more applications to see your scorecard.")
        return

    overall = df[metric].mean()
    n_succ = int(df[metric].sum())
    m = st.columns(3)
    m[0].metric("Applications judged", len(df))
    m[1].metric("Successes", n_succ)
    m[2].metric("Your average", pct(overall, 1))
    if n_succ < 10:
        st.warning(f"Only {n_succ} successes so far, so differences between groups are hints rather than proof. "
                   "Try **Any reply** as the success measure for a bigger sample.")

    card = A.scorecard_all(df, metric=metric)
    best, worst = A.strengths_and_gaps(card)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Where you do best")
        if best.empty:
            st.caption("No segment stands out yet.")
        for _, r in best.iterrows():
            st.markdown(_segment_line(r))
    with c2:
        st.subheader("Where you struggle")
        if worst.empty:
            st.caption("No segment stands out yet.")
        for _, r in worst.iterrows():
            st.markdown(_segment_line(r))

    st.divider()
    st.subheader("By dimension")
    dims = [d for d in A.DIMENSIONS if d in df]
    dim = st.radio("Dimension", dims, format_func=A.DIMENSIONS.get, horizontal=True, key="sc_dim")
    sc = A.scorecard(df, dim, metric)
    known = (~sc["value"].isin(UNKNOWN_VALUES)) if not sc.empty else None
    coverage = int(sc.loc[known, "applied"].sum()) if known is not None else 0
    if coverage < len(df) * 0.5 and dim in COVERAGE_HINT:
        st.info(f"Known for {coverage} of {len(df)} applications. {COVERAGE_HINT[dim]}")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(_dimension_chart(sc, A.DIMENSIONS[dim]), width="stretch")
    with c2:
        show = sc[["value", "applied", "successes", "rate", "verdict"]].copy()
        show["rate"] = show["rate"].map(pct)
        show["verdict"] = [f"{VERDICT_STYLE.get(v, ('', ''))[0]} {v}" for v in show["verdict"]]
        st.dataframe(show.rename(columns={"value": A.DIMENSIONS[dim], "rate": "Rate",
                                          "verdict": "Verdict", "applied": "Applied", "successes": "Successes"}),
                     hide_index=True, width="stretch")

    st.divider()
    st.subheader("Combine two dimensions")
    c1, c2 = st.columns(2)
    rows = c1.selectbox("Rows", dims, index=dims.index("role_area"), format_func=A.DIMENSIONS.get, key="hm_r")
    cols = c2.selectbox("Columns", dims, index=dims.index("seniority"), format_func=A.DIMENSIONS.get, key="hm_c")
    if rows == cols:
        st.caption("Pick two different dimensions.")
    else:
        rate, n = A.heatmap(df, rows, cols, metric)
        text = [[("" if (cnt != cnt or cnt == 0) else f"{r:.0%}<br><sub>n={int(cnt)}</sub>")
                 for r, cnt in zip(rr, nn)] for rr, nn in zip(rate.to_numpy(), n.to_numpy())]
        fig = go.Figure(go.Heatmap(
            z=rate.to_numpy(), x=list(rate.columns), y=list(rate.index), text=text, texttemplate="%{text}",
            colorscale=[[0, "#f3f5f9"], [1, ACCENT]], zmin=0, hoverongaps=False, colorbar=dict(tickformat=".0%"),
            customdata=n.to_numpy(), hovertemplate="%{y} × %{x}<br>%{z:.0%} of %{customdata}<extra></extra>",
        ))
        st.plotly_chart(plot_layout(fig, max(300, 40 * len(rate) + 80)), width="stretch")
        st.caption("Cells with few applications are noisy; check n before drawing conclusions.")

    with st.expander("How the scorecard works"):
        st.markdown(
            "- **Rate** is successes ÷ applications in that group.\n"
            "- **Adjusted rate** blends a group's rate with your overall average, weighted as if each group had "
            "10 extra average applications. Small groups stay close to your average until they have enough data, "
            "so 1 success out of 2 doesn't outrank 5 out of 30.\n"
            "- The whiskers on the chart show the 95% range for the true rate (Wilson interval).\n"
            "- **Strength**: even the low end of the range beats your average. **Weak spot**: even the high end is "
            "below it. **Promising / Below average**: adjusted rate is at least 30% above / below your average. "
            "Groups with fewer than 5 applications are marked *Too few to tell*.\n"
            "- Dimensions like seniority, industry, work permit and language are inferred from the job title, "
            "company and job description. Correct any of them on the Applications page; rules live in Settings."
        )
