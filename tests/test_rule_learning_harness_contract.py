from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_blueprint_contains_rule_learning_invariants_and_runtime_exclusion():
    blueprint = yaml.safe_load((ROOT / "harness" / "app_blueprint.yaml").read_text(encoding="utf-8"))
    invariants = set(blueprint.get("non_negotiable_invariants", []))
    required = {
        "learned_rule_changes_must_not_trigger_market_data_fetch",
        "learned_rules_must_use_point_in_time_history",
        "learned_rules_must_require_out_of_sample_validation",
        "learned_rules_must_be_bounded_and_reversible",
        "human_external_event_thresholds_must_not_be_auto_learned",
        "source_yaml_must_not_be_rewritten_by_rule_learning",
    }
    assert required.issubset(invariants)
    assert "data/history/rule_learning" in blueprint.get("runtime_state_exclusions", [])
    assert "src/value_dislocation/strategy/rule_learning.py" in blueprint.get("required_files", [])


def test_actual_data_enables_guarded_learning_but_demo_does_not():
    real = yaml.safe_load((ROOT / "config" / "real_data.yaml").read_text(encoding="utf-8"))
    demo = yaml.safe_load((ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    assert real["rule_learning"]["enabled"] is True
    assert real["rule_learning"]["auto_apply"] is True
    assert demo["rule_learning"]["enabled"] is False
    assert demo["rule_learning"]["auto_apply"] is False
    assert int(real["rule_learning"]["minimum_mature_events"]) >= 40
    assert int(real["rule_learning"]["minimum_validation_events"]) >= 10
    assert float(real["rule_learning"]["minimum_mean_return_improvement"]) >= 0.02
    assert int(real["rule_learning"]["cooldown_days"]) >= 30


def test_rule_learning_runtime_state_is_gitignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/history/rule_learning/" in ignore


def test_rule_learning_documentation_explains_human_review_boundary():
    doc = (ROOT / "docs" / "18_AUTOMATIC_RULE_LEARNING.md").read_text(encoding="utf-8")
    assert "外的要因らしさ" in doc
    assert "自動変更しません" in doc
    assert "ネットワークアクセスを行いません" in doc
    assert "時系列の前70%を学習、後30%を検証" in doc
    assert "`config/real_data.yaml` 自体を書き換えません" in doc


def test_status_script_requires_explicit_reset_flag():
    text = (ROOT / "scripts" / "rule_learning_status.py").read_text(encoding="utf-8")
    assert '"--reset-active"' in text
    assert "if args.reset_active:" in text
    assert "clear_active_rule_overrides(ROOT)" in text
