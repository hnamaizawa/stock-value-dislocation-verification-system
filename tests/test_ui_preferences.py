import json
from pathlib import Path

from value_dislocation.ui_preferences import load_ui_preferences, save_ui_preferences


def test_ui_theme_persists_across_reload(tmp_path):
    path = tmp_path / "config" / "ui_preferences.json"
    save_ui_preferences(path, {"ui_theme": "やわらかパステル"})
    assert load_ui_preferences(path)["ui_theme"] == "やわらかパステル"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["ui_theme"] == "やわらかパステル"


def test_invalid_ui_theme_falls_back_to_standard(tmp_path):
    path = tmp_path / "ui_preferences.json"
    path.write_text('{"ui_theme": "unknown"}', encoding="utf-8")
    assert load_ui_preferences(path)["ui_theme"] == "標準"


def test_dashboard_initializes_theme_from_persistent_preferences():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert 'UI_PREFERENCES_PATH = ROOT / "config" / "ui_preferences.json"' in source
    assert 'if "ui_theme" not in st.session_state' in source
    assert 'load_ui_preferences(UI_PREFERENCES_PATH)' in source
    assert 'on_change=_persist_ui_theme' in source
    assert 'save_ui_preferences(UI_PREFERENCES_PATH' in source


def test_generated_app_does_not_copy_saved_ui_preferences():
    source = Path("scripts/generate_app.py").read_text(encoding="utf-8")
    assert 'Path("config/ui_preferences.json")' in source
