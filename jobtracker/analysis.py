"""Analysis helpers: enrich applications and compute success metrics.

All functions are pure pandas so they can be tested and reused outside Streamlit.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from .categorise import Categoriser
from .dimensions import DimensionInferer
from .storage import ACTIVE_STAGES, INTERVIEW_STAGES, PIPELINE

IMPORTED_NOTE = "imported"


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion; robust for small n."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _lookup(ids: pd.Series, values: pd.Series) -> pd.Series:
    """Like ids.map(values) but safe when `values` is empty (pandas can't map an empty datetime Series)."""
    return pd.Series(values.reindex(ids.to_numpy()).to_numpy(), index=ids.index)


# Dimensions that are inferred automatically but can be set per application.
INFERRED = ["seniority", "industry", "company_size", "work_authorization", "language", "work_mode"]

TIMING_BUCKETS = [(-1, 2, "0–2 days"), (2, 7, "3–7 days"), (7, 14, "8–14 days"), (14, 30, "15–30 days"),
                  (30, 10_000, "30+ days")]
MATCH_BUCKETS = [(-0.01, 0.4, "Low (<40%)"), (0.4, 0.7, "Medium (40–70%)"), (0.7, 1.01, "High (70%+)")]


def _bucket(value, buckets, missing: str):
    if value is None or pd.isna(value):
        return missing
    for lo, hi, label in buckets:
        if lo < value <= hi:
            return label
    return missing


def enrich(apps: pd.DataFrame, events: pd.DataFrame, cat: Categoriser, today: date | None = None,
           inferer: DimensionInferer | None = None, my_skills: list[str] | None = None) -> pd.DataFrame:
    """Add categories, inferred role dimensions, furthest stage, outcome and timing columns."""
    today = pd.Timestamp(today or date.today())
    df = apps.copy()
    if df.empty:
        for col in ["role_area", "region", "furthest_stage", "reached_interview", "responded", "positive",
                    "outcome", "days_since_applied", "days_to_response", "last_activity", "days_since_activity",
                    "active", "days_to_apply", "timing", "jd_skills", "jd_match", "jd_match_bucket", "min_years",
                    "weekday", "fit", "has_jd", *INFERRED, *[f"{c}_auto" for c in INFERRED]]:
            df[col] = pd.Series(dtype="object")
        return df
    for col in ["date_posted", "job_description", "cv_version", "fit_rating", *INFERRED]:
        if col not in df:
            df[col] = None

    auto_role = df["position"].map(cat.role_area)
    auto_region = df["location"].map(cat.region)
    df["role_area"] = df["role_area_override"].where(df["role_area_override"].fillna("") != "", auto_role)
    df["region"] = df["region_override"].where(df["region_override"].fillna("") != "", auto_region)

    # Role dimensions: use what you set, otherwise infer from title / company / job description.
    inferer = inferer or DimensionInferer.from_yaml()
    inferred = [inferer.infer_all(t, c, j) for t, c, j in
                zip(df["position"], df["company"], df["job_description"].fillna(""))]
    inf = pd.DataFrame(inferred, index=df.index)
    remote = df["location"].fillna("").str.contains(r"\bremote\b", case=False)
    inf.loc[remote & (inf["work_mode"] == inferer.options("work_mode")[-1]), "work_mode"] = "Remote"
    for col in INFERRED:
        df[f"{col}_auto"] = inf[col]
        df[col] = df[col].where(df[col].fillna("").astype(str).str.strip() != "", inf[col])
    df["jd_skills"] = inf["jd_skills"]
    df["min_years"] = inf["min_years"]
    df["has_jd"] = df["job_description"].fillna("").str.strip().str.len() > 0
    mine = {s.strip().lower() for s in (my_skills or []) if s and s.strip()}
    if mine:
        def match(skills):
            if not skills:
                return None
            return sum(s.lower() in mine for s in skills) / len(skills)
        df["jd_match"] = df["jd_skills"].map(match)
    else:
        df["jd_match"] = None
    df["jd_match_bucket"] = [
        (_bucket(m, MATCH_BUCKETS, "No skills found") if h else "No job description")
        for m, h in zip(df["jd_match"], df["has_jd"])
    ]

    # Timing: how long after the posting went up you applied.
    df["days_to_apply"] = (df["date_applied"] - pd.to_datetime(df["date_posted"], errors="coerce")).dt.days
    df.loc[df["days_to_apply"] < 0, "days_to_apply"] = pd.NA
    df["timing"] = df["days_to_apply"].map(lambda v: _bucket(v, TIMING_BUCKETS, "Posting date unknown"))
    df["weekday"] = df["date_applied"].dt.day_name()
    df["fit"] = df["fit_rating"].map(lambda v: "Not rated" if v is None or pd.isna(v) else f"{int(v)}/5")

    ev = events.copy()
    rank = {s: i for i, s in enumerate(PIPELINE)}
    ev["rank"] = ev["stage"].map(rank)
    furthest = ev.dropna(subset=["rank"]).sort_values("rank").groupby("application_id")["stage"].last()
    df["furthest_stage"] = _lookup(df["id"], furthest).fillna("Applied")
    df["reached_interview"] = df["furthest_stage"].isin(INTERVIEW_STAGES)
    df["positive"] = df["furthest_stage"].map(rank).fillna(0) >= rank["Screening"]

    # A response is any stage after "Applied" other than Ghosted / Withdrawn.
    resp = ev[~ev["stage"].isin(["Applied", "Ghosted", "Withdrawn"])]
    df["responded"] = df["id"].isin(resp["application_id"])

    # Days to first response: only from events with real dates (not bulk-imported placeholders).
    dated = resp[resp["note"].fillna("") != IMPORTED_NOTE]
    first_resp = dated.groupby("application_id")["date"].min()
    df["days_to_response"] = (pd.to_datetime(_lookup(df["id"], first_resp)) - df["date_applied"]).dt.days
    df.loc[df["days_to_response"] < 0, "days_to_response"] = pd.NA

    last = ev.groupby("application_id")["date"].max()
    df["last_activity"] = pd.to_datetime(_lookup(df["id"], last)).fillna(df["date_applied"])
    df["days_since_applied"] = (today - df["date_applied"]).dt.days
    df["days_since_activity"] = (today - df["last_activity"]).dt.days

    def outcome(r) -> str:
        if r["status"] in ("Offer", "Accepted"):
            return "Offer"
        if r["reached_interview"]:
            return "Interviewed"
        if r["status"] == "Rejected":
            return "Rejected"
        if r["status"] == "Ghosted":
            return "Ghosted"
        if r["status"] == "Withdrawn":
            return "Withdrawn"
        return "Waiting"

    df["outcome"] = df.apply(outcome, axis=1)
    df["active"] = df["status"].isin(ACTIVE_STAGES)
    return df


def breakdown(df: pd.DataFrame, by: str, min_n: int = 5) -> pd.DataFrame:
    """Success metrics per group (e.g. role_area, region, source)."""
    if df.empty:
        return pd.DataFrame()
    g = df.assign(_key=df[by].fillna("Unspecified").replace("", "Unspecified")).groupby("_key")
    out = pd.DataFrame({
        "applied": g.size(),
        "responses": g["responded"].sum(),
        "interviews": g["reached_interview"].sum(),
        "offers": g["outcome"].apply(lambda s: (s == "Offer").sum()),
        "rejected": g["status"].apply(lambda s: (s == "Rejected").sum()),
        "ghosted": g["status"].apply(lambda s: (s == "Ghosted").sum()),
        "waiting": g["active"].sum(),
    })
    closed = out["applied"] - out["waiting"]
    out["response_rate"] = out["responses"] / out["applied"]
    out["interview_rate"] = out["interviews"] / out["applied"]
    out["ghost_rate"] = (out["ghosted"] / closed).where(closed > 0)
    ci = [wilson_interval(int(i), int(n)) for i, n in zip(out["interviews"], out["applied"])]
    out["interview_rate_low"] = [c[0] for c in ci]
    out["interview_rate_high"] = [c[1] for c in ci]
    out["small_sample"] = out["applied"] < min_n
    out.index.name = by
    return out.sort_values(["interview_rate", "response_rate", "applied"], ascending=False).reset_index()


def funnel(df: pd.DataFrame) -> pd.DataFrame:
    """How many applications reached each step."""
    rank = {s: i for i, s in enumerate(PIPELINE)}
    r = df["furthest_stage"].map(rank).fillna(0)
    steps = [
        ("Applied", len(df)),
        ("Got a response", int(df["responded"].sum())),
        ("Screening or later", int((r >= rank["Screening"]).sum())),
        ("Interview", int((r >= rank["Interview"]).sum())),
        ("Final interview", int((r >= rank["Final interview"]).sum())),
        ("Offer", int((r >= rank["Offer"]).sum())),
    ]
    return pd.DataFrame(steps, columns=["step", "count"])


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Applications per month by outcome, plus response and interview rates."""
    if df.empty:
        return pd.DataFrame()
    m = df.assign(month=df["date_applied"].dt.to_period("M").dt.to_timestamp())
    counts = m.pivot_table(index="month", columns="outcome", values="id", aggfunc="count", fill_value=0)
    rates = m.groupby("month").agg(applied=("id", "count"), response_rate=("responded", "mean"),
                                   interview_rate=("reached_interview", "mean"))
    return rates.join(counts).reset_index()


def follow_ups(df: pd.DataFrame, follow_up_after: int = 10, ghost_after: int = 42) -> pd.DataFrame:
    """Active applications that need action, with a suggested next step."""
    if df.empty:
        return df
    waiting = df[df["status"].isin(["Applied", "Screening", "Interview", "Final interview"])].copy()
    waiting["action"] = None
    stale = waiting["days_since_activity"]
    waiting.loc[stale >= follow_up_after, "action"] = "Follow up"
    waiting.loc[(waiting["status"] == "Applied") & (stale >= ghost_after), "action"] = "Mark as ghosted"
    return waiting.dropna(subset=["action"]).sort_values("days_since_activity", ascending=False)


def response_time_stats(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    d = df.dropna(subset=["days_to_response"])
    if d.empty:
        return pd.DataFrame()
    if by:
        return d.groupby(by)["days_to_response"].describe()[["count", "50%", "mean", "max"]].rename(
            columns={"50%": "median"}).reset_index()
    return d["days_to_response"].describe()[["count", "50%", "mean", "max"]].rename({"50%": "median"}).to_frame().T


def insights(df: pd.DataFrame, min_n: int = 8) -> list[str]:
    """Plain-language takeaways, only where the sample is big enough to say something."""
    out: list[str] = []
    if df.empty:
        return ["No applications yet. Add one or import your existing tracker."]
    n = len(df)
    resp = df["responded"].mean()
    ints = int(df["reached_interview"].sum())
    out.append(f"{n} applications: {resp:.0%} got a response and {ints} ({ints / n:.1%}) reached interview.")

    for col, label in [("role_area", "role area"), ("region", "location"), ("source", "source")]:
        if col not in df or df[col].fillna("").eq("").all():
            continue
        b = breakdown(df, col)
        b = b[b["applied"] >= min_n]
        if len(b) < 2:
            continue
        best = b.sort_values(["interview_rate", "response_rate"], ascending=False).iloc[0]
        if best["interviews"] > 0:
            out.append(f"Best {label} for interviews: {best[col]} ({int(best['interviews'])}/{int(best['applied'])}, "
                       f"{best['interview_rate']:.0%}).")
        else:
            best_r = b.sort_values("response_rate", ascending=False).iloc[0]
            out.append(f"Highest response rate by {label}: {best_r[col]} ({best_r['response_rate']:.0%} of "
                       f"{int(best_r['applied'])}).")
        g = b.dropna(subset=["ghost_rate"]).sort_values("ghost_rate", ascending=False)
        if len(g) >= 2 and g.iloc[0]["ghost_rate"] - g.iloc[-1]["ghost_rate"] >= 0.15:
            out.append(f"Most ignored {label}: {g.iloc[0][col]} ({g.iloc[0]['ghost_rate']:.0%} ghosted) vs "
                       f"{g.iloc[-1][col]} ({g.iloc[-1]['ghost_rate']:.0%}).")

    rt = df["days_to_response"].dropna()
    if len(rt) >= 5:
        out.append(f"Typical time to first response: {rt.median():.0f} days (based on {len(rt)} dated responses).")
    if ints < 5:
        out.append("Interview counts are still small, so treat rate differences between groups as hints, not proof.")
    return out


# ---------------------------------------------------------------------------
# Role Success Scorecard
# ---------------------------------------------------------------------------

METRICS = {
    "Positive response (screening or further)": "positive",
    "Interview": "reached_interview",
    "Any reply (incl. rejections)": "responded",
}

# Dimension column -> label shown in the app.
DIMENSIONS = {
    "role_area": "Job family",
    "seniority": "Seniority",
    "industry": "Industry",
    "region": "Location",
    "company_size": "Company size",
    "work_authorization": "Work permit requirement",
    "language": "Language requirement",
    "work_mode": "Work mode",
    "source": "Application channel",
    "timing": "Applied after posting",
    "jd_match_bucket": "Skills match with JD",
    "cv_version": "CV version",
    "fit": "Your fit rating",
    "weekday": "Day applied",
}


def judged(df: pd.DataFrame, too_new_days: int = 21) -> pd.DataFrame:
    """Applications old enough to judge: drops ones still waiting that were sent in the last `too_new_days`."""
    if df.empty:
        return df
    return df[~(df["active"] & (df["furthest_stage"] == "Applied") & (df["days_since_applied"] < too_new_days))]


def _verdict(n, ci_low, ci_high, lift, overall, min_n) -> str:
    if n < min_n:
        return "Too few to tell"
    if overall > 0 and ci_low > overall:
        return "Strength"
    if ci_high < overall:
        return "Weak spot"
    if lift >= 0.3:
        return "Promising"
    if lift <= -0.3:
        return "Below average"
    return "About average"


def scorecard(df: pd.DataFrame, dim: str, metric: str = "positive", k: float = 10, min_n: int = 5) -> pd.DataFrame:
    """Success rate for each value of one dimension.

    `smoothed` pulls small groups towards your overall rate (k pseudo-applications), so
    1 success out of 2 doesn't outrank 5 out of 30. `lift` compares the smoothed rate with
    your overall rate.
    """
    if df.empty:
        return pd.DataFrame()
    overall = float(df[metric].mean())
    key = df[dim].astype("object").where(df[dim].notna(), "Not recorded")
    key = key.map(lambda v: "Not recorded" if str(v).strip() == "" else str(v))
    g = df.assign(_k=key).groupby("_k")
    out = pd.DataFrame({
        "applied": g.size(),
        "successes": g[metric].sum().astype(int),
        "ghosted": g["status"].apply(lambda s: int((s == "Ghosted").sum())),
    })
    out["rate"] = out["successes"] / out["applied"]
    out["smoothed"] = (out["successes"] + k * overall) / (out["applied"] + k)
    out["lift"] = (out["smoothed"] / overall - 1) if overall > 0 else 0.0
    ci = [wilson_interval(int(s), int(n)) for s, n in zip(out["successes"], out["applied"])]
    out["ci_low"] = [c[0] for c in ci]
    out["ci_high"] = [c[1] for c in ci]
    out["verdict"] = [_verdict(n, lo, hi, li, overall, min_n)
                      for n, lo, hi, li in zip(out["applied"], out["ci_low"], out["ci_high"], out["lift"])]
    out["overall"] = overall
    out.index.name = "value"
    return out.sort_values(["smoothed", "applied"], ascending=False).reset_index()


def scorecard_all(df: pd.DataFrame, dims: list[str] | None = None, metric: str = "positive", min_n: int = 5) -> pd.DataFrame:
    frames = []
    for d in dims or list(DIMENSIONS):
        if d not in df:
            continue
        s = scorecard(df, d, metric, min_n=min_n)
        if s.empty or s["value"].nunique() < 2:
            continue
        frames.append(s.assign(dimension=d, dimension_label=DIMENSIONS.get(d, d)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


UNINFORMATIVE = {"Not recorded", "Unknown", "Not stated", "Not rated", "Posting date unknown", "No job description",
                 "No skills found", "Mid / unspecified", "No extra language stated", "Other", "Other / unspecified"}


def strengths_and_gaps(card: pd.DataFrame, min_n: int = 5, top: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Best and worst segments across all dimensions, ignoring tiny or 'unknown' groups."""
    if card.empty:
        return card, card
    c = card[(card["applied"] >= min_n) & (~card["value"].isin(UNINFORMATIVE))]
    best = c[c["successes"] > 0].sort_values(["lift", "applied"], ascending=False).head(top)
    worst = c.sort_values(["lift", "applied"], ascending=[True, False])
    worst = worst[worst["lift"] < 0].head(top)
    return best, worst


def heatmap(df: pd.DataFrame, rows: str, cols: str, metric: str = "positive") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Success rate and count for every combination of two dimensions."""
    d = df.assign(_r=df[rows].fillna("Not recorded").astype(str), _c=df[cols].fillna("Not recorded").astype(str))
    rate = d.pivot_table(index="_r", columns="_c", values=metric, aggfunc="mean")
    n = d.pivot_table(index="_r", columns="_c", values=metric, aggfunc="count")
    rate.index.name, rate.columns.name = rows, cols
    return rate, n


# ---------------------------------------------------------------------------
# Funnel and flow
# ---------------------------------------------------------------------------

def funnel_with_dropoff(df: pd.DataFrame) -> pd.DataFrame:
    f = funnel(df)
    f["of_applied"] = f["count"] / max(1, f["count"].iloc[0])
    prev = f["count"].shift(1)
    f["from_previous"] = (f["count"] / prev).where(prev > 0)
    f["lost"] = (prev - f["count"]).fillna(0).astype(int)
    return f


def flow_links(df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Transitions between stages for a Sankey diagram: source, target, count."""
    if df.empty:
        return pd.DataFrame(columns=["source", "target", "count"])
    rank = {s: i for i, s in enumerate(PIPELINE)}
    ev = events[events["application_id"].isin(df["id"])]
    reached = ev[ev["stage"].isin(PIPELINE[1:])].groupby("application_id")["stage"].apply(
        lambda s: sorted(set(s), key=rank.get))
    pairs: dict[tuple[str, str], int] = {}
    for _, r in df.iterrows():
        path = ["Applied", *reached.get(r["id"], [])]
        if r["status"] in ("Rejected", "Ghosted", "Withdrawn"):
            path.append(r["status"])
        elif path[-1] == "Applied":
            path.append("Awaiting reply")
        for a, b in zip(path, path[1:]):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1
    return pd.DataFrame([(a, b, n) for (a, b), n in pairs.items()], columns=["source", "target", "count"])


# ---------------------------------------------------------------------------
# Job descriptions and skills
# ---------------------------------------------------------------------------

def skills_table(df: pd.DataFrame, my_skills: list[str] | None, groups: dict[str, str],
                 metric: str = "positive", min_postings: int = 2) -> pd.DataFrame:
    """How often each skill appears in your job descriptions, whether you have it, and how you did when it did."""
    d = df[df["has_jd"]] if "has_jd" in df else df.iloc[0:0]
    if d.empty:
        return pd.DataFrame()
    mine = {s.strip().lower() for s in (my_skills or [])}
    ex = d[["id", "jd_skills", metric]].explode("jd_skills").dropna(subset=["jd_skills"])
    if ex.empty:
        return pd.DataFrame()
    g = ex.groupby("jd_skills")
    out = pd.DataFrame({"postings": g.size(), "successes": g[metric].sum().astype(int)})
    out["share_of_postings"] = out["postings"] / len(d)
    out["success_rate"] = out["successes"] / out["postings"]
    out["you_have_it"] = [s.lower() in mine for s in out.index]
    out["group"] = [groups.get(s, groups.get(s.lower(), "")) for s in out.index]
    out.index.name = "skill"
    out = out[out["postings"] >= min_postings]
    return out.sort_values("postings", ascending=False).reset_index()


# ---------------------------------------------------------------------------
# Pace
# ---------------------------------------------------------------------------

def weekly_counts(df: pd.DataFrame, weeks: int = 12, today: date | None = None) -> pd.DataFrame:
    today = pd.Timestamp(today or date.today())
    start = (today - pd.Timedelta(days=today.weekday())).normalize() - pd.Timedelta(weeks=weeks - 1)
    idx = pd.date_range(start, periods=weeks, freq="7D")
    if df.empty:
        return pd.DataFrame({"week": idx, "applied": 0})
    wk = (df["date_applied"] - pd.to_timedelta(df["date_applied"].dt.weekday, unit="D")).dt.normalize()
    counts = wk.value_counts().reindex(idx, fill_value=0)
    return pd.DataFrame({"week": idx, "applied": counts.to_numpy()})


# ---------------------------------------------------------------------------
# Conversion metrics (Analytics page)
# ---------------------------------------------------------------------------

LATER_ROUNDS = {"Final interview", "Offer", "Accepted"}
OFFER_STAGES = {"Offer", "Accepted"}


def _ratio(num: int, den: int) -> dict:
    lo, hi = wilson_interval(num, den)
    return {"numerator": int(num), "denominator": int(den), "rate": (num / den) if den else None,
            "ci_low": lo, "ci_high": hi}


def conversion_metrics(df: pd.DataFrame, too_new_days: int = 21) -> dict:
    """The headline conversion rates between pipeline steps.

    Each rate only counts applications that could have reached the step: e.g. "interview to offer"
    uses applications that reached an interview, and very recent unanswered applications are left out.
    """
    if df.empty:
        return {}
    j = judged(df, too_new_days)
    furthest = j["furthest_stage"]
    interviewed = j[j["reached_interview"]]
    later = interviewed["furthest_stage"].isin(LATER_ROUNDS)
    offers = j["furthest_stage"].isin(OFFER_STAGES) | j["status"].isin(OFFER_STAGES)
    rt = df["days_to_response"].dropna()
    return {
        "application_to_response": _ratio(int(j["responded"].sum()), len(j)),
        "application_to_interview": _ratio(int(j["reached_interview"].sum()), len(j)),
        "interview_to_later_round": _ratio(int(later.sum()), len(interviewed)),
        "interview_to_offer": _ratio(int(offers[j["reached_interview"]].sum()), len(interviewed)),
        "application_to_offer": _ratio(int(offers.sum()), len(j)),
        "median_days_to_response": float(rt.median()) if len(rt) else None,
        "response_time_samples": int(len(rt)),
        "judged": int(len(j)),
        "excluded_recent": int(len(df) - len(j)),
        "_furthest_counts": furthest.value_counts().to_dict(),
    }


def rates_by(df: pd.DataFrame, dim: str, too_new_days: int = 21, min_n: int = 1) -> pd.DataFrame:
    """Response, interview and offer rate per value of a dimension (e.g. offer rate by job family)."""
    j = judged(df, too_new_days)
    if j.empty:
        return pd.DataFrame()
    key = j[dim].astype("object").where(j[dim].notna(), "Not recorded").astype(str)
    offers = j["furthest_stage"].isin(OFFER_STAGES) | j["status"].isin(OFFER_STAGES)
    g = j.assign(_k=key, _offer=offers).groupby("_k")
    out = pd.DataFrame({
        "applied": g.size(),
        "responses": g["responded"].sum().astype(int),
        "interviews": g["reached_interview"].sum().astype(int),
        "offers": g["_offer"].sum().astype(int),
    })
    out["response_rate"] = out["responses"] / out["applied"]
    out["interview_rate"] = out["interviews"] / out["applied"]
    out["offer_rate"] = out["offers"] / out["applied"]
    out["interview_to_offer"] = (out["offers"] / out["interviews"]).where(out["interviews"] > 0)
    out.index.name = "value"
    out = out[out["applied"] >= min_n]
    return out.sort_values(["applied"], ascending=False).reset_index()


def response_time_by(df: pd.DataFrame, dim: str) -> pd.DataFrame:
    d = df.dropna(subset=["days_to_response"])
    if d.empty:
        return pd.DataFrame(columns=["value", "count", "median"])
    g = d.groupby(d[dim].astype(str))["days_to_response"]
    return pd.DataFrame({"count": g.size(), "median": g.median()}).rename_axis("value").reset_index()
