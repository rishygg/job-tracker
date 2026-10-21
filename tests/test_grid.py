"""Spreadsheet-style editing: the diff between the grid as loaded and as edited is saved correctly."""

from datetime import date

import pandas as pd

from jobtracker import analysis as A
from jobtracker.categorise import Categoriser
from jobtracker.dimensions import DimensionInferer
from jobtracker.storage import Store
from jobtracker.ui.applications import GRID, save_grid
from jobtracker.ui.common import DEFAULT_SETTINGS, Ctx


def make_ctx(store):
    cat, inf = Categoriser.from_yaml(), DimensionInferer.from_yaml()
    ev = store.events()
    df = A.enrich(store.applications(), ev, cat, date(2026, 10, 1), inf, [])
    return Ctx(store, cat, inf, dict(DEFAULT_SETTINGS), df, ev)


def test_save_grid(tmp_path):
    s = Store(tmp_path / "g.db")
    a = s.add_application("Novartis", "Data Scientist", "2026-09-01", location="Basel")
    b = s.add_application("Acme", "Analyst", "2026-09-02")
    s.add_application("Gone", "Clerk", "2026-09-03")
    ctx = make_ctx(s)
    view = ctx.df[GRID].reset_index(drop=True)
    edited = view.copy()
    ia = edited.index[edited["id"] == a][0]
    ib = edited.index[edited["id"] == b][0]
    edited.loc[ia, "status"] = "Interview"
    edited.loc[ia, "notes"] = "Spoke to Anna"
    edited.loc[ia, "industry"] = "Pharma / biotech"      # same as inferred -> stays automatic
    edited.loc[ib, "industry"] = "Consulting"            # differs -> stored as override
    edited.loc[ib, "date_posted"] = pd.Timestamp("2026-08-30")
    edited.loc[ib, "role_area"] = "Research / academia"
    edited = edited[edited["company"] != "Gone"]          # deleted row
    new = {c: None for c in GRID}
    new.update(company="NewCo", position="Junior Data Analyst", status="Applied")
    edited = pd.concat([edited, pd.DataFrame([new])], ignore_index=True)

    counts = save_grid(ctx, view, edited)
    assert counts == {"changed": 2, "added": 1, "deleted": 1, "skipped": 0}

    apps = s.applications().set_index("company")
    assert apps.loc["Novartis", "status"] == "Interview"
    assert apps.loc["Novartis", "notes"] == "Spoke to Anna"
    assert pd.isna(apps.loc["Novartis", "industry"])
    assert apps.loc["Acme", "industry"] == "Consulting"
    assert apps.loc["Acme", "role_area_override"] == "Research / academia"
    assert apps.loc["Acme", "date_posted"] == pd.Timestamp("2026-08-30")
    assert "Gone" not in apps.index and "NewCo" in apps.index
    assert list(s.events(a)["stage"]) == ["Applied", "Interview"]


def test_unchanged_grid_saves_nothing(tmp_path):
    s = Store(tmp_path / "n.db")
    s.add_application("Roche", "Medical Writer", "2026-09-01", job_description="Fluent German is required.")
    ctx = make_ctx(s)
    view = ctx.df[GRID].reset_index(drop=True)
    assert save_grid(ctx, view, view.copy()) == {"changed": 0, "added": 0, "deleted": 0, "skipped": 0}
