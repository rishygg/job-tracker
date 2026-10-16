"""Rule-based categorisation of job titles and locations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "categories.yaml"


@dataclass
class Rule:
    name: str
    keywords: list[str]
    _pattern: re.Pattern = field(init=False, repr=False)

    def __post_init__(self) -> None:
        parts = [re.escape(k.strip().lower()) for k in self.keywords if k.strip()]
        # Whole-word / whole-phrase match so "ai" does not match "maintenance".
        self._pattern = re.compile(r"(?<![\w])(" + "|".join(parts) + r")(?![\w])") if parts else re.compile(r"$^")

    def matches(self, text: str) -> bool:
        return bool(self._pattern.search(text.lower()))


@dataclass
class Categoriser:
    role_rules: list[Rule]
    region_rules: list[Rule]
    default_role_area: str = "Other"
    default_region: str = "Other / unspecified"

    @classmethod
    def from_yaml(cls, path: str | Path = DEFAULT_CONFIG) -> "Categoriser":
        with open(path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        return cls.from_dict(cfg)

    @classmethod
    def from_dict(cls, cfg: dict) -> "Categoriser":
        return cls(
            role_rules=[Rule(r["name"], r.get("keywords", [])) for r in cfg.get("role_areas", [])],
            region_rules=[Rule(r["name"], r.get("keywords", [])) for r in cfg.get("regions", [])],
            default_role_area=cfg.get("default_role_area", "Other"),
            default_region=cfg.get("default_region", "Other / unspecified"),
        )

    def to_dict(self) -> dict:
        return {
            "role_areas": [{"name": r.name, "keywords": r.keywords} for r in self.role_rules],
            "default_role_area": self.default_role_area,
            "regions": [{"name": r.name, "keywords": r.keywords} for r in self.region_rules],
            "default_region": self.default_region,
        }

    def role_area(self, title: str | None) -> str:
        if not title:
            return self.default_role_area
        for rule in self.role_rules:
            if rule.matches(str(title)):
                return rule.name
        return self.default_role_area

    def region(self, location: str | None) -> str:
        if not location:
            return self.default_region
        for rule in self.region_rules:
            if rule.matches(str(location)):
                return rule.name
        return self.default_region

    @property
    def role_area_names(self) -> list[str]:
        return [r.name for r in self.role_rules] + [self.default_role_area]

    @property
    def region_names(self) -> list[str]:
        return [r.name for r in self.region_rules] + [self.default_region]


def save_yaml(cat: Categoriser, path: str | Path = DEFAULT_CONFIG) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cat.to_dict(), fh, sort_keys=False, allow_unicode=True)
