"""API tests: applications, stages, reminders, priorities and analytics."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from jobtracker.api import create_app, guess_title_company
from jobtracker.service import Service

TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Service(tmp_path / "api.db")))


def test_create_and_read(client):
    r = client.post("/api/applications", json={"company": "Novartis", "position": "Junior Data Scientist",
                                               "location": "Basel", "job_description": "2+ years of Python. Fluent German is required."})
    app_id = r.json()["id"]
    a = client.get(f"/api/applications/{app_id}").json()
    assert a["industry"] == "Pharma & biotech" and a["seniority"] == "Junior / entry"
    assert a["role_area"] == "Data science" and a["region"] == "Switzerland"
    assert a["jd_analysis"]["language"] == "German required"
    assert [e["stage"] for e in a["events"]] == ["Applied"]


def test_requires_company_and_position(client):
    assert client.post("/api/applications", json={"company": "X"}).status_code == 422


def test_override_and_reset(client):
    app_id = client.post("/api/applications", json={"company": "Novartis", "position": "Analyst"}).json()["id"]
    a = client.patch(f"/api/applications/{app_id}", json={"industry": "Consulting & professional services"}).json()
    assert a["industry"] == "Consulting & professional services" and a["auto"]["industry"] == "Pharma & biotech"
    a = client.patch(f"/api/applications/{app_id}", json={"industry": ""}).json()
    assert a["industry"] == "Pharma & biotech" and a["overrides"]["industry"] is None


def test_stages_and_status_follow_latest_date(client):
    app_id = client.post("/api/applications", json={"company": "A", "position": "B", "date_applied": d(-20)}).json()["id"]
    a = client.post(f"/api/applications/{app_id}/stages", json={"stage": "Interview", "date": d(3), "note": "Call"}).json()
    assert a["status"] == "Interview" and a["furthest_stage"] == "Interview"
    # Backfilling an earlier screening doesn't change the current status.
    a = client.post(f"/api/applications/{app_id}/stages", json={"stage": "Screening", "date": d(-10)}).json()
    assert a["status"] == "Interview"
    ov = client.get("/api/overview").json()
    assert ov["upcoming_interviews"][0]["application_id"] == app_id
    assert any(p["kind"] == "interview" for p in ov["priorities"])
    # Edit and delete events.
    ev = {e["stage"]: e["id"] for e in a["events"]}
    assert client.delete(f"/api/events/{ev['Interview']}").status_code == 200
    assert client.get(f"/api/applications/{app_id}").json()["status"] == "Screening"
    assert client.patch(f"/api/events/{ev['Screening']}", json={"stage": "Rejected"}).status_code == 200
    assert client.get(f"/api/applications/{app_id}").json()["status"] == "Rejected"


def test_priorities_and_actions(client):
    s = client
    old = s.post("/api/applications", json={"company": "Old", "position": "Analyst", "date_applied": d(-60)}).json()["id"]
    mid = s.post("/api/applications", json={"company": "Mid", "position": "Analyst", "date_applied": d(-15)}).json()["id"]
    s.post("/api/reminders", json={"title": "Apply to round 2", "due_date": d(0)})
    s.post("/api/reminders", json={"title": "Later", "due_date": d(5)})
    items = s.get("/api/overview").json()["priorities"]
    kinds = {i["kind"]: i for i in items}
    assert {"ghost", "follow_up", "reminder"} <= set(kinds)
    assert kinds["ghost"]["application_id"] == old and kinds["follow_up"]["application_id"] == mid
    assert s.post("/api/priorities/act", json={"key": kinds["ghost"]["key"], "action": "mark_ghosted"}).status_code == 200
    assert s.get(f"/api/applications/{old}").json()["status"] == "Ghosted"
    s.post("/api/priorities/act", json={"key": kinds["follow_up"]["key"], "action": "followed_up"})
    s.post("/api/priorities/act", json={"key": kinds["reminder"]["key"], "action": "done"})
    left = {i["kind"] for i in s.get("/api/overview").json()["priorities"]}
    assert left.isdisjoint({"ghost", "follow_up", "reminder"})
    assert [r["title"] for r in s.get("/api/overview").json()["upcoming_reminders"]] == ["Later"]


def test_snooze(client):
    client.post("/api/applications", json={"company": "Mid", "position": "Analyst", "date_applied": d(-15)})
    key = client.get("/api/overview").json()["priorities"][0]["key"]
    client.post("/api/priorities/act", json={"key": key, "action": "snooze", "days": 3})
    assert client.get("/api/overview").json()["priorities"] == []


def test_filters_and_analytics(client):
    client.post("/api/sample")
    allv = client.get("/api/applications").json()
    fam = client.get("/api/applications?role_area=Data science").json()["items"]
    assert 0 < len(fam) < allv["total"] and all(a["role_area"] == "Data science" for a in fam)
    an = client.get("/api/analytics?metric=positive&dim=source").json()
    c = an["conversion"]
    assert c["application_to_interview"]["numerator"] > 0
    assert {"application_to_response", "interview_to_later_round", "interview_to_offer", "median_days_to_response"} <= set(c)
    assert any(r["value"] == "Referral" for r in an["by_dim"])
    assert an["heatmap"]["rows"] and an["flow"]


def test_parse_and_guess(client):
    p = client.post("/api/parse", json={"job_description": "Data Analyst\nRoche is hiring. Hybrid. SQL and Python."}).json()
    assert p["guess"] == {"position": "Data Analyst", "company": "Roche"}
    assert p["work_mode"] == "Hybrid"
    assert guess_title_company("Title: Medical Writer\nCompany: Lonza")["company"] == "Lonza"


def test_settings_and_rules(client):
    s = client.put("/api/settings", json={"my_skills": ["Python"], "weekly_goal": 5, "unknown": 1}).json()
    assert s["my_skills"] == ["Python"] and "unknown" not in s
    assert client.put("/api/rules/categories", json={"text": "role_areas: [oops"}).status_code == 422


def test_export_and_clear(client):
    client.post("/api/sample")
    assert client.get("/api/export.xlsx").status_code == 200
    assert client.delete("/api/applications").status_code == 422
    assert client.delete("/api/applications?confirm=DELETE").status_code == 200
    assert client.get("/api/applications").json()["total"] == 0
