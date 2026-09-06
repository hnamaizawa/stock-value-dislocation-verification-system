import pandas as pd

from value_dislocation.data.jquants import normalize_financials
from value_dislocation.strategy.criteria import apply_quantitative_criteria, prepare_quantitative_universe


def test_normalize_and_filter_dividend_fields():
    raw = pd.DataFrame([{ 
        "DiscDate": "2026-05-12", "DiscTime": "10:00:00", "Code": "55760",
        "CurPerType": "FY", "CurPerEn": "2026-03-31", "CurFYEn": "2026-03-31",
        "Sales": "1000", "OP": "100", "CFO": "80", "TA": "1000", "Eq": "600",
        "EPS": "100", "BPS": "500", "DivAnn": "30", "PayoutRatioAnn": "0.30",
        "NxFDivAnn": "40", "NxFPayoutRatioAnn": "0.40", "ShOutFY": "1000000",
    }])
    fin = normalize_financials(raw)
    assert fin.loc[0, "actual_annual_dividend_per_share"] == 30
    assert fin.loc[0, "next_forecast_annual_dividend_per_share"] == 40

    companies = pd.DataFrame([{"code": "55760", "name": "Sample", "market": "Prime", "sector": "Test", "shares_outstanding": 1_000_000}])
    dates = pd.bdate_range("2025-07-01", periods=260)
    prices = pd.DataFrame({"date": dates, "code": "55760", "open": 1000, "high": 1200, "low": 900, "close": 1000, "volume": 100000, "turnover_yen": 100000000})
    prepared = prepare_quantitative_universe(companies, prices, fin, dates.max())
    assert prepared.loc[0, "forecast_annual_dividend_per_share"] == 40
    assert abs(prepared.loc[0, "forecast_dividend_yield"] - 0.04) < 1e-9

    config = {
        "universe": {"allowed_markets": ["Prime"], "min_average_turnover_yen_20d": 0, "min_price_yen": 0},
        "screen": {
            "minimum_equity_ratio": 0, "minimum_operating_cf_positive_ratio_3y": 0,
            "minimum_sales_cagr_3y": -1, "minimum_operating_margin": 0,
            "minimum_drawdown_52w": 0, "minimum_relative_underperformance_6m": 0,
            "use_relative_underperformance_filter": False, "maximum_forecast_op_decline": -1,
            "require_forecast": False, "quantitative_min_score": -999,
            "require_dividend": True, "minimum_annual_dividend_per_share": 20,
            "minimum_forecast_dividend_yield": 0.03, "maximum_forecast_dividend_yield": 0.06,
            "maximum_payout_ratio": 0.6, "exclude_forecast_dividend_cut": True,
        },
    }
    audited = apply_quantitative_criteria(prepared, config)
    assert bool(audited.loc[0, "pass_dividend_conditions"])
