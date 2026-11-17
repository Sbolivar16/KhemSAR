"""Trilingual internationalization engine (ES / EN / PT) for KhemSAR."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_LANGUAGES = ("es", "en", "pt")
LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


@lru_cache(maxsize=4)
def load_locale(lang: str) -> dict[str, Any]:
    """Load a locale JSON file, defaulting to Spanish if unknown."""
    code = lang if lang in SUPPORTED_LANGUAGES else "es"
    path = LOCALES_DIR / f"{code}.json"
    if not path.exists():
        path = LOCALES_DIR / "es.json"
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, lang: str = "es", **kwargs: Any) -> str:
    """Translate a dotted key (e.g. 'app.title') with optional format kwargs."""
    data = load_locale(lang)
    cur: Any = data
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            cur = None
            break
    if cur is None and lang != "en":
        return t(key, lang="en", **kwargs)
    if not isinstance(cur, str):
        return key
    return cur.format(**kwargs) if kwargs else cur
