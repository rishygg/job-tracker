"""What a job prioritises, and which of your evidence is most relevant to it.

Used by interview preparation and the stories/practice suggestions. (The CV and cover-letter writing itself is left to
your chat assistant: the app builds the prompt.)
"""

from __future__ import annotations

import re
from collections import Counter

from .dimensions import DimensionInferer
from .fit import JUNK, STOP, _header_kind, _terms, extract_requirements

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
