from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected 1 match, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- features.py: build recovery-quality source metrics from existing curated data ---
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''        latest_sales = _num(latest_actual.get("sales"))\n        latest_op = _num(latest_actual.get("operating_profit"))\n        op_margin = latest_op / latest_sales if latest_sales and latest_sales > 0 else np.nan\n        ocf = pd.to_numeric(annual.get("operating_cf"), errors="coerce")\n''',
    '''        latest_sales = _num(latest_actual.get("sales"))\n        latest_op = _num(latest_actual.get("operating_profit"))\n        op_margin = latest_op / latest_sales if latest_sales and latest_sales > 0 else np.nan\n\n        op_values = pd.to_numeric(annual["operating_profit"], errors="coerce")\n        operating_profit_cagr_3y = (\n            _safe_cagr(float(op_values.iloc[0]), float(op_values.iloc[-1]), len(annual) - 1)\n            if len(annual) >= 2 and op_values.notna().all()\n            else np.nan\n        )\n        ocf = pd.to_numeric(annual.get("operating_cf"), errors="coerce")\n        valid_conversion = op_values.notna() & ocf.notna() & (op_values > 0)\n        conversion_profit = float(op_values.loc[valid_conversion].sum()) if valid_conversion.any() else np.nan\n        cash_conversion_ratio_3y = (\n            float(ocf.loc[valid_conversion].sum()) / conversion_profit\n            if valid_conversion.any() and conversion_profit > 0\n            else np.nan\n        )\n''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''        net_cash = cash - debt if not pd.isna(cash) and not pd.isna(debt) else np.nan\n\n        forecast_rows = all_rows.dropna(subset=["forecast_operating_profit"])\n''',
    '''        net_cash = cash - debt if not pd.isna(cash) and not pd.isna(debt) else np.nan\n        net_cash_to_assets = (\n            net_cash / total_assets\n            if not pd.isna(net_cash) and total_assets and total_assets > 0\n            else np.nan\n        )\n\n        forecast_rows = all_rows.dropna(subset=["forecast_operating_profit"])\n''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''        forecast_op_growth = (\n            forecast_op / latest_op - 1\n            if latest_op and latest_op > 0 and not pd.isna(forecast_op)\n            else np.nan\n        )\n\n        eps = _num(latest_actual.get("eps"))\n''',
    '''        forecast_op_growth = (\n            forecast_op / latest_op - 1\n            if latest_op and latest_op > 0 and not pd.isna(forecast_op)\n            else np.nan\n        )\n        forecast_revision_rate = np.nan\n        forecast_revision_observed = False\n        revision_flag = str(forecast_row.get("is_revision", "")).strip().lower() in {\n            "true", "1", "yes"\n        }\n        if revision_flag and len(forecast_rows) >= 2:\n            previous_forecast = _num(forecast_rows.iloc[-2].get("forecast_operating_profit"))\n            if previous_forecast and previous_forecast > 0 and not pd.isna(forecast_op):\n                forecast_revision_rate = forecast_op / previous_forecast - 1\n                forecast_revision_observed = True\n\n        eps = _num(latest_actual.get("eps"))\n''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''                "sales_cagr_3y": sales_cagr_3y,\n                "operating_margin": op_margin,\n                "operating_profit_latest": latest_op,\n''',
    '''                "sales_cagr_3y": sales_cagr_3y,\n                "operating_profit_cagr_3y": operating_profit_cagr_3y,\n                "operating_margin": op_margin,\n                "operating_profit_latest": latest_op,\n                "cash_conversion_ratio_3y": cash_conversion_ratio_3y,\n''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''                "equity_ratio": equity_ratio,\n                "net_cash": net_cash,\n                "eps": eps,\n''',
    '''                "equity_ratio": equity_ratio,\n                "net_cash": net_cash,\n                "net_cash_to_assets": net_cash_to_assets,\n                "eps": eps,\n''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''                "forecast_operating_profit": forecast_op,\n                "forecast_op_growth": forecast_op_growth,\n                "actual_annual_dividend_per_share": actual_dividend,\n''',
    '''                "forecast_operating_profit": forecast_op,\n                "forecast_op_growth": forecast_op_growth,\n                "forecast_revision_rate": forecast_revision_rate,\n                "forecast_revision_observed": forecast_revision_observed,\n                "actual_annual_dividend_per_share": actual_dividend,\n''',
)

# --- criteria.py: calculate a missing-safe, sector-aware Recovery Quality score ---
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''def _join_reasons(row: pd.Series, mapping: list[tuple[str, str]], expected: bool) -> str:\n''',
    '''def _scale_recovery_component(values: pd.Series, low: float, high: float) -> pd.Series:\n    numeric = pd.to_numeric(values, errors="coerce")\n    scaled = (numeric - low) / (high - low)\n    return scaled.clip(lower=0.0, upper=1.0)\n\n\ndef _join_reasons(row: pd.Series, mapping: list[tuple[str, str]], expected: bool) -> str:\n''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''    require_dividend = bool(s.get("require_dividend", False))\n''',
    '''    sector_text = scored.get("sector", pd.Series("", index=index)).astype(str).str.lower()\n    financial_sector = sector_text.str.contains(\n        r"銀行|保険|証券|金融|bank|insurance|securit|financial", regex=True, na=False\n    )\n    cash_conversion = _numeric_series(scored, "cash_conversion_ratio_3y", index).mask(financial_sector)\n    op_profit_cagr = _numeric_series(scored, "operating_profit_cagr_3y", index)\n    forecast_revision = _numeric_series(scored, "forecast_revision_rate", index)\n    net_cash_assets = _numeric_series(scored, "net_cash_to_assets", index)\n\n    recovery_components = {\n        "cash_conversion": (_scale_recovery_component(cash_conversion, 0.0, 1.10), 35.0),\n        "operating_profit_trend": (_scale_recovery_component(op_profit_cagr, -0.20, 0.10), 25.0),\n        "forecast_revision": (_scale_recovery_component(forecast_revision, -0.20, 0.10), 25.0),\n        "balance_sheet_buffer": (_scale_recovery_component(net_cash_assets, -0.30, 0.20), 15.0),\n    }\n    observed_weight = pd.Series(0.0, index=index)\n    weighted_score = pd.Series(0.0, index=index)\n    observed_components = pd.Series(0, index=index, dtype=int)\n    for component, (values, weight) in recovery_components.items():\n        available = values.notna()\n        scored[f"recovery_{component}_score"] = values * 100.0\n        observed_weight = observed_weight + available.astype(float) * weight\n        weighted_score = weighted_score + values.fillna(0.0) * weight\n        observed_components = observed_components + available.astype(int)\n    scored["recovery_quality_observed_components"] = observed_components\n    scored["recovery_quality_score"] = np.where(\n        observed_weight > 0, weighted_score / observed_weight * 100.0, np.nan\n    )\n    minimum_recovery_components = int(s.get("minimum_recovery_quality_components", 2))\n    minimum_recovery_score = float(s.get("minimum_recovery_quality_score", 55.0))\n    scored["pass_recovery_quality"] = (\n        (scored["recovery_quality_observed_components"] < minimum_recovery_components)\n        | pd.isna(scored["recovery_quality_score"])\n        | (scored["recovery_quality_score"] >= minimum_recovery_score)\n    )\n\n    require_dividend = bool(s.get("require_dividend", False))\n''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''    hard_columns = REQUIRED_CHECK_COLUMNS + ["pass_dividend_conditions"]\n''',
    '''    hard_columns = REQUIRED_CHECK_COLUMNS + ["pass_recovery_quality", "pass_dividend_conditions"]\n''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''        ("pass_forecast", "会社予想"),\n        ("pass_dividend_conditions", "配当条件"),\n''',
    '''        ("pass_forecast", "会社予想"),\n        ("pass_recovery_quality", "回復品質"),\n        ("pass_dividend_conditions", "配当条件"),\n''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''            ("会社予想条件", REQUIRED_CHECK_COLUMNS),\n            ("配当条件", REQUIRED_CHECK_COLUMNS + ["pass_dividend_conditions"]),\n            ("定量スコア", REQUIRED_CHECK_COLUMNS + ["pass_dividend_conditions", "pass_quantitative_score"]),\n''',
    '''            ("会社予想条件", REQUIRED_CHECK_COLUMNS),\n            ("回復品質", REQUIRED_CHECK_COLUMNS + ["pass_recovery_quality"]),\n            ("配当条件", REQUIRED_CHECK_COLUMNS + ["pass_recovery_quality", "pass_dividend_conditions"]),\n            ("定量スコア", REQUIRED_CHECK_COLUMNS + ["pass_recovery_quality", "pass_dividend_conditions", "pass_quantitative_score"]),\n''',
)

# --- configuration defaults ---
for config_path in ("config/real_data.yaml", "config/real_data.example.yaml", "config/default.yaml"):
    replace_once(
        config_path,
        '''  maximum_forecast_op_decline: -0.20\n''',
        '''  maximum_forecast_op_decline: -0.20\n  minimum_recovery_quality_score: 55\n  minimum_recovery_quality_components: 2\n''',
    )

# --- version and contract ---
replace_once("pyproject.toml", 'version = "0.6.61"', 'version = "0.6.62"')
replace_once("src/value_dislocation/__init__.py", '__version__ = "0.6.61"', '__version__ = "0.6.62"')
replace_once("tests/test_package_init.py", '== "0.6.61"', '== "0.6.62"')
replace_once("harness/app_blueprint.yaml", "blueprint_version: 0.6.61", "blueprint_version: 0.6.62")
replace_once(
    "harness/app_blueprint.yaml",
    '''- legacy_vs_reversal_star_outcome_comparison\n''',
    '''- legacy_vs_reversal_star_outcome_comparison\n- recovery_quality_structural_deterioration_guard\n''',
)
replace_once(
    "harness/app_blueprint.yaml",
    '''- legacy_star_eligibility_must_remain_comparable_after_rule_change\n''',
    '''- legacy_star_eligibility_must_remain_comparable_after_rule_change\n- recovery_quality_must_be_missing_safe_and_not_fetch_market_data\n''',
)

# --- changelog and task note ---
replace_once(
    "CHANGELOG.md",
    "# Changelog\n",
    "# Changelog\n\n## v0.6.62\n- `Recovery Quality（回復の質）` を追加し、利益のキャッシュ転換性・営業利益の中期方向・会社予想の修正方向・ネットキャッシュ/総資産を複合評価。\n- 最低2成分が観測できる場合だけ標準55点以上を必須化し、データ不足では機械的に候補を除外しない。\n- 銀行・保険・証券等では営業CFの意味が一般事業会社と異なるためキャッシュ転換成分を除外。\n- 既存curatedデータだけで計算し、条件変更や画面遷移でJ-Quants/Yahoo追加取得を行わない。\n\n",
)

print("v0.6.62 patch applied")
