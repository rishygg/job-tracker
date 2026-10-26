"""Fit analysis: requirement extraction, evidence matching, blockers, the Ollama path (with a fake
Ollama server) and the API endpoints."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobtracker.api import create_app
from jobtracker.dimensions import DimensionInferer
from jobtracker.fit import analyse_keywords, analyse_llm, extract_requirements, recommend, target_cv_llm
from jobtracker.llm import Ollama
from jobtracker.service import Service

CV = (Path(__file__).parent / "fixtures" / "cv.txt").read_text()
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
class FakeOllama(BaseHTTPRequestHandler):
    reply: dict = {}

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

    def _stream(self, content: str):
        """Answer like Ollama with stream=true: one JSON line per small piece, then a final stats line."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        pieces = [content[i:i + 6] for i in range(0, len(content), 6)]
        for p in pieces:
            self.wfile.write((json.dumps({"message": {"content": p}, "done": False}) + "\n").encode())
        self.wfile.write((json.dumps({"done": True, "eval_count": len(pieces), "eval_duration": len(pieces) * 50_000_000,
                                      "prompt_eval_count": 900, "prompt_eval_duration": 3_000_000_000}) + "\n").encode())
        self.close_connection = True

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        props = req["format"]["properties"]
        msgs = req["messages"]
        req["messages"] = [msgs[0], {"role": "user", "content": msgs[0]["content"] + "\n" + msgs[1]["content"]}]
        if "r" in props:
            text = req["messages"][1]["content"]
            import re as _re
            rids = _re.findall(r"^(R\d+) \[", text, _re.M)
            cv_line = next(l.split(":")[0] for l in text.splitlines() if "quality-control pipelines" in l)
            ans = []
            for i, rid in enumerate(rids):
                if i == 0:
                    ans.append({"id": rid, "status": "met", "type": "essential", "cv": [cv_line]})
                elif i == 1:
                    ans.append({"id": rid, "status": "met", "type": "essential", "cv": ["C999"]})  # invalid id
                else:
                    ans.append({"id": rid, "status": "missing", "cv": []})
            content = {"summary": "Good technical fit.", "r": ans}
        elif "critique" in props:
            text = req["messages"][1]["content"]
            e = next(l.split(" ")[0] for l in text.splitlines() if "statistical analyses" in l)
            content = {"reword": [],
                       "critique": [{"e": e, "issue": "No outcome", "fix": "Say what the models showed", "priority": "high"},
                                    {"e": "E77", "issue": "x", "fix": "y"}]}
        elif "questions" in props:
            content = {"emphasise": [{"e": "E1", "why": "Imaging at scale"}, {"e": "E99", "why": "bogus"}],
                       "questions": [{"question": "Why this role?"}], "add_if_true": [{"what": "PyTorch"}]}
        elif "connection" in props:
            content = {"connection": {"e": "E1", "requirement": "Python", "why": "Direct match"},
                       "interest": {"reason": "Imaging biomarkers match your cohort MRI work", "basis": "About us"},
                       "highlight": {"e": "E42", "why": "bogus id"}}
        elif "outline" in props:
            content = {"missing": ["Clinical trial exposure"],
                       "avoid": [{"phrase": "I am passionate", "instead": "Show it"}], "outline": ["Open", "Why", "Proof", "Close"]}
        elif "fruits" in props:
            content = {"fruits": [{"name": "apple", "fact": "crisp"}]}
        elif "items" in props:
            text = req["messages"][1]["content"]
            ids = [l.split(" ")[0] for l in text.splitlines() if l.startswith("E")]
            content = {"items": [{"id": i, "kind": "achievement", "did": "Did a thing", "outcome": ""} for i in ids]}
        elif "emphasise" in props:
            text = req["messages"][1]["content"]
            c = next(l.split(":")[0] for l in text.splitlines() if "MRI data" in l)
            content = {"emphasise": [{"cv": c, "why": "Matches imaging"}, {"cv": "C999", "why": "bogus"}],
                       "reword": [], "cut": [], "add": [{"what": "PyTorch project, if true", "why": "Preferred"}],
                       "keywords": ["Python", "PyTorch"]}
        elif "requirements" in props:
            content = {"summary": "Good technical fit.", "requirements": [
                {"text": "Python programming", "type": "essential", "status": "met",
                 "evidence": "Built automated quality-control pipelines in Python and Bash"},
                {"text": "Kubernetes in production", "type": "essential", "status": "met",
                 "evidence": "Deployed Kubernetes clusters at scale"},  # not in the CV: must be caught
                {"text": "Deep learning", "type": "preferred", "status": "missing", "evidence": ""}]}
        elif "sections" in props:
            content = {"headline": "Neuroimaging data scientist", "summary": "…", "advice": ["Lead with MRI work"],
                       "skills": [{"skill": "Python", "support": "backed"}, {"skill": "Kubernetes", "support": "backed"}],
                       "sections": [{"title": "Experience", "bullets": [
                           {"text": "Processed MRI data for a 1,200-person cohort", "support": "backed",
                            "source": "Processed structural and functional MRI data for a longitudinal cohort of 1,200 participants using Python and FSL."},
                           {"text": "Led a team of 10 engineers", "support": "backed", "source": "Managed ten engineers"},
                           {"text": "Experience deploying deep learning models", "support": "gap", "source": "something"}]}]}
        else:
            content = {"greeting": "Dear team,", "closing": "Best", "paragraphs": [
                {"text": "I built QC pipelines in Python.", "support": "backed",
                 "sources": ["Built automated quality-control pipelines in Python and Bash"]},
                {"text": "I led large teams.", "support": "backed", "sources": ["Led global teams of 50"]}]}
        if req.get("stream"):
            self._stream(json.dumps(content))
        else:
            self._send({"message": {"content": json.dumps(content)}})


@pytest.fixture
def fake_ollama():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_llm_compact_analysis(fake_ollama):
    client = Ollama(fake_ollama, "qwen2.5:7b")
    res = analyse_llm(CV, JD, PROFILE, INF, client, "Switzerland")
    asked = [r for r in res["requirements"] if not str(r.get("evidence") or "").startswith("Profile:")]
    assert asked[0]["status"] == "met" and "quality-control" in asked[0]["evidence"] and asked[0]["evidence_verified"]
    assert asked[1]["status"] == "partial" and not asked[1]["evidence_verified"]  # pointed at a line that doesn't exist
    assert res["method"] == "ollama" and res["summary"] == "Good technical fit."


def test_cv_tips(fake_ollama):
    from jobtracker.fit import cv_tips_keywords, cv_tips_llm
    fit = analyse_keywords(CV, JD, PROFILE, INF, "Switzerland")
    k = cv_tips_keywords(CV, JD, fit, INF)
    assert k["emphasise"] and any("PyTorch" in a["what"] for a in k["add"])
    t = cv_tips_llm(CV, JD, fit, INF, Ollama(fake_ollama, "qwen2.5:7b"))
    assert len(t["emphasise"]) == 1 and "MRI" in t["emphasise"][0]["text"]  # bogus id dropped
    assert t["missing_keywords"] == ["PyTorch"] and t["keywords"] == ["Python"]


def test_target_cv_guard(fake_ollama):
    client = Ollama(fake_ollama, "qwen2.5:7b")
    t = target_cv_llm(CV, JD, None, INF, client, "Data Scientist", "Acme")
    bullets = t["sections"][0]["bullets"]
    assert bullets[0]["support"] == "backed" and bullets[0]["source_verified"]
    assert bullets[1]["support"] == "partial"  # "Managed ten engineers" isn't in the CV
    assert bullets[2]["source"] == ""
    assert {s["skill"]: s["support"] for s in t["skills"]}["Kubernetes"] == "gap"


# ---------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Service(tmp_path / "fit.db")))


def setup_profile(c, url=None):
    body = {"cv_text": CV, "profile": PROFILE, "ai_engine": "auto"}
    if url:
        body.update(ollama_url=url, ollama_model="qwen2.5:7b")
    else:
        body.update(ollama_url="http://127.0.0.1:9")  # nothing listening -> keyword fallback
    c.put("/api/settings", json=body)


def test_fit_api_keyword_fallback(client):
    setup_profile(client)
    assert client.get("/api/ai/status").json()["available"] is False
    app_id = client.post("/api/applications", json={"company": "Acme Bio", "position": "Data Scientist",
                                                    "location": "Basel", "job_description": JD}).json()["id"]
    # Saving a job with a description scores it instantly with keywords.
    assert client.get(f"/api/fit/application/{app_id}").json()["result"]["method"] == "keywords"
    r = client.post(f"/api/fit/application/{app_id}", json={}).json()
    assert r["result"]["method"] == "keywords" and r["result"]["fallback_reason"]
    cached = client.get(f"/api/fit/application/{app_id}").json()
    assert cached["stale"] is False
    client.patch(f"/api/applications/{app_id}", json={"job_description": JD + "\n- Knowledge of SQL is required"})
    after = client.get(f"/api/fit/application/{app_id}").json()  # re-scored automatically
    assert after["stale"] is False and any("SQL" in r["text"] for r in after["result"]["requirements"])
    guide = client.post(f"/api/docs/application/{app_id}/target_cv", json={}).json()["result"]
    assert guide["method"] == "keywords" and guide["sections"]
    letter = client.post(f"/api/docs/application/{app_id}/cover_letter", json={}).json()["result"]
    assert letter["method"] == "template"
    assert client.post(f"/api/fit/application/{app_id}", json={"engine": "ollama"}).status_code == 503


def test_fit_requires_cv(client):
    app_id = client.post("/api/applications", json={"company": "A", "position": "B", "job_description": JD}).json()["id"]
    r = client.post(f"/api/fit/application/{app_id}", json={})
    assert r.status_code == 422 and "CV" in r.json()["detail"]


def test_fit_api_with_ollama(client, fake_ollama):
    setup_profile(client, fake_ollama)
    st = client.get("/api/ai/status").json()
    assert st["available"] and st["model"] == "qwen2.5:7b"
    res = client.post("/api/fit/check", json={"company": "Acme", "position": "DS", "location": "Basel", "job_description": JD}).json()
    assert res["method"] == "ollama"


def test_opportunities_flow(client):
    setup_profile(client)
    oid = client.post("/api/opportunities", json={"company": "Acme Bio", "position": "Data Scientist", "location": "Zurich",
                                                  "job_description": JD, "deadline": "2099-01-01"}).json()["id"]
    client.post("/api/opportunities", json={"company": "Other", "position": "Analyst", "job_description": "short"})
    b = client.post("/api/fit/batch", json={"kind": "opportunity"}).json()
    assert b["analysed"] == 0 and b["skipped"] == 2  # already scored on save; one has no description
    d = client.get("/api/discover").json()
    assert d["opportunities"][0]["id"] == oid and d["opportunities"][0]["fit"]["score"] is not None
    app_id = client.post(f"/api/opportunities/{oid}/apply").json()["application_id"]
    assert client.get(f"/api/fit/application/{app_id}").json()["result"] is not None
    assert all(o["id"] != oid for o in client.get("/api/opportunities").json())
    assert client.get(f"/api/applications/{app_id}").json()["job_description"] == JD


def test_cv_upload_docx(client, tmp_path):
    import docx
    d = docx.Document()
    for line in CV.splitlines():
        d.add_paragraph(line)
    path = tmp_path / "cv.docx"
    d.save(path)
    r = client.post("/api/profile/cv", files={"file": ("cv.docx", path.read_bytes())}).json()
    assert r["chars"] > 200 and "Neuroimaging" in r["text"]
    assert client.post("/api/profile/cv", files={"file": ("cv.exe", b"x")}).status_code == 422


def test_ai_queue(client, fake_ollama):
    import time
    setup_profile(client, fake_ollama)
    ids = [client.post("/api/opportunities", json={"company": f"C{i}", "position": "Data Scientist", "job_description": JD}).json()["id"]
           for i in range(3)]
    q = client.post("/api/ai/queue", json={"items": [{"kind": "opportunity", "ref_id": i} for i in ids]}).json()
    assert q["total"] == 3
    for _ in range(50):
        q = client.get("/api/ai/queue").json()
        if q["done"] == 3:
            break
        time.sleep(0.1)
    assert q["done"] == 3 and not q["errors"]
    assert all(o["fit"]["method"] == "ollama" for o in client.get("/api/opportunities").json())
    tips = client.post(f"/api/docs/opportunity/{ids[0]}/cv_tips", json={}).json()["result"]
    assert tips["method"] == "ollama" and tips["emphasise"]


def test_ai_queue_needs_ollama(client):
    setup_profile(client)
    assert client.post("/api/ai/queue", json={"items": [{"kind": "opportunity", "ref_id": 1}]}).status_code == 503


def test_evidence_and_builders_rules(client):
    setup_profile(client)
    ev = client.get("/api/evidence").json()
    assert ev["has_cv"] and ev["counts"]["achievement"] >= 2 and ev["counts"]["qualification"] == 2
    mri = next(e for e in ev["items"] if "MRI data" in e["text"])
    assert "1,200 participants" in mri["metrics"] and mri["context"].startswith("Research Assistant")
    # Edits survive a rebuild; manual evidence is kept.
    client.patch(f"/api/evidence/{mri['id']}", json={"confirmed": True, "note": "I wrote the pipeline"})
    client.post("/api/evidence", json={"text": "Taught a Python workshop for 30 students"})
    ev2 = client.post("/api/evidence/rebuild").json()["items"]
    again = next(e for e in ev2 if "MRI data" in e["text"])
    assert again["confirmed"] and again["note"] == "I wrote the pipeline"
    assert any(e["source"] == "manual" for e in ev2)
    app_id = client.post("/api/applications", json={"company": "Acme Bio", "position": "Data Scientist",
                                                    "location": "Basel", "job_description": JD}).json()["id"]
    cvb = client.post(f"/api/docs/application/{app_id}/cv_builder", json={}).json()["result"]
    assert cvb["method"] == "rules" and cvb["emphasise"] and cvb["priorities"]
    assert all({"text", "issue", "fix"} <= set(c) for c in cvb["critique"])
    assert "Lead with these lines" in cvb["brief"]
    lb = client.post(f"/api/docs/application/{app_id}/letter_builder", json={}).json()["result"]
    assert lb["connection"]["text"] and lb["highlight"] and lb["avoid"] and lb["outline"]
    assert client.get(f"/api/docs/application/{app_id}/cv_builder").json()["stale"] is False
    client.patch(f"/api/evidence/{again['id']}", json={"note": "changed"})
    assert client.get(f"/api/docs/application/{app_id}/cv_builder").json()["stale"] is True


def test_builders_ai(client, fake_ollama):
    setup_profile(client, fake_ollama)
    app_id = client.post("/api/applications", json={"company": "Acme Bio", "position": "Data Scientist",
                                                    "job_description": JD}).json()["id"]
    first = client.post(f"/api/docs/application/{app_id}/cv_builder", json={"engine": "ollama"}).json()
    assert first["job"]["status"] in ("queued", "running", "done") and first["result"]  # rules shown meanwhile
    wait_job(client, first["job"]["id"])
    cvb = client.get(f"/api/docs/application/{app_id}/cv_builder").json()["result"]
    assert cvb["method"] == "ollama" and not cvb["in_progress"]
    assert cvb["sources"]["critique"] == "ai" and cvb["sources"]["emphasise"] == "ai"  # both parts used
    assert len(cvb["critique"]) == 1 and "statistical" in cvb["critique"][0]["text"]  # bogus id dropped
    assert len(cvb["emphasise"]) == 1
    job = client.post(f"/api/docs/application/{app_id}/letter_builder", json={"engine": "ollama"}).json()["job"]
    wait_job(client, job["id"])
    lb = client.get(f"/api/docs/application/{app_id}/letter_builder").json()["result"]
    assert lb["interest"]["reason"].startswith("Imaging") and lb["connection"]["why"] == "Direct match"
    assert lb["highlight"]["why"] != "bogus id"  # invalid id -> rule-based highlight kept
    job = wait_job(client, client.post("/api/evidence/enrich").json()["job"]["id"])
    assert job["status"] == "done"
    assert client.get("/api/evidence").json()["enriched"] >= 5
    speed = client.get("/api/ai/status").json()["speed"]
    assert speed and speed["gen_tps"] > 0  # measured from the streamed answer


def wait_job(client, jid, timeout=15):
    import time as _t
    end = _t.time() + timeout
    while _t.time() < end:
        j = client.get(f"/api/ai/jobs/{jid}").json()
        if j["status"] not in ("queued", "running"):
            assert j["status"] == "done", j
            return j
        _t.sleep(0.05)
    raise AssertionError("AI job didn't finish")


# ---------------------------------------------------------------- messy CVs and AI transparency
MESSY = (Path(__file__).parent / "fixtures" / "cv_messy.txt").read_text()


def messy_evidence():
    from jobtracker.evidence import extract
    cv = MESSY.replace("EDUCATION\n", "EDUCATION\nAddress: Phone: Email: 12 Example Strasse +41 79 123 45 67 jamie@example.com\n", 1)
    return [{**r, "id": i + 1, "hidden": r.get("hidden", False)} for i, r in enumerate(extract(cv, INF))]


def test_messy_cv_extraction():
    ev = messy_evidence()
    personal = [e for e in ev if e["kind"] == "personal"]
    assert personal and all(e["hidden"] for e in personal)
    assert any(e["kind"] == "coursework" for e in ev)
    thesis = next(e for e in ev if e["text"].startswith("Investigated"))
    assert "University of Zurich" not in thesis["text"]  # glued heading removed
    tested = next(e for e in ev if e["text"].startswith("Tested scripts"))
    assert "Intern" not in tested["text"]  # date range + next heading removed
    assert any(e.get("duplicate_of") for e in ev if e["text"].startswith("Develop incentive"))


def test_builders_ignore_personal_and_coursework():
    from jobtracker.builder import cv_builder_rules, job_profile
    jd = (Path(__file__).parent / "fixtures" / "jd_digital.txt").read_text()
    job = job_profile(jd, INF)
    assert not any(":" == p.strip()[-1] for p in job["priorities"])
    assert not any("Fixed Term" in p for p in job["essential"] + job["priorities"])
    assert "exampla" not in " ".join(job["themes"]).lower()
    res = cv_builder_rules(messy_evidence(), job, None, MESSY)
    texts = [x["text"] for k in ("critique", "emphasise", "cut", "reword") for x in res[k]]
    assert not any("@" in t or "Permit" in t or "modules" in t for t in texts)
    dup = [t for t in texts if t.startswith("Develop incentive")]
    assert not dup  # near-duplicate never shown alongside the original


class StubClient:
    model = "stub"

    def __init__(self, reply):
        self.reply = reply

    def chat_json(self, system, user, schema, **kw):
        return self.reply


def test_ai_ids_are_resolved_flexibly_and_fallback_is_labelled():
    from jobtracker.builder import cv_builder_ai, job_profile
    jd = (Path(__file__).parent / "fixtures" / "jd_digital.txt").read_text()
    job, ev = job_profile(jd, INF), messy_evidence()
    good = {"critique": [{"e": "e1: something", "issue": "Hides your part (see E1)", "fix": "Name the tool", "priority": "high"}],
            "emphasise": [{"e": 2, "why": "fits"}], "reword": [], "questions": [], "add_if_true": []}
    r = cv_builder_ai(ev, job, None, MESSY, StubClient(good))
    assert r["method"] == "ollama" and r["sources"]["critique"] == "ai" and r["sources"]["reword"] == "rules"
    assert "E1" not in r["critique"][0]["issue"]  # stray id replaced by a quote
    bad = {"critique": [{"e": "E99", "issue": "x", "fix": "y", "priority": "low"}], "emphasise": [], "reword": [],
           "questions": [], "add_if_true": []}
    r2 = cv_builder_ai(ev, job, None, MESSY, StubClient(bad))
    assert r2["method"] == "rules" and "couldn't be matched" in r2["ai_note"]


def test_truncated_json_is_repaired():
    from jobtracker.llm import parse_loose
    cut = '{"critique": [{"e": "E1", "issue": "Vague", "fix": "Name it", "priority": "high"}, {"e": "E2", "iss'
    assert parse_loose(cut) == {"critique": [{"e": "E1", "issue": "Vague", "fix": "Name it", "priority": "high"}]}


def test_partial_results_and_cancel():
    import time as _t
    from jobtracker.aijobs import AIJobs
    from jobtracker.builder import cv_builder_ai, job_profile
    jd = (Path(__file__).parent / "fixtures" / "jd_digital.txt").read_text()
    reply = {"critique": [{"e": "E1", "issue": "Hides your part", "fix": "Name the tool", "priority": "high"}],
             "reword": [], "emphasise": [{"e": "E2", "why": "fits"}], "questions": [], "add_if_true": []}
    seen = []
    r = cv_builder_ai(messy_evidence(), job_profile(jd, INF), None, MESSY, StubClient(reply), on_partial=seen.append)
    assert seen and seen[0]["in_progress"] and seen[0]["sources"]["emphasise"] == "pending"
    assert seen[0]["sources"]["critique"] == "ai" and not r["in_progress"]

    jobs = AIJobs()

    def slow(progress):
        for _ in range(200):
            _t.sleep(0.01)
            progress.token()
    a = jobs.submit("a", "slow", slow)
    b = jobs.submit("b", "waiting", lambda p: 1, priority=5)
    c = jobs.submit("c", "urgent", lambda p: 2, priority=0)
    assert jobs.submit("a", "dupe", slow)["id"] == a["id"]  # same task isn't queued twice
    assert jobs.get(c["id"])["ahead"] == 1 and jobs.get(b["id"])["ahead"] == 2  # interactive jumps the batch
    _t.sleep(0.1)
    jobs.cancel(a["id"])
    end = _t.time() + 5
    while _t.time() < end and jobs.get(b["id"])["status"] != "done":
        _t.sleep(0.02)
    assert jobs.get(a["id"])["status"] == "cancelled" and jobs.get(c["id"])["status"] == "done"
    assert jobs.get(b["id"])["status"] == "done" and jobs.get(c["id"])["finished"] <= jobs.get(b["id"])["finished"]
