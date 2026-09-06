from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pandas as pd

YAHOO_BULK_FETCH_BLOCK_THRESHOLD = 100


def yahoo_bulk_fetch_allowed(candidate_count: int) -> bool:
    """Return True only when bulk Yahoo retrieval is below the safety threshold.

    100 or more candidates must not trigger bulk Yahoo/yfinance retrieval.
    Individual-stock lookups remain unaffected.
    """
    return int(candidate_count) < YAHOO_BULK_FETCH_BLOCK_THRESHOLD


@dataclass(frozen=True)
class LatestQuote:
    code: str
    ticker: str
    price: float
    previous_close: float | None
    change: float | None
    change_pct: float | None
    observed_at: str
    market_time: str | None
    source: str
    delayed_or_unofficial: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _display_code(code: str) -> str:
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) >= 5 and digits.endswith("0"):
        digits = digits[:-1]
    return digits[:4]


def fetch_yahoo_finance_quote(code: str) -> LatestQuote:
    """Fetch a latest-available Tokyo quote through yfinance for display only."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is not installed. Run setup_windows.cmd.") from exc

    display_code = _display_code(code)
    if len(display_code) != 4:
        raise ValueError(f"Unsupported Tokyo security code: {code}")
    ticker_symbol = f"{display_code}.T"
    ticker = yf.Ticker(ticker_symbol)
    frame = ticker.history(period="5d", interval="1m", auto_adjust=False, prepost=False)
    if frame is None or frame.empty or "Close" not in frame.columns:
        frame = ticker.history(period="10d", interval="1d", auto_adjust=False, prepost=False)
    if frame is None or frame.empty or "Close" not in frame.columns:
        raise RuntimeError(f"No Yahoo Finance quote returned for {ticker_symbol}")
    close = pd.to_numeric(frame["Close"], errors="coerce").dropna()
    if close.empty:
        raise RuntimeError(f"Yahoo Finance returned no valid close for {ticker_symbol}")
    price = float(close.iloc[-1])
    market_time = pd.Timestamp(close.index[-1]).isoformat()
    index_dates = pd.Index(pd.to_datetime(close.index).date)
    previous = close[index_dates != index_dates[-1]]
    previous_close = float(previous.iloc[-1]) if not previous.empty else None
    change = price - previous_close if previous_close is not None else None
    change_pct = change / previous_close if previous_close not in (None, 0) else None
    return LatestQuote(code=display_code, ticker=ticker_symbol, price=price, previous_close=previous_close, change=change, change_pct=change_pct, observed_at=datetime.now().astimezone().isoformat(), market_time=market_time, source="Yahoo Finance via yfinance (unofficial)")


def fetch_yahoo_finance_history(code: str, period: str = "1y") -> pd.DataFrame:
    """Fetch latest-available daily Tokyo price history through yfinance.

    Returned columns are normalized to date/close/high/low/volume. This data is display-only
    and must not silently replace the point-in-time J-Quants screening snapshot.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is not installed. Run setup_windows.cmd.") from exc

    display_code = _display_code(code)
    if len(display_code) != 4:
        raise ValueError(f"Unsupported Tokyo security code: {code}")
    ticker_symbol = f"{display_code}.T"
    frame = yf.Ticker(ticker_symbol).history(
        period=period,
        interval="1d",
        auto_adjust=True,
        actions=False,
    )
    if frame is None or frame.empty or "Close" not in frame.columns:
        raise RuntimeError(f"No Yahoo Finance daily history returned for {ticker_symbol}")
    result = pd.DataFrame({
        "date": pd.to_datetime(frame.index, errors="coerce"),
        "close": pd.to_numeric(frame["Close"], errors="coerce"),
        "high": pd.to_numeric(frame.get("High"), errors="coerce"),
        "low": pd.to_numeric(frame.get("Low"), errors="coerce"),
        "volume": pd.to_numeric(frame.get("Volume"), errors="coerce"),
    }).dropna(subset=["date", "close"]).sort_values("date")
    if result.empty:
        raise RuntimeError(f"Yahoo Finance returned no valid daily close for {ticker_symbol}")
    result["source"] = "Yahoo Finance via yfinance (unofficial)"
    return result.reset_index(drop=True)


def assess_yahoo_history_freshness(
    history: pd.DataFrame | None,
    *,
    max_age_days: int = 7,
    now: datetime | pd.Timestamp | None = None,
) -> dict:
    """Assess candidate-specific market-data freshness from Yahoo daily history.

    Yahoo/yfinance remains an unofficial supplemental source. This function is
    only for the order-preview freshness gate; it never changes the J-Quants
    point-in-time screening score or financial snapshot.
    """
    result = {
        "source": "Yahoo Finance via yfinance (unofficial)",
        "latest_market_date": None,
        "age_days": None,
        "max_age_days": int(max_age_days),
        "fresh": False,
    }
    if history is None or not isinstance(history, pd.DataFrame) or history.empty or "date" not in history.columns:
        return result
    dates = pd.to_datetime(history["date"], errors="coerce").dropna()
    if dates.empty:
        return result
    latest = pd.Timestamp(dates.max())
    if latest.tzinfo is not None:
        latest = latest.tz_convert("Asia/Tokyo").tz_localize(None)
    current = pd.Timestamp(now if now is not None else datetime.now().astimezone())
    if current.tzinfo is not None:
        current = current.tz_convert("Asia/Tokyo").tz_localize(None)
    age_days = max(0, (current.normalize() - latest.normalize()).days)
    result.update({
        "latest_market_date": latest.date().isoformat(),
        "age_days": int(age_days),
        "fresh": bool(age_days <= int(max_age_days)),
    })
    return result
