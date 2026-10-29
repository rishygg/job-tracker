"""The lighter side: momentum calendar, milestones, a "Wrapped" summary, company reply times and the map."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml


PLACES_YAML = Path(__file__).resolve().parent.parent / "config" / "places.yaml"
INTERVIEW = {"Interview", "Final interview", "Offer", "Accepted"}


def _d(x) -> date | None:
    if x is None or (not isinstance(x, (str, date)) and pd.isna(x)):
        return None
    try:
        return pd.Timestamp(str(x)[:10]).date()
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- momentum
def momentum(df: pd.DataFrame, events: pd.DataFrame, interviews: list[dict], practice: list[dict], stories: list[dict],
             weekly_goal: int, today: date | None = None, weeks: int = 26) -> dict:
    """Daily activity for a GitHub-style calendar, plus streaks and this week's progress toward your goal."""
    today = today or date.today()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    days: dict[date, Counter] = {}

    def bump(d: date | None, kind: str):
        if d and start <= d <= today:
            days.setdefault(d, Counter())[kind] += 1

    if not df.empty:
        for d in df["date_applied"].dt.date:
            bump(d, "applied")
    if not events.empty:
        for e in events[events["stage"] != "Applied"].itertuples():
            bump(e.date.date(), "updates")
    for i in interviews:
        bump(_d(i.get("created_at")), "journal")
    for p in practice:
        bump(_d(p.get("created_at")), "practice")
    for s in stories:
        bump(_d(s.get("created_at")), "stories")

    cells = []
    d = start
    while d <= today:
        c = days.get(d, Counter())
        cells.append({"date": d.isoformat(), "total": sum(c.values()), **dict(c)})
        d += timedelta(days=1)

    # Applications per week, for the goal.
    def week_start(x: date) -> date:
        return x - timedelta(days=x.weekday())
    per_week = Counter()
    if not df.empty:
        for x in df["date_applied"].dt.date:
            per_week[week_start(x)] += 1
    this_week = week_start(today)
    goal = max(1, int(weekly_goal or 1))
    streak_weeks = 0
    w = this_week if per_week[this_week] >= goal else this_week - timedelta(weeks=1)
    while per_week[w] >= goal:
        streak_weeks += 1
        w -= timedelta(weeks=1)
    active = {date.fromisoformat(c["date"]) for c in cells if c["total"]}
    streak_days = 0
    d = today if today in active else today - timedelta(days=1)
    while d in active:
        streak_days += 1
        d -= timedelta(days=1)
    best_week = max(per_week.values()) if per_week else 0
    return {"cells": cells, "goal": goal, "this_week": per_week[this_week], "streak_weeks": streak_weeks,
            "streak_days": streak_days, "best_week": best_week, "active_days": len(active),
            "weekly": [{"week": (this_week - timedelta(weeks=i)).isoformat(),
                        "applied": per_week[this_week - timedelta(weeks=i)]} for i in range(11, -1, -1)]}


# --------------------------------------------------------------------------- milestones
def milestones(df: pd.DataFrame, events: pd.DataFrame, interviews: list[dict], questions: list[dict],
               practice: list[dict], stories: list[dict], mom: dict) -> list[dict]:
    """Small achievements. Each: id, title, detail, icon, achieved, date, progress (current, target)."""
    out = []

    def add(mid, title, detail, icon, current, target, when=None):
        out.append({"id": mid, "title": title, "detail": detail, "icon": icon, "achieved": current >= target,
                    "date": when.isoformat() if isinstance(when, date) and current >= target else None,
                    "progress": [min(current, target), target]})

    n = len(df)
    dates = sorted(df["date_applied"].dt.date) if n else []
    for t, title in ((1, "First application"), (10, "Ten applications"), (50, "Fifty applications"), (100, "A hundred applications")):
        add(f"apps_{t}", title, f"Sent {t} application{'s' if t > 1 else ''}.", "send", n, t, dates[t - 1] if n >= t else None)

    resp = df[df["responded"]] if n else df
    first_resp = None
    if n and not events.empty:
        ev = events[(events["stage"] != "Applied") & (events["stage"] != "Ghosted") & (events["stage"] != "Withdrawn")]
        first_resp = ev["date"].min().date() if not ev.empty else None
    add("first_reply", "First reply", "Heard back from a company.", "mail", int(len(resp) > 0), 1, first_resp)

    def first_stage(stages):
        if events.empty:
            return None
        e = events[events["stage"].isin(stages) & (events["date"].dt.date <= date.today())]
        return e["date"].min().date() if not e.empty else None
    reached = int(df["reached_interview"].sum()) if n else 0
    add("first_interview", "First interview", "Got through to an interview.", "mic", reached, 1, first_stage(INTERVIEW))
    finals = int(df["furthest_stage"].isin(["Final interview", "Offer", "Accepted"]).sum()) if n else 0
    add("final_round", "Final round", "Reached a final interview.", "flag", finals, 1, first_stage({"Final interview", "Offer", "Accepted"}))
    offers = int(df["furthest_stage"].isin(["Offer", "Accepted"]).sum()) if n else 0
    add("offer", "An offer!", "Received an offer.", "trophy", offers, 1, first_stage({"Offer", "Accepted"}))

    add("goal_streak", "Three weeks on target", "Hit your weekly application goal three weeks running.", "flame",
        mom["streak_weeks"], 3, date.today())
    add("busy_week", "Big week", "Ten applications in one week.", "zap", mom["best_week"], 10, date.today())

    iv_dates = sorted(_d(i.get("created_at")) for i in interviews if i.get("created_at"))
    add("journal_1", "Reflective", "Logged your first interview in the journal.", "notebook", len(interviews), 1,
        iv_dates[0] if iv_dates else None)
    add("journal_5", "Pattern spotter", "Logged five interviews.", "notebook", len(interviews), 5,
        iv_dates[4] if len(iv_dates) >= 5 else None)
    st_dates = sorted(_d(s.get("created_at")) for s in stories if s.get("created_at"))
    add("story_1", "Storyteller", "Wrote your first STAR story.", "book", len(stories), 1, st_dates[0] if st_dates else None)
    uses = Counter(q.get("story_id") for q in questions if q.get("story_id"))
    add("story_reuse", "Greatest hit", "Used the same story in three interviews.", "repeat", max(uses.values(), default=0), 3, date.today())
    pr_dates = sorted(_d(p.get("created_at")) for p in practice if p.get("created_at"))
    add("practice_10", "Rehearsed", "Practised ten answers.", "graduation", len(practice), 10,
        pr_dates[9] if len(pr_dates) >= 10 else None)
    top = [p for p in practice if (p.get("feedback") or {}).get("score") == 5]
    add("practice_5", "Nailed it", "An answer scored 5/5.", "star", len(top), 1, _d(top[0].get("updated_at")) if top else None)
    return out


# --------------------------------------------------------------------------- company reply times
def company_replies(df: pd.DataFrame, min_apps: int = 1) -> dict:
    """Which companies reply quickly, slowly, or never.

    Reply times need stages recorded with their real date (imported history has none), so reply *rates*
    are given too: they work for imported data.
    """
    if df.empty:
        return {"fastest": [], "slowest": [], "responsive": [], "ghosts": [], "dated_replies": 0}
    rows = []
    for company, g in df.groupby("company"):
        old = g[~(g["active"] & (g["furthest_stage"] == "Applied") & (g["days_since_applied"] < 21))]
        rt = g["days_to_response"].dropna()
        silent = int((old["status"] == "Ghosted").sum() + ((~old["responded"]) & (old["status"] == "Applied")).sum())
        rows.append({"company": company, "applications": int(len(g)), "replied": int(g["responded"].sum()),
                     "reply_rate": round(float(old["responded"].mean()), 2) if len(old) else None,
                     "median_days": float(rt.median()) if len(rt) else None,
                     "ghosted": silent, "judged": int(len(old)),
                     "ghost_rate": round(silent / len(old), 2) if len(old) else None})
    with_rt = [r for r in rows if r["median_days"] is not None and r["applications"] >= min_apps]
    rated = [r for r in rows if r["judged"] >= 2 and r["reply_rate"] is not None]
    ghosts = [r for r in rows if r["ghosted"] and r["judged"]]
    return {"fastest": sorted(with_rt, key=lambda r: r["median_days"])[:8],
            "slowest": sorted(with_rt, key=lambda r: -r["median_days"])[:8],
            "responsive": sorted(rated, key=lambda r: (-r["reply_rate"], -r["judged"]))[:8],
            "ghosts": sorted(ghosts, key=lambda r: (-r["ghost_rate"], -r["ghosted"], r["company"]))[:10],
            "dated_replies": int(df["days_to_response"].notna().sum())}


# --------------------------------------------------------------------------- map
def load_places(path: Path = PLACES_YAML) -> list[tuple[re.Pattern, str, float, float]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for names, (lat, lon) in data.items():
        alts = [n.strip() for n in str(names).split("|") if n.strip()]
        rx = re.compile(r"\b(" + "|".join(re.escape(a) for a in alts) + r")\b", re.I)
        out.append((rx, alts[0], float(lat), float(lon)))
    return out


COUNTRY_ALIASES = {"uk": "United Kingdom", "england": "United Kingdom", "scotland": "United Kingdom", "wales": "United Kingdom",
                   "great britain": "United Kingdom", "usa": "United States", "us": "United States", "deutschland": "Germany",
                   "schweiz": "Switzerland", "suisse": "Switzerland", "svizzera": "Switzerland", "österreich": "Austria",
                   "nederland": "Netherlands", "holland": "Netherlands", "the netherlands": "Netherlands", "españa": "Spain",
                   "italia": "Italy", "danmark": "Denmark", "sverige": "Sweden", "norge": "Norway", "polska": "Poland",
                   "czech republic": "Czechia", "eire": "Ireland", "united states of america": "United States",
                   "u.s.": "United States", "u.k.": "United Kingdom", "uae": "United Arab Emirates", "türkiye": "Turkey"}
EUROPE_FIRST = {"CH", "DE", "AT", "GB", "FR", "IT", "NL", "BE", "LU", "DK", "SE", "NO", "FI", "IE", "ES", "PT", "PL", "CZ"}
_GEO: dict = {}


def _geo() -> dict:
    """Town and country lookup from the bundled GeoNames list (towns over 15,000 people). Built once, offline."""
    if _GEO:
        return _GEO
    cities: dict[str, list] = {}
    countries: dict[str, tuple[str, str]] = {}
    try:
        import geonamescache
        g = geonamescache.GeonamesCache()
        for c in g.get_cities().values():
            rec = (c["name"], c["countrycode"], int(c["population"] or 0), float(c["latitude"]), float(c["longitude"]))
            for n in {c["name"], *[a for a in c.get("alternatenames", []) if a and len(a) > 2 and a.isascii() is False or (a and a[:1].isupper())]}:
                cities.setdefault(n.lower(), []).append(rec)
        for c in g.get_countries().values():
            countries[c["name"].lower()] = (c["name"], c["iso"], str(c.get("isonumeric") or "").zfill(3))
    except Exception:  # noqa: BLE001  (package missing: the map falls back to config/places.yaml)
        pass
    for alias, name in COUNTRY_ALIASES.items():
        if name.lower() in countries:
            countries[alias] = countries[name.lower()]
    _GEO.update(cities=cities, countries=countries)
    return _GEO


def locate(loc: str, places=None) -> dict | None:
    """'Kassel, Germany' -> a town point; 'United Kingdom' -> a country; None when nothing is recognised."""
    if not loc:
        return None
    hits = [(m.start(), -(m.end() - m.start()), name, lat, lon) for rx, name, lat, lon in places or [] if (m := rx.search(loc))]
    if hits:  # the earliest, then the most specific match ("Cambridge, MA" over "Cambridge")
        _, _, name, lat, lon = min(hits)
        return {"level": "city", "name": name, "lat": lat, "lon": lon}
    geo = _geo()
    tokens = [t.strip(" .") for t in re.split(r"[,/|;()·]|\s+or\s+|\s+-\s+", loc) if t.strip(" .")]
    ctx = None
    for t in tokens:
        c = geo.get("countries", {}).get(t.lower())
        if c:
            ctx = c[1]
    best = None
    for t in tokens:
        if t.lower() in geo.get("countries", {}):  # "USA" is a country, not a town called USA
            continue
        for name, cc, pop, lat, lon in geo.get("cities", {}).get(t.lower(), []):
            score = pop * (50 if ctx and cc == ctx else 1) * (5 if cc in EUROPE_FIRST else 1)
            if best is None or score > best[0]:
                best = (score, {"level": "city", "name": name, "lat": lat, "lon": lon, "country": cc})
        if best:
            return best[1]
    for t in tokens:
        c = geo.get("countries", {}).get(t.lower())
        if c:
            return {"level": "country", "name": c[0], "lat": None, "lon": None, "country": c[1], "iso_num": c[2]}
    return None


STAGE_ORDER = ["Applied", "Screening", "Interview", "Final interview", "Offer", "Accepted"]


def map_points(df: pd.DataFrame, places=None) -> dict:
    places = places if places is not None else load_places()
    points: dict[str, dict] = {}
    unmatched = Counter()
    remote = various = 0
    for r in df.itertuples():
        loc = (r.location or "") if isinstance(r.location, str) else ""
        hit = locate(loc, places)
        if not hit:
            if re.search(r"\bremote\b|home ?office|anywhere", loc, re.I):
                remote += 1
            elif re.search(r"\b(various|multiple|several|diverse|flexible|tbd|verschiedene)\b", loc, re.I):
                various += 1
            elif loc:
                unmatched[loc] += 1
            continue
        p = points.setdefault(hit["name"], {"city": hit["name"], "level": hit["level"], "lat": hit["lat"], "lon": hit["lon"],
                                            "iso_num": hit.get("iso_num"),
                                            "applications": 0, "interviews": 0, "offers": 0, "active": 0, "best": "Applied", "items": []})
        p["applications"] += 1
        p["interviews"] += int(bool(r.reached_interview))
        p["offers"] += int(r.furthest_stage in ("Offer", "Accepted"))
        p["active"] += int(bool(r.active))
        if r.furthest_stage in STAGE_ORDER and STAGE_ORDER.index(r.furthest_stage) > STAGE_ORDER.index(p["best"]):
            p["best"] = r.furthest_stage
        if len(p["items"]) < 6:
            p["items"].append({"id": int(r.id), "company": r.company, "position": r.position, "status": r.status})
    return {"points": sorted(points.values(), key=lambda p: -p["applications"]), "remote": remote, "various": various,
            "unmatched": [{"location": k, "count": v} for k, v in unmatched.most_common(8)]}
