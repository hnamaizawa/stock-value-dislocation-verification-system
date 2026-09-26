from pathlib import Path


def test_root_package_init_does_not_import_decision_module():
    init_path = Path(__file__).parents[1] / "src" / "value_dislocation" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "buy_readiness" not in text
    assert "from .decision" not in text
    assert "__version__" in text


def test_public_decision_exports_import_from_decision_package():
    import value_dislocation
    from value_dislocation.decision import (
        build_buy_readiness,
        build_entry_price_guidance,
        build_intuitive_signal,
        build_price_trend_snapshot,
        build_split_entry_plan,
        build_trend_transition,
        prepare_trend_chart_frame,
    )

    assert value_dislocation.__version__ == "0.6.69"
    for fn in (
        build_buy_readiness, build_entry_price_guidance, build_intuitive_signal,
        build_price_trend_snapshot, build_split_entry_plan, build_trend_transition,
        prepare_trend_chart_frame,
    ):
        assert callable(fn)
