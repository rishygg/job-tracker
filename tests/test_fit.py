"""Fit analysis (rules), the profile as entries, chat-assistant prompts and rankings, background reading with a fake
Ollama server, and the API endpoints."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobtracker.api import create_app
from jobtracker.dimensions import DimensionInferer
from jobtracker.fit import analyse_keywords, extract_requirements, recommend
from jobtracker.service import Service

FIX = Path(__file__).parent / "fixtures"
CV = (FIX / "cv.txt").read_text()
MESSY = (FIX / "cv_messy.txt").read_text()
INF = DimensionInferer.from_yaml()
JD = """Data Scientist, Clinical Imaging
About us
We are a biotech in Basel developing imaging biomarkers.
Your responsibilities
- Analyse MRI data from clinical trials
Requirements
- MSc or PhD in neuroscience, physics or a related field
- 2+ years of experience analysing neuroimaging data
- Strong programming skills in Python
- Experience with statistical modelling in R
Nice to have
- Experience with PyTorch or deep learning
- German is a plus
"""
PROFILE = {"languages": [{"language": "English", "level": "Native"}, {"language": "German", "level": "B1"}],
           "degree": "Master (in progress)", "years_experience": 2,
           "permits": {"Switzerland": "Have a valid work permit", "United Kingdom": "Would need sponsorship"},
           "locations": ["Switzerland"], "relocate": False}


def test_extract_essential_vs_preferred():
    reqs = extract_requirements(JD)
    kinds = {r["text"]: r["type"] for r in reqs}
    assert kinds["Strong programming skills in Python"] == "essential"
    assert kinds["Experience with PyTorch or deep learning"] == "preferred"
    assert kinds["German is a plus"] == "preferred"
    assert not any("Analyse MRI data" in t for t in kinds)  # responsibilities aren't requirements


def test_cue_words_without_sections():
    reqs = extract_requirements("We need someone with a degree in biology. Experience with SQL is a plus. We offer lunch.")
    assert {r["type"] for r in reqs} == {"essential", "preferred"} and len(reqs) == 2


def test_keyword_analysis():
    res = analyse_keywords(CV, JD, PROFILE, INF, "Switzerland")
    by = {r["text"]: r for r in res["requirements"]}
    assert by["Strong programming skills in Python"]["status"] == "met"
    assert "Python" in by["Strong programming skills in Python"]["evidence"]
    assert by["Experience with PyTorch or deep learning"]["status"] == "missing"
    assert by["2+ years of experience analysing neuroimaging data"]["status"] == "met"
    assert res["recommendation"]["action"] in ("Apply", "Apply with caveats")
    assert res["counts"]["essential"] == 4


def test_language_blocker_deprioritises():
    jd = JD.replace("- German is a plus", "- Fluent German is required")
    res = analyse_keywords(CV, jd, PROFILE, INF, "Switzerland")
    assert any(b["type"] == "Language" and b["severity"] == "high" for b in res["blockers"])
    assert res["recommendation"]["action"] in ("Deprioritise", "Apply with caveats")


def test_permit_blocker():
    jd = JD + "\nCandidates must hold a valid work permit for the UK."
    res = analyse_keywords(CV, jd, PROFILE, INF, "United Kingdom")
    assert any(b["type"] == "Work permit" and b["severity"] == "high" for b in res["blockers"])


def test_recommend_rules():
    reqs = [{"type": "essential", "status": "met"}] * 4
    assert recommend(0.9, [], reqs)["action"] == "Apply"
    assert recommend(0.2, [], [{"type": "essential", "status": "missing"}] * 3)["action"] == "Deprioritise"


# ---------------------------------------------------------------- fake Ollama


# ---------------------------------------------------------------- the user's two problem postings
def test_benefits_and_company_text_are_not_requirements():
    reqs = extract_requirements((FIX / "jd_jobsch.txt").read_text())
    texts = " ".join(r["text"] for r in reqs)
    assert len(reqs) <= 6, reqs
    assert "Master 2 in Data Engineering" in texts and "English" in texts
    assert not any(w in texts for w in ("reasons to join", "Capgemini group", "certification path", "sogeti.com", "interview tips"))
    assert any(r["soft"] for r in reqs if "Autonomy" in r["text"])


def test_site_summary_line_is_not_double_counted():
    reqs = extract_requirements((FIX / "jd_uk_summary.txt").read_text())
    texts = [r["text"] for r in reqs]
    assert not any(t.startswith(("Requirements:", "Degree level education")) for t in texts)
    assert "Microsoft Office" not in texts
    pref = [r["text"] for r in reqs if r["type"] == "preferred"]
    assert any("medical sales" in t for t in pref) and any("primary care" in t for t in pref)
    res = analyse_keywords(CV, (FIX / "jd_uk_summary.txt").read_text(), {**PROFILE, "degree": "Master"}, INF, "United Kingdom")
    degree = next(r for r in res["requirements"] if "degree level" in r["text"].lower())
    assert degree["status"] == "met"  # from the profile, not from a random CV line
    assert len(res["soft_skills"]) == 2  # listed separately, not counted as failures


def test_german_posting_has_no_score():
    jd = ("Praktikant/in Datenanalyse 80-100%\nRoche AG\nIhre Aufgaben\nSie unterstützen das Team bei der Analyse von Daten "
          "und der Erstellung von Berichten für die Geschäftsleitung. Ihr Profil\nSie haben ein abgeschlossenes Studium und "
          "sehr gute Kenntnisse in Python und SQL sowie fliessende Deutschkenntnisse. Wir bieten Ihnen eine spannende Aufgabe "
          "in einem dynamischen Umfeld mit vielen Möglichkeiten und einem motivierten Team.")
    res = analyse_keywords(CV, jd, PROFILE, INF, "Switzerland")
    assert res["score"] is None and res["posting_language"] == "de" and res["requirements"] == []
    assert res["recommendation"]["action"] in ("Not scored", "Deprioritise")


def test_posting_fields():
    from jobtracker import posting as P
    ex = P.extract((FIX / "jd_jobsch.txt").read_text())
    assert ex["company"] == "Capgemini Suisse SA" and ex["position"].startswith("Data Engineer")
    assert ex["workload"] == "100%" and ex["contract"] == "Internship"
    li = P.extract("Digital & Data Analyst (m/w/d)\nNorgine · Zurich, Switzerland (Hybrid)\n2 days ago\nAbout the job\nWe are looking for an analyst.")
    assert (li["position"], li["company"], li["location"]) == ("Digital & Data Analyst", "Norgine", "Zurich, Switzerland")
    de = P.extract("Praktikant/in Datenanalyse 80-100% (w/m/d)\nRoche AG\nBasel\nBewerbungsfrist: 15.11.2026")
    assert de["workload"] == "80–100%" and de["deadline"] == "2026-11-15" and "80" not in de["position"]
    cleaned, removed = P.clean((FIX / "jd_jobsch.txt").read_text())
    assert "AI Generated Summary" not in cleaned and "See company profile" not in cleaned and removed["summary"] > 5


# ---------------------------------------------------------------- entries
def test_entries_from_cv_and_paste():
    from jobtracker.entries import from_cv, split_text, to_text
    es = from_cv(MESSY.replace("EDUCATION\n", "EDUCATION\nAddress: Phone: Email: 12 Example Strasse +41 79 123 45 67 jamie@example.com\n", 1), INF)
    assert not any("@" in (e["details"] or "") or "@" in (e["title"] or "") for e in es)
    assert {e["section"] for e in es} >= {"education", "experience", "skills"}
    ra = next(e for e in es if e["title"] == "Research Assistant")
    assert ra["start"] == "Mar 2025" and "Investigated" in ra["details"]
    glued = "Feb 2025 - Apr 2025 May 2023 - Aug 2023Research Internship, Mood and Anxiety Department, Institute of Mental Health\n- Co-authored a publication"
    d = split_text("experience", glued)
    assert [(x["start"], x["title"]) for x in d] == [("Feb 2025", "Research Internship"), ("May 2023", "Research Internship")]
    assert "EXPERIENCE" in to_text(es) and "- Investigated" in to_text(es)


# ---------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Service(tmp_path / "fit.db")))


def setup_profile(c, url="http://127.0.0.1:9"):
    c.put("/api/settings", json={"cv_text": CV, "profile": PROFILE, "ollama_url": url, "ollama_model": "qwen2.5:7b"})


def test_fit_api(client):
    setup_profile(client)
    app_id = client.post("/api/applications", json={"company": "Acme Bio", "position": "Data Scientist",
                                                    "location": "Basel", "job_description": JD}).json()["id"]
    got = client.get(f"/api/fit/application/{app_id}").json()  # scored instantly on save
    assert got["result"]["method"] == "keywords" and got["stale"] is False
    client.patch(f"/api/applications/{app_id}", json={"job_description": JD + "\n- Knowledge of SQL is required"})
    after = client.get(f"/api/fit/application/{app_id}").json()
    assert after["stale"] is False and any("SQL" in r["text"] for r in after["result"]["requirements"])
    assert client.post(f"/api/docs/application/{app_id}/cv_builder", json={}).status_code in (404, 405)


def test_fit_requires_profile(client):
    app_id = client.post("/api/applications", json={"company": "A", "position": "B", "job_description": JD}).json()["id"]
    r = client.post(f"/api/fit/application/{app_id}", json={})
    assert r.status_code == 422 and "Me" in r.json()["detail"]


def test_entries_api_drive_matching(client):
    client.put("/api/settings", json={"profile": PROFILE})
    d = client.post("/api/entries/split", json={"section": "experience", "text":
        "Imaging Analyst, Brain Lab, Basel  Jan 2024 - Present\n- Analysed MRI data from clinical trials in Python\n- Built statistical models in R"}).json()["drafts"]
    assert d[0]["title"] == "Imaging Analyst" and "MRI" in d[0]["details"]
    client.post("/api/entries/bulk", json={"entries": d})
    client.post("/api/entries", json={"section": "education", "title": "MSc Neuroscience", "org": "ETH Zurich"})
    es = client.get("/api/entries").json()["entries"]
    assert len(es) == 2
    assert "Imaging Analyst" in client.get("/api/profile/text").json()["text"]
    app_id = client.post("/api/applications", json={"company": "Acme", "position": "DS", "job_description": JD}).json()["id"]
    fit = client.get(f"/api/fit/application/{app_id}").json()["result"]
    stats = next(r for r in fit["requirements"] if "statistical modelling" in r["text"])
    assert stats["status"] != "missing" and "statistical models in R" in stats["evidence"]
    ev = client.get("/api/evidence").json()["items"]
    assert ev and all(e["source"] == "entry" for e in ev)
    client.patch(f"/api/entries/{es[0]['id']}", json={"details": "Analysed MRI data\nTaught statistics"})
    assert any("Taught statistics" in e["text"] for e in client.get("/api/evidence").json()["items"])


def test_cv_upload_creates_entries(client, tmp_path):
    import docx
    d = docx.Document()
    for line in MESSY.splitlines():
        d.add_paragraph(line)
    path = tmp_path / "cv.docx"
    d.save(path)
    r = client.post("/api/profile/cv", files={"file": ("cv.docx", path.read_bytes())}).json()
    assert r["chars"] > 200 and r["entries_created"] >= 4
    assert client.post("/api/profile/cv", files={"file": ("cv.exe", b"x")}).status_code == 422


def test_chat_ranking_roundtrip(client):
    setup_profile(client)
    ids = [client.post("/api/opportunities", json={"company": f"C{i}", "position": "Data Scientist", "job_description": JD}).json()["id"]
           for i in range(3)]
    p = client.post("/api/rank/prompt", json={}).json()
    assert p["count"] == 3 and f"S{ids[0]}" in p["prompt"] and "JSON" in p["prompt"] and "Strasse" not in p["prompt"]
    reply = ("Here you go:\n```json\n[" + f'{{"code": "S{ids[1]}", "score": 8, "verdict": "Apply", "reason": "Strong imaging match", "missing": "none"}},'
             f'{{"code": "S{ids[0]}", "score": 4, "verdict": "skip", "reason": "Too senior"}}' + "]\n```")
    r = client.post("/api/rank/import", json={"text": reply}).json()
    assert len(r["saved"]) == 2 and r["saved"][1]["verdict"] == "Skip"
    opps = {o["id"]: o for o in client.get("/api/opportunities").json()}
    assert opps[ids[1]]["rank"]["score"] == 8 and opps[ids[2]]["rank"] is None
    lines = client.post("/api/rank/import", json={"text": f"S{ids[2]} – 6/10 – Apply with caveats – needs German"}).json()
    assert lines["saved"][0]["score"] == 6 and lines["saved"][0]["verdict"] == "Apply with caveats"
    assert client.post("/api/rank/import", json={"text": "nothing useful"}).status_code == 422
    pr = client.get(f"/api/prompts/opportunity/{ids[0]}/weakness").json()
    assert "biggest weakness" in pr["prompt"].lower() and "Data Scientist" in pr["prompt"]


# ---------------------------------------------------------------- background reading (fake Ollama)
class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": [{"name": "qwen2.5:7b"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        props = req["format"]["properties"]
        if "fruits" in props:
            content = {"fruits": [{"name": "apple", "fact": "crisp"}]}
        else:
            content = {"skills": ["MRI analysis", "Python", "R"], "industry": "Pharma & biotech", "seniority": "Mid",
                       "requirements": ["MSc in neuroscience"], "language": ["English"]}
        text = json.dumps(content)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for i in range(0, len(text), 8):
            self.wfile.write((json.dumps({"message": {"content": text[i:i + 8]}, "done": False}) + "\n").encode())
        self.wfile.write((json.dumps({"done": True, "eval_count": 20, "eval_duration": 1_000_000_000,
                                      "prompt_eval_count": 500, "prompt_eval_duration": 1_000_000_000}) + "\n").encode())
        self.close_connection = True


@pytest.fixture
def fake_ollama():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_background_reading_of_descriptions(client, fake_ollama):
    setup_profile(client, fake_ollama)
    for i in range(3):
        client.post("/api/applications", json={"company": f"C{i}", "position": "Data Scientist", "job_description": JD})
    st = client.get("/api/digest").json()
    assert st["total"] == 3 and st["done"] == 0
    assert client.post("/api/digest/run").json()["queued_now"] == 3
    end = time.time() + 15
    while time.time() < end and client.get("/api/digest").json()["done"] < 3:
        time.sleep(0.1)
    st = client.get("/api/digest").json()
    assert st["done"] == 3 and st["seconds_each"]
    rep = client.get("/api/career/skills").json()
    assert rep["digests"] == 3 and any(s["skill"].lower() == "mri analysis" for s in rep["skills"])
    assert client.post("/api/digest/run").json()["queued_now"] == 0  # cached by content


def test_digest_needs_ollama(client):
    assert client.post("/api/digest/run").status_code == 503


def test_truncated_json_is_repaired():
    from jobtracker.llm import parse_loose
    cut = '{"skills": ["SQL", "R"], "industry": "Pharma", "requirements": ["MSc", "Pyth'
    assert parse_loose(cut)["skills"] == ["SQL", "R"]


def test_job_queue_priority_and_cancel():
    from jobtracker.aijobs import AIJobs
    jobs = AIJobs()

    def slow(progress):
        for _ in range(200):
            time.sleep(0.01)
            progress.token()
    a = jobs.submit("a", "slow", slow)
    b = jobs.submit("b", "waiting", lambda p: 1, priority=5)
    c = jobs.submit("c", "urgent", lambda p: 2, priority=0)
    assert jobs.submit("a", "dupe", slow)["id"] == a["id"]
    assert jobs.get(c["id"])["ahead"] == 1 and jobs.get(b["id"])["ahead"] == 2
    time.sleep(0.1)
    jobs.cancel(a["id"])
    end = time.time() + 5
    while time.time() < end and jobs.get(b["id"])["status"] != "done":
        time.sleep(0.02)
    assert jobs.get(a["id"])["status"] == "cancelled" and jobs.get(c["id"])["status"] == "done"
