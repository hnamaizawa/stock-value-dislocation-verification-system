from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from value_dislocation.codes import display_tse_code, normalize_tse_code
from value_dislocation.data.jquants import (
    JQuantsFetchPolicy,
    _fetch_equity_bars_range,
    _parse_subscription_coverage_error,
    fetch_and_curate_jquants,
    normalize_companies,
    normalize_financials,
    normalize_prices,
    normalize_topix,
)
from value_dislocation.data.search import load_curated_latest, search_companies, stock_detail
from value_dislocation.data.snapshot import read_manifest


def test_tse_code_normalization():
    assert normalize_tse_code("7203") == "72030"
    assert normalize_tse_code("72030") == "72030"
    assert display_tse_code("72030") == "7203"


def test_jquants_normalizers_use_actual_v2_columns():
    master = pd.DataFrame(
        {"Date": ["2026-07-31"], "Code": ["72030"], "CoName": ["Test Motors"], "S33Nm": ["輸送用機器"], "Mkt": ["0111"]}
    )
    topix_raw = pd.DataFrame({"Date": ["2026-07-30", "2026-07-31"], "C": [3000.0, 3010.0]})
    prices_raw = pd.DataFrame(
        {
            "Date": ["2026-07-30", "2026-07-31"], "Code": ["72030", "72030"],
            "AdjO": [2500.0, 2520.0], "AdjH": [2550.0, 2580.0], "AdjL": [2480.0, 2510.0],
            "AdjC": [2530.0, 2570.0], "AdjVo": [1000000, 1200000], "Va": [2530000000, 3084000000],
        }
    )
    fin_raw = pd.DataFrame(
        {
            "DiscDate": ["2026-05-10"], "DiscTime": ["15:00"], "Code": ["72030"],
            "CurPerType": ["FY"], "CurFYEn": ["2026-03-31"], "Sales": [1000000], "OP": [100000],
            "CFO": [120000], "TA": [2000000], "Eq": [1000000], "CashEq": [300000],
            "EPS": [120.0], "BPS": [1000.0], "FOP": [110000], "ShOutFY": [100000000],
        }
    )
    topix = normalize_topix(topix_raw)
    companies = normalize_companies(master, fin_raw)
    prices = normalize_prices(prices_raw, topix)
    financials = normalize_financials(fin_raw)
    assert companies.loc[0, "code"] == "72030"
    assert companies.loc[0, "market"] == "Prime"
    assert prices.loc[1, "topix_close"] == 3010.0
    assert financials.loc[0, "operating_profit"] == 100000
    assert bool(financials.loc[0, "is_full_year_actual"])


class FakeJQuantsClient:
    def get_list(self, date_yyyymmdd: str = ""):
        return pd.DataFrame(
            {"Date": [date_yyyymmdd or "2026-07-31"], "Code": ["72030"], "CoName": ["Test Motors"], "S33Nm": ["輸送用機器"], "Mkt": ["0111"]}
        )

    def get_eq_bars_daily_range(self, start_dt, end_dt):
        raise AssertionError("The official concurrent range helper must not be used")

    def get_eq_bars_daily(self, *, date_yyyymmdd: str):
        day = pd.Timestamp(date_yyyymmdd)
        if day.dayofweek >= 5:
            return pd.DataFrame()
        close = 3000.0 - (day - pd.Timestamp("2026-07-01")).days * 2.5
        return pd.DataFrame(
            {
                "Date": [day.strftime("%Y-%m-%d")], "Code": ["72030"], "AdjO": [close + 5],
                "AdjH": [close + 20], "AdjL": [close - 20], "AdjC": [close], "AdjVo": [1000000],
                "Va": [close * 1000000],
            }
        )

    def get_fin_summary_cursor(self, *, date_yyyymmdd: str):
        rows = {
            "20240510": ("2024-03-31", 900000, 90000, 100000, 1800000, 900000, 250000, 100.0, 900.0, 95000),
            "20250509": ("2025-03-31", 950000, 95000, 110000, 1900000, 950000, 280000, 110.0, 950.0, 100000),
            "20260508": ("2026-03-31", 1000000, 100000, 120000, 2000000, 1000000, 300000, 120.0, 1000.0, 110000),
        }
        row = rows.get(date_yyyymmdd)
        if row is None:
            return pd.DataFrame(), None
        period, sales, op, cfo, assets, equity, cash, eps, bps, fop = row
        return pd.DataFrame(
            {
                "DiscDate": [pd.Timestamp(date_yyyymmdd).strftime("%Y-%m-%d")],
                "DiscTime": ["15:00"], "Code": ["72030"], "DiscNo": [date_yyyymmdd],
                "CurPerType": ["FY"], "CurFYEn": [period], "Sales": [sales], "OP": [op],
                "CFO": [cfo], "TA": [assets], "Eq": [equity], "CashEq": [cash],
                "EPS": [eps], "BPS": [bps], "FOP": [fop], "ShOutFY": [100000000],
            }
        ), None

    def get_idx_bars_daily_topix(self, from_yyyymmdd: str, to_yyyymmdd: str):
        dates = pd.bdate_range(from_yyyymmdd, to_yyyymmdd)
        return pd.DataFrame({"Date": dates.strftime("%Y-%m-%d"), "C": range(2800, 2800 + len(dates))})

    def get_eq_earnings_cal(self):
        return pd.DataFrame({"Date": ["2026-08-10"], "Code": ["72030"], "CoName": ["Test Motors"], "FY": ["2027"], "FQ": ["1Q"], "Section": ["Prime"]})


def test_fetch_curate_manifest_and_search(tmp_path: Path):
    paths = fetch_and_curate_jquants(
        project_root=tmp_path,
        start="2025-07-01",
        end="2026-07-31",
        financial_start="2023-01-01",
        client=FakeJQuantsClient(),
        fetch_policy=JQuantsFetchPolicy(
            initial_interval_seconds=0,
            rate_limited_interval_seconds=0,
            initial_backoff_seconds=0,
            max_backoff_seconds=0,
            progress_every_days=0,
        ),
    )
    manifest = read_manifest(paths.manifest_path)
    assert manifest["actual_data"] is True
    assert manifest["sample_data"] is False
    assert manifest["provider"] == "J-Quants API V2"
    assert manifest["curated_files"]["prices"]["sha256"]

    data = load_curated_latest(tmp_path)
    matches = search_companies(data["companies"], "7203")
    assert len(matches) == 1
    detail = stock_detail(data, "7203")
    assert detail["company"]["name"] == "Test Motors"
    assert not detail["prices"].empty


class DateOnlyBarsClient:
    def __init__(self):
        self.requested_dates: list[str] = []

    def get_eq_bars_daily(self, *, date_yyyymmdd: str):
        self.requested_dates.append(date_yyyymmdd)
        if date_yyyymmdd != "2026-07-31":
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "Date": [date_yyyymmdd],
                "Code": ["72030"],
                "AdjO": [2500.0],
                "AdjH": [2550.0],
                "AdjL": [2480.0],
                "AdjC": [2530.0],
                "AdjVo": [1000000],
            }
        )


def test_equity_bars_fallback_uses_date_parameter_not_from_to(tmp_path: Path):
    client = DateOnlyBarsClient()
    result = _fetch_equity_bars_range(
        client,
        "2026-07-30",
        "2026-08-01",
        cache_dir=tmp_path / "bars",
        policy=JQuantsFetchPolicy(
            initial_interval_seconds=0,
            rate_limited_interval_seconds=0,
            initial_backoff_seconds=0,
            max_backoff_seconds=0,
            progress_every_days=0,
        ),
    )
    assert client.requested_dates == ["2026-07-30", "2026-07-31"]
    assert len(result) == 1
    assert result.loc[0, "Date"] == "2026-07-31"


class OnceRateLimitedClient:
    def __init__(self):
        self.calls = 0

    def get_eq_bars_daily(self, *, date_yyyymmdd: str):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("429 Too Many Requests")
        return pd.DataFrame(
            {
                "Date": [date_yyyymmdd],
                "Code": ["72030"],
                "AdjO": [2500.0],
                "AdjH": [2550.0],
                "AdjL": [2480.0],
                "AdjC": [2530.0],
                "AdjVo": [1000000],
            }
        )


def test_429_backoff_and_daily_cache_resume(tmp_path: Path, monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("value_dislocation.data.jquants.time.sleep", waits.append)
    policy = JQuantsFetchPolicy(
        initial_interval_seconds=0,
        rate_limited_interval_seconds=0,
        max_attempts=3,
        initial_backoff_seconds=1,
        max_backoff_seconds=1,
        progress_every_days=0,
    )
    client = OnceRateLimitedClient()
    cache = tmp_path / "bars"
    first = _fetch_equity_bars_range(
        client, "2026-07-31", "2026-07-31", cache_dir=cache, policy=policy
    )
    assert len(first) == 1
    assert waits == [1.0]
    assert client.calls == 2

    second = _fetch_equity_bars_range(
        client, "2026-07-31", "2026-07-31", cache_dir=cache, policy=policy
    )
    assert len(second) == 1
    assert client.calls == 2


class SubscriptionRangeError(RuntimeError):
    def __init__(self, start: str, end: str):
        super().__init__(
            "400 for url: https://api.jquants.com/v2/equities/bars/daily "
            f"body: Your subscription covers the following dates: {start} ~ {end}."
        )
        self.response = SimpleNamespace(status_code=400)


def test_parse_subscription_coverage_error():
    coverage = _parse_subscription_coverage_error(
        SubscriptionRangeError("2024-05-10", "2026-05-10")
    )
    assert coverage is not None
    assert coverage.start == "2024-05-10"
    assert coverage.end == "2026-05-10"


class CoverageLimitedClient(FakeJQuantsClient):
    coverage_start = "2026-05-05"
    coverage_end = "2026-05-10"

    def __init__(self):
        self.bar_requests: list[str] = []
        self.financial_requests: list[str] = []

    def get_eq_bars_daily(self, *, date_yyyymmdd: str):
        self.bar_requests.append(date_yyyymmdd)
        if not self.coverage_start <= date_yyyymmdd <= self.coverage_end:
            raise SubscriptionRangeError(self.coverage_start, self.coverage_end)
        day = pd.Timestamp(date_yyyymmdd)
        if day.dayofweek >= 5:
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "Date": [date_yyyymmdd],
                "Code": ["72030"],
                "AdjO": [2500.0],
                "AdjH": [2550.0],
                "AdjL": [2480.0],
                "AdjC": [2530.0],
                "AdjVo": [1000000],
                "Va": [2530000000],
            }
        )

    def get_fin_summary_cursor(self, *, date_yyyymmdd: str):
        day = pd.Timestamp(date_yyyymmdd).strftime("%Y-%m-%d")
        self.financial_requests.append(day)
        if not self.coverage_start <= day <= self.coverage_end:
            raise AssertionError(f"financial request outside coverage: {day}")
        if day != "2026-05-08":
            return pd.DataFrame(), None
        return pd.DataFrame(
            {
                "DiscDate": [day],
                "DiscTime": ["15:00"],
                "Code": ["72030"],
                "CurPerType": ["FY"],
                "CurFYEn": ["2026-03-31"],
                "Sales": [1000000],
                "OP": [100000],
                "CFO": [120000],
                "TA": [2000000],
                "Eq": [1000000],
                "CashEq": [300000],
                "EPS": [120.0],
                "BPS": [1000.0],
                "FOP": [110000],
                "ShOutFY": [100000000],
            }
        ), None


def test_subscription_window_is_detected_and_all_datasets_are_clamped(tmp_path: Path):
    client = CoverageLimitedClient()
    paths = fetch_and_curate_jquants(
        project_root=tmp_path,
        start="2026-05-01",
        end="2026-06-01",
        financial_start="2026-04-01",
        client=client,
        fetch_policy=JQuantsFetchPolicy(
            initial_interval_seconds=0,
            rate_limited_interval_seconds=0,
            initial_backoff_seconds=0,
            max_backoff_seconds=0,
            progress_every_days=0,
        ),
    )
    manifest = read_manifest(paths.manifest_path)
    assert manifest["subscription_coverage"] == {
        "start": "2026-05-05",
        "end": "2026-05-10",
    }
    request = manifest["request"]
    assert request["requested_price_end"] == "2026-06-01"
    assert request["effective_price_start"] == "2026-05-05"
    assert request["effective_price_end"] == "2026-05-10"
    assert request["effective_financial_start"] == "2026-05-05"
    assert any("clamped" in warning for warning in manifest["warnings"])
    assert client.bar_requests[0] == "2026-06-01"
    assert all(
        "2026-05-05" <= day <= "2026-05-10"
        for day in client.bar_requests[1:]
    )
    assert client.financial_requests
    assert all(
        "2026-05-05" <= day <= "2026-05-10"
        for day in client.financial_requests
    )


def test_normalize_prices_adds_topix_etf_proxy_from_1306():
    raw = pd.DataFrame({
        "Date": ["2026-05-11", "2026-05-12", "2026-05-11", "2026-05-12"],
        "Code": ["13060", "13060", "72030", "72030"],
        "AdjO": [100, 101, 2000, 2010], "AdjH": [101, 102, 2010, 2020],
        "AdjL": [99, 100, 1990, 2000], "AdjC": [100, 101, 2000, 2010],
        "AdjVo": [1000, 1000, 1000, 1000],
    })
    prices = normalize_prices(raw, pd.DataFrame())
    company = prices.loc[prices["code"] == "72030"].sort_values("date")
    assert list(company["topix_proxy_close"]) == [100, 101]
    assert set(company["topix_proxy_code"]) == {"13060"}
