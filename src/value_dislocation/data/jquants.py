from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from dateutil import tz
from dotenv import load_dotenv

from ..codes import normalize_tse_code
from .security_master_history import archive_security_master
from .snapshot import make_run_id, now_jst, write_dataframe, write_manifest




@dataclass(frozen=True)
class JQuantsFetchPolicy:
    """Rate-limit and retry policy for serial J-Quants retrieval.

    The official ``*_range`` helpers submit many requests concurrently.  This
    application intentionally performs one request at a time, writes each day
    to a resumable cache, and switches to a conservative interval after the
    first HTTP 429 response.
    """

    initial_interval_seconds: float = 13.0
    rate_limited_interval_seconds: float = 20.0
    max_attempts: int = 8
    initial_backoff_seconds: float = 65.0
    max_backoff_seconds: float = 900.0
    backoff_multiplier: float = 2.0
    skip_weekends: bool = True
    progress_every_days: int = 10


def fetch_policy_from_config(provider: dict[str, Any] | None) -> JQuantsFetchPolicy:
    settings = (provider or {}).get("rate_limit", {}) or {}
    return JQuantsFetchPolicy(
        initial_interval_seconds=float(settings.get("initial_interval_seconds", 13.0)),
        rate_limited_interval_seconds=float(
            settings.get("rate_limited_interval_seconds", 20.0)
        ),
        max_attempts=int(settings.get("max_attempts", 8)),
        initial_backoff_seconds=float(settings.get("initial_backoff_seconds", 65.0)),
        max_backoff_seconds=float(settings.get("max_backoff_seconds", 900.0)),
        backoff_multiplier=float(settings.get("backoff_multiplier", 2.0)),
        skip_weekends=bool(settings.get("skip_weekends", True)),
        progress_every_days=int(settings.get("progress_every_days", 10)),
    )


class _RequestPacer:
    def __init__(
        self,
        policy: JQuantsFetchPolicy,
        *,
        sleep_fn: Callable[[float], None] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
    ) -> None:
        self.policy = policy
        self.sleep_fn = sleep_fn or time.sleep
        self.monotonic_fn = monotonic_fn or time.monotonic
        self.interval_seconds = max(0.0, float(policy.initial_interval_seconds))
        self._last_started_at: float | None = None

    def before_request(self) -> None:
        now = self.monotonic_fn()
        if self._last_started_at is not None:
            remaining = self.interval_seconds - (now - self._last_started_at)
            if remaining > 0:
                self.sleep_fn(remaining)
        self._last_started_at = self.monotonic_fn()

    def enter_rate_limited_mode(self) -> None:
        self.interval_seconds = max(
            self.interval_seconds, float(self.policy.rate_limited_interval_seconds)
        )


def _exception_status_code(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    reason = getattr(exc, "reason", None)
    response = getattr(reason, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _is_rate_limit_exception(exc: BaseException) -> bool:
    return _exception_status_code(exc) == 429 or "429" in str(exc)


def _is_optional_access_error(exc: BaseException) -> bool:
    status = _exception_status_code(exc)
    return status in {400, 401, 403, 404} or any(
        token in str(exc) for token in ("400", "401", "403", "404")
    )


_SUBSCRIPTION_COVERAGE_PATTERN = re.compile(
    r"subscription\s+covers\s+the\s+following\s+dates:\s*"
    r"(?P<start>\d{4}-\d{2}-\d{2})\s*[~～]\s*"
    r"(?P<end>\d{4}-\d{2}-\d{2})",
    flags=re.IGNORECASE,
)


def _parse_subscription_coverage_error(
    exc: BaseException,
) -> JQuantsSubscriptionCoverage | None:
    """Extract the active plan's date window from a J-Quants HTTP 400 message."""

    match = _SUBSCRIPTION_COVERAGE_PATTERN.search(str(exc))
    if not match:
        return None
    return JQuantsSubscriptionCoverage(
        start=match.group("start"),
        end=match.group("end"),
    )


def _clamp_iso_date(value: str, lower: str, upper: str) -> str:
    return min(max(value, lower), upper)


def _discover_subscription_window(
    client: Any,
    *,
    price_start: str,
    price_end: str,
    financial_start: str,
    pacer: _RequestPacer,
) -> tuple[JQuantsResolvedWindow, dict[str, pd.DataFrame], list[str]]:
    """Resolve requested dates against the plan's actual accessible range.

    J-Quants returns HTTP 400 with an explicit ``start ~ end`` range when a
    requested date falls outside the active subscription. We deliberately probe
    the requested end and start dates before the long-running sync, parse that
    response, and clamp every dataset to the same effective window.

    Successful probe responses are returned so the daily-bar fetcher can put
    them directly into its cache instead of issuing duplicate requests.
    """

    daily_method = getattr(client, "get_eq_bars_daily", None)
    if not callable(daily_method):
        raise JQuantsDataError("The J-Quants client does not expose get_eq_bars_daily.")

    preload: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []
    coverage: JQuantsSubscriptionCoverage | None = None

    for probe_date in dict.fromkeys([price_end, price_start, financial_start]):
        try:
            frame = _call_with_rate_limit(
                lambda probe_date=probe_date: daily_method(date_yyyymmdd=probe_date),
                label=f"subscription coverage probe {probe_date}",
                pacer=pacer,
            )
        except Exception as exc:
            parsed = _parse_subscription_coverage_error(exc)
            if parsed is None:
                raise
            coverage = parsed
            break
        else:
            preload[probe_date] = (
                frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)
            )

    if coverage is None:
        resolved = JQuantsResolvedWindow(
            requested_price_start=price_start,
            requested_price_end=price_end,
            requested_financial_start=financial_start,
            effective_price_start=price_start,
            effective_price_end=price_end,
            effective_financial_start=financial_start,
            subscription_coverage=None,
        )
        return resolved, preload, warnings

    if price_end < coverage.start or price_start > coverage.end:
        raise JQuantsDataError(
            "The requested price window does not overlap the J-Quants subscription "
            f"coverage ({coverage.start} through {coverage.end})."
        )

    effective_price_start = _clamp_iso_date(price_start, coverage.start, coverage.end)
    effective_price_end = _clamp_iso_date(price_end, coverage.start, coverage.end)
    effective_financial_start = _clamp_iso_date(
        financial_start, coverage.start, coverage.end
    )
    effective_financial_start = min(effective_financial_start, effective_price_end)

    warnings.append(
        "J-Quants subscription coverage detected: "
        f"{coverage.start} through {coverage.end}."
    )
    if price_end != effective_price_end:
        warnings.append(
            f"Requested price end {price_end} was clamped to {effective_price_end}."
        )
    if price_start != effective_price_start:
        warnings.append(
            f"Requested price start {price_start} was clamped to {effective_price_start}."
        )
    if financial_start != effective_financial_start:
        warnings.append(
            "Requested financial start "
            f"{financial_start} was clamped to {effective_financial_start}."
        )

    print(
        "[J-Quants] Subscription date coverage: "
        f"{coverage.start} through {coverage.end}. "
        f"Using prices {effective_price_start} through {effective_price_end} and "
        f"financials {effective_financial_start} through {effective_price_end}.",
        flush=True,
    )

    resolved = JQuantsResolvedWindow(
        requested_price_start=price_start,
        requested_price_end=price_end,
        requested_financial_start=financial_start,
        effective_price_start=effective_price_start,
        effective_price_end=effective_price_end,
        effective_financial_start=effective_financial_start,
        subscription_coverage=coverage,
    )
    return resolved, preload, warnings


def _call_with_rate_limit(
    operation: Callable[[], Any],
    *,
    label: str,
    pacer: _RequestPacer,
) -> Any:
    policy = pacer.policy
    attempts = max(1, int(policy.max_attempts))
    for attempt in range(1, attempts + 1):
        pacer.before_request()
        try:
            return operation()
        except Exception as exc:
            if not _is_rate_limit_exception(exc):
                raise
            if attempt >= attempts:
                raise JQuantsDataError(
                    f"J-Quants rate limit persisted while fetching {label}. "
                    "Completed days remain in the local cache; wait and run again to resume."
                ) from exc
            pacer.enter_rate_limited_mode()
            backoff = min(
                float(policy.max_backoff_seconds),
                float(policy.initial_backoff_seconds)
                * (float(policy.backoff_multiplier) ** (attempt - 1)),
            )
            backoff = max(backoff, pacer.interval_seconds)
            print(
                f"[J-Quants] HTTP 429 while fetching {label}. "
                f"Waiting {backoff:.0f} seconds, then resuming from cache "
                f"(attempt {attempt + 1}/{attempts}).",
                flush=True,
            )
            pacer.sleep_fn(backoff)
    raise AssertionError("unreachable")


def _iter_request_dates(start: str, end: str, *, skip_weekends: bool) -> list[pd.Timestamp]:
    dates = pd.date_range(start, end, freq="D")
    if skip_weekends:
        dates = dates[dates.dayofweek < 5]
    return list(dates)


def _cache_locations(cache_dir: Path, prefix: str, day: pd.Timestamp) -> tuple[Path, Path]:
    year_dir = cache_dir / day.strftime("%Y")
    year_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{prefix}_{day.strftime('%Y%m%d')}"
    return year_dir / f"{stem}.csv.gz", year_dir / f"{stem}.empty"


def _read_day_cache(csv_path: Path, empty_path: Path) -> tuple[bool, pd.DataFrame]:
    if csv_path.exists():
        return True, pd.read_csv(csv_path, dtype=str, compression="gzip")
    if empty_path.exists():
        return True, pd.DataFrame()
    return False, pd.DataFrame()


def _write_day_cache(frame: pd.DataFrame, csv_path: Path, empty_path: Path) -> None:
    if frame is None or frame.empty:
        empty_path.write_text(now_jst().isoformat(), encoding="utf-8")
        csv_path.unlink(missing_ok=True)
        return
    frame.to_csv(csv_path, index=False, compression="gzip")
    empty_path.unlink(missing_ok=True)


class JQuantsConfigurationError(RuntimeError):
    pass


class JQuantsDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class JQuantsSubscriptionCoverage:
    """Date coverage reported by J-Quants for the active subscription."""

    start: str
    end: str


@dataclass(frozen=True)
class JQuantsResolvedWindow:
    requested_price_start: str
    requested_price_end: str
    requested_financial_start: str
    effective_price_start: str
    effective_price_end: str
    effective_financial_start: str
    subscription_coverage: JQuantsSubscriptionCoverage | None


@dataclass(frozen=True)
class RealDataPaths:
    run_id: str
    raw_dir: Path
    curated_run_dir: Path
    curated_latest_dir: Path
    output_dir: Path
    manifest_path: Path


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _first_present(df: pd.DataFrame, names: list[str], default: Any = np.nan) -> pd.Series:
    for name in names:
        if name in df.columns:
            return df[name]
    return pd.Series(default, index=df.index)


def _has_value(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.lower()
    return series.notna() & ~text.isin({"", "nan", "none", "null"})


def _require_api_key(env_name: str = "JQUANTS_API_KEY") -> str:
    load_dotenv()
    value = os.getenv(env_name, "").strip()
    if not value:
        raise JQuantsConfigurationError(
            f"{env_name} is not set. Create .env from .env.example or set an OS environment variable."
        )
    return value


def create_client(api_key_env: str = "JQUANTS_API_KEY"):
    api_key = _require_api_key(api_key_env)
    try:
        import jquantsapi
    except ImportError as exc:
        raise JQuantsConfigurationError(
            "jquants-api-client is not installed. Run setup_windows.cmd again."
        ) from exc
    return jquantsapi.ClientV2(api_key=api_key)


def normalize_companies(raw_master: pd.DataFrame, raw_financials: pd.DataFrame | None = None) -> pd.DataFrame:
    if raw_master.empty:
        raise JQuantsDataError("J-Quants company master is empty")
    required = {"Code", "CoName"}
    missing = required - set(raw_master.columns)
    if missing:
        raise JQuantsDataError(f"Company master columns missing: {sorted(missing)}")

    out = pd.DataFrame(index=raw_master.index)
    out["code"] = raw_master["Code"].map(normalize_tse_code)
    out["name"] = raw_master["CoName"].astype(str)
    out["sector"] = _first_present(raw_master, ["S33Nm", "S33NmEn", "S17Nm"]).fillna("")
    out["sector33_code"] = _first_present(raw_master, ["S33"], "").astype(str)
    market_name = _first_present(raw_master, ["MktNmEn", "MktNm"], "")
    market_code = _first_present(raw_master, ["Mkt"], "").astype(str)
    market_map = {"0111": "Prime", "0112": "Standard", "0113": "Growth"}
    out["market"] = market_code.map(market_map).fillna(market_name.astype(str))
    out["master_date"] = pd.to_datetime(_first_present(raw_master, ["Date"]), errors="coerce")
    out["shares_outstanding"] = np.nan

    if raw_financials is not None and not raw_financials.empty and "Code" in raw_financials.columns:
        f = raw_financials.copy()
        f["code"] = f["Code"].map(normalize_tse_code)
        f["DiscDate"] = pd.to_datetime(f.get("DiscDate"), errors="coerce")
        f["shares"] = _numeric(_first_present(f, ["ShOutFY", "AvgSh"]))
        latest = (
            f.dropna(subset=["shares"])
            .sort_values(["code", "DiscDate"])
            .drop_duplicates("code", keep="last")[["code", "shares"]]
        )
        out = out.merge(latest, on="code", how="left")
        out["shares_outstanding"] = out["shares"]
        out = out.drop(columns=["shares"])

    return out.drop_duplicates("code", keep="last").reset_index(drop=True)


def normalize_topix(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["date", "topix_close"])
    if "Date" not in raw.columns or "C" not in raw.columns:
        raise JQuantsDataError(f"TOPIX columns unexpected: {list(raw.columns)}")
    out = pd.DataFrame({
        "date": pd.to_datetime(raw["Date"], errors="coerce"),
        "topix_close": _numeric(raw["C"]),
    })
    return out.dropna(subset=["date", "topix_close"]).drop_duplicates("date", keep="last")


TOPIX_PROXY_CODES = ("13060", "14750", "13050")
TOPIX_PROXY_LABELS = {
    "13060": "NEXT FUNDS TOPIX連動型上場投信 (1306)",
    "14750": "iシェアーズ・コア TOPIX ETF (1475)",
    "13050": "iFreeETF TOPIX (1305)",
}


def _topix_proxy_series(prices: pd.DataFrame) -> pd.DataFrame:
    """Return one adjusted-close proxy series, preferring 1306 then 1475 then 1305."""
    for code in TOPIX_PROXY_CODES:
        candidate = prices.loc[prices["code"] == code, ["date", "close"]].dropna()
        if len(candidate) >= 2:
            out = candidate.drop_duplicates("date", keep="last").rename(columns={"close": "topix_proxy_close"})
            out["topix_proxy_code"] = code
            out["topix_proxy_label"] = TOPIX_PROXY_LABELS[code]
            return out
    return pd.DataFrame(columns=["date", "topix_proxy_close", "topix_proxy_code", "topix_proxy_label"])


def normalize_prices(raw: pd.DataFrame, topix: pd.DataFrame | None = None) -> pd.DataFrame:
    if raw.empty:
        raise JQuantsDataError("J-Quants daily prices are empty")
    aliases = {
        "Date": "date",
        "Code": "code",
        "AdjO": "open",
        "AdjH": "high",
        "AdjL": "low",
        "AdjC": "close",
        "AdjVo": "volume",
        "O": "open_raw",
        "H": "high_raw",
        "L": "low_raw",
        "C": "close_raw",
        "Vo": "volume_raw",
        "Va": "turnover_yen",
        "AdjFactor": "adjustment_factor",
    }
    out = raw.rename(columns={k: v for k, v in aliases.items() if k in raw.columns}).copy()
    if "date" not in out or "code" not in out:
        raise JQuantsDataError(f"Daily price columns unexpected: {list(raw.columns)}")
    for target, fallback in (("open", "open_raw"), ("high", "high_raw"), ("low", "low_raw"), ("close", "close_raw"), ("volume", "volume_raw")):
        if target not in out.columns and fallback in out.columns:
            out[target] = out[fallback]
    needed = ["date", "code", "open", "high", "low", "close", "volume"]
    missing = [c for c in needed if c not in out.columns]
    if missing:
        raise JQuantsDataError(f"Daily price columns missing: {missing}; actual={list(raw.columns)}")

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["code"] = out["code"].map(normalize_tse_code)
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = _numeric(out[col])
    if "turnover_yen" not in out.columns:
        out["turnover_yen"] = out["close"] * out["volume"]
    else:
        out["turnover_yen"] = _numeric(out["turnover_yen"])
        out["turnover_yen"] = out["turnover_yen"].fillna(out["close"] * out["volume"])
    if "adjustment_factor" not in out.columns:
        out["adjustment_factor"] = 1.0
    else:
        out["adjustment_factor"] = _numeric(out["adjustment_factor"]).fillna(1.0)

    keep = needed + ["turnover_yen", "adjustment_factor"]
    out = out[keep].dropna(subset=["date", "code", "close"]).copy()
    proxy = _topix_proxy_series(out)
    if topix is not None and not topix.empty:
        out = out.merge(topix[["date", "topix_close"]], on="date", how="left")
    if not proxy.empty:
        out = out.merge(proxy, on="date", how="left")
    return out.sort_values(["code", "date"]).drop_duplicates(["code", "date"], keep="last").reset_index(drop=True)


def normalize_financials(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        raise JQuantsDataError("J-Quants financial summary is empty")
    required = {"DiscDate", "Code"}
    missing = required - set(raw.columns)
    if missing:
        raise JQuantsDataError(f"Financial summary columns missing: {sorted(missing)}")

    out = pd.DataFrame(index=raw.index)
    out["disclosure_date"] = pd.to_datetime(raw["DiscDate"], errors="coerce")
    out["disclosure_time"] = _first_present(raw, ["DiscTime"], "").astype(str)
    out["code"] = raw["Code"].map(normalize_tse_code)
    out["document_id"] = _first_present(raw, ["DiscNo"], "").astype(str)
    out["statement_type"] = _first_present(raw, ["CurPerType"], "").astype(str)
    out["period_end"] = pd.to_datetime(_first_present(raw, ["CurPerEn", "CurFYEn"]), errors="coerce")
    out["fiscal_year"] = pd.to_datetime(_first_present(raw, ["CurFYEn", "CurPerEn"]), errors="coerce").dt.year
    out["sales"] = _numeric(_first_present(raw, ["Sales", "NCSales"]))
    out["operating_profit"] = _numeric(_first_present(raw, ["OP", "NCOP"]))
    out["ordinary_profit"] = _numeric(_first_present(raw, ["OdP", "NCOdP"]))
    out["net_income"] = _numeric(_first_present(raw, ["NP", "NCNP"]))
    out["operating_cf"] = _numeric(_first_present(raw, ["CFO"]))
    out["investing_cf"] = _numeric(_first_present(raw, ["CFI"]))
    out["financing_cf"] = _numeric(_first_present(raw, ["CFF"]))
    out["total_assets"] = _numeric(_first_present(raw, ["TA", "NCTA"]))
    out["equity"] = _numeric(_first_present(raw, ["Eq", "NCEq"]))
    out["interest_bearing_debt"] = np.nan
    out["cash"] = _numeric(_first_present(raw, ["CashEq"]))
    out["eps"] = _numeric(_first_present(raw, ["EPS", "NCEPS"]))
    out["book_value_per_share"] = _numeric(_first_present(raw, ["BPS", "NCBPS"]))
    out["forecast_sales"] = _numeric(_first_present(raw, ["FSales", "FNCSales"]))
    out["forecast_operating_profit"] = _numeric(_first_present(raw, ["FOP", "FNCOP"]))
    out["forecast_eps"] = _numeric(_first_present(raw, ["FEPS", "FNCEPS"]))
    # Dividend fields available in the J-Quants V2 financial summary.
    out["actual_annual_dividend_per_share"] = _numeric(_first_present(raw, ["DivAnn"]))
    out["forecast_annual_dividend_per_share"] = _numeric(_first_present(raw, ["FDivAnn"]))
    out["next_forecast_annual_dividend_per_share"] = _numeric(_first_present(raw, ["NxFDivAnn"]))
    out["actual_payout_ratio"] = _numeric(_first_present(raw, ["PayoutRatioAnn"]))
    out["forecast_payout_ratio"] = _numeric(_first_present(raw, ["FPayoutRatioAnn"]))
    out["next_forecast_payout_ratio"] = _numeric(_first_present(raw, ["NxFPayoutRatioAnn"]))
    out["shares_outstanding"] = _numeric(_first_present(raw, ["ShOutFY", "AvgSh"]))
    out["is_full_year_actual"] = out["statement_type"].str.upper().eq("FY")
    out["is_revision"] = (
        _has_value(_first_present(raw, ["ChgByASRev"], ""))
        | _has_value(_first_present(raw, ["ChgNoASRev"], ""))
    )
    out["source_type"] = "jquants_fin_summary_v2"
    return out.dropna(subset=["disclosure_date", "code"]).sort_values(["code", "disclosure_date", "disclosure_time"]).reset_index(drop=True)


def normalize_earnings_calendar(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["date", "code", "name", "fiscal_year", "quarter", "market"])
    out = pd.DataFrame(index=raw.index)
    out["date"] = pd.to_datetime(_first_present(raw, ["Date"]), errors="coerce")
    out["code"] = _first_present(raw, ["Code"], "").map(normalize_tse_code)
    out["name"] = _first_present(raw, ["CoName"], "").astype(str)
    out["fiscal_year"] = _first_present(raw, ["FY"], "").astype(str)
    out["quarter"] = _first_present(raw, ["FQ"], "").astype(str)
    out["market"] = _first_present(raw, ["Section"], "").astype(str)
    return out.dropna(subset=["date"]).reset_index(drop=True)


def normalize_tdnet(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    rename = {
        "Code": "code",
        "DiscDate": "published_date",
        "DiscTime": "published_time",
        "DiscNo": "document_id",
        "Title": "title",
    }
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
    if "code" in out:
        out["code"] = out["code"].map(normalize_tse_code)
    if "published_date" in out:
        out["published_date"] = pd.to_datetime(out["published_date"], errors="coerce")
    return out


def _as_jst_datetime(value: str) -> datetime:
    """Convert an ISO date to a timezone-aware Asia/Tokyo datetime."""
    return datetime.fromisoformat(value).replace(tzinfo=tz.gettz("Asia/Tokyo"))


def _fetch_equity_bars_range(
    client: Any,
    start: str,
    end: str,
    *,
    cache_dir: Path | None = None,
    policy: JQuantsFetchPolicy | None = None,
    pacer: _RequestPacer | None = None,
    preloaded: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Fetch all-stock daily bars serially with per-day resumable caching.

    J-Quants V2 requires ``date`` or ``code`` for the daily-bars endpoint.  The
    official range helper satisfies that contract but uses concurrent workers,
    which can quickly trigger HTTP 429.  This implementation deliberately calls
    ``get_eq_bars_daily(date_yyyymmdd=...)`` one day at a time.
    """
    daily_method = getattr(client, "get_eq_bars_daily", None)
    if not callable(daily_method):
        raise JQuantsDataError("The J-Quants client does not expose get_eq_bars_daily.")

    policy = policy or JQuantsFetchPolicy()
    pacer = pacer or _RequestPacer(policy)
    cache_dir = cache_dir or Path("data/raw/jquants/_cache/equity_bars")
    preloaded = preloaded or {}
    dates = _iter_request_dates(start, end, skip_weekends=policy.skip_weekends)
    frames: list[pd.DataFrame] = []
    fetched = 0
    cached = 0

    for index, day in enumerate(dates, start=1):
        csv_path, empty_path = _cache_locations(
            cache_dir, "v2_eq_bars_daily", day
        )
        found, frame = _read_day_cache(csv_path, empty_path)
        if found:
            cached += 1
        elif day.strftime("%Y-%m-%d") in preloaded:
            frame = preloaded[day.strftime("%Y-%m-%d")]
            _write_day_cache(frame, csv_path, empty_path)
            fetched += 1
        else:
            date_text = day.strftime("%Y-%m-%d")
            frame = _call_with_rate_limit(
                lambda date_text=date_text: daily_method(date_yyyymmdd=date_text),
                label=f"equity bars {date_text}",
                pacer=pacer,
            )
            if not isinstance(frame, pd.DataFrame):
                frame = pd.DataFrame(frame)
            _write_day_cache(frame, csv_path, empty_path)
            fetched += 1
        if not frame.empty:
            frames.append(frame)
        if policy.progress_every_days > 0 and (
            index % policy.progress_every_days == 0 or index == len(dates)
        ):
            print(
                f"[J-Quants] Equity bars {index}/{len(dates)} days "
                f"(new={fetched}, cache={cached}).",
                flush=True,
            )

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    sort_columns = [column for column in ("Code", "Date") if column in out.columns]
    if sort_columns:
        out = out.sort_values(sort_columns)
    return out.reset_index(drop=True)


def _fetch_financial_summary_range(
    client: Any,
    start: str,
    end: str,
    *,
    cache_dir: Path,
    policy: JQuantsFetchPolicy,
    pacer: _RequestPacer,
) -> pd.DataFrame:
    """Fetch financial summaries serially and resume from a per-day cache."""
    cursor_method = getattr(client, "get_fin_summary_cursor", None)
    legacy_method = getattr(client, "get_fin_summary", None)
    if not callable(cursor_method) and not callable(legacy_method):
        raise JQuantsDataError(
            "The J-Quants client exposes neither get_fin_summary_cursor nor get_fin_summary."
        )

    dates = _iter_request_dates(start, end, skip_weekends=policy.skip_weekends)
    frames: list[pd.DataFrame] = []
    fetched = 0
    cached = 0
    for index, day in enumerate(dates, start=1):
        csv_path, empty_path = _cache_locations(
            cache_dir, "v2_fin_summary", day
        )
        found, frame = _read_day_cache(csv_path, empty_path)
        if found:
            cached += 1
        else:
            date_text = day.strftime("%Y%m%d")

            def request(date_text: str = date_text) -> pd.DataFrame:
                if callable(cursor_method):
                    result = cursor_method(date_yyyymmdd=date_text)
                    return result[0] if isinstance(result, tuple) else result
                return legacy_method(date_yyyymmdd=date_text)

            frame = _call_with_rate_limit(
                request, label=f"financial summary {date_text}", pacer=pacer
            )
            if not isinstance(frame, pd.DataFrame):
                frame = pd.DataFrame(frame)
            _write_day_cache(frame, csv_path, empty_path)
            fetched += 1
        if not frame.empty:
            frames.append(frame)
        if policy.progress_every_days > 0 and (
            index % policy.progress_every_days == 0 or index == len(dates)
        ):
            print(
                f"[J-Quants] Financial summaries {index}/{len(dates)} days "
                f"(new={fetched}, cache={cached}).",
                flush=True,
            )

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    sort_columns = [
        column for column in ("DiscDate", "DiscTime", "Code") if column in out.columns
    ]
    if sort_columns:
        out = out.sort_values(sort_columns)
    return out.reset_index(drop=True)


def _fetch_raw(
    client: Any,
    start: str,
    end: str,
    financial_start: str,
    include_topix: bool,
    include_earnings: bool,
    financial_cache_dir: Path | None = None,
    equity_cache_dir: Path | None = None,
    fetch_policy: JQuantsFetchPolicy | None = None,
) -> tuple[dict[str, pd.DataFrame], list[str], JQuantsResolvedWindow]:
    policy = fetch_policy or JQuantsFetchPolicy()
    pacer = _RequestPacer(policy)
    resolved, preloaded, warnings = _discover_subscription_window(
        client,
        price_start=start,
        price_end=end,
        financial_start=financial_start,
        pacer=pacer,
    )
    prices = _fetch_equity_bars_range(
        client,
        resolved.effective_price_start,
        resolved.effective_price_end,
        cache_dir=equity_cache_dir,
        policy=policy,
        pacer=pacer,
        preloaded=preloaded,
    )
    master_date = resolved.effective_price_end
    if not prices.empty and "Date" in prices.columns:
        parsed_dates = pd.to_datetime(prices["Date"], errors="coerce").dropna()
        if not parsed_dates.empty:
            master_date = parsed_dates.max().date().isoformat()
    master = _call_with_rate_limit(
        lambda: client.get_list(date_yyyymmdd=master_date),
        label=f"listed companies {master_date}",
        pacer=pacer,
    )
    if master.empty:
        master = _call_with_rate_limit(
            lambda: client.get_list(), label="listed companies latest", pacer=pacer
        )

    financial_cache_dir = financial_cache_dir or Path(
        "data/raw/jquants/_cache/fin_summary"
    )
    financials = _fetch_financial_summary_range(
        client,
        resolved.effective_financial_start,
        resolved.effective_price_end,
        cache_dir=financial_cache_dir,
        policy=policy,
        pacer=pacer,
    )

    topix = pd.DataFrame()
    if include_topix:
        try:
            topix = _call_with_rate_limit(
                lambda: client.get_idx_bars_daily_topix(
                    from_yyyymmdd=resolved.effective_price_start,
                    to_yyyymmdd=resolved.effective_price_end,
                ),
                label="TOPIX",
                pacer=pacer,
            )
        except Exception as exc:
            if not _is_optional_access_error(exc):
                raise
            warnings.append(f"TOPIX was skipped because the plan/API denied access: {exc}")
            print(f"[J-Quants] {warnings[-1]}", flush=True)

    earnings = pd.DataFrame()
    if include_earnings:
        try:
            earnings = _call_with_rate_limit(
                lambda: client.get_eq_earnings_cal(),
                label="earnings calendar",
                pacer=pacer,
            )
        except Exception as exc:
            if not _is_optional_access_error(exc):
                raise
            warnings.append(
                f"Earnings calendar was skipped because the plan/API denied access: {exc}"
            )
            print(f"[J-Quants] {warnings[-1]}", flush=True)

    return {
        "master": master,
        "prices": prices,
        "financials": financials,
        "topix": topix,
        "earnings": earnings,
    }, warnings, resolved


def fetch_and_curate_jquants(
    *,
    project_root: Path,
    start: str,
    end: str,
    financial_start: str,
    api_key_env: str = "JQUANTS_API_KEY",
    include_topix: bool = True,
    include_earnings: bool = True,
    client: Any | None = None,
    fetch_policy: JQuantsFetchPolicy | None = None,
) -> RealDataPaths:
    run_id = make_run_id("jquants")
    raw_dir = project_root / "data" / "raw" / "jquants" / run_id
    curated_run_dir = project_root / "data" / "curated" / "runs" / run_id
    curated_latest_dir = project_root / "data" / "curated" / "latest"
    output_dir = project_root / "outputs" / "real"
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_run_dir.mkdir(parents=True, exist_ok=True)
    curated_latest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    jq = client or create_client(api_key_env)
    cache_root = project_root / "data" / "raw" / "jquants" / "_cache"
    financial_cache_dir = cache_root / "fin_summary"
    equity_cache_dir = cache_root / "equity_bars"
    raw, fetch_warnings, resolved = _fetch_raw(
        jq,
        start,
        end,
        financial_start,
        include_topix,
        include_earnings,
        financial_cache_dir,
        equity_cache_dir,
        fetch_policy,
    )

    raw_files: dict[str, Any] = {}
    for name, df in raw.items():
        raw_file = raw_dir / f"{name}.csv"
        raw_files[name] = write_dataframe(df, raw_file)
        raw_files[name]["path"] = raw_file.relative_to(project_root).as_posix()

    topix = normalize_topix(raw["topix"])
    financials = normalize_financials(raw["financials"])
    companies = normalize_companies(raw["master"], raw["financials"])
    historical_master_path = archive_security_master(
        project_root,
        companies,
        snapshot_date=resolved.effective_price_end,
        run_id=run_id,
    )
    prices = normalize_prices(raw["prices"], topix)
    earnings = normalize_earnings_calendar(raw["earnings"])

    curated = {
        "companies": companies,
        "prices": prices,
        "financials": financials,
        "topix": topix,
        "earnings": earnings,
    }
    curated_files: dict[str, Any] = {}
    for name, df in curated.items():
        run_file = curated_run_dir / f"{name}.csv"
        curated_files[name] = write_dataframe(df, run_file)
        curated_files[name]["path"] = run_file.relative_to(project_root).as_posix()
        shutil.copy2(run_file, curated_latest_dir / f"{name}.csv")

    retrieved_at = now_jst().isoformat()
    actual_cutoff = pd.Timestamp(prices["date"].max()).date().isoformat()
    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "provider": "J-Quants API V2",
        "actual_data": True,
        "sample_data": False,
        "retrieved_at": retrieved_at,
        "data_cutoff_at": actual_cutoff,
        "request": {
            "requested_price_start": resolved.requested_price_start,
            "requested_price_end": resolved.requested_price_end,
            "requested_financial_start": resolved.requested_financial_start,
            "effective_price_start": resolved.effective_price_start,
            "effective_price_end": resolved.effective_price_end,
            "effective_financial_start": resolved.effective_financial_start,
            "api_key_env": api_key_env,
            "methods": [
                "ClientV2.get_list",
                "ClientV2.get_eq_bars_daily(date_yyyymmdd=...) serial daily cache",
                "ClientV2.get_fin_summary_cursor(date_yyyymmdd=...) serial daily cache",
                "ClientV2.get_idx_bars_daily_topix",
                "ClientV2.get_eq_earnings_cal",
            ],
        },
        "subscription_coverage": (
            {
                "start": resolved.subscription_coverage.start,
                "end": resolved.subscription_coverage.end,
            }
            if resolved.subscription_coverage is not None
            else None
        ),
        "fetch_policy": {
            "strategy": "adaptive_serial_resumable",
            "initial_interval_seconds": (fetch_policy or JQuantsFetchPolicy()).initial_interval_seconds,
            "rate_limited_interval_seconds": (fetch_policy or JQuantsFetchPolicy()).rate_limited_interval_seconds,
            "max_attempts": (fetch_policy or JQuantsFetchPolicy()).max_attempts,
            "initial_backoff_seconds": (fetch_policy or JQuantsFetchPolicy()).initial_backoff_seconds,
            "skip_weekends": (fetch_policy or JQuantsFetchPolicy()).skip_weekends,
        },
        "warnings": fetch_warnings,
        "raw_files": raw_files,
        "curated_files": curated_files,
        "historical_security_master": {
            "path": historical_master_path.relative_to(project_root).as_posix(),
            "snapshot_date": historical_master_path.name[:10],
            "rows": int(len(companies)),
        },
    }
    manifest_path = write_manifest(manifest, curated_run_dir / "manifest.json")
    shutil.copy2(manifest_path, curated_latest_dir / "manifest.json")
    shutil.copy2(manifest_path, output_dir / "manifest_latest.json")

    return RealDataPaths(run_id, raw_dir, curated_run_dir, curated_latest_dir, output_dir, manifest_path)



def fetch_jquants_v2(start: str, end: str, output_dir: Path, client: Any | None = None) -> dict[str, Path]:
    """Compatibility helper that stores raw J-Quants V2 CSV files.

    New development should prefer ``fetch_and_curate_jquants`` because it also
    writes provenance manifests and normalized datasets.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jq = client or create_client()
    start_dt = datetime.fromisoformat(start).replace(tzinfo=tz.gettz("Asia/Tokyo"))
    end_dt = datetime.fromisoformat(end).replace(tzinfo=tz.gettz("Asia/Tokyo"))
    frames = {
        "master": jq.get_list(date_yyyymmdd=end),
        "prices": _fetch_equity_bars_range(
            jq, start, end, cache_dir=output_dir / "_cache" / "equity_bars"
        ),
        "financials": _fetch_financial_summary_range(
            jq,
            start,
            end,
            cache_dir=output_dir / "_cache" / "fin_summary",
            policy=JQuantsFetchPolicy(),
            pacer=_RequestPacer(JQuantsFetchPolicy()),
        ),
        "topix": jq.get_idx_bars_daily_topix(from_yyyymmdd=start, to_yyyymmdd=end),
        "earnings": jq.get_eq_earnings_cal(),
    }
    paths: dict[str, Path] = {}
    for name, frame in frames.items():
        path = output_dir / f"jquants_{name}_{start}_{end}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[name] = path
    return paths

def search_tdnet_by_code(
    code: str,
    *,
    from_date: str,
    to_date: str,
    api_key_env: str = "JQUANTS_API_KEY",
    client: Any | None = None,
) -> pd.DataFrame:
    jq = client or create_client(api_key_env)
    result = jq.get_td_list(
        code=normalize_tse_code(code),
        from_date=from_date,
        to_date=to_date,
    )
    raw = result[0] if isinstance(result, tuple) else result
    return normalize_tdnet(raw)


def date_window(end: str | None, price_lookback_days: int, financial_lookback_days: int) -> tuple[str, str, str]:
    end_date = datetime.fromisoformat(end).date() if end else now_jst().date()
    start = end_date - timedelta(days=price_lookback_days)
    financial_start = end_date - timedelta(days=financial_lookback_days)
    return start.isoformat(), end_date.isoformat(), financial_start.isoformat()
