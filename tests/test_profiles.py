from pathlib import Path

from value_dislocation.strategy.profiles import (
    PRESETS,
    list_profiles,
    load_profile,
    normalize_profile_name,
    preset_overrides,
    save_profile,
)


def test_beginner_presets_have_required_sections_and_valid_ranges():
    assert {"安全重視", "標準", "割安重視"}.issubset(PRESETS)
    for name in PRESETS:
        overrides = preset_overrides(name)
        assert overrides["universe"]["allowed_markets"]
        screen = overrides["screen"]
        assert 0 <= screen["minimum_equity_ratio"] <= 1
        assert 0 <= screen["minimum_operating_cf_positive_ratio_3y"] <= 1
        assert screen["minimum_drawdown_52w"] <= 0
        assert screen["minimum_relative_underperformance_6m"] <= 0
        assert 0 <= screen["quantitative_min_score"] <= 100


def test_profile_round_trip_and_safe_name(tmp_path: Path):
    overrides = preset_overrides("標準")
    path = save_profile(tmp_path, "私の 条件/1", "標準", overrides)
    assert path.parent == tmp_path
    assert path.name == f"{normalize_profile_name('私の 条件/1')}.json"
    document = load_profile(path)
    assert document["preset"] == "標準"
    assert document["overrides"] == overrides
    assert list_profiles(tmp_path) == [path]
