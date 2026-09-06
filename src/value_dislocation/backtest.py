from __future__ import annotations

import numpy as np
import pandas as pd


def run_signal_backtest(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    top_n: int = 6,
    initial_capital: float = 3_000_000,
    transaction_cost_bps: float = 10,
) -> tuple[pd.DataFrame, dict]:
    """月次シグナルを翌営業日の終値で等金額保有する簡易バックテスト。

    signals columns: signal_date, code, score
    prices columns: date, code, close
    """
    sig = signals.copy()
    sig["signal_date"] = pd.to_datetime(sig["signal_date"])
    px = prices[["date", "code", "close"]].copy()
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values(["date", "code"])
    all_dates = sorted(px["date"].unique())
    if not all_dates or sig.empty:
        return pd.DataFrame(), {}

    rebalance_dates = sorted(sig["signal_date"].unique())
    equity = initial_capital
    holdings: dict[str, float] = {}
    cash = initial_capital
    history = []
    cost_rate = transaction_cost_bps / 10_000

    for current_date in all_dates:
        day_px = px.loc[px["date"] == current_date].set_index("code")["close"].to_dict()
        portfolio_value = cash + sum(qty * day_px.get(code, 0) for code, qty in holdings.items())

        if current_date in rebalance_dates:
            selected = (
                sig.loc[sig["signal_date"] == current_date]
                .sort_values("score", ascending=False)
                .head(top_n)
            )
            target_codes = selected["code"].tolist()
            # 全売却後に等金額で再構築。約定可能な銘柄だけ対象。
            sell_value = sum(qty * day_px.get(code, 0) for code, qty in holdings.items())
            cash += sell_value * (1 - cost_rate)
            holdings = {}
            tradable = [c for c in target_codes if day_px.get(c, 0) > 0]
            if tradable:
                target_value = cash / len(tradable)
                spent = 0.0
                for code in tradable:
                    price = day_px[code]
                    qty = np.floor((target_value * (1 - cost_rate)) / price)
                    if qty > 0:
                        value = qty * price
                        fee = value * cost_rate
                        holdings[code] = qty
                        spent += value + fee
                cash -= spent
            portfolio_value = cash + sum(qty * day_px.get(code, 0) for code, qty in holdings.items())

        equity = portfolio_value
        history.append({"date": current_date, "equity": equity, "cash": cash})

    curve = pd.DataFrame(history)
    curve["return"] = curve["equity"].pct_change().fillna(0)
    curve["cum_return"] = curve["equity"] / initial_capital - 1
    running_max = curve["equity"].cummax()
    curve["drawdown"] = curve["equity"] / running_max - 1
    years = max((curve["date"].iloc[-1] - curve["date"].iloc[0]).days / 365.25, 1 / 365.25)
    cagr = (curve["equity"].iloc[-1] / initial_capital) ** (1 / years) - 1
    vol = curve["return"].std() * np.sqrt(252)
    sharpe = curve["return"].mean() / curve["return"].std() * np.sqrt(252) if curve["return"].std() else np.nan
    metrics = {
        "final_equity": round(float(curve["equity"].iloc[-1]), 2),
        "total_return": round(float(curve["cum_return"].iloc[-1]), 4),
        "cagr": round(float(cagr), 4),
        "annualized_volatility": round(float(vol), 4),
        "max_drawdown": round(float(curve["drawdown"].min()), 4),
        "sharpe": round(float(sharpe), 3) if pd.notna(sharpe) else None,
    }
    return curve, metrics
