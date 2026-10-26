"""CV builder and cover-letter builder: focused critique, not ghost-writing.

Per job, the app works out what the role prioritises, picks the candidate's most relevant evidence
from the evidence bank, and returns a small set of prioritised findings:

  CV builder     what to emphasise, what to reword, recruiter-style critiques of specific bullets
                 (why it's weak + one concrete fix), questions a recruiter would ask, what to add if
                 true, what to cut, keywords.
  Letter builder the strongest experience-to-role connection, the most credible reason to be
                 interested, the one example worth highlighting, what's missing from the story,
                 generic statements to avoid, and a suggested outline.

Both run instantly with rules; with Ollama, only the job priorities and the top evidence (by id) are
sent, so the model's answer stays short and can only point at real CV lines.
"""

from __future__ import annotations

import re
from collections import Counter

from .dimensions import DimensionInferer
from .evidence import METRIC, RESULT_VERBS, WEAK_STARTS
from .fit import JUNK, STOP, _header_kind, _terms, extract_requirements
from .llm import LLMError, Ollama

RESP_HEADERS = ("in this role", "what you will be doing", "what you'll be doing", "your impact", "responsibilities", "what you'll do", "what you will do", "your tasks", "your role", "the role",
                "key responsibilities", "your responsibilities", "tasks", "aufgaben", "deine aufgaben", "ihre aufgaben",
                "you will", "in this role")
ABOUT_HEADERS = ("about us", "who we are", "about the company", "our mission", "why join", "about the role", "the team")
VAGUE = re.compile(r"\b(various|several|multiple|many|numerous|etc\.?|a range of|different|some)\b", re.I)
PASSIVE = re.compile(r"\b(was|were|been|being)\s+\w+ed\b", re.I)
GENERIC_PHRASES = [
    ("I am writing to apply for", "Open with the connection between your work and their need."),
    ("I am passionate about", "Show the interest through something you did or chose."),
    ("I am a hard-working team player", "Name a team result you contributed to."),
    ("I believe I would be a great fit", "Let the evidence make the case; state the match concretely."),
    ("strong communication skills", "Mention who you communicated with and what came of it."),
    ("fast learner", "Give one example of something you picked up quickly and used."),
    ("detail-oriented", "Point to work where accuracy mattered (data QC, regulated documents)."),
    ("Your company is a leader in", "Refer to a specific product, study or decision of theirs."),
    ("I have always wanted to", "Explain the more recent, concrete reason."),
    ("Please find my CV attached", "End with availability and what you'd like to discuss."),
]


# --------------------------------------------------------------------------- job profile
THEME_STOP = STOP | {"experience", "skills", "ability", "knowledge", "about", "their", "within", "working", "including",
                     "join", "candidate", "position", "requirements", "career", "support", "develop", "solutions", "role",
                     "company", "opportunity", "looking", "help", "make", "ensure", "across", "every", "provide", "offer",
                     "people", "great", "world", "together", "also", "global", "based", "business", "strong", "good"}


def _themes(jd: str, inferer: DimensionInferer) -> list[str]:
    """Repeated themes: named skills, then two-word phrases that recur (e.g. "continuous improvement")."""
    skills = Counter()
    for sent in re.split(r"[\n.;]", jd):
        for sk in inferer.analyse_jd(sent).skills:
            skills[sk] += 1
    # The company's own name repeats a lot; leave out capitalised words that look like names.
    names = {w.lower() for w in re.findall(r"\b[A-Z][a-z]{3,}\b", jd) if jd.count(w) >= 2 and w.lower() not in
             {"experience", "data", "digital", "business", "manufacturing"}} - {s.lower() for s in skills}
    words = [w for w in re.findall(r"[a-zäöü][a-zäöü\-]{2,}", jd.lower())]
    bigrams = Counter(f"{a} {b}" for a, b in zip(words, words[1:])
                      if a not in THEME_STOP and b not in THEME_STOP and a not in names and b not in names
                      and len(a) > 3 and len(b) > 3)
    out = [sk for sk, _ in skills.most_common(8)]
    out += [bg for bg, n in bigrams.most_common(10) if n >= 2]
    return list(dict.fromkeys(out))[:10]


def job_profile(jd: str, inferer: DimensionInferer) -> dict:
    """What the role is about: responsibilities, essential and desirable requirements, repeated themes."""
    reqs = extract_requirements(jd)
    responsibilities, about = [], []
    section = None
    for raw in (jd or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.strip(":*# ").lower()
        if len(low) <= 60 and any(low.startswith(h) for h in RESP_HEADERS):
            section = "resp"
            continue
        if len(low) <= 60 and any(low.startswith(h) for h in ABOUT_HEADERS):
            section = "about"
            continue
        if _header_kind(line):
            section = "other"
            continue
        text = re.sub(r"^\s*(?:[•▪◦●○■□➢►▶–—\-*·✓✔]|\d+[.)])\s*", "", line).strip()
        if text.endswith(":") or JUNK.search(text):
            continue
        if section == "resp" and 12 <= len(text) <= 260:
            responsibilities.append(text)
        elif section in ("about", None) and 20 <= len(text) <= 400 and (section == "about" or len(text.split()) >= 7):
            about.extend(s.strip() for s in re.split(r"(?<=[.!])\s+", text) if len(s.strip()) > 20)
    themes = _themes(jd or "", inferer)
    ess = [r["text"] for r in reqs if r["type"] == "essential"]
    pref = [r["text"] for r in reqs if r["type"] == "preferred"]
    priorities = (ess[:3] + responsibilities[:2])[:5]
    return {"essential": ess, "preferred": pref, "responsibilities": responsibilities[:10], "themes": themes,
            "priorities": priorities, "about": about[:6], "skills": inferer.analyse_jd(jd or "").skills}


# --------------------------------------------------------------------------- relevance
GENERIC_TERMS = {"analys", "analysi", "data", "experienc", "develop", "work", "team", "support", "manag", "project",
                 "result", "skill", "strong", "relat", "field", "provid", "ensur", "prepar", "plann", "use", "process"}


def _relevance(ev: dict, targets: list[tuple[str, float]], jd_skills: set[str]) -> tuple[float, str | None]:
    eterms = _terms(ev["text"] + " " + (ev.get("did") or "")) - GENERIC_TERMS
    eskills = {s.lower() for s in ev.get("skills", [])}
    best, best_t = 0.0, None
    eskills_l = {s.lower() for s in ev.get("skills", [])}
    for text, weight in targets:
        tt = _terms(text) - GENERIC_TERMS
        if not tt:
            continue
        shared = eterms & tt
        tskills = {s.lower() for s in jd_skills if s.lower() in text.lower()}
        if len(shared) < 2 and not (tskills & eskills_l):
            continue  # one shared word is usually coincidence
        ov = len(shared) / len(tt) + 0.3 * len(tskills & eskills_l)
        if ov * weight > best:
            best, best_t = ov * weight, text
    best += 0.15 * len(eskills & jd_skills)
    if ev.get("kind") == "achievement":
        best *= 1.15
    if ev.get("confirmed"):
        best *= 1.05
    return best, best_t


NON_EVIDENCE = {"personal", "coursework"}
WORK_KINDS = {"achievement", "responsibility", "project"}
AI_KINDS = WORK_KINDS | {"publication", "qualification"}  # skills lists and summaries aren't lines to critique


def rank_evidence(evidence: list[dict], job: dict, k: int = 12) -> list[dict]:
    targets = ([(t, 1.0) for t in job["essential"]] + [(t, 0.7) for t in job["preferred"]]
               + [(t, 0.8) for t in job["responsibilities"]] + [(t, 0.5) for t in job["themes"]])
    jd_skills = {s.lower() for s in job["skills"]}
    scored = []
    seen: list[set] = []
    for ev in evidence:
        if ev.get("hidden") or ev.get("kind") in NON_EVIDENCE:
            continue
        words = set(re.findall(r"[a-z]{3,}", ev["text"].lower()))
        if any(words and len(words & w) / len(words | w) >= 0.7 for w in seen):
            continue  # near-duplicate of a record already considered
        seen.append(words)
        sc, t = _relevance(ev, targets, jd_skills)
        scored.append({**ev, "relevance": round(sc, 3), "matches": t})
    scored.sort(key=lambda e: e["relevance"], reverse=True)
    return scored[:k]


# --------------------------------------------------------------------------- critique rules
def critique_bullet(ev: dict, job: dict) -> dict | None:
    """The single most important recruiter objection to one bullet, with one concrete fix."""
    text = ev["text"]
    words = text.split()
    has_metric = bool(METRIC.search(text))
    if ev.get("kind") not in WORK_KINDS or "education" in (ev.get("section") or "").lower():
        return None
    if WEAK_STARTS.search(text):
        first = WEAK_STARTS.search(text).group(0)
        return {"issue": f"Starts with “{first}”, which describes a duty, not what you achieved.",
                "fix": "Start with the action you took and end with the result, e.g. “Built …, reducing …”.", "severity": 3}
    if ev.get("kind") == "achievement" and not has_metric and RESULT_VERBS.search(text):
        return {"issue": "Claims an achievement but gives no sense of scale or result, so it's hard to judge.",
                "fix": "Add one number: how many (people, datasets, sites), how much faster, or what changed.", "severity": 3}
    if not has_metric and ev.get("kind") == "responsibility":
        return {"issue": "Reads as a task list; a recruiter can't tell how well you did it or at what scale.",
                "fix": "Add the outcome or scale (volume, frequency, accuracy, who used the result).", "severity": 2}
    if len(words) > 35:
        return {"issue": f"{len(words)} words: too long to skim in the 6–8 seconds a first screen takes.",
                "fix": "Split it into two bullets or cut it to one action and one result (under 25 words).", "severity": 2}
    if VAGUE.search(text):
        w = VAGUE.search(text).group(0)
        return {"issue": f"“{w}” is vague and invites the question “how many, exactly?”.",
                "fix": f"Replace “{w}” with the actual number or names.", "severity": 2}
    if PASSIVE.search(text):
        return {"issue": "Passive wording hides who did the work.", "fix": "Rewrite in the active voice with you as the subject.",
                "severity": 1}
    missing_terms = [s for s in job["skills"] if s.lower() not in text.lower()
                     and any(s.lower() in t.lower() for t in [ev.get("matches") or ""])]
    if missing_terms:
        return {"issue": f"Relevant to “{ev.get('matches')}”, but doesn't use the job's term “{missing_terms[0]}”.",
                "fix": f"If accurate, name “{missing_terms[0]}” explicitly so screeners and ATS match it.", "severity": 1}
    return None


def _questions(fit: dict | None, job: dict, evidence: list[dict]) -> list[dict]:
    """Questions a recruiter would likely ask, from gaps and blockers."""
    qs = []
    for b in (fit or {}).get("blockers", [])[:3]:
        if b["type"] == "Work permit":
            qs.append({"question": "Are you able to work here without sponsorship?",
                       "how_to_answer": "State your current permit and what you're eligible for, in one line on the CV or letter."})
        elif b["type"] == "Language":
            qs.append({"question": "How well do you speak the required language?",
                       "how_to_answer": "Give your certified level and what you're doing to improve it (course, exam date)."})
        elif b["type"] == "Experience":
            qs.append({"question": "You have fewer years than we asked for. Why should we still talk to you?",
                       "how_to_answer": "Point to the most comparable responsibility you've held and its result."})
        elif b["type"] == "Eligibility":
            qs.append({"question": "Do you meet the degree requirement?", "how_to_answer": "Give your degree status and expected completion date."})
    for r in (fit or {}).get("requirements", []):
        if r.get("type") == "essential" and r.get("status") == "partial" and r.get("kind") == "degree":
            qs.append({"question": "When will you finish your degree, and can you start before then?",
                       "how_to_answer": "Put the expected completion date next to the degree and your earliest start date in the letter."})
        elif r.get("type") == "essential" and r.get("status") == "partial" and r.get("kind") == "years":
            qs.append({"question": f"{r.get('note') or 'You have fewer years than asked.'} What makes up for it?",
                       "how_to_answer": "Lead with your most comparable, results-backed experience and its scale."})
    for g in (fit or {}).get("gaps", [])[:6]:
        if g.get("type") == "essential" and g.get("status") == "missing" and len(qs) < 5:
            qs.append({"question": f"Where have you done this: “{g['point']}”?",
                       "how_to_answer": "Find the closest experience you have and name it explicitly, or address it as something you're building."})
    return qs[:5]


def _keywords(cv_text: str, job: dict) -> tuple[list[str], list[str]]:
    low = cv_text.lower()
    return [s for s in job["skills"] if s.lower() in low], [s for s in job["skills"] if s.lower() not in low]


def cv_builder_rules(evidence: list[dict], job: dict, fit: dict | None, cv_text: str) -> dict:
    top = rank_evidence(evidence, job, k=14)
    rel = [e for e in top if e["relevance"] > 0.12]
    emphasise, used = [], Counter()
    for e in rel:
        if e["kind"] in ("achievement", "responsibility", "project", "publication") and used[e["matches"]] < 2:
            used[e["matches"]] += 1
            emphasise.append({"id": e["id"], "text": e["text"], "why": f"Shows: {e['matches']}"})
        if len(emphasise) >= 5:
            break
    critiques = []
    for e in rel:
        c = critique_bullet(e, job)
        if c:
            critiques.append({"id": e["id"], "text": e["text"], "issue": c["issue"], "fix": c["fix"],
                              "priority": "high" if c["severity"] >= 3 and e["relevance"] > 0.3 else "medium" if c["severity"] >= 2 else "low",
                              "_s": c["severity"] * (1 + e["relevance"])})
    critiques.sort(key=lambda c: c["_s"], reverse=True)
    for c in critiques:
        c.pop("_s")
    reword = []
    for e in rel:
        missing = [s for s in job["skills"] if s.lower() not in e["text"].lower()
                   and e.get("matches") and s.lower() in e["matches"].lower()]
        if missing and len(reword) < 4:
            reword.append({"id": e["id"], "text": e["text"],
                           "suggestion": f"Use the job's wording (“{missing[0]}”) if it accurately describes this work."})
    rel_ids = {e["id"] for e in top if e["relevance"] > 0.05}
    cut = [{"id": e["id"], "text": e["text"], "why": "Little to do with this role; shorten it or move it down."}
           for e in evidence if not e.get("hidden") and e["id"] not in rel_ids and not e.get("duplicate_of")
           and e.get("kind") in WORK_KINDS and len(e["text"].split()) > 8][:4]
    add = [{"what": g["point"], "why": "Essential, and your CV doesn't show it." if g.get("type") == "essential" else "Preferred; would strengthen the case."}
           for g in (fit or {}).get("gaps", []) if g.get("status") == "missing"][:5]
    have, missing_kw = _keywords(cv_text, job)
    return {"method": "rules", "model": None, "priorities": job["priorities"], "themes": job["themes"],
            "emphasise": emphasise, "reword": reword, "critique": critiques[:6], "questions": _questions(fit, job, evidence),
            "add_if_true": add, "cut": cut, "keywords": have, "missing_keywords": missing_kw}


def letter_builder_rules(evidence: list[dict], job: dict, fit: dict | None, company: str, position: str) -> dict:
    top = rank_evidence(evidence, job, k=10)
    work = [e for e in top if e["kind"] in ("achievement", "responsibility", "project", "publication")]
    ess = set(job["essential"])
    conn = next((e for e in work if e.get("matches") in ess), work[0] if work else None)
    highlight = next((e for e in work if METRIC.search(e["text"]) and (not conn or e["id"] != conn["id"])),
                     next((e for e in work if e["kind"] == "achievement" and (not conn or e["id"] != conn["id"])), None))
    # Interest: the "about us" sentence that overlaps most with the candidate's own background.
    cand_terms = set().union(*[_terms(e["text"] + " " + (e.get("context") or "")) for e in evidence] or [set()])
    best_about, best_ov = None, 0
    for s in job["about"]:
        ov = len(_terms(s) & cand_terms)
        if ov > best_ov:
            best_about, best_ov = s, ov
    interest = ({"reason": f"Their work on “{best_about[:140]}” connects to your own background; say what drew you to it.",
                 "basis": best_about} if best_about and best_ov >= 1
                else {"reason": f"Find one specific thing about {company or 'the company'} (a product, study or recent news) that links to your experience.",
                      "basis": None})
    missing = []
    for g in (fit or {}).get("gaps", []):
        if g.get("type") == "essential" and g.get("status") == "missing":
            missing.append(f"No evidence yet for “{g['point']}”. Address it briefly or show something adjacent.")
    pref_gap = next((g for g in (fit or {}).get("gaps", []) if g.get("type") == "preferred" and g.get("status") == "missing"), None)
    if pref_gap:
        missing.append(f"Nothing on “{pref_gap['point']}” (preferred). If you've touched it at all, mention it in one line.")
    if not highlight or not METRIC.search(highlight["text"]):
        missing.append("No quantified result relevant to this role. Pick one and give its scale or outcome.")
    for b in (fit or {}).get("blockers", []):
        if b["severity"] in ("high", "medium") and b["type"] in ("Work permit", "Language"):
            missing.append(f"{b['type']}: {b['detail']} Say how you'd handle it, in one sentence.")
    avoid = [{"phrase": p, "instead": i} for p, i in GENERIC_PHRASES[:6]]
    outline = [
        f"Opening: the role ({position or 'position'}) and your strongest link to it"
        + (f" ({conn['text'][:70]}…)." if conn else "."),
        "Why them: " + ("the connection in “Most credible reason”." if best_about else f"one specific thing about {company or 'them'}."),
        "Proof: your highlighted example, with its scale or result, tied to their top priority.",
        "Gap or logistics (only if needed): one honest sentence.",
        "Close: availability and what you'd like to discuss.",
    ]
    return {"method": "rules", "model": None, "priorities": job["priorities"],
            "connection": {"id": conn["id"], "text": conn["text"], "requirement": conn.get("matches"),
                           "why": "Your closest match to an essential requirement."} if conn else None,
            "interest": interest,
            "highlight": {"id": highlight["id"], "text": highlight["text"],
                          "why": "Concrete, with a result you can explain in two sentences."} if highlight else None,
            "missing": missing[:5], "avoid": avoid, "outline": outline}


# --------------------------------------------------------------------------- AI versions
def _evidence_list(top: list[dict]) -> tuple[str, dict[str, dict]]:
    ids = {f"E{i + 1}": e for i, e in enumerate(top)}
    lines = []
    for k, e in ids.items():
        where = e.get("context") or e.get("section") or ""
        extra = [f"role: {where[:70]}"] if where else []
        if e.get("metrics"):
            extra.append("numbers: " + ", ".join(e["metrics"][:3]))
        if e.get("note"):
            extra.append(f"candidate's note: {e['note'][:100]}")
        lines.append(f"{k} [{e.get('kind')}] {e['text'][:260]}" + (f" ({'; '.join(extra)})" if extra else ""))
    return "\n".join(lines), ids


def _rid(value, ids: dict[str, dict]) -> dict | None:
    """Resolve whatever the model returned ("E3", "e3", 3, "E3: Built…") to an evidence record."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return ids.get(f"E{int(value)}")
    for m in re.finditer(r"\b[Ee]\s?(\d+)\b|^(\d+)$", str(value).strip()):
        key = f"E{m.group(1) or m.group(2)}"
        if key in ids:
            return ids[key]
    # Last resort: the model quoted the text instead of the id.
    low = str(value).lower()[:80]
    for e in ids.values():
        if len(low) > 20 and low[:40] in e["text"].lower():
            return e
    return None


def _deref(text: str, ids: dict[str, dict]) -> str:
    """Replace stray E# references in free text with a short quote of the line."""
    return re.sub(r"\b[Ee](\d+)\b", lambda m: (f"“{ids[f'E{m.group(1)}']['text'][:60]}…”" if f"E{m.group(1)}" in ids
                                                 else m.group(0)), text or "").strip()


def _job_text(job: dict) -> str:
    parts = ["TOP PRIORITIES: " + " | ".join(job["priorities"][:5]),
             "ESSENTIAL: " + " | ".join(job["essential"][:8]), "PREFERRED: " + " | ".join(job["preferred"][:6]),
             "RESPONSIBILITIES: " + " | ".join(job["responsibilities"][:6]), "THEMES: " + ", ".join(job["themes"][:8])]
    return "\n".join(p for p in parts if not p.endswith(": "))


RULES = """Rules: refer to the candidate's lines only by their id (E1, E2...). Never invent facts about the candidate.
Be specific to THIS job and THIS candidate; generic advice ("add metrics", "be specific") is useless.
Keep every text field short: at most 35 words."""

CV_CONTEXT = """You are a senior recruiter screening a candidate for the job below. You see their CV lines (E#).
Judge every line against THIS job's priorities, not in general.
""" + RULES

CV_TASK_A = """Task 1 of 2.
- critique: the 3-4 lines you would push back on for this job. "issue" = what exactly you would doubt or find weak and
  why it matters for this job (unclear ownership, no result or scale, jargon the hiring manager won't value, vague
  scope, mismatch with a priority). "fix" = ONE concrete change written for that line, naming what to add or change.
  Good: {"e":"E3","issue":"'Supported the development of workflows' hides your part; an analytics team will want to
  know what you built and with which tools.","fix":"Say what you built (e.g. the Python pipeline merging three data
  types) and how much data it handled.","priority":"high"}
  Bad (too generic): {"issue":"No numbers","fix":"Add metrics"}
- reword: up to 2 lines that describe relevant work in the wrong vocabulary for this job; give the new wording, keeping
  only facts that are in the line."""

CV_TASK_B = """Task 2 of 2.
- emphasise: up to 3 lines that best prove fit; "why" = which priority it proves and why a recruiter would care.
- questions: up to 3 questions you would ask in a screening call given what's missing or unclear, each with
  "how_to_answer" = what the candidate should say, using their own lines.
- add_if_true: up to 3 things this job needs that the lines don't show, phrased as what to add IF it is true."""

CV_SCHEMA_A = {
    "type": "object",
    "properties": {
        "critique": {"type": "array", "items": {"type": "object", "properties": {
            "e": {"type": "string"}, "issue": {"type": "string"}, "fix": {"type": "string"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]}}, "required": ["e", "issue", "fix", "priority"]}},
        "reword": {"type": "array", "items": {"type": "object", "properties": {"e": {"type": "string"}, "suggestion": {"type": "string"}}, "required": ["e", "suggestion"]}},
    },
    "required": ["critique", "reword"],
}
CV_SCHEMA_B = {
    "type": "object",
    "properties": {
        "emphasise": {"type": "array", "items": {"type": "object", "properties": {"e": {"type": "string"}, "why": {"type": "string"}}, "required": ["e", "why"]}},
        "questions": {"type": "array", "items": {"type": "object", "properties": {"question": {"type": "string"}, "how_to_answer": {"type": "string"}}, "required": ["question", "how_to_answer"]}},
        "add_if_true": {"type": "array", "items": {"type": "object", "properties": {"what": {"type": "string"}, "why": {"type": "string"}}, "required": ["what", "why"]}},
    },
    "required": ["emphasise", "questions", "add_if_true"],
}

LETTER_CONTEXT = """You coach a candidate on what their cover letter for the job below should say. Do NOT write the letter.
Use the candidate's lines (E#) and the job text.
""" + RULES

LETTER_TASK_A = """Task 1 of 2.
- connection: the single strongest link between one of their lines and one of the job's top priorities: "e", the
  "requirement" it matches, and "why" a hiring manager would find it convincing and how to phrase the link.
- interest: the most credible reason THIS candidate would want THIS job, grounded in their background and a concrete
  detail of the role or employer (not flattery). "reason" = 2 sentences; "basis" = a short phrase quoted from the job text.
- highlight: the one example worth telling ("e") and "why", including which result or detail to make explicit."""

LETTER_TASK_B = """Task 2 of 2.
- missing: up to 3 things a hiring manager would notice are missing from the story, each with what to do about it.
- avoid: up to 3 generic sentences this candidate is likely to write for this job, each with a specific alternative
  that uses their own evidence.
- outline: 4-5 lines, paragraph by paragraph, saying what to cover and which evidence (E#) to use."""

LETTER_SCHEMA_A = {
    "type": "object",
    "properties": {
        "connection": {"type": "object", "properties": {"e": {"type": "string"}, "requirement": {"type": "string"}, "why": {"type": "string"}}, "required": ["e", "requirement", "why"]},
        "interest": {"type": "object", "properties": {"reason": {"type": "string"}, "basis": {"type": "string"}}, "required": ["reason", "basis"]},
        "highlight": {"type": "object", "properties": {"e": {"type": "string"}, "why": {"type": "string"}}, "required": ["e", "why"]},
    },
    "required": ["connection", "interest", "highlight"],
}
LETTER_SCHEMA_B = {
    "type": "object",
    "properties": {
        "missing": {"type": "array", "items": {"type": "string"}},
        "avoid": {"type": "array", "items": {"type": "object", "properties": {"phrase": {"type": "string"}, "instead": {"type": "string"}}, "required": ["phrase", "instead"]}},
        "outline": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["missing", "avoid", "outline"],
}

# Rough answer lengths, for progress bars and time estimates.
EXPECTED_TOKENS = {"cv": (430, 380), "letter": (330, 380)}
PREDICT = {"cv": (700, 600), "letter": (560, 600)}


def _style_text(style: dict | None) -> str:
    if not style:
        return ""
    bits = []
    if style.get("spelling"):
        bits.append(f"{style['spelling']} spelling")
    if style.get("tone"):
        bits.append(f"tone: {style['tone']}")
    if style.get("avoid"):
        bits.append(f"avoid: {style['avoid']}")
    out = "CANDIDATE PREFERENCES: " + "; ".join(bits) if bits else ""
    if style.get("samples"):
        out += f"\nHOW THE CANDIDATE WRITES (sample): {style['samples'][:600]}"
    return out


def _gaps_text(fit: dict | None) -> str:
    gaps = [g["point"] for g in (fit or {}).get("gaps", []) if g.get("status") == "missing"][:5]
    blocks = [f"{b['type']}: {b['detail']}" for b in (fit or {}).get("blockers", [])][:3]
    out = ""
    if gaps:
        out += "\nNOT SHOWN IN CV: " + " | ".join(gaps)
    if blocks:
        out += "\nPOSSIBLE BLOCKERS: " + " | ".join(blocks)
    return out



def _finish(base: dict, sections: dict, model: str, pending: set[str] | None = None, failed: str | None = None) -> dict:
    """Merge AI sections over the rule-based ones, recording where each section came from."""
    out, sources = {**base}, {}
    for k, v in sections.items():
        if k in (pending or set()):
            sources[k] = "pending"
        elif v:
            out[k], sources[k] = v, "ai"
        else:
            sources[k] = "rules"
    used_ai = any(v == "ai" for v in sources.values())
    note = None
    if failed:
        note = f"The second part of the AI review failed ({failed}); those sections show rule-based findings."
    elif pending:
        note = None
    elif not used_ai:
        note = "The model's answer couldn't be matched to your CV lines, so rule-based findings are shown."
    elif not all(v == "ai" for v in sources.values()):
        note = "Some sections came back empty from the model and show rule-based findings instead (marked 'rules')."
    out.update(method="ollama" if used_ai else "rules", model=model if used_ai else None, sources=sources, ai_note=note,
               in_progress=bool(pending))
    return out


def _run_parts(context: str, tasks: list[tuple[str, dict, int, int, str]], client: Ollama, progress=None,
               on_part=None) -> tuple[list[dict], str | None]:
    """Run the task prompts in order against one shared context (Ollama reuses the processed context)."""
    raws, failed = [], None
    for i, (task, schema, predict, expected, label) in enumerate(tasks):
        if progress:
            progress.step(label, i + 1, len(tasks), expected)
        try:
            raws.append(client.chat_json(context, task, schema, temperature=0.3, num_predict=predict))
        except LLMError as e:
            if i == 0:
                raise
            raws.append({})
            failed = str(e)
            break
        if on_part and i < len(tasks) - 1:
            on_part(raws)
    while len(raws) < len(tasks):
        raws.append({})
    return raws, failed


def cv_builder_ai(evidence: list[dict], job: dict, fit: dict | None, cv_text: str, client: Ollama, style: dict | None = None,
                  progress=None, on_partial=None) -> dict:
    base = cv_builder_rules(evidence, job, fit, cv_text)  # cut + keywords stay rule-based
    top = rank_evidence([e for e in evidence if e.get("kind") in AI_KINDS], job, k=12)
    listing, ids = _evidence_list(top)
    context = f"{CV_CONTEXT}\n\nJOB\n{_job_text(job)}{_gaps_text(fit)}\n\nCANDIDATE CV LINES\n{listing}\n{_style_text(style)}"

    def res(items, *keys):
        out = []
        for x in items or []:
            e = _rid(x.get("e"), ids) if isinstance(x, dict) else None
            if e:
                out.append({"id": e["id"], "text": e["text"], **{k: _deref(str(x.get(k, "")), ids) for k in keys}})
        return out

    def part_a(raw):
        critique = [c for c in res(raw.get("critique"), "issue", "fix", "priority") if c["issue"] and c["fix"]][:4]
        for c in critique:
            c["priority"] = c["priority"] if c["priority"] in ("high", "medium", "low") else "medium"
        return {"critique": critique, "reword": res(raw.get("reword"), "suggestion")[:3]}

    def part_b(raw):
        return {
            "emphasise": res(raw.get("emphasise"), "why")[:4],
            "questions": [{"question": _deref(q.get("question", ""), ids), "how_to_answer": _deref(q.get("how_to_answer", ""), ids)}
                          for q in raw.get("questions", []) if isinstance(q, dict) and q.get("question")][:4],
            "add_if_true": [{"what": _deref(a.get("what", ""), ids), "why": _deref(a.get("why", ""), ids)}
                            for a in raw.get("add_if_true", []) if isinstance(a, dict) and a.get("what")][:4],
        }
    b_keys = {"emphasise", "questions", "add_if_true"}
    exp, pred = EXPECTED_TOKENS["cv"], PREDICT["cv"]
    raws, failed = _run_parts(context, [(CV_TASK_A, CV_SCHEMA_A, pred[0], exp[0], "Critique and rewording"),
                                        (CV_TASK_B, CV_SCHEMA_B, pred[1], exp[1], "What to emphasise, questions, gaps")],
                              client, progress,
                              on_part=(lambda rs: on_partial(_finish(base, {**part_a(rs[0]), **{k: None for k in b_keys}},
                                                                     client.model, pending=b_keys))) if on_partial else None)
    return _finish(base, {**part_a(raws[0]), **part_b(raws[1])}, client.model, failed=failed)


def letter_builder_ai(evidence: list[dict], job: dict, fit: dict | None, client: Ollama, company: str, position: str,
                      style: dict | None = None, progress=None, on_partial=None) -> dict:
    base = letter_builder_rules(evidence, job, fit, company, position)
    top = rank_evidence([e for e in evidence if e.get("kind") in AI_KINDS], job, k=12)
    listing, ids = _evidence_list(top)
    about = " ".join(job["about"][:4])
    context = (f"{LETTER_CONTEXT}\n\nJOB: {position} at {company}\n{_job_text(job)}{_gaps_text(fit)}\n"
               f"ABOUT THE EMPLOYER / ROLE: {about[:900]}\n\nCANDIDATE CV LINES\n{listing}\n{_style_text(style)}")

    def pick(obj, *keys):
        if not isinstance(obj, dict):
            return None
        e = _rid(obj.get("e"), ids)
        if not e:
            return None
        return {"id": e["id"], "text": e["text"], **{k: _deref(str(obj.get(k, "")), ids) for k in keys}}

    def part_a(raw):
        interest = None
        if isinstance(raw.get("interest"), dict) and raw["interest"].get("reason"):
            basis = raw["interest"].get("basis") or ""
            jd_words = set(re.findall(r"[a-z]{4,}", " ".join(job["about"] + job["responsibilities"] + job["priorities"]).lower()))
            grounded = len(set(re.findall(r"[a-z]{4,}", basis.lower())) & jd_words) >= 2
            interest = {"reason": _deref(raw["interest"]["reason"], ids), "basis": basis if grounded else None}
        return {"connection": pick(raw.get("connection"), "requirement", "why"), "interest": interest,
                "highlight": pick(raw.get("highlight"), "why")}

    def part_b(raw):
        return {
            "missing": [_deref(m, ids) for m in raw.get("missing", []) if isinstance(m, str) and m][:4],
            "avoid": [{"phrase": a.get("phrase", ""), "instead": _deref(a.get("instead", ""), ids)}
                      for a in raw.get("avoid", []) if isinstance(a, dict) and a.get("phrase")][:4],
            "outline": [_deref(o, ids) for o in raw.get("outline", []) if isinstance(o, str) and o][:6],
        }
    b_keys = {"missing", "avoid", "outline"}
    exp, pred = EXPECTED_TOKENS["letter"], PREDICT["letter"]
    raws, failed = _run_parts(context, [(LETTER_TASK_A, LETTER_SCHEMA_A, pred[0], exp[0], "Connection, interest, highlight"),
                                        (LETTER_TASK_B, LETTER_SCHEMA_B, pred[1], exp[1], "Gaps, phrases to avoid, structure")],
                              client, progress,
                              on_part=(lambda rs: on_partial(_finish(base, {**part_a(rs[0]), **{k: None for k in b_keys}},
                                                                     client.model, pending=b_keys))) if on_partial else None)
    return _finish(base, {**part_a(raws[0]), **part_b(raws[1])}, client.model, failed=failed)


# --------------------------------------------------------------------------- brief for a chatbot
def brief(kind: str, result: dict, job: dict, company: str, position: str, style: dict | None = None) -> str:
    """A ready-to-paste prompt so any chat assistant can write the final CV or letter from these findings."""
    L = [f"Help me write my {'CV for' if kind == 'cv' else 'cover letter for'} the {position} role at {company}.",
         "Use only facts from my experience below; ask me before adding anything new.", "",
         "What the role prioritises:"] + [f"- {p}" for p in job["priorities"]]
    if kind == "cv":
        if result.get("emphasise"):
            L += ["", "Lead with these lines from my CV:"] + [f"- {e['text']}" for e in result["emphasise"]]
        if result.get("critique"):
            L += ["", "Fix these weaknesses:"] + [f"- \"{c['text']}\": {c['issue']} Fix: {c['fix']}" for c in result["critique"]]
        if result.get("reword"):
            L += ["", "Reword:"] + [f"- \"{r['text']}\" -> {r['suggestion']}" for r in result["reword"]]
        if result.get("keywords"):
            L += ["", "Use these terms where accurate: " + ", ".join(result["keywords"] + result.get("missing_keywords", []))]
    else:
        if result.get("connection"):
            L += ["", f"Strongest link: {result['connection']['text']} ({result['connection'].get('why', '')})"]
        if result.get("interest"):
            L += [f"Why I'm interested: {result['interest']['reason']}"]
        if result.get("highlight"):
            L += [f"Example to highlight: {result['highlight']['text']}"]
        if result.get("missing"):
            L += ["", "Address briefly:"] + [f"- {m}" for m in result["missing"]]
        if result.get("avoid"):
            L += ["", "Avoid generic lines like:"] + [f"- \"{a['phrase']}\" ({a['instead']})" for a in result["avoid"]]
        if result.get("outline"):
            L += ["", "Structure:"] + [f"{i + 1}. {o}" for i, o in enumerate(result["outline"])]
    st = _style_text(style)
    if st:
        L += ["", st]
    return "\n".join(L)
