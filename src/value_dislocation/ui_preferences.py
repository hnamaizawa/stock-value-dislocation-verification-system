from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOWED_UI_THEMES = ("標準", "やわらかパステル")
DEFAULT_UI_THEME = "標準"


def load_ui_preferences(path: str | Path) -> dict[str, Any]:
    preference_path = Path(path)
    if not preference_path.exists():
        return {"ui_theme": DEFAULT_UI_THEME}
    try:
        raw = json.loads(preference_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {"ui_theme": DEFAULT_UI_THEME}
    if not isinstance(raw, dict):
        return {"ui_theme": DEFAULT_UI_THEME}
    theme = raw.get("ui_theme", DEFAULT_UI_THEME)
    if theme not in ALLOWED_UI_THEMES:
        theme = DEFAULT_UI_THEME
    return {**raw, "ui_theme": theme}


def save_ui_preferences(path: str | Path, preferences: dict[str, Any]) -> Path:
    preference_path = Path(path)
    preference_path.parent.mkdir(parents=True, exist_ok=True)
    theme = preferences.get("ui_theme", DEFAULT_UI_THEME)
    if theme not in ALLOWED_UI_THEMES:
        theme = DEFAULT_UI_THEME
    payload = {**preferences, "ui_theme": theme}
    temp_path = preference_path.with_suffix(preference_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(preference_path)
    return preference_path
