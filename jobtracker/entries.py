"""Your profile as entries (education, experience, projects, publications, skills) instead of a CV file.

Entries are the source of truth: each bullet becomes an evidence line for matching, and a plain CV text is assembled
from them when a prompt for a chat assistant needs one. A pasted section can be split into draft entries, and an
existing CV can be converted once so nothing has to be retyped.
"""

from __future__ import annotations

import re

from .cvtext import BULLET
from .dimensions import DimensionInferer
from .evidence import COURSEWORK, PERSONAL, classify, metrics, stakeholders
from .evidence import extract as extract_evidence

SECTIONS = {
    "experience": "Experience", "education": "Education", "projects": "Projects", "publications": "Publications",
    "skills": "Skills", "other": "Other",
}
SECTION_OF = [  # CV heading -> entry section
    ("education", r"education|academic|qualification|degree|studies|ausbildung"),
    ("publications", r"publication|presentation|poster|conference|paper"),
    ("projects", r"project"),
    ("skills", r"skill|tool|technolog|language|competenc|software|kenntnisse"),
    ("experience", r"experience|employment|work|research|internship|career|position|professional|leadership|volunteer|"
                   r"extracurricular|activities|berufserfahrung"),
]
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE = rf"(?:{MONTH}\s*'?\d{{2,4}}|(?:19|20)\d{{2}}|\d{{1,2}}/(?:19|20)?\d{{2}})"
RANGE = re.compile(rf"({DATE})\s*(?:[–—-]|to|bis)\s*({DATE}|present|now|current|today|heute)", re.I)


def section_for(heading: str) -> str:
    h = (heading or "").lower()
    for sec, pat in SECTION_OF:
        if re.search(pat, h):
            return sec
    return "other"


def parse_header(line: str) -> dict:
    """'Research Assistant, Neuroeconomics Group, UZH  Mar 2025 – Present' -> title, org, dates, location."""
    text = line.strip()
    start = end = None
    m = RANGE.search(text)
    if m:
        start, end = m.group(1).strip(), m.group(2).strip()
        text = (text[:m.start()] + " " + text[m.end():]).strip(" ,|–-")
    else:
        y = re.search(rf"\b({DATE})\s*$", text)
        if y:
            end = y.group(1)
            text = text[:y.start()].strip(" ,|–-")
    parts = [p.strip() for p in re.split(r"\s+[|–—]\s+|\s+-\s+|,\s+|\s+at\s+|\s*@\s*", text) if p.strip()]
    title = parts[0] if parts else text
    org = parts[1] if len(parts) > 1 else None
    location = ", ".join(parts[2:]) if len(parts) > 2 else None
    return {"title": title[:140], "org": (org or "")[:140] or None, "location": (location or "")[:80] or None,
            "start": start, "end": end}


def _is_header_line(line: str, nxt: str) -> bool:
    if BULLET.match(line):
        return False
    if RANGE.search(line) and len(line) <= 160:
        return True
    return bool(nxt) and bool(BULLET.match(nxt)) and len(line) <= 120 and not line.endswith(".")


def split_text(section: str, text: str) -> list[dict]:
    """Split a pasted block (one CV section) into draft entries for the person to tidy."""
    lines = [ln.rstrip() for ln in (text or "").replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln.strip() and not PERSONAL.search(ln)]
    if section == "skills":
        items = [s.strip(" •-–") for ln in lines for s in re.split(r"[,;•|]", ln.split(":", 1)[-1] if ":" in ln else ln)]
        return [{"section": "skills", "title": "Skills", "details": ", ".join(i for i in items if i)}] if lines else []
    out: list[dict] = []
    cur: dict | None = None
    for i, ln in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        # PDF damage: two date ranges glued onto one line ("Feb 2025 - Apr 2025 May 2023 - Aug 2023Research…").
        ranges = list(RANGE.finditer(ln))
        if len(ranges) >= 2 and not BULLET.match(ln):
            tail = ln[ranges[-1].end():].strip()
            for r in ranges[:-1]:
                out.append({"section": section, **parse_header(ln[r.start():r.end()] + " " + tail), "details": ""})
            ln = ln[ranges[-1].start():]
        if _is_header_line(ln, nxt) or cur is None:
            if cur is not None or not BULLET.match(ln):
                cur = {"section": section, **parse_header(BULLET.sub("", ln)), "details": ""}
                out.append(cur)
                continue
            cur = {"section": section, "title": "", "org": None, "location": None, "start": None, "end": None, "details": ""}
            out.append(cur)
        cur["details"] = (cur["details"] + "\n" if cur["details"] else "") + BULLET.sub("", ln).strip()
    for e in out:
        e["details"] = e.get("details", "").strip()
    return [e for e in out if e.get("title") or e.get("details")]


def from_cv(cv: str, inferer: DimensionInferer) -> list[dict]:
    """Convert a CV once into entries, grouped by role, dropping contact details."""
    recs = extract_evidence(cv, inferer)
    groups: dict[tuple, dict] = {}
    order: list[tuple] = []
    for r in recs:
        if r["kind"] == "personal" or r.get("duplicate_of"):
            continue
        sec = section_for(r.get("section") or "")
        if r["kind"] == "skill":
            sec = "skills"
        ctx = r.get("context") or ""
        key = (sec, ctx if sec != "skills" else "")
        if key not in groups:
            head = parse_header(ctx) if ctx else {"title": "", "org": None, "location": None, "start": None, "end": None}
            if sec == "skills":
                head["title"] = "Skills"
            groups[key] = {"section": sec, **head, "details": []}
            order.append(key)
        text = r["text"]
        if COURSEWORK.search(text) and sec == "education":
            text = "Relevant modules: " + re.sub(r"^.*?(modules?|courses?)[^:]*:\s*", "", text, flags=re.I)
        groups[key]["details"].append(text)
    out = []
    for k in order:
        g = groups[k]
        if g["section"] == "education" and not g["title"] and g["details"]:
            g.update({x: v for x, v in parse_header(g["details"][0]).items() if v})
            g["details"] = g["details"][1:]
        title = (g.get("title") or "").lower()
        g["details"] = "\n".join(d for d in dict.fromkeys(g["details"]) if not (title and d.lower().startswith(title)))
        out.append(g)
    return out


def to_text(entries: list[dict]) -> str:
    """Plain CV text from entries (for matching and for prompts)."""
    lines: list[str] = []
    for sec, label in SECTIONS.items():
        items = [e for e in entries if e.get("section") == sec]
        if not items:
            continue
        lines += ["", label.upper()]
        for e in items:
            head = ", ".join(x for x in (e.get("title"), e.get("org"), e.get("location")) if x)
            dates = " – ".join(x for x in (e.get("start"), e.get("end")) if x)
            if head or dates:
                lines.append(f"{head}  {dates}".strip())
            for d in (e.get("details") or "").split("\n"):
                if d.strip():
                    lines.append(d.strip() if sec == "skills" else f"- {d.strip()}")
    return "\n".join(lines).strip()


def evidence(entries: list[dict], inferer: DimensionInferer) -> list[dict]:
    """One evidence record per bullet, with the entry as its context."""
    out = []
    for e in entries:
        sec = e.get("section") or "other"
        ctx = ", ".join(x for x in (e.get("title"), e.get("org")) if x)
        bullets = [d.strip() for d in (e.get("details") or "").split("\n") if d.strip()]
        if sec == "education" and ctx:
            bullets = [ctx] + bullets
        if sec == "skills":
            bullets = [", ".join(bullets)] if bullets else []
        for b in bullets:
            kind = "skill" if sec == "skills" else classify(SECTIONS.get(sec, "Other"), b)
            if kind == "personal":
                continue
            out.append({"section": SECTIONS.get(sec, "Other"), "context": ctx, "text": b, "kind": kind,
                        "metrics": metrics(b), "skills": inferer.analyse_jd(b).skills, "stakeholders": stakeholders(b),
                        "industry": inferer.industry(e.get("org"), b), "entry_id": e.get("id")})
    return out
