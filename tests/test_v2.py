"""Tests for role dimensions, the scorecard, migration and spreadsheet editing."""

import sqlite3
from datetime import date

import pandas as pd
import pytest

from jobtracker import analysis as A
from jobtracker.categorise import Categoriser
from jobtracker.dimensions import DimensionInferer
from jobtracker.importer import export_excel, import_into, parse_dates, read_tracker
from jobtracker.storage import Store

CAT = Categoriser.from_yaml()
INF = DimensionInferer.from_yaml()


@pytest.mark.parametrize("title,expected", [
    ("Data Research Intern", "Internship"),
    ("Hovione Global Graduate Program 2026", "Graduate / trainee"),
    ("Junior Brand Manager", "Junior / entry"),
    ("Senior Biostatistician", "Experienced"),
    ("Data Scientist", "Mid / unspecified"),
])
def test_seniority_from_title(title, expected):
    assert INF.seniority(title) == expected


def test_seniority_from_years_in_jd():
    jd = INF.analyse_jd("You bring 5+ years of experience in clinical research.")
    assert jd.min_years == 5
    assert INF.seniority("Data Scientist", jd) == "Experienced"


def test_industry_and_size():
    assert INF.industry("F. Hoffmann-La Roche") == "Pharma / biotech"
    assert INF.industry("IQVIA") == "CRO / clinical services"
    assert INF.industry("Acme", "We are a contract research organization") == "CRO / clinical services"
    assert INF.industry("Acme") == "Unknown"
    assert INF.company_size("Novartis") == "Large (1000+)"


def test_jd_requirements():
    a = INF.analyse_jd("Fluent German is required. Candidates must hold a valid work permit. Hybrid model. "
                       "Experience with Python, R and SQL; knowledge of ICH-GCP.")
    assert a.language == "German required"
    assert a.work_authorization == "Requires existing permit / EU-EFTA"
    assert a.work_mode == "Hybrid"
    assert {"python", "R", "sql", "ich-gcp"} <= set(a.skills)


def test_r_is_case_sensitive():
    assert "R" not in INF.analyse_jd("Our r&d team is great, see section r.").skills


def test_german_posting_detected():
    jd = ("Wir suchen für unser Team in Zürich eine engagierte Person. Sie unterstützen die Abteilung bei der "
          "Planung und Durchführung von Studien und sind für die Dokumentation verantwortlich. Wir bieten Ihnen "
          "eine spannende Aufgabe mit Entwicklungsmöglichkeiten und ein motiviertes Team, das Sie bei der "
          "Einarbeitung unterstützt und mit Ihnen gemeinsam die Ziele der Abteilung erreicht.")
    a = INF.analyse_jd(jd)
    assert a.written_in_german and a.language == "German required"


def test_parse_dates_iso_and_dayfirst():
    out = parse_dates(["2026-02-01", "03.04.2026"])
    assert out.iloc[0] == pd.Timestamp("2026-02-01") and out.iloc[1] == pd.Timestamp("2026-04-03")


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.db")
    for i in range(12):
        a = s.add_application(f"Co{i}", "Data Scientist" if i < 6 else "Clinical Trial Assistant",
                              f"2026-0{1 + i % 6}-10", date_posted=f"2026-0{1 + i % 6}-0{1 + i % 2 * 5}",
                              source="Referral" if i < 4 else "LinkedIn")
        if i < 3:
            s.move_stage(a, "Interview", f"2026-0{1 + i % 6}-20")
        else:
            s.move_stage(a, "Rejected", f"2026-0{1 + i % 6}-25")
    return s


def enrich(s, skills=None):
    return A.enrich(s.applications(), s.events(), CAT, date(2026, 10, 1), INF, skills)


def test_scorecard(store):
    df = enrich(store)
    sc = A.scorecard(df, "source", "positive").set_index("value")
    assert sc.loc["Referral", "successes"] == 3 and sc.loc["Referral", "applied"] == 4
    assert sc.loc["Referral", "smoothed"] < sc.loc["Referral", "rate"]  # pulled towards the average
    assert sc.loc["Referral", "lift"] > 0 > sc.loc["LinkedIn", "lift"]
    card = A.scorecard_all(df)
    assert {"source", "role_area", "timing"} <= set(card["dimension"])


def test_timing_buckets(store):
    df = enrich(store)
    assert set(df["timing"]) <= {"0–2 days", "3–7 days", "8–14 days", "15–30 days", "30+ days"}
    assert df["days_to_apply"].notna().all()


def test_flow_links(store):
    links = A.flow_links(enrich(store), store.events())
    pairs = {(r.source, r.target): r.count for r in links.itertuples()}
    assert pairs[("Applied", "Interview")] == 3 and pairs[("Applied", "Rejected")] == 9


def test_jd_match(tmp_path):
    s = Store(tmp_path / "m.db")
    s.add_application("A", "Analyst", "2026-05-01", job_description="Python, SQL and Tableau required.")
    df = enrich(s, ["Python", "SQL"])
    assert df["jd_match"].iloc[0] == pytest.approx(2 / 3)
    assert df["jd_match_bucket"].iloc[0] == "Medium (40–70%)"


def test_override_beats_inference(tmp_path):
    s = Store(tmp_path / "o.db")
    a = s.add_application("Novartis", "Data Scientist", "2026-05-01")
    s.update_application(a, industry="Consulting", seniority="Experienced")
    row = enrich(s).iloc[0]
    assert row["industry"] == "Consulting" and row["industry_auto"] == "Pharma / biotech"
    assert row["seniority"] == "Experienced"


def test_migrates_old_database(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE applications (id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL,
            position TEXT NOT NULL, location TEXT, date_applied TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Applied',
            source TEXT, contact TEXT, url TEXT, notes TEXT, role_area_override TEXT, region_override TEXT,
            created_at TEXT NOT NULL);
        CREATE TABLE stage_events (id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER NOT NULL,
            stage TEXT NOT NULL, date TEXT NOT NULL, note TEXT);
        INSERT INTO applications (company, position, date_applied, status, created_at)
            VALUES ('Old Co', 'Analyst', '2026-03-01', 'Applied', '2026-03-01');
        INSERT INTO stage_events (application_id, stage, date) VALUES (1, 'Applied', '2026-03-01');
    """)
    con.commit()
    con.close()
    s = Store(path)
    apps = s.applications()
    assert apps.loc[0, "company"] == "Old Co" and "job_description" in apps
    s.update_application(1, date_posted="2026-02-20")
    assert enrich(s)["days_to_apply"].iloc[0] == 9


def test_export_roundtrip(store, tmp_path):
    df = enrich(store)
    path = tmp_path / "export.xlsx"
    path.write_bytes(export_excel(df, store.events()))
    back = read_tracker(path, "Applications")
    assert len(back) == len(df) and back["date_posted"].notna().all()
    s2 = Store(tmp_path / "re.db")
    assert import_into(s2, back) == len(df)


def test_import_sample_csv():
    t = read_tracker("sample_data/sample_applications.csv")
    assert {"date_posted", "job_description", "industry", "fit_rating"} <= set(t.columns)
    assert t["date_applied"].notna().all()
