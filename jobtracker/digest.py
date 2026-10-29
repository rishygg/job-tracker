"""Background reading of job descriptions with a local model (optional).

Each description is read once into a small summary (skills, tools, industry, seniority, main requirements). Results
are cached by the description's content, so only new or edited descriptions are read again. The statistics built on
top (which skills come up most, where you get results) are plain counting and are instant.
"""

from __future__ import annotations

from .fit import text_hash
from .posting import clean

SYSTEM = """You read one job description and summarise it as JSON. Be factual; use only what the text says.
- skills: up to 12 concrete skills, methods or tools the job asks for, in English, short (e.g. "SQL", "clinical trials",
  "stakeholder management", "Power BI"). No soft traits like "motivated".
- industry: the employer's industry in a few words (e.g. "Pharma & biotech", "Consulting").
- seniority: one of Intern, Graduate/Junior, Mid, Senior, Lead/Manager.
- requirements: up to 6 essential requirements, each under 12 words, in English.
- language: languages the job requires (e.g. ["English", "German"]); empty if none stated."""

SCHEMA = {"type": "object", "properties": {
    "skills": {"type": "array", "items": {"type": "string"}},
    "industry": {"type": "string"},
    "seniority": {"type": "string"},
    "requirements": {"type": "array", "items": {"type": "string"}},
    "language": {"type": "array", "items": {"type": "string"}},
}, "required": ["skills", "industry", "seniority", "requirements", "language"]}

EXPECTED_TOKENS = 170


def jd_hash(jd: str) -> str:
    return text_hash("digest-v1", jd)


def read(jd: str, client) -> dict:
    text, _ = clean(jd or "")
    raw = client.chat_json(SYSTEM, text[:5000], SCHEMA, temperature=0.1, num_predict=260)
    norm = lambda xs: [str(x).strip() for x in (xs or []) if str(x).strip()]  # noqa: E731
    return {"skills": norm(raw.get("skills"))[:12], "industry": str(raw.get("industry") or "").strip()[:60],
            "seniority": str(raw.get("seniority") or "").strip()[:30], "requirements": norm(raw.get("requirements"))[:6],
            "language": norm(raw.get("language"))[:4], "model": getattr(client, "model", None)}
