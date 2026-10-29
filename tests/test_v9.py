"""v9: prepare checklist, batch + undo, bookmark inbox, momentum, milestones, wrapped, company replies, map."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobtracker.api import create_app
from jobtracker.service import Service

TODAY = date.today()
JD = (Path(__file__).parent / "fixtures" / "jd_digital.txt").read_text()
CV = (Path(__file__).parent / "fixtures" / "cv.txt").read_text()


def d(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


@pytest.fixture
def client(tmp_path):
    c = TestClient(create_app(Service(tmp_path / "v9.db")), follow_redirects=False)
    c.put("/api/settings", json={"cv_text": CV, "ollama_url": "http://127.0.0.1:9", "weekly_goal": 2})
    return c


def test_prepare_checklist(client):
    oid = client.post("/api/opportunities", json={"company": "Norgine", "position": "Analyst", "job_description": JD}).json()["id"]
    st = client.get(f"/api/prepare/opportunity/{oid}").json()
    by = {s["id"]: s for s in st["steps"]}
    assert [s["id"] for s in st["steps"]] == ["fit", "apply", "interview", "journal"]
    assert by["fit"]["done"] and not by["apply"]["done"]
    prep = client.get(f"/api/prepare/opportunity/{oid}/interview").json()
    assert any("Why Norgine" in q["question"] for q in prep["suggested"])
    client.post("/api/career/practice", json={"question": "Why Norgine?", "answer": "Because.", "ref": f"opportunity:{oid}"})
    aid = client.post(f"/api/opportunities/{oid}/apply").json()["application_id"]
    st = client.get(f"/api/prepare/application/{aid}").json()
    by = {s["id"]: s for s in st["steps"]}
    assert by["apply"]["done"] and by["interview"]["practised"] == 1  # practice followed the job
    assert by["fit"]["done"]


def test_batch_and_undo(client):
    ids = [client.post("/api/applications", json={"company": f"C{i}", "position": "Analyst", "date_applied": d(-60)}).json()["id"]
           for i in range(3)]
    r = client.post("/api/applications/batch", json={"ids": ids[:2], "action": "Rejected"}).json()
    assert r["count"] == 2
    assert client.get(f"/api/applications/{ids[0]}").json()["status"] == "Rejected"
    client.post("/api/events/undo", json={"event_ids": r["event_ids"]})
    assert client.get(f"/api/applications/{ids[0]}").json()["status"] == "Applied"
    one = client.post(f"/api/applications/{ids[2]}/stages", json={"stage": "Screening"}).json()
    assert one["event_id"]
    g = client.post("/api/priorities/ghost-all").json()
    assert g["count"] == 2  # the two still waiting after 60 days (ids[2] moved to Screening)
    client.post("/api/applications/batch", json={"ids": ids, "action": "delete"})
    assert client.get("/api/applications").json()["total"] == 0


def test_bookmark_inbox(client):
    page = "Home\nJobs\nAbout the job\nWe are looking for a Data Analyst to join our digital team. " * 3 + "\nShow less\nAbout the company\nAds"
    r = client.post("/inbox", data={"text": page, "title": "Data Analyst - Norgine | LinkedIn", "url": "https://example.com/job/1"})
    assert r.status_code == 303 and "/?inbox=" in r.headers["location"]
    iid = r.headers["location"].split("=")[1]
    item = client.get(f"/api/inbox/{iid}").json()
    assert item["guess"]["company"] == "Norgine" and item["guess"]["position"] == "Data Analyst"
    assert item["text"].startswith("About the job") and "Ads" not in item["text"]
    assert client.get("/api/bookmarklet").json()["href"].startswith("javascript:")


def test_momentum_milestones_map(client):
    for i in range(6):
        aid = client.post("/api/applications", json={"company": ["Roche", "Novartis", "Lonza"][i % 3], "position": "Data Analyst",
                                                     "location": ["Basel", "Zurich", "Remote"][i % 3], "source": "LinkedIn",
                                                     "date_applied": d(-i * 3)}).json()["id"]
        if i == 1:
            client.post(f"/api/applications/{aid}/stages", json={"stage": "Interview", "date": d(-1)})
    m = client.get("/api/momentum").json()
    assert m["this_week"] >= 1 and m["cells"][-1]["date"] == TODAY.isoformat() and m["streak_days"] >= 1
    ms = client.get("/api/milestones").json()
    assert ms["new"] == []  # first run: nothing is "new"
    assert {x["id"]: x["achieved"] for x in ms["items"]}["first_interview"]
    client.post("/api/career/stories", json={"title": "A story"})
    ms = client.get("/api/milestones").json()
    assert [x["id"] for x in ms["new"]] == ["story_1"]
    client.post("/api/milestones/seen", json={"ids": ["story_1"]})
    assert client.get("/api/milestones").json()["new"] == []

    mp = client.get("/api/map").json()
    assert {p["city"] for p in mp["points"]} == {"Basel", "Zurich"} and mp["remote"] == 2
    assert {"fastest", "slowest", "responsive", "ghosts"} <= client.get("/api/analytics/companies").json().keys()
