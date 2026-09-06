from __future__ import annotations

from pathlib import Path

import pandas as pd

from .codes import normalize_tse_code


REQUIRED_COLUMNS = {
    "companies": {"code", "name", "sector", "market", "shares_outstanding"},
    "prices": {"date", "code", "close", "high", "low", "volume"},
    "financials": {
        "disclosure_date",
        "fiscal_year",
        "code",
        "sales",
        "operating_profit",
        "operating_cf",
        "total_assets",
        "equity",
        "interest_bearing_debt",
        "cash",
        "eps",
        "book_value_per_share",
        "forecast_operating_profit",
    },
    "events": {
        "event_date",
        "code",
        "category",
        "externality",
        "temporary_probability",
        "catalyst_probability",
        "evidence",
        "source_url",
        "review_status",
    },
}


class DataValidationError(RuntimeError):
    pass


def _read_csv(path: Path, kind: str, date_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise DataValidationError(f"{kind} CSV が見つかりません: {path}")
    df = pd.read_csv(path, dtype={"code": str})
    missing = REQUIRED_COLUMNS[kind] - set(df.columns)
    if missing:
        raise DataValidationError(f"{kind} CSV の必須列が不足しています: {sorted(missing)}")
    for col in date_columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
        if df[col].isna().any():
            raise DataValidationError(f"{kind}.{col} に不正な日付があります")
    df["code"] = df["code"].map(normalize_tse_code)
    return df


def load_all(companies_path: Path, prices_path: Path, financials_path: Path, events_path: Path):
    companies = _read_csv(companies_path, "companies", [])
    prices = _read_csv(prices_path, "prices", ["date"])
    financials = _read_csv(financials_path, "financials", ["disclosure_date"])
    events = _read_csv(events_path, "events", ["event_date"])
    return companies, prices, financials, events


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
