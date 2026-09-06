from pathlib import Path

from scripts.harness_check import (
    check_blueprint,
    check_dashboard_actual_search,
    check_demo_isolation,
    check_provenance_implementation,
    check_jquants_price_api_contract,
    check_jquants_rate_limit_resilience,
    check_jquants_subscription_coverage,
    check_real_data_contract,
    check_real_safety,
    check_topix_no_substitution,
    check_explainable_screening,
    check_data_freshness_gate,
    check_beginner_condition_ui,
    check_profile_state_not_generated,
    check_fast_interactive_screening,
    check_instant_preset_and_candidate_navigation,
    check_sbi_csv_bridge,
    check_required_files,
    check_risk_guards,
    check_buy_decision_support,
    check_external_event_review_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def test_harness_documents_real_data_and_safety():
    results = [
        check_required_files(ROOT),
        check_demo_isolation(ROOT),
        check_real_data_contract(ROOT),
        check_real_safety(ROOT),
        check_provenance_implementation(ROOT),
        check_jquants_price_api_contract(ROOT),
        check_jquants_rate_limit_resilience(ROOT),
        check_jquants_subscription_coverage(ROOT),
        check_topix_no_substitution(ROOT),
        check_explainable_screening(ROOT),
        check_data_freshness_gate(ROOT),
        check_beginner_condition_ui(ROOT),
        check_profile_state_not_generated(ROOT),
        check_dashboard_actual_search(ROOT),
        check_fast_interactive_screening(ROOT),
        check_instant_preset_and_candidate_navigation(ROOT),
        check_sbi_csv_bridge(ROOT),
        check_buy_decision_support(ROOT),
        check_external_event_review_gate(ROOT),
        check_blueprint(ROOT),
        check_risk_guards(ROOT),
    ]
    assert all(r.passed for r in results), [r for r in results if not r.passed]
