from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


PROFILE_SCHEMA_VERSION = "1.0"

METRIC_HELP = {
    "allowed_markets": "調べる銘柄の上場市場を選びます。Prime・Standard・Growthは東証の市場区分です。",
    "min_average_turnover_yen_20d": "直近20営業日の1日あたり売買金額の平均です。金額を大きくすると、売買が少ない銘柄を候補から外しやすくなります。",
    "min_price_yen": "候補に残す最低株価です。株価が安いことだけでは、会社が割安とはいえません。",
    "minimum_equity_ratio": "会社の資産のうち、借入金などの返済が不要な自己資本が占める割合です。一般に高いほど財務の余裕があります。",
    "minimum_operating_cf_positive_ratio_3y": "直近の決算（最大3期）で、本業による現金収入がプラスだった割合です。",
    "minimum_sales_cagr_3y": "過去約3年間で、売上が年平均どれだけ増減したかです。マイナスなら売上が縮小しています。",
    "minimum_operating_margin": "売上に対して、本業の利益がどれだけ残ったかです。0%未満は本業が赤字です。",
    "minimum_cash_conversion_ratio": "本業で得た現金を営業利益と比べます。利益に見合う現金が入っているかの目安です。",
    "minimum_operating_margin_change_3y": "過去最大3期で、本業の利益率がどれだけ下がったかを確認します。下がり方が大きい会社を見つける目安です。",
    "minimum_forecast_revision_rate": "会社が同じ年度について出した営業利益予想が、前回からどれだけ変わったかです。マイナスは下方修正です。",
    "minimum_sector_relative_return_6m": "過去6か月の株価変化を同じ業種の真ん中の値と比べます。同業他社より大きく下がった会社を見つける目安です。",
    "maximum_forecast_op_decline": "会社が予想する営業利益が、直近の実績よりどれだけ減ってよいかを設定します。",
    "minimum_drawdown_52w": "今の株価が過去52週間の最高値から、少なくともどれだけ下がった銘柄を探すかです。",
    "minimum_relative_underperformance_6m": "過去6か月で、銘柄の株価が市場全体よりどれだけ弱かったかを見ます。市場の目安は正式TOPIXを優先し、使えない場合はTOPIX連動ETFで代用します。",
    "quantitative_min_score": "財務や株価など、設定した数値条件への当てはまりを点数にしたものです。外的要因が原因かどうかは点数に含みません。",
    "minimum_forecast_dividend_yield": "会社予想の年間配当を今の株価で割った割合です。高い場合は、配当が減る可能性も確認してください。",
    "maximum_payout_ratio": "利益のうち、配当に回す割合です。割合が高すぎると、配当を続けにくくなることがあります。",
    "minimum_volatility_60d": "直近60営業日の終値の動きから、値動きの大きさを年換算した目安です。数字が大きいほど、株価が大きく上下する傾向があります。",
    "minimum_average_intraday_range_20d": "直近20営業日について、1日の最高値と最安値の幅を平均したものです。数字が大きいほど、日中によく動いています。",
}

PRESETS: dict[str, dict[str, Any]] = {
    "安全重視": {
        "description": "財務体力とキャッシュフローを重視し、候補数を絞る設定です。",
        "universe": {
            "allowed_markets": ["Prime", "Standard"],
            "min_average_turnover_yen_20d": 100_000_000,
            "min_price_yen": 300,
        },
        "screen": {
            "selection_strategy": "value_dislocation",
            "minimum_volatility_60d": 0.35,
            "minimum_average_intraday_range_20d": 0.025,
            "minimum_daytrade_activity_score": 50,
            "minimum_equity_ratio": 0.40,
            "minimum_operating_cf_positive_ratio_3y": 1.0,
            "minimum_sales_cagr_3y": -0.02,
            "minimum_operating_margin": 0.03,
            "use_structural_deterioration_guard": True,
            "minimum_cash_conversion_ratio": 0.90,
            "minimum_operating_margin_change_3y": -0.02,
            "minimum_forecast_revision_rate": -0.05,
            "minimum_sector_relative_return_6m": -0.10,
            "maximum_forecast_op_decline": -0.10,
            "minimum_drawdown_52w": -0.15,
            "minimum_relative_underperformance_6m": -0.05,
            "use_relative_underperformance_filter": True,
            "market_benchmark_mode": "auto",
            "require_forecast": False,
            "require_sales_history": True,
            "require_dividend": True,
            "minimum_annual_dividend_per_share": 1.0,
            "minimum_forecast_dividend_yield": 0.02,
            "maximum_forecast_dividend_yield": 0.06,
            "maximum_payout_ratio": 0.60,
            "exclude_forecast_dividend_cut": True,
            "quantitative_min_score": 48,
            "max_review_queue": 30,
        },
    },
    "標準": {
        "description": "財務の健全性と株価下落のバランスを取った基本設定です。",
        "universe": {
            "allowed_markets": ["Prime", "Standard", "Growth"],
            "min_average_turnover_yen_20d": 50_000_000,
            "min_price_yen": 200,
        },
        "screen": {
            "selection_strategy": "value_dislocation",
            "minimum_volatility_60d": 0.35,
            "minimum_average_intraday_range_20d": 0.025,
            "minimum_daytrade_activity_score": 50,
            "minimum_equity_ratio": 0.30,
            "minimum_operating_cf_positive_ratio_3y": 2 / 3,
            "minimum_sales_cagr_3y": -0.05,
            "minimum_operating_margin": 0.00,
            "use_structural_deterioration_guard": True,
            "minimum_cash_conversion_ratio": 0.70,
            "minimum_operating_margin_change_3y": -0.03,
            "minimum_forecast_revision_rate": -0.10,
            "minimum_sector_relative_return_6m": -0.15,
            "maximum_forecast_op_decline": -0.20,
            "minimum_drawdown_52w": -0.18,
            "minimum_relative_underperformance_6m": -0.08,
            "use_relative_underperformance_filter": True,
            "market_benchmark_mode": "auto",
            "require_forecast": False,
            "require_sales_history": False,
            "require_dividend": False,
            "minimum_annual_dividend_per_share": 0.0,
            "minimum_forecast_dividend_yield": 0.00,
            "maximum_forecast_dividend_yield": 0.10,
            "maximum_payout_ratio": 0.80,
            "exclude_forecast_dividend_cut": False,
            "quantitative_min_score": 42,
            "max_review_queue": 50,
        },
    },
    "割安重視": {
        "description": "株価下落と割安度を広く拾い、警告を確認しながら調査する設定です。",
        "universe": {
            "allowed_markets": ["Prime", "Standard", "Growth"],
            "min_average_turnover_yen_20d": 30_000_000,
            "min_price_yen": 100,
        },
        "screen": {
            "selection_strategy": "value_dislocation",
            "minimum_volatility_60d": 0.35,
            "minimum_average_intraday_range_20d": 0.025,
            "minimum_daytrade_activity_score": 50,
            "minimum_equity_ratio": 0.25,
            "minimum_operating_cf_positive_ratio_3y": 2 / 3,
            "minimum_sales_cagr_3y": -0.08,
            "minimum_operating_margin": 0.00,
            "use_structural_deterioration_guard": True,
            "minimum_cash_conversion_ratio": 0.50,
            "minimum_operating_margin_change_3y": -0.05,
            "minimum_forecast_revision_rate": -0.20,
            "minimum_sector_relative_return_6m": -0.20,
            "maximum_forecast_op_decline": -0.30,
            "minimum_drawdown_52w": -0.25,
            "minimum_relative_underperformance_6m": -0.10,
            "use_relative_underperformance_filter": True,
            "market_benchmark_mode": "auto",
            "require_forecast": False,
            "require_sales_history": False,
            "require_dividend": True,
            "minimum_annual_dividend_per_share": 1.0,
            "minimum_forecast_dividend_yield": 0.03,
            "maximum_forecast_dividend_yield": 0.08,
            "maximum_payout_ratio": 0.80,
            "exclude_forecast_dividend_cut": False,
            "quantitative_min_score": 36,
            "max_review_queue": 80,
        },
    },
}


def preset_names() -> list[str]:
    return list(PRESETS)


def preset_overrides(name: str) -> dict[str, Any]:
    if name not in PRESETS:
        raise KeyError(f"Unknown preset: {name}")
    return deepcopy({"universe": PRESETS[name]["universe"], "screen": PRESETS[name]["screen"]})


def normalize_profile_name(value: str) -> str:
    name = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠_-]+", "_", value.strip())
    name = name.strip("_.")
    return name[:80] or "my_conditions"


def profile_document(name: str, preset: str, overrides: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profile_name": name,
        "preset": preset,
        "saved_at": datetime.now().astimezone().isoformat(),
        "overrides": deepcopy(overrides),
    }


def save_profile(directory: Path, name: str, preset: str, overrides: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = normalize_profile_name(name)
    path = directory / f"{safe_name}.json"
    path.write_text(
        json.dumps(profile_document(safe_name, preset, overrides), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def list_profiles(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"), key=lambda p: p.name.lower())


def load_profile(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError("Unsupported profile schema version")
    overrides = data.get("overrides")
    if not isinstance(overrides, dict) or not isinstance(overrides.get("universe"), dict) or not isinstance(overrides.get("screen"), dict):
        raise ValueError("Invalid profile structure")
    return data
