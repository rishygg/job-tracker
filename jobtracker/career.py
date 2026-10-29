"""Career development: interview journal insights, personalised practice, story bank and the skills report.

Everything here works without AI. Ollama is used only for two optional, focused tasks: practice questions for a
specific upcoming interview, and feedback on an answer you wrote.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, timedelta

import pandas as pd

from .dimensions import DimensionInferer
from .evidence import METRIC

# --------------------------------------------------------------------------- question types
CATEGORIES = ["Motivation", "Experience & CV", "Behavioural", "Situational", "Technical", "Case & problem-solving",
              "Career goals", "Company & industry", "Logistics", "Other"]

CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("Logistics", re.compile(r"\b(salary|compensation|notice period|start date|when can you start|permit|visa|relocat|"
                             r"availability|available|part[- ]time|hours|gehalt|kündigungsfrist)\b", re.I)),
    ("Behavioural", re.compile(r"\b(tell (me|us) about a time|describe a (time|situation)|give (me |us )?an example|"
                               r"have you ever|when did you|a time when|biggest (challenge|mistake|failure)|"
                               r"conflict|disagree|difficult (person|colleague|stakeholder)|proud of)\b", re.I)),
    ("Situational", re.compile(r"\b(what would you do|how would you (handle|deal|react|respond|approach)|imagine|"
                               r"suppose|if you (were|had)|in your first \d+ days|first (90|100) days)\b", re.I)),
    ("Case & problem-solving", re.compile(r"\b(estimate|how many|market size|case|brain ?teaser|guesstimate|"
                                          r"walk (me|us) through how you would|prioriti[sz]e these|design an? )\b", re.I)),
    ("Motivation", re.compile(r"\b(why (do you want|are you interested|this (role|job|position|company)|us|our|"
                              r"did you apply|should we hire)|what (attracts|interests|motivates) you|motivation)\b", re.I)),
    ("Career goals", re.compile(r"\b(where do you see yourself|five years|5 years|long[- ]term|career (goals?|plans?)|"
                                r"next step in your career|ambitions?)\b", re.I)),
    ("Company & industry", re.compile(r"\b(what do you know about (us|the company|our)|our (products?|competitors?|"
                                      r"strategy)|industry trends?|the market|regulat)\b", re.I)),
    ("Experience & CV", re.compile(r"\b(walk (me|us) through (your|the) (cv|resume|background)|tell (me|us) about "
                                   r"(yourself|your (thesis|project|role|background|research|internship))|"
                                   r"your (thesis|cv|resume|publication)|what did you do (at|in))\b", re.I)),
    ("Technical", re.compile(r"\b(explain|what is|what's the difference|how does|how do you|how would you (check|test|measure|"
                             r"validate|analy[sz]e|clean)|data ?set|data quality|code|coding|sql|python|r\b|"
                             r"statistic|regression|p-?value|algorithm|model|machine learning|excel|test|method|"
                             r"technique|analy[sz]e)\b", re.I)),
]

COMPETENCIES: dict[str, re.Pattern] = {
    "Stakeholder management": re.compile(r"stakeholder|client|customer|manager|senior|partner|cross[- ]functional", re.I),
    "Teamwork": re.compile(r"\bteam|collaborat|colleague|together", re.I),
    "Leadership": re.compile(r"\blead|leader|mentor|supervis|took charge|ownership|initiative", re.I),
    "Conflict & disagreement": re.compile(r"conflict|disagree|push ?back|difficult (person|colleague)|tension", re.I),
    "Prioritisation & time": re.compile(r"priorit|deadline|time management|pressure|multiple (tasks|projects)|busy", re.I),
    "Communication": re.compile(r"communicat|present|explain|non[- ]technical|audience|writ(e|ing) (a|the) report", re.I),
    "Problem solving": re.compile(r"problem|solve|solution|challenge|obstacle|issue|troubleshoot", re.I),
    "Data & analysis": re.compile(r"\bdata|analy|statistic|model|insight|dashboard|metric|sql|python|\br\b", re.I),
    "Attention to detail & quality": re.compile(r"detail|accura|quality|error|mistake|compliance|gmp|validat|regulat", re.I),
    "Adaptability & learning": re.compile(r"adapt|change|learn|new (tool|skill|field)|uncertain|ambigu|unfamiliar", re.I),
    "Failure & resilience": re.compile(r"fail|mistake|setback|went wrong|weakness|criticism|feedback", re.I),
    "Influence & persuasion": re.compile(r"persuad|convinc|influenc|buy[- ]in|negotiat", re.I),
    "Motivation & fit": re.compile(r"why (us|this|do you)|motivat|interest|values|culture", re.I),
}


def categorise(question: str) -> str:
    for cat, rx in CATEGORY_RULES:
        if rx.search(question or ""):
            return cat
    return "Other"


def competencies(text: str) -> list[str]:
    return [c for c, rx in COMPETENCIES.items() if rx.search(text or "")]


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (t or "").lower()) if w not in _STOP}


_STOP = {"tell", "about", "time", "when", "what", "your", "with", "have", "that", "this", "would", "describe", "give",
         "example", "were", "they", "them", "there", "which", "from", "into", "how", "you", "could", "should", "please"}


def similar(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / max(1, len(wa | wb))


# --------------------------------------------------------------------------- themes from the journal
def themes(interviews: list[dict], questions: list[dict], stories: list[dict]) -> dict:
    """Recurring patterns across your interviews."""
    by_iv = {i["id"]: i for i in interviews}
    cat = defaultdict(lambda: {"count": 0, "ratings": []})
    comp = Counter()
    comp_low = Counter()
    for q in questions:
        c = q.get("category") or categorise(q["question"])
        cat[c]["count"] += 1
        if q.get("rating"):
            cat[c]["ratings"].append(q["rating"])
        cs = q.get("competencies") or competencies(q["question"])
        comp.update(cs)
        if q.get("rating") and q["rating"] <= 2:
            comp_low.update(cs)
    categories = sorted(({"category": k, "count": v["count"],
                          "avg_rating": round(sum(v["ratings"]) / len(v["ratings"]), 1) if v["ratings"] else None,
                          "rated": len(v["ratings"])} for k, v in cat.items()), key=lambda x: -x["count"])

    # What you said you struggled with, and what feedback mentioned.
    struggle_comp, feedback_comp = Counter(), Counter()
    for i in interviews:
        struggle_comp.update(competencies(i.get("struggled") or ""))
        feedback_comp.update(competencies(i.get("feedback") or ""))
    weak = Counter()
    for k, v in comp_low.items():
        weak[k] += 2 * v
    for k, v in struggle_comp.items():
        weak[k] += 2 * v
    for k, v in feedback_comp.items():
        weak[k] += v
    for c in categories:
        if c["avg_rating"] is not None and c["avg_rating"] < 3 and c["rated"] >= 1:
            weak[f"{c['category']} questions"] += 2

    # Questions you've been asked more than once (in different interviews).
    repeated, used = [], set()
    for i, a in enumerate(questions):
        if a["id"] in used:
            continue
        group = [a] + [b for b in questions[i + 1:] if b["id"] not in used and b["interview_id"] != a["interview_id"]
                       and similar(a["question"], b["question"]) >= 0.5]
        if len(group) > 1:
            used.update(q["id"] for q in group)
            repeated.append({"question": a["question"], "times": len(group),
                             "companies": sorted({by_iv.get(q["interview_id"], {}).get("company") or "?" for q in group}),
                             "avg_rating": _avg([q.get("rating") for q in group])})
    repeated.sort(key=lambda r: -r["times"])

    # Competencies you're asked about but have no story for.
    story_comp = Counter(c for s in stories for c in (s.get("competencies") or []))
    story_gaps = [{"competency": k, "asked": v} for k, v in comp.most_common()
                  if not story_comp.get(k) and k != "Motivation & fit"][:6]

    ratings = [i["rating"] for i in interviews if i.get("rating")]
    trend = None
    if len(ratings) >= 4:
        dated = sorted((i for i in interviews if i.get("rating")), key=lambda i: i["date"])
        half = len(dated) // 2
        trend = round(_avg([i["rating"] for i in dated[half:]]) - _avg([i["rating"] for i in dated[:half]]), 1)

    return {"interviews": len(interviews), "questions": len(questions), "categories": categories,
            "competencies": [{"competency": k, "count": v, "low": comp_low.get(k, 0)} for k, v in comp.most_common(10)],
            "focus": [{"area": k, "score": v} for k, v in weak.most_common(4)],
            "repeated": repeated[:6], "story_gaps": story_gaps,
            "avg_rating": _avg(ratings), "rating_trend": trend,
            "struggled": [{"date": i["date"], "company": i.get("company"), "text": i["struggled"]}
                          for i in sorted(interviews, key=lambda i: i["date"], reverse=True) if i.get("struggled")][:5],
            "feedback": [{"date": i["date"], "company": i.get("company"), "text": i["feedback"]}
                         for i in sorted(interviews, key=lambda i: i["date"], reverse=True) if i.get("feedback")][:5]}


def _avg(xs):
    xs = [x for x in xs if x]
    return round(sum(xs) / len(xs), 1) if xs else None


# --------------------------------------------------------------------------- practice
BANK: list[tuple[str, str]] = [
    ("Motivation", "Why do you want this role, and why with us rather than a competitor?"),
    ("Motivation", "What about this position fits where you want to go next?"),
    ("Experience & CV", "Walk me through your CV in two minutes, focusing on what's relevant here."),
    ("Experience & CV", "Tell me about the project on your CV you're proudest of. What exactly was your part?"),
    ("Experience & CV", "Explain your thesis or research to someone outside your field in one minute."),
    ("Behavioural", "Tell me about a time you had to work with a difficult stakeholder."),
    ("Behavioural", "Describe a situation where you disagreed with a colleague or supervisor. What happened?"),
    ("Behavioural", "Tell me about a time something went wrong in your work. What did you do and learn?"),
    ("Behavioural", "Give an example of a time you had several deadlines at once. How did you prioritise?"),
    ("Behavioural", "Tell me about a time you took the initiative without being asked."),
    ("Behavioural", "Describe a time you had to explain something technical to a non-technical audience."),
    ("Behavioural", "Tell me about a time you had to learn a new tool or field quickly."),
    ("Behavioural", "Give an example of when you persuaded someone to change their approach."),
    ("Situational", "In your first 90 days here, what would you focus on?"),
    ("Situational", "What would you do if you found an error in a report that had already been shared?"),
    ("Situational", "How would you handle two senior people giving you conflicting priorities?"),
    ("Technical", "How do you check that a dataset is reliable before you analyse it?"),
    ("Technical", "Explain a statistical method you've used and why it was the right choice."),
    ("Technical", "How would you present the same analysis to a scientist and to a manager?"),
    ("Case & problem-solving", "A key metric dropped 20% last month. How would you find out why?"),
    ("Case & problem-solving", "How would you decide which of five process-improvement ideas to do first?"),
    ("Career goals", "Where do you see yourself in three to five years?"),
    ("Company & industry", "What do you know about us, and what do you think our biggest challenge is?"),
    ("Company & industry", "What trend in this industry do you find most interesting right now?"),
    ("Other", "What is your biggest weakness, and what are you doing about it?"),
    ("Other", "What questions do you have for us?"),
]


def _req_question(req: str) -> str:
    r = re.sub(r"^(experience (in|with)|knowledge of|proficiency in|ability to|strong|excellent|proven)\s+", "",
               req.strip().rstrip("."), flags=re.I)
    r = r[0].lower() + r[1:] if r else r
    return f"This role asks for {r[:140]}. Tell me about a time you showed it."


def practice_set(interviews: list[dict], questions: list[dict], stories: list[dict], upcoming: list[dict],
                 job_profiles: dict[int, dict], theme: dict, done: list[dict], limit: int = 14) -> list[dict]:
    """A practice list built from your own history first, then your next interviews, then your weak spots.

    upcoming: [{application_id, company, position, stage, date}], job_profiles: application_id -> builder.job_profile
    done: past practice rows, to avoid repeating what you've already practised well.
    """
    practised_well = {p["question"].lower() for p in done if (p.get("rating") or 0) >= 4}
    out, seen = [], set()

    def add(q: str, category: str, source: str, reason: str, ref: str | None = None, priority: int = 5):
        key = q.lower()
        if key in seen or key in practised_well:
            return
        if any(similar(q, o["question"]) >= 0.6 for o in out):
            return
        seen.add(key)
        out.append({"question": q, "category": category, "source": source, "reason": reason, "ref": ref,
                    "priority": priority, "story": suggest_story(q, stories)})

    by_iv = {i["id"]: i for i in interviews}
    # 1. Questions you were actually asked and rated low.
    for q in sorted(questions, key=lambda q: (q.get("rating") or 3)):
        if (q.get("rating") or 5) <= 3:
            iv = by_iv.get(q["interview_id"], {})
            add(q["question"], q.get("category") or categorise(q["question"]), "history",
                f"You rated your answer {q['rating']}/5 at {iv.get('company') or 'an interview'}.", priority=1)
    # 2. Next interviews: what that company asked before, its essential requirements, motivation.
    for u in upcoming:
        job = job_profiles.get(u["application_id"]) or {}
        ref = u.get("ref") or f"application:{u['application_id']}"
        p0 = 0 if u.get("date") else 2  # a dated interview is more urgent than one that's only "coming up"
        asked_motivation = False
        for q in questions:
            iv = by_iv.get(q["interview_id"], {})
            if iv.get("application_id") == u["application_id"] or (iv.get("company") or "").lower() == u["company"].lower():
                cat = q.get("category") or categorise(q["question"])
                asked_motivation |= cat == "Motivation"
                add(q["question"], cat, "upcoming",
                    f"{u['company']} asked this before; your {u['stage'].lower()} is {u['when']}.", ref, priority=p0)
        if not asked_motivation:
            add(f"Why {u['company']}, and why this {u['position']} role?", "Motivation", "upcoming",
                f"Almost certain in your {u['stage'].lower()} with {u['company']} ({u['when']}).", ref, priority=p0)
        for req in (job.get("essential") or job.get("priorities") or [])[:3 if u.get("date") else 1]:
            add(_req_question(req), "Behavioural", "upcoming",
                f"Essential for {u['position']} at {u['company']}; have an example ready.", ref, priority=p0 + 1)
    # 3. Weak areas from your journal.
    focus = [f["area"] for f in theme.get("focus", [])]
    for area in focus:
        cat = area.replace(" questions", "")
        for c, q in BANK:
            if c == cat or COMPETENCIES.get(area, re.compile("$^")).search(q):
                add(q, c, "focus", f"Your journal shows {area.lower()} as an area to work on.", priority=2)
    # 4. Fill with common questions in categories you haven't practised.
    practised_cats = Counter(p.get("category") for p in done)
    for c, q in sorted(BANK, key=lambda x: practised_cats.get(x[0], 0)):
        add(q, c, "common", "Asked in most interviews.", priority=4)
    out.sort(key=lambda x: x["priority"])
    return out[:limit]


NO_STORY = {"Motivation", "Logistics", "Career goals", "Company & industry"}


def suggest_story(question: str, stories: list[dict]) -> dict | None:
    if categorise(question) in NO_STORY:
        return None
    want = set(competencies(question)) - {"Motivation & fit"}
    qw = _words(question)
    best, score = None, 0.0
    for s in stories:
        sc = 2 * len(want & set(s.get("competencies") or [])) + len(qw & _words(" ".join(
            str(s.get(k) or "") for k in ("title", "situation", "task", "action", "result")))) * 0.3
        if sc > score:
            best, score = s, sc
    return {"id": best["id"], "title": best["title"]} if best and score >= 1 else None


# --------------------------------------------------------------------------- answer feedback (rules)
STAR = {
    "situation": re.compile(r"\b(when i was|while (working|at)|at (my|the) |during|in my (role|internship|thesis|lab)|"
                            r"the (project|team|lab) (was|had)|context)\b", re.I),
    "task": re.compile(r"\b(i (was|had) (asked|tasked|responsible)|my (task|goal|job|role) was|needed to|had to|"
                       r"the (goal|aim|challenge) was)\b", re.I),
    "action": re.compile(r"\bi (built|wrote|designed|analy[sz]ed|created|set up|organi[sz]ed|led|proposed|decided|"
                         r"spoke|met|developed|automated|trained|tested|changed|introduced|reached out|prioriti[sz]ed)\b", re.I),
    "result": re.compile(r"\b(as a result|result(ed)? in|which (led|meant|cut|saved|improved)|so that|outcome|"
                         r"in the end|reduced|increased|improved|saved|achiev|published|adopted|was used)\b", re.I),
}


def answer_feedback(question: str, answer: str, category: str | None = None) -> dict:
    a = (answer or "").strip()
    words = len(a.split())
    cat = category or categorise(question)
    strengths, improve = [], []
    star = {k: bool(rx.search(a)) for k, rx in STAR.items()}
    story_q = cat in ("Behavioural", "Situational") or bool(re.search(r"\b(time|example|situation)\b", question, re.I))
    i_count = len(re.findall(r"\bI\b", a))
    we_count = len(re.findall(r"\bwe\b", a, re.I))
    has_number = bool(METRIC.search(a))

    if words < 40:
        improve.append("Too short to judge or to convince: aim for 150-250 words (about 1-2 minutes spoken).")
    elif words > 380:
        improve.append(f"About {words} words is over 2.5 minutes spoken. Cut the context to two sentences.")
    else:
        strengths.append("A good length for a spoken answer.")
    if story_q:
        missing = [k for k, v in star.items() if not v]
        if not missing:
            strengths.append("Has all four STAR parts: situation, task, action and result.")
        else:
            labels = {"situation": "the situation (where, when, what was at stake)", "task": "your specific task or goal",
                      "action": "what YOU did, step by step", "result": "the result, and what changed because of you"}
            improve.append("Missing " + "; ".join(labels[m] for m in missing) + ".")
    if we_count > i_count and we_count >= 3:
        improve.append(f"You say \"we\" {we_count} times and \"I\" {i_count}. Interviewers need to hear your part.")
    elif i_count >= 3:
        strengths.append("Makes your own contribution clear.")
    if star["result"] and not has_number and story_q:
        improve.append("The result has no scale. Add a number if you can (time saved, people, datasets, accuracy).")
    elif has_number:
        strengths.append("Uses concrete numbers.")
    if cat == "Motivation" and not re.search(r"\b(your|the company|the team|the role|this role|products?|mission)\b", a, re.I):
        improve.append("Say something specific about them (a product, the team's work, a detail of the role), not only about you.")
    if re.search(r"\b(passionate|hard[- ]working|team player|perfectionist|detail[- ]oriented)\b", a, re.I):
        improve.append("Swap self-descriptions (\"passionate\", \"team player\") for an example that shows it.")
    score = max(1, min(5, round(3 + 0.6 * (len(strengths) - len(improve)))))
    return {"method": "rules", "score": score, "strengths": strengths[:4], "improve": improve[:5], "star": star if story_q else None,
            "follow_up": _follow_up(cat, star)}


def _follow_up(cat: str, star: dict) -> str | None:
    if cat in ("Behavioural", "Situational"):
        if not star.get("result"):
            return "And what was the outcome?"
        return "What would you do differently next time?"
    if cat == "Motivation":
        return "What would make you turn this job down?"
    if cat == "Technical":
        return "What are the limitations of that approach?"
    return None


# --------------------------------------------------------------------------- story suggestions
def suggest_stories(evidence: list[dict], stories: list[dict], limit: int = 5) -> list[dict]:
    """Achievements from your evidence bank that would make good interview stories and aren't in the bank yet."""
    linked = {s.get("evidence_id") for s in stories}
    told = " ".join((s.get("title") or "") + " " + (s.get("action") or "") for s in stories).lower()
    out = []
    for e in evidence:
        if e.get("hidden") or e["id"] in linked or e.get("kind") not in ("achievement", "project", "responsibility"):
            continue
        if e["text"][:40].lower() in told:
            continue
        score = 2 * bool(e.get("metrics")) + (e.get("kind") == "achievement") + bool(e.get("stakeholders")) + \
            bool(e.get("note") or e.get("outcome"))
        if any(similar(e["text"], o["text"]) >= 0.6 for _, o in out):
            continue
        out.append((score, e))
    out.sort(key=lambda x: -x[0])
    return [{"evidence_id": e["id"], "text": e["text"], "context": e.get("context"),
             "competencies": competencies(e["text"] + " " + (e.get("note") or "")), "metrics": e.get("metrics", [])}
            for s, e in out[:limit] if s >= 1]


def story_check(story: dict) -> list[str]:
    tips = []
    for k, label in (("situation", "situation"), ("task", "task"), ("action", "action"), ("result", "result")):
        if not (story.get(k) or "").strip():
            tips.append(f"Add the {label}.")
    act = story.get("action") or ""
    if act and len(re.findall(r"\bI\b", act)) < 1 and re.search(r"\bwe\b", act, re.I):
        tips.append("Write the action as what you did (\"I…\"), not the team.")
    if story.get("result") and not METRIC.search(story["result"]):
        tips.append("Give the result a scale or number if you can.")
    return tips


# --------------------------------------------------------------------------- skills report
def skills_report(jobs: list[dict], inferer: DimensionInferer, have: set[str], fits: dict[str, dict],
                  today: date | None = None, recent_days: int = 60, material: str = "") -> dict:
    """Skills across the roles you want.

    jobs: [{key, company, position, jd, date, kind, wanted}] (applications and saved jobs)
    have: lower-case skills found in your profile, CV and evidence bank. fits: key -> fit result.
    """
    today = today or date.today()
    cut = today - timedelta(days=recent_days)
    groups = inferer.skill_groups
    jobs = [j for j in jobs if len((j.get("jd") or "").strip()) >= 80]
    stats: dict[str, dict] = {}
    recent_n = sum(1 for j in jobs if j["date"] and j["date"] >= cut)
    older_n = len(jobs) - recent_n
    for j in jobs:
        skills = list(dict.fromkeys([x.lower() for x in inferer.analyse_jd(j["jd"]).skills]
                                    + [x.lower() for x in j.get("extra_skills", [])]))
        for s in skills:
            st = stats.setdefault(s, {"skill": s, "jobs": 0, "recent": 0, "older": 0, "examples": []})
            st["jobs"] += 1
            if j["date"] and j["date"] >= cut:
                st["recent"] += 1
            else:
                st["older"] += 1
            if len(st["examples"]) < 3:
                st["examples"].append(f"{j['position']} · {j['company']}")
    rows = []
    for s, st in stats.items():
        share = st["jobs"] / max(1, len(jobs))
        trend = None
        if recent_n >= 3 and older_n >= 3:
            trend = round(st["recent"] / recent_n - st["older"] / older_n, 2)
        mat = material.lower()
        has = s.lower() in have or bool(mat and re.search(rf"(?<![\w]){re.escape(s.lower())}(?![\w])", mat))
        rows.append({**st, "label": display_skill(s), "share": round(share, 2), "have": has, "group": groups.get(s, ""), "trend": trend})
    rows.sort(key=lambda r: (-r["jobs"], r["skill"]))

    # Essential requirements you were missing, across all fit analyses.
    missing = Counter()
    where = defaultdict(list)
    for key, f in fits.items():
        for r in f.get("requirements", []):
            if r.get("type") == "essential" and r.get("status") == "missing" and r.get("text"):
                label = _req_label(r["text"], inferer)
                missing[label] += 1
                j = next((x for x in jobs if x["key"] == key), None)
                if j and len(where[label]) < 3:
                    where[label].append(f"{j['position']} · {j['company']}")
    blockers = Counter(b["type"] for f in fits.values() for b in f.get("blockers", []) if b.get("severity") == "high")
    return {
        "jobs": len(jobs), "recent_jobs": recent_n,
        "skills": rows[:40],
        "top_gaps": [r for r in rows if not r["have"]][:8],
        "strengths": [r for r in rows if r["have"]][:8],
        "emerging": sorted([r for r in rows if r["trend"] and r["trend"] >= 0.15], key=lambda r: -r["trend"])[:6],
        "missing_essentials": [{"requirement": k, "jobs": v, "examples": where[k]} for k, v in missing.most_common(8) if v >= 1],
        "blockers": [{"type": k, "jobs": v} for k, v in blockers.most_common()],
        "fits_counted": len(fits),
    }


SPECIAL = {"gxp": "GxP", "power bi": "Power BI", "power automate": "Power Automate", "pytorch": "PyTorch",
           "tensorflow": "TensorFlow", "javascript": "JavaScript", "typescript": "TypeScript", "github": "GitHub",
           "matlab": "MATLAB", "ga4": "GA4", "hubspot": "HubSpot", "salesforce": "Salesforce", "scikit-learn": "scikit-learn",
           "fmri": "fMRI", "eeg": "EEG", "mri": "MRI", "ml": "ML", "ai": "AI", "bi": "BI", "etl": "ETL", "crm": "CRM",
           "seo": "SEO", "ux": "UX", "oee": "OEE", "capa": "CAPA", "sap": "SAP", "cdisc": "CDISC", "sdtm": "SDTM",
           "qpcr": "qPCR", "crispr": "CRISPR", "facs": "FACS", "elisa": "ELISA", "nlp": "NLP", "spss": "SPSS"}


def display_skill(s: str) -> str:
    low = s.lower().strip()
    if low in SPECIAL:
        return SPECIAL[low]
    if s != low:  # already has its own capitalisation
        return s
    if len(low) <= 4 and low.isalpha() and low not in {"excel", "java", "rust", "go"}:
        return low.upper()
    return " ".join(SPECIAL.get(w, w.upper() if len(w) <= 3 and w.isalpha() and w not in {"and", "of", "for", "the"} else w.capitalize())
                    for w in low.split())


def _req_label(text: str, inferer: DimensionInferer) -> str:
    """Group requirements by their skill when there is one, else a shortened sentence."""
    skills = inferer.analyse_jd(text).skills
    if skills:
        return ", ".join(display_skill(x) for x in skills[:2])
    t = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return t[:90] + ("…" if len(t) > 90 else "")


# --------------------------------------------------------------------------- upcoming interviews
INTERVIEW_STAGES = {"Screening", "Interview", "Final interview"}


def upcoming_interviews(df: pd.DataFrame, events: pd.DataFrame, today: date | None = None) -> list[dict]:
    """Applications with an interview coming up (future-dated stage) or currently at an interview stage."""
    today = today or date.today()
    out = {}
    if df.empty:
        return []
    names = df.set_index("id")
    fut = events[events["stage"].isin(INTERVIEW_STAGES) & (events["date"].dt.date >= today)] if not events.empty else events
    for e in fut.sort_values("date").itertuples():
        if e.application_id in names.index and e.application_id not in out:
            a = names.loc[e.application_id]
            days = (e.date.date() - today).days
            out[int(e.application_id)] = {"application_id": int(e.application_id), "company": a["company"],
                                          "position": a["position"], "stage": e.stage, "date": e.date.date().isoformat(),
                                          "when": "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"}
    # At an interview stage without a dated event: only if something happened recently (otherwise it's stale).
    for r in df[df["status"].isin(["Interview", "Final interview"]) & (df["days_since_activity"] <= 21)].itertuples():
        if int(r.id) not in out:
            out[int(r.id)] = {"application_id": int(r.id), "company": r.company, "position": r.position,
                              "stage": r.status, "date": None, "when": "coming up"}
    return list(out.values())[:4]


def interviews_to_log(df: pd.DataFrame, events: pd.DataFrame, interviews: list[dict], today: date | None = None,
                      days: int = 21) -> list[dict]:
    """Interview stages in the past few weeks with no journal entry yet."""
    today = today or date.today()
    if df.empty or events.empty:
        return []
    logged = {(i.get("application_id"), i["date"]) for i in interviews}
    logged_apps = {i.get("application_id") for i in interviews}
    names = df.set_index("id")
    past = events[events["stage"].isin(INTERVIEW_STAGES - {"Screening"}) & (events["date"].dt.date < today + timedelta(days=1))
                  & (events["date"].dt.date >= today - timedelta(days=days))]
    out = []
    for e in past.itertuples():
        d = e.date.date().isoformat()
        if e.application_id not in names.index or (int(e.application_id), d) in logged:
            continue
        if int(e.application_id) in logged_apps and e.stage == "Interview":
            # Already logged an interview with them after this date? Then this one's covered.
            if any(i.get("application_id") == int(e.application_id) and i["date"] >= d for i in interviews):
                continue
        a = names.loc[e.application_id]
        out.append({"application_id": int(e.application_id), "company": a["company"], "position": a["position"],
                    "stage": e.stage, "date": d, "event_id": int(e.id)})
    return out
