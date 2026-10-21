"""Shared state, labels and helpers for the Streamlit pages."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from jobtracker import analysis as A
from jobtracker.categorise import DEFAULT_CONFIG as CATEGORIES_YAML, Categoriser
from jobtracker.dimensions import DEFAULT_CONFIG as DIMENSIONS_YAML, DimensionInferer
from jobtracker.storage import Store

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("JOBTRACKER_DB", ROOT / "data" / "tracker.db"))
SAMPLE = ROOT / "sample_data" / "sample_applications.csv"

OUTCOME_COLORS = {
    "Offer": "#1b7f5c", "Interviewed": "#3aa17e", "Rejected": "#b8b8c4",
    "Ghosted": "#e0a43a", "Waiting": "#4a78c2", "Withdrawn": "#8e8e99",
}
OUTCOME_ORDER = ["Offer", "Interviewed", "Rejected", "Ghosted", "Withdrawn", "Waiting"]
STAGE_COLORS = {
    "Applied": "#4a78c2", "Screening": "#5b9bd5", "Interview": "#3aa17e", "Final interview": "#2b8f6b",
    "Offer": "#1b7f5c", "Accepted": "#13694b", "Rejected": "#b8b8c4", "Ghosted": "#e0a43a",
    "Withdrawn": "#8e8e99", "Awaiting reply": "#9db6e0",
}
VERDICT_STYLE = {
    "Strength": ("🟢", "#1b7f5c"), "Promising": ("🟩", "#3aa17e"), "About average": ("⚪", "#8e8e99"),
    "Below average": ("🟧", "#e0a43a"), "Weak spot": ("🔴", "#c0504d"), "Too few to tell": ("·", "#b8b8c4"),
}
ACCENT = "#1b7f5c"
MUTED = "#b8c9e8"

DEFAULT_SETTINGS = {
    "my_skills": [],
    "weekly_goal": 10,
    "follow_up_after": 10,
    "ghost_after": 42,
    "too_new_days": 21,
}


@dataclass
class Ctx:
    store: Store
    cat: Categoriser
    inferer: DimensionInferer
    settings: dict
    df: pd.DataFrame
    events: pd.DataFrame

    @property
    def my_skills(self) -> list[str]:
        return self.settings.get("my_skills", [])


@st.cache_resource
def get_store() -> Store:
    return Store(DB_PATH)


def load_settings(store: Store) -> dict:
    return {k: store.get_setting(k, v) for k, v in DEFAULT_SETTINGS.items()}


def build_ctx() -> Ctx:
    store = get_store()
    cat = Categoriser.from_yaml(CATEGORIES_YAML)
    inferer = DimensionInferer.from_yaml(DIMENSIONS_YAML)
    settings = load_settings(store)
    events = store.events()
    df = A.enrich(store.applications(), events, cat, date.today(), inferer, settings["my_skills"])
    return Ctx(store, cat, inferer, settings, df, events)


# ---- formatting ---------------------------------------------------------
def pct(x, digits: int = 0) -> str:
    return "–" if x is None or pd.isna(x) else f"{x:.{digits}%}"


def txt(v) -> str:
    """Display-safe string: missing values (None/NaN) become ''."""
    return "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)


def plot_layout(fig, height: int = 320, **kw):
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=height, legend_title_text="",
                      font=dict(size=12), **kw)
    return fig


def empty_state(message: str) -> None:
    st.info(message)
