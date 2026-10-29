"""Prompts for a chat assistant (ChatGPT, Claude…) and reading its answers back.

The tracker does the bookkeeping: it collects your profile and clean job descriptions into one well-structured prompt.
The assistant does the thinking. For rankings, its reply is pasted back and recorded against each job.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .posting import clean

MAX_JD = 3500  # characters per job description in a batch prompt
PART_JOBS = 30       # most jobs in one prompt: the reply (a JSON object per job) has to fit in one answer
PART_CHARS = 100_000  # most characters of job text in one prompt (about 25k tokens)
RANKING_YAML = Path(__file__).resolve().parent.parent / "config" / "ranking.yaml"
CORE = ("score", "verdict", "reason", "missing")
TYPES = ("number", "choice", "text")


def ranking_config(text: str | None = None, path: Path = RANKING_YAML) -> dict:
    """The extra ranking fields from config/ranking.yaml, checked. Raises ValueError with a readable message."""
    raw = yaml.safe_load(text if text is not None else (path.read_text(encoding="utf-8") if path.exists() else "")) or {}
    if not isinstance(raw, dict):
        raise ValueError("the file should contain 'default_criteria' and 'fields'")
    fields, seen = [], set()
    for i, f in enumerate(raw.get("fields") or []):
        if not isinstance(f, dict) or not f.get("key"):
            raise ValueError(f"field {i + 1} needs a 'key'")
        key = str(f["key"]).strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", key):
            raise ValueError(f"'{key}': keys use letters, numbers and underscores only")
        if key in CORE or key in seen:
            raise ValueError(f"'{key}' is built in or used twice")
        typ = str(f.get("type") or "text")
        if typ not in TYPES:
            raise ValueError(f"'{key}': type must be number, choice or text")
        if typ == "choice" and not f.get("options"):
            raise ValueError(f"'{key}': a choice needs 'options'")
        seen.add(key)
        fields.append({"key": key, "label": str(f.get("label") or key.replace("_", " ").capitalize()), "type": typ,
                       "min": f.get("min"), "max": f.get("max"), "suffix": str(f.get("suffix") or ""),
                       "options": [str(o) for o in f.get("options") or []], "ask": str(f.get("ask") or f.get("label") or key),
                       "show": "card" if f.get("show") == "card" else "detail"})
    return {"default_criteria": str(raw.get("default_criteria") or "").strip(), "fields": fields}


def _jd(text: str, limit: int = MAX_JD) -> str:
    t, _ = clean(text or "")
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t if len(t) <= limit else t[:limit].rsplit("\n", 1)[0] + "\n[…shortened]"


def _eligibility(profile: dict) -> str:
    bits = []
    langs = ", ".join(f"{l.get('language')} {l.get('level')}" for l in profile.get("languages", []) if l.get("language"))
    if langs:
        bits.append(f"Languages: {langs}")
    if profile.get("degree"):
        bits.append(f"Highest degree: {profile['degree']}")
    if profile.get("years_experience") not in (None, ""):
        bits.append(f"Years of relevant experience: {profile['years_experience']}")
    permits = "; ".join(f"{k}: {v}" for k, v in (profile.get("permits") or {}).items() if v)
    if permits:
        bits.append(f"Work permits: {permits}")
    if profile.get("locations"):
        bits.append("Preferred locations: " + ", ".join(profile["locations"]))
    return "\n".join(bits)


def code(kind: str, ref_id: int) -> str:
    """Stable job codes used in prompts and replies: A12 = application 12, S7 = saved job 7."""
    return f"{'A' if kind == 'application' else 'S'}{ref_id}"


def decode(c: str) -> tuple[str, int] | None:
    m = re.fullmatch(r"\s*\[?([AS])(\d+)\]?\s*", c or "", re.I)
    if not m:
        return None
    return ("application" if m.group(1).upper() == "A" else "opportunity"), int(m.group(2))


def _example(fields: list[dict]) -> str:
    ex = {"code": "S7", "score": 8, "verdict": "Apply", "reason": "one sentence", "missing": "the main gap, or none"}
    for f in fields:
        if f["type"] == "choice":
            ex[f["key"]] = " | ".join(f["options"])
        elif f["type"] == "number":
            lo, hi = f.get("min") or 0, f.get("max") if f.get("max") is not None else 10
            ex[f["key"]] = round((float(lo) + float(hi)) / 2)
        else:
            ex[f["key"]] = "short text"
    return json.dumps([ex], ensure_ascii=False)


def _rule(f: dict) -> str:
    if f["type"] == "choice":
        return "one of " + json.dumps(f["options"], ensure_ascii=False)
    if f["type"] == "number":
        lo, hi = f.get("min"), f.get("max")
        return "a number" + (f" from {lo}" if lo is not None else "") + (f" to {hi}" if hi is not None else "")
    return "short text"


def split_jobs(jobs: list[dict]) -> list[list[dict]]:
    """Cut a long list of jobs into prompts an assistant can read and answer in one go (by count and by text size)."""
    parts: list[list[dict]] = []
    cur: list[dict] = []
    size = 0
    for j in jobs:
        n = len(_jd(j.get("jd") or "")) + 120
        if cur and (len(cur) >= PART_JOBS or size + n > PART_CHARS):
            parts.append(cur)
            cur, size = [], 0
        cur.append(j)
        size += n
    if cur:
        parts.append(cur)
    return parts


def rank_prompt(material: str, profile: dict, jobs: list[dict], goals: str = "", fields: list[dict] | None = None,
                part: tuple[int, int] | None = None) -> str:
    """One prompt asking the assistant to score every job against the profile and reply in a fixed format."""
    fields = fields or []
    lines = [
        "You are an experienced recruiter and career coach. Rank the jobs below for me, based on my profile.",
        "For each job, judge: how well my experience matches the essential requirements, eligibility (language, work permit, "
        "degree, location), whether the seniority fits, and the most important missing requirement.",
        "",
        "Reply ONLY with a JSON array, best job first, one object per job, exactly in this form:",
        _example(fields),
        'score is 1-10; verdict is one of "Apply", "Apply with caveats", "Skip". Use the job codes exactly as given.',
    ]
    for f in fields:
        rule = _rule(f)
        lines.append(f'{f["key"]}: {f["ask"]} ({rule}).')
    lines += ["", "=== MY PROFILE ===", material.strip()]
    elig = _eligibility(profile)
    if elig:
        lines += ["", "=== ELIGIBILITY ===", elig]
    if goals.strip():
        lines += ["", "=== WHAT I'M LOOKING FOR ===", goals.strip()]
    where = f", part {part[0]} of {part[1]}" if part and part[1] > 1 else ""
    lines += ["", f"=== JOBS ({len(jobs)}{where}) ==="]
    if where:
        lines.append(f"This is part {part[0]} of {part[1]}: rank only the jobs in this message. Other parts come separately.")
    for j in jobs:
        lines += ["", f"--- {j['code']}: {j['position']} at {j['company']}" + (f" ({j['location']})" if j.get("location") else "") + " ---",
                  _jd(j.get("jd") or "") or "(no description saved)"]
    return "\n".join(lines)


VERDICTS = {"apply": "Apply", "apply with caveats": "Apply with caveats", "caveats": "Apply with caveats",
            "maybe": "Apply with caveats", "skip": "Skip", "deprioritise": "Skip", "deprioritize": "Skip", "no": "Skip"}


def parse_ranking(text: str, fields: list[dict] | None = None) -> list[dict]:
    """Read the assistant's reply: the JSON array asked for, or 'S7 – 8/10 – Apply – reason' lines as a fallback."""
    out: list[dict] = []
    t = (text or "").strip()
    # Read every complete {...} object that has a job code, wherever it sits: this survives code fences, chatter
    # (even with [brackets]) before the list, and a reply that was cut off halfway through.
    dec, i, seen = json.JSONDecoder(), 0, set()
    while (i := t.find("{", i)) != -1:
        try:
            d, end = dec.raw_decode(t, i)
        except json.JSONDecodeError:
            i += 1
            continue
        i = end
        c = decode(str(d.get("code") or d.get("id") or "")) if isinstance(d, dict) else None
        if c and c not in seen:
            seen.add(c)
            item = _norm_item(c, d.get("score"), d.get("verdict"), d.get("reason"), d.get("missing"))
            item["extra"] = _extras(d, fields or [])
            out.append(item)
    if out:
        return out
    for ln in t.splitlines():
        mm = re.search(r"\b([AS]\d+)\b", ln, re.I)
        if not mm:
            continue
        c = decode(mm.group(1))
        sc = re.search(r"\b(10|[1-9])(?:\s*/\s*10)?\b", ln[mm.end():])
        verdict = next((v for k, v in sorted(VERDICTS.items(), key=lambda kv: -len(kv[0])) if re.search(rf"\b{k}\b", ln, re.I)), None)
        reason = re.split(r"[–—:-]\s*", ln[mm.end():], maxsplit=3)[-1].strip() if len(ln) > mm.end() + 3 else ""
        out.append(_norm_item(c, sc.group(1) if sc else None, verdict, reason, None))
    return out


def _extras(d: dict, fields: list[dict]) -> dict:
    """The configured extra fields from one reply object, cleaned up; anything unreadable is left out."""
    out = {}
    lower = {str(k).lower(): v for k, v in d.items()}
    for f in fields:
        v = d.get(f["key"], lower.get(f["key"].lower()))
        if v is None or v == "":
            continue
        if f["type"] == "number":
            m = re.search(r"-?\d+(?:\.\d+)?", str(v))
            if not m:
                continue
            x = float(m.group(0))
            if f.get("min") is not None:
                x = max(float(f["min"]), x)
            if f.get("max") is not None:
                x = min(float(f["max"]), x)
            out[f["key"]] = int(x) if x == int(x) else round(x, 1)
        elif f["type"] == "choice":
            hit = next((o for o in f["options"] if o.lower() == str(v).strip().lower()), None)
            out[f["key"]] = hit or str(v).strip()[:40]
        else:
            out[f["key"]] = (", ".join(map(str, v)) if isinstance(v, list) else str(v)).strip()[:300]
    return out


def _norm_item(c, score, verdict, reason, missing) -> dict:
    try:
        s = max(1, min(10, int(round(float(score))))) if score is not None else None
    except (TypeError, ValueError):
        s = None
    v = VERDICTS.get(str(verdict or "").strip().lower(), str(verdict).strip() if verdict else None)
    if v is None and s is not None:
        v = "Apply" if s >= 7 else "Apply with caveats" if s >= 5 else "Skip"
    return {"kind": c[0], "ref_id": c[1], "code": code(*c), "score": s, "verdict": v,
            "reason": (str(reason).strip() if reason else "")[:400], "missing": (str(missing).strip() if missing else "")[:200]}


# --------------------------------------------------------------------------- single-job prompts
CRITIQUES = {
    "weakness": ("What is the biggest weakness in my application?",
                 "Act as the recruiter screening applications for this job. Name the single biggest weakness of my application "
                 "for THIS job, explain why it matters to this employer, and give 2-3 concrete ways to address it (in my CV, "
                 "cover letter or interview), using only facts from my profile."),
    "evidence": ("Which claim needs better evidence?",
                 "Act as a sceptical hiring manager for this job. Find the 2-3 claims or bullets in my profile that matter most "
                 "for this job but are least convincing as written (vague scope, no result, unclear ownership). For each, quote "
                 "it, say what you'd doubt, and suggest exactly what to add or change. Don't invent facts; ask me if needed."),
    "hesitate": ("What would make a recruiter hesitate?",
                 "List the 3 things most likely to make a recruiter hesitate to shortlist me for this job (eligibility, "
                 "seniority, missing requirements, gaps, wording), most serious first. For each, say how I can pre-empt it."),
    "cv": ("Tailor my CV for this job",
           "Help me tailor my CV for this job. First tell me which experiences to lead with and which to cut, then rewrite "
           "the 5 most relevant bullets using the job's vocabulary. Use only facts from my profile; ask me before adding anything."),
    "letter": ("Draft my cover letter",
               "Help me write a cover letter for this job (250-350 words). Start by telling me the strongest link between my "
               "experience and their top priority, the most credible reason I'd want this job, and one example to highlight. "
               "Then draft it. Use only facts from my profile; avoid generic phrases."),
    "interview": ("Prepare me for the interview",
                  "Prepare me for an interview for this job: list the 8 questions they're most likely to ask (from the "
                  "requirements and my profile's weak spots), and for each, the story or example from my profile I should use."),
}


def job_prompt(kind: str, material: str, profile: dict, job: dict, fit: dict | None, style: dict | None = None) -> str:
    title, ask = CRITIQUES[kind]
    lines = [ask, "", f"=== THE JOB: {job['position']} at {job['company']}" + (f" ({job['location']})" if job.get("location") else "") + " ===",
             _jd(job.get("jd") or "", 6000)]
    if fit and fit.get("requirements"):
        miss = [r["text"] for r in fit["requirements"] if r.get("status") == "missing" and r.get("type") == "essential"][:5]
        if miss:
            lines += ["", "Requirements my profile doesn't obviously show (from a quick keyword check): " + "; ".join(miss)]
    lines += ["", "=== MY PROFILE ===", material.strip()]
    elig = _eligibility(profile)
    if elig:
        lines += ["", "=== ELIGIBILITY ===", elig]
    if style and kind in ("cv", "letter"):
        bits = [f"{style['spelling']} spelling" if style.get("spelling") else "", f"tone: {style['tone']}" if style.get("tone") else "",
                f"avoid: {style['avoid']}" if style.get("avoid") else ""]
        bits = [b for b in bits if b]
        if bits:
            lines += ["", "My writing preferences: " + "; ".join(bits)]
        if style.get("samples"):
            lines += ["A sample of how I write:", style["samples"][:800]]
    lines += ["", "Keep the answer short and concrete."]
    return "\n".join(lines)
