"""Analysis helpers: enrich applications and compute success metrics.

All functions are pure pandas so they can be tested and reused outside Streamlit.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from .categorise import Categoriser
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


def enrich(apps: pd.DataFrame, events: pd.DataFrame, cat: Categoriser, today: date | None = None) -> pd.DataFrame:
    """Add categories, furthest stage, outcome and timing columns."""
    today = pd.Timestamp(today or date.today())
    df = apps.copy()
    if df.empty:
        for col in ["role_area", "region", "furthest_stage", "reached_interview", "responded", "outcome",
                    "days_since_applied", "days_to_response", "last_activity"]:
            df[col] = pd.Series(dtype="object")
        return df

    auto_role = df["position"].map(cat.role_area)
    auto_region = df["location"].map(cat.region)
    df["role_area"] = df["role_area_override"].where(df["role_area_override"].fillna("") != "", auto_role)
    df["region"] = df["region_override"].where(df["region_override"].fillna("") != "", auto_region)

    ev = events.copy()
    rank = {s: i for i, s in enumerate(PIPELINE)}
    ev["rank"] = ev["stage"].map(rank)
    furthest = ev.dropna(subset=["rank"]).sort_values("rank").groupby("application_id")["stage"].last()
    df["furthest_stage"] = _lookup(df["id"], furthest).fillna("Applied")
    df["reached_interview"] = df["furthest_stage"].isin(INTERVIEW_STAGES)

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
