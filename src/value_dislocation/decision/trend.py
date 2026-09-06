from __future__ import annotations

from typing import Any
import math
import pandas as pd


def _safe(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_price_trend_snapshot(prices: pd.DataFrame) -> dict[str, Any]:
    """Build explainable trend/momentum indicators from daily prices.

    Uses only historical daily data. It is not a prediction or trading signal.
    """
    if prices is None or prices.empty:
        return {"trend_state": "データ不足", "trend_score": 0, "signals": [], "warnings": ["株価履歴がありません。"]}
    frame = prices.copy()
    date_col = "date" if "date" in frame.columns else "Date"
    close_col = "close" if "close" in frame.columns else ("AdjC" if "AdjC" in frame.columns else "C")
    volume_col = "volume" if "volume" in frame.columns else ("Vo" if "Vo" in frame.columns else None)
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame[close_col] = pd.to_numeric(frame[close_col], errors="coerce")
    frame = frame.dropna(subset=[date_col, close_col]).sort_values(date_col)
    if frame.empty:
        return {"trend_state": "データ不足", "trend_score": 0, "signals": [], "warnings": ["有効な終値がありません。"]}
    close = frame[close_col].astype(float)
    latest = float(close.iloc[-1])
    sma20 = _safe(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma50 = _safe(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    sma200 = _safe(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    sma20_prev = _safe(close.rolling(20).mean().iloc[-6]) if len(close) >= 25 else None
    sma50_prev = _safe(close.rolling(50).mean().iloc[-11]) if len(close) >= 60 else None
    ret20 = _safe(latest / close.iloc[-21] - 1) if len(close) >= 21 else None
    ret60 = _safe(latest / close.iloc[-61] - 1) if len(close) >= 61 else None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi14 = _safe((100 - 100 / (1 + rs)).iloc[-1]) if len(close) >= 15 else None
    high20 = _safe(close.tail(20).max()) if len(close) >= 20 else None
    low20 = _safe(close.tail(20).min()) if len(close) >= 20 else None
    high60 = _safe(close.tail(60).max()) if len(close) >= 60 else None
    low60 = _safe(close.tail(60).min()) if len(close) >= 60 else None
    volume_ratio = None
    if volume_col and volume_col in frame.columns:
        volume = pd.to_numeric(frame[volume_col], errors="coerce")
        if volume.notna().sum() >= 20:
            avg20 = _safe(volume.tail(20).mean())
            latest_vol = _safe(volume.iloc[-1])
            if avg20 and latest_vol is not None:
                volume_ratio = latest_vol / avg20

    signals: list[str] = []
    warnings: list[str] = []
    score = 0
    if sma20 is not None:
        if latest > sma20:
            signals.append("株価が20日移動平均線を上回っています。")
            score += 1
        else:
            warnings.append("株価が20日移動平均線を下回っています。短期下落トレンドに注意。")
            score -= 1
    if sma50 is not None:
        if latest > sma50:
            signals.append("株価が50日移動平均線を上回っています。")
            score += 1
        else:
            warnings.append("株価が50日移動平均線を下回っています。中期トレンドは弱めです。")
            score -= 1
    if sma200 is not None:
        if latest > sma200:
            signals.append("株価が200日移動平均線を上回り、長期トレンドは強めです。")
            score += 1
        else:
            warnings.append("株価が200日移動平均線を下回り、長期下落トレンドの可能性があります。")
            score -= 1
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            signals.append("20日線が50日線を上回っています。短中期は上向きです。")
            score += 1
        else:
            warnings.append("20日線が50日線を下回っています。反転確認前の可能性があります。")
            score -= 1
    if sma20 is not None and sma20_prev is not None:
        if sma20 > sma20_prev:
            signals.append("20日移動平均線が上向きです。")
            score += 1
        else:
            warnings.append("20日移動平均線が下向きです。落ちるナイフを拾うリスクがあります。")
            score -= 1
    if ret20 is not None and ret20 > 0:
        score += 1
    elif ret20 is not None and ret20 < -0.10:
        warnings.append("直近20営業日の下落が10%を超えています。下落加速に注意。")
        score -= 1
    if rsi14 is not None:
        if 40 <= rsi14 <= 65:
            signals.append("RSIは過熱感が比較的小さい範囲です。")
            score += 1
        elif rsi14 >= 75:
            warnings.append("RSIが75以上で短期的な買われ過ぎに注意。")
            score -= 1
        elif rsi14 <= 30:
            warnings.append("RSIが30以下ですが、反発確認前の安易な逆張りに注意。")
    if high20 and latest >= high20 * 0.995:
        signals.append("20日高値圏にあり、上抜けの兆候があります。")
        score += 1
    if low20 and latest <= low20 * 1.005:
        warnings.append("20日安値圏にあり、下抜けリスクがあります。")
        score -= 1
    if volume_ratio is not None and volume_ratio >= 1.5:
        signals.append("出来高が20日平均の1.5倍以上です。値動きの確認材料になります。")

    if score >= 5:
        state = "上昇トレンド"
    elif score >= 2:
        state = "上昇転換の兆候"
    elif score <= -5:
        state = "明確な下向きトレンド"
    elif score <= -2:
        state = "下向きトレンド"
    else:
        state = "方向感なし・もみ合い"

    return {
        "trend_state": state,
        "trend_score": score,
        "latest_price": latest,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "sma20_rising": bool(sma20 is not None and sma20_prev is not None and sma20 > sma20_prev),
        "sma50_rising": bool(sma50 is not None and sma50_prev is not None and sma50 > sma50_prev),
        "return_20d": ret20,
        "return_60d": ret60,
        "rsi14": rsi14,
        "volume_ratio_20d": volume_ratio,
        "high20": high20,
        "low20": low20,
        "high60": high60,
        "low60": low60,
        "near_20d_high": bool(high20 and latest >= high20 * 0.995),
        "near_20d_low": bool(low20 and latest <= low20 * 1.005),
        "signals": signals,
        "warnings": warnings,
    }


def prepare_trend_chart_frame(prices: pd.DataFrame, tail: int = 260) -> pd.DataFrame:
    """Normalize price history and add 20/50/200-day moving averages for display.

    The function is display-oriented and does not mutate the screening snapshot.
    """
    if prices is None or prices.empty:
        return pd.DataFrame(columns=["date", "close", "sma20", "sma50", "sma200"])
    frame = prices.copy()
    date_col = "date" if "date" in frame.columns else "Date"
    close_col = "close" if "close" in frame.columns else ("AdjC" if "AdjC" in frame.columns else "C")
    if date_col not in frame.columns or close_col not in frame.columns:
        return pd.DataFrame(columns=["date", "close", "sma20", "sma50", "sma200"])
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame[close_col] = pd.to_numeric(frame[close_col], errors="coerce")
    frame = frame.dropna(subset=[date_col, close_col]).sort_values(date_col)
    if frame.empty:
        return pd.DataFrame(columns=["date", "close", "sma20", "sma50", "sma200"])
    close = frame[close_col].astype(float)
    result = pd.DataFrame({
        "date": frame[date_col],
        "close": close,
        "sma20": close.rolling(20).mean(),
        "sma50": close.rolling(50).mean(),
        "sma200": close.rolling(200).mean(),
    })
    if tail and tail > 0:
        result = result.tail(int(tail))
    return result.reset_index(drop=True)


def build_trend_transition(prices: pd.DataFrame, lookback_days: int = 90) -> dict[str, Any]:
    """Compare the latest trend with the trend around ``lookback_days`` ago.

    This is intended for fresh external daily history. It distinguishes a stock
    that is still falling from one that may have escaped a prior downtrend.
    """
    if prices is None or prices.empty:
        return {
            "current": build_price_trend_snapshot(prices),
            "previous": {"trend_state": "データ不足", "trend_score": 0},
            "transition_state": "判定不能",
            "escaped_downtrend": False,
            "summary": "最新株価履歴がありません。",
        }
    frame = prices.copy()
    date_col = "date" if "date" in frame.columns else "Date"
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame.dropna(subset=[date_col]).sort_values(date_col)
    current = build_price_trend_snapshot(frame)
    if frame.empty:
        previous = {"trend_state": "データ不足", "trend_score": 0}
    else:
        cutoff = frame[date_col].max() - pd.to_timedelta(int(lookback_days), unit="D")
        earlier = frame.loc[frame[date_col] <= cutoff]
        previous = build_price_trend_snapshot(earlier)

    previous_score = int(previous.get("trend_score", 0) or 0)
    current_score = int(current.get("trend_score", 0) or 0)
    was_down = previous_score <= -2 or "下向き" in str(previous.get("trend_state", ""))
    now_positive = current_score >= 2
    now_neutral = -1 <= current_score <= 1
    escaped = bool(was_down and current_score >= 0)

    if was_down and current_score >= 5:
        transition = "下降トレンドから上昇転換を確認"
        summary = "約3カ月前は下降基調でしたが、最新系列では複数の上昇条件を満たしています。"
    elif was_down and now_positive:
        transition = "下降トレンド脱出の可能性"
        summary = "約3カ月前の下降基調から改善し、最新系列では上昇転換の兆候があります。"
    elif was_down and now_neutral:
        transition = "底打ち・下げ止まりの兆候"
        summary = "下降の勢いは弱まりましたが、上昇転換の確認には追加の値動きが必要です。"
    elif was_down and current_score <= -2:
        transition = "下降トレンド継続"
        summary = "約3カ月前から最新時点まで下降基調が継続しています。"
    elif previous_score < current_score and now_positive:
        transition = "上昇基調が改善"
        summary = "3カ月前よりトレンド指標が改善し、最新時点では上向きです。"
    elif current_score >= 2:
        transition = "上昇トレンド"
        summary = "最新時点では上昇条件が優勢です。"
    elif current_score <= -2:
        transition = "下降トレンド"
        summary = "最新時点では下降条件が優勢です。"
    else:
        transition = "方向感なし・確認待ち"
        summary = "最新時点では明確な上昇・下降の優位性を確認できません。"

    return {
        "current": current,
        "previous": previous,
        "previous_state": previous.get("trend_state", "データ不足"),
        "current_state": current.get("trend_state", "データ不足"),
        "previous_score": previous_score,
        "current_score": current_score,
        "transition_state": transition,
        "escaped_downtrend": escaped,
        "summary": summary,
        "lookback_days": lookback_days,
    }
