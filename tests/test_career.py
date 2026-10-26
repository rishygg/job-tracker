"""Career development: interview journal, themes, practice, stories, skills report and notes."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobtracker import career as CR
from jobtracker.api import create_app
from jobtracker.service import Service

TODAY = date.today()
JD = (Path(__file__).parent / "fixtures" / "jd_digital.txt").read_text()
CV = (Path(__file__).parent / "fixtures" / "cv.txt").read_text()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


@pytest.fixture
def client(tmp_path):
    c = TestClient(create_app(Service(tmp_path / "career.db")))
    c.put("/api/settings", json={"cv_text": CV, "ollama_url": "http://127.0.0.1:9"})
    return c


def test_categorise_and_competencies():
    assert CR.categorise("Tell me about a time you disagreed with your supervisor") == "Behavioural"
    assert CR.categorise("Why do you want to work at Roche?") == "Motivation"
    assert CR.categorise("What would you do if two managers gave you conflicting deadlines?") == "Situational"
    assert CR.categorise("Walk me through your CV") == "Experience & CV"
    assert CR.categorise("What is your notice period?") == "Logistics"
    assert CR.categorise("Explain what a p-value means") == "Technical"
    assert "Conflict & disagreement" in CR.competencies("Tell me about a time you disagreed with a colleague")


def test_answer_feedback_rules():
    weak = CR.answer_feedback("Tell me about a time you solved a problem", "We fixed it together as a team. We did well. We were happy.")
    assert weak["score"] <= 2 and any("short" in x for x in weak["improve"])
    assert weak["star"] and not weak["star"]["result"]
    strong = CR.answer_feedback(
        "Tell me about a time you solved a problem",
        "During my internship at the institute, the lab's MRI quality checks took two days per batch. My task was to "
        "speed this up without missing errors. I wrote a Python pipeline that ran the checks automatically, I tested it "
        "against 200 scans that had been checked by hand, and I presented it to the team. As a result, checks took "
        "40 minutes instead of two days and the pipeline was adopted for the whole cohort of 1,200 participants. "
        "I learned to validate a tool against the manual process before asking people to trust it.")
    assert strong["score"] >= 4 and all(strong["star"].values())


def test_journal_flow(client):
    app_id = client.post("/api/applications", json={"company": "Norgine", "position": "Digital Analyst",
                                                    "job_description": JD, "date_applied": d(-20)}).json()["id"]
    client.post(f"/api/applications/{app_id}/stages", json={"stage": "Interview", "date": d(-2)})
    pri = client.get("/api/overview").json()["priorities"]
    assert any(p["kind"] == "journal" and p["application_id"] == app_id for p in pri)

    r = client.post("/api/career/interviews", json={
        "application_id": app_id, "date": d(-2), "round": "First interview", "rating": 3,
        "struggled": "Explaining my thesis to a non-technical manager", "feedback": "Wanted more detail on stakeholders",
        "questions": [{"question": "Why do you want to work at Norgine?", "rating": 4},
                      {"question": "Tell me about a time you dealt with a difficult stakeholder", "rating": 2},
                      {"question": "Walk me through your CV"}]})
    iid = r.json()["id"]
    data = client.get("/api/career/interviews").json()
    iv = data["interviews"][0]
    assert iv["company"] == "Norgine" and len(iv["questions"]) == 3
    assert iv["questions"][1]["category"] == "Behavioural"
    assert not data["to_log"]  # logged, so no longer asked for
    assert not any(p["kind"] == "journal" for p in client.get("/api/overview").json()["priorities"])
    th = data["themes"]
    assert th["questions"] == 3 and any(f["area"] == "Stakeholder management" for f in th["focus"])

    # Second interview elsewhere repeats a question -> recurring.
    other = client.post("/api/applications", json={"company": "Roche", "position": "Analyst"}).json()["id"]
    client.post("/api/career/interviews", json={"application_id": other, "date": d(-1), "questions": [
        {"question": "Tell me about a time you handled a difficult stakeholder", "rating": 2}]})
    th = client.get("/api/career/interviews").json()["themes"]
    assert th["repeated"] and th["repeated"][0]["times"] == 2

    # Editing keeps question ids, so story links survive.
    sid = client.post("/api/career/stories", json={"title": "Thesis pipeline", "action": "I built a pipeline",
                                                   "competencies": ["Stakeholder management"]}).json()["id"]
    qs = client.get("/api/career/interviews").json()["interviews"][-1]["questions"]
    qs[1]["story_id"] = sid
    client.patch(f"/api/career/interviews/{iid}", json={"questions": qs, "outcome": "Passed"})
    st = client.get("/api/career/stories").json()["stories"][0]
    assert st["used"] and st["used"][0]["company"] == "Norgine"
    assert any("result" in t for t in st["tips"])


def test_practice_suggestions(client):
    app_id = client.post("/api/applications", json={"company": "Norgine", "position": "Digital Analyst",
                                                    "job_description": JD, "date_applied": d(-20)}).json()["id"]
    client.post(f"/api/applications/{app_id}/stages", json={"stage": "Final interview", "date": d(3)})
    client.post("/api/career/interviews", json={"application_id": app_id, "date": d(-5), "questions": [
        {"question": "Tell me about a time you dealt with conflict in a team", "rating": 2}]})
    p = client.get("/api/career/practice").json()
    assert p["upcoming"][0]["company"] == "Norgine" and p["upcoming"][0]["when"] == "in 3 days"
    qs = [s["question"] for s in p["suggested"]]
    assert any("Why Norgine" in q for q in qs)
    assert any("conflict" in q for q in qs)
    assert any(s["source"] == "upcoming" and "role asks for" in s["question"] for s in p["suggested"])

    r = client.post("/api/career/practice", json={"question": qs[0], "answer": "We did it as a team.", "ref": f"application:{app_id}"}).json()
    assert r["feedback"]["method"] == "rules" and r["feedback"]["improve"]
    assert client.post("/api/career/practice/questions", json={"application_id": app_id}).status_code == 503  # no Ollama


def test_story_suggestions_and_skills_report(client):
    client.post("/api/applications", json={"company": "Norgine", "position": "Digital Analyst", "job_description": JD})
    client.post("/api/opportunities", json={"company": "Roche", "position": "Data Analyst", "job_description": JD + "\nSQL and Tableau required."})
    sug = client.get("/api/career/stories").json()["suggestions"]
    assert sug and all("evidence_id" in s for s in sug)
    sid = client.post("/api/career/stories", json={"evidence_id": sug[0]["evidence_id"]}).json()["id"]
    assert client.get("/api/career/stories").json()["stories"][0]["id"] == sid
    assert all(s["evidence_id"] != sug[0]["evidence_id"] for s in client.get("/api/career/stories").json()["suggestions"])

    rep = client.get("/api/career/skills").json()
    assert rep["jobs"] == 2 and rep["skills"]
    assert any(s["skill"] == "sql" for s in rep["skills"])
    assert all(isinstance(s["have"], bool) for s in rep["skills"])
    assert rep["fits_counted"] == 2  # both were scored instantly on save


def test_notes(client):
    client.post("/api/applications", json={"company": "Novartis", "position": "Analyst", "job_description": "Pharma company. " * 10})
    nid = client.post("/api/career/notes", json={"title": "Pharma hiring cycles", "industry": "Pharma & biotech",
                                                 "body": "Graduate programmes open in autumn.", "tags": ["timing"]}).json()["id"]
    n = client.get("/api/career/notes").json()
    assert n["notes"][0]["tags"] == ["timing"]
    assert "Pharma & biotech" in n["industry_stats"]
    client.patch(f"/api/career/notes/{nid}", json={"body": "Updated"})
    assert client.get("/api/career/notes").json()["notes"][0]["body"] == "Updated"
    client.delete(f"/api/career/notes/{nid}")
    assert client.get("/api/career/notes").json()["notes"] == []
