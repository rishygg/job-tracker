"""CV-vs-job fit analysis.

Two engines produce the same result shape:
  * "keywords": deterministic rules (always available, no AI) - extracts requirements from the job
    description, splits them into essential vs preferred, and finds the closest line in your CV.
  * "ollama": a local language model does the reading; its output is then checked against your CV so
    it can't invent evidence, and combined with the same rule-based blockers.

The score and recommendation are always computed here from the requirement statuses and blockers, so
both engines are judged the same way.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .cvtext import chunks as cv_chunks
from .dimensions import DimensionInferer
from .llm import Ollama

ESSENTIAL_HEADERS = [
    "requirements", "qualifications", "what you bring", "what we're looking for", "what we are looking for",
    "who you are", "your profile", "your background", "must have", "must-have", "required", "minimum qualifications",
    "basic qualifications", "essential", "skills and experience", "experience and skills", "about you", "your skills",
    "you have", "you bring", "you will need", "what you need", "key requirements", "candidate profile",
    "dein profil", "ihr profil", "anforderungen", "was du mitbringst", "was sie mitbringen", "profil", "votre profil",
    "you will bring", "what you will bring", "you'll bring", "what you'll bring", "your experience", "skills & experience",
    "skills and qualifications", "technical skills", "technical tools", "tools", "who we're looking for",
    "who we are looking for", "the ideal candidate", "ideal candidate", "minimum requirements", "your qualifications",
]
PREFERRED_HEADERS = [
    "preferred", "nice to have", "nice-to-have", "bonus", "desirable", "preferred qualifications", "ideally",
    "would be great", "plus", "additional qualifications", "it would be great if", "wünschenswert", "von vorteil",
]
OTHER_HEADERS = [
    "responsibilities", "what you'll do", "what you will do", "your tasks", "your role", "the role", "about us",
    "about the role", "benefits", "we offer", "what we offer", "why join", "about the company", "your responsibilities",
    "key responsibilities", "tasks", "aufgaben", "deine aufgaben", "ihre aufgaben", "wir bieten", "our offer",
    "how to apply", "location", "the team", "who we are", "job description", "overview", "mission",
    "our values", "values", "what we stand for", "our culture", "culture", "life at", "why us", "perks",
]
PREFERRED_CUES = re.compile(
    r"\b(a plus|is a plus|plus\b|nice to have|nice-to-have|preferred|preferably|desirable|desired|advantage|"
    r"advantageous|ideally|bonus|beneficial|would be great|welcome|von vorteil|wünschenswert|an asset|is helpful|"
    r"helpful|optional)\b", re.I)
ESSENTIAL_CUES = re.compile(
    r"\b(must|required|requirement|essential|minimum|mandatory|need to|necessary|proven|solid|strong|fluent|fluency|"
    r"degree in|degree|at least|\d+\+?\s*(?:years?|yrs)|experience (?:in|with)|knowledge of|proficien\w*|"
    r"expertise|you have|you bring|background in|qualification)\b", re.I)
BULLET = re.compile(r"^\s*(?:[•▪◦●○■□➢►▶–—\-*·✓✔]|\d+[.)])\s*")
# Lines about the contract, pay, benefits or how to apply are not requirements.
JUNK = re.compile(r"\b(fixed[- ]term|contract role|permanent role|salary|compensation|benefits|bonus scheme|we offer|"
                  r"how to apply|apply now|equal opportunit\w*|diversity|closing date|start date|full[- ]time|part[- ]time|"
                  r"\d+\s*%\s*(?:workload|pensum)|pensum|hybrid working|home office)\b", re.I)
ELIGIBILITY = re.compile(r"\b(work permit|right to work|eligible to work|visa|sponsorship|eu/efta|eu or efta|"
                         r"arbeitsbewilligung|is based in|located in|based at|relocat\w*|on-site in|onsite in)\b", re.I)

STOP = set("""a an and are as at be by for from has have in into is it its of on or our the their this to was will with
you your we us they them who what which that than then also such any all both each per via within across able ability
strong good excellent solid proven experience experienced knowledge skills skill understanding working work team teams
plus preferred ideally required must have having well using use including include etc other relevant related similar
field area areas level demonstrated hands environment role position candidate looking least years year minimum
advantage desirable nice great bonus would like being can new high based more least must""".split())

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"]
DEGREES = ["None", "Bachelor", "Master (in progress)", "Master", "PhD (in progress)", "PhD"]
PERMIT_STATUSES = ["Citizen / no permit needed", "Have a valid work permit", "Eligible for a permit (e.g. graduate route)",
                   "Would need sponsorship"]
ACTIONS = ["Apply", "Apply with caveats", "Deprioritise"]


def text_hash(*parts: str | None) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w+#&/.\- ]", " ", s.lower())).strip()


def _stem(w: str) -> str:
    for suf in ("ings", "ing", "ers", "er", "ies", "es", "ed", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _terms(s: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-zäöüß0-9+#]{3,}", s.lower()) if w not in STOP}


# --------------------------------------------------------------------------- requirements
def _header_kind(line: str) -> str | None:
    if BULLET.match(line) and not line.strip().startswith("#"):
        return None
    t = line.strip().strip(":").strip("*#_ ").lower()
    if len(t) > 60 or not t:
        return None
    strong = line.rstrip().endswith(":") or line.strip().isupper() or line.strip().startswith(("#", "**"))
    if not (strong or len(t.split()) <= 6):
        return None
    if not strong and (PREFERRED_CUES.search(t) and len(t.split()) > 3):
        return None
    for h in PREFERRED_HEADERS:
        if t == h or t.startswith(h):
            return "preferred"
    for h in ESSENTIAL_HEADERS:
        if t == h or t.startswith(h) or (strong and h in t and len(t.split()) <= 5):
            return "essential"
    for h in OTHER_HEADERS:
        if t == h or t.startswith(h) or (strong and h in t and len(t.split()) <= 5):
            return "other"
    return None


def extract_requirements(jd: str, limit: int = 22) -> list[dict]:
    """Requirement lines from a job description, each marked essential or preferred."""
    lines = [ln for ln in (jd or "").replace("\r", "").split("\n")]
    reqs: list[dict] = []
    section: str | None = None
    saw_section = False
    for raw in lines:
        if not raw.strip():
            continue
        kind = _header_kind(raw)
        if kind:
            section, saw_section = kind, True
            # "Requirements: Python, SQL" - header with content on the same line.
            rest = raw.split(":", 1)[1].strip() if ":" in raw else ""
            if not rest:
                continue
            raw = rest
        text = BULLET.sub("", raw).strip()
        for sent in re.split(r"(?<=[.;])\s+(?=[A-Z])", text):
            s = sent.strip(" .;")
            if not (12 <= len(s) <= 320):
                continue
            pref, ess = bool(PREFERRED_CUES.search(s)), bool(ESSENTIAL_CUES.search(s))
            if section == "other":
                continue
            if section in ("essential", "preferred"):
                kind = "preferred" if (section == "preferred" or pref) else "essential"
            elif not saw_section or section is None:
                if not (pref or ess):
                    continue
                kind = "preferred" if pref else "essential"
            else:
                continue
            if ELIGIBILITY.search(s) or JUNK.search(s):
                continue  # permits/location are blockers; contract and pay lines aren't requirements
            if s.rstrip().endswith(":"):
                continue  # an unrecognised sub-heading ("Technical tools mentioned:")
            reqs.append({"text": s, "type": kind})
    # De-duplicate, keep order.
    seen, out = set(), []
    for r in reqs:
        k = _norm(r["text"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out[:limit]


# --------------------------------------------------------------------------- profile checks
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs)", re.I)
PHD_RE = re.compile(r"\b(ph\.?\s?d|doctorate|doctoral degree)\b", re.I)
MASTER_RE = re.compile(r"\b(master'?s?|msc|m\.sc|ma\b|mphil|graduate degree)\b", re.I)
BACHELOR_RE = re.compile(r"\b(bachelor'?s?|bsc|b\.sc|undergraduate degree|university degree)\b", re.I)
LANG_NAMES = ["german", "french", "italian", "spanish", "english", "dutch", "portuguese", "mandarin", "chinese",
              "japanese", "hindi", "polish", "danish", "swedish", "norwegian"]
LANG_NEED = re.compile(r"\b(fluent|fluency|native|business[- ]fluent|excellent|proficient|proficiency|c1|c2|"
                       r"verhandlungssicher|fließend|fliessend|courant|full professional)\b", re.I)


def _level_index(level: str | None) -> int:
    try:
        return LEVELS.index(level) if level else -1
    except ValueError:
        return -1


def _profile_level(profile: dict, language: str) -> str | None:
    for item in profile.get("languages", []) or []:
        if str(item.get("language", "")).strip().lower() == language.lower():
            return item.get("level")
    return None


def special_check(req: str, profile: dict) -> dict | None:
    """Rule-based status for requirements about languages, degrees or years of experience."""
    low = req.lower()
    # Languages
    for lang in LANG_NAMES:
        if re.search(rf"\b{lang}\b", low):
            have = _profile_level(profile, lang)
            needs_fluent = bool(LANG_NEED.search(req))
            need_idx = LEVELS.index("C1") if needs_fluent else LEVELS.index("B1")
            have_idx = _level_index(have)
            if not profile.get("languages"):
                return None
            if have_idx >= need_idx:
                return {"status": "met", "evidence": f"Profile: {lang.title()} {have}", "kind": "language"}
            if have_idx >= 0:
                return {"status": "partial", "evidence": f"Profile: {lang.title()} {have}", "kind": "language",
                        "note": f"Asks for {'fluent ' if needs_fluent else ''}{lang.title()}; you have {have}."}
            return {"status": "missing", "evidence": None, "kind": "language",
                    "note": f"{lang.title()} isn't in your profile languages."}
    # Degrees
    degree = profile.get("degree") or ""
    d_idx = DEGREES.index(degree) if degree in DEGREES else -1
    has_phd, has_master, has_bachelor = bool(PHD_RE.search(req)), bool(MASTER_RE.search(req)), bool(BACHELOR_RE.search(req))
    if has_phd or has_master or has_bachelor:
        if not degree or not re.search(r"degree|phd|ph\.d|doctor|master|msc|bachelor|bsc|graduate", low):
            return None
        # "MSc or PhD" -> the lowest degree mentioned is what's needed.
        need = "Bachelor" if has_bachelor else "Master" if has_master else "PhD"
        need_idx = DEGREES.index(need)
        if d_idx >= need_idx:
            return {"status": "met", "evidence": f"Profile: {degree}", "kind": "degree"}
        if degree.endswith("(in progress)") and DEGREES.index(degree.replace(" (in progress)", "")) >= need_idx:
            return {"status": "partial", "evidence": f"Profile: {degree}", "kind": "degree",
                    "note": f"Your {degree.replace(' (in progress)', '')} is in progress; check whether they accept graduates-to-be."}
        return {"status": "missing", "evidence": f"Profile: {degree}", "kind": "degree", "note": f"Asks for a {need} degree."}
    # Years of experience
    m = YEARS_RE.search(req)
    if m and "experience" in low and profile.get("years_experience") not in (None, ""):
        need, have = int(m.group(1)), float(profile.get("years_experience") or 0)
        if have >= need:
            return {"status": "met", "evidence": f"Profile: {have:g} years of experience", "kind": "years"}
        status = "partial" if have >= need - 1 or have >= need * 0.6 else "missing"
        return {"status": status, "evidence": f"Profile: {have:g} years of experience", "kind": "years",
                "note": f"Asks for {need}+ years; you have {have:g}."}
    return None


# --------------------------------------------------------------------------- matching
@dataclass
class Matcher:
    cv: str
    inferer: DimensionInferer
    pieces: list[dict] = field(init=False)

    def __post_init__(self):
        self.pieces = cv_chunks(self.cv)
        for p in self.pieces:
            p["terms"] = _terms(p["text"])
            p["skills"] = {t.lower() for t in self.inferer.analyse_jd(p["text"]).skills}
        self.cv_norm = _norm(self.cv)

    def best(self, req: str) -> tuple[float, dict | None]:
        rterms = _terms(req)
        rskills = {t.lower() for t in self.inferer.analyse_jd(req).skills}
        weight = sum(3 if any(t in s for s in rskills) else 1 for t in rterms) + 2 * len(rskills)
        if not weight:
            return 0.0, None
        best_score, best_piece = 0.0, None
        for p in self.pieces:
            score = 3 * len(rskills & p["skills"]) + len(rterms & p["terms"])
            # Skills mentioned anywhere in the CV count a little even outside this piece.
            score += 0.5 * sum(1 for s in rskills - p["skills"] if s in self.cv_norm)
            s = score / weight
            if s > best_score:
                best_score, best_piece = s, p
        return min(best_score, 1.0), best_piece

    def verify(self, quote: str | None) -> tuple[bool, str | None]:
        """Is this quote really in the CV? Returns (verified, the CV text it matches)."""
        if not quote or len(quote.strip()) < 8:
            return False, None
        q = _norm(quote)
        if q and q in self.cv_norm:
            return True, quote.strip()
        qt = _terms(quote)
        if not qt:
            return False, None
        best, piece = 0.0, None
        for p in self.pieces:
            if not p["terms"]:
                continue
            ov = len(qt & p["terms"]) / len(qt)
            if ov > best:
                best, piece = ov, p
        return (best >= 0.7), (piece["text"] if piece and best >= 0.7 else None)


def status_from_score(s: float) -> str:
    return "met" if s >= 0.5 else "partial" if s >= 0.25 else "missing"


# --------------------------------------------------------------------------- blockers
def blockers(jd: str, profile: dict, inferer: DimensionInferer, region: str | None, reqs: list[dict]) -> list[dict]:
    out: list[dict] = []
    a = inferer.analyse_jd(jd)
    # Language
    if a.language in ("German required", "French required"):
        lang = a.language.split()[0]
        lvl = _profile_level(profile, lang)
        if _level_index(lvl) < LEVELS.index("C1"):
            out.append({"type": "Language", "severity": "high",
                        "detail": f"{lang} is required" + (f"; your profile says {lvl}." if lvl else "; it isn't in your profile.")
                        + (" The posting is written in German." if a.written_in_german else "")})
    elif a.language == "German a plus":
        lvl = _profile_level(profile, "German")
        if _level_index(lvl) < LEVELS.index("B1"):
            out.append({"type": "Language", "severity": "low", "detail": f"German is a plus; you have {lvl or 'none listed'}."})
    # Work permit
    permits = profile.get("permits") or {}
    status = permits.get(region or "", "") if region else ""
    if a.work_authorization == "Requires existing permit / EU-EFTA":
        if status == "Would need sponsorship":
            out.append({"type": "Work permit", "severity": "high",
                        "detail": f"The posting asks for an existing work permit or EU/EFTA status; for {region} you'd need sponsorship."})
        elif status.startswith("Eligible"):
            out.append({"type": "Work permit", "severity": "medium",
                        "detail": f"Asks for an existing permit; you're eligible for one in {region}. Mention it in your application."})
        elif not status:
            out.append({"type": "Work permit", "severity": "medium",
                        "detail": "Asks for an existing work permit or EU/EFTA status. Set your permit status per location in Settings to check this."})
    elif status == "Would need sponsorship" and a.work_authorization != "Sponsorship offered":
        out.append({"type": "Work permit", "severity": "medium",
                    "detail": f"You'd need sponsorship in {region} and the posting doesn't say it offers it."})
    # Location
    prefs = profile.get("locations") or []
    if prefs and region and region not in prefs and region not in ("Remote", "Other / unspecified") and not profile.get("relocate"):
        out.append({"type": "Location", "severity": "medium", "detail": f"{region} isn't one of your preferred locations."})
    # Hard requirements found missing (degree / years / languages) that are essential.
    for r in reqs:
        if r["type"] == "essential" and r.get("kind") in ("degree", "years") and r["status"] == "missing":
            out.append({"type": "Eligibility" if r["kind"] == "degree" else "Experience", "severity": "high" if r["kind"] == "degree" else "medium",
                        "detail": r.get("note") or r["text"]})
    # De-duplicate by type+detail.
    seen, uniq = set(), []
    for b in out:
        k = (b["type"], b["detail"])
        if k not in seen:
            seen.add(k)
            uniq.append(b)
    return uniq


# --------------------------------------------------------------------------- scoring
def score(reqs: list[dict]) -> float | None:
    if not reqs:
        return None
    val = {"met": 1.0, "partial": 0.5, "missing": 0.0}
    tot = sum((2 if r["type"] == "essential" else 1) for r in reqs)
    got = sum((2 if r["type"] == "essential" else 1) * val.get(r["status"], 0) for r in reqs)
    return got / tot if tot else None


def recommend(fit: float | None, block: list[dict], reqs: list[dict]) -> dict:
    high = [b for b in block if b["severity"] == "high"]
    medium = [b for b in block if b["severity"] == "medium"]
    ess = [r for r in reqs if r["type"] == "essential"]
    ess_missing = [r for r in ess if r["status"] == "missing"]
    if fit is None:
        return {"action": "Apply with caveats", "why": "Couldn't find clear requirements in this posting, so there's nothing to score against."}
    if high:
        if fit >= 0.75 and len(high) == 1 and high[0]["type"] in ("Work permit", "Language"):
            return {"action": "Apply with caveats", "why": f"Strong match ({fit:.0%}), but {high[0]['detail'][0].lower() + high[0]['detail'][1:]}"}
        return {"action": "Deprioritise", "why": f"{high[0]['detail']} That's usually a hard filter."}
    if fit >= 0.7 and len(ess_missing) <= 1 and not medium:
        return {"action": "Apply", "why": f"You meet most essential requirements ({fit:.0%} overall)."}
    if fit >= 0.45:
        reason = medium[0]["detail"] if medium else (f"{len(ess_missing)} essential requirement(s) not shown in your CV." if ess_missing else "Several requirements are only partly covered.")
        return {"action": "Apply with caveats", "why": f"Reasonable match ({fit:.0%}). {reason}"}
    return {"action": "Deprioritise", "why": f"Low match ({fit:.0%}): {len(ess_missing)} of {len(ess)} essential requirements aren't covered by your CV."}


def _summarise(reqs: list[dict]) -> tuple[list[dict], list[dict]]:
    strengths = [{"point": r["text"], "evidence": r.get("evidence"), "type": r["type"]}
                 for r in reqs if r["status"] == "met"]
    gaps = [{"point": r["text"], "severity": ("high" if r["status"] == "missing" else "medium") if r["type"] == "essential" else "low",
             "note": r.get("note"), "type": r["type"], "status": r["status"]}
            for r in reqs if r["status"] != "met"]
    order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: order[g["severity"]])
    return strengths, gaps


# --------------------------------------------------------------------------- engines
def analyse_keywords(cv: str, jd: str, profile: dict, inferer: DimensionInferer, region: str | None = None) -> dict:
    m = Matcher(cv, inferer)
    reqs = []
    for r in extract_requirements(jd):
        special = special_check(r["text"], profile)
        if special:
            reqs.append({**r, **special})
            continue
        s, piece = m.best(r["text"])
        reqs.append({**r, "status": status_from_score(s), "evidence": piece["text"] if piece and s >= 0.25 else None,
                     "evidence_section": piece["section"] if piece and s >= 0.25 else None, "match": round(s, 2),
                     "evidence_verified": bool(piece and s >= 0.25)})
    return _finish(reqs, jd, profile, inferer, region, method="keywords", model=None)


SYSTEM_FIT = """You are a meticulous career advisor. Compare the candidate's CV with the job description.
Rules:
- List the job's requirements (skills, experience, education, languages, eligibility). Mark each "essential" if the
  posting presents it as required (must, required, minimum, in a requirements section) and "preferred" if it is
  described as a plus, nice to have, preferred, desirable or ideally.
- For each requirement give status "met", "partial" or "missing" based ONLY on the CV and profile.
- "evidence" must be an exact quote copied from the CV (a phrase or bullet) that supports the status, or "" if none.
  Never invent or paraphrase evidence.
- Be honest about gaps. Do not assume skills that aren't written in the CV.
- Keep requirement texts short (under 20 words)."""

FIT_SCHEMA = {
    "type": "object",
    "properties": {
        "requirements": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "type": {"type": "string", "enum": ["essential", "preferred"]},
            "status": {"type": "string", "enum": ["met", "partial", "missing"]},
            "evidence": {"type": "string"}, "note": {"type": "string"}},
            "required": ["text", "type", "status", "evidence"]}},
        "summary": {"type": "string"},
    },
    "required": ["requirements", "summary"],
}


def _profile_text(profile: dict) -> str:
    langs = ", ".join(f"{l.get('language')} {l.get('level')}" for l in profile.get("languages", []) or [] if l.get("language"))
    permits = "; ".join(f"{k}: {v}" for k, v in (profile.get("permits") or {}).items() if v)
    return (f"Languages: {langs or 'not given'}\nHighest degree: {profile.get('degree') or 'not given'}\n"
            f"Years of relevant experience: {profile.get('years_experience', 'not given')}\nWork permits: {permits or 'not given'}")


COMPACT_SYSTEM = """You compare a CV with job requirements. Answer ONLY with ids from the lists given.
For each requirement R#: status "met" (the CV clearly shows it), "partial" (related but weaker) or "missing";
"type" essential or preferred (keep the given type unless the wording clearly says otherwise);
"cv" = up to 2 CV line ids C# that prove it ([] if missing). Never guess beyond what the CV says."""

COMPACT_SCHEMA = {
    "type": "object",
    "properties": {
        "r": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "status": {"type": "string", "enum": ["met", "partial", "missing"]},
            "type": {"type": "string", "enum": ["essential", "preferred"]},
            "cv": {"type": "array", "items": {"type": "string"}}}, "required": ["id", "status", "cv"]}},
        "summary": {"type": "string"},
    },
    "required": ["r", "summary"],
}


def _numbered_cv(m: "Matcher", limit: int = 70) -> tuple[str, dict[str, dict]]:
    pieces = m.pieces[:limit]
    ids = {f"C{i + 1}": p for i, p in enumerate(pieces)}
    return "\n".join(f"{k}: {p['text'][:220]}" for k, p in ids.items()), ids


def analyse_llm(cv: str, jd: str, profile: dict, inferer: DimensionInferer, client: Ollama, region: str | None = None) -> dict:
    """Fast AI analysis: the app extracts and numbers requirements and CV lines; the model only answers
    with statuses and line ids. Short output = fast, and evidence can only point at real CV lines."""
    reqs = extract_requirements(jd)
    if len(reqs) < 3:
        return analyse_llm_full(cv, jd, profile, inferer, client, region)
    m = Matcher(cv, inferer)
    cv_list, cv_ids = _numbered_cv(m)
    final: list[dict] = []
    ask: list[tuple[str, dict]] = []
    for i, r in enumerate(reqs):
        special = special_check(r["text"], profile)
        if special:
            final.append({**r, **special})
        else:
            ask.append((f"R{i + 1}", r))
    raw: dict = {"r": [], "summary": ""}
    if ask:
        req_list = "\n".join(f"{rid} [{r['type']}]: {r['text']}" for rid, r in ask)
        user = f"REQUIREMENTS\n{req_list}\n\nCV LINES\n{cv_list}\n\nAlso give a one-sentence summary of the fit."
        raw = client.chat_json(COMPACT_SYSTEM, user, COMPACT_SCHEMA, num_predict=60 + 40 * len(ask))
    answers = {str(x.get("id", "")).strip().upper(): x for x in raw.get("r", [])}
    for rid, r in ask:
        a = answers.get(rid)
        if not a:  # model skipped it: fall back to keyword matching for this one
            sc, piece = m.best(r["text"])
            final.append({**r, "status": status_from_score(sc), "evidence": piece["text"] if piece and sc >= 0.25 else None,
                          "evidence_verified": bool(piece and sc >= 0.25)})
            continue
        pieces = [cv_ids[c.strip().upper()] for c in a.get("cv", []) if c.strip().upper() in cv_ids]
        status = a.get("status") if a.get("status") in ("met", "partial", "missing") else "missing"
        if status in ("met", "partial") and not pieces:
            status = "partial" if status == "met" else "missing"
        final.append({**r, "type": a.get("type") if a.get("type") in ("essential", "preferred") else r["type"],
                      "status": status, "evidence": pieces[0]["text"] if pieces else None,
                      "evidence_section": pieces[0]["section"] if pieces else None, "evidence_verified": bool(pieces)})
    order = {_norm(r["text"]): i for i, r in enumerate(reqs)}
    final.sort(key=lambda r: order.get(_norm(r["text"]), 99))
    res = _finish(final, jd, profile, inferer, region, method="ollama", model=client.model)
    if raw.get("summary"):
        res["summary"] = raw["summary"]
    return res


def analyse_llm_full(cv: str, jd: str, profile: dict, inferer: DimensionInferer, client: Ollama, region: str | None = None) -> dict:
    """Slower path for postings without a clear requirements list: the model extracts them itself."""
    user = (f"CANDIDATE PROFILE\n{_profile_text(profile)}\n\nCANDIDATE CV\n{cv[:9000]}\n\nJOB DESCRIPTION\n{jd[:6000]}\n\n"
            "Return the requirements and a two-sentence summary of the fit.")
    raw = client.chat_json(SYSTEM_FIT, user, FIT_SCHEMA, num_predict=1500)
    m = Matcher(cv, inferer)
    reqs = []
    for r in (raw.get("requirements") or [])[:25]:
        text = str(r.get("text", "")).strip()
        if not text:
            continue
        typ = r.get("type") if r.get("type") in ("essential", "preferred") else "essential"
        status = r.get("status") if r.get("status") in ("met", "partial", "missing") else "missing"
        special = special_check(text, profile)
        if special:
            reqs.append({"text": text, "type": typ, **special})
            continue
        ok, matched = m.verify(r.get("evidence"))
        item = {"text": text, "type": typ, "status": status, "note": r.get("note") or None,
                "evidence": matched or (r.get("evidence") or None), "evidence_verified": ok}
        if status == "met" and not ok:
            item["status"] = "partial"
            item["note"] = "The model's evidence couldn't be found in your CV, so this is marked as partial."
        reqs.append(item)
    res = _finish(reqs, jd, profile, inferer, region, method="ollama", model=client.model)
    res["summary"] = raw.get("summary") or res.get("summary")
    return res


def _finish(reqs: list[dict], jd: str, profile: dict, inferer: DimensionInferer, region: str | None,
            method: str, model: str | None) -> dict:
    block = blockers(jd, profile, inferer, region, reqs)
    fit = score(reqs)
    rec = recommend(fit, block, reqs)
    strengths, gaps = _summarise(reqs)
    ess = [r for r in reqs if r["type"] == "essential"]
    pref = [r for r in reqs if r["type"] == "preferred"]
    summary = (f"Meets {sum(r['status'] == 'met' for r in ess)} of {len(ess)} essential and "
               f"{sum(r['status'] == 'met' for r in pref)} of {len(pref)} preferred requirements.")
    return {"method": method, "model": model, "score": fit, "recommendation": rec, "requirements": reqs,
            "strengths": strengths, "gaps": gaps, "blockers": block, "summary": summary,
            "counts": {"essential": len(ess), "preferred": len(pref),
                       "essential_met": sum(r["status"] == "met" for r in ess),
                       "preferred_met": sum(r["status"] == "met" for r in pref)}}


# --------------------------------------------------------------------------- target CV & cover letter
SYSTEM_TARGET = """You help a candidate tailor their own CV to one job. Write the strongest HONEST version of their CV
for this job. Every bullet must be tagged:
- "backed": a rewording of something in the CV. "source" must be the exact CV text it comes from.
- "partial": related experience exists in the CV but the bullet stretches it; "source" is the closest CV text and
  "note" says what the candidate must confirm or add.
- "gap": something the employer wants that the CV does not show. Phrase it as what the employer wants to see
  (e.g. "Evidence of leading a cross-functional project"), never as a claim. "source" is "".
Never fabricate employers, dates, numbers, degrees or achievements. Use the job's vocabulary where truthful."""

TARGET_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "sections": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"},
            "bullets": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"}, "support": {"type": "string", "enum": ["backed", "partial", "gap"]},
                "source": {"type": "string"}, "addresses": {"type": "string"}, "note": {"type": "string"}},
                "required": ["text", "support", "source"]}}},
            "required": ["title", "bullets"]}},
        "skills": {"type": "array", "items": {"type": "object", "properties": {
            "skill": {"type": "string"}, "support": {"type": "string", "enum": ["backed", "gap"]}},
            "required": ["skill", "support"]}},
        "advice": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "summary", "sections", "skills", "advice"],
}

SYSTEM_LETTER = """Write a concise, specific cover letter (250-350 words) for the candidate, using ONLY facts from
their CV. Split it into paragraphs. Tag each paragraph "backed" if every claim comes from the CV, or "partial" if it
needs the candidate to fill in or confirm details (use [square brackets] for placeholders). List the exact CV text
each paragraph relies on in "sources". Do not invent achievements, numbers or motivations; where motivation is
needed, leave a [placeholder] for the candidate's own reason."""

LETTER_SCHEMA = {
    "type": "object",
    "properties": {
        "greeting": {"type": "string"},
        "paragraphs": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "support": {"type": "string", "enum": ["backed", "partial"]},
            "sources": {"type": "array", "items": {"type": "string"}}}, "required": ["text", "support", "sources"]}},
        "closing": {"type": "string"},
    },
    "required": ["greeting", "paragraphs", "closing"],
}


def target_cv_llm(cv: str, jd: str, fit: dict | None, inferer: DimensionInferer, client: Ollama,
                  position: str = "", company: str = "") -> dict:
    gaps = "; ".join(g["point"] for g in (fit or {}).get("gaps", [])[:8])
    user = (f"JOB: {position} at {company}\n\nJOB DESCRIPTION\n{jd[:7000]}\n\nCANDIDATE CV\n{cv[:12000]}\n\n"
            f"Known gaps: {gaps or 'none listed'}\n\nWrite the target CV.")
    raw = client.chat_json(SYSTEM_TARGET, user, TARGET_SCHEMA, temperature=0.3)
    m = Matcher(cv, inferer)
    for sec in raw.get("sections", []):
        for b in sec.get("bullets", []):
            if b.get("support") in ("backed", "partial"):
                ok, matched = m.verify(b.get("source"))
                b["source_verified"] = ok
                if matched:
                    b["source"] = matched
                if b["support"] == "backed" and not ok:
                    b["support"] = "partial"
                    b["note"] = (b.get("note") or "") + " The source line couldn't be found in your CV; check this before using it."
            else:
                b["source"] = ""
    cv_low = cv.lower()
    for s in raw.get("skills", []):
        if s.get("support") == "backed" and s.get("skill", "").lower() not in cv_low:
            s["support"] = "gap"
    return {"method": "ollama", "model": client.model, **raw}


def cover_letter_llm(cv: str, jd: str, inferer: DimensionInferer, client: Ollama, position: str = "", company: str = "") -> dict:
    user = f"JOB: {position} at {company}\n\nJOB DESCRIPTION\n{jd[:7000]}\n\nCANDIDATE CV\n{cv[:12000]}"
    raw = client.chat_json(SYSTEM_LETTER, user, LETTER_SCHEMA, temperature=0.4)
    m = Matcher(cv, inferer)
    for p in raw.get("paragraphs", []):
        checked = [m.verify(s) for s in p.get("sources", [])]
        p["sources_verified"] = sum(ok for ok, _ in checked)
        if p.get("support") == "backed" and (not checked or not all(ok for ok, _ in checked)):
            p["support"] = "partial"
    return {"method": "ollama", "model": client.model, **raw}


def tailoring_guide(cv: str, jd: str, fit: dict, inferer: DimensionInferer) -> dict:
    """No-AI version of the target CV: which of your lines to lead with, and what's missing."""
    m = Matcher(cv, inferer)
    sections = []
    lead = []
    for r in fit.get("requirements", []):
        if r["status"] in ("met", "partial") and r.get("evidence") and not str(r["evidence"]).startswith("Profile:"):
            lead.append({"text": r["evidence"], "support": "backed" if r["status"] == "met" else "partial",
                         "source": r["evidence"], "addresses": r["text"],
                         "note": None if r["status"] == "met" else "Related, but rephrase to match the requirement more directly."})
    seen, uniq = set(), []
    for b in lead:
        if b["text"] not in seen:
            seen.add(b["text"])
            uniq.append(b)
    if uniq:
        sections.append({"title": "Lead with these lines from your CV", "bullets": uniq[:10]})
    gaps = [{"text": g["point"], "support": "gap", "source": "", "addresses": g["point"], "note": g.get("note")}
            for g in fit.get("gaps", []) if g["status"] == "missing"]
    if gaps:
        sections.append({"title": "What they want to see that your CV doesn't show", "bullets": gaps[:10]})
    jd_skills = inferer.analyse_jd(jd).skills
    cv_skills = {s.lower() for s in inferer.analyse_jd(cv).skills}
    skills = [{"skill": s, "support": "backed" if s.lower() in cv_skills else "gap"} for s in jd_skills]
    return {"method": "keywords", "model": None, "headline": "", "summary": "",
            "sections": sections, "skills": skills,
            "advice": ["Move the lines above to the top of the relevant role or section.",
                       "Use the job's own words for skills you really have (see the skills list).",
                       "Install Ollama to get a fully rewritten target CV and a draft cover letter."]}


# --------------------------------------------------------------------------- CV suggestions (fast)
TIPS_SYSTEM = """You advise a candidate how to adapt THEIR OWN CV for one job. Use only the ids given.
- emphasise: CV lines (C#) that best match the job; say briefly why and which requirement they show.
- reword: CV lines worth rephrasing with the job's vocabulary; give the suggested wording, keeping the facts.
- cut: CV lines least relevant to this job that could be shortened or moved down.
- add: things the job wants that the CV doesn't show. Phrase as what to add IF TRUE, never as a claim.
- keywords: job terms the candidate should mirror where truthful.
Be brief: at most 5 items per list, each "why" under 15 words."""

TIPS_SCHEMA = {
    "type": "object",
    "properties": {
        "emphasise": {"type": "array", "items": {"type": "object", "properties": {"cv": {"type": "string"}, "why": {"type": "string"}}, "required": ["cv", "why"]}},
        "reword": {"type": "array", "items": {"type": "object", "properties": {"cv": {"type": "string"}, "suggestion": {"type": "string"}}, "required": ["cv", "suggestion"]}},
        "cut": {"type": "array", "items": {"type": "object", "properties": {"cv": {"type": "string"}, "why": {"type": "string"}}, "required": ["cv", "why"]}},
        "add": {"type": "array", "items": {"type": "object", "properties": {"what": {"type": "string"}, "why": {"type": "string"}}, "required": ["what", "why"]}},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["emphasise", "reword", "cut", "add", "keywords"],
}


def cv_tips_keywords(cv: str, jd: str, fit: dict, inferer: DimensionInferer) -> dict:
    """Instant CV suggestions from the fit analysis: what to lead with, what to add if true, what to trim."""
    m = Matcher(cv, inferer)
    used = set()
    emphasise = []
    for r in fit.get("requirements", []):
        ev = r.get("evidence")
        if r["status"] in ("met", "partial") and ev and not str(ev).startswith("Profile:") and ev not in used:
            used.add(ev)
            emphasise.append({"text": ev, "why": f"Shows: {r['text']}"})
    add = [{"what": g["point"], "why": "Essential requirement your CV doesn't show." if g["type"] == "essential"
            else "Preferred, would strengthen your application."}
           for g in fit.get("gaps", []) if g.get("status") == "missing"][:6]
    # Lines that match nothing in the job are candidates to shorten.
    req_terms = set().union(*[_terms(r["text"]) for r in fit.get("requirements", [])] or [set()]) | _terms(jd[:4000])
    scored = [(len(p["terms"] & req_terms) / max(1, len(p["terms"])), p) for p in m.pieces
              if p["text"] not in used and len(p["terms"]) >= 4 and p["section"].lower() not in ("education", "languages", "skills")]
    cut = [{"text": p["text"], "why": "Little overlap with this job; shorten or move down."}
           for sc, p in sorted(scored, key=lambda x: x[0])[:4] if sc < 0.1]
    jd_skills = inferer.analyse_jd(jd).skills
    cv_low = cv.lower()
    keywords = [s for s in jd_skills if s.lower() in cv_low]
    missing_kw = [s for s in jd_skills if s.lower() not in cv_low]
    return {"method": "keywords", "model": None, "emphasise": emphasise[:6], "reword": [], "cut": cut, "add": add,
            "keywords": keywords, "missing_keywords": missing_kw}


def cv_tips_llm(cv: str, jd: str, fit: dict | None, inferer: DimensionInferer, client: Ollama) -> dict:
    m = Matcher(cv, inferer)
    cv_list, cv_ids = _numbered_cv(m)
    reqs = "\n".join(f"- [{r['type']}] {r['text']}" for r in (fit or {}).get("requirements", [])[:15]) or jd[:3000]
    raw = client.chat_json(TIPS_SYSTEM, f"JOB REQUIREMENTS\n{reqs}\n\nCV LINES\n{cv_list}", TIPS_SCHEMA,
                           temperature=0.3, num_predict=700)

    def resolve(items, key):
        out = []
        for x in items or []:
            p = cv_ids.get(str(x.get("cv", "")).strip().upper())
            if p:
                out.append({"text": p["text"], key: x.get(key, "")})
        return out[:5]
    cv_low = cv.lower()
    kws = [k for k in raw.get("keywords", [])][:12]
    return {"method": "ollama", "model": client.model,
            "emphasise": resolve(raw.get("emphasise"), "why"), "reword": resolve(raw.get("reword"), "suggestion"),
            "cut": resolve(raw.get("cut"), "why"), "add": [a for a in raw.get("add", [])][:5],
            "keywords": [k for k in kws if k.lower() in cv_low],
            "missing_keywords": [k for k in kws if k.lower() not in cv_low]}
