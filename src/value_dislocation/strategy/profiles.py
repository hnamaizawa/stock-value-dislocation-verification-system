from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


PROFILE_SCHEMA_VERSION = "1.0"

METRIC_HELP = {
    "allowed_markets": "対象にする東証市場です。初心者はPrimeとStandardから始めると、流動性の低い銘柄を減らせます。",
    "min_average_turnover_yen_20d": "直近20営業日の1日平均売買代金です。大きいほど一般に売買しやすくなります。",
    "min_price_yen": "低位株を除外するための最低株価です。株価の低さだけで企業価値は判断できません。",
    "minimum_equity_ratio": "総資産に占める自己資本の割合です。高いほど一般に財務余力があります。",
    "minimum_operating_cf_positive_ratio_3y": "直近最大3期のうち営業CFがプラスだった割合です。本業で現金を生み出せているかを確認します。",
    "minimum_sales_cagr_3y": "売上高の年平均成長率です。大幅な縮小が続く企業を除外する目的で使います。",
    "minimum_operating_margin": "売上高に対する営業利益の割合です。0%以上なら少なくとも営業黒字です。",
    "minimum_cash_conversion_ratio": "直近通期の営業CF÷営業利益です。会計上の利益が現金を伴っているかを見る利益の質の指標です。",
    "minimum_operating_margin_change_3y": "直近最大3期で営業利益率がどこまで悪化してよいかの下限です。継続的な採算悪化を見つけます。",
    "minimum_forecast_revision_rate": "同じ対象年度の会社予想営業利益が前回予想からどこまで下方修正されても許容するかです。",
    "minimum_sector_relative_return_6m": "6か月騰落率を同業種中央値と比較し、企業固有に極端に弱い銘柄を構造悪化候補として除外する目安です。",
    "maximum_forecast_op_decline": "会社予想の営業利益が直近実績からどこまで減っても許容するかです。",
    "minimum_drawdown_52w": "現在株価が52週高値から何%以上下落していることを求めるかです。",
    "minimum_relative_underperformance_6m": "6か月で市場比較指標より何%以上劣後したことを求めるかです。自動では正式TOPIXを優先し、なければTOPIX連動ETFの調整後終値を代理利用します。",
    "quantitative_min_score": "財務、割安度、価格下落を合計した定量点の最低値です。外的要因の評価点は含めません。",
    "minimum_forecast_dividend_yield": "会社予想の1株年間配当を株価で割った予想利回りです。高すぎる利回りは減配懸念も確認してください。",
    "maximum_payout_ratio": "利益のうち配当に回す割合です。高すぎる場合は配当の継続余力に注意します。",
    "minimum_volatility_60d": "直近60営業日の終値騰落率から計算した年率ボラティリティです。高いほど値動きが大きい傾向です。",
    "minimum_average_intraday_range_20d": "直近20営業日の（高値-安値）÷終値の平均です。日中の値幅の大きさを見る補助指標です。",
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
