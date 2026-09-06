from __future__ import annotations

import math

import pandas as pd


def _floor_to_lot(quantity: float, lot: int) -> int:
    if quantity <= 0:
        return 0
    return int(math.floor(quantity / lot) * lot)


def create_order_proposals(candidates: pd.DataFrame, risk_cfg: dict) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()

    capital = float(risk_cfg["trading_capital_yen"])
    max_total = capital * float(risk_cfg["max_total_invested_ratio"])
    max_position = capital * float(risk_cfg["max_position_ratio"])
    risk_budget = capital * float(risk_cfg["risk_per_position_ratio"])
    stop_pct = float(risk_cfg["catastrophic_stop_pct"])
    take_pct = float(risk_cfg["take_profit_pct"])
    lot = int(risk_cfg["board_lot"])
    tranches = risk_cfg["entry_tranches"]

    rows: list[dict] = []
    allocated = 0.0
    selected = candidates.head(int(risk_cfg["max_positions"]))

    for _, r in selected.iterrows():
        close = float(r["close"])
        stop_price = close * (1 - stop_pct)
        risk_per_share = close - stop_price
        qty_by_risk = risk_budget / risk_per_share if risk_per_share > 0 else 0
        qty_by_cap = max_position / close
        base_qty = _floor_to_lot(min(qty_by_risk, qty_by_cap), lot)
        if base_qty <= 0:
            continue

        total_weight = sum(float(t["weight"]) for t in tranches)
        base_lots = base_qty // lot
        raw_lots = [base_lots * float(t["weight"]) / total_weight for t in tranches]
        tranche_lots = [int(math.floor(x)) for x in raw_lots]
        remainder = int(base_lots - sum(tranche_lots))
        order = sorted(range(len(raw_lots)), key=lambda i: raw_lots[i] - tranche_lots[i], reverse=True)
        for i in order[:remainder]:
            tranche_lots[i] += 1

        for idx, (t, lots_for_tranche) in enumerate(zip(tranches, tranche_lots), start=1):
            entry = round(close * (1 - float(t["discount_from_close"])), 1)
            qty = int(lots_for_tranche * lot)
            if qty <= 0:
                continue
            order_value = entry * qty
            if allocated + order_value > max_total:
                remaining_qty = _floor_to_lot((max_total - allocated) / entry, lot)
                qty = max(0, remaining_qty)
                order_value = entry * qty
            if qty <= 0:
                break

            rows.append(
                {
                    "approval_status": "未承認",
                    "code": r["code"],
                    "name": r["name"],
                    "sector": r["sector"],
                    "side": "現物買",
                    "tranche": idx,
                    "order_type": "指値",
                    "limit_price": entry,
                    "quantity": qty,
                    "estimated_amount": round(order_value),
                    "catastrophic_stop_reference": round(entry * (1 - stop_pct), 1),
                    "take_profit_reference": round(entry * (1 + take_pct), 1),
                    "score": r["score"],
                    "thesis": f"{r.get('category', '')}: {r.get('evidence', '')}",
                    "invalidation": "外的要因が構造問題と判明、営業赤字化、会社予想の大幅下方修正、財務悪化",
                    "source_url": r.get("source_url", ""),
                    "sbi_entry_note": "SBI証券で銘柄・数量・価格を本人が再確認して手入力。認証情報は本システムに保存しない。",
                }
            )
            allocated += order_value
            if allocated >= max_total:
                break
        if allocated >= max_total:
            break

    return pd.DataFrame(rows)
