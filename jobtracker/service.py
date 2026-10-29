"""Shared application state for the API: the store, rules, settings and the enriched table."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from . import analysis as A
from .categorise import DEFAULT_CONFIG as CATEGORIES_YAML, Categoriser
from .dimensions import DEFAULT_CONFIG as DIMENSIONS_YAML, DimensionInferer
from .storage import Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "tracker.db"
SAMPLE = ROOT / "sample_data" / "sample_applications.csv"

DEFAULT_SETTINGS = {
    "my_skills": [],
    "weekly_goal": 10,
    "follow_up_after": 10,
    "ghost_after": 42,
    "too_new_days": 21,
    "name": "",
    # CV and profile used for fit analysis (stored only in the local database).
    "cv_text": "",
    "cv_filename": "",
    "profile": {"languages": [], "permits": {}, "years_experience": None, "degree": "", "locations": [],
                "relocate": False},
    # Local AI (Ollama)
    "ai_engine": "auto",           # kept for older databases; AI no longer scores jobs
    "digest_auto": False,          # read new job descriptions with Ollama in the background
    "rank_last_codes": [], "rank_parts": [],         # job codes in the last ranking prompt, to spot ones missing from the reply
    "rank_goals": "",              # your criteria for chat rankings (kept private, prefilled each time)
    "ollama_url": "http://localhost:11434",
    "ollama_model": "",
    # How you write, used by the builders' advice and the chatbot brief.
    "writing": {"spelling": "", "tone": "", "avoid": "", "samples": ""},
}


@dataclass
class Snapshot:
    df: pd.DataFrame
    events: pd.DataFrame
    settings: dict
    cat: Categoriser
    inferer: DimensionInferer


class Service:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or os.environ.get("JOBTRACKER_DB", DEFAULT_DB))
        self.store = Store(self.db_path)
        self._lock = threading.Lock()
        self._key = None
        self._snap: Snapshot | None = None

    # The enriched table is rebuilt only when the database, the rules or the date change.
    def _cache_key(self):
        def mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime_ns
            except FileNotFoundError:
                return 0
        return (mtime(self.db_path), mtime(CATEGORIES_YAML), mtime(DIMENSIONS_YAML), date.today())

    def invalidate(self) -> None:
        self._key = None

    def settings(self) -> dict:
        return {k: self.store.get_setting(k, v) for k, v in DEFAULT_SETTINGS.items()}

    def snapshot(self) -> Snapshot:
        with self._lock:
            key = self._cache_key()
            if self._snap is None or key != self._key:
                cat = Categoriser.from_yaml(CATEGORIES_YAML)
                inferer = DimensionInferer.from_yaml(DIMENSIONS_YAML)
                settings = self.settings()
                events = self.store.events()
                df = A.enrich(self.store.applications(), events, cat, date.today(), inferer, settings["my_skills"])
                self._snap = Snapshot(df, events, settings, cat, inferer)
                self._key = key
            return self._snap


FILTER_FIELDS = ["role_area", "industry", "seniority", "region", "source", "status", "company_size",
                 "work_mode", "language", "work_authorization"]


REACHED_ORDER = ["Applied", "Screening", "Interview", "Final interview", "Offer", "Accepted"]


def apply_filters(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Filters shared by every list, chart and insight: multi-value fields are separated by "|"."""
    if df.empty:
        return df
    d = df
    for f in FILTER_FIELDS:
        v = params.get(f)
        if v:
            vals = [x for x in str(v).split("|") if x]
            if vals:
                d = d[d[f].astype(str).isin(vals)]
    reached = params.get("reached")
    if reached in REACHED_ORDER:
        rank = {s: i for i, s in enumerate(REACHED_ORDER)}
        d = d[d["furthest_stage"].map(rank).fillna(0) >= rank[reached]]
    if params.get("date_from"):
        d = d[d["date_applied"] >= pd.Timestamp(params["date_from"])]
    if params.get("date_to"):
        d = d[d["date_applied"] <= pd.Timestamp(params["date_to"])]
    if params.get("active") in ("1", "true", True):
        d = d[d["active"]]
    q = (params.get("q") or "").strip().lower()
    if q:
        hay = (d["company"].fillna("") + " " + d["position"].fillna("") + " " + d["location"].fillna("") + " "
               + d["notes"].fillna("") + " " + d["role_area"].fillna("")).str.lower()
        d = d[hay.str.contains(q, regex=False)]
    return d
