from datetime import date

import pandas as pd
import pytest

from jobtracker import analysis as A
from jobtracker.categorise import Categoriser
from jobtracker.importer import build_history, normalise_status, read_tracker, import_into
from jobtracker.storage import Store

CAT = Categoriser.from_yaml()


@pytest.mark.parametrize("title,expected", [
    ("Clinical Trial Assistant (Switzerland)", "Clinical operations"),
    ("Assistant CRA", "Clinical operations"),
    ("Junior Data Analyst", "Data science / AI"),
    ("Applied AI Engineer", "Data science / AI"),
    ("Hovione Global Graduate Program 2026", "Graduate / trainee programme"),
    ("Medical Writer", "Medical / regulatory / safety"),
    ("Junior Brand Manager", "Commercial / marketing"),
    ("Business Analyst", "Consulting / business analysis"),
    ("Maintenance Technician", "Other"),  # "ai" must not match inside words
])
def test_role_area(title, expected):
    assert CAT.role_area(title) == expected


def test_region():
    assert CAT.region("Allschwil, Basel-Country, Switzerland") == "Switzerland"
    assert CAT.region("Maidenhead, United Kingdom") == "United Kingdom"
    assert CAT.region(None) == CAT.default_region


def test_status_normalisation():
    assert normalise_status("Submitted") == "Applied"
    assert normalise_status(" rejected ") == "Rejected"
    assert normalise_status(float("nan")) is None


def test_history_interview_then_rejected():
    status, hist = build_history(pd.Series({"date_applied": pd.Timestamp("2026-05-01"),
                                            "status": "Interview", "final_status": "Rejected"}))
    assert status == "Rejected"
    assert [h[0] for h in hist] == ["Applied", "Interview", "Rejected"]


def test_wilson():
    lo, hi = A.wilson_interval(1, 10)
    assert 0 < lo < 0.1 < hi < 0.5
    assert A.wilson_interval(0, 0) == (0.0, 0.0)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.db")
    a = s.add_application("Acme", "Data Scientist", "2026-09-01", location="Zurich")
    s.move_stage(a, "Interview", "2026-09-11")
    s.move_stage(a, "Rejected", "2026-09-20")
    s.add_application("Beta", "Clinical Trial Assistant", "2026-08-01", status="Ghosted", location="Basel")
    s.add_application("Gamma", "Data Analyst", "2026-10-10", location="London")
    return s


def test_enrich_and_breakdown(store):
    df = A.enrich(store.applications(), store.events(), CAT, date(2026, 10, 16))
    acme = df[df.company == "Acme"].iloc[0]
    assert acme.reached_interview and acme.outcome == "Interviewed"
    assert acme.days_to_response == 10
    b = A.breakdown(df, "role_area").set_index("role_area")
    assert b.loc["Data science / AI", "applied"] == 2
    assert b.loc["Data science / AI", "interviews"] == 1
    assert b.loc["Clinical operations", "ghost_rate"] == 1.0
    f = A.funnel(df).set_index("step")["count"]
    assert f["Applied"] == 3 and f["Interview"] == 1


def test_follow_ups(store):
    df = A.enrich(store.applications(), store.events(), CAT, date(2026, 12, 1))
    fu = A.follow_ups(df, 10, 42)
    assert list(fu["company"]) == ["Gamma"]
    assert fu.iloc[0]["action"] == "Mark as ghosted"


def test_override(store):
    apps = store.applications()
    gid = int(apps[apps.company == "Gamma"].id.iloc[0])
    store.update_application(gid, role_area_override="Research / academia")
    df = A.enrich(store.applications(), store.events(), CAT)
    assert df[df.id == gid].role_area.iloc[0] == "Research / academia"


def test_import_messy_excel(tmp_path):
    # Title rows and a summary block above the real header, like many home-made trackers.
    raw = pd.DataFrame([
        ["My tracker", None, None, None, None],
        [None, None, None, None, None],
        ["Company", "Position", "Date Applied", "Application Status", "Details"],
        ["Acme", "Data Scientist", "2026-09-01", "Submitted", "Zurich"],
        ["Beta", "CRA", "2026-08-01", "Interview", "Basel"],
        [None, None, None, None, None],
    ])
    path = tmp_path / "t.xlsx"
    raw.to_excel(path, header=False, index=False)
    tidy = read_tracker(path)
    assert len(tidy) == 2 and set(tidy.status) == {"Applied", "Interview"}
    s = Store(tmp_path / "i.db")
    assert import_into(s, tidy) == 2
    df = A.enrich(s.applications(), s.events(), CAT)
    assert df.reached_interview.sum() == 1
    assert df.days_to_response.isna().all()  # imported stages have no real reply date
