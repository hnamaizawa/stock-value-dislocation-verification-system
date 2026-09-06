def test_decision_package_exports_trend_transition():
    from value_dislocation import decision

    assert callable(decision.build_price_trend_snapshot)
    assert callable(decision.build_trend_transition)
