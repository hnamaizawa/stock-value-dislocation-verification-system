from pathlib import Path

import yaml


def test_attribution_controls_and_comparison_are_visible_in_dashboard():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    for label in (
        "外因説明率の下限（%）",
        "外因説明率を計算できない場合",
        "下限未達で外れた件数",
        "計算不能で外れた件数",
        "計算できずに通した件数",
        "外因説明率を計算できない銘柄の内訳",
        "外因以外の条件を通過",
        "外因説明率・TOPIX条件の候補数を比較",
        "外因説明率・TOPIX条件をWalk-Forwardで比較",
    ):
        assert label in source
    assert "0%ならこの条件は使いません" in source
    assert 's.get("minimum_external_shock_attribution", 0.0)' in source


def test_all_configs_keep_attribution_disabled_and_topix_cutoff_unchanged():
    for path in (
        Path("config/default.yaml"),
        Path("config/real_data.yaml"),
        Path("config/real_data.example.yaml"),
    ):
        screen = yaml.safe_load(path.read_text(encoding="utf-8"))["screen"]
        assert screen["minimum_external_shock_attribution"] == 0.0
        assert screen["external_shock_attribution_when_missing"] == "skip_with_warning"
        assert screen["minimum_relative_underperformance_6m"] == -0.08


def test_yahoo_history_fetch_requires_explicit_refresh_button():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    start = source.index("def _render_latest_candidate_trends(")
    end = source.index("def _candidate_card(", start)
    candidate_renderer = source[start:end]
    assert '"Yahoo Finance系の最新トレンドを更新"' in candidate_renderer
    assert "if not refresh_latest:" in candidate_renderer
    assert candidate_renderer.index("if not refresh_latest:") < candidate_renderer.index("_latest_external_history(code)")
