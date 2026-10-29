"""v10: map lookups, chat rankings on applications, results by industry from description reading."""

import pandas as pd
from fastapi.testclient import TestClient

from jobtracker import digest as DG
from jobtracker import fun
from jobtracker.api import create_app
from jobtracker.service import Service

from test_fit import JD, setup_profile  # noqa: F401  (reuse the fixtures' posting and profile)


def test_locate_countries_and_towns():
    places = fun.load_places()
    usa = fun.locate("USA", places)
    assert usa["level"] == "country" and usa["iso_num"] == "840"
    assert fun.locate("Czech Republic", places)["name"] == "Czechia"
    assert fun.locate("Boston, USA", places)["name"] == "Boston"
    assert fun.locate("Kassel, Germany", places)["name"] == "Kassel"
    assert fun.locate("Various", places) is None


def test_map_points_count_various_and_countries():
    df = pd.DataFrame([
        {"id": 1, "location": "United Kingdom", "reached_interview": True, "furthest_stage": "Interview", "active": False,
         "company": "A", "position": "P", "status": "Rejected"},
        {"id": 2, "location": "Various", "reached_interview": False, "furthest_stage": "Applied", "active": True,
         "company": "B", "position": "P", "status": "Applied"},
        {"id": 3, "location": "Remote", "reached_interview": False, "furthest_stage": "Applied", "active": True,
         "company": "C", "position": "P", "status": "Applied"},
    ])
    m = fun.map_points(df)
    assert m["various"] == 1 and m["remote"] == 1 and not m["unmatched"]
    uk = m["points"][0]
    assert uk["level"] == "country" and uk["iso_num"] == "826" and uk["lat"] is None


def test_application_rank_and_industry_results(tmp_path):
    svc = Service(tmp_path / "v10.db")
    c = TestClient(create_app(svc))
    setup_profile(c)
    a1 = c.post("/api/applications", json={"company": "Acme Bio", "position": "Data Scientist", "job_description": JD}).json()["id"]
    a2 = c.post("/api/applications", json={"company": "Beta", "position": "Analyst", "job_description": JD + "\nMore."}).json()["id"]
    c.post(f"/api/applications/{a1}/stages", json={"stage": "Interview", "date": "2026-10-01"})
    c.post("/api/rank/import", json={"text": f'[{{"code": "A{a1}", "score": 9, "verdict": "Apply", "reason": "Fits"}}]'})
    items = {i["id"]: i for i in c.get("/api/applications").json()["items"]}
    assert items[a1]["rank"]["score"] == 9 and items[a2]["rank"] is None
    # Pretend Ollama read both descriptions.
    for aid, jd, industry in ((a1, JD, "Pharma & biotech"), (a2, JD + "\nMore.", "Consulting")):
        svc.store.save_result("application", aid, "digest", {"skills": ["Neuroimaging"], "industry": industry, "seniority": "Mid",
                                                             "requirements": [], "language": []}, "ollama", "test", DG.jd_hash(jd))
    rep = c.get("/api/career/skills").json()
    assert rep["digests"] == 2
    by = {r["label"]: r for r in rep["by_industry"]}
    assert by["Pharma & biotech"]["interviews"] == 1 and by["Consulting"]["interviews"] == 0
    assert any(s["skill"].lower() == "neuroimaging" for s in rep["skills"])


def test_ranking_fields_are_configurable(tmp_path):
    from jobtracker import prompts as PR
    cfg = PR.ranking_config()
    keys = [f["key"] for f in cfg["fields"]]
    assert {"ats", "salary", "interview_chance"} <= set(keys)
    prompt = PR.rank_prompt("PROFILE", {}, [{"code": "S1", "position": "X", "company": "Y", "jd": "Do things."}], "", cfg["fields"])
    assert '"ats": 50' in prompt and "Low | Medium | High" in prompt and "salary:" in prompt
    reply = '[{"code": "S1", "score": 7, "verdict": "apply", "reason": "ok", "ATS": "140%", "interview_chance": "high", "salary": "CHF 50-60k"}]'
    item = PR.parse_ranking(reply, cfg["fields"])[0]
    assert item["extra"] == {"ats": 100, "interview_chance": "High", "salary": "CHF 50-60k"}
    for bad in ("fields: [{key: score}]", "fields: [{key: x, type: choice}]", "fields: [{key: 'a b'}]", "fields: [{key: x, type: date}]"):
        try:
            PR.ranking_config(bad)
            raise AssertionError(bad)
        except ValueError:
            pass


def test_rank_config_api_and_saved_criteria(tmp_path):
    c = TestClient(create_app(Service(tmp_path / "r.db")))
    setup_profile(c)
    cfg = c.get("/api/rank/config").json()
    assert cfg["fields"] and cfg["default_criteria"] and cfg["goals"] == ""
    oid = c.post("/api/opportunities", json={"company": "A", "position": "Data Scientist", "job_description": JD}).json()["id"]
    p = c.post("/api/rank/prompt", json={"goals": "Prefer Switzerland; salary above 40k"}).json()["prompt"]
    assert "Prefer Switzerland" in p and "interview_chance" in p
    assert c.get("/api/rank/config").json()["goals"] == "Prefer Switzerland; salary above 40k"
    c.post("/api/rank/import", json={"text": f'[{{"code": "S{oid}", "score": 8, "verdict": "Apply", "reason": "r", "ats": 72, "salary": "CHF 45-55k"}}]'})
    opp = next(o for o in c.get("/api/opportunities").json() if o["id"] == oid)
    assert opp["rank"]["extra"] == {"ats": 72, "salary": "CHF 45-55k"}
    assert c.put("/api/rules/ranking", json={"text": "fields: [{key: score}]"}).status_code == 422
    assert "ATS match" in c.get("/api/rules/ranking").json()["text"]


def test_truncated_reply_keeps_complete_rankings_and_reports_missing(tmp_path):
    import json as _json
    c = TestClient(create_app(Service(tmp_path / "t.db")))
    setup_profile(c)
    ids = [c.post("/api/opportunities", json={"company": f"C{i}", "position": "Data Scientist", "job_description": JD}).json()["id"] for i in range(5)]
    c.post("/api/rank/prompt", json={})
    full = _json.dumps([{"code": f"S{i}", "score": 6, "verdict": "Apply", "reason": "ok [fine]", "ats": 60} for i in ids], indent=2)
    r = c.post("/api/rank/import", json={"text": "Sure [note]!\n```json\n" + full[: int(len(full) * 0.55)]}).json()
    assert 1 <= len(r["saved"]) < 5 and all(x["score"] == 6 for x in r["saved"])
    assert set(r["not_in_reply"]) == {f"S{i}" for i in ids} - {x["code"] for x in r["saved"]}
    assert r["unscored"] == []


def _jd(i):
    return JD + f"\nPosting number {i}. " + ("Extra detail. " * 20)


def test_inbox_ranks_only_new_jobs_and_splits_into_parts(tmp_path):
    from jobtracker import prompts as PR
    c = TestClient(create_app(Service(tmp_path / "i.db")))
    setup_profile(c)
    ids = [c.post("/api/opportunities", json={"company": f"C{i}", "position": "Data Scientist", "job_description": _jd(i)}).json()["id"]
           for i in range(7)]
    r = c.post("/api/rank/prompt", json={}).json()
    assert r["count"] == 7 and len(r["parts"]) == 1 and "part" not in r["prompt"].split("=== JOBS")[1].split("\n")[0]
    c.post("/api/rank/import", json={"text": "\n".join(f'{{"code": "S{i}", "score": 7, "verdict": "Apply", "reason": "ok"}}' for i in ids[:3])})
    r = c.post("/api/rank/prompt", json={}).json()           # tomorrow: only the four that are new
    assert r["count"] == 4 and r["ranked"] == 3 and not any(f"S{i}:" in r["prompt"] for i in ids[:3])
    assert c.post("/api/rank/prompt", json={"include_ranked": True}).json()["count"] == 7
    # A long list is cut into numbered parts, and each pasted reply is checked against its own part.
    old = PR.PART_JOBS
    PR.PART_JOBS = 3
    try:
        r = c.post("/api/rank/prompt", json={"include_ranked": True}).json()
        assert [p["count"] for p in r["parts"]] == [3, 3, 1] and "part 2 of 3" in r["parts"][1]["prompt"]
        reply = "\n".join(f'{{"code": "{code}", "score": 6, "verdict": "Apply", "reason": "ok"}}' for code in r["parts"][1]["codes"][:2])
        out = c.post("/api/rank/import", json={"text": reply}).json()
        assert out["not_in_reply"] == [r["parts"][1]["codes"][2]]
    finally:
        PR.PART_JOBS = old


def test_skip_archives_and_restores_and_applied_joins_pipeline(tmp_path):
    c = TestClient(create_app(Service(tmp_path / "s.db")))
    setup_profile(c)
    ids = [c.post("/api/opportunities", json={"company": f"C{i}", "position": "Analyst", "job_description": _jd(i)}).json()["id"]
           for i in range(3)]
    assert c.post("/api/opportunities/batch", json={"ids": ids[:2], "action": "archive"}).json()["count"] == 2
    assert [o["id"] for o in c.get("/api/opportunities").json()] == [ids[2]]
    assert {o["id"] for o in c.get("/api/opportunities?status=archived").json()} == set(ids[:2])
    assert c.post("/api/rank/prompt", json={}).json()["count"] == 1            # skipped jobs are not ranked again
    seen = c.post("/api/parse", json={"company": "C0", "position": "Analyst", "job_description": _jd(0)}).json()["seen"]
    assert seen and seen[0]["status"] == "archived"                            # re-pasting a skipped job warns
    c.post("/api/opportunities/batch", json={"ids": [ids[0]], "action": "restore"})
    assert {o["id"] for o in c.get("/api/opportunities").json()} == {ids[0], ids[2]}
    before = c.get("/api/applications").json()["total"]
    c.post("/api/opportunities/batch", json={"ids": [ids[2]], "action": "apply"})
    assert c.get("/api/applications").json()["total"] == before + 1
    assert [o["id"] for o in c.get("/api/opportunities").json()] == [ids[0]]
    assert c.post("/api/opportunities/batch", json={"ids": [ids[0]], "action": "nope"}).status_code == 422
