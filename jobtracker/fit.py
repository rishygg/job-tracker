"""Profile-vs-job fit, from rules only (no AI).

Requirements are extracted from the job description (page clutter, benefits and company text removed), split
into essential and preferred, and each is matched to the closest line in your profile entries. Eligibility
blockers (language, permits, degree, years) come from your Me page. Every verdict can be traced to a line.
German postings get the eligibility check only; rank those with your chat assistant.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .cvtext import chunks as cv_chunks
from .dimensions import DimensionInferer

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
# Headings that start a section about the employer, benefits or process: the requirements section is over.
SECTION_END = re.compile(
    r"^\s*(some reasons to join|reasons to join|why (join|work (with|for|at))|join us|we offer|what we offer|our offer|"
    r"what('s| is) in it for you|benefits|perks|our (commitments?|promise|values|culture|benefits|mission|story)|"
    r"about (us|the company|the team)|life at |working at |learn more|how to apply|application process|next steps|"
    r"equal opportunit|diversity|wir bieten|unser angebot|(deine|ihre) vorteile|über uns|nous offrons|"
    r"pourquoi nous rejoindre|the (company|employer)|who we are|our team|meet the team)", re.I)
SOFT = re.compile(
    r"\b(team ?spirit|teamwork|team player|collaborat\w*|communication|interpersonal|proactiv\w*|autonom\w*|"
    r"self[- ]starter|self[- ]motivated|motivated|curious|curiosity|detail[- ]oriented|attention to detail|organi[sz]ed|"
    r"flexib\w*|adaptab\w*|influencing|negotiation|results?[- ]oriented|passion\w*|positive attitude|can-do|"
    r"independently|work autonomously|problem[- ]solving|eager to learn|willingness to learn|hands-on mentality|"
    r"teamfähig\w*|kommunikationsstark|selbstständig\w*|eigeninitiative|belastbar\w*|zuverlässig\w*)\b", re.I)
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


def _is_soft(text: str) -> bool:
    """Mostly about attitude or soft skills: keywords can't verify it from a CV."""
    if not SOFT.search(text):
        return False
    hard = _terms(SOFT.sub(" ", text)) - {"abil", "skill", "demonstrat", "excellent", "exceptional", "proven", "high",
                                          "level", "strong", "good", "very", "work", "part", "able", "and", "both"}
    return len(hard) <= 3


def _near_dup(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.7


def extract_requirements(jd: str, limit: int = 24) -> list[dict]:
    """Requirement lines from a job description, each marked essential or preferred (and soft if it's about attitude)."""
    from .posting import clean
    text_all, _ = clean(jd or "")
    lines = text_all.split("\n")
    reqs: list[dict] = []
    section: str | None = None
    saw_section = False
    for raw in lines:
        if not raw.strip():
            continue
        stripped = BULLET.sub("", raw).strip()
        if SECTION_END.match(stripped) and len(stripped) <= 70:
            section, saw_section = "other", True
            continue
        kind = _header_kind(raw)
        if not kind:  # "Requirements: Degree level…; …" - a heading with content on the same line
            m = re.match(r"^([\w' &/-]{3,40}):\s+(\S.+)$", stripped)
            if m and (k2 := _header_kind(m.group(1) + ":")):
                kind, raw = k2, m.group(1) + ": " + m.group(2)
        if kind:
            section, saw_section = kind, True
            # "Requirements: Python, SQL" - header with content on the same line.
            rest = raw.split(":", 1)[1].strip() if ":" in raw else ""
            if not rest:
                continue
            raw = rest
        text = BULLET.sub("", raw).strip()
        # A summary line listing several requirements separated by semicolons: treat each part separately.
        summary = text.count(";") >= 2
        parts = [p for p in re.split(r";\s*", text) if p.strip()] if summary else [text]
        for part in parts:
            for sent in re.split(r"(?<=[.;])\s+(?=[A-Z])", part):
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
                reqs.append({"text": s[0].upper() + s[1:], "type": kind, "soft": _is_soft(s), "summary": summary})
    # De-duplicate (also near-duplicates, e.g. a site summary repeating the bullets), keep the fuller wording.
    out: list[dict] = []
    for r in reqs:
        t = _terms(r["text"])
        dup = next((o for o in out if _near_dup(t, _terms(o["text"]))), None)
        if dup is None:
            out.append(r)
        elif dup["summary"] and not r["summary"]:
            dup.clear()
            dup.update(r)  # the posting's own bullet beats the summary line that repeats it
        elif len(r["text"]) > len(dup["text"]) and r["type"] == dup["type"] and r["summary"] == dup["summary"]:
            dup.update(r)
    # Final pass: drop a short line that another, fuller requirement already covers ("Microsoft Office").
    terms = [_terms(r["text"]) for r in out]
    keep = [r for i, r in enumerate(out)
            if not any(j != i and len(out[j]["text"]) > len(r["text"]) and _near_dup(terms[i], terms[j]) for j in range(len(out)))]
    for r in keep:
        r.pop("summary", None)
    return keep[:limit]


# --------------------------------------------------------------------------- profile checks
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs)", re.I)
PHD_RE = re.compile(r"\b(ph\.?\s?d|doctorate|doctoral degree)\b", re.I)
MASTER_RE = re.compile(r"\b(master'?s?|msc|m\.sc|ma\b|mphil|graduate degree)\b", re.I)
BACHELOR_RE = re.compile(r"\b(bachelor'?s?|bsc|b\.sc|undergraduate degree|university degree|degree level|educated to degree|"
                         r"degree or equivalent|degree \(or equivalent\)|university education|higher education|"
                         r"hochschulabschluss|studium)\b", re.I)
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
        reason = medium[0]["detail"] if medium else (f"{len(ess_missing)} essential requirement(s) not shown in your profile." if ess_missing else "Several requirements are only partly covered.")
        return {"action": "Apply with caveats", "why": f"Reasonable match ({fit:.0%}). {reason}"}
    return {"action": "Deprioritise", "why": f"Low match ({fit:.0%}): {len(ess_missing)} of {len(ess)} essential requirements aren't covered by your profile."}


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
GERMAN_NOTE = ("This posting is in German. Keyword rules can't compare German text with an English profile reliably, "
               "so there's no score. The eligibility checks still apply; rank it with your chat assistant.")


def analyse_keywords(cv: str, jd: str, profile: dict, inferer: DimensionInferer, region: str | None = None) -> dict:
    from .posting import language
    if language(jd) == "de":
        block = blockers(jd, profile, inferer, region, [])
        high = [b for b in block if b["severity"] == "high"]
        return {"method": "keywords", "model": None, "score": None, "requirements": [], "soft_skills": [], "strengths": [],
                "gaps": [], "blockers": block, "counts": {"essential": 0, "essential_met": 0, "preferred": 0, "preferred_met": 0},
                "posting_language": "de", "note": GERMAN_NOTE,
                "recommendation": {"action": "Deprioritise" if high else "Not scored",
                                   "why": ("; ".join(b["detail"] for b in high) if high else GERMAN_NOTE)},
                "summary": None}
    m = Matcher(cv, inferer)
    reqs, soft = [], []
    for r in extract_requirements(jd):
        if r.get("soft") and not special_check(r["text"], profile):
            soft.append(r)
            continue
        special = special_check(r["text"], profile)
        if special:
            reqs.append({**r, **special})
            continue
        s, piece = m.best(r["text"])
        reqs.append({**r, "status": status_from_score(s), "evidence": piece["text"] if piece and s >= 0.25 else None,
                     "evidence_section": piece["section"] if piece and s >= 0.25 else None, "match": round(s, 2),
                     "evidence_verified": bool(piece and s >= 0.25)})
    res = _finish(reqs, jd, profile, inferer, region, method="keywords", model=None)
    res["soft_skills"] = [r["text"] for r in soft]
    res["posting_language"] = "en"
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
