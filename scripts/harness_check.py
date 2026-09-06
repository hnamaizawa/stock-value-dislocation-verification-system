from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


REQUIRED_DOCS = [
    "AGENTS.md",
    "HARNESS.md",
    "docs/01_PROJECT_CHARTER.md",
    "docs/02_CURRENT_STATUS.md",
    "docs/03_TARGET_ARCHITECTURE.md",
    "docs/04_DATA_SOURCES.md",
    "docs/05_DATA_CONTRACTS.md",
    "docs/06_STRATEGY_AND_RESEARCH.md",
    "docs/07_RISK_AND_ORDER_GATES.md",
    "docs/08_SECURITY_AND_COMPLIANCE.md",
    "docs/09_TEST_AND_VALIDATION.md",
    "docs/10_OPERATIONS_RUNBOOK.md",
    "docs/11_ROADMAP.md",
    "docs/12_DECISIONS.md",
    "docs/13_KNOWN_ISSUES.md",
    "docs/14_DEFINITION_OF_DONE.md",
    "docs/15_SOURCE_REGISTER.md",
    "docs/16_APP_GENERATOR.md",
    "docs/17_BEGINNER_CONDITION_UI.md",
    "tasks/CURRENT.md",
    "tasks/BACKLOG.md",
]

REQUIRED_REAL_FILES = [
    "run_real.cmd",
    "dashboard.py",
    "config/real_data.yaml",
    "harness/app_blueprint.yaml",
    "scripts/generate_app.py",
    "src/value_dislocation/data/jquants.py",
    "src/value_dislocation/data/search.py",
    "src/value_dislocation/data/latest_quote.py",
    "src/value_dislocation/data/snapshot.py",
    "src/value_dislocation/real_pipeline.py",
    "src/value_dislocation/strategy/criteria.py",
    "src/value_dislocation/strategy/profiles.py",
    "src/value_dislocation/external_event_review.py",
    "src/value_dislocation/hypothesis_invalidation.py",
    "src/value_dislocation/history.py",
]

TEXT_SUFFIXES = {".py", ".ps1", ".cmd", ".yaml", ".yml", ".toml", ".md"}
SKIP_DIRS = {".venv", ".git", ".pytest_cache", "__pycache__", "generated"}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def check_required_files(root: Path) -> CheckResult:
    required = REQUIRED_DOCS + REQUIRED_REAL_FILES
    missing = [p for p in required if not (root / p).exists()]
    return CheckResult("required_files", not missing, "missing=" + ", ".join(missing) if missing else "ok")


def check_demo_isolation(root: Path) -> CheckResult:
    cfg = yaml.safe_load((root / "config/default.yaml").read_text(encoding="utf-8"))
    paths = cfg.get("paths", {})
    values = [str(paths.get(k, "")) for k in ("companies", "prices", "financials", "events")]
    passed = all(v.startswith("data/sample/") for v in values)
    return CheckResult("demo_isolation", passed, str(values))


def check_real_data_contract(root: Path) -> CheckResult:
    cfg = yaml.safe_load((root / "config/real_data.yaml").read_text(encoding="utf-8"))
    provider = cfg.get("providers", {}).get("jquants", {})
    runtime = cfg.get("runtime", {})
    paths = cfg.get("paths", {})
    actual_paths = [str(paths.get(k, "")) for k in ("companies", "prices", "financials")]
    passed = (
        cfg.get("mode") == "paper"
        and provider.get("enabled") is True
        and provider.get("api_key_env") == "JQUANTS_API_KEY"
        and provider.get("include_topix") is True
        and runtime.get("reject_sample_data") is True
        and all("data/sample" not in p for p in actual_paths)
        and all(p.startswith("data/curated/latest/") for p in actual_paths)
    )
    return CheckResult(
        "real_data_contract",
        passed,
        json.dumps({"provider": provider, "runtime": runtime, "paths": actual_paths}, ensure_ascii=False),
    )


def check_real_safety(root: Path) -> CheckResult:
    cfg = yaml.safe_load((root / "config/real_data.yaml").read_text(encoding="utf-8"))
    safety = cfg.get("safety", {})
    orders = cfg.get("orders", {})
    passed = (
        safety.get("order_transmission_enabled") is False
        and safety.get("allow_browser_automation") is False
        and safety.get("allow_sbi_credentials") is False
        and safety.get("require_human_event_approval") is True
        and safety.get("require_human_order_approval") is True
        and orders.get("mode") == "preview_only"
        and orders.get("execution_channel") == "manual_sbi"
        and orders.get("generation_enabled") is False
    )
    return CheckResult("real_data_safety", passed, json.dumps({"safety": safety, "orders": orders}, ensure_ascii=False))


def check_provenance_implementation(root: Path) -> CheckResult:
    jquants = (root / "src/value_dislocation/data/jquants.py").read_text(encoding="utf-8")
    snapshot = (root / "src/value_dislocation/data/snapshot.py").read_text(encoding="utf-8")
    pipeline = (root / "src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    required_terms = [
        '"actual_data": True',
        '"sample_data": False',
        '"provider": "J-Quants API V2"',
        "write_manifest",
        "sha256",
        "data_cutoff_at",
        "orders_generated",
        '"order_transmission": False',
    ]
    combined = jquants + snapshot + pipeline
    missing = [term for term in required_terms if term not in combined]
    return CheckResult("actual_data_provenance", not missing, "missing=" + ", ".join(missing) if missing else "ok")


def check_jquants_price_api_contract(root: Path) -> CheckResult:
    text = (root / "src/value_dislocation/data/jquants.py").read_text(encoding="utf-8")
    required = [
        "get_eq_bars_daily",
        "date_yyyymmdd=",
        "_fetch_equity_bars_range",
        "adaptive_serial_resumable",
        "v2_eq_bars_daily",
    ]
    missing = [term for term in required if term not in text]
    invalid_from_to = re.search(
        r"get_eq_bars_daily\(\s*from_yyyymmdd\s*=", text, flags=re.MULTILINE
    )
    concurrent_range_call = re.search(
        r"\.get_eq_bars_daily_range\(", text, flags=re.MULTILINE
    )
    passed = not missing and invalid_from_to is None and concurrent_range_call is None
    detail = {
        "missing": missing,
        "invalid_from_to_only_call": bool(invalid_from_to),
        "concurrent_range_call": bool(concurrent_range_call),
    }
    return CheckResult("jquants_v2_price_contract", passed, json.dumps(detail))


def check_jquants_rate_limit_resilience(root: Path) -> CheckResult:
    cfg = yaml.safe_load((root / "config/real_data.yaml").read_text(encoding="utf-8"))
    provider = cfg.get("providers", {}).get("jquants", {})
    rate = provider.get("rate_limit", {})
    text = (root / "src/value_dislocation/data/jquants.py").read_text(encoding="utf-8")
    required_terms = [
        "_call_with_rate_limit",
        "_fetch_financial_summary_range",
        "rate_limited_interval_seconds",
        "initial_backoff_seconds",
        "Completed days remain in the local cache",
        ".empty",
    ]
    missing = [term for term in required_terms if term not in text]
    passed = (
        rate.get("strategy") == "adaptive_serial_resumable"
        and float(rate.get("initial_interval_seconds", 0)) >= 12
        and float(rate.get("rate_limited_interval_seconds", 0)) >= 15
        and int(rate.get("max_attempts", 0)) >= 3
        and float(rate.get("initial_backoff_seconds", 0)) >= 60
        and rate.get("skip_weekends") is True
        and not missing
    )
    return CheckResult(
        "jquants_rate_limit_resilience",
        passed,
        json.dumps({"rate_limit": rate, "missing": missing}, ensure_ascii=False),
    )


def check_jquants_subscription_coverage(root: Path) -> CheckResult:
    text = (root / "src/value_dislocation/data/jquants.py").read_text(encoding="utf-8")
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    required_terms = [
        "_parse_subscription_coverage_error",
        "_discover_subscription_window",
        "effective_price_start",
        "effective_price_end",
        "effective_financial_start",
        "subscription_coverage",
        "Requested price end",
    ]
    missing = [term for term in required_terms if term not in text]
    dashboard_missing = [
        term
        for term in ("subscription_coverage_end", "契約データ上限日")
        if term not in dashboard
    ]
    return CheckResult(
        "jquants_subscription_coverage",
        not missing and not dashboard_missing,
        json.dumps(
            {"missing_source": missing, "missing_dashboard": dashboard_missing},
            ensure_ascii=False,
        ),
    )



def check_topix_no_substitution(root: Path) -> CheckResult:
    features = (root / "src/value_dislocation/strategy/features.py").read_text(encoding="utf-8")
    criteria = (root / "src/value_dislocation/strategy/criteria.py").read_text(encoding="utf-8")
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    forbidden_pattern = r"relative_return_6m\s*=\s*return_6m\s*(?:$|#)"
    required = [
        "relative_return_6m = np.nan",
        "topix_available",
        "topix_proxy_available",
        "relative_filter_when_topix_missing",
        "正式TOPIX",
        "TOPIX連動ETF",
        "正式TOPIXではありません",
    ]
    combined = features + criteria + dashboard
    missing = [term for term in required if term not in combined]
    forbidden_found = re.search(forbidden_pattern, features, flags=re.MULTILINE) is not None
    passed = not forbidden_found and not missing
    return CheckResult(
        "topix_no_substitution",
        passed,
        json.dumps({"forbidden_found": forbidden_found, "missing": missing}, ensure_ascii=False),
    )


def check_explainable_screening(root: Path) -> CheckResult:
    criteria = (root / "src/value_dislocation/strategy/criteria.py").read_text(encoding="utf-8")
    pipeline = (root / "src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    required = [
        "pass_reasons", "fail_reasons", "warning_reasons", "screening_funnel",
        "quantitative_audit_latest.csv", "候補になった理由",
    ]
    combined = criteria + pipeline + dashboard
    missing = [term for term in required if term not in combined]
    return CheckResult("explainable_screening", not missing, "missing=" + ", ".join(missing) if missing else "ok")


def check_data_freshness_gate(root: Path) -> CheckResult:
    cfg = yaml.safe_load((root / "config/real_data.yaml").read_text(encoding="utf-8"))
    pipeline = (root / "src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    max_age = cfg.get("runtime", {}).get("max_data_age_days_for_order_preview")
    required = ["data_age_days", "data_fresh_enough_for_order_preview", "order_preview_eligible"]
    missing = [term for term in required if term not in pipeline + dashboard]
    passed = isinstance(max_age, int) and max_age > 0 and not missing
    return CheckResult(
        "data_freshness_gate", passed,
        json.dumps({"max_age": max_age, "missing": missing}, ensure_ascii=False),
    )


def check_beginner_condition_ui(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    profiles = (root / "src/value_dislocation/strategy/profiles.py").read_text(encoding="utf-8")
    criteria = (root / "src/value_dislocation/strategy/criteria.py").read_text(encoding="utf-8")
    required = [
        "安全重視", "標準", "割安重視", "条件設定・候補",
        "st.slider", "st.multiselect", "apply_quantitative_criteria",
        "prepare_quantitative_universe", "save_profile", "load_profile",
        "設定JSONをダウンロード", "候補CSVをダウンロード",
    ]
    combined = dashboard + profiles + criteria
    missing = [term for term in required if term not in combined]
    return CheckResult(
        "beginner_condition_ui", not missing,
        "missing=" + ", ".join(missing) if missing else "ok",
    )


def check_profile_state_not_generated(root: Path) -> CheckResult:
    generator = (root / "scripts/generate_app.py").read_text(encoding="utf-8")
    blueprint = yaml.safe_load((root / "harness/app_blueprint.yaml").read_text(encoding="utf-8"))
    exclusions = blueprint.get("runtime_state_exclusions", [])
    passed = "config/user_profiles" in generator and "config/user_profiles" in exclusions
    return CheckResult(
        "profile_state_not_generated", passed,
        json.dumps({"blueprint_excluded": "config/user_profiles" in exclusions}, ensure_ascii=False),
    )

def check_dashboard_actual_search(root: Path) -> CheckResult:
    text = (root / "dashboard.py").read_text(encoding="utf-8")
    terms = ["load_curated_latest", "search_companies", "stock_detail", "run_real_pipeline", "JQUANTS_API_KEY"]
    missing = [term for term in terms if term not in text]
    return CheckResult("dashboard_actual_search", not missing, "missing=" + ", ".join(missing) if missing else "ok")



def check_fuzzy_stock_search(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    search_module = (root / "src/value_dislocation/data/search.py").read_text(encoding="utf-8")
    dashboard_terms = [
        '@st.dialog("検索候補を選択"',
        'index=None',
        'stock_search_candidates',
        '選択した銘柄を表示',
        '複数候補の場合は選択画面を表示します',
    ]
    search_terms = [
        'normalize_company_search_text',
        'SequenceMatcher',
        '企業名部分一致',
        'あいまい一致',
        'search_score',
    ]
    missing_dashboard = [term for term in dashboard_terms if term not in dashboard]
    missing_search = [term for term in search_terms if term not in search_module]
    passed = not missing_dashboard and not missing_search
    return CheckResult(
        "fuzzy_stock_search",
        passed,
        json.dumps({"missing_dashboard": missing_dashboard, "missing_search": missing_search}, ensure_ascii=False),
    )


def check_external_event_review_gate(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    module = (root / "src/value_dislocation/external_event_review.py").read_text(encoding="utf-8")
    generator = (root / "scripts/generate_app.py").read_text(encoding="utf-8")
    required_dashboard = [
        "外的要因レビュー", "下落要因", "一次資料", "一時性確率", "カタリスト確率",
        "構造リスク", "回復カタリストと期限", "仮説無効化条件", "承認ステータス",
        "candidate_order_preview_allowed", "注文直前プレビューへ進む（未送信）",
        "各入力項目は任意です", "入力例・ガイドライン", "assess_yahoo_history_freshness",
        "最新市場データ: Yahoo Finance系",
    ]
    required_module = [
        "save_external_event_review", "load_external_event_review",
        "external_event_review_is_approved", "approval_status", '== "approved"',
    ]
    invalidation_module = (root / "src/value_dislocation/hypothesis_invalidation.py").read_text(encoding="utf-8")
    pipeline = (root / "src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    required_invalidation = [
        "structured_invalidation_conditions", "evaluate_hypothesis_invalidation",
        "evaluate_saved_reviews", "METRIC_DEFINITIONS",
    ]
    missing_dashboard = [term for term in required_dashboard if term not in dashboard]
    missing_module = [term for term in required_module if term not in module]
    missing_invalidation = [term for term in required_invalidation if term not in invalidation_module]
    pipeline_recalculates = "hypothesis_invalidation_latest.csv" in pipeline and "evaluate_saved_reviews" in pipeline
    no_fetch_dependency = "data.jquants" not in invalidation_module and "fetch_and_curate_jquants" not in invalidation_module
    generated_state_excluded = "config/external_event_reviews" in generator
    passed = not missing_dashboard and not missing_module and not missing_invalidation and pipeline_recalculates and no_fetch_dependency and generated_state_excluded
    return CheckResult(
        "external_event_review_gate", passed,
        json.dumps({
            "missing_dashboard": missing_dashboard,
            "missing_module": missing_module,
            "missing_invalidation": missing_invalidation,
            "pipeline_recalculates": pipeline_recalculates,
            "no_fetch_dependency": no_fetch_dependency,
            "generated_state_excluded": generated_state_excluded,
        }, ensure_ascii=False),
    )

def check_blueprint(root: Path) -> CheckResult:
    blueprint = yaml.safe_load((root / "harness/app_blueprint.yaml").read_text(encoding="utf-8"))
    required_invariants = {
        "sbi_order_transmission_disabled",
        "sbi_browser_automation_disabled",
        "sbi_credentials_forbidden",
        "actual_data_must_have_manifest",
        "sample_data_must_never_be_labeled_actual",
        "external_event_review_required_before_order_preview",
        "saved_user_profiles_must_not_be_copied_into_generated_apps",
    }
    invariants = set(blueprint.get("non_negotiable_invariants", []))
    required_files = blueprint.get("required_files", [])
    missing_files = [p for p in required_files if not (root / p).exists()]
    passed = required_invariants.issubset(invariants) and not missing_files
    return CheckResult(
        "app_blueprint",
        passed,
        f"missing_invariants={sorted(required_invariants - invariants)} missing_files={missing_files}",
    )



def check_fast_interactive_screening(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    pipeline = (root / "src/value_dislocation/real_pipeline.py").read_text(encoding="utf-8")
    perf = root / "src/value_dislocation/data/performance.py"
    passed = (
        'st.form("screening_conditions"' in dashboard
        and 'form_submit_button("条件を適用"' in dashboard
        and "load_feature_snapshot" in dashboard
        and "build_feature_snapshot" in pipeline
        and perf.exists()
    )
    return CheckResult("fast_interactive_screening", passed, "form + feature snapshot" if passed else "missing optimization")


def check_instant_preset_and_candidate_navigation(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    required = [
        'on_change=_on_preset_change',
        'def _open_stock_detail',
        'unified_candidate_code_',
        'unified_candidate_name_',
        'st.switch_page(STOCK_DETAIL_PAGE)',
        'key="stock_query"',
        'st.navigation(',
        'position="top"',
        'key="detail_dividend_shares"',
        '1株当たり予想年間配当',
    ]
    missing = [token for token in required if token not in dashboard]
    forbidden = ['st.radio(']
    found_forbidden = [token for token in forbidden if token in dashboard]
    passed = not missing and not found_forbidden
    return CheckResult(
        "instant_preset_and_candidate_navigation",
        passed,
        "ok" if passed else "missing=" + ", ".join(missing) + " forbidden=" + ", ".join(found_forbidden),
    )




def check_dividend_screening(root: Path) -> CheckResult:
    jquants = (root / "src/value_dislocation/data/jquants.py").read_text(encoding="utf-8")
    features = (root / "src/value_dislocation/strategy/features.py").read_text(encoding="utf-8")
    criteria = (root / "src/value_dislocation/strategy/criteria.py").read_text(encoding="utf-8")
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    required = [
        "NxFDivAnn", "forecast_annual_dividend_per_share", "forecast_dividend_yield",
        "pass_dividend_conditions", "minimum_forecast_dividend_yield",
        "配当を必須条件にする", "年間配当（税引前）", "概算投資額",
    ]
    combined = jquants + features + criteria + dashboard
    missing = [term for term in required if term not in combined]
    return CheckResult("dividend_screening", not missing, "ok" if not missing else "missing=" + ", ".join(missing))

def check_sbi_csv_bridge(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    module = root / "src/value_dislocation/data/sbi_import.py"
    passed = module.exists() and "parse_sbi_screening_csv" in dashboard and "SBI CSV取込" in dashboard
    return CheckResult("sbi_csv_bridge", passed, "CSV-only bridge; no credentials" if passed else "missing SBI CSV bridge")


def check_translated_news_and_analyst_help(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    market_context = (root / "src/value_dislocation/data/market_context.py").read_text(encoding="utf-8")
    analyst_heading = 'st.markdown("#### アナリスト評価・目標株価")'
    news_heading = 'st.markdown("#### 関連ニュース・市場コメント（最大10件）")'
    required_dashboard = [
        "機械翻訳", "原文を表示", "was_translated",
        "平均目標株価への乖離", "対象アナリスト数", "help=",
    ]
    required_context = [
        "translate_market_news_to_japanese", "translate_text_to_japanese",
        "deep_translator", "original_title", "original_summary",
    ]
    missing_dashboard = [x for x in required_dashboard if x not in dashboard]
    missing_context = [x for x in required_context if x not in market_context]
    correct_order = (
        analyst_heading in dashboard
        and news_heading in dashboard
        and dashboard.index(analyst_heading) < dashboard.index(news_heading)
    )
    return CheckResult(
        "translated_news_and_analyst_help",
        correct_order and not missing_dashboard and not missing_context,
        json.dumps({
            "correct_order": correct_order,
            "missing_dashboard": missing_dashboard,
            "missing_context": missing_context,
        }, ensure_ascii=False),
    )


def check_latest_trend_count_reconciliation(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    forbidden = [
        "limit = min(len(shortlist), 20)",
        "shortlist.head(limit)",
    ]
    required = [
        "for _, row in score_passed.iterrows()",
        "score_passed,",
        "star_only=",
        "all_result = pd.DataFrame(rows)",
        'metric("統合一覧"',
        'metric("取得失敗・判定不能"',
        "内部件数不整合を検出しました",
    ]
    forbidden_found = [term for term in forbidden if term in dashboard]
    missing = [term for term in required if term not in dashboard]
    return CheckResult(
        "latest_trend_count_reconciliation",
        not forbidden_found and not missing,
        json.dumps({"forbidden_found": forbidden_found, "missing": missing}, ensure_ascii=False),
    )


def check_buy_decision_support(root: Path) -> CheckResult:
    dashboard = (root / "dashboard.py").read_text(encoding="utf-8")
    module = root / "src/value_dislocation/decision/buy_readiness.py"
    trend_module = root / "src/value_dislocation/decision/trend.py"
    required = [
        "購入判断の整理", "注文前に人が確認する項目", "分割買いの参考案",
        "購入判断メモをJSONで保存", "利益保証ではありません",
        "株価トレンドと売買タイミング", "売却・撤退条件の例",
        "font-size: 1.12rem",
        "統合候補一覧（抽出条件 + 最新トレンド）", "build_trend_transition",
        "下降トレンド脱出", "_latest_external_history",
        "直感判定", "◎ 買い候補", "◎☆ 買い候補", "買い検討価格帯", "追いかけ買い上限", "再評価ライン",
        "株価・移動平均線グラフ", "prepare_trend_chart_frame", "st.plotly_chart",
    ]
    missing = [term for term in required if term not in dashboard]
    module_text = module.read_text(encoding="utf-8") if module.exists() else ""
    trend_text = trend_module.read_text(encoding="utf-8") if trend_module.exists() else ""
    module_missing = [term for term in ["build_buy_readiness", "build_intuitive_signal", "build_entry_price_guidance"] if term not in module_text]
    trend_missing = [term for term in ["build_price_trend_snapshot", "build_trend_transition", "prepare_trend_chart_frame"] if term not in trend_text]
    module_ok = module.exists() and not module_missing
    trend_ok = trend_module.exists() and not trend_missing
    details = []
    if missing:
        details.append("dashboard=" + ", ".join(missing))
    if not module.exists():
        details.append("missing_file=src/value_dislocation/decision/buy_readiness.py")
    elif module_missing:
        details.append("buy_readiness.py=" + ", ".join(module_missing))
    if not trend_module.exists():
        details.append("missing_file=src/value_dislocation/decision/trend.py")
    elif trend_missing:
        details.append("trend.py=" + ", ".join(trend_missing))
    return CheckResult(
        "buy_decision_support",
        module_ok and trend_ok and not missing,
        "ok" if module_ok and trend_ok and not missing else "; ".join(details),
    )

def check_no_sbi_secrets(root: Path) -> CheckResult:
    patterns = [
        re.compile(r"SBI_(?:LOGIN|USER|PASSWORD|TRADE_PASSWORD|OTP)\s*=", re.I),
        re.compile(r"sbisec_(?:password|cookie|session)\s*=", re.I),
    ]
    hits = []
    for path in _iter_text_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern.search(text):
                hits.append(str(path.relative_to(root)))
                break
    return CheckResult("no_sbi_secrets", not hits, "hits=" + ", ".join(hits) if hits else "ok")


def check_no_sbi_browser_automation(root: Path) -> CheckResult:
    automation_terms = ("selenium", "playwright", "pyautogui")
    hits = []
    for path in _iter_text_files(root):
        if path.resolve() == Path(__file__).resolve() or path.suffix.lower() != ".py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "sbi" in text and any(term in text for term in automation_terms):
            hits.append(str(path.relative_to(root)))
    return CheckResult("no_sbi_browser_automation", not hits, "hits=" + ", ".join(hits) if hits else "ok")


def check_risk_guards(root: Path) -> CheckResult:
    cfg = yaml.safe_load((root / "config/real_data.yaml").read_text(encoding="utf-8"))
    risk = cfg.get("risk", {})
    required = [
        "trading_capital_yen", "max_total_invested_ratio", "max_positions",
        "max_position_ratio", "max_sector_ratio", "risk_per_position_ratio", "board_lot",
    ]
    missing = [key for key in required if key not in risk]
    passed = not missing and risk.get("board_lot", 0) > 0 and risk.get("max_total_invested_ratio", 2) <= 1
    return CheckResult("risk_guards", passed, "missing=" + ", ".join(missing) if missing else "ok")


def _run(root: Path, name: str, args: list[str]) -> CheckResult:
    completed = subprocess.run(
        args, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    output = (completed.stdout + completed.stderr).strip()
    return CheckResult(name, completed.returncode == 0, output[-2500:] or "ok")


def run_compile(root: Path) -> CheckResult:
    return _run(root, "compileall", [sys.executable, "-m", "compileall", "-q", "src", "dashboard.py", "scripts"])


def run_generator_self_test(root: Path) -> CheckResult:
    return _run(root, "generator_self_test", [sys.executable, "scripts/generate_app.py", "--self-test"])


def run_pytest(root: Path) -> CheckResult:
    return _run(root, "pytest", [sys.executable, "-m", "pytest", "-q"])


def run_checks(root: Path, include_pytest: bool = True) -> list[CheckResult]:
    checks = [
        check_required_files(root),
        check_demo_isolation(root),
        check_real_data_contract(root),
        check_real_safety(root),
        check_provenance_implementation(root),
        check_jquants_price_api_contract(root),
        check_jquants_rate_limit_resilience(root),
        check_jquants_subscription_coverage(root),
        check_topix_no_substitution(root),
        check_explainable_screening(root),
        check_data_freshness_gate(root),
        check_beginner_condition_ui(root),
        check_profile_state_not_generated(root),
        check_dashboard_actual_search(root),
        check_fuzzy_stock_search(root),
        check_latest_trend_count_reconciliation(root),
        check_fast_interactive_screening(root),
        check_instant_preset_and_candidate_navigation(root),
        check_dividend_screening(root),
        check_sbi_csv_bridge(root),
        check_translated_news_and_analyst_help(root),
        check_buy_decision_support(root),
        check_external_event_review_gate(root),
        check_blueprint(root),
        check_no_sbi_secrets(root),
        check_no_sbi_browser_automation(root),
        check_risk_guards(root),
        run_compile(root),
        run_generator_self_test(root),
    ]
    if include_pytest:
        checks.append(run_pytest(root))
    return checks


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    results = run_checks(root)
    report = {"passed": all(r.passed for r in results), "checks": [asdict(r) for r in results]}
    output = root / "outputs/harness_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"[{marker}] {result.name}: {result.detail}")
    print(f"Report: {output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
