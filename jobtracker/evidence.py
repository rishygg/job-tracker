"""Evidence bank: the CV turned into structured, reusable records (done once per CV).

Each record keeps the original wording plus what can be read from it: the kind of record
(achievement, responsibility, qualification...), the role/organisation it belongs to, metrics,
tools/skills, stakeholders and industry. The person can confirm records, add a note about what
they actually did, hide records or add evidence that isn't on the CV.
"""

from __future__ import annotations

import re

from .cvtext import BULLET, SECTION_WORDS
from .dimensions import DimensionInferer

# Bump when extraction improves; existing evidence banks are rebuilt automatically (edits are kept).
EXTRACTOR_VERSION = 2

KIND_BY_SECTION = {
    "education": "qualification", "certifications": "qualification", "courses": "qualification",
    "skills": "skill", "technical skills": "skill", "languages": "skill",
    "publications": "publication", "presentations": "publication",
    "projects": "project", "awards": "achievement", "summary": "summary", "profile": "summary",
}
RESULT_VERBS = re.compile(
    r"\b(increas\w*|reduc\w*|cut|cutting|improv\w*|launch\w*|built|build|develop\w*|publish\w*|won|award\w*|deliver\w*|"
    r"sav\w*|grew|grow\w*|led|lead|design\w*|automat\w*|creat\w*|present\w*|establish\w*|introduc\w*|"
    r"achiev\w*|exceed\w*|accelerat\w*|optimi[sz]\w*|streamlin\w*|secur\w*|initiat\w*|implement\w*)\b", re.I)
WEAK_STARTS = re.compile(r"^(responsible for|assisted( with| in)?|helped( to)?|worked on|involved in|participated in|"
                         r"tasked with|duties included|supported|exposure to|familiar with)\b", re.I)
METRIC = re.compile(
    r"(?<![\w.])(?:\d{1,3}(?:[,.]\d{3})+|\d+(?:\.\d+)?)\s*(?:%|percent|x\b|×|k\b|m\b|million|billion|chf|eur|usd|\$|"
    r"participants|patients|subjects|users|samples|sites|countries|people|members|students|hours|days|weeks|months|"
    r"datasets|scans|studies|papers|publications|clients|projects|conferences|teams?)|[$€£]\s?\d[\d,.]*\w*", re.I)
STAKEHOLDERS = {
    "cross-functional": "cross-functional teams", "sales": "sales", "medical": "medical teams", "marketing": "marketing",
    "clinicians": "clinicians", "physicians": "physicians", "patients": "patients", "investigators": "investigators",
    "sites": "trial sites", "regulators": "regulators", "clients": "clients", "customers": "customers",
    "stakeholders": "stakeholders", "management": "management", "senior leadership": "senior leadership",
    "researchers": "researchers", "pi": "principal investigator", "supervisor": "supervisor", "students": "students",
    "vendors": "vendors", "partners": "partners", "engineers": "engineers", "kols": "KOLs", "kol": "KOLs",
}
YEAR = re.compile(r"\b(19|20)\d{2}\b")
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE_RANGE = re.compile(rf"\b{MONTH}\s*'?\d{{2,4}}\s*[–—-]\s*(?:{MONTH}\s*'?\d{{2,4}}|present|now|current|today)\b"
                        r"|\b(?:19|20)\d{2}\s*[–—-]\s*(?:(?:19|20)\d{2}|present|now)\b", re.I)
# Contact details, nationality, permits, date of birth: not evidence, never sent to the model.
PERSONAL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|linkedin\.com|\+\d{2}[\d\s]{7,}|\b(address|phone|e-?mail|nationality|"
                      r"date of birth|d\.o\.b|permit|citizenship|marital|github\.com)\b|\b\d{2}\.\d{2}\.(?:19|20)\d{2}\b", re.I)
COURSEWORK = re.compile(r"\b(relevant )?(modules?|coursework|courses taken|relevant courses)\b", re.I)
# A role/organisation heading glued onto the end of a bullet by PDF extraction.
TRAILING_HEADING = re.compile(r"(?<=[).])\s+([A-Z][^.]{8,}\b(University|Department|Institute|Group|Lab|Laboratory|"
                              r"Hospital|Centre|Center|AG|GmbH|Ltd|Inc|Company|School|College)\b[^.]*)$")


def _is_header(line: str) -> str | None:
    bare = line.rstrip(":").strip().lower()
    if bare in SECTION_WORDS or (line.isupper() and 3 <= len(line) <= 40 and len(line.split()) <= 4):
        return line.rstrip(":").strip().title()
    return None


def _looks_like_role(line: str) -> bool:
    words = line.split()
    return len(words) <= 16 and (bool(YEAR.search(line)) or (", " in line and not line.endswith(".")))


def metrics(text: str) -> list[str]:
    found = [m.group(0).strip() for m in METRIC.finditer(text)]
    return [f for f in found if not YEAR.fullmatch(f.strip())][:5]


def stakeholders(text: str) -> list[str]:
    low = text.lower()
    out = []
    for k, v in STAKEHOLDERS.items():
        if re.search(rf"\b{re.escape(k)}\b", low) and v not in out:
            out.append(v)
    return out


def classify(section: str, text: str) -> str:
    if PERSONAL.search(text):
        return "personal"
    if COURSEWORK.search(text[:60]):
        return "coursework"
    s = section.lower()
    for key, kind in KIND_BY_SECTION.items():
        if key in s:
            return kind
    if metrics(text) or (RESULT_VERBS.search(text[:60]) and not WEAK_STARTS.search(text)):
        return "achievement"
    return "responsibility"


def clean_piece(text: str) -> str:
    """Undo common PDF-extraction damage: a date range or the next role's heading glued onto a bullet."""
    t = text.strip(" ;")
    m = DATE_RANGE.search(t)
    if m and m.start() > 25 and not PERSONAL.search(t):
        t = t[:m.start()].strip(" ;,–-")  # what follows the date range is the next role's heading
    t = TRAILING_HEADING.sub("", t).strip(" ;,")
    return t


def extract(cv: str, inferer: DimensionInferer) -> list[dict]:
    """Split a CV into evidence records with their section and role context."""
    records: list[dict] = []
    section, context = "Other", ""
    buf: list[str] = []
    pending_line: str | None = None

    def flush():
        if not buf:
            return
        text = " ".join(buf).strip(" ;")
        buf.clear()
        for sent in re.split(r"(?<=[.;])\s+(?=[A-Z])", text):
            sent = clean_piece(sent)
            if len(sent) < 15:
                continue
            kind = classify(section, sent)
            records.append({
                "section": section, "context": context, "text": sent, "kind": kind, "hidden": kind == "personal",
                "metrics": metrics(sent), "skills": inferer.analyse_jd(sent).skills, "stakeholders": stakeholders(sent),
                "industry": inferer.industry(context or None, sent),
            })

    lines = [ln.strip() for ln in cv.replace("\r", "").split("\n")]
    for i, line in enumerate(lines):
        if not line:
            flush()
            continue
        h = _is_header(line)
        if h:
            flush()
            section, context = h, ""
            continue
        nxt = next((ln for ln in lines[i + 1:] if ln), "")
        if BULLET.match(line):
            flush()
            buf.append(BULLET.sub("", line))
        elif (_looks_like_role(line) and (not buf or YEAR.search(line))
              and (BULLET.match(nxt) or section.lower() in ("education", "certifications"))):
            flush()
            context = line
            if section.lower() in ("education", "certifications"):
                buf.append(line)  # a degree line is evidence in itself
                flush()
        else:
            buf.append(line)
    flush()
    # Drop very short fragments; mark near-duplicates (same bullet pasted twice with small edits).
    out: list[dict] = []
    for r in records:
        if len(r["text"].split()) < 4 and r["kind"] not in ("skill", "qualification"):
            continue
        words = set(re.findall(r"[a-z]{3,}", r["text"].lower()))
        for prev in out:
            pw = set(re.findall(r"[a-z]{3,}", prev["text"].lower()))
            if words and pw and len(words & pw) / len(words | pw) >= 0.7:
                r["duplicate_of"] = prev["text"][:80]
                break
        out.append(r)
    return out
