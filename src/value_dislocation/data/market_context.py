from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
import re

import pandas as pd


@dataclass(frozen=True)
class MarketNewsItem:
    title: str
    publisher: str | None
    published_at: str | None
    summary: str | None
    url: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalystSnapshot:
    recommendation_key: str | None
    recommendation_mean: float | None
    analyst_count: int | None
    target_low: float | None
    target_mean: float | None
    target_median: float | None
    target_high: float | None
    current_price: float | None
    upside_to_mean_target: float | None
    source: str
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_TRANSLATION_SEPARATOR = "\n---VD-SUMMARY---\n"


def contains_japanese(text: str | None) -> bool:
    """Return True when the text already contains Japanese script."""
    return bool(text and _JAPANESE_RE.search(str(text)))


def translate_text_to_japanese(text: str | None, translator_factory=None) -> str | None:
    """Machine-translate non-Japanese text; preserve the original on failure."""
    if text in (None, ""):
        return text
    original = str(text)
    if contains_japanese(original):
        return original
    try:
        if translator_factory is None:
            try:
                from deep_translator import GoogleTranslator
            except ImportError as exc:
                raise RuntimeError("deep-translator is not installed. Run setup_windows.cmd.") from exc
            translator = GoogleTranslator(source="auto", target="ja")
        else:
            translator = translator_factory(source="auto", target="ja")
        translated = translator.translate(original)
        return str(translated).strip() if translated else original
    except Exception:
        return original


def translate_market_news_to_japanese(
    items: list[MarketNewsItem], translator_factory=None
) -> list[dict[str, Any]]:
    """Return display dictionaries with Japanese title/summary and original text retained."""
    translated_items: list[dict[str, Any]] = []
    for item in items:
        title = item.title or ""
        summary = item.summary or ""
        combined = title + (_TRANSLATION_SEPARATOR + summary if summary else "")
        translated = translate_text_to_japanese(combined, translator_factory=translator_factory) or combined
        if _TRANSLATION_SEPARATOR in translated:
            ja_title, ja_summary = translated.split(_TRANSLATION_SEPARATOR, 1)
        else:
            ja_title = translated
            ja_summary = translate_text_to_japanese(summary, translator_factory=translator_factory) if summary else None
        was_translated = (ja_title != title) or (bool(summary) and ja_summary != summary)
        translated_items.append({
            **item.to_dict(),
            "title_ja": ja_title or title,
            "summary_ja": ja_summary or summary or None,
            "was_translated": was_translated,
            "original_title": title if was_translated else None,
            "original_summary": summary if was_translated and summary else None,
        })
    return translated_items


def _display_code(code: str) -> str:
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) >= 5 and digits.endswith("0"):
        digits = digits[:-1]
    return digits[:4]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(number) else number


def _timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).astimezone().isoformat()
        return pd.Timestamp(value).isoformat()
    except Exception:
        return str(value)


def _news_url(item: dict[str, Any]) -> str | None:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    canonical = content.get("canonicalUrl") if isinstance(content.get("canonicalUrl"), dict) else {}
    click = content.get("clickThroughUrl") if isinstance(content.get("clickThroughUrl"), dict) else {}
    return (
        item.get("link")
        or item.get("url")
        or canonical.get("url")
        or click.get("url")
    )


def _normalise_news(item: dict[str, Any]) -> MarketNewsItem | None:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
    title = item.get("title") or content.get("title")
    if not title:
        return None
    summary = (
        item.get("summary")
        or content.get("summary")
        or content.get("description")
    )
    publisher = item.get("publisher") or provider.get("displayName") or provider.get("name")
    published = (
        item.get("providerPublishTime")
        or item.get("pubDate")
        or content.get("pubDate")
        or content.get("displayTime")
    )
    return MarketNewsItem(
        title=str(title),
        publisher=str(publisher) if publisher else None,
        published_at=_timestamp(published),
        summary=str(summary) if summary else None,
        url=_news_url(item),
    )


def _ticker_for_code(code: str, ticker_factory=None):
    display_code = _display_code(code)
    if len(display_code) != 4:
        raise ValueError(f"Unsupported Tokyo security code: {code}")
    if ticker_factory is None:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance is not installed. Run setup_windows.cmd.") from exc
        ticker_factory = yf.Ticker
    return ticker_factory(f"{display_code}.T")


def fetch_market_news(code: str, limit: int = 10, ticker_factory=None) -> list[MarketNewsItem]:
    """Return latest available related articles; never scrapes Yahoo Japan message boards."""
    ticker = _ticker_for_code(code, ticker_factory=ticker_factory)
    raw: list[dict[str, Any]] = []
    try:
        getter = getattr(ticker, "get_news", None)
        if callable(getter):
            result = getter(count=max(limit, 10), tab="news")
            if isinstance(result, list):
                raw = result
    except TypeError:
        result = ticker.get_news(count=max(limit, 10))
        if isinstance(result, list):
            raw = result
    except Exception:
        raw = []
    if not raw:
        try:
            result = getattr(ticker, "news", [])
            if isinstance(result, list):
                raw = result
        except Exception:
            raw = []

    items: list[MarketNewsItem] = []
    seen: set[tuple[str, str | None]] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        item = _normalise_news(row)
        if item is None:
            continue
        key = (item.title, item.url)
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= limit:
            break
    return items


def fetch_analyst_snapshot(code: str, ticker_factory=None) -> AnalystSnapshot:
    """Return public Yahoo Finance analyst consensus when available."""
    ticker = _ticker_for_code(code, ticker_factory=ticker_factory)
    info: dict[str, Any] = {}
    try:
        result = getattr(ticker, "info", {})
        if isinstance(result, dict):
            info = result
    except Exception:
        info = {}

    targets: dict[str, Any] = {}
    try:
        result = getattr(ticker, "analyst_price_targets", {})
        if isinstance(result, dict):
            targets = result
    except Exception:
        targets = {}

    current = _number(targets.get("current") or info.get("currentPrice") or info.get("regularMarketPrice"))
    mean_target = _number(targets.get("mean") or info.get("targetMeanPrice"))
    upside = None
    if current not in (None, 0) and mean_target is not None:
        upside = mean_target / current - 1

    return AnalystSnapshot(
        recommendation_key=(str(info.get("recommendationKey")) if info.get("recommendationKey") else None),
        recommendation_mean=_number(info.get("recommendationMean")),
        analyst_count=int(info["numberOfAnalystOpinions"]) if info.get("numberOfAnalystOpinions") not in (None, "") else None,
        target_low=_number(targets.get("low") or info.get("targetLowPrice")),
        target_mean=mean_target,
        target_median=_number(targets.get("median") or info.get("targetMedianPrice")),
        target_high=_number(targets.get("high") or info.get("targetHighPrice")),
        current_price=current,
        upside_to_mean_target=upside,
        source="Yahoo Finance via yfinance (unofficial)",
        observed_at=datetime.now().astimezone().isoformat(),
    )
