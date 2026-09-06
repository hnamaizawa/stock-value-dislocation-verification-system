from pathlib import Path


def test_dashboard_uses_one_unified_candidate_list_with_latest_external_history():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "統合候補一覧（抽出条件 + 最新トレンド）" in text
    assert "定量候補（外的要因の調査対象）" not in text
    assert "スコア通過銘柄の最新トレンド再判定" not in text
    assert "_latest_external_history" in text
    assert "build_trend_transition" in text
    assert "unified_candidate_code_" in text
    assert "unified_candidate_name_" in text


def test_latest_trend_recheck_has_no_hidden_twenty_stock_cap():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "limit = min(len(shortlist), 20)" not in text
    assert "shortlist.head(limit)" not in text
    assert "for _, row in score_passed.iterrows()" in text
    assert "score_passed," in text
    assert "star_only=" in text


def test_unified_list_exposes_count_reconciliation_and_failures():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert 'metric("スコア通過"' in text
    assert 'metric("統合一覧"' in text
    assert 'metric("外部株価取得成功"' in text
    assert 'metric("取得失敗・判定不能"' in text
    assert '統合一覧は' in text
