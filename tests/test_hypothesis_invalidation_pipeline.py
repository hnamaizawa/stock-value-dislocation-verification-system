from pathlib import Path


def test_real_pipeline_recalculates_invalidation_from_fresh_prepared_features():
    source = Path("src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    assert "build_feature_snapshot" in source
    assert "prepared=prepared" in source
    assert "evaluate_saved_reviews" in source
    assert "hypothesis_invalidation_latest.csv" in source
    assert "load_feature_snapshot" not in source
    assert source.index("prepare_quantitative_universe") < source.rindex("evaluate_saved_reviews")


def test_dashboard_shows_hypothesis_warning_and_structured_editor():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert "財務指標で自動照合する仮説無効化条件" in source
    assert "仮説無効化条件の最新財務データ照合" in source
    assert "保存済みの仮説無効化条件に最新財務データが抵触" in source
    assert '"仮説警告"' in source


def test_structured_invalidation_editor_uses_independent_row_widgets():
    """Regression: grid commit timing could leave the second edited row stale."""
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert 'with st.form(f"external_event_review_{code_key}"' not in source
    assert 'st.data_editor(' not in source[source.index("財務指標で自動照合する仮説無効化条件"):source.index("仮説無効化条件の最新財務データ照合")]
    assert 'structured_draft_key = f"structured_invalidation_rows_{code_key}"' in source
    assert 'enabled_key = _structured_widget_key(row_id, "enabled")' in source
    assert 'threshold_key = _structured_widget_key(row_id, "threshold")' in source
    assert 'row_cols[3].text_input(' in source
    assert 'structured_conditions_from_ui_rows(structured_conditions_input)' in source
    assert 'key=f"save_external_event_review_{code_key}"' in source


def test_structured_invalidation_rows_have_stable_per_row_keys():
    """Each condition row must retain its own widget state across reruns."""
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert '"_row_id": f"saved_{idx}"' in source
    assert 'new_row_id = f"new_{next_row}"' in source
    assert 'return f"structured_invalidation_{code_key}_{row_id}_{field}"' in source
    assert 'for row in list(st.session_state[structured_draft_key]):' in source


def test_structured_threshold_editor_does_not_force_four_decimal_places():
    """Regression: v0.6.16 displayed 50 as 50.0000 in threshold fields."""
    source = Path("dashboard.py").read_text(encoding="utf-8")
    section = source[source.index("財務指標で自動照合する仮説無効化条件"):source.index("仮説無効化条件の最新財務データ照合")]
    assert 'format="%.4f"' not in section
    assert 'threshold_value = row_cols[3].text_input(' in section
    assert 'format_threshold_input_value(row.get("閾値", 0.0))' in section
