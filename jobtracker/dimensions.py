"""Infer role dimensions (seniority, industry, size, work permit, language, skills, ...)
from the job title, company name and job description.

All rules live in config/dimensions.yaml so they can be tuned without touching code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "dimensions.yaml"

GERMAN_STOPWORDS = {"und", "die", "der", "das", "wir", "sie", "mit", "für", "ihre", "ihr", "eine", "bei", "von",
                    "auf", "sind", "werden", "unser", "unsere", "zu", "als", "oder", "du", "dein", "deine"}


def _phrase_pattern(terms: list[str], case_sensitive: bool = False) -> re.Pattern | None:
    parts = [re.escape(t.strip()) for t in terms if t and str(t).strip()]
    if not parts:
        return None
    # Longest first so "clinical trials" wins over "clinical trial" in findall.
    parts.sort(key=len, reverse=True)
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(r"(?<![\w])(" + "|".join(parts) + r")(?![\w])", flags)


@dataclass
class NamedRule:
    name: str
    pattern: re.Pattern | None
    companies: re.Pattern | None = None

    def matches(self, text: str | None) -> bool:
        return bool(isinstance(text, str) and text and self.pattern and self.pattern.search(text))

    def matches_company(self, company: str | None) -> bool:
        return bool(isinstance(company, str) and company and self.companies and self.companies.search(company))


def _rules(items: list[dict]) -> list[NamedRule]:
    return [NamedRule(i["name"], _phrase_pattern(i.get("keywords", [])), _phrase_pattern(i.get("companies", [])))
            for i in items or []]


def _first(rules: list[NamedRule], *texts: str | None) -> str | None:
    for text in texts:
        if not isinstance(text, str) or not text:
            continue
        for r in rules:
            if r.matches(text):
                return r.name
    return None


YEARS_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to|bis)\s*(\d{1,2})\s*)?\+?\s*(?:years?|yrs?|jahre)",
    re.IGNORECASE,
)


@dataclass
class JDAnalysis:
    skills: list[str] = field(default_factory=list)
    language: str | None = None
    work_authorization: str | None = None
    work_mode: str | None = None
    min_years: int | None = None
    written_in_german: bool = False


@dataclass
class DimensionInferer:
    cfg: dict

    def __post_init__(self) -> None:
        c = self.cfg
        self.seniority_rules = _rules(c.get("seniority"))
        self.industry_rules = _rules(c.get("industries"))
        self.workauth_rules = _rules(c.get("work_authorization"))
        self.language_rules = _rules(c.get("languages"))
        self.workmode_rules = _rules(c.get("work_mode"))
        self.size_rules = [NamedRule(size, None, _phrase_pattern(names))
                           for size, names in (c.get("company_size") or {}).items()]
        self.skill_patterns: list[tuple[str, str, re.Pattern]] = []
        for group, items in (c.get("skills") or {}).items():
            for item in items:
                if isinstance(item, dict):
                    term, cs = item["term"], bool(item.get("case_sensitive"))
                else:
                    term, cs = str(item), False
                pat = _phrase_pattern([term], case_sensitive=cs)
                if pat:
                    self.skill_patterns.append((term if cs else term.lower(), group, pat))

    # ---- config --------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str | Path = DEFAULT_CONFIG) -> "DimensionInferer":
        with open(path, encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh) or {})

    def options(self, key: str) -> list[str]:
        c = self.cfg
        lists = {
            "seniority": [r["name"] for r in c.get("seniority", [])] + [c.get("default_seniority", "Mid / unspecified")],
            "industry": [r["name"] for r in c.get("industries", [])] + [c.get("default_industry", "Unknown")],
            "company_size": c.get("size_options", ["Startup (<50)", "SME (50–999)", "Large (1000+)", "Unknown"]),
            "work_authorization": [r["name"] for r in c.get("work_authorization", [])]
            + [c.get("default_work_authorization", "Not stated")],
            "language": [r["name"] for r in c.get("languages", [])] + [c.get("default_language", "No extra language stated")],
            "work_mode": [r["name"] for r in c.get("work_mode", [])] + [c.get("default_work_mode", "Not stated")],
        }
        # Keep order, drop duplicates.
        return list(dict.fromkeys(lists[key]))

    @property
    def skill_groups(self) -> dict[str, str]:
        return {term: group for term, group, _ in self.skill_patterns}

    # ---- inference -----------------------------------------------------
    def analyse_jd(self, jd: str | None) -> JDAnalysis:
        if not isinstance(jd, str) or not jd.strip():
            return JDAnalysis()
        text = str(jd)
        skills = sorted({term for term, _, pat in self.skill_patterns if pat.search(text)})
        years = [int(m.group(1)) for m in YEARS_RE.finditer(text) if int(m.group(1)) <= 20]
        words = re.findall(r"[a-zäöüß]+", text.lower())
        german_share = sum(w in GERMAN_STOPWORDS for w in words) / max(1, len(words))
        written_in_german = len(words) >= 40 and german_share > 0.06
        language = _first(self.language_rules, text)
        if written_in_german and language in (None, "German a plus"):
            language = "German required"
        return JDAnalysis(
            skills=skills,
            language=language,
            work_authorization=_first(self.workauth_rules, text),
            work_mode=_first(self.workmode_rules, text),
            min_years=min(years) if years else None,
            written_in_german=written_in_german,
        )

    def seniority(self, title: str | None, jd: JDAnalysis | None = None) -> str:
        found = _first(self.seniority_rules, title)
        if found:
            return found
        if jd and jd.min_years is not None:
            for step in self.cfg.get("years_to_seniority", []):
                if jd.min_years <= step["max_years"]:
                    return step["name"]
        return self.cfg.get("default_seniority", "Mid / unspecified")

    def industry(self, company: str | None, jd_text: str | None = None) -> str:
        for r in self.industry_rules:
            if r.matches_company(company):
                return r.name
        return _first(self.industry_rules, jd_text) or self.cfg.get("default_industry", "Unknown")

    def company_size(self, company: str | None) -> str:
        for r in self.size_rules:
            if r.matches_company(company):
                return r.name
        return "Unknown"

    def infer_all(self, title: str | None, company: str | None, jd_text: str | None) -> dict:
        jd = self.analyse_jd(jd_text)
        c = self.cfg
        return {
            "seniority": self.seniority(title, jd),
            "industry": self.industry(company, jd_text),
            "company_size": self.company_size(company),
            "work_authorization": jd.work_authorization or c.get("default_work_authorization", "Not stated"),
            "language": jd.language or c.get("default_language", "No extra language stated"),
            "work_mode": jd.work_mode or c.get("default_work_mode", "Not stated"),
            "jd_skills": jd.skills,
            "min_years": jd.min_years,
        }
