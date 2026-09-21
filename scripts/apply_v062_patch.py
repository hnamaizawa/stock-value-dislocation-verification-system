from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


# --- Derived features: earnings quality, margin deterioration, forecast revisions, sector-relative weakness.
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''        op_margin = latest_op / latest_sales if latest_sales and latest_sales > 0 else np.nan
        ocf = pd.to_numeric(annual.get("operating_cf"), errors="coerce")
        ocf_positive_ratio = float((ocf > 0).mean()) if ocf.notna().any() else np.nan
        ocf_observed_years = int(ocf.notna().sum())
        ocf_positive_years = int((ocf > 0).sum()) if ocf.notna().any() else 0
''',
    '''        op_margin = latest_op / latest_sales if latest_sales and latest_sales > 0 else np.nan
        annual_sales = pd.to_numeric(annual.get("sales"), errors="coerce")
        annual_op = pd.to_numeric(annual.get("operating_profit"), errors="coerce")
        annual_margins = annual_op / annual_sales.where(annual_sales > 0)
        valid_margins = annual_margins.dropna()
        operating_margin_change_3y = (
            float(valid_margins.iloc[-1] - valid_margins.iloc[0])
            if len(valid_margins) >= 2
            else np.nan
        )
        ocf = pd.to_numeric(annual.get("operating_cf"), errors="coerce")
        ocf_positive_ratio = float((ocf > 0).mean()) if ocf.notna().any() else np.nan
        ocf_observed_years = int(ocf.notna().sum())
        ocf_positive_years = int((ocf > 0).sum()) if ocf.notna().any() else 0
        latest_ocf = _num(latest_actual.get("operating_cf"))
        cash_conversion_ratio = (
            latest_ocf / latest_op
            if latest_op and latest_op > 0 and not pd.isna(latest_ocf)
            else np.nan
        )
''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''        forecast_rows = all_rows.dropna(subset=["forecast_operating_profit"])
        forecast_row = forecast_rows.iloc[-1] if not forecast_rows.empty else latest_snapshot
        forecast_op = _num(forecast_row.get("forecast_operating_profit"))
        forecast_op_growth = (
            forecast_op / latest_op - 1
            if latest_op and latest_op > 0 and not pd.isna(forecast_op)
            else np.nan
        )
''',
    '''        forecast_values = pd.to_numeric(all_rows.get("forecast_operating_profit"), errors="coerce")
        forecast_rows = all_rows.loc[forecast_values.notna()].copy()
        forecast_revision_rate = np.nan
        forecast_revision_from = np.nan
        forecast_revision_target_year = np.nan
        if not forecast_rows.empty:
            forecast_fy = pd.to_numeric(forecast_rows.get("fiscal_year"), errors="coerce")
            statement_type = forecast_rows.get(
                "statement_type", pd.Series("", index=forecast_rows.index)
            ).astype(str).str.upper()
            forecast_rows["_forecast_target_year"] = forecast_fy
            fy_mask = statement_type.eq("FY") & forecast_fy.notna()
            forecast_rows.loc[fy_mask, "_forecast_target_year"] = forecast_fy.loc[fy_mask] + 1
            forecast_row = forecast_rows.iloc[-1]
            forecast_op = _num(forecast_row.get("forecast_operating_profit"))
            forecast_revision_target_year = _num(forecast_row.get("_forecast_target_year"))
            prior_rows = forecast_rows.iloc[:-1]
            if not pd.isna(forecast_revision_target_year):
                prior_rows = prior_rows.loc[
                    pd.to_numeric(prior_rows["_forecast_target_year"], errors="coerce").eq(
                        forecast_revision_target_year
                    )
                ]
            prior_values = pd.to_numeric(prior_rows.get("forecast_operating_profit"), errors="coerce")
            if isinstance(prior_values, pd.Series) and prior_values.notna().any():
                # If the latest disclosure simply repeats already-revised guidance, retain
                # the most recent different guidance so a prior downward revision is not lost.
                distinct = prior_rows.loc[
                    prior_values.notna()
                    & (~prior_values.eq(forecast_op))
                ]
                prior_row = distinct.iloc[-1] if not distinct.empty else prior_rows.iloc[-1]
                forecast_revision_from = _num(prior_row.get("forecast_operating_profit"))
                if forecast_revision_from and forecast_revision_from > 0 and not pd.isna(forecast_op):
                    forecast_revision_rate = forecast_op / forecast_revision_from - 1
        else:
            forecast_row = latest_snapshot
            forecast_op = _num(forecast_row.get("forecast_operating_profit"))
        forecast_op_growth = (
            forecast_op / latest_op - 1
            if latest_op and latest_op > 0 and not pd.isna(forecast_op)
            else np.nan
        )
''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''                "operating_margin": op_margin,
                "operating_profit_latest": latest_op,
                "operating_cf_positive_ratio_3y": ocf_positive_ratio,
''',
    '''                "operating_margin": op_margin,
                "operating_margin_change_3y": operating_margin_change_3y,
                "operating_profit_latest": latest_op,
                "cash_conversion_ratio": cash_conversion_ratio,
                "operating_cf_positive_ratio_3y": ocf_positive_ratio,
''',
)
replace_once(
    "src/value_dislocation/strategy/features.py",
    '''                "forecast_operating_profit": forecast_op,
                "forecast_op_growth": forecast_op_growth,
''',
    '''                "forecast_operating_profit": forecast_op,
                "forecast_op_growth": forecast_op_growth,
                "forecast_revision_rate": forecast_revision_rate,
                "forecast_revision_from": forecast_revision_from,
                "forecast_revision_target_year": forecast_revision_target_year,
''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''    merged = companies.merge(pf, on="code", how="inner").merge(ff, on="code", how="inner")
    if merged.empty:
        return merged
    for key, value in EVENT_PLACEHOLDERS.items():
''',
    '''    merged = companies.merge(pf, on="code", how="inner").merge(ff, on="code", how="inner")
    if merged.empty:
        return merged
    # A market-relative fall can be sector-wide rather than company-specific.  Keep
    # a separate same-sector context so unusually weak company-specific performance
    # can be treated as a possible structural problem rather than a bargain signal.
    merged["sector_peer_count_6m"] = merged.groupby("sector")["return_6m"].transform("count")
    merged["sector_return_6m_median"] = merged.groupby("sector")["return_6m"].transform("median")
    merged["sector_relative_return_6m"] = merged["return_6m"] - merged["sector_return_6m_median"]
    merged.loc[merged["sector_peer_count_6m"] < 5, "sector_relative_return_6m"] = np.nan
    for key, value in EVENT_PLACEHOLDERS.items():
''',
)

# --- Screening guard. Missing optional evidence warns but does not falsely reject.
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''    require_dividend = bool(s.get("require_dividend", False))
''',
    '''    use_structural_guard = bool(s.get("use_structural_deterioration_guard", True))
    cash_conversion = _numeric_series(scored, "cash_conversion_ratio", index)
    margin_change = _numeric_series(scored, "operating_margin_change_3y", index)
    forecast_revision = _numeric_series(scored, "forecast_revision_rate", index)
    sector_relative = _numeric_series(scored, "sector_relative_return_6m", index)
    if use_structural_guard:
        scored["pass_cash_conversion"] = cash_conversion.isna() | (
            cash_conversion >= float(s.get("minimum_cash_conversion_ratio", 0.70))
        )
        scored["pass_margin_stability"] = margin_change.isna() | (
            margin_change >= float(s.get("minimum_operating_margin_change_3y", -0.03))
        )
        scored["pass_forecast_revision"] = forecast_revision.isna() | (
            forecast_revision >= float(s.get("minimum_forecast_revision_rate", -0.10))
        )
        scored["pass_sector_relative"] = sector_relative.isna() | (
            sector_relative >= float(s.get("minimum_sector_relative_return_6m", -0.15))
        )
    else:
        for column in (
            "pass_cash_conversion", "pass_margin_stability",
            "pass_forecast_revision", "pass_sector_relative",
        ):
            scored[column] = True
    structural_columns = [
        "pass_cash_conversion", "pass_margin_stability",
        "pass_forecast_revision", "pass_sector_relative",
    ]
    scored["pass_structural_deterioration_guard"] = scored[structural_columns].all(axis=1)

    structural_labels = {
        "pass_cash_conversion": "利益の質（営業CF÷営業利益）",
        "pass_margin_stability": "営業利益率の悪化",
        "pass_forecast_revision": "会社予想の下方修正",
        "pass_sector_relative": "同業他社対比の異常な弱さ",
    }
    scored["structural_guard_failures"] = scored.apply(
        lambda row: " / ".join(
            label for column, label in structural_labels.items() if not bool(row.get(column, True))
        ),
        axis=1,
    )

    require_dividend = bool(s.get("require_dividend", False))
''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''    hard_columns = REQUIRED_CHECK_COLUMNS + ["pass_dividend_conditions"]
''',
    '''    hard_columns = REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard", "pass_dividend_conditions"]
''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''        ("pass_forecast", "会社予想"),
        ("pass_dividend_conditions", "配当条件"),
''',
    '''        ("pass_forecast", "会社予想"),
        ("pass_structural_deterioration_guard", "構造悪化ガード"),
        ("pass_dividend_conditions", "配当条件"),
''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''        if pd.isna(row.get("forecast_op_growth")):
            warnings.append("会社予想データなし")
''',
    '''        if pd.isna(row.get("forecast_op_growth")):
            warnings.append("会社予想データなし")
        if use_structural_guard:
            if pd.isna(row.get("cash_conversion_ratio")):
                warnings.append("利益現金化率データなし")
            if pd.isna(row.get("operating_margin_change_3y")):
                warnings.append("営業利益率の推移データ不足")
            if pd.isna(row.get("forecast_revision_rate")):
                warnings.append("比較可能な会社予想修正履歴なし")
            if pd.isna(row.get("sector_relative_return_6m")):
                warnings.append("同業比較に必要な6か月株価データ不足")
            failures = str(row.get("structural_guard_failures", "") or "").strip()
            if failures:
                warnings.append(f"構造悪化ガード不通過: {failures}")
''',
)
replace_once(
    "src/value_dislocation/strategy/criteria.py",
    '''            ("会社予想条件", REQUIRED_CHECK_COLUMNS),
            ("配当条件", REQUIRED_CHECK_COLUMNS + ["pass_dividend_conditions"]),
            ("定量スコア", REQUIRED_CHECK_COLUMNS + ["pass_dividend_conditions", "pass_quantitative_score"]),
''',
    '''            ("会社予想条件", REQUIRED_CHECK_COLUMNS),
            ("構造悪化ガード", REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard"]),
            ("配当条件", REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard", "pass_dividend_conditions"]),
            ("定量スコア", REQUIRED_CHECK_COLUMNS + ["pass_structural_deterioration_guard", "pass_dividend_conditions", "pass_quantitative_score"]),
''',
)

# --- Presets and metric help.
replace_once(
    "src/value_dislocation/strategy/profiles.py",
    '''    "minimum_operating_margin": "売上高に対する営業利益の割合です。0%以上なら少なくとも営業黒字です。",
    "maximum_forecast_op_decline": "会社予想の営業利益が直近実績からどこまで減っても許容するかです。",
''',
    '''    "minimum_operating_margin": "売上高に対する営業利益の割合です。0%以上なら少なくとも営業黒字です。",
    "minimum_cash_conversion_ratio": "直近通期の営業CF÷営業利益です。会計上の利益が現金を伴っているかを見る利益の質の指標です。",
    "minimum_operating_margin_change_3y": "直近最大3期で営業利益率がどこまで悪化してよいかの下限です。継続的な採算悪化を見つけます。",
    "minimum_forecast_revision_rate": "同じ対象年度の会社予想営業利益が前回予想からどこまで下方修正されても許容するかです。",
    "minimum_sector_relative_return_6m": "6か月騰落率を同業種中央値と比較し、企業固有に極端に弱い銘柄を構造悪化候補として除外する目安です。",
    "maximum_forecast_op_decline": "会社予想の営業利益が直近実績からどこまで減っても許容するかです。",
''',
)
for preset, cash, margin, revision, sector in [
    ("安全重視", 0.90, -0.02, -0.05, -0.10),
    ("標準", 0.70, -0.03, -0.10, -0.15),
    ("割安重視", 0.50, -0.05, -0.20, -0.20),
]:
    marker = f'''            "minimum_operating_margin": '''
    text = read("src/value_dislocation/strategy/profiles.py")
    start = text.index(f'    "{preset}":')
    next_start = text.find('\n    "', start + 8)
    end = next_start if next_start != -1 else len(text)
    block = text[start:end]
    old_line = [line for line in block.splitlines() if '"minimum_operating_margin"' in line][0]
    replacement = old_line + f'''\n            "use_structural_deterioration_guard": True,\n            "minimum_cash_conversion_ratio": {cash:.2f},\n            "minimum_operating_margin_change_3y": {margin:.2f},\n            "minimum_forecast_revision_rate": {revision:.2f},\n            "minimum_sector_relative_return_6m": {sector:.2f},'''
    new_block = block.replace(old_line, replacement, 1)
    write("src/value_dislocation/strategy/profiles.py", text[:start] + new_block + text[end:])

# --- YAML defaults.
def add_guard_yaml(path: str) -> None:
    replace_once(
        path,
        "  minimum_operating_margin: 0.00\n",
        "  minimum_operating_margin: 0.00\n"
        "  use_structural_deterioration_guard: true\n"
        "  minimum_cash_conversion_ratio: 0.70\n"
        "  minimum_operating_margin_change_3y: -0.03\n"
        "  minimum_forecast_revision_rate: -0.10\n"
        "  minimum_sector_relative_return_6m: -0.15\n",
    )

for yaml_path in ("config/real_data.yaml", "config/real_data.example.yaml"):
    add_guard_yaml(yaml_path)
# Demo config has fewer quality fields; keep identical guard semantics without requiring extra APIs.
replace_once(
    "config/default.yaml",
    "  minimum_equity_ratio: 0.30\n",
    "  minimum_equity_ratio: 0.30\n"
    "  use_structural_deterioration_guard: true\n"
    "  minimum_cash_conversion_ratio: 0.70\n"
    "  minimum_operating_margin_change_3y: -0.03\n"
    "  minimum_forecast_revision_rate: -0.10\n"
    "  minimum_sector_relative_return_6m: -0.15\n",
)

# --- Dashboard: rebuild old snapshots locally, expose controls and metrics.
replace_once(
    "dashboard.py",
    '''    required_feature_columns = {"volatility_60d", "average_intraday_range_20d", "average_absolute_return_20d"}
''',
    '''    required_feature_columns = {
        "volatility_60d", "average_intraday_range_20d", "average_absolute_return_20d",
        "cash_conversion_ratio", "operating_margin_change_3y",
        "forecast_revision_rate", "sector_relative_return_6m",
    }
''',
)
replace_once(
    "dashboard.py",
    '''    st.session_state["ui_op_margin_pct"] = int(round(s["minimum_operating_margin"] * 100))
    st.session_state["ui_forecast_decline_pct"] = int(round(-s["maximum_forecast_op_decline"] * 100))
''',
    '''    st.session_state["ui_op_margin_pct"] = int(round(s["minimum_operating_margin"] * 100))
    st.session_state["ui_use_structural_guard"] = bool(s.get("use_structural_deterioration_guard", True))
    st.session_state["ui_min_cash_conversion_pct"] = float(s.get("minimum_cash_conversion_ratio", 0.70)) * 100
    st.session_state["ui_max_margin_deterioration_pt"] = -float(s.get("minimum_operating_margin_change_3y", -0.03)) * 100
    st.session_state["ui_max_forecast_revision_decline_pct"] = -float(s.get("minimum_forecast_revision_rate", -0.10)) * 100
    st.session_state["ui_max_sector_underperformance_pct"] = -float(s.get("minimum_sector_relative_return_6m", -0.15)) * 100
    st.session_state["ui_forecast_decline_pct"] = int(round(-s["maximum_forecast_op_decline"] * 100))
''',
)
replace_once(
    "dashboard.py",
    '''    st.session_state.setdefault("ui_star_only", False)
''',
    '''    st.session_state.setdefault("ui_star_only", False)
    st.session_state.setdefault("ui_use_structural_guard", True)
    st.session_state.setdefault("ui_min_cash_conversion_pct", 70.0)
    st.session_state.setdefault("ui_max_margin_deterioration_pt", 3.0)
    st.session_state.setdefault("ui_max_forecast_revision_decline_pct", 10.0)
    st.session_state.setdefault("ui_max_sector_underperformance_pct", 15.0)
''',
)
replace_once(
    "dashboard.py",
    '''            "minimum_operating_margin": float(st.session_state["ui_op_margin_pct"]) / 100,
            "maximum_forecast_op_decline": -float(st.session_state["ui_forecast_decline_pct"]) / 100,
''',
    '''            "minimum_operating_margin": float(st.session_state["ui_op_margin_pct"]) / 100,
            "use_structural_deterioration_guard": bool(st.session_state["ui_use_structural_guard"]),
            "minimum_cash_conversion_ratio": float(st.session_state["ui_min_cash_conversion_pct"]) / 100,
            "minimum_operating_margin_change_3y": -float(st.session_state["ui_max_margin_deterioration_pt"]) / 100,
            "minimum_forecast_revision_rate": -float(st.session_state["ui_max_forecast_revision_decline_pct"]) / 100,
            "minimum_sector_relative_return_6m": -float(st.session_state["ui_max_sector_underperformance_pct"]) / 100,
            "maximum_forecast_op_decline": -float(st.session_state["ui_forecast_decline_pct"]) / 100,
''',
)
replace_once(
    "dashboard.py",
    '''        st.markdown("### 2. 配当条件")
''',
    '''        st.markdown("### 2. 構造悪化ガード（バリュートラップ回避）")
        use_structural_guard = st.checkbox(
            "利益の質・採算悪化・会社予想修正・同業比較を必須チェックにする",
            value=bool(st.session_state["ui_use_structural_guard"]),
            disabled=active_mode,
            help="過去業績が良くても企業固有の構造悪化が進んでいる銘柄を除外します。データ欠損だけでは除外せず警告します。",
        )
        sg1, sg2, sg3, sg4 = st.columns(4)
        with sg1:
            min_cash_conversion_pct = st.slider(
                "最低 利益現金化率（%）", -100.0, 300.0,
                value=float(st.session_state["ui_min_cash_conversion_pct"]), step=5.0,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_cash_conversion_ratio"],
            )
        with sg2:
            max_margin_deterioration_pt = st.slider(
                "営業利益率の最大悪化幅（pt）", 0.0, 20.0,
                value=float(st.session_state["ui_max_margin_deterioration_pt"]), step=0.5,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_operating_margin_change_3y"],
            )
        with sg3:
            max_forecast_revision_decline_pct = st.slider(
                "会社予想の最大下方修正率（%）", 0.0, 50.0,
                value=float(st.session_state["ui_max_forecast_revision_decline_pct"]), step=1.0,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_forecast_revision_rate"],
            )
        with sg4:
            max_sector_underperformance_pct = st.slider(
                "同業中央値への最大劣後率（6か月・%）", 0.0, 40.0,
                value=float(st.session_state["ui_max_sector_underperformance_pct"]), step=1.0,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_sector_relative_return_6m"],
            )
        st.caption("利益現金化率=営業CF÷営業利益。営業利益率の悪化幅は直近最大3期、会社予想修正は同じ対象年度の前回予想比、同業比較は同業種の6か月騰落率中央値比です。")

        st.markdown("### 3. 配当条件")
''',
)
replace_once("dashboard.py", '        st.markdown("### 3. 市場比較・相対条件")\n', '        st.markdown("### 4. 市場比較・相対条件")\n')
replace_once("dashboard.py", '        st.markdown("### 4. 値動き活発型の条件")\n', '        st.markdown("### 5. 値動き活発型の条件")\n')
replace_once("dashboard.py", '        st.markdown("### 5. 順位付けと表示件数")\n', '        st.markdown("### 6. 順位付けと表示件数")\n')
replace_once(
    "dashboard.py",
    '''            "ui_forecast_decline_pct": forecast_decline,
            "ui_require_forecast": require_forecast, "ui_drawdown_pct": drawdown,
''',
    '''            "ui_forecast_decline_pct": forecast_decline,
            "ui_use_structural_guard": use_structural_guard,
            "ui_min_cash_conversion_pct": min_cash_conversion_pct,
            "ui_max_margin_deterioration_pt": max_margin_deterioration_pt,
            "ui_max_forecast_revision_decline_pct": max_forecast_revision_decline_pct,
            "ui_max_sector_underperformance_pct": max_sector_underperformance_pct,
            "ui_require_forecast": require_forecast, "ui_drawdown_pct": drawdown,
''',
)
replace_once(
    "dashboard.py",
    '''        st.write(f"通過理由: {row.get('pass_reasons', '')}")
        st.write(f"注意: {row.get('warning_reasons', '')}")
''',
    '''        quality_cols = st.columns(4)
        quality_cols[0].metric("利益現金化率", _format_pct(row.get("cash_conversion_ratio")))
        quality_cols[1].metric("営業利益率変化", _format_pct(row.get("operating_margin_change_3y")))
        quality_cols[2].metric("会社予想修正", _format_pct(row.get("forecast_revision_rate")))
        quality_cols[3].metric("同業中央値対比", _format_pct(row.get("sector_relative_return_6m")))
        st.write(f"通過理由: {row.get('pass_reasons', '')}")
        st.write(f"注意: {row.get('warning_reasons', '')}")
''',
)

# --- Buy readiness: known deterioration becomes a blocker; unknown data stays unknown.
replace_once(
    "src/value_dislocation/decision/buy_readiness.py",
    '''    ocf = _number(metrics.get("operating_cf_positive_ratio_3y"))
    forecast = _number(metrics.get("forecast_op_growth"))
''',
    '''    ocf = _number(metrics.get("operating_cf_positive_ratio_3y"))
    cash_quality = _number(metrics.get("cash_conversion_ratio"))
    margin_change = _number(metrics.get("operating_margin_change_3y"))
    forecast_revision = _number(metrics.get("forecast_revision_rate"))
    sector_relative = _number(metrics.get("sector_relative_return_6m"))
    forecast = _number(metrics.get("forecast_op_growth"))
''',
)
replace_once(
    "src/value_dislocation/decision/buy_readiness.py",
    '''        _check("ocf", "現金創出の継続性", ocf, lambda x: x >= 0.999, lambda x: x >= 0.66,
               f"営業CFプラス比率 {ocf:.0%}" if ocf is not None else "営業CF履歴", 12),
        _check("forecast", "会社予想", forecast, lambda x: x >= 0, lambda x: x >= -0.15,
''',
    '''        _check("ocf", "現金創出の継続性", ocf, lambda x: x >= 0.999, lambda x: x >= 0.66,
               f"営業CFプラス比率 {ocf:.0%}" if ocf is not None else "営業CF履歴", 12),
        _check("cash_quality", "利益の質", cash_quality, lambda x: x >= 0.80, lambda x: x >= 0.50,
               f"営業CF÷営業利益 {cash_quality:.0%}" if cash_quality is not None else "利益現金化率", 8),
        _check("margin_stability", "採算の安定性", margin_change, lambda x: x >= -0.02, lambda x: x >= -0.05,
               f"営業利益率変化 {margin_change:+.1%}" if margin_change is not None else "営業利益率変化", 6),
        _check("forecast_revision", "会社予想の修正方向", forecast_revision, lambda x: x >= -0.05, lambda x: x >= -0.15,
               f"同一年度の前回予想比 {forecast_revision:+.1%}" if forecast_revision is not None else "会社予想修正", 8),
        _check("sector_relative", "同業他社対比", sector_relative, lambda x: x >= -0.10, lambda x: x >= -0.20,
               f"業種中央値比 {sector_relative:+.1%}" if sector_relative is not None else "業種中央値比", 6),
        _check("forecast", "会社予想", forecast, lambda x: x >= 0, lambda x: x >= -0.15,
''',
)
replace_once(
    "src/value_dislocation/decision/buy_readiness.py",
    '''    hard_failure_keys = {"equity", "ocf", "forecast", "margin", "trend"}
''',
    '''    hard_failure_keys = {
        "equity", "ocf", "cash_quality", "margin_stability",
        "forecast_revision", "sector_relative", "forecast", "margin", "trend",
    }
''',
)
replace_once(
    "src/value_dislocation/decision/buy_readiness.py",
    '''    core_checks = [item for item in checks if item.get("key") in core_keys]
    core_clear = bool(core_checks) and all(item.get("status") == "pass" for item in core_checks)
    has_failure = any(item.get("status") == "fail" for item in checks)
''',
    '''    core_checks = [item for item in checks if item.get("key") in core_keys]
    structural_keys = {"cash_quality", "margin_stability", "forecast_revision", "sector_relative"}
    structural_checks = [item for item in checks if item.get("key") in structural_keys]
    # Missing optional structural evidence does not fabricate a failure, but a known
    # warn/fail blocks the highest ◎☆ quality badge until the concern is resolved.
    structural_clear = all(item.get("status") in {"pass", "unknown"} for item in structural_checks)
    core_clear = (
        bool(core_checks)
        and all(item.get("status") == "pass" for item in core_checks)
        and structural_clear
    )
    has_failure = any(item.get("status") == "fail" for item in checks)
''',
)

# --- Persist/expose metrics for point-in-time validation and invalidation rules.
replace_once(
    "src/value_dislocation/history.py",
    '''    "close", "drawdown_52w", "relative_return_6m", "sales_cagr_3y", "operating_margin",
    "operating_cf_positive_ratio_3y", "equity_ratio", "forecast_op_growth",
''',
    '''    "close", "drawdown_52w", "relative_return_6m", "sector_relative_return_6m",
    "sales_cagr_3y", "operating_margin", "operating_margin_change_3y",
    "operating_cf_positive_ratio_3y", "cash_conversion_ratio", "equity_ratio",
    "forecast_op_growth", "forecast_revision_rate",
''',
)
replace_once(
    "src/value_dislocation/history.py",
    '''    ("会社予想営業利益が増益", "forecast_op_growth", ">=", 0.0),
''',
    '''    ("会社予想営業利益が増益", "forecast_op_growth", ">=", 0.0),
    ("利益現金化率 80%以上", "cash_conversion_ratio", ">=", 0.80),
    ("営業利益率の悪化 3pt以内", "operating_margin_change_3y", ">=", -0.03),
    ("会社予想の下方修正 10%以内", "forecast_revision_rate", ">=", -0.10),
    ("業種中央値への劣後 15%以内", "sector_relative_return_6m", ">=", -0.15),
''',
)
replace_once(
    "src/value_dislocation/strategy/quantitative.py",
    '''        "operating_margin", "operating_cf_positive_ratio_3y", "equity_ratio",
        "forecast_op_growth", "pass_reasons", "warning_reasons", "data_limitations",
''',
    '''        "operating_margin", "operating_margin_change_3y", "operating_cf_positive_ratio_3y",
        "cash_conversion_ratio", "equity_ratio", "forecast_op_growth", "forecast_revision_rate",
        "sector_relative_return_6m", "pass_reasons", "warning_reasons", "data_limitations",
''',
)
replace_once(
    "src/value_dislocation/hypothesis_invalidation.py",
    '''    "operating_margin": {"label": "営業利益率", "unit": "%", "scale": "percent"},
    "operating_profit_latest": {"label": "直近営業利益", "unit": "円", "scale": "raw"},
''',
    '''    "operating_margin": {"label": "営業利益率", "unit": "%", "scale": "percent"},
    "operating_margin_change_3y": {"label": "営業利益率変化（直近最大3期）", "unit": "%", "scale": "percent"},
    "cash_conversion_ratio": {"label": "利益現金化率（営業CF÷営業利益）", "unit": "%", "scale": "percent"},
    "forecast_revision_rate": {"label": "会社予想営業利益の修正率", "unit": "%", "scale": "percent"},
    "sector_relative_return_6m": {"label": "6か月騰落率の業種中央値比", "unit": "%", "scale": "percent"},
    "operating_profit_latest": {"label": "直近営業利益", "unit": "円", "scale": "raw"},
''',
)

# --- Versions and docs.
replace_once("pyproject.toml", 'version = "0.6.61"', 'version = "0.6.62"')
replace_once("src/value_dislocation/__init__.py", '__version__ = "0.6.61"', '__version__ = "0.6.62"')
replace_once("tests/test_package_init.py", 'assert value_dislocation.__version__ == "0.6.61"', 'assert value_dislocation.__version__ == "0.6.62"')
replace_once("README.md", 'Version: **0.6.61**', 'Version: **0.6.62**')
replace_once(
    "README.md",
    '''### v0.6.61 ◎☆を反転確認済みの最上位評価へ厳格化
''',
    '''### v0.6.62 構造悪化ガードでバリュートラップを識別

- 「外的要因で安い」と「企業固有の悪化で安い」を切り分けるため、利益現金化率、営業利益率の悪化幅、会社予想の修正方向、6か月騰落率の業種中央値比を追加しました。
- 既存の標準設定では、利益現金化率70%以上、営業利益率悪化3pt以内、会社予想下方修正10%以内、業種中央値への劣後15%以内を目安にします。
- 指標が取得できないだけでは除外せず警告し、取得できた指標が明確に悪い場合のみ構造悪化ガードで除外します。
- 新指標は履歴・条件別実績にも保存しますが、自動ルール学習の対象にはまだ加えず、前向き実績が蓄積してから有効性を検証します。
- J-Quantsで有利子負債を安定取得できないため、負債レバレッジは今回の必須条件にはしていません。

### v0.6.61 ◎☆を反転確認済みの最上位評価へ厳格化
''',
)
write(
    "CHANGELOG.md",
    '''## v0.6.62
- 利益現金化率（営業CF÷営業利益）、営業利益率の直近最大3期変化、同一対象年度の会社予想修正率、6か月騰落率の業種中央値比を追加。
- 4指標を「構造悪化ガード」として候補抽出へ追加。欠損は警告扱い、既知の悪化だけを除外する。
- 個別の購入判断整理と◎☆品質判定にも新指標を反映し、既知の構造悪化が最上位評価へ上がらないようにした。
- 新指標をpoint-in-time履歴、外的要因レビューキュー、仮説無効化条件へ追加。追加API取得は行わない。
- 有利子負債はJ-Quants決算サマリーでは欠損のため、レバレッジ必須判定はEDINET補完まで保留。

''' + read("CHANGELOG.md"),
)
write(
    "docs/21_STRUCTURAL_DETERIORATION_GUARDS.md",
    '''# v0.6.62 構造悪化ガード

## 目的

このシステムは「外的要因で株価が低迷しているが、本業は壊れていない企業」を探します。過去業績が黒字というだけでは、利益の質低下・採算悪化・会社予想の下方修正・企業固有の株価弱さを見逃し、バリュートラップを拾う可能性があります。

## 追加指標

1. **利益現金化率 (`cash_conversion_ratio`)**: 直近通期の営業CF÷営業利益。標準70%以上。
2. **営業利益率変化 (`operating_margin_change_3y`)**: 直近最大3期の最新利益率−最古利益率。標準は3ポイント超の悪化を除外。
3. **会社予想修正率 (`forecast_revision_rate`)**: 同じ対象年度の最新会社予想営業利益÷前回の異なる予想−1。標準は10%超の下方修正を除外。
4. **業種中央値比 (`sector_relative_return_6m`)**: 銘柄の6か月騰落率−同業種中央値。5銘柄以上の比較対象がある場合に算出し、標準は15%超の劣後を除外。

## 欠損時の扱い

新指標が取得できないこと自体は不合格にしません。候補を誤って消さず、`warning_reasons` に不足を表示します。一方、値が取得できて閾値を下回る場合は「企業固有の構造悪化の可能性」として候補から除外します。

## スコアと自動学習

既存の定量スコア配点は変更しません。新指標はハードガードと購入判断整理に追加し、過去スコアとの比較可能性を維持します。また、前向き実績がない段階で過学習しないよう、自動ルール学習の対象にはまだ追加しません。履歴には保存するため、10/20/30/60/90/180日実績が蓄積した後に有効性を検証できます。

## 負債レバレッジ

財務レバレッジも重要ですが、現在のJ-Quants決算サマリー正規化では有利子負債を欠損として扱っています。欠損を0と誤認しないため、今回は必須ガードに含めません。EDINET等で安定補完できる段階で追加する候補とします。
''',
)
# Prepend completed task section.
write(
    "tasks/CURRENT.md",
    '''## v0.6.62 structural deterioration guards

- [x] 利益現金化率（営業CF÷営業利益）を追加する。
- [x] 営業利益率の直近最大3期の悪化幅を追加する。
- [x] 同一対象年度の会社予想営業利益の修正率を追加する。
- [x] 6か月騰落率の業種中央値比を追加する。
- [x] 欠損は警告、既知の明確な悪化だけを除外する構造悪化ガードを追加する。
- [x] 履歴・仮説無効化・購入判断整理へ新指標を連携する。
- [x] 追加API取得やSBI安全境界の変更を行わない。

''' + read("tasks/CURRENT.md"),
)

# --- Blueprint contract.
replace_once("harness/app_blueprint.yaml", "blueprint_version: 0.6.61", "blueprint_version: 0.6.62")
replace_once(
    "harness/app_blueprint.yaml",
    "- reversal_confirmed_quality_star\n",
    "- reversal_confirmed_quality_star\n- structural_deterioration_value_trap_guard\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- quality_star_must_require_confirmed_short_term_reversal\n",
    "- quality_star_must_require_confirmed_short_term_reversal\n- known_structural_deterioration_must_block_value_dislocation_candidate\n- missing_structural_guard_metric_must_warn_not_fabricate_failure\n",
)
replace_once(
    "harness/app_blueprint.yaml",
    "- docs/19_PERFORMANCE_OPTIMIZATION.md\n",
    "- docs/19_PERFORMANCE_OPTIMIZATION.md\n- docs/21_STRUCTURAL_DETERIORATION_GUARDS.md\n",
)

# --- README structure test.
replace_once("tests/test_sort_performance_and_readme_structure.py", 'assert lines[2] == "Version: **0.6.61**"', 'assert lines[2] == "Version: **0.6.62**"')
replace_once(
    "tests/test_sort_performance_and_readme_structure.py",
    '''    versions = [
        "### v0.6.61 ◎☆を反転確認済みの最上位評価へ厳格化",
''',
    '''    versions = [
        "### v0.6.62 構造悪化ガードでバリュートラップを識別",
        "### v0.6.61 ◎☆を反転確認済みの最上位評価へ厳格化",
''',
)

# --- Regression tests.
write(
    "tests/test_structural_deterioration_guards.py",
    '''from __future__ import annotations

import numpy as np
import pandas as pd

from value_dislocation.decision.buy_readiness import build_buy_readiness
from value_dislocation.strategy.criteria import apply_quantitative_criteria, prepare_quantitative_universe
from value_dislocation.strategy.features import financial_features


def _financial_rows() -> pd.DataFrame:
    rows = []
    for year, sales, op, cfo, forecast, kind, disclosed in [
        (2022, 1_000.0, 100.0, 90.0, np.nan, "FY", "2023-05-10"),
        (2023, 1_050.0, 94.5, 90.0, np.nan, "FY", "2024-05-10"),
        # FY2024 forecast is for FY2025.
        (2024, 1_100.0, 88.0, 70.4, 120.0, "FY", "2025-05-10"),
        # Q1 FY2025 forecasts the same FY2025 and revises it downward.
        (2025, 300.0, 15.0, np.nan, 90.0, "1Q", "2025-08-10"),
    ]:
        rows.append({
            "code": "11110", "disclosure_date": pd.Timestamp(disclosed),
            "statement_type": kind, "period_end": pd.Timestamp(f"{year}-03-31"),
            "fiscal_year": year, "is_full_year_actual": kind == "FY",
            "sales": sales, "operating_profit": op, "operating_cf": cfo,
            "total_assets": 2_000.0, "equity": 1_000.0, "cash": 300.0,
            "interest_bearing_debt": np.nan, "eps": 100.0,
            "book_value_per_share": 500.0, "forecast_operating_profit": forecast,
        })
    return pd.DataFrame(rows)


def test_financial_features_measure_cash_quality_margin_deterioration_and_revision():
    f = financial_features(_financial_rows(), pd.Timestamp("2025-09-01"))
    row = f.iloc[0]
    assert row["cash_conversion_ratio"] == pytest.approx(0.8)
    assert row["operating_margin_change_3y"] == pytest.approx(-0.02)
    assert row["forecast_revision_rate"] == pytest.approx(-0.25)
    assert row["forecast_revision_target_year"] == pytest.approx(2025)


def _companies() -> pd.DataFrame:
    return pd.DataFrame({
        "code": [f"{i:04d}0" for i in range(1, 7)],
        "name": [f"C{i}" for i in range(1, 7)],
        "sector": ["TestSector"] * 6,
        "market": ["Prime"] * 6,
        "shares_outstanding": [1_000_000] * 6,
    })


def _prices() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=150)
    frames = []
    # First stock is much weaker than its peers.
    endings = [70.0, 100.0, 102.0, 104.0, 106.0, 108.0]
    for code, ending in zip(_companies()["code"], endings):
        close = np.linspace(100.0, ending, len(dates))
        frames.append(pd.DataFrame({
            "date": dates, "code": code, "open": close, "high": close * 1.01,
            "low": close * 0.99, "close": close, "volume": 100_000,
            "turnover_yen": close * 100_000,
        }))
    return pd.concat(frames, ignore_index=True)


def _financials_for_universe() -> pd.DataFrame:
    base = _financial_rows()
    frames = []
    for code in _companies()["code"]:
        copy = base.copy()
        copy["code"] = code
        # Avoid forecast-revision failure here; this test targets sector context.
        copy.loc[copy["statement_type"].eq("1Q"), "forecast_operating_profit"] = 120.0
        frames.append(copy)
    return pd.concat(frames, ignore_index=True)


def _config() -> dict:
    return {
        "universe": {"allowed_markets": ["Prime"], "min_average_turnover_yen_20d": 0, "min_price_yen": 0},
        "screen": {
            "minimum_equity_ratio": 0.0, "minimum_operating_cf_positive_ratio_3y": 0.0,
            "minimum_sales_cagr_3y": -1.0, "minimum_operating_margin": -1.0,
            "maximum_forecast_op_decline": -1.0, "require_forecast": False,
            "minimum_drawdown_52w": 0.0, "minimum_relative_underperformance_6m": -1.0,
            "use_relative_underperformance_filter": False, "market_benchmark_mode": "disabled",
            "relative_filter_when_topix_missing": "skip_with_warning", "quantitative_min_score": 0,
            "use_structural_deterioration_guard": True,
            "minimum_cash_conversion_ratio": 0.70,
            "minimum_operating_margin_change_3y": -0.03,
            "minimum_forecast_revision_rate": -0.10,
            "minimum_sector_relative_return_6m": -0.15,
            "require_dividend": False,
        },
    }


def test_sector_relative_weakness_blocks_company_specific_laggard():
    prepared = prepare_quantitative_universe(
        _companies(), _prices(), _financials_for_universe(), _prices()["date"].max()
    )
    weak = prepared.loc[prepared["code"].eq("00010")].iloc[0]
    assert weak["sector_peer_count_6m"] == 6
    assert weak["sector_relative_return_6m"] < -0.15
    evaluated = apply_quantitative_criteria(prepared, _config())
    weak_evaluated = evaluated.loc[evaluated["code"].eq("00010")].iloc[0]
    assert not bool(weak_evaluated["pass_structural_deterioration_guard"])
    assert "同業他社対比" in weak_evaluated["structural_guard_failures"]
    assert not bool(weak_evaluated["selected_for_review"])


def test_missing_structural_metric_warns_without_fabricating_failure():
    prepared = prepare_quantitative_universe(
        _companies(), _prices(), _financials_for_universe(), _prices()["date"].max()
    ).drop(columns=["forecast_revision_rate"])
    cfg = _config()
    cfg["screen"]["minimum_sector_relative_return_6m"] = -1.0
    evaluated = apply_quantitative_criteria(prepared, cfg)
    row = evaluated.iloc[0]
    assert bool(row["pass_forecast_revision"])
    assert "比較可能な会社予想修正履歴なし" in row["warning_reasons"]


def test_known_bad_cash_quality_is_a_buy_readiness_blocker():
    readiness = build_buy_readiness({
        "drawdown_52w": -0.25, "relative_return_6m": -0.10,
        "sales_cagr_3y": 0.03, "operating_margin": 0.08, "equity_ratio": 0.50,
        "operating_cf_positive_ratio_3y": 1.0, "cash_conversion_ratio": 0.20,
        "operating_margin_change_3y": 0.0, "forecast_revision_rate": 0.0,
        "sector_relative_return_6m": 0.0, "forecast_op_growth": 0.05,
    }, external_quote_available=True)
    checks = {item["key"]: item for item in readiness["checks"]}
    assert checks["cash_quality"]["status"] == "fail"
    assert readiness["decision_level"] == "stop"


# pytest is imported late to keep the fixture data visually compact above.
import pytest
''',
)

print("v0.6.62 patch applied")
