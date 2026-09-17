from pathlib import Path


def test_large_market_bundle_uses_shared_resource_cache():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    start = text.index("def _load_bundle(")
    prefix = text[max(0, start - 120):start]
    assert "@st.cache_resource" in prefix
    assert "@st.cache_data" not in prefix
    assert "_load_bundle.clear()" in text


def test_normal_config_reads_do_not_refresh_rule_learning():
    text = Path("src/value_dislocation/config.py").read_text(encoding="utf-8")
    assert "refresh_rule_learning: bool = False" in text
    assert "if refresh_rule_learning:" in text
    assert "apply_active_rule_overrides(data, project_root_from_config(config_path))" in text

    pipeline = Path("src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    assert "load_config(config_path, refresh_rule_learning=True)" in pipeline
    assert pipeline.index("fetch_and_curate_jquants(") < pipeline.index(
        "load_config(config_path, refresh_rule_learning=True)"
    )


def test_data_refresh_reuses_one_prepared_feature_universe():
    pipeline = Path("src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    assert pipeline.count("prepare_quantitative_universe(") == 1
    assert "prepared=prepared" in pipeline
    assert "apply_quantitative_criteria(prepared, cfg)" in pipeline
    assert "build_quantitative_table(" not in pipeline
    assert "load_feature_snapshot(" not in pipeline


def test_rule_learning_builds_price_lookup_once_instead_of_full_scan_per_code():
    text = Path("src/value_dislocation/strategy/rule_learning.py").read_text(encoding="utf-8")
    start = text.index("def _attach_forward_returns(")
    end = text.index("def _deduplicate_overlapping_events(", start)
    block = text[start:end]
    assert 'prices.groupby("code", sort=False)' in block
    assert "price_groups.get(str(code))" in block
    assert 'prices.loc[prices["code"].astype(str) == str(code)' not in block
