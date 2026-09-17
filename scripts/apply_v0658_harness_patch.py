from pathlib import Path

path = Path("scripts/harness_check.py")
text = path.read_text(encoding="utf-8")

insert_before = "def check_dividend_screening(root: Path) -> CheckResult:\n"
check = '''def check_large_data_navigation_performance(root: Path) -> CheckResult:\n    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")\n    config = (root / "src/value_dislocation/config.py").read_text(encoding="utf-8")\n    pipeline = (root / "src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")\n    learning = (root / "src/value_dislocation/strategy/rule_learning.py").read_text(encoding="utf-8")\n\n    bundle_resource_cache = "@st.cache_resource(show_spinner=False, max_entries=2)" in dashboard\n    normal_config_is_light = (\n        "refresh_rule_learning: bool = False" in config\n        and "if refresh_rule_learning:" in config\n        and "apply_active_rule_overrides(data, project_root_from_config(config_path))" in config\n    )\n    refresh_is_explicit = "load_config(config_path, refresh_rule_learning=True)" in pipeline\n    one_feature_prepare = (\n        pipeline.count("prepare_quantitative_universe(") == 1\n        and "prepared=prepared" in pipeline\n        and "apply_quantitative_criteria(prepared, cfg)" in pipeline\n        and "build_quantitative_table(" not in pipeline\n    )\n    indexed_price_lookup = (\n        'prices.groupby("code", sort=False)' in learning\n        and "price_groups.get(str(code))" in learning\n        and 'prices.loc[prices["code"].astype(str) == str(code)' not in learning\n    )\n    passed = all((bundle_resource_cache, normal_config_is_light, refresh_is_explicit, one_feature_prepare, indexed_price_lookup))\n    return CheckResult(\n        "large_data_navigation_performance",\n        passed,\n        json.dumps({\n            "bundle_resource_cache": bundle_resource_cache,\n            "normal_config_is_light": normal_config_is_light,\n            "refresh_is_explicit": refresh_is_explicit,\n            "one_feature_prepare": one_feature_prepare,\n            "indexed_price_lookup": indexed_price_lookup,\n        }, ensure_ascii=False),\n    )\n\n\n'''
if text.count(insert_before) != 1:
    raise SystemExit("dividend check marker missing")
text = text.replace(insert_before, check + insert_before, 1)

run_marker = "        check_candidate_stock_new_tab_navigation(root),\n        check_dividend_screening(root),\n"
run_new = "        check_candidate_stock_new_tab_navigation(root),\n        check_large_data_navigation_performance(root),\n        check_dividend_screening(root),\n"
if text.count(run_marker) != 1:
    raise SystemExit("run_checks marker missing")
text = text.replace(run_marker, run_new, 1)

invariant_marker = '        "history_stock_detail_must_open_new_tab_without_mutating_history_session",\n'
invariant_new = invariant_marker + '        "screen_navigation_must_not_refresh_rule_learning",\n        "large_curated_bundle_must_not_be_copied_per_rerun",\n        "quantitative_features_must_be_prepared_once_per_data_refresh",\n        "rule_learning_must_not_rescan_all_prices_per_security",\n'
if text.count(invariant_marker) != 1:
    raise SystemExit("blueprint invariant marker missing")
text = text.replace(invariant_marker, invariant_new, 1)

path.write_text(text, encoding="utf-8")
