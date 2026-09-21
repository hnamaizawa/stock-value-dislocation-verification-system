from pathlib import Path


def test_sort_headers_use_callback_without_explicit_second_rerun():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "def _toggle_sort_state(" in text
    assert "on_click=_toggle_sort_state" in text
    assert "args=(key, field)" in text
    start = text.index("def _sortable_header_button(")
    end = text.index("def _render_history_stock_buttons(", start)
    block = text[start:end]
    assert "st.rerun()" not in block


def test_sortable_tables_are_fragment_scoped():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert text.count("@st.fragment") >= 3
    assert "def _render_history_sortable_stock_table(" in text
    assert "def _render_clickable_candidates(" in text
    assert "def _render_unified_candidate_table(" in text
    assert "_render_unified_candidate_table(result, active_mode=active_mode)" in text
    assert '_render_history_sortable_stock_table(sorted_hist, "daily_history")' in text
    assert '_render_history_sortable_stock_table(sorted_e, "evaluation_history")' in text
    assert '_render_history_sortable_stock_table(summary, "star_summary")' in text
    assert '_render_history_sortable_stock_table(event_show, "star_events_detail")' in text


def test_readme_has_single_top_level_version_history_in_descending_order():
    readme = Path("README.md").read_text(encoding="utf-8")
    lines = readme.splitlines()
    assert lines[0] == "# Stock Value Dislocation Verification System"
    assert lines[2] == "Version: **0.6.62**"
    assert readme.count("## 開発履歴（新しい順）") == 1
    assert "Version: **0.6.51**" not in readme
    versions = [
        "### v0.6.62 構造悪化ガードでバリュートラップを識別",
        "### v0.6.61 ◎☆を反転確認済みの最上位評価へ厳格化",
        "### v0.6.60 旧実績データの期間列後方互換修正",
        "### v0.6.59 実績検証の短中期評価期間を拡張",
        "### v0.6.58 大規模データ更新・画面遷移の高速化",
        "### v0.6.57 条件設定・候補から個別銘柄を新しいタブで確認",
        "### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認",
        "### v0.6.55 履歴画面の generic timedelta 警告修正",
        "### v0.6.54 履歴実績から定量抽出ルールを安全に自動改善",
        "### v0.6.53 ソート高速化・README再構成",
        "### v0.6.52 一覧表の列クリックソート復活",
        "### v0.6.51 Streamlit 1.53.0 互換性修正",
        "### v0.6.50 パステルモード強調",
        "### v0.6.23 運用上限",
        "### v0.6.19 やわらかパステルテーマ強化",
        "### v0.6.18 画面テーマと2種類の抽出ルール",
        "### v0.6.12 外的要因レビューと最新市場鮮度",
        "### v0.6.8 見える化",
        "### v0.6.6 直感判定と買い検討価格帯",
        "### v0.6.5 NumPy timedelta警告の完全修正",
        "### v0.6.4 NumPy timedelta警告の修正",
        "### v0.6.3 パッチ整合性修正",
        "### v0.6.2 最新株価によるトレンド再判定",
        "### v0.6.1 トレンド・売却判断",
        "### v0.6.0 購入判断の整理",
        "### v0.5.10 個別銘柄の補助情報・外部評価",
        "### v0.5.8 個別銘柄画面",
        "### v0.5.6 市場比較データの自動フォールバック",
        "### v0.5.3 画面操作・配当表示改善",
        "### v0.5.0 高速化とSBI CSV連携",
        "### v0.4.0 条件設定・説明性の強化",
        "### v0.3.4 TOPIX欠損時の安全性改善",
        "### v0.3.3 J-Quants契約期間対応",
        "### v0.3.2 J-Quantsレート制限制御",
    ]
    headings = [line for line in lines if line.startswith("### v")]
    assert headings == versions
    assert readme.index("## 開発履歴（新しい順）") < readme.index("## Windows / WSL での利用")
