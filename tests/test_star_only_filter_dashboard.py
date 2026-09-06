from pathlib import Path


def test_dashboard_supports_star_only_candidate_filter_without_jquants_refetch():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert '"☆だけの銘柄を表示"' in text
    assert 'st.session_state.setdefault("ui_star_only", False)' in text
    assert 'star_only=bool(st.session_state.get("ui_star_only", False))' in text
    assert 'str.startswith("◎☆")' in text
    assert '"☆限定候補CSVをダウンロード"' in text
    # The star-only filter is applied to the already-built unified result; it must
    # not invoke the real-data pipeline / J-Quants fetch path.
    star_section = text[text.index('"☆だけの銘柄を表示"'):]
    assert "run_real_pipeline(" not in star_section.split("def render_sbi_csv_import", 1)[0]


def test_star_only_filter_preserves_unfiltered_integrity_count():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "all_result = pd.DataFrame(rows)" in text
    assert "if len(all_result) != total:" in text
    assert 'count_cols[1].metric("統合一覧", f"{len(all_result):,}")' in text
    assert "result = all_result.loc[star_mask].reset_index(drop=True)" in text
