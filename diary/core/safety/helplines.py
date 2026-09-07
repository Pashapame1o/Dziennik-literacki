"""Helpline banner content, loaded from config/helplines/<locale>.yaml (SPEC 6.5)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

HELPLINES_DIR = Path(__file__).resolve().parents[3] / "config" / "helplines"


class HelplineNumber(BaseModel):
    label: str
    phone: str


class Helplines(BaseModel):
    locale: str
    footer_text: str
    banner_intro: str
    numbers: list[HelplineNumber] = Field(default_factory=list)


def load_helplines(locale: str) -> Helplines:
    path = HELPLINES_DIR / f"{locale}.yaml"
    if not path.is_file():
        path = HELPLINES_DIR / "pl.yaml"  # graceful fallback: always show something
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Helplines.model_validate(raw)
