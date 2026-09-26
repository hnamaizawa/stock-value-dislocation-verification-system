from __future__ import annotations

import hashlib
import html
import json
import os
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

import pandas as pd
import streamlit as st

from value_dislocation.codes import display_tse_code
from value_dislocation.config import load_config
from value_dislocation.data.performance import load_feature_snapshot
from value_dislocation.data.latest_quote import (
    YAHOO_BULK_FETCH_BLOCK_THRESHOLD,
    assess_yahoo_history_freshness,
    fetch_yahoo_finance_history,
    fetch_yahoo_finance_quote,
    yahoo_bulk_fetch_allowed,
)
from value_dislocation.data.market_context import (fetch_analyst_snapshot, fetch_market_news, translate_market_news_to_japanese)
from value_dislocation.data.sbi_import import parse_sbi_screening_csv
from value_dislocation.data.security_master_history import load_security_master_history
from value_dislocation.decision import build_buy_readiness, build_split_entry_plan, build_intuitive_signal, build_entry_price_guidance, build_price_trend_snapshot, build_trend_transition, prepare_trend_chart_frame
from value_dislocation.data.search import (
    RealDataNotReadyError,
    load_curated_latest,
    search_companies,
    stock_detail,
)
from value_dislocation.real_pipeline import run_real_pipeline
from value_dislocation.external_event_review import (
    approval_completeness_issues,
    candidate_order_preview_allowed,
    external_event_review_is_approved,
    load_external_event_review,
    save_external_event_review,
)
from value_dislocation.ui_preferences import load_ui_preferences, save_ui_preferences
from value_dislocation.history import (
    STAR_OUTCOME_HORIZONS,
    attach_daily_final_evaluations,
    select_slow_revaluation_batch,
    build_star_events,
    condition_performance,
    daily_evaluation_counts,
    daily_history_text_summary,
    evaluation_history_text_summary,
    evaluation_symbol_counts,
    enrich_star_events_with_market_histories,
    load_analysis_history,
    load_evaluation_history,
    load_star_outcomes,
    reconcile_star_outcomes,
    revaluate_unassessed_rows,
    upsert_daily_evaluations,
    save_star_outcomes,
    summarize_star_outcomes_by_code,
    star_forward_return_summary,
    star_validation_text_summary,
    write_star_outcomes,
)
from value_dislocation.history_visuals import (
    condition_outcome_bubbles,
    condition_return_heatmap,
    security_return_bubbles,
)
from value_dislocation import __version__
from value_dislocation.walkforward_cache import (
    load_walk_forward_result,
    save_walk_forward_result,
    walk_forward_cache_key,
)
from value_dislocation.validation import (
    WalkForwardConfig,
    attribution_outcome_summary,
    walk_forward_summary,
    walk_forward_validation,
)
from value_dislocation.hypothesis_invalidation import (
    METRIC_DEFINITIONS,
    evaluate_hypothesis_invalidation,
    normalize_structured_conditions,
    structured_conditions_from_ui_rows,
    format_threshold_input_value,
)
from value_dislocation.strategy.criteria import (
    apply_quantitative_criteria,
    copy_with_screen_overrides,
    prepare_quantitative_universe,
    screening_funnel,
    shortlist_from_table,
)
from value_dislocation.strategy.profiles import (
    METRIC_HELP,
    PRESETS,
    list_profiles,
    load_profile,
    preset_names,
    preset_overrides,
    profile_document,
    save_profile,
)

ROOT = Path(__file__).resolve().parent
SLOW_REVALUATION_DELAY_SECONDS = 0.75
SLOW_REVALUATION_BATCH_PAUSE_SECONDS = 2.0
SLOW_REVALUATION_BATCH_OPTIONS = [10, 20, 50]
REAL_CONFIG = ROOT / "config" / "real_data.yaml"
REAL_OUTPUT = ROOT / "outputs" / "real"
PROFILE_DIR = ROOT / "config" / "user_profiles"
EXTERNAL_REVIEW_DIR = ROOT / "config" / "external_event_reviews"
UI_PREFERENCES_PATH = ROOT / "config" / "ui_preferences.json"
DEMO_OUTPUT = ROOT / "outputs"
WALK_FORWARD_CACHE = REAL_OUTPUT / "walk_forward_cache"
STOCK_DETAIL_URL_PATH = "render_stock_search"

st.set_page_config(page_title="Stock Value Dislocation Verification System", layout="wide")


def _apply_ui_theme(theme: str) -> None:
    base_css = """
    <style>
    [data-testid="stNavigation"] button p,
    [data-testid="stNavigation"] a p,
    [data-testid="stTopNav"] button p {
        font-size: 1.12rem !important;
        font-weight: 650 !important;
    }
    [data-testid="stNavigation"] button,
    [data-testid="stNavigation"] a {
        min-height: 2.8rem !important;
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
    }
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)
    if theme != "やわらかパステル":
        return
    st.markdown(
        """
        <style>
        /* Vivid pastel theme: presentation only. Analysis and scoring are unchanged. */
        .stApp {
            background:
                radial-gradient(circle at 6% 6%, rgba(255, 137, 184, .72) 0, rgba(255, 137, 184, 0) 30%),
                radial-gradient(circle at 94% 8%, rgba(176, 150, 255, .72) 0, rgba(176, 150, 255, 0) 32%),
                radial-gradient(circle at 90% 88%, rgba(112, 218, 255, .66) 0, rgba(112, 218, 255, 0) 31%),
                radial-gradient(circle at 12% 90%, rgba(255, 210, 112, .58) 0, rgba(255, 210, 112, 0) 28%),
                linear-gradient(135deg, #fff0f7 0%, #fff4d9 27%, #f1e9ff 55%, #e7f9ff 78%, #edfff4 100%);
            background-attachment: fixed;
        }
        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 15% 8%, rgba(255, 119, 177, .38), transparent 30%),
                linear-gradient(180deg, #ffd4e7 0%, #eadcff 38%, #d9f5ff 70%, #e8ffe9 100%);
            border-right: 2px solid #ef9fc8;
            box-shadow: 8px 0 26px rgba(157, 90, 164, .18);
        }
        h1 { color: #7d3f75 !important; text-shadow: 0 2px 0 rgba(255,255,255,.92), 0 5px 16px rgba(201,84,157,.18); }
        h2 { color: #68468a !important; }
        h3 { color: #9c4674 !important; }
        h1, h2, h3 { letter-spacing: .018em; }
        p, label, [data-testid="stCaptionContainer"] { color: #5f4d60; }

        [data-testid="stMetric"], [data-testid="stExpander"],
        [data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 22px !important;
        }
        [data-testid="stMetric"] {
            background: linear-gradient(145deg, rgba(255,255,255,.96), rgba(255,225,239,.88) 42%, rgba(230,221,255,.88) 100%);
            border: 2px solid #f0a8ce;
            padding: .76rem .9rem;
            box-shadow: 0 10px 26px rgba(177, 90, 159, .18), inset 0 1px 0 rgba(255,255,255,.92);
        }
        [data-testid="stMetricValue"] { color: #733e6d !important; font-weight: 760 !important; }
        [data-testid="stMetricLabel"] { color: #865775 !important; font-weight: 650 !important; }

        [data-testid="stExpander"] {
            background: linear-gradient(135deg, rgba(255,246,251,.94), rgba(243,236,255,.90));
            border: 2px solid #e7b6dd !important;
            box-shadow: 0 7px 20px rgba(152, 91, 159, .12);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(135deg, rgba(255,247,252,.76), rgba(233,248,255,.70));
            border-color: #eab6d7 !important;
            box-shadow: 0 8px 22px rgba(136, 98, 158, .09);
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: 999px !important;
            border: 2px solid #e98fbe !important;
            background: linear-gradient(115deg, #ffb8d5 0%, #ffd6a6 28%, #d9c5ff 58%, #afe8ff 82%, #c5f5cf 100%) !important;
            color: #68445f !important;
            font-weight: 760 !important;
            box-shadow: 0 7px 18px rgba(176, 83, 151, .20), inset 0 1px 0 rgba(255,255,255,.75) !important;
            transition: transform .14s ease, box-shadow .14s ease, filter .14s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color: #d96aa5 !important;
            background: linear-gradient(115deg, #ff9fc8 0%, #ffc989 28%, #cbb0ff 58%, #91dcff 82%, #a9edb8 100%) !important;
            box-shadow: 0 10px 24px rgba(164, 70, 142, .27) !important;
            transform: translateY(-2px) scale(1.01);
            filter: saturate(1.08);
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(115deg, #ff8fbd 0%, #ffc275 30%, #bda0ff 60%, #79d5ff 100%) !important;
            color: #57354f !important;
            border: 2px solid #db72ad !important;
            box-shadow: 0 8px 22px rgba(161, 71, 144, .25) !important;
        }

        div[data-baseweb="select"] > div,
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextArea"] textarea {
            border-radius: 16px !important;
            background: linear-gradient(135deg, rgba(255,255,255,.97), rgba(255,238,248,.92)) !important;
            border: 2px solid #e9afd1 !important;
        }
        div[data-baseweb="select"] > div:focus-within,
        [data-testid="stTextInput"] input:focus,
        [data-testid="stNumberInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus {
            border-color: #b990ef !important;
            box-shadow: 0 0 0 3px rgba(190, 143, 238, .28), 0 5px 16px rgba(194, 109, 181, .12) !important;
        }

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: .42rem;
            background: linear-gradient(90deg, rgba(255,205,226,.82), rgba(231,215,255,.84), rgba(202,239,255,.82));
            border: 2px solid #ebb4d6;
            border-radius: 999px;
            padding: .34rem .44rem;
            box-shadow: 0 7px 18px rgba(153, 90, 153, .13);
        }
        [data-testid="stTabs"] button[role="tab"] {
            border-radius: 999px !important;
            color: #77516f !important;
            font-weight: 680 !important;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background: linear-gradient(115deg, #ff9fc8 0%, #ffd08f 35%, #c7aeff 68%, #9fe1ff 100%) !important;
            color: #58384f !important;
            box-shadow: 0 4px 12px rgba(145, 71, 141, .18) !important;
        }

        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
            border-radius: 18px !important;
            overflow: hidden;
            border: 2px solid #eab2d5;
            box-shadow: 0 7px 20px rgba(146, 87, 148, .10);
        }
        [data-testid="stAlert"] {
            border-radius: 20px !important;
            border: 2px solid #e5b0d3 !important;
            box-shadow: 0 5px 16px rgba(145, 90, 144, .09);
        }
        [data-testid="stProgress"] > div > div > div > div {
            background: linear-gradient(90deg, #ff91bf 0%, #ffc978 27%, #b99cff 55%, #79d9ff 78%, #98e8b4 100%) !important;
        }
        hr { border-color: #e9acd0 !important; opacity: .85; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _persist_ui_theme() -> None:
    save_ui_preferences(UI_PREFERENCES_PATH, {"ui_theme": st.session_state.get("ui_theme", "標準")})


if "ui_theme" not in st.session_state:
    st.session_state["ui_theme"] = load_ui_preferences(UI_PREFERENCES_PATH).get("ui_theme", "標準")

with st.sidebar:
    st.markdown("### 画面テーマ")
    ui_theme = st.selectbox(
        "見た目",
        ["標準", "やわらかパステル"],
        key="ui_theme",
        on_change=_persist_ui_theme,
        help="選択したテーマはこのPCに保存され、画面の再読み込み後も維持されます。分析内容は変わりません。",
    )
_apply_ui_theme(ui_theme)

st.title("Stock Value Dislocation Verification System")
st.caption(
    "J-Quantsの実データから日本株を検索し、条件を画面で変更して定量候補を調査します。"
    "SBI証券への接続、ログイン、注文送信は行いません。"
)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _format_pct(value) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "-"


DIVIDEND_WITHHOLDING_RATE = 0.20315



METRIC_DESCRIPTIONS = {
    "close": "分析基準日の終値です。外部最新株価とは別に保持し、候補抽出や財務評価の基準として使います。",
    "drawdown_52w": "過去約52週間の高値から現在の分析株価がどれだけ下落したかを示します。マイナス幅が大きいほど高値から大きく下がっています。",
    "return_6m": "約6か月前から分析基準日までの株価騰落率です。",
    "relative_return_6m": "個別株の6か月騰落率から、市場比較指標の6か月騰落率を差し引いた値です。マイナスほど市場より弱い動きです。",
    "sales_cagr_3y": "直近数年間の売上高の年平均成長率です。プラスは拡大、マイナスは縮小傾向を示します。",
    "operating_margin": "売上高のうち本業の営業利益として残った割合です。業種差が大きいため同業比較を重視します。",
    "equity_ratio": "総資産に占める自己資本の割合です。一般に高いほど借入依存が低く、財務余力があると考えられます。",
    "forecast_annual_dividend_per_share": "会社予想を優先して採用した、1株当たりの年間配当見込みです。予想がない場合は直近実績を使うことがあります。",
    "forecast_dividend_yield": "1株当たり予想年間配当を表示株価で割った比率です。高すぎる場合は減配懸念も確認します。",
    "payout_ratio": "利益のうち配当に回す割合です。高すぎる場合、配当維持の余力が小さい可能性があります。",
    "forecast_dividend_change_rate": "前期年間配当に対する予想年間配当の増減率です。プラスは増配、マイナスは減配予想です。",
}

# Keep beginner-facing explanations in one place so the same term means the
# same thing in filters, metric cards, and table-column tooltips.
ANALYSIS_ITEM_HELP = {
    "code": "東京証券取引所の銘柄コードです。",
    "コード": "東京証券取引所の銘柄コードです。",
    "name": "上場会社の名称です。",
    "企業名": "上場会社の名称です。",
    "market": "Prime・Standard・Growthなど、銘柄が上場している市場区分です。",
    "市場": "Prime・Standard・Growthなど、銘柄が上場している市場区分です。",
    "sector": "会社の主な事業内容に基づく業種区分です。",
    "close": METRIC_DESCRIPTIONS["close"],
    "終値": METRIC_DESCRIPTIONS["close"],
    "分析終値": "候補抽出に使ったJ-Quants分析基準日の終値です。最新株価とは異なる場合があります。",
    "最新株価": "Yahoo Finance系から取得できた参考用の最新株価です。注文前にはSBI証券で確認してください。",
    "drawdown_52w": METRIC_DESCRIPTIONS["drawdown_52w"],
    "52週高値比": METRIC_DESCRIPTIONS["drawdown_52w"],
    "return_6m": METRIC_DESCRIPTIONS["return_6m"],
    "6か月騰落率": METRIC_DESCRIPTIONS["return_6m"],
    "relative_return_6m": METRIC_DESCRIPTIONS["relative_return_6m"],
    "市場比較相対": METRIC_DESCRIPTIONS["relative_return_6m"],
    "sales_cagr_3y": METRIC_DESCRIPTIONS["sales_cagr_3y"],
    "operating_margin": METRIC_DESCRIPTIONS["operating_margin"],
    "equity_ratio": METRIC_DESCRIPTIONS["equity_ratio"],
    "forecast_dividend_yield": METRIC_DESCRIPTIONS["forecast_dividend_yield"],
    "quantitative_score": "財務・割安度・株価下落など、定量条件の充足度を合計した比較用スコアです。",
    "strategy_score": "選択中の抽出ルールで計算した比較用スコアです。利益確率ではありません。",
    "定量スコア": "財務・割安度・株価下落など、定量条件の充足度を合計した比較用スコアです。",
    "スコア": "条件の充足度を比較する参考点です。将来の利益を保証しません。",
    "selected_for_review": "定量条件を通過し、人が詳しく確認する候補になったかを示します。",
    "selection_strategy": "候補抽出に使ったルールです。割安株調査または値動き活発度などを表します。",
    "抽出ルール": "候補抽出に使ったルールです。割安株調査または値動き活発度などを表します。",
    "final_evaluation": "最新トレンドを含めて保存した最終評価です。◎☆、◎、○、△、×などで表します。",
    "intuitive_symbol": "主要条件とトレンドをまとめた直感的な評価記号です。",
    "評価": "主要条件とトレンドをまとめた評価です。単独で売買を決めるものではありません。",
    "最新判定": "外部最新日足で再確認したトレンド評価です。定量スコア自体は変更しません。",
    "evaluation_status": "当日評価済み、後日補完、未評価など、評価データの状態です。",
    "未評価理由": "最終評価を作れなかった理由です。データ不足や外部取得失敗などを区別します。",
    "analysis_date": "定量分析を実行し、候補状態を保存した日です。",
    "evaluation_date": "最新トレンド評価を保存した日です。",
    "data_as_of": "分析に使用した市場・財務データの基準日です。",
    "selection_date": "Walk-Forwardで、その時点の情報だけを使って候補を選んだ日です。",
    "star_date": "◎☆評価が記録された日です。",
    "first_star_date": "この銘柄が最初に◎☆になった日です。",
    "latest_star_date": "この銘柄が直近で◎☆になった日です。",
    "star_count": "保存履歴の中で◎☆になった回数です。",
    "entry_price": "評価日の終値を使った検証上の基準価格です。実際の約定価格ではありません。",
    "latest_entry_price": "直近の◎☆評価日における検証上の基準価格です。",
    "return_10d": "候補選定後10取引日目までの株価リターンです。",
    "return_20d": "候補選定後20取引日目までの株価リターンです。",
    "return_30d": "候補選定後30取引日目までの株価リターンです。",
    "return_60d": "候補選定後60取引日目までの株価リターンです。",
    "return_90d": "候補選定後90取引日目までの株価リターンです。",
    "return_180d": "候補選定後180取引日目までの株価リターンです。",
    "selected_return": "その時点で選ばれた候補銘柄の、その後の平均リターンです。",
    "control_return": "似た条件でも選ばれなかった比較銘柄の、その後の平均リターンです。",
    "selection_effect": "候補銘柄のリターンから比較銘柄のリターンを引いた差です。プラスほど選別が有効だった可能性があります。",
    "external_shock_ratio": "株価変動のうち、市場・業種など企業外の要因で説明できる割合の参考値です。",
    "外因説明率": "株価変動のうち、市場・業種など企業外の要因で説明できる割合の参考値です。",
    "master_coverage_ratio": "過去時点の対象銘柄を、現在保存している会社マスターでどれだけ確認できたかを示します。",
    "survivorship_bias_warning": "上場廃止などで現在の会社マスターから消えた銘柄を復元できない可能性を示す注意です。",
    "候補イベント": "Walk-Forwardの各過去時点で定量条件を通過した候補の延べ件数です。",
    "再現時点": "過去の何日分をさかのぼって候補抽出を再現したかを示します。",
    "検証期間": "Walk-Forwardで最初に再現した日から最後に再現した日までの範囲です。",
    "会社マスター最低カバレッジ": "検証期間中で最も低かった会社マスターの網羅率です。低いほど生存者バイアスに注意が必要です。",
    "fail_reasons": "必須条件を通過できなかった理由です。",
    "warning_reasons": "候補から直ちに除外はしないものの、追加確認が必要な注意点です。",
    "種類": "確認材料を価格・業績・配当などに分類したものです。",
    "確認条件": "売却や再確認を検討するきっかけの例です。自動注文条件ではありません。",
    "意味": "その条件が投資仮説に与える影響を簡単に説明しています。",
    "判定": "現在のデータによる通過・注意・不通過・不明の状態です。",
    "確認項目": "購入判断前に確認する材料です。",
    "現在の内容": "現在取得できているデータから整理した確認結果です。",
    "disclosure_date": "決算情報が公表され、市場参加者が知ることができた日です。",
    "period_end": "決算が対象とする会計期間の終了日です。",
    "statement_type": "本決算・四半期決算など、財務諸表の種類です。",
    "sales": "会社が商品やサービスの提供で得た売上高です。",
    "operating_profit": "本業から得た利益です。",
    "operating_cf": "本業による現金の増減です。利益が実際の現金につながっているかを見る材料です。",
    "equity": "返済義務のない自己資本の金額です。",
    "total_assets": "会社が保有する資産の合計です。",
    "forecast_operating_profit": "会社が予想している通期の営業利益です。",
    "eps": "1株当たり利益です。株価と利益の関係を見る基礎指標です。",
    "book_value_per_share": "1株当たり純資産です。PBRを考える基礎になります。",
    "actual_annual_dividend_per_share": "直近実績の1株当たり年間配当です。",
    "forecast_annual_dividend_per_share": METRIC_DESCRIPTIONS["forecast_annual_dividend_per_share"],
    "actual_payout_ratio": "直近実績で、利益のうち配当に回した割合です。",
    "forecast_payout_ratio": "会社予想利益に対する予想配当の割合です。",
    "date": "この行の価格・予定・記録が対象とする日です。",
}


def _analysis_help(item: str, fallback: str | None = None) -> str:
    """Return a short beginner-facing explanation for one analysis item."""
    return ANALYSIS_ITEM_HELP.get(str(item), fallback or f"{item}を分析・比較するための項目です。")


def _analysis_column_config(frame: pd.DataFrame) -> dict:
    """Add hover help to every displayed analysis-table column."""
    return {
        str(column): st.column_config.Column(
            label=str(column),
            help=_analysis_help(str(column)),
        )
        for column in frame.columns
    }


def _analysis_dataframe(frame: pd.DataFrame, **kwargs) -> None:
    """Render an analysis table with beginner-facing help on every header."""
    existing = dict(kwargs.pop("column_config", {}) or {})
    generated = _analysis_column_config(frame)
    generated.update(existing)
    st.dataframe(frame, column_config=generated, **kwargs)

GENERAL_METRIC_GUIDES = {
    "close": "比較基準なし",
    "drawdown_52w": "目安 -20%以下",
    "return_6m": "目安 0%",
    "relative_return_6m": "目安 -10%以下",
    "sales_cagr_3y": "目安 3%",
    "operating_margin": "目安 10%",
    "equity_ratio": "目安 40%",
    "forecast_annual_dividend_per_share": "銘柄ごと",
    "forecast_dividend_yield": "目安 3%",
    "payout_ratio": "目安 40%",
    "forecast_dividend_change_rate": "目安 0%以上",
}


def _metric_reference_label(
    prepared: pd.DataFrame,
    company: pd.Series,
    metric: str,
) -> str:
    """Return an industry median when reliable, otherwise a beginner guide."""
    guide = GENERAL_METRIC_GUIDES.get(metric, "参考値なし")
    if metric in {"close", "forecast_annual_dividend_per_share"}:
        return guide
    if prepared is None or prepared.empty or metric not in prepared.columns:
        return guide
    sector = str(company.get("sector", "")).strip()
    if not sector or "sector" not in prepared.columns:
        return guide
    peers = prepared.loc[prepared["sector"].astype(str).eq(sector), metric]
    peers = pd.to_numeric(peers, errors="coerce").dropna()
    if len(peers) < 5:
        return guide
    median = float(peers.median())
    if metric in {
        "drawdown_52w", "return_6m", "relative_return_6m", "sales_cagr_3y",
        "operating_margin", "equity_ratio", "forecast_dividend_yield",
        "payout_ratio", "forecast_dividend_change_rate",
    }:
        return f"同業中央値 {median:.1%}"
    return guide


def _metric_title(name: str, prepared: pd.DataFrame, company: pd.Series, metric: str) -> str:
    return f"{name}（{_metric_reference_label(prepared, company, metric)}）"


def _render_reference_metric(
    container,
    name: str,
    reference: str,
    value: str,
    delta: str | None = None,
    help_text: str | None = None,
) -> None:
    delta_html = f'<div class="vd-metric-delta">{html.escape(delta)}</div>' if delta else ''
    tooltip = html.escape(help_text or f"{name}の参考値です。")
    card_html = (
        '<div class="vd-metric-card">'
        f'<div class="vd-metric-label vd-help-label" title="{tooltip}">{html.escape(name)} '
        f'<span class="vd-metric-reference">（{html.escape(reference)}）</span>'
        '<span class="vd-help-icon" aria-label="項目の説明">ⓘ</span></div>'
        f'<div class="vd-metric-value">{html.escape(value)}</div>'
        f'{delta_html}</div>'
    )
    container.markdown(card_html, unsafe_allow_html=True)


st.markdown("""
<style>
.vd-metric-card { min-height: 88px; padding: 0.05rem 0 0.35rem 0; }
.vd-metric-label { font-size: 0.88rem; color: rgba(49,51,63,.72); line-height: 1.25; }
.vd-metric-reference { font-size: 0.72rem; color: rgba(49,51,63,.58); white-space: nowrap; }
.vd-metric-value { font-size: 2rem; line-height: 1.25; margin-top: .32rem; color: rgb(49,51,63); }
.vd-metric-delta { font-size: .82rem; margin-top: .12rem; }
.vd-help-label { cursor: help; text-decoration: underline dotted rgba(49,51,63,.35); text-underline-offset: 3px; }
.vd-help-icon { font-size: .68rem; margin-left: .25rem; color: rgba(49,51,63,.48); }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def _latest_external_quote(code: str) -> dict:
    return fetch_yahoo_finance_quote(code).to_dict()


@st.cache_data(ttl=900, show_spinner=False)
def _latest_external_history(code: str) -> pd.DataFrame:
    return fetch_yahoo_finance_history(code, period="1y")


@st.cache_data(ttl=3600, show_spinner=False)
def _history_validation_market_history(code: str) -> pd.DataFrame:
    return fetch_yahoo_finance_history(code, period="2y")


def _path_signature(path: Path) -> tuple[str, int, int]:
    try:
        stat = path.stat()
        return (str(path), int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        return (str(path), 0, 0)


def _analysis_history_signature(start, end) -> tuple[tuple[str, int, int], ...]:
    folder = ROOT / "data" / "history" / "analysis"
    if not folder.exists():
        return tuple()
    items = []
    for path in sorted(folder.glob("????-??-??.csv.gz")):
        try:
            day = pd.Timestamp(path.name[:10]).date()
        except Exception:
            continue
        if start and day < start:
            continue
        if end and day > end:
            continue
        items.append(_path_signature(path))
    return tuple(items)


def _evaluation_history_signature() -> tuple[str, int, int]:
    return _path_signature(ROOT / "data" / "history" / "evaluations" / "evaluations.csv.gz")


def _star_outcomes_signature() -> tuple[str, int, int]:
    return _path_signature(ROOT / "data" / "history" / "outcomes" / "star_outcomes.csv.gz")


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_load_analysis_history(root_text: str, start_text: str, end_text: str, selected_only: bool, signature) -> pd.DataFrame:
    start = pd.Timestamp(start_text).date() if start_text else None
    end = pd.Timestamp(end_text).date() if end_text else None
    return load_analysis_history(Path(root_text), start=start, end=end, selected_only=selected_only)


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_load_evaluation_history(root_text: str, signature) -> pd.DataFrame:
    return load_evaluation_history(Path(root_text))


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_load_attached_analysis_history(
    root_text: str,
    start_text: str,
    end_text: str,
    selected_only: bool,
    analysis_signature,
    evaluation_signature,
) -> pd.DataFrame:
    start = pd.Timestamp(start_text).date() if start_text else None
    end = pd.Timestamp(end_text).date() if end_text else None
    root = Path(root_text)
    analysis = load_analysis_history(root, start=start, end=end, selected_only=selected_only)
    evaluations = load_evaluation_history(root)
    return attach_daily_final_evaluations(analysis, evaluations)


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_load_star_outcomes(root_text: str, signature) -> pd.DataFrame:
    return load_star_outcomes(Path(root_text))


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_condition_performance(root_text: str, analysis_signature, star_signature) -> pd.DataFrame:
    events = load_star_outcomes(Path(root_text))
    return condition_performance(Path(root_text), events)


def _history_page_slice(frame: pd.DataFrame, key: str, *, default_size: int = 200, compact_sizes: bool = False) -> pd.DataFrame:
    if frame.empty:
        return frame
    sizes = [25, 50, 100, 200] if compact_sizes else [100, 200, 500, 1000]
    default_index = sizes.index(default_size) if default_size in sizes else min(1, len(sizes) - 1)
    page_size = int(st.selectbox("1ページの表示件数", sizes, index=default_index, key=f"{key}_page_size"))
    total_pages = max(1, (len(frame) + page_size - 1) // page_size)
    page_key = f"{key}_page_no"
    current = int(st.session_state.get(page_key, 1))
    if current < 1 or current > total_pages:
        current = 1
        st.session_state[page_key] = current

    nav1, nav2, nav3, nav4 = st.columns([1, 1.3, 1, 4])
    if nav1.button("◀ 前へ", key=f"{key}_prev", disabled=current <= 1):
        st.session_state[page_key] = current - 1
        st.rerun()
    page_no = int(nav2.number_input("ページ", min_value=1, max_value=total_pages, value=current, step=1, key=page_key))
    if nav3.button("次へ ▶", key=f"{key}_next", disabled=page_no >= total_pages):
        st.session_state[page_key] = page_no + 1
        st.rerun()
    start = (page_no - 1) * page_size
    nav4.caption(
        f"全 {len(frame):,}件を表示対象にしています。 "
        f"{start + 1:,}～{min(start + page_size, len(frame)):,}件 / {total_pages:,}ページ"
    )
    return frame.iloc[start:start + page_size].copy()


@st.cache_data(ttl=900, show_spinner=False)
def _latest_market_news(code: str) -> list[dict]:
    return translate_market_news_to_japanese(fetch_market_news(code, limit=10))


@st.cache_data(ttl=900, show_spinner=False)
def _latest_analyst_snapshot(code: str) -> dict:
    return fetch_analyst_snapshot(code).to_dict()


def _format_number(value, digits: int = 0) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _render_trend_price_chart(
    price_history: pd.DataFrame,
    *,
    entry_guidance: dict | None = None,
    title: str = "株価・移動平均線",
) -> None:
    """Render an intuitive price chart with 20/50/200-day moving averages."""
    chart = prepare_trend_chart_frame(price_history, tail=260)
    if chart.empty:
        st.info("グラフ表示に必要な株価履歴がありません。")
        return
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.line_chart(chart.set_index("date")[["close", "sma20", "sma50", "sma200"]], width="stretch")
        st.caption("Plotlyが利用できないため簡易グラフを表示しています。setup_windows.cmd を実行すると詳細グラフを利用できます。")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=chart["date"], y=chart["close"], mode="lines", name="株価", line={"width": 3}))
    fig.add_trace(go.Scatter(x=chart["date"], y=chart["sma20"], mode="lines", name="20日線", line={"width": 2}))
    fig.add_trace(go.Scatter(x=chart["date"], y=chart["sma50"], mode="lines", name="50日線", line={"width": 2}))
    fig.add_trace(go.Scatter(x=chart["date"], y=chart["sma200"], mode="lines", name="200日線", line={"width": 2}))

    if len(chart) > 1:
        latest = chart.iloc[-1]
        fig.add_trace(go.Scatter(
            x=[latest["date"]], y=[latest["close"]], mode="markers+text", name="最新株価",
            text=[f"¥{latest['close']:,.1f}"], textposition="top center", marker={"size": 10},
            showlegend=False,
        ))
        three_month_cutoff = chart["date"].max() - pd.to_timedelta(90, unit="D")
        fig.add_vline(x=three_month_cutoff, line_dash="dot", annotation_text="約3カ月前", annotation_position="top left")

    guidance = entry_guidance or {}
    zone_low = guidance.get("zone_low")
    zone_high = guidance.get("zone_high")
    if zone_low is not None and zone_high is not None:
        fig.add_hrect(y0=float(zone_low), y1=float(zone_high), opacity=0.12, line_width=0, annotation_text="買い検討価格帯", annotation_position="top left")
    if guidance.get("chase_limit") is not None:
        fig.add_hline(y=float(guidance["chase_limit"]), line_dash="dash", annotation_text="追いかけ買い上限", annotation_position="bottom right")
    if guidance.get("reconsider_below") is not None:
        fig.add_hline(y=float(guidance["reconsider_below"]), line_dash="dot", annotation_text="再評価ライン", annotation_position="top right")

    fig.update_layout(
        title=title,
        xaxis_title="日付", yaxis_title="株価（円）",
        hovermode="x unified", legend={"orientation": "h", "y": 1.08, "x": 0},
        margin={"l": 20, "r": 20, "t": 70, "b": 20}, height=500,
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption("太線が株価、20日線＝短期、50日線＝中期、200日線＝長期の目安です。価格帯やラインは参考表示で、注文指示ではありません。")


def _render_history_analytical_visuals(star_events: pd.DataFrame, perf: pd.DataFrame) -> None:
    """Render local-only multi-dimensional history analysis charts."""
    try:
        import numpy as np
        import plotly.graph_objects as go
    except ImportError:
        st.info("分析グラフの表示にはPlotlyが必要です。表形式の実績は引き続き確認できます。")
        return

    st.markdown("### 多面的な実績分析")
    st.caption(
        "保存済み履歴だけを組み合わせて、条件・期間・リターン・プラス率・確定件数の関係を可視化します。"
        "円が大きいほど観測件数が多いことを表します。相関や傾向であり、因果関係や将来利益を保証しません。"
    )
    heat_tab, security_tab = st.tabs(
        ["条件×期間ヒートマップ", "銘柄の期間比較バブル"]
    )

    with heat_tab:
        returns, counts = condition_return_heatmap(perf)
        if returns.empty or not returns.notna().any().any():
            st.info("ヒートマップに必要な条件別の確定実績がまだありません。")
        else:
            min_count = st.selectbox(
                "表示する最小確定件数",
                [1, 3, 5, 10, 20],
                index=0,
                key="history_heatmap_min_count",
                help="少数データによる偶然の偏りを避けるため、各マスに必要な最低件数を指定します。",
            )
            visible = returns.mask(counts < int(min_count))
            if not visible.notna().any().any():
                st.info("指定した最低件数を満たす条件×期間がありません。件数を下げて確認してください。")
            else:
                values = visible.to_numpy(dtype=float)
                max_abs = float(np.nanmax(np.abs(values))) if np.isfinite(values).any() else 1.0
                labels = np.empty(values.shape, dtype=object)
                for row_idx in range(values.shape[0]):
                    for col_idx in range(values.shape[1]):
                        value = values[row_idx, col_idx]
                        labels[row_idx, col_idx] = (
                            f"{value:+.1f}%<br>n={counts.iloc[row_idx, col_idx]:,}"
                            if np.isfinite(value)
                            else ""
                        )
                fig = go.Figure(go.Heatmap(
                    z=values,
                    x=visible.columns.tolist(),
                    y=visible.index.tolist(),
                    text=labels,
                    texttemplate="%{text}",
                    customdata=counts.to_numpy(),
                    colorscale="RdYlGn",
                    zmid=0,
                    zmin=-max(max_abs, 0.1),
                    zmax=max(max_abs, 0.1),
                    colorbar={"title": "平均<br>リターン%"},
                    hovertemplate="条件=%{y}<br>期間=%{x}<br>平均=%{z:+.2f}%<br>確定件数=%{customdata}<extra></extra>",
                ))
                fig.update_layout(
                    height=max(430, 42 * len(visible.index)),
                    margin={"l": 20, "r": 20, "t": 25, "b": 20},
                    xaxis_title="◎☆判定後の取引日数",
                    yaxis_title="判定時に満たしていた条件",
                )
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.caption("緑は平均プラス、赤は平均マイナスです。各マスの n はその期間まで実績が確定したイベント数です。")

    with security_tab:
        c1, c2 = st.columns(2)
        horizon_labels = [f"{h}日" for h in STAR_OUTCOME_HORIZONS]
        x_label = c1.selectbox(
            "横軸の期間", horizon_labels, index=2, key="history_security_bubble_x",
            help="各銘柄の◎☆イベント後リターンを平均し、横方向へ配置する期間です。",
        )
        y_label = c2.selectbox(
            "縦軸の期間", horizon_labels, index=4, key="history_security_bubble_y",
            help="各銘柄の◎☆イベント後リターンを平均し、縦方向へ配置する期間です。",
        )
        x_days = int(x_label.removesuffix("日"))
        y_days = int(y_label.removesuffix("日"))
        if x_days == y_days:
            st.info("異なる2期間を選ぶと、短期と中長期の動きの違いを比較できます。")
        bubbles = security_return_bubbles(star_events, x_days, y_days)
        if bubbles.empty:
            st.info("選択した2期間がともに確定した銘柄実績がまだありません。")
        else:
            sizes = 12 + np.sqrt(bubbles["◎☆回数"].clip(lower=1)) * 8
            labels = bubbles["code"].astype(str) + " " + bubbles["name"].astype(str)
            fig = go.Figure(go.Scatter(
                x=bubbles["横軸リターン(%)"],
                y=bubbles["縦軸リターン(%)"],
                mode="markers",
                customdata=np.column_stack([
                    labels, bubbles["◎☆回数"], bubbles["比較可能件数"]
                ]),
                marker={
                    "size": sizes,
                    "color": bubbles["縦軸リターン(%)"],
                    "colorscale": "RdYlGn",
                    "cmid": 0,
                    "showscale": True,
                    "colorbar": {"title": f"{y_days}日%"},
                    "line": {"width": 1, "color": "#666"},
                    "opacity": 0.78,
                },
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    f"{x_days}日平均=%{{x:+.2f}}%<br>{y_days}日平均=%{{y:+.2f}}%<br>"
                    "◎☆回数=%{customdata[1]}<br>2期間とも確定=%{customdata[2]}件<extra></extra>"
                ),
            ))
            fig.add_vline(x=0, line_dash="dash", line_color="#777")
            fig.add_hline(y=0, line_dash="dash", line_color="#777")
            fig.update_layout(
                height=560,
                margin={"l": 20, "r": 20, "t": 25, "b": 20},
                xaxis_title=f"銘柄別 {x_days}取引日後の平均リターン（%）",
                yaxis_title=f"銘柄別 {y_days}取引日後の平均リターン（%）",
            )
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.caption("右上は両期間とも平均プラス、左上は短期下落後に中長期で回復、右下は短期上昇後に失速した領域です。円の大きさは◎☆回数です。")


def _render_horizon_performance_bubbles(forward_chart: pd.DataFrame) -> None:
    """Show return, positive rate, and sample size across outcome horizons."""
    if forward_chart is None or forward_chart.empty:
        return
    frame = forward_chart.reset_index().copy()
    required = {"期間", "平均リターン(%)", "プラス率(%)", "確定件数"}
    if not required.issubset(frame.columns):
        return
    frame["平均リターン(%)"] = pd.to_numeric(frame["平均リターン(%)"], errors="coerce")
    frame["プラス率(%)"] = pd.to_numeric(frame["プラス率(%)"], errors="coerce")
    frame["確定件数"] = pd.to_numeric(frame["確定件数"], errors="coerce").fillna(0).astype(int)
    frame["取引日数"] = pd.to_numeric(frame["期間"].astype(str).str.replace("日", "", regex=False), errors="coerce")
    frame = frame.loc[
        frame["平均リターン(%)"].notna()
        & frame["プラス率(%)"].notna()
        & frame["取引日数"].notna()
        & frame["確定件数"].gt(0)
    ].sort_values("取引日数")
    if frame.empty:
        return
    try:
        import numpy as np
        import plotly.graph_objects as go
    except ImportError:
        st.info("期間別の多軸グラフ表示にはPlotlyが必要です。")
        return
    sizes = 14 + np.sqrt(frame["確定件数"].clip(lower=1)) * 8
    fig = go.Figure(go.Scatter(
        x=frame["取引日数"],
        y=frame["平均リターン(%)"],
        mode="lines+markers+text",
        text=frame["期間"],
        textposition="top center",
        customdata=np.column_stack([frame["プラス率(%)"], frame["確定件数"]]),
        line={"width": 2, "color": "#7386d5"},
        marker={
            "size": sizes,
            "color": frame["プラス率(%)"],
            "colorscale": "RdYlGn",
            "cmin": 0,
            "cmax": 100,
            "showscale": True,
            "colorbar": {"title": "プラス率%"},
            "line": {"width": 1, "color": "#555"},
            "opacity": 0.85,
        },
        hovertemplate=(
            "%{x:.0f}取引日後<br>平均リターン=%{y:+.2f}%<br>"
            "プラス率=%{customdata[0]:.1f}%<br>確定件数=%{customdata[1]}<extra></extra>"
        ),
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#777")
    fig.update_layout(
        height=510,
        margin={"l": 20, "r": 20, "t": 25, "b": 20},
        xaxis_title="◎☆判定後の取引日数",
        yaxis_title="平均リターン（%）",
        xaxis={"tickmode": "array", "tickvals": frame["取引日数"], "ticktext": frame["期間"]},
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def _render_condition_performance_bubbles(perf: pd.DataFrame, horizon_days: int) -> None:
    """Show return, positive rate, and confirmed count for one condition horizon."""
    bubbles = condition_outcome_bubbles(perf, horizon_days)
    if bubbles.empty:
        st.info("選択した期間の条件別確定実績がまだありません。")
        return
    try:
        import numpy as np
        import plotly.graph_objects as go
    except ImportError:
        st.info("条件別の多軸グラフ表示にはPlotlyが必要です。")
        return
    sizes = 14 + np.sqrt(bubbles["確定件数"].clip(lower=1)) * 8
    fig = go.Figure(go.Scatter(
        x=bubbles["平均リターン(%)"],
        y=bubbles["プラス率(%)"],
        mode="markers+text",
        text=bubbles["条件"],
        textposition="top center",
        customdata=np.column_stack([bubbles["条件"], bubbles["確定件数"]]),
        marker={
            "size": sizes,
            "color": bubbles["平均リターン(%)"],
            "colorscale": "RdYlGn",
            "cmid": 0,
            "showscale": True,
            "colorbar": {"title": "平均%"},
            "line": {"width": 1, "color": "#555"},
            "opacity": 0.84,
        },
        hovertemplate=(
            "条件=%{customdata[0]}<br>平均リターン=%{x:+.2f}%<br>"
            "プラス率=%{y:.1f}%<br>確定件数=%{customdata[1]}<extra></extra>"
        ),
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#777")
    fig.add_hline(y=50, line_dash="dash", line_color="#777")
    fig.update_layout(
        height=550,
        margin={"l": 20, "r": 20, "t": 25, "b": 20},
        xaxis_title=f"{horizon_days}取引日後の平均リターン（%）",
        yaxis_title="プラスになった割合（%）",
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


@st.cache_resource(show_spinner=False, max_entries=2)
def _load_bundle(manifest_mtime_ns: int) -> dict:
    # The curated market bundle can contain millions of price rows. cache_resource
    # shares the same read-only object across Streamlit reruns/sessions instead of
    # serializing and copying the full DataFrames on every page navigation.
    del manifest_mtime_ns
    data = load_curated_latest(ROOT)
    as_of = pd.Timestamp(data["prices"]["date"].max())
    prepared = load_feature_snapshot(ROOT / "data" / "curated" / "latest")
    required_feature_columns = {
        "volatility_60d", "average_intraday_range_20d", "average_absolute_return_20d",
        "cash_conversion_ratio", "operating_margin_change_3y",
        "forecast_revision_rate", "sector_relative_return_6m",
    }
    if prepared is None or not required_feature_columns.issubset(prepared.columns):
        # Rebuild from already-curated local files only. A UI/strategy change must never
        # trigger a J-Quants fetch. The next run_real will persist the new snapshot schema.
        prepared = prepare_quantitative_universe(
            data["companies"], data["prices"], data["financials"], as_of
        )
    return {"data": data, "as_of": as_of, "prepared": prepared}


def _bundle_or_none() -> dict | None:
    manifest = ROOT / "data" / "curated" / "latest" / "manifest.json"
    if not manifest.exists():
        return None
    try:
        return _load_bundle(manifest.stat().st_mtime_ns)
    except RealDataNotReadyError:
        return None


def _open_stock_detail(code: str) -> None:
    """Navigate in the current tab and preselect the requested code."""
    normalized = display_tse_code(str(code))
    st.session_state["stock_query"] = normalized
    st.session_state["stock_selected_code"] = str(code)
    st.switch_page(STOCK_DETAIL_PAGE)


def _stock_detail_new_tab_url(code: str) -> str:
    """Build an absolute stock-detail URL for a separate browser tab."""
    current = urlsplit(str(st.context.url))
    current_path = current.path.rstrip("/")
    app_root = current_path.rsplit("/", 1)[0] if "/" in current_path else ""
    stock_path = f"{app_root}/{STOCK_DETAIL_URL_PATH}" if app_root else f"/{STOCK_DETAIL_URL_PATH}"
    query = urlencode({"code": str(code).strip()})
    return urlunsplit((current.scheme, current.netloc, stock_path, query, ""))


def _sorted_clickable_table_frame(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    """Sort a custom clickable table using state set by its header buttons."""
    if frame.empty:
        return frame.reset_index(drop=True)
    sort_column = st.session_state.get(f"{key}_sort_column")
    if not sort_column or sort_column not in frame.columns:
        return frame.reset_index(drop=True)
    ascending = bool(st.session_state.get(f"{key}_sort_ascending", True))
    series = frame[sort_column]
    non_null = series.notna()
    numeric = pd.to_numeric(series, errors="coerce")
    if bool(non_null.any()) and bool(numeric.loc[non_null].notna().all()):
        sort_key = lambda values: pd.to_numeric(values, errors="coerce")
    else:
        sort_key = lambda values: values.astype("string").str.casefold()
    return frame.sort_values(
        sort_column,
        ascending=ascending,
        na_position="last",
        kind="mergesort",
        key=sort_key,
    ).reset_index(drop=True)


def _toggle_sort_state(key: str, field: str) -> None:
    """Update sort state before Streamlit reruns the table fragment."""
    column_state = f"{key}_sort_column"
    ascending_state = f"{key}_sort_ascending"
    if st.session_state.get(column_state) == field:
        st.session_state[ascending_state] = not bool(st.session_state.get(ascending_state, True))
    else:
        st.session_state[column_state] = field
        st.session_state[ascending_state] = True


def _sortable_header_button(container, label: str, field: str, key: str) -> None:
    """Render a table header that toggles ascending/descending sort."""
    active_field = st.session_state.get(f"{key}_sort_column")
    active_ascending = bool(st.session_state.get(f"{key}_sort_ascending", True))
    if active_field == field:
        marker = " ▲" if active_ascending else " ▼"
    else:
        marker = " ↕"
    container.button(
        f"{label}{marker}",
        key=f"{key}_sort_header_{field}",
        width="stretch",
        help=f"{_analysis_help(field, _analysis_help(label))} クリックで昇順／降順を切り替えます。",
        on_click=_toggle_sort_state,
        args=(key, field),
    )


def _render_history_stock_buttons(
    frame: pd.DataFrame,
    key: str,
    *,
    caption: bool = True,
) -> None:
    """Render paged history rows with stock details opened in a new browser tab.

    The history screens intentionally render only the current page as links.
    Opening stock detail in a separate Streamlit session keeps the filtered/sorted
    history tab intact while the user inspects and closes individual stock tabs.
    """
    if frame.empty or "code" not in frame.columns:
        _analysis_dataframe(frame, width="stretch", hide_index=True)
        return

    if caption:
        st.caption("銘柄コードまたは企業名をクリックすると、個別銘柄検索を新しいタブで開きます。元の履歴一覧はそのまま残ります。列名をクリックすると昇順／降順を切り替えられます。")

    display_frame = frame.reset_index(drop=True)
    preferred = {
        "daily_history": ["analysis_date", "final_evaluation", "evaluation_status", "strategy_score", "close"],
        "evaluation_history": ["evaluation_date", "intuitive_symbol", "evaluation_status", "selection_strategy", "latest_close"],
        "star_summary": ["first_star_date", "latest_star_date", "star_count", "latest_entry_price", "return_10d_avg"],
        "star_events_detail": ["star_date", "entry_price", "return_10d", "return_20d", "return_30d"],
    }
    meta_cols = [c for c in preferred.get(key, []) if c in display_frame.columns][:5]
    header = st.columns([1.1, 2.5] + [1.15] * len(meta_cols))
    _sortable_header_button(header[0], "コード", "code", key)
    _sortable_header_button(header[1], "企業名", "name", key)
    for col, name in zip(header[2:], meta_cols):
        _sortable_header_button(col, name, name, key)

    for idx, row in display_frame.iterrows():
        code = str(row.get("code", ""))
        if not code or code.lower() == "nan":
            continue
        display_code = display_tse_code(code)
        name = str(row.get("name", ""))
        cols = st.columns([1.1, 2.5] + [1.15] * len(meta_cols))
        stock_url = _stock_detail_new_tab_url(code)
        cols[0].link_button(display_code, stock_url, width="stretch", help="個別銘柄検索を新しいブラウザタブで開きます。")
        cols[1].link_button(name or display_code, stock_url, width="stretch", help="個別銘柄検索を新しいブラウザタブで開きます。")
        for col, field in zip(cols[2:], meta_cols):
            value = row.get(field)
            if pd.isna(value):
                col.write("-")
            elif field.startswith("return_"):
                col.write(f"{float(value):.1f}%")
            elif field in {"strategy_score", "latest_close", "latest_entry_price", "entry_price", "close"}:
                col.write(_format_number(value, 1 if field == "strategy_score" else 0))
            else:
                col.write(str(value))

    with st.expander("現在ページの全列を表形式で確認", expanded=False):
        _analysis_dataframe(display_frame, width="stretch", hide_index=True)


@st.fragment
def _render_history_sortable_stock_table(
    frame: pd.DataFrame,
    key: str,
    *,
    default_size: int = 50,
    compact_sizes: bool = True,
) -> None:
    """Sort, paginate, and redraw only the history table fragment."""
    sorted_frame = _sorted_clickable_table_frame(frame, key)
    page = _history_page_slice(
        sorted_frame,
        key,
        default_size=default_size,
        compact_sizes=compact_sizes,
    )
    _render_history_stock_buttons(page, key)


@st.fragment
def _render_clickable_candidates(shortlist: pd.DataFrame) -> None:
    """Render candidate code and company name as new-tab stock-detail links."""
    st.caption("銘柄コードまたは企業名をクリックすると、個別銘柄検索を新しいタブで開きます。元の候補一覧はそのまま残ります。列名をクリックすると昇順／降順を切り替えられます。")
    score_field = "strategy_score" if "strategy_score" in shortlist.columns else "quantitative_score"
    display_shortlist = _sorted_clickable_table_frame(shortlist, "clickable_candidates")
    header = st.columns([1, 3, 1, 1, 1])
    for col, (label, field) in zip(
        header,
        [("コード", "code"), ("企業名", "name"), ("市場", "market"), ("終値", "close"), ("スコア", score_field)],
    ):
        _sortable_header_button(col, label, field, "clickable_candidates")
    for _, row in display_shortlist.iterrows():
        code = str(row.get("code", ""))
        display_code = display_tse_code(code)
        name = str(row.get("name", ""))
        cols = st.columns([1, 3, 1, 1, 1])
        stock_url = _stock_detail_new_tab_url(code)
        cols[0].link_button(
            display_code,
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[1].link_button(
            name or display_code,
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[2].write(str(row.get("market", "-")))
        cols[3].write(f"¥{_format_number(row.get('close'))}")
        cols[4].write(_format_number(row.get("strategy_score", row.get("quantitative_score")), 1))

@st.fragment
def _render_unified_candidate_table(result: pd.DataFrame, *, active_mode: bool) -> None:
    """Render the sortable unified-candidate table without rerunning Yahoo analysis."""
    display_result = _sorted_clickable_table_frame(result, "unified_candidates")
    header = st.columns([1.15, 1.0, 2.4, 0.8, 1.0, 1.0, 1.6, 1.6, 1.35])
    unified_headers = [
        ("評価", "直感判定"), ("コード", "コード"), ("企業名", "企業名"),
        ("スコア", "定量スコア"), ("分析終値", "分析終値"), ("最新株価", "最新株価"),
        ("最新判定", "最新判定"), ("変化", "変化"), ("仮説警告", "仮説警告"),
    ]
    for col, (label, field) in zip(header, unified_headers):
        _sortable_header_button(col, label, field, "unified_candidates")
    for _, item in display_result.iterrows():
        cols = st.columns([1.15, 1.0, 2.4, 0.8, 1.0, 1.0, 1.6, 1.6, 1.35])
        cols[0].write(str(item["直感判定"]))
        raw_code = str(item["raw_code"])
        stock_url = _stock_detail_new_tab_url(raw_code)
        cols[1].link_button(
            str(item["コード"]),
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[2].link_button(
            str(item["企業名"]) or str(item["コード"]),
            stock_url,
            width="stretch",
            help="個別銘柄検索を新しいブラウザタブで開きます。",
        )
        cols[3].write(_format_number(item.get("定量スコア"), 1))
        cols[4].write(f"¥{_format_number(item.get('分析終値'))}")
        cols[5].write("-" if pd.isna(item.get("最新株価")) else f"¥{_format_number(item.get('最新株価'), 1)}")
        cols[6].write(str(item["最新判定"]))
        cols[7].write(str(item["変化"]))
        cols[8].write(str(item["仮説警告"]))
        with st.expander(f"詳細: {item['コード']} {item['企業名']}", expanded=False):
            detail_cols = st.columns(4)
            detail_cols[0].metric("約3カ月前", str(item["約3カ月前"]))
            detail_cols[1].metric("下降脱出", str(item["下降脱出"]))
            if active_mode:
                detail_cols[2].metric("最新60日ボラ", "-" if pd.isna(item.get("最新60日ボラ")) else f"{float(item['最新60日ボラ']):.1f}%")
                detail_cols[3].metric("最新20日値幅", "-" if pd.isna(item.get("最新20日値幅")) else f"{float(item['最新20日値幅']):.1f}%")
            st.caption(str(item["判断メモ"]))
    st.caption("Yahoo Finance系の最新情報は候補抽出スコア自体には混入しません。SBI証券の現在値・板・最新開示で最終確認してください。")

def _render_latest_candidate_trends(score_passed: pd.DataFrame, *, star_only: bool = False, analysis_as_of=None) -> pd.DataFrame:
    """Render one unified candidate list with quantitative and latest-trend data.

    The score-passed frame is the single source of truth for row membership. Yahoo
    failures remain as explicit ``判定不能`` rows, so there is no second list whose
    membership can drift from the quantitative candidate list.
    """
    if score_passed.empty:
        return pd.DataFrame()
    active_mode = str(score_passed.iloc[0].get("selection_strategy", "value_dislocation")) == "active_trading"
    st.markdown("### 統合候補一覧（抽出条件 + 最新トレンド）")
    st.caption(
        "抽出条件を通過した全銘柄を母集団に、同じ行へYahoo Finance系の最新日足による再判定を統合しています。"
        "外部データ取得に失敗しても銘柄は消さず『判定不能』として残します。銘柄コードまたは企業名をクリックすると個別銘柄検索を新しいタブで開きます。元の候補一覧はそのまま残ります。"
    )
    if active_mode:
        st.info("⚡は取得済みスナップショットで値動きが活発だった候補です。最新Yahoo系日足で現在の値動きも同じ一覧内で再確認します。")
    else:
        st.info("直感判定: ◎☆ 買い候補（主要欠点なし） / ◎ 買い候補 / ○ 条件付き候補 / △ 様子見 / × 見送り。☆は主要な財務・業績・トレンド項目に明確な欠点が見当たらない場合です。")

    rows: list[dict] = []
    total = len(score_passed)
    target_label = "値動き条件通過" if active_mode else "スコア通過"
    bulk_yahoo_allowed = yahoo_bulk_fetch_allowed(total)
    if not bulk_yahoo_allowed:
        st.warning(
            f"Yahoo Finance系の最新株価取得対象が {total:,} 銘柄あります。"
            f"{YAHOO_BULK_FETCH_BLOCK_THRESHOLD}銘柄以上の場合は外部取得を実施しません。"
            "条件を絞って99銘柄以下にしてから最新トレンドを再判定してください。"
        )

    spinner_text = (
        f"最新株価系列で{target_label} {total} 銘柄すべてを統合しています…"
        if bulk_yahoo_allowed
        else f"{target_label} {total} 銘柄を外部取得なしで表示しています…"
    )
    with st.spinner(spinner_text):
        for _, row in score_passed.iterrows():
            code = str(row.get("code", ""))
            latest_price = None
            latest_market_date = None
            latest_volatility = None
            latest_range = None
            previous_state = "取得不能"
            current_state = "取得不能"
            transition_state = "判定不能"
            escaped = "未確認"
            intuitive_label = "△ 判定保留"
            detail = ""
            evaluation_status = "未評価"
            unassessed_reason = "その他"
            try:
                if not bulk_yahoo_allowed:
                    previous_state = "未実施（100件以上）"
                    current_state = "未実施（100件以上）"
                    transition_state = "未実施（100件以上）"
                    escaped = "未実施"
                    intuitive_label = (
                        f"⚡ 活発度 {float(row.get('daytrade_activity_score', 0)):.0f}点"
                        if active_mode
                        else "△ 最新判定未実施"
                    )
                    detail = "Yahoo Finance系の一括取得対象が100銘柄以上のため、最新株価・最新トレンド判定を実施していません。"
                    evaluation_status = "未評価"
                    unassessed_reason = "Yahoo100件制限で未実施"
                    raise StopIteration
                history = _latest_external_history(code)
                transition = build_trend_transition(history, lookback_days=90)
                current = transition["current"]
                candidate_metrics = row.to_dict()
                candidate_readiness = build_buy_readiness(
                    candidate_metrics,
                    external_quote_available=True,
                    benchmark_available=str(row.get("benchmark_source", "none")) in {"official_topix", "topix_etf_proxy"},
                    trend=current,
                )
                intuitive = build_intuitive_signal(candidate_readiness, transition)
                latest_returns = pd.to_numeric(history.get("close"), errors="coerce").pct_change().dropna().tail(60)
                latest_volatility = float(latest_returns.std() * (252 ** 0.5)) if len(latest_returns) >= 20 else None
                if {"high", "low", "close"}.issubset(history.columns):
                    recent20 = history.tail(20)
                    denom = pd.to_numeric(recent20["close"], errors="coerce").where(lambda x: x > 0)
                    latest_range = float(((pd.to_numeric(recent20["high"], errors="coerce") - pd.to_numeric(recent20["low"], errors="coerce")) / denom).mean())
                latest_price = current.get("latest_price")
                if not history.empty and "date" in history.columns:
                    latest_market_date = pd.to_datetime(history["date"], errors="coerce").max()
                    latest_market_date = latest_market_date.date().isoformat() if pd.notna(latest_market_date) else None
                previous_state = transition.get("previous_state")
                current_state = transition.get("current_state")
                transition_state = transition.get("transition_state")
                escaped = "可能性あり" if transition.get("escaped_downtrend") else "未確認"
                intuitive_label = (f"⚡ 活発度 {float(row.get('daytrade_activity_score', 0)):.0f}点" if active_mode else f"{intuitive['symbol']} {intuitive['label']}")
                detail = (("最新Yahoo系日足でも値動きの大きさを確認してください。 " if active_mode else intuitive["detail"] + " ") + str(transition.get("summary", "")))
                evaluation_status = "当日評価済み"
                unassessed_reason = ""
            except StopIteration:
                pass
            except Exception as exc:
                detail = f"外部株価履歴を取得できませんでした: {exc}"
                evaluation_status = "未評価"
                unassessed_reason = "Yahoo取得失敗"

            try:
                candidate_review = load_external_event_review(
                    EXTERNAL_REVIEW_DIR, display_tse_code(code), str(row.get("name", ""))
                )
                candidate_invalidation = evaluate_hypothesis_invalidation(candidate_review, row.to_dict())
                if candidate_invalidation["status"] == "breached":
                    invalidation_label = f"🚨 抵触 {len(candidate_invalidation['breached'])}件"
                elif candidate_invalidation["status"] == "unevaluable":
                    invalidation_label = "⚠️ 評価不能あり"
                elif candidate_invalidation["status"] == "manual_review":
                    invalidation_label = "👁 要目視確認"
                elif candidate_invalidation["status"] == "clear":
                    invalidation_label = "✅ 抵触なし"
                else:
                    invalidation_label = "未設定"
            except Exception:
                invalidation_label = "⚠️ レビュー読込エラー"

            rows.append({
                "直感判定": intuitive_label,
                "仮説警告": invalidation_label,
                "コード": display_tse_code(code),
                "raw_code": code,
                "企業名": str(row.get("name", "")),
                "市場": str(row.get("market", "-")),
                "分析終値": row.get("close"),
                "定量スコア": row.get("strategy_score", row.get("quantitative_score")),
                "最新株価": latest_price,
                "latest_market_date": latest_market_date,
                "selection_strategy": str(row.get("selection_strategy", "value_dislocation")),
                "最新60日ボラ": (latest_volatility * 100 if active_mode and latest_volatility is not None else None),
                "最新20日値幅": (latest_range * 100 if active_mode and latest_range is not None else None),
                "約3カ月前": previous_state,
                "最新判定": current_state,
                "変化": transition_state,
                "下降脱出": escaped,
                "判断メモ": detail,
                "evaluation_status": evaluation_status,
                "unassessed_reason": unassessed_reason,
                "original_final_evaluation": "" if evaluation_status == "当日評価済み" else "未評価",
                "original_unassessed_reason": "" if evaluation_status == "当日評価済み" else unassessed_reason,
                "evaluation_as_of": str(analysis_as_of or ""),
            })

    all_result = pd.DataFrame(rows)
    # Integrity is checked against the unfiltered unified result.  The optional
    # star-only view is a presentation filter after the latest Yahoo trend check.
    if len(all_result) != total:
        st.error(
            f"内部件数不整合を検出しました。{target_label} {total:,} 件に対し、"
            f"統合一覧は {len(all_result):,} 件です。"
        )

    # Save the unfiltered unified evaluation once per date/code.  This is local history
    # only; it performs no additional Yahoo or J-Quants request.
    try:
        today = pd.Timestamp.now(tz="Asia/Tokyo").date()
        upsert_daily_evaluations(ROOT, all_result, evaluation_date=today, analysis_as_of=analysis_as_of)
        write_star_outcomes(ROOT)
    except Exception as exc:
        st.warning(f"履歴の保存に失敗しました（画面表示は継続します）: {exc}")

    skipped_count = int(all_result["最新判定"].astype(str).str.startswith("未実施").sum()) if not all_result.empty else 0
    failed_count = int((all_result["最新判定"] == "取得不能").sum()) if not all_result.empty else 0
    success_count = len(all_result) - failed_count - skipped_count

    star_mask = all_result["直感判定"].astype(str).str.startswith("◎☆") if not all_result.empty else pd.Series(dtype=bool)
    star_count = int(star_mask.sum()) if not all_result.empty else 0
    if star_only and not active_mode:
        if not bulk_yahoo_allowed:
            st.warning(
                "☆だけの銘柄を表示するには最新Yahoo Finance系トレンド判定が必要です。"
                "対象を99銘柄以下へ絞ってから再度実行してください。"
            )
            result = all_result.iloc[0:0].copy()
        else:
            result = all_result.loc[star_mask].reset_index(drop=True)
            st.info(f"☆限定表示: {star_count:,} 銘柄 / 統合候補 {total:,} 銘柄")
    else:
        result = all_result

    count_cols = st.columns(5 if (star_only and not active_mode) else 4)
    count_cols[0].metric(target_label, f"{total:,}", help="定量スコアを通過し、最新トレンド再確認の対象になった銘柄数です。")
    count_cols[1].metric("統合一覧", f"{len(all_result):,}", help="取得成功・失敗・未実施を含め、一覧に残した全対象銘柄数です。")
    count_cols[2].metric("外部株価取得成功", f"{success_count:,}", help="Yahoo Finance系の最新日足を取得してトレンドを再確認できた銘柄数です。")
    if skipped_count:
        count_cols[3].metric("100件以上のため未実施", f"{skipped_count:,}", help="一括外部取得の安全上限を超えたため、最新トレンド再確認を行わなかった銘柄数です。")
    else:
        count_cols[3].metric("取得失敗・判定不能", f"{failed_count:,}", help="外部日足を取得できず、最新トレンドを判定できなかった銘柄数です。")
    if star_only and not active_mode:
        count_cols[4].metric("☆該当", f"{star_count:,}", help="主要な定量条件に加えて短期反転条件も確認できた◎☆銘柄数です。利益保証ではありません。")

    if result.empty and star_only and not active_mode:
        st.info("現在の最新トレンド判定では、☆条件に該当する銘柄はありません。")
        return result

    _render_unified_candidate_table(result, active_mode=active_mode)
    return result

def _candidate_card(row: pd.Series) -> None:
    code = display_tse_code(str(row.get("code", "")))
    name = str(row.get("name", ""))
    strategy = str(row.get("selection_strategy", "value_dislocation"))
    if strategy == "active_trading":
        score = _format_number(row.get("daytrade_activity_score"), 1)
        with st.expander(f"{code} {name}　値動き活発度 {score}"):
            cols = st.columns(5)
            cols[0].metric("終値", f"¥{_format_number(row.get('close'))}")
            cols[1].metric("60日ボラ", _format_pct(row.get("volatility_60d")))
            cols[2].metric("20日平均日中値幅", _format_pct(row.get("average_intraday_range_20d")))
            cols[3].metric("20日平均絶対騰落", _format_pct(row.get("average_absolute_return_20d")))
            turnover_m = float(row.get("average_turnover_yen_20d", 0) or 0) / 1_000_000
            cols[4].metric("20日平均売買代金", f"{turnover_m:,.0f}百万円")
            st.caption(
                "値動き活発度は取得済みJ-Quantsスナップショット内の相対順位です。"
                "デイトレードの利益可能性を示すものではなく、値動きが大きい銘柄ほど損失も急拡大し得ます。"
            )
            st.write(f"注意: {row.get('warning_reasons', '')}")
        return

    score = _format_number(row.get("quantitative_score"), 1)
    with st.expander(f"{code} {name}　定量スコア {score}"):
        cols = st.columns(9)
        cols[0].metric("終値", f"¥{_format_number(row.get('close'))}")
        cols[1].metric("52週高値比", _format_pct(row.get("drawdown_52w")))
        cols[2].metric("6か月騰落率", _format_pct(row.get("return_6m")))
        cols[3].metric("市場比較相対", _format_pct(row.get("relative_return_6m")))
        cols[4].metric("売上CAGR", _format_pct(row.get("sales_cagr_3y")))
        cols[5].metric("営業利益率", _format_pct(row.get("operating_margin")))
        cols[6].metric("自己資本比率", _format_pct(row.get("equity_ratio")))
        cols[7].metric("予想営業利益", _format_pct(row.get("forecast_op_growth")))
        cols[8].metric("予想配当利回り", _format_pct(row.get("forecast_dividend_yield")))
        quality_cols = st.columns(5)
        quality_cols[0].metric("利益現金化率", _format_pct(row.get("cash_conversion_ratio")))
        quality_cols[1].metric("営業利益率変化", _format_pct(row.get("operating_margin_change_3y")))
        quality_cols[2].metric("会社予想修正", _format_pct(row.get("forecast_revision_rate")))
        quality_cols[3].metric("同業中央値対比", _format_pct(row.get("sector_relative_return_6m")))
        quality_cols[4].metric("外因説明率", _format_pct(row.get("external_shock_attribution")))
        st.write(f"通過理由: {row.get('pass_reasons', '')}")
        st.write(f"注意: {row.get('warning_reasons', '')}")


def render_data_status_and_update() -> None:
    status = _read_json(REAL_OUTPUT / "run_status_latest.json")
    manifest = _read_json(ROOT / "data" / "curated" / "latest" / "manifest.json")
    st.subheader("実データの状態")
    if status:
        cols = st.columns(6)
        cols[0].metric("株価基準日", str(status.get("as_of", "-"))[:10])
        cols[1].metric("データ経過日数", f"{status.get('data_age_days', '-')}日")
        cols[2].metric("上場銘柄", f"{status.get('company_rows', 0):,}")
        cols[3].metric("株価行数", f"{status.get('price_rows', 0):,}")
        cols[4].metric("既定条件の候補", f"{status.get('shortlist_rows', 0):,}")
        cols[5].metric("契約データ上限日", str(status.get("subscription_coverage_end") or "-")[:10])
        st.caption(
            f"Provider: {status.get('provider', '-')} / Run ID: {status.get('run_id', '-')} / "
            f"actual_data={status.get('actual_data', False)}"
        )
        if not status.get("data_fresh_enough_for_order_preview", False):
            st.warning(
                "J-Quantsの分析スナップショットは注文直前判断の鮮度上限を超えています。"
                "検索・定量評価にはこのpoint-in-timeデータを使い、個別銘柄の注文直前プレビューでは"
                "Yahoo Finance系の最新日足を別途取得して市場鮮度を判定します。"
            )
        benchmark_source = status.get("benchmark_source", "none")
        benchmark_label = status.get("benchmark_label", "市場比較なし")
        if benchmark_source == "official_topix":
            st.success(f"市場比較データ: {benchmark_label}")
        elif benchmark_source == "topix_etf_proxy":
            st.warning(f"市場比較データ: {benchmark_label}（TOPIX連動ETFの代理値。正式TOPIXではありません）")
        else:
            st.warning("正式TOPIXとTOPIX連動ETF代理値を利用できないため、市場比較条件を適用できません。")
        for warning in status.get("warnings", []) or []:
            st.warning(str(warning))
    else:
        st.info("実データはまだ取得されていません。下の欄から初回取得してください。")

    with st.expander("J-Quantsから実データを取得・更新", expanded=not bool(status)):
        st.write(
            "J-Quants API V2のAPIキーを入力すると、このStreamlitプロセス内だけで使用します。"
            "画面入力したキーはファイルへ保存しません。`.env` に設定済みなら入力不要です。"
        )
        st.info(
            "初回同期には時間がかかります。HTTP 429時は自動待機し、取得済み日から再開します。"
            "実行中に更新ボタンを繰り返し押さないでください。"
        )
        api_key = st.text_input("J-Quants API key", type="password", key="jquants_api_key")
        end_date = st.date_input("取得終了日", value=pd.Timestamp.now(tz="Asia/Tokyo").date())
        if st.button("実データを更新", type="primary"):
            if api_key.strip():
                os.environ["JQUANTS_API_KEY"] = api_key.strip()
            with st.spinner("J-Quantsから株価・決算・TOPIX・決算予定を取得しています…"):
                try:
                    result = run_real_pipeline(REAL_CONFIG, end=end_date.isoformat())
                except Exception as exc:
                    st.error(f"取得に失敗しました: {type(exc).__name__}: {exc}")
                else:
                    _load_bundle.clear()
                    effective_end = result.get("effective_price_end")
                    requested_end = result.get("requested_price_end")
                    if effective_end and requested_end and effective_end != requested_end:
                        st.warning(f"契約プランに合わせ、取得終了日を {effective_end} に調整しました。")
                    st.success(f"更新しました。Run ID: {result['run_id']}")
                    st.rerun()

    with st.expander("取得元・スナップショット情報"):
        st.json(manifest if manifest else {"message": "マニフェストはありません"})


def _apply_values(overrides: dict) -> None:
    u = overrides["universe"]
    s = overrides["screen"]
    st.session_state["ui_markets"] = list(u["allowed_markets"])
    st.session_state["ui_turnover_million"] = int(round(u["min_average_turnover_yen_20d"] / 1_000_000))
    st.session_state["ui_min_price"] = int(u["min_price_yen"])
    st.session_state["ui_equity_pct"] = int(round(s["minimum_equity_ratio"] * 100))
    st.session_state["ui_ocf_years"] = int(round(s["minimum_operating_cf_positive_ratio_3y"] * 3))
    st.session_state["ui_sales_cagr_pct"] = int(round(s["minimum_sales_cagr_3y"] * 100))
    st.session_state["ui_op_margin_pct"] = int(round(s["minimum_operating_margin"] * 100))
    st.session_state["ui_use_structural_guard"] = bool(s.get("use_structural_deterioration_guard", True))
    st.session_state["ui_min_cash_conversion_pct"] = float(s.get("minimum_cash_conversion_ratio", 0.70)) * 100
    st.session_state["ui_max_margin_deterioration_pt"] = -float(s.get("minimum_operating_margin_change_3y", -0.03)) * 100
    st.session_state["ui_max_forecast_revision_decline_pct"] = -float(s.get("minimum_forecast_revision_rate", -0.10)) * 100
    st.session_state["ui_max_sector_underperformance_pct"] = -float(s.get("minimum_sector_relative_return_6m", -0.15)) * 100
    st.session_state["ui_forecast_decline_pct"] = int(round(-s["maximum_forecast_op_decline"] * 100))
    st.session_state["ui_drawdown_pct"] = int(round(-s["minimum_drawdown_52w"] * 100))
    st.session_state["ui_use_relative"] = bool(s.get("use_relative_underperformance_filter", True))
    st.session_state["ui_benchmark_mode"] = str(s.get("market_benchmark_mode", "auto"))
    st.session_state["ui_relative_pct"] = int(round(-s["minimum_relative_underperformance_6m"] * 100))
    st.session_state["ui_require_forecast"] = bool(s.get("require_forecast", False))
    st.session_state["ui_require_sales_history"] = bool(s.get("require_sales_history", False))
    st.session_state["ui_min_score"] = int(round(s["quantitative_min_score"]))
    st.session_state["ui_max_queue"] = int(s["max_review_queue"])
    st.session_state["ui_require_dividend"] = bool(s.get("require_dividend", False))
    st.session_state["ui_min_dividend_yield_pct"] = float(s.get("minimum_forecast_dividend_yield", 0.0)) * 100
    st.session_state["ui_max_dividend_yield_pct"] = float(s.get("maximum_forecast_dividend_yield", 0.10)) * 100
    st.session_state["ui_min_dividend_per_share"] = float(s.get("minimum_annual_dividend_per_share", 0.0))
    st.session_state["ui_max_payout_pct"] = float(s.get("maximum_payout_ratio", 0.80)) * 100
    st.session_state["ui_exclude_dividend_cut"] = bool(s.get("exclude_forecast_dividend_cut", False))
    if "selection_strategy" in s:
        st.session_state["ui_selection_strategy"] = str(s["selection_strategy"])
        st.session_state["ui_rule_choice_draft"] = st.session_state["ui_selection_strategy"]
    st.session_state["ui_min_volatility_pct"] = float(s.get("minimum_volatility_60d", 0.35)) * 100
    st.session_state["ui_min_intraday_range_pct"] = float(s.get("minimum_average_intraday_range_20d", 0.025)) * 100
    st.session_state["ui_min_daytrade_score"] = int(round(float(s.get("minimum_daytrade_activity_score", 50))))


def _on_preset_change() -> None:
    selected = st.session_state.get("condition_preset", "標準")
    if selected in PRESETS:
        _apply_values(preset_overrides(selected))


def _on_load_profile() -> None:
    selected = st.session_state.get("saved_profile_path")
    if not selected:
        return
    document = load_profile(Path(selected))
    _apply_values(document["overrides"])
    st.session_state["condition_preset"] = "カスタム"
    st.session_state["profile_notice"] = f"{document.get('profile_name', '設定')}を読み込みました。"


def _initialize_condition_state() -> None:
    if "ui_markets" not in st.session_state:
        _apply_values(preset_overrides("標準"))
    st.session_state.setdefault("condition_preset", "標準")
    st.session_state.setdefault("ui_selection_strategy", "value_dislocation")
    st.session_state.setdefault("ui_rule_choice_draft", st.session_state["ui_selection_strategy"])
    st.session_state.setdefault("ui_min_volatility_pct", 35.0)
    st.session_state.setdefault("ui_min_intraday_range_pct", 2.5)
    st.session_state.setdefault("ui_min_daytrade_score", 50)
    st.session_state.setdefault("ui_star_only", False)
    st.session_state.setdefault("ui_use_structural_guard", True)
    st.session_state.setdefault("ui_min_cash_conversion_pct", 70.0)
    st.session_state.setdefault("ui_max_margin_deterioration_pt", 3.0)
    st.session_state.setdefault("ui_max_forecast_revision_decline_pct", 10.0)
    st.session_state.setdefault("ui_max_sector_underperformance_pct", 15.0)


def _current_overrides() -> dict:
    return {
        "universe": {
            "allowed_markets": list(st.session_state["ui_markets"]),
            "min_average_turnover_yen_20d": int(st.session_state["ui_turnover_million"]) * 1_000_000,
            "min_price_yen": int(st.session_state["ui_min_price"]),
        },
        "screen": {
            "minimum_equity_ratio": float(st.session_state["ui_equity_pct"]) / 100,
            "minimum_operating_cf_positive_ratio_3y": float(st.session_state["ui_ocf_years"]) / 3,
            "minimum_sales_cagr_3y": float(st.session_state["ui_sales_cagr_pct"]) / 100,
            "minimum_operating_margin": float(st.session_state["ui_op_margin_pct"]) / 100,
            "use_structural_deterioration_guard": bool(st.session_state["ui_use_structural_guard"]),
            "minimum_cash_conversion_ratio": float(st.session_state["ui_min_cash_conversion_pct"]) / 100,
            "minimum_operating_margin_change_3y": -float(st.session_state["ui_max_margin_deterioration_pt"]) / 100,
            "minimum_forecast_revision_rate": -float(st.session_state["ui_max_forecast_revision_decline_pct"]) / 100,
            "minimum_sector_relative_return_6m": -float(st.session_state["ui_max_sector_underperformance_pct"]) / 100,
            "maximum_forecast_op_decline": -float(st.session_state["ui_forecast_decline_pct"]) / 100,
            "minimum_drawdown_52w": -float(st.session_state["ui_drawdown_pct"]) / 100,
            "minimum_relative_underperformance_6m": -float(st.session_state["ui_relative_pct"]) / 100,
            "use_relative_underperformance_filter": bool(st.session_state["ui_use_relative"]),
            "market_benchmark_mode": str(st.session_state.get("ui_benchmark_mode", "auto")),
            "relative_filter_when_topix_missing": "skip_with_warning",
            "require_forecast": bool(st.session_state["ui_require_forecast"]),
            "require_sales_history": bool(st.session_state["ui_require_sales_history"]),
            "quantitative_min_score": int(st.session_state["ui_min_score"]),
            "max_review_queue": int(st.session_state["ui_max_queue"]),
            "require_dividend": bool(st.session_state["ui_require_dividend"]),
            "minimum_forecast_dividend_yield": float(st.session_state["ui_min_dividend_yield_pct"]) / 100,
            "maximum_forecast_dividend_yield": float(st.session_state["ui_max_dividend_yield_pct"]) / 100,
            "minimum_annual_dividend_per_share": float(st.session_state["ui_min_dividend_per_share"]),
            "maximum_payout_ratio": float(st.session_state["ui_max_payout_pct"]) / 100,
            "exclude_forecast_dividend_cut": bool(st.session_state["ui_exclude_dividend_cut"]),
            "selection_strategy": str(st.session_state.get("ui_selection_strategy", "value_dislocation")),
            "minimum_volatility_60d": float(st.session_state.get("ui_min_volatility_pct", 35.0)) / 100,
            "minimum_average_intraday_range_20d": float(st.session_state.get("ui_min_intraday_range_pct", 2.5)) / 100,
            "minimum_daytrade_activity_score": int(st.session_state.get("ui_min_daytrade_score", 50)),
        },
    }


def render_condition_builder() -> None:
    bundle = _bundle_or_none()
    if bundle is None:
        st.warning("先に「データ更新」タブで実データを取得してください。")
        return

    _initialize_condition_state()
    base_config = load_config(REAL_CONFIG)
    status = _read_json(REAL_OUTPUT / "run_status_latest.json")

    st.subheader("条件を設定して候補を再計算")
    st.info(
        "スライダーを変更しても再計算されません。最後に「条件を適用」を押したときだけ、"
        "約4,000銘柄の集約済み指標を再評価します。J-Quants APIにはアクセスしません。"
    )

    rule_labels = {
        "外的要因で下落 × 経営良好": "value_dislocation",
        "値動き活発（デイトレ候補）": "active_trading",
    }
    current_draft_rule = str(st.session_state.get("ui_rule_choice_draft", st.session_state.get("ui_selection_strategy", "value_dislocation")))
    selected_rule_label = st.selectbox(
        "大まかな抽出ルール",
        list(rule_labels.keys()),
        index=list(rule_labels.values()).index(current_draft_rule) if current_draft_rule in rule_labels.values() else 0,
        help="抽出ルールの変更だけではJ-Quants APIを呼びません。『条件を適用』後に取得済みスナップショットを再評価します。",
    )
    draft_rule = rule_labels[selected_rule_label]
    st.session_state["ui_rule_choice_draft"] = draft_rule
    if draft_rule == "active_trading":
        st.info(
            "値動き活発型は、売買代金・60日ボラティリティ・20日平均日中値幅を中心に候補化します。"
            "値動きが大きいほど損失も拡大しやすいため、売買推奨ではなく調査候補として扱います。"
            "候補抽出は取得済みJ-Quantsスナップショット、候補後の最新トレンド確認はYahoo Finance系を使います。"
        )
    else:
        st.info("従来どおり、経営状態を確認しながら外的要因等で大きく下落した銘柄を探します。")

    top1, top2 = st.columns([2, 3])
    if draft_rule == "value_dislocation":
        with top1:
            selected_preset = st.selectbox(
                "投資スタイル",
                preset_names() + ["カスタム"],
                key="condition_preset",
                on_change=_on_preset_change,
                help="安全重視・標準・割安重視など、複数の抽出条件をまとめて切り替えます。",
            )
            if selected_preset in PRESETS:
                st.caption(PRESETS[selected_preset]["description"])
        with top2:
            st.caption(
                "投資スタイルを選択すると、各パラメータへ直ちに反映されます。"
                "その後に個別調整し、最後に「条件を適用」を押してください。"
            )
    else:
        with top1:
            st.markdown("**値動き活発型**")
            st.caption("共通条件と値動き条件を調整してください。財務・配当・市場劣後条件は候補抽出には使いません。")
        with top2:
            st.caption("初期目安: 60日年率ボラ35%以上、20日平均日中値幅2.5%以上、値動き活発度50点以上。")

    active_mode = draft_rule == "active_trading"
    with st.form("screening_conditions", clear_on_submit=False):
        st.markdown("### 1. 共通の必須条件")
        col1, col2, col3 = st.columns(3)
        with col1:
            markets = st.multiselect("対象市場", ["Prime", "Standard", "Growth"], default=st.session_state["ui_markets"], help=METRIC_HELP["allowed_markets"])
            turnover = st.slider("20日平均売買代金（百万円以上）", 0, 1000, value=int(st.session_state["ui_turnover_million"]), step=10, help=METRIC_HELP["min_average_turnover_yen_20d"])
            min_price = st.slider("最低株価（円）", 0, 3000, value=int(st.session_state["ui_min_price"]), step=50, help=METRIC_HELP["min_price_yen"])
        with col2:
            equity = st.slider("自己資本比率（%以上）", 0, 80, value=int(st.session_state["ui_equity_pct"]), step=5, help=METRIC_HELP["minimum_equity_ratio"], disabled=active_mode)
            ocf_years = st.slider("営業CFがプラスの年数（直近最大3期）", 0, 3, value=int(st.session_state["ui_ocf_years"]), step=1, help=METRIC_HELP["minimum_operating_cf_positive_ratio_3y"], disabled=active_mode)
            sales_cagr = st.slider("売上CAGR（%以上）", -30, 30, value=int(st.session_state["ui_sales_cagr_pct"]), step=1, help=METRIC_HELP["minimum_sales_cagr_3y"], disabled=active_mode)
            require_sales = st.checkbox("売上履歴が不足する銘柄を除外", value=bool(st.session_state["ui_require_sales_history"]), disabled=active_mode, help="売上成長を十分な年数で確認できない銘柄を候補から外します。")
        with col3:
            op_margin = st.slider("営業利益率（%以上）", -10, 30, value=int(st.session_state["ui_op_margin_pct"]), step=1, help=METRIC_HELP["minimum_operating_margin"], disabled=active_mode)
            forecast_decline = st.slider("許容する会社予想の最大減益率（%）", 0, 80, value=int(st.session_state["ui_forecast_decline_pct"]), step=5, help=METRIC_HELP["maximum_forecast_op_decline"], disabled=active_mode)
            require_forecast = st.checkbox("会社予想がない銘柄を除外", value=bool(st.session_state["ui_require_forecast"]), disabled=active_mode, help="会社発表の業績予想を確認できない銘柄を候補から外します。")
            drawdown = st.slider("52週高値からの下落率（%以上）", 0, 70, value=int(st.session_state["ui_drawdown_pct"]), step=1, help=METRIC_HELP["minimum_drawdown_52w"], disabled=active_mode)

        st.markdown("### 2. 構造悪化ガード（バリュートラップ回避）")
        use_structural_guard = st.checkbox(
            "利益の質・採算悪化・会社予想修正・同業比較を必須チェックにする",
            value=bool(st.session_state["ui_use_structural_guard"]),
            disabled=active_mode,
            help="過去業績が良くても企業固有の構造悪化が進んでいる銘柄を除外します。データ欠損だけでは除外せず警告します。",
        )
        sg1, sg2, sg3, sg4 = st.columns(4)
        with sg1:
            min_cash_conversion_pct = st.slider(
                "最低 利益現金化率（%）", -100.0, 300.0,
                value=float(st.session_state["ui_min_cash_conversion_pct"]), step=5.0,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_cash_conversion_ratio"],
            )
        with sg2:
            max_margin_deterioration_pt = st.slider(
                "営業利益率の最大悪化幅（pt）", 0.0, 20.0,
                value=float(st.session_state["ui_max_margin_deterioration_pt"]), step=0.5,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_operating_margin_change_3y"],
            )
        with sg3:
            max_forecast_revision_decline_pct = st.slider(
                "会社予想の最大下方修正率（%）", 0.0, 50.0,
                value=float(st.session_state["ui_max_forecast_revision_decline_pct"]), step=1.0,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_forecast_revision_rate"],
            )
        with sg4:
            max_sector_underperformance_pct = st.slider(
                "同業中央値への最大劣後率（6か月・%）", 0.0, 40.0,
                value=float(st.session_state["ui_max_sector_underperformance_pct"]), step=1.0,
                disabled=active_mode or (not use_structural_guard),
                help=METRIC_HELP["minimum_sector_relative_return_6m"],
            )
        st.caption("利益現金化率=営業CF÷営業利益。営業利益率の悪化幅は直近最大3期、会社予想修正は同じ対象年度の前回予想比、同業比較は同業種の6か月騰落率中央値比です。")

        st.markdown("### 3. 配当条件")
        dv1, dv2, dv3 = st.columns(3)
        with dv1:
            require_dividend = st.checkbox("配当を必須条件にする", value=bool(st.session_state["ui_require_dividend"]), disabled=active_mode, help="オンにすると、指定した配当利回り・配当額・配当性向を必須条件にします。")
            min_dividend_per_share = st.number_input("最低1株年間配当（円）", min_value=0.0, max_value=1000.0, value=float(st.session_state["ui_min_dividend_per_share"]), step=1.0, disabled=(not require_dividend) or active_mode, help="1株当たり年間配当がこの金額以上の銘柄だけを残します。")
        with dv2:
            min_dividend_yield_pct = st.slider("最低予想配当利回り（%）", 0.0, 15.0, value=float(st.session_state["ui_min_dividend_yield_pct"]), step=0.1, disabled=(not require_dividend) or active_mode, help=METRIC_HELP["minimum_forecast_dividend_yield"])
            max_dividend_yield_pct = st.slider("最大予想配当利回り（%）", 1.0, 20.0, value=max(1.0, float(st.session_state["ui_max_dividend_yield_pct"])), step=0.5, disabled=(not require_dividend) or active_mode, help="異常に高い利回りを減配懸念として除外する上限です。")
        with dv3:
            max_payout_pct = st.slider("最大配当性向（%）", 10.0, 200.0, value=float(st.session_state["ui_max_payout_pct"]), step=5.0, disabled=(not require_dividend) or active_mode, help=METRIC_HELP["maximum_payout_ratio"])
            exclude_dividend_cut = st.checkbox("減配予想の銘柄を除外", value=bool(st.session_state["ui_exclude_dividend_cut"]), disabled=(not require_dividend) or active_mode, help="会社予想の年間配当が前期実績を下回る銘柄を除外します。")
        st.caption("予想配当は『次期会社予想 → 当期会社予想 → 直近実績』の順で採用します。高利回りは減配懸念で株価が下がっている場合もあります。")

        st.markdown("### 4. 市場比較・相対条件")
        benchmark_options = {
            "自動（正式TOPIXを優先）": "auto",
            "正式TOPIXのみ": "official_topix",
            "TOPIX連動ETF代理のみ": "topix_etf_proxy",
            "市場比較を使わない": "disabled",
        }
        current_benchmark_mode = str(st.session_state.get("ui_benchmark_mode", "auto"))
        benchmark_labels = list(benchmark_options.keys())
        benchmark_values = list(benchmark_options.values())
        benchmark_index = benchmark_values.index(current_benchmark_mode) if current_benchmark_mode in benchmark_values else 0
        benchmark_label = st.selectbox(
            "市場比較データ",
            benchmark_labels,
            index=benchmark_index,
            help="正式TOPIXが利用できない場合は、1306・1475・1305の順にTOPIX連動ETFの調整後終値を代理利用できます。",
        )
        benchmark_mode = benchmark_options[benchmark_label]
        rel1, rel2 = st.columns(2)
        with rel1:
            use_relative = st.checkbox(
                "市場平均より下落した銘柄に絞る",
                value=bool(st.session_state["ui_use_relative"]),
                disabled=active_mode or benchmark_mode == "disabled",
                help=METRIC_HELP["minimum_relative_underperformance_6m"],
            )
        with rel2:
            relative_pct = st.slider(
                "市場比較に対する6か月劣後率（%以上）",
                0, 40,
                value=int(st.session_state["ui_relative_pct"]),
                step=1,
                disabled=active_mode or (not use_relative) or benchmark_mode == "disabled",
            )

        st.markdown("### 5. 値動き活発型の条件")
        dt1, dt2, dt3 = st.columns(3)
        with dt1:
            min_volatility_pct = st.slider(
                "60日ボラティリティ（年率・%以上）", 10, 150,
                value=int(round(float(st.session_state.get("ui_min_volatility_pct", 35)))), step=5,
                disabled=not active_mode,
                help="取得済み日足の終値騰落率から計算した60日年率ボラティリティです。高いほど値動きが大きい傾向です。",
            )
        with dt2:
            min_intraday_range_pct = st.slider(
                "20日平均日中値幅（%以上）", 0.5, 15.0,
                value=float(st.session_state.get("ui_min_intraday_range_pct", 2.5)), step=0.5,
                disabled=not active_mode,
                help="直近20営業日の (高値-安値)/終値 の平均です。",
            )
        with dt3:
            min_daytrade_score = st.slider(
                "値動き活発度スコア（点以上）", 0, 100,
                value=int(st.session_state.get("ui_min_daytrade_score", 50)), step=5,
                disabled=not active_mode,
                help="ボラティリティ45%、日中値幅35%、売買代金20%のスナップショット内順位から算出します。",
            )

        st.markdown("### 6. 順位付けと表示件数")
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            min_score = st.slider("定量スコア（点以上）", 0, 80, value=int(st.session_state["ui_min_score"]), step=1, disabled=active_mode, help=_analysis_help("定量スコア"))
        with sc2:
            max_queue = st.slider("最大候補数", 5, 100, value=int(st.session_state["ui_max_queue"]), step=5, help="スコア上位から一覧へ残す候補銘柄数の上限です。")
        with sc3:
            star_only = st.checkbox(
                "☆だけの銘柄を表示",
                value=bool(st.session_state.get("ui_star_only", False)),
                disabled=active_mode,
                help="定量条件通過後、Yahoo Finance系の最新トレンド再判定で◎☆となった銘柄だけを表示します。J-Quantsの再取得は行いません。",
            )
        submitted = st.form_submit_button("条件を適用", type="primary", width="stretch")

    if submitted:
        st.session_state.update({
            "ui_markets": markets, "ui_turnover_million": turnover,
            "ui_min_price": min_price, "ui_equity_pct": equity,
            "ui_ocf_years": ocf_years, "ui_sales_cagr_pct": sales_cagr,
            "ui_require_sales_history": require_sales, "ui_op_margin_pct": op_margin,
            "ui_forecast_decline_pct": forecast_decline,
            "ui_use_structural_guard": use_structural_guard,
            "ui_min_cash_conversion_pct": min_cash_conversion_pct,
            "ui_max_margin_deterioration_pt": max_margin_deterioration_pt,
            "ui_max_forecast_revision_decline_pct": max_forecast_revision_decline_pct,
            "ui_max_sector_underperformance_pct": max_sector_underperformance_pct,
            "ui_require_forecast": require_forecast, "ui_drawdown_pct": drawdown,
            "ui_use_relative": use_relative, "ui_relative_pct": relative_pct, "ui_benchmark_mode": benchmark_mode,
            "ui_min_score": min_score, "ui_max_queue": max_queue,
            "ui_require_dividend": require_dividend,
            "ui_min_dividend_yield_pct": min_dividend_yield_pct,
            "ui_max_dividend_yield_pct": max_dividend_yield_pct,
            "ui_min_dividend_per_share": min_dividend_per_share,
            "ui_max_payout_pct": max_payout_pct,
            "ui_exclude_dividend_cut": exclude_dividend_cut,
            "ui_selection_strategy": draft_rule,
            "ui_min_volatility_pct": min_volatility_pct,
            "ui_min_intraday_range_pct": min_intraday_range_pct,
            "ui_min_daytrade_score": min_daytrade_score,
            "ui_star_only": bool(star_only),
        })
        if draft_rule == "active_trading":
            st.session_state["condition_preset"] = "カスタム"
        st.session_state["screening_revision"] = st.session_state.get("screening_revision", 0) + 1

    selected_mode = str(st.session_state.get("ui_benchmark_mode", "auto"))
    prepared = bundle["prepared"]
    has_official = bool(prepared.get("topix_available", pd.Series(dtype=bool)).fillna(False).any())
    has_proxy = bool(prepared.get("topix_proxy_available", pd.Series(dtype=bool)).fillna(False).any())
    applied_strategy = str(st.session_state.get("ui_selection_strategy", "value_dislocation"))
    if applied_strategy == "value_dislocation" and selected_mode == "official_topix" and not has_official:
        st.warning("正式TOPIXを利用できません。相対条件は保留されます。")
    elif applied_strategy == "value_dislocation" and selected_mode == "topix_etf_proxy" and not has_proxy:
        st.warning("TOPIX連動ETF代理値を利用できません。相対条件は保留されます。")
    elif applied_strategy == "value_dislocation" and selected_mode == "auto" and not has_official and not has_proxy:
        st.warning("正式TOPIX・ETF代理値とも利用できません。相対条件は保留されます。")
    elif applied_strategy == "value_dislocation" and selected_mode == "auto" and not has_official and has_proxy:
        proxy_label = prepared.loc[prepared["topix_proxy_available"].fillna(False), "topix_proxy_label"].dropna()
        label = str(proxy_label.iloc[0]) if not proxy_label.empty else "TOPIX連動ETF"
        st.warning(f"市場比較には {label} の調整後終値を代理利用しています。正式TOPIXではありません。")

    overrides = _current_overrides()
    cache_key = json.dumps(overrides, ensure_ascii=False, sort_keys=True)
    if st.session_state.get("screen_cache_key") != cache_key:
        dynamic_config = copy_with_screen_overrides(base_config, overrides)
        audit = apply_quantitative_criteria(bundle["prepared"], dynamic_config)
        shortlist = shortlist_from_table(audit, dynamic_config)
        st.session_state["screen_cache_key"] = cache_key
        st.session_state["screen_audit"] = audit
        st.session_state["screen_shortlist"] = shortlist
        st.session_state["screen_funnel"] = screening_funnel(audit)
    audit = st.session_state["screen_audit"]
    shortlist = st.session_state["screen_shortlist"]
    funnel = st.session_state["screen_funnel"]
    score_passed = (
        audit.loc[audit["selected_for_review"]]
        .sort_values(["strategy_score", "average_turnover_yen_20d"], ascending=False)
        .reset_index(drop=True)
    )

    st.divider()
    st.markdown("### 再計算結果")
    metrics = st.columns(5)
    metrics[0].metric("評価可能銘柄", f"{len(audit):,}", help="取得済みデータから抽出条件を評価できた銘柄数です。")
    if applied_strategy == "active_trading":
        metrics[1].metric("高ボラ通過", f"{funnel[2]['count']:,}", help="設定した60日年率ボラティリティ以上だった銘柄数です。")
        metrics[2].metric("日中値幅通過", f"{funnel[3]['count']:,}", help="設定した20日平均日中値幅以上だった銘柄数です。")
        metrics[3].metric("活発度通過", f"{funnel[-1]['count']:,}", help="値動き活発度スコアの条件を通過した銘柄数です。")
    else:
        metrics[1].metric("財務条件通過", f"{funnel[2]['count']:,}", help="自己資本・利益・売上などの必須財務条件を通過した銘柄数です。")
        metrics[2].metric("価格下落条件通過", f"{funnel[3]['count']:,}", help="52週高値からの下落や市場比較など、価格条件を通過した銘柄数です。")
        metrics[3].metric("スコア通過", f"{funnel[-1]['count']:,}", help="必須条件と最低定量スコアを通過した銘柄数です。")
    metrics[4].metric("統合候補", f"{len(score_passed):,}", help="最新トレンド再確認へ進む候補銘柄数です。")
    _analysis_dataframe(pd.DataFrame(funnel), width="stretch", hide_index=True)

    export_document = profile_document("current_conditions", st.session_state["condition_preset"], overrides)
    export_json = json.dumps(export_document, ensure_ascii=False, indent=2)
    tools1, tools2, tools3 = st.columns(3)
    with tools1:
        profile_name = st.text_input("設定名", value="my_conditions", help="現在の抽出条件をPCへ保存するときのファイル名です。")
        if st.button("この設定をPCへ保存"):
            path = save_profile(PROFILE_DIR, profile_name, st.session_state["condition_preset"], overrides)
            st.success(f"保存しました: {path.name}")
    with tools2:
        st.download_button("設定JSONをダウンロード", data=export_json.encode("utf-8"), file_name="value_dislocation_conditions.json", mime="application/json")
    with tools3:
        if not shortlist.empty:
            st.download_button("候補CSVをダウンロード", data=shortlist.to_csv(index=False).encode("utf-8-sig"), file_name="quantitative_shortlist_custom.csv", mime="text/csv")

    st.markdown("### 配当金額の表示株数")
    st.number_input("保有株数（候補カードの配当金額に使用）", min_value=1, max_value=1_000_000, value=int(st.session_state.get("dividend_shares", 100)), step=100, key="dividend_shares", help="通常の国内株式は100株単位ですが、S株などを想定して任意株数も入力できます。")
    if score_passed.empty:
        st.markdown("### 統合候補一覧（抽出条件 + 最新トレンド）")
        st.info("現在の条件をすべて通過する銘柄はありません。")
    else:
        displayed_latest = _render_latest_candidate_trends(
            score_passed,
            star_only=bool(st.session_state.get("ui_star_only", False)),
            analysis_as_of=bundle["as_of"],
        )
        displayed_codes = set(displayed_latest.get("raw_code", pd.Series(dtype=str)).astype(str)) if not displayed_latest.empty else set()
        displayed_shortlist = shortlist.loc[shortlist["code"].astype(str).isin(displayed_codes)].copy()
        with st.expander("詳細指標を表で表示"):
            display_cols = (["code", "name", "market", "sector", "close", "strategy_score", "daytrade_activity_score", "volatility_60d", "average_intraday_range_20d", "average_turnover_yen_20d", "warning_reasons"] if applied_strategy == "active_trading" else ["code", "name", "market", "sector", "close", "quantitative_score", "drawdown_52w", "relative_return_6m", "sales_cagr_3y", "operating_margin", "operating_cf_positive_ratio_3y", "equity_ratio", "forecast_op_growth", "forecast_annual_dividend_per_share", "forecast_dividend_yield", "payout_ratio", "forecast_dividend_change_rate", "warning_reasons"])
            _analysis_dataframe(displayed_shortlist[[c for c in display_cols if c in displayed_shortlist.columns]], width="stretch", hide_index=True)
        if bool(st.session_state.get("ui_star_only", False)) and applied_strategy != "active_trading":
            st.download_button(
                "☆限定候補CSVをダウンロード",
                data=displayed_shortlist.to_csv(index=False).encode("utf-8-sig"),
                file_name="star_only_candidates.csv",
                mime="text/csv",
            )
        st.markdown("#### 候補になった理由")
        for _, row in displayed_shortlist.iterrows():
            _candidate_card(row)

    with st.expander("条件に近かったが除外された銘柄"):
        near = audit.loc[~audit["selected_for_review"]].sort_values("quantitative_score", ascending=False).head(30)
        _analysis_dataframe(near[[c for c in ["code", "name", "quantitative_score", "fail_reasons", "warning_reasons"] if c in near.columns]], width="stretch", hide_index=True)



def _render_history_analysis_summary(lines: list[str], *, title: str = "分析結果サマリ") -> None:
    if not lines:
        return
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown("\n".join(f"- {line}" for line in lines))


def _render_history_daily(evaluation_signature) -> None:
    analysis_dir = ROOT / "data" / "history" / "analysis"
    files = sorted(analysis_dir.glob("????-??-??.csv.gz")) if analysis_dir.exists() else []
    if not files:
        st.info("まだ日次分析履歴がありません。次回 run_real.cmd 実行時から日付別に保存されます。")
        return

    first_day = pd.Timestamp(files[0].name[:10]).date()
    last_day = pd.Timestamp(files[-1].name[:10]).date()
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    period = c1.date_input(
        "期間",
        value=(max(first_day, last_day - timedelta(days=30)), last_day),
        min_value=first_day,
        max_value=last_day,
        key="history_period",
    )
    query = c2.text_input("銘柄コード・企業名", value="", key="history_query", help="保存済み履歴を銘柄コードまたは企業名の一部で絞り込みます。")
    selected_only = c3.checkbox("定量候補だけ表示（selected_for_review）", value=True, key="history_selected_only", help=_analysis_help("selected_for_review"))
    if isinstance(period, (tuple, list)) and len(period) == 2:
        start, end = period
    else:
        start = end = period

    final_options = ["◎☆", "◎", "○", "△", "×", "未評価", "対象外"]
    selected_final = c4.multiselect("当日の最終評価", final_options, default=final_options, key="history_final_evaluation", help=_analysis_help("final_evaluation"))
    analysis_signature = _analysis_history_signature(start, end)
    hist = _cached_load_attached_analysis_history(
        str(ROOT), start.isoformat(), end.isoformat(), selected_only, analysis_signature, evaluation_signature
    )

    if selected_final and not hist.empty:
        hist = hist.loc[hist["final_evaluation"].astype(str).isin(selected_final)]
    if query and not hist.empty:
        q = query.strip().lower()
        hist = hist.loc[
            hist.get("code", "").astype(str).str.lower().str.contains(q, regex=False)
            | hist.get("name", "").astype(str).str.lower().str.contains(q, regex=False)
        ]

    f1, f2 = st.columns(2)
    status_options = ["当日評価済み", "後日補完", "未評価", "評価対象外"]
    selected_status = f1.multiselect("評価状態", status_options, default=status_options, key="history_evaluation_status", help=_analysis_help("evaluation_status"))
    reason_options = ["評価履歴なし", "Yahoo取得失敗", "Yahoo100件制限で未実施", "旧履歴", "履歴不足／再現不能", "その他", "定量候補外"]
    selected_reasons = f2.multiselect("未評価理由", reason_options, default=reason_options, key="history_unassessed_reason", help=_analysis_help("未評価理由"))
    if selected_status and not hist.empty:
        hist = hist.loc[hist["evaluation_status"].astype(str).isin(selected_status)]
    if selected_reasons and not hist.empty:
        reason_mask = hist["unassessed_reason"].astype(str).isin(selected_reasons)
        assessed_mask = hist["evaluation_status"].astype(str).isin(["当日評価済み", "後日補完", "評価対象外"])
        hist = hist.loc[reason_mask | assessed_mask]

    _render_history_analysis_summary(daily_history_text_summary(hist))
    st.metric("該当履歴", f"{len(hist):,} 行", help="現在の期間・銘柄・評価フィルターに一致する保存済み分析履歴の行数です。")
    if not hist.empty:
        daily_chart = daily_evaluation_counts(hist)
        if not daily_chart.empty:
            st.markdown("#### 可視化：当日の最終評価件数の推移")
            st.caption("現在の検索条件に該当する履歴を日付別・最終評価別に集計しています。追加の外部データ取得は行いません。")
            st.line_chart(daily_chart, width="stretch")
    st.caption(
        "selected_for_review は定量条件の通過有無です。定量候補外は『評価対象外』として扱い、未評価件数には含めません。評価状態（当日評価済み / 後日補完 / 未評価 / 評価対象外）を保存・表示します。"
    )
    st.caption("履歴ファイルの読込みと評価履歴の結合はファイル更新時だけ再計算し、通常の検索・ページ移動ではキャッシュを再利用します。")

    unassessed = (
        hist.loc[hist.get("evaluation_status", pd.Series(index=hist.index, dtype=str)).astype(str) == "未評価"].copy()
        if not hist.empty
        else pd.DataFrame()
    )
    if not unassessed.empty:
        st.markdown("#### 未評価を後から再評価")
        st.caption(
            "表示中の未評価だけを対象に、Yahoo過去日足を取得し、各分析日より後の株価を切り捨てて当時の最終評価を再現します。元の未評価は original_final_evaluation として保持します。"
        )
        unique_codes = sorted(set(unassessed.get("code", pd.Series(dtype=str)).dropna().astype(str)))
        if len(unique_codes) >= YAHOO_BULK_FETCH_BLOCK_THRESHOLD:
            st.warning(
                f"後日再評価のYahoo Finance系対象が {len(unique_codes):,} 銘柄あります。"
                "通常の一括再評価は100銘柄以上では開始しません。代わりに低速バッチ再評価を利用できます。"
            )
            slow_batch_size = st.selectbox(
                "低速バッチの1回あたり銘柄数",
                SLOW_REVALUATION_BATCH_OPTIONS,
                index=1,
                key="history_slow_revaluation_batch_size",
                help="1回のクリックでこの件数までYahoo日足を順番に取得します。完了分は都度保存されるため、中断後も続きから再開できます。",
            )
            slow_batch = select_slow_revaluation_batch(unassessed, batch_size=int(slow_batch_size))
            slow_codes = sorted(set(slow_batch.get("code", pd.Series(dtype=str)).dropna().astype(str)))
            st.caption(
                f"未評価 {len(unassessed):,} 行 / {len(unique_codes):,} 銘柄。"
                f"次のバッチでは最大 {len(slow_codes):,} 銘柄を、約 {SLOW_REVALUATION_DELAY_SECONDS:.2f} 秒間隔で処理します。"
            )
            if st.button(
                f"低速バッチ再評価を開始・続行（次の{len(slow_codes):,}銘柄）",
                key="history_slow_backfill_unassessed",
                type="primary",
                disabled=not slow_codes,
            ):
                progress = st.progress(0.0, text="低速バッチ再評価を開始します…")
                completed = 0
                remaining_after_attempt = 0
                failed_codes = []
                evaluated_at = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
                for idx, code in enumerate(slow_codes, start=1):
                    code_rows = slow_batch.loc[slow_batch["code"].astype(str) == str(code)].copy()
                    try:
                        history_for_code = _history_validation_market_history(code)
                        histories = {str(code): history_for_code}
                    except Exception:
                        histories = {}
                        failed_codes.append(str(code))
                    rebuilt_code = revaluate_unassessed_rows(code_rows, histories, evaluated_at=evaluated_at)
                    if not rebuilt_code.empty:
                        for day, group in rebuilt_code.groupby("evaluation_date", dropna=False):
                            if not day:
                                continue
                            as_of_values = group.get("analysis_as_of", pd.Series(dtype=str)).dropna().astype(str)
                            analysis_as_of = as_of_values.iloc[0] if not as_of_values.empty else day
                            upsert_daily_evaluations(ROOT, group, evaluation_date=day, analysis_as_of=analysis_as_of)
                        completed += int((rebuilt_code.get("evaluation_status", pd.Series(dtype=str)).astype(str) == "後日補完").sum())
                        remaining_after_attempt += int((rebuilt_code.get("evaluation_status", pd.Series(dtype=str)).astype(str) == "未評価").sum())
                    progress.progress(
                        idx / max(len(slow_codes), 1),
                        text=f"低速バッチ再評価 {idx:,}/{len(slow_codes):,} 銘柄（{code}）",
                    )
                    if idx < len(slow_codes):
                        time.sleep(SLOW_REVALUATION_DELAY_SECONDS)
                write_star_outcomes(ROOT)
                st.success(
                    f"このバッチを完了しました。後日補完 {completed:,} 件 / 未評価のまま {remaining_after_attempt:,} 件。完了分は都度保存済みです。"
                )
                if failed_codes:
                    st.warning(f"このバッチでYahoo日足を取得できなかった銘柄: {len(failed_codes):,} 件")
                st.rerun()

            estimated_seconds = (
                max(len(unique_codes) - 1, 0) * SLOW_REVALUATION_DELAY_SECONDS
                + max((len(unique_codes) - 1) // max(int(slow_batch_size), 1), 0) * SLOW_REVALUATION_BATCH_PAUSE_SECONDS
            )
            loop_confirm = st.checkbox(
                "全未評価を最後まで自動ループする",
                key="history_slow_revaluation_loop_confirm",
                help=(
                    "表示中の未評価銘柄を、選択したバッチ件数ごとに区切りながら最後まで1回ずつ処理します。"
                    "各銘柄の結果は都度保存され、取得失敗銘柄は未評価のまま残ります。"
                ),
            )
            st.caption(
                f"全件ループは {len(unique_codes):,} 銘柄を順番に1回ずつ試行します。"
                f"最低でも約 {estimated_seconds / 60:.1f} 分 + Yahoo応答時間が目安です。"
                "ブラウザを閉じても完了済み分は保存されます。取得失敗銘柄は同じ実行内で無限再試行しません。"
            )
            if st.button(
                f"全件を低速ループ再評価（{len(unique_codes):,}銘柄）",
                key="history_slow_backfill_all_unassessed",
                disabled=(not loop_confirm or not unique_codes),
            ):
                progress = st.progress(0.0, text="全件低速ループ再評価を開始します…")
                completed = 0
                remaining_after_attempt = 0
                failed_codes = []
                evaluated_at = pd.Timestamp.now(tz="Asia/Tokyo").isoformat()
                total_codes = len(unique_codes)
                batch_size_value = max(int(slow_batch_size), 1)
                for idx, code in enumerate(unique_codes, start=1):
                    code_rows = unassessed.loc[unassessed["code"].astype(str) == str(code)].copy()
                    try:
                        history_for_code = _history_validation_market_history(code)
                        histories = {str(code): history_for_code}
                    except Exception:
                        histories = {}
                        failed_codes.append(str(code))
                    rebuilt_code = revaluate_unassessed_rows(code_rows, histories, evaluated_at=evaluated_at)
                    if not rebuilt_code.empty:
                        for day, group in rebuilt_code.groupby("evaluation_date", dropna=False):
                            if not day:
                                continue
                            as_of_values = group.get("analysis_as_of", pd.Series(dtype=str)).dropna().astype(str)
                            analysis_as_of = as_of_values.iloc[0] if not as_of_values.empty else day
                            upsert_daily_evaluations(ROOT, group, evaluation_date=day, analysis_as_of=analysis_as_of)
                        completed += int((rebuilt_code.get("evaluation_status", pd.Series(dtype=str)).astype(str) == "後日補完").sum())
                        remaining_after_attempt += int((rebuilt_code.get("evaluation_status", pd.Series(dtype=str)).astype(str) == "未評価").sum())
                    batch_no = ((idx - 1) // batch_size_value) + 1
                    progress.progress(
                        idx / max(total_codes, 1),
                        text=f"全件低速ループ再評価 バッチ{batch_no} / {idx:,}/{total_codes:,} 銘柄（{code}）",
                    )
                    if idx < total_codes:
                        time.sleep(SLOW_REVALUATION_DELAY_SECONDS)
                        if idx % batch_size_value == 0:
                            time.sleep(SLOW_REVALUATION_BATCH_PAUSE_SECONDS)
                write_star_outcomes(ROOT)
                st.success(
                    f"全件低速ループを最後まで試行しました。後日補完 {completed:,} 件 / 未評価のまま {remaining_after_attempt:,} 件。完了分はすべて都度保存済みです。"
                )
                if failed_codes:
                    st.warning(
                        f"Yahoo日足を取得できず未評価のまま残った銘柄: {len(set(failed_codes)):,} 銘柄。"
                        "必要なら未評価で絞り込み、後でもう一度実行してください。"
                    )
                st.rerun()
        elif st.button(
            f"表示中の未評価 {len(unassessed):,} 件を後から再評価",
            key="history_backfill_unassessed",
            type="primary",
        ):
            histories = {}
            failed_codes = []
            with st.spinner(f"対象日の時点までのYahoo日足で再評価しています（{len(unique_codes)}銘柄）…"):
                for code in unique_codes:
                    try:
                        histories[code] = _history_validation_market_history(code)
                    except Exception:
                        failed_codes.append(code)
                rebuilt = revaluate_unassessed_rows(
                    unassessed,
                    histories,
                    evaluated_at=pd.Timestamp.now(tz="Asia/Tokyo").isoformat(),
                )
                if not rebuilt.empty:
                    for day, group in rebuilt.groupby("evaluation_date", dropna=False):
                        if not day:
                            continue
                        as_of_values = group.get("analysis_as_of", pd.Series(dtype=str)).dropna().astype(str)
                        analysis_as_of = as_of_values.iloc[0] if not as_of_values.empty else day
                        upsert_daily_evaluations(ROOT, group, evaluation_date=day, analysis_as_of=analysis_as_of)
            write_star_outcomes(ROOT)
            completed = int((rebuilt.get("evaluation_status", pd.Series(dtype=str)).astype(str) == "後日補完").sum()) if not rebuilt.empty else 0
            remaining = int(len(rebuilt) - completed) if not rebuilt.empty else len(unassessed)
            st.success(f"後日補完 {completed:,} 件 / 未評価のまま {remaining:,} 件。結果を履歴へ保存しました。")
            if failed_codes:
                st.warning(f"Yahoo日足を取得できなかった銘柄: {len(failed_codes):,} 件")
            st.rerun()

    cols = [
        "analysis_date", "data_as_of", "code", "name", "selection_strategy", "selected_for_review",
        "final_evaluation", "evaluation_status", "unassessed_reason", "original_final_evaluation",
        "original_unassessed_reason", "evaluated_at", "evaluation_as_of", "strategy_score", "close",
        "drawdown_52w", "sales_cagr_3y", "operating_margin", "equity_ratio", "forecast_op_growth", "warning_reasons",
    ]
    sort_cols = [c for c in ["analysis_date", "strategy_score"] if c in hist.columns]
    sorted_hist = hist[[c for c in cols if c in hist.columns]].sort_values(
        sort_cols,
        ascending=[False, False] if len(sort_cols) == 2 else False,
    ) if sort_cols else hist[[c for c in cols if c in hist.columns]]
    _render_history_sortable_stock_table(sorted_hist, "daily_history")


def _render_history_evaluations(evaluation: pd.DataFrame) -> None:
    if evaluation.empty:
        st.info("評価履歴はまだありません。『条件設定・候補』で統合候補一覧を表示すると、その日の評価が保存されます。")
        return
    e = evaluation.copy()
    c1, c2, c3, c4 = st.columns(4)
    q = c1.text_input("銘柄コード・企業名で検索", key="evaluation_query")
    symbols = sorted([x for x in e.get("intuitive_symbol", pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    selected_symbols = c2.multiselect("保存評価", symbols, default=symbols, key="evaluation_symbols")
    strategies = sorted([x for x in e.get("selection_strategy", pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    selected_strategies = c3.multiselect("抽出ルール", strategies, default=strategies, key="evaluation_strategies")
    statuses = sorted([x for x in e.get("evaluation_status", pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    selected_eval_status = c4.multiselect("評価状態", statuses, default=statuses, key="evaluation_status_filter")
    if q:
        qq = q.strip().lower()
        e = e.loc[
            e.get("code", "").astype(str).str.lower().str.contains(qq, regex=False)
            | e.get("name", "").astype(str).str.lower().str.contains(qq, regex=False)
        ]
    if selected_symbols:
        e = e.loc[e["intuitive_symbol"].astype(str).isin(selected_symbols)]
    if selected_strategies and "selection_strategy" in e.columns:
        e = e.loc[e["selection_strategy"].astype(str).isin(selected_strategies)]
    if selected_eval_status and "evaluation_status" in e.columns:
        e = e.loc[e["evaluation_status"].astype(str).isin(selected_eval_status)]
    _render_history_analysis_summary(evaluation_history_text_summary(e))
    st.metric("該当評価履歴", f"{len(e):,} 行")
    if not e.empty:
        symbol_chart = evaluation_symbol_counts(e)
        if not symbol_chart.empty:
            st.markdown("#### 可視化：最終評価の構成")
            st.caption("現在の検索条件に該当する評価履歴を ◎☆ / ◎ / ○ / △ / × などの件数で比較します。")
            st.bar_chart(symbol_chart, width="stretch")
    sorted_e = e.sort_values("evaluation_date", ascending=False)
    _render_history_sortable_stock_table(sorted_e, "evaluation_history")


def _render_history_star_validation(evaluation: pd.DataFrame) -> None:
    star_signature = _star_outcomes_signature()
    saved_star_events = _cached_load_star_outcomes(str(ROOT), star_signature)
    # Evaluation history is the source of truth for the complete ◎☆ event set.
    # Reconcile every render so older events cannot disappear merely because the
    # outcomes file was created later; preserve any already-enriched returns.
    star_events = reconcile_star_outcomes(evaluation, saved_star_events) if not evaluation.empty else saved_star_events.copy()
    saved_keys = set()
    current_keys = set()
    if not saved_star_events.empty and {"code", "star_date"}.issubset(saved_star_events.columns):
        saved_keys = set(zip(saved_star_events["code"].astype(str), saved_star_events["star_date"].astype(str)))
    if not star_events.empty and {"code", "star_date"}.issubset(star_events.columns):
        current_keys = set(zip(star_events["code"].astype(str), star_events["star_date"].astype(str)))
    if current_keys != saved_keys:
        save_star_outcomes(ROOT, star_events)
        star_signature = _star_outcomes_signature()

    if star_events.empty:
        st.info("◎☆イベントがまだありません。◎☆評価が保存されると、その日を起点に追跡を開始します。")
        return

    star_codes = sorted(set(star_events.get("code", pd.Series(dtype=str)).dropna().astype(str)))
    refresh_col, info_col = st.columns([2, 5])
    refresh_clicked = refresh_col.button("Yahooで10/20/30/60/90/180日実績を更新", key="history_refresh_star_outcomes", type="primary")
    info_col.caption("画面を開いただけではYahooへアクセスしません。必要なときだけ明示的に更新するため、履歴画面の初期表示を高速化しています。")
    if refresh_clicked:
        if star_codes and yahoo_bulk_fetch_allowed(len(star_codes)):
            histories = {}
            with st.spinner(f"◎☆実績の10/20/30/60/90/180日リターンを最新Yahoo日足で更新しています（{len(star_codes)}銘柄）…"):
                for code in star_codes:
                    try:
                        histories[code] = _history_validation_market_history(code)
                    except Exception:
                        continue
            if histories:
                star_events = enrich_star_events_with_market_histories(star_events, histories)
                save_star_outcomes(ROOT, star_events)
                st.success("◎☆実績を更新しました。")
                st.rerun()
        elif len(star_codes) >= YAHOO_BULK_FETCH_BLOCK_THRESHOLD:
            st.warning(
                f"◎☆実績更新のYahoo Finance系対象が {len(star_codes):,} 銘柄あります。"
                f"{YAHOO_BULK_FETCH_BLOCK_THRESHOLD}銘柄以上では外部取得を実施しません。"
            )

    completed_by_horizon = {
        horizon: pd.to_numeric(star_events.get(f"return_{horizon}d", pd.Series(index=star_events.index, dtype=float)), errors="coerce").dropna()
        for horizon in STAR_OUTCOME_HORIZONS
    }
    unique_star_codes = star_events.get("code", pd.Series(dtype=str)).dropna().astype(str).nunique()
    first_metrics = st.columns(4)
    first_metrics[0].metric("◎☆開始イベント", f"{len(star_events):,}", f"ユニーク {unique_star_codes:,} 銘柄")
    for idx, horizon in enumerate((10, 20, 30), start=1):
        completed = completed_by_horizon[horizon]
        first_metrics[idx].metric(f"{horizon}日確定", f"{len(completed):,}", f"平均 {completed.mean()*100:.1f}%" if len(completed) else "未確定")
    second_metrics = st.columns(3)
    for idx, horizon in enumerate((60, 90, 180)):
        completed = completed_by_horizon[horizon]
        second_metrics[idx].metric(f"{horizon}日確定", f"{len(completed):,}", f"平均 {completed.mean()*100:.1f}%" if len(completed) else "未確定")

    forward_chart = star_forward_return_summary(star_events)
    all_analysis_signature = _analysis_history_signature(None, None)
    perf = _cached_condition_performance(str(ROOT), all_analysis_signature, _star_outcomes_signature())
    _render_history_analysis_summary(star_validation_text_summary(star_events, forward_chart, perf))
    if not forward_chart.empty and pd.to_numeric(
        forward_chart.get("確定件数", pd.Series(dtype=float)), errors="coerce"
    ).fillna(0).gt(0).any():
        st.markdown("#### 可視化：◎☆後の期間別成績（リターン・プラス率・確定件数）")
        st.caption(
            "横軸は判定後の取引日数、縦軸は平均リターン、色はプラス率、円の大きさは確定件数です。"
            "線の傾きで、短期から中長期へ成績が改善したか失速したかを確認できます。"
        )
        _render_horizon_performance_bubbles(forward_chart)

    _render_history_analytical_visuals(star_events, perf)

    st.markdown("#### ◎☆銘柄サマリ（同一銘柄は1行）")
    st.caption("同じ銘柄が複数回◎☆になっても銘柄コード単位で1行にまとめます。初回/最新の◎☆日、◎☆回数、最新entry_price、確定済みイベントの平均10/20/30/60/90/180日リターンを表示します。")
    sort_order = st.segmented_control("並び順", ["最新◎☆日の新しい順", "初回◎☆日の古い順"], default="最新◎☆日の新しい順", key="star_history_sort_order", help="◎☆銘柄サマリを直近順または初回発生日順に並べます。")
    summary = summarize_star_outcomes_by_code(star_events)
    for h in STAR_OUTCOME_HORIZONS:
        col = f"return_{h}d_avg"
        if col in summary.columns:
            summary[col] = pd.to_numeric(summary[col], errors="coerce") * 100
    summary_cols = ["code", "name", "first_star_date", "latest_star_date", "star_count", "latest_entry_price"]
    for h in STAR_OUTCOME_HORIZONS:
        summary_cols.extend([f"return_{h}d_avg", f"completed_{h}d"])
    summary = summary[[c for c in summary_cols if c in summary.columns]]
    if sort_order == "初回◎☆日の古い順":
        summary = summary.sort_values(["first_star_date", "code"], ascending=[True, True])
    else:
        summary = summary.sort_values(["latest_star_date", "code"], ascending=[False, True])
    _render_history_sortable_stock_table(summary, "star_summary")
    st.caption("return_*_avg は同じ銘柄の◎☆開始イベントのうち、その期間の実績が確定済みのものだけを平均した値（%）です。completed_*d は平均に含めたイベント数です。")

    if st.checkbox("◎☆開始イベントを個別表示する", value=False, key="show_star_event_details", help="銘柄別の集約ではなく、◎☆になった日ごとの実績を表示します。"):
        event_show = star_events.copy()
        for h in STAR_OUTCOME_HORIZONS:
            if f"return_{h}d" in event_show.columns:
                event_show[f"return_{h}d"] = pd.to_numeric(event_show[f"return_{h}d"], errors="coerce") * 100
        event_cols = ["star_date", "code", "name", "entry_price"]
        for h in STAR_OUTCOME_HORIZONS:
            event_cols.extend([f"return_{h}d", f"actual_days_{h}d"])
        event_show = event_show[[c for c in event_cols if c in event_show.columns]].sort_values(["star_date", "code"], ascending=[False, True])
        _render_history_sortable_stock_table(event_show, "star_events_detail")
        st.caption("個別表示はイベント単位です。同じ銘柄が◎☆から外れた後に再び◎☆になった場合は別イベントとして複数行表示されます。")

    st.markdown("#### どの条件がその後の成績と結びついたか")
    st.caption("この集計は日次履歴が更新されたときだけ再計算し、通常の画面再描画ではキャッシュを利用します。")
    if perf.empty:
        st.info("条件別集計に必要な日次分析履歴がまだ不足しています。")
    else:
        display = perf.copy()
        for col in display.columns:
            if col.endswith("平均") or col.endswith("プラス率"):
                display[col] = pd.to_numeric(display[col], errors="coerce") * 100
        _analysis_dataframe(display, width="stretch", hide_index=True)
        horizon = st.segmented_control(
            "条件別グラフの期間",
            [f"{h}日" for h in STAR_OUTCOME_HORIZONS],
            default="90日",
            key="history_condition_chart_horizon",
            help="条件ごとの平均リターンを比較する、選定後の取引日数を選びます。",
        )
        horizon_days = int(str(horizon).removesuffix("日"))
        st.markdown(f"#### 条件の成績バブル：{horizon}（リターン・プラス率・確定件数）")
        st.caption(
            "横軸は平均リターン、縦軸はプラス率、円の大きさは確定件数です。"
            "右上かつ大きい円ほど、成績と観測数の両面で注目できます。相関傾向であり因果関係ではありません。"
        )
        _render_condition_performance_bubbles(perf, horizon_days)


def _walk_forward_data_signature() -> str:
    paths = [
        ROOT / "data/curated/latest/companies.parquet",
        ROOT / "data/curated/latest/companies.csv",
        ROOT / "data/curated/latest/prices.parquet",
        ROOT / "data/curated/latest/prices.csv",
        ROOT / "data/curated/latest/financials.parquet",
        ROOT / "data/curated/latest/financials.csv",
        ROOT / "data/curated/latest/manifest.json",
    ]
    state = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            state.append((str(path.relative_to(ROOT)), int(stat.st_size), int(stat.st_mtime_ns)))
    history_dir = ROOT / "data/history/security_master"
    if history_dir.exists():
        for path in sorted(history_dir.glob("????-??-??.csv.gz")):
            stat = path.stat()
            state.append((str(path.relative_to(ROOT)), int(stat.st_size), int(stat.st_mtime_ns)))
    return hashlib.sha256(
        json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _render_history_walk_forward() -> None:
    st.markdown("### Walk-Forward過去検証")
    st.caption(
        "現在の定量・構造悪化ルールを過去の時点へ再適用し、その後の実績を採点します。"
        "選定には各時点までの価格・開示だけを使い、将来株価は選定完了後の結果評価にのみ使用します。"
        "過去ニュースや人手の外的要因レビューは再現しないため、◎☆全体ではなく定量候補層の検証です。"
        "10/20/30/60/90/180日は暦日ではなく、選定日の後に観測できた取引セッション数です。"
    )
    st.warning(
        "生存者バイアス注意: 現在のcurated会社マスターに存在しない過去銘柄は復元できません。"
        "結果には会社マスターのカバレッジを記録し、欠落を可視化します。完全な除去には過去時点の銘柄マスターが必要です。"
    )
    modes = {
        "簡易": {
            "description": "3時点・10/30/90取引日。条件を素早く確認します。",
            "snapshots": 3, "spacing": 40, "controls": 3, "horizons": (10, 30, 90),
        },
        "標準": {
            "description": "8時点・全6期間。通常の検証に推奨します。",
            "snapshots": 8, "spacing": 20, "controls": 5,
            "horizons": tuple(STAR_OUTCOME_HORIZONS),
        },
        "詳細": {
            "description": "12時点・全6期間。時間をかけて確認します。",
            "snapshots": 12, "spacing": 10, "controls": 5,
            "horizons": tuple(STAR_OUTCOME_HORIZONS),
        },
    }
    mode_name = st.segmented_control(
        "検証モード", list(modes), default="標準", key="wf_mode",
        help="簡易は短時間、標準は通常確認、詳細は多くの過去時点を使う検証です。",
    )
    mode = modes.get(mode_name or "標準", modes["標準"])
    st.caption(mode["description"])
    advanced = st.checkbox("詳細設定を変更", value=False, key="wf_advanced", help="再現時点数・間隔・比較銘柄数・評価期間を個別に変更します。")
    if advanced:
        c1, c2, c3 = st.columns(3)
        snapshots = c1.slider("再現時点数", 3, 12, int(mode["snapshots"]), 1, key="wf_snapshots", help="過去の何時点で候補抽出を再現するかを指定します。多いほど時間がかかります。")
        spacing = c2.slider("時点間隔（取引日）", 10, 40, int(mode["spacing"]), 5, key="wf_spacing", help="各再現日の間を何取引日空けるかを指定します。")
        controls = c3.slider("類似非選択銘柄数", 3, 10, int(mode["controls"]), 1, key="wf_controls", help="候補1件と比較する、似ているが選ばれなかった銘柄の最大数です。")
        horizon_values = st.multiselect(
            "評価期間（取引日）",
            list(STAR_OUTCOME_HORIZONS),
            default=list(mode["horizons"]),
            key="wf_horizons",
            help="候補選定後、何取引日目の成績を評価するかを選びます。",
        )
        horizons = tuple(sorted(int(value) for value in horizon_values))
    else:
        snapshots = int(mode["snapshots"])
        spacing = int(mode["spacing"])
        controls = int(mode["controls"])
        horizons = tuple(int(value) for value in mode["horizons"])

    st.caption(
        "類似銘柄は同業種を優先し、時価総額・52週下落率・60日ボラ・PER/PBRの業種比が近い"
        "『その時点で選ばれなかった銘柄』から選びます。通常表示だけではデータ取得・再計算しません。"
    )
    force_recalculate = st.checkbox(
        "保存済み結果を使わず再計算", value=False, key="wf_force_recalculate",
        help="同じ条件の保存済み結果を無視して再計算します。通常はオフの方が高速です。",
    )
    if st.button(
        "ローカル過去データでWalk-Forward検証を実行",
        key="run_walk_forward",
        type="primary",
        disabled=not horizons,
    ):
        data = load_curated_latest(ROOT)
        historical_masters = load_security_master_history(ROOT)
        cfg = load_config(REAL_CONFIG)
        settings = WalkForwardConfig(
            max_snapshots=int(snapshots),
            spacing_trading_days=int(spacing),
            controls_per_event=int(controls),
        )
        data_signature = _walk_forward_data_signature()
        cache_key = walk_forward_cache_key(
            data_signature=data_signature,
            config=cfg,
            settings=settings,
            horizons=horizons,
            app_version=__version__,
        )
        events = None if force_recalculate else load_walk_forward_result(
            WALK_FORWARD_CACHE, cache_key
        )
        if events is not None:
            st.session_state["walk_forward_validation_events"] = events
            st.session_state["walk_forward_validation_horizons"] = horizons
            st.success(
                f"保存済みの同一条件の結果を読み込みました。候補イベント {len(events):,} 件です。"
            )
        else:
            progress_bar = st.progress(0.0)
            progress_text = st.empty()

            def update_walk_forward_progress(info: dict) -> None:
                current = int(info.get("snapshot", 0))
                total = max(int(info.get("total_snapshots", 1)), 1)
                as_of = info.get("as_of")
                as_of_text = pd.Timestamp(as_of).date().isoformat() if as_of is not None else "-"
                progress_bar.progress(min(current / total, 1.0))
                progress_text.caption(
                    f"再現時点 {current}/{total}・基準日 {as_of_text}・"
                    f"{info.get('message', '処理中')}"
                )

            with st.spinner("保存済みローカルデータで過去検証を実行しています…"):
                events = walk_forward_validation(
                    data["companies"], data["prices"], data["financials"], cfg,
                    settings=settings,
                    horizons=horizons,
                    cache_dir=WALK_FORWARD_CACHE,
                    data_signature=f"{data_signature}:{__version__}",
                    progress=update_walk_forward_progress,
                    historical_masters=historical_masters,
                )
                save_walk_forward_result(WALK_FORWARD_CACHE, cache_key, events)
                st.session_state["walk_forward_validation_events"] = events
                st.session_state["walk_forward_validation_horizons"] = horizons
            progress_bar.progress(1.0)
            progress_text.caption("Walk-Forward過去検証が完了しました。")
            if events.empty:
                st.warning("現在ローカルに保持している過去データでは、検証可能な定量候補イベントを作れませんでした。")
            else:
                st.success(f"Walk-Forward検証を完了しました。候補イベント {len(events):,} 件です。")

    events = st.session_state.get("walk_forward_validation_events")
    if not isinstance(events, pd.DataFrame) or events.empty:
        st.info("『実行』を押すと、ローカル保存済みデータの範囲で過去検証を行います。")
        return

    result_horizons = tuple(
        int(value) for value in st.session_state.get(
            "walk_forward_validation_horizons", tuple(STAR_OUTCOME_HORIZONS)
        )
    )
    summary = walk_forward_summary(events, horizons=result_horizons)
    dates = pd.to_datetime(events.get("selection_date"), errors="coerce").dropna()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("候補イベント", f"{len(events):,}件", help=_analysis_help("候補イベント"))
    m2.metric("再現時点", f"{events.get('selection_date', pd.Series(dtype=str)).nunique():,}日", help=_analysis_help("再現時点"))
    m3.metric("検証期間", f"{dates.min().date()} ～ {dates.max().date()}" if not dates.empty else "-", help=_analysis_help("検証期間"))
    coverage = pd.to_numeric(events.get("master_coverage_ratio"), errors="coerce").dropna()
    m4.metric("会社マスター最低カバレッジ", f"{coverage.min() * 100:.1f}%" if not coverage.empty else "-", help=_analysis_help("会社マスター最低カバレッジ"))
    historical_used = events.get("historical_master_available", pd.Series(dtype=bool)).fillna(False).astype(bool)
    if bool(historical_used.any()):
        used_dates = events.loc[historical_used, "master_snapshot_date"].dropna().astype(str)
        st.success(
            f"過去銘柄マスターを {historical_used.sum():,}/{len(events):,} 候補イベントで使用しました。"
            + (f" 使用スナップショット: {used_dates.min()} ～ {used_dates.max()}。" if not used_dates.empty else "")
        )
    else:
        st.warning(
            "評価日以前の過去銘柄マスターがないため、現在マスターで代用しています。"
            "今後のデータ更新ごとに日付別マスターが蓄積されます。"
        )
    missing_master = pd.to_numeric(events.get("missing_master_code_count"), errors="coerce").fillna(0)
    if missing_master.gt(0).any():
        st.warning(
            f"再現時点の観測可能銘柄のうち、最大 {int(missing_master.max()):,} 銘柄が"
            "現在の会社マスターに存在せず、選定対象に含められませんでした。"
        )

    display = summary.copy()
    for col in ["候補平均", "候補プラス率", "類似非選択平均", "選択効果", "選択効果プラス率"]:
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors="coerce") * 100
    st.markdown("#### 現在ルールのWalk-Forward成績")
    _analysis_dataframe(display, width="stretch", hide_index=True)
    chart_cols = [c for c in ["候補平均", "類似非選択平均", "選択効果"] if c in display.columns]
    if chart_cols:
        st.bar_chart(display.set_index("期間")[chart_cols], width="stretch")
    st.caption(
        "選択効果 = 選ばれた候補の実績 − 類似していた非選択銘柄の平均実績。"
        "市場全体が上昇しただけなのか、選択ロジック自体に上乗せ効果があったのかを確認します。"
    )

    attribution = attribution_outcome_summary(events, horizon_days=30)
    if not attribution.empty:
        shown = attribution.copy()
        shown["平均リターン"] = pd.to_numeric(shown["平均リターン"], errors="coerce") * 100
        shown["プラス率"] = pd.to_numeric(shown["プラス率"], errors="coerce") * 100
        st.markdown("#### 外因説明率と30取引日後実績")
        _analysis_dataframe(shown, width="stretch", hide_index=True)
        st.caption(
            "外因説明率は6カ月下落を『市場＋業種』と『企業固有』に分解した記述統計です。"
            "高いほど市場・業種の下落で説明できる割合が大きいことを示しますが、因果関係の証明ではありません。"
        )

    if st.checkbox("Walk-Forwardイベント詳細を表示", value=False, key="wf_details", help="過去の候補を選定日・銘柄単位で確認します。列名にマウスを置くと意味を表示します。"):
        details = events.copy()
        pct_cols = [c for c in details.columns if c.startswith(("return_", "control_return_", "selection_edge_"))]
        for col in pct_cols:
            details[col] = pd.to_numeric(details[col], errors="coerce") * 100
        _analysis_dataframe(details.sort_values(["selection_date", "code"], ascending=[False, True]), width="stretch", hide_index=True)


def render_history_and_validation() -> None:
    st.title("履歴・実績検証")
    st.caption("日次の定量分析と、統合候補一覧で保存された◎☆/◎/○/△/×評価を後から検索します。大量履歴でも反応が落ちにくいよう、必要なセクションだけ遅延読込みします。")

    section = st.segmented_control(
        "履歴表示",
        ["日次分析履歴", "評価履歴", "◎☆実績検証", "Walk-Forward検証"],
        default="日次分析履歴",
        selection_mode="single",
        label_visibility="collapsed",
        help="表示する履歴・検証の種類を切り替えます。通常の切替では外部データを取得しません。",
        key="history_section",
    )
    evaluation_signature = _evaluation_history_signature()
    evaluation = _cached_load_evaluation_history(str(ROOT), evaluation_signature)

    if section == "日次分析履歴":
        _render_history_daily(evaluation_signature)
    elif section == "評価履歴":
        _render_history_evaluations(evaluation)
    elif section == "◎☆実績検証":
        _render_history_star_validation(evaluation)
    else:
        _render_history_walk_forward()

def render_sbi_csv_import() -> None:
    bundle = _bundle_or_none()
    st.subheader("SBI証券スクリーナーCSVの取込")
    st.info("HYPER SBI 2またはSBI証券のスクリーニング結果CSVを読み込み、アプリの候補と突合します。ログイン情報は不要です。")
    uploaded = st.file_uploader("SBI証券から出力したCSV", type=["csv"])
    if uploaded is None:
        st.caption("CSVの列名は自動判定します。UTF-8とShift-JIS（CP932）に対応しています。")
        return
    try:
        result = parse_sbi_screening_csv(uploaded.getvalue())
    except Exception as exc:
        st.error(f"CSVを読み込めませんでした: {exc}")
        return
    rows = result.rows.copy()
    if bundle is not None:
        companies = bundle["data"]["companies"][["code", "name", "market", "sector"]].drop_duplicates("code")
        rows = rows.merge(companies, on="code", how="left", suffixes=("_sbi", "_app"))
        shortlist = st.session_state.get("screen_shortlist", pd.DataFrame())
        candidate_codes = set(shortlist.get("code", pd.Series(dtype=str)).astype(str))
        rows["アプリ候補"] = rows["code"].astype(str).isin(candidate_codes)
    st.success(f"{len(rows):,}銘柄を読み込みました。文字コード: {result.encoding}")
    for warning in result.warnings:
        st.warning(warning)
    _analysis_dataframe(rows, width="stretch", hide_index=True)
    st.download_button("突合結果CSVをダウンロード", data=rows.to_csv(index=False).encode("utf-8-sig"), file_name="sbi_screening_matched.csv", mime="text/csv")

def _candidate_records(matches: pd.DataFrame, max_items: int = 15) -> list[dict]:
    keep = [c for c in ["code", "display_code", "name", "market", "sector", "match_type", "search_score"] if c in matches.columns]
    return matches.loc[:, keep].head(max_items).to_dict(orient="records")


def _candidate_label(item: dict) -> str:
    market = str(item.get("market", "")).strip()
    match_type = str(item.get("match_type", "")).strip()
    suffix = " / ".join(v for v in [market, match_type] if v)
    return f"{item.get('display_code', '')}  {item.get('name', '')}" + (f"  [{suffix}]" if suffix else "")


@st.dialog("検索候補を選択", width="large")
def _choose_stock_candidate_dialog() -> None:
    candidates = st.session_state.get("stock_search_candidates", [])
    query = str(st.session_state.get("stock_search_candidate_query", ""))
    if not candidates:
        st.info("候補がありません。")
        return
    st.write(f"「{query}」に複数の候補が見つかりました。表示する銘柄を選択してください。")
    labels = [_candidate_label(item) for item in candidates]
    selected_label = st.selectbox(
        "候補",
        labels,
        index=None,
        key="stock_candidate_dialog_choice",
        help="候補を選択するまでは個別銘柄を自動表示しません。",
    )
    left, right = st.columns(2)
    if left.button("選択した銘柄を表示", type="primary", width="stretch", disabled=selected_label is None):
        idx = labels.index(selected_label)
        selected = candidates[idx]
        st.session_state["stock_selected_code"] = str(selected["code"])
        st.session_state["stock_search_candidates"] = []
        st.session_state["stock_search_candidate_query"] = ""
        st.rerun()
    if right.button("キャンセル", width="stretch"):
        st.session_state["stock_search_candidates"] = []
        st.session_state["stock_search_candidate_query"] = ""
        st.rerun()


def _seed_stock_search_from_query_params() -> None:
    """Initialize a new stock-search session from a history-link query parameter."""
    requested = str(st.query_params.get("code", "")).strip()
    if not requested or st.session_state.get("_stock_query_param_code") == requested:
        return
    st.session_state["_stock_query_param_code"] = requested
    st.session_state["stock_query"] = display_tse_code(requested)
    st.session_state["stock_selected_code"] = requested
    st.session_state["stock_search_candidates"] = []
    st.session_state["stock_search_candidate_query"] = ""
    st.session_state["stock_search_no_match"] = ""


def render_stock_search() -> None:
    bundle = _bundle_or_none()
    if bundle is None:
        st.warning("先に「データ更新」タブで実データを取得してください。")
        return
    data = bundle["data"]
    _seed_stock_search_from_query_params()
    st.subheader("会社名・証券コードで検索")
    st.caption("企業名は部分一致・表記ゆれ・軽い入力ミスを含むあいまい検索に対応します。複数候補の場合は選択画面を表示します。")

    with st.form("stock_search_form", clear_on_submit=False):
        query = st.text_input(
            "会社名または証券コード",
            placeholder="例: トヨタ / とよた / 7203 / 三菱UFJ",
            key="stock_query",
            help="企業名の一部、読み方、4桁・5桁の証券コードで検索できます。複数候補は選択画面で確認します。",
        )
        submitted = st.form_submit_button("検索", type="primary")

    requested_code = str(st.session_state.get("stock_selected_code", ""))
    if submitted:
        st.session_state["stock_selected_code"] = ""
        st.session_state["stock_search_candidates"] = []
        st.session_state["stock_search_candidate_query"] = ""
        if query.strip():
            matches = search_companies(data["companies"], query, limit=50)
            if matches.empty:
                st.session_state["stock_search_no_match"] = query.strip()
            elif len(matches) == 1:
                st.session_state["stock_selected_code"] = str(matches.iloc[0]["code"])
                st.session_state["stock_search_no_match"] = ""
            else:
                # Never silently use the first fuzzy match. The user must choose.
                st.session_state["stock_search_candidates"] = _candidate_records(matches)
                st.session_state["stock_search_candidate_query"] = query.strip()
                st.session_state["stock_search_no_match"] = ""
        requested_code = str(st.session_state.get("stock_selected_code", ""))

    pending_candidates = st.session_state.get("stock_search_candidates", [])
    if pending_candidates:
        _choose_stock_candidate_dialog()
        st.info(f"候補が {len(pending_candidates)} 件あります。候補選択後に個別銘柄を表示します。")
        return

    no_match = str(st.session_state.get("stock_search_no_match", ""))
    if no_match and submitted:
        st.warning(f"「{no_match}」に近い銘柄が見つかりません。企業名の一部または証券コードで再検索してください。")
        return

    selected_code = str(st.session_state.get("stock_selected_code", ""))
    if not selected_code:
        return

    detail = stock_detail(data, selected_code)
    company = detail["company"]
    metrics = detail["metrics"]
    prices = detail["prices"].copy()
    financials = detail["financials"].copy()
    upcoming = detail["earnings"].copy()

    st.markdown(
        f"### {display_tse_code(company['code'])} {company['name']}　"
        f"`{company.get('market', '')}` / `{company.get('sector', '')}`"
    )
    prepared = bundle.get("prepared", pd.DataFrame())
    external_quote = None
    external_history = None
    external_quote_error = None
    try:
        with st.spinner("最新の外部株価と日足トレンドを確認しています…"):
            external_quote = _latest_external_quote(str(company["code"]))
            external_history = _latest_external_history(str(company["code"]))
    except Exception as exc:
        external_quote_error = str(exc)
    if external_quote:
        quote_cols = st.columns(4)
        latest_price = float(external_quote["price"])
        change = external_quote.get("change")
        change_pct = external_quote.get("change_pct")
        quote_cols[0].metric("外部取得の最新株価", f"¥{latest_price:,.1f}", f"{change:+,.1f} ({change_pct:+.2%})" if change is not None and change_pct is not None else None, help="Yahoo Finance系から取得した参考用の最新株価です。注文前にはSBI証券で確認してください。")
        quote_cols[1].metric("J-Quants分析終値", f"¥{_format_number(metrics.get('close'))}", help=_analysis_help("分析終値"))
        quote_cols[2].metric("外部株価の時刻", str(external_quote.get("market_time", "-"))[:19].replace("T", " "), help="外部の株価情報が示す市場時刻です。遅延している場合があります。")
        quote_cols[3].metric("外部データ元", "Yahoo Finance系", help="最新表示の取得元です。J-Quantsの分析スナップショットとは分離されています。")
        st.caption("外部取得値はYahoo Financeをyfinance経由で参照した非公式・遅延の可能性がある表示です。J-Quantsの分析スナップショットには混入させず、注文前にはSBI証券の現在値で再確認してください。")
    else:
        st.info("外部の最新株価を取得できなかったため、J-Quantsの分析終値を表示しています。" + (f" 詳細: {external_quote_error}" if external_quote_error else ""))
    cols = st.columns(7)
    metric_defs = [("終値", "close", f"¥{_format_number(metrics.get('close'))}"), ("52週高値比", "drawdown_52w", _format_pct(metrics.get("drawdown_52w"))), ("6か月騰落率", "return_6m", _format_pct(metrics.get("return_6m"))), ("市場比較相対", "relative_return_6m", _format_pct(metrics.get("relative_return_6m"))), ("売上CAGR", "sales_cagr_3y", _format_pct(metrics.get("sales_cagr_3y"))), ("営業利益率", "operating_margin", _format_pct(metrics.get("operating_margin"))), ("自己資本比率", "equity_ratio", _format_pct(metrics.get("equity_ratio")))]
    for col, (name, metric_name, value) in zip(cols, metric_defs):
        _render_reference_metric(col, name, _metric_reference_label(prepared, company, metric_name), value, help_text=METRIC_DESCRIPTIONS.get(metric_name))
    st.caption("括弧内は同じ業種の取得済み銘柄が5社以上ある場合は同業中央値、それ以外は一般的な目安です。業種や企業の成長段階により適正値は異なります。")
    source = str(metrics.get("benchmark_source", "none"))
    label = str(metrics.get("benchmark_label", "市場比較なし"))
    if source == "topix_etf_proxy":
        st.warning(f"市場比較: {label} の調整後終値を代理利用しています。正式TOPIXではありません。")
    elif source == "official_topix":
        st.caption("市場比較: 正式TOPIX")
    else:
        st.info("市場比較データがないため、相対騰落率は計算していません。")

    st.markdown("#### 配当情報")
    dividend_per_share = pd.to_numeric(
        pd.Series([metrics.get("forecast_annual_dividend_per_share")]), errors="coerce"
    ).iloc[0]
    dividend_yield = pd.to_numeric(
        pd.Series([metrics.get("forecast_dividend_yield")]), errors="coerce"
    ).iloc[0]
    payout_ratio = pd.to_numeric(
        pd.Series([metrics.get("payout_ratio")]), errors="coerce"
    ).iloc[0]
    dividend_change = pd.to_numeric(
        pd.Series([metrics.get("forecast_dividend_change_rate")]), errors="coerce"
    ).iloc[0]
    jq_close = pd.to_numeric(pd.Series([metrics.get("close")]), errors="coerce").iloc[0]
    yield_price = float(external_quote["price"]) if external_quote and external_quote.get("price") else jq_close
    yield_price_source = "外部最新株価" if external_quote and external_quote.get("price") else "J-Quants終値"
    if pd.isna(dividend_yield) and not pd.isna(dividend_per_share) and not pd.isna(yield_price) and float(yield_price) > 0:
        dividend_yield = float(dividend_per_share) / float(yield_price)
    div_cols = st.columns(4)
    dividend_metric_defs = [("1株当たり予想年間配当", "forecast_annual_dividend_per_share", f"¥{_format_number(dividend_per_share, 1)}" if not pd.isna(dividend_per_share) else "-"), ("予想配当利回り", "forecast_dividend_yield", _format_pct(dividend_yield)), ("予想配当性向", "payout_ratio", _format_pct(payout_ratio)), ("予想増配・減配率", "forecast_dividend_change_rate", _format_pct(dividend_change))]
    for col, (name, metric_name, value) in zip(div_cols, dividend_metric_defs):
        _render_reference_metric(col, name, _metric_reference_label(prepared, company, metric_name), value, help_text=METRIC_DESCRIPTIONS.get(metric_name))
    if not pd.isna(dividend_yield):
        st.caption(f"予想配当利回りは {yield_price_source}（¥{float(yield_price):,.1f}）を基準に表示しています。")

    detail_shares = int(
        st.number_input(
            "保有株数",
            min_value=1,
            max_value=1_000_000,
            value=int(st.session_state.get("detail_dividend_shares", 100)),
            step=100,
            key="detail_dividend_shares",
            help="1株当たり配当から、税引前・概算税引後の年間受取額を計算します。",
        )
    )
    if not pd.isna(dividend_per_share):
        gross_dividend = float(dividend_per_share) * detail_shares
        taxable_after_tax = gross_dividend * (1 - DIVIDEND_WITHHOLDING_RATE)
        close_value = yield_price
        investment = float(close_value) * detail_shares if not pd.isna(close_value) else float("nan")
        amount_cols = st.columns(4)
        amount_cols[0].metric("年間配当（税引前）", f"¥{gross_dividend:,.0f}", help="1株当たり予想年間配当×入力した保有株数です。会社予想は変更される場合があります。")
        amount_cols[1].metric("課税口座の概算受取額", f"¥{taxable_after_tax:,.0f}", help="税引前配当から20.315%を差し引いた概算です。実際の税額とは異なる場合があります。")
        amount_cols[2].metric("NISAの概算受取額", f"¥{gross_dividend:,.0f}", help="NISA口座で国内配当が非課税となる前提の概算です。受取方式などの適用条件を確認してください。")
        amount_cols[3].metric(
            "概算投資額",
            f"¥{investment:,.0f}" if not pd.isna(investment) else "-",
            help="表示株価×入力した株数で計算した参考金額です。手数料や実際の約定価格は含みません。",
        )
        st.caption(
            f"配当データ: {metrics.get('dividend_forecast_source', '-')} / "
            f"配当基準日: {str(metrics.get('dividend_disclosure_date', '-'))[:10]}。"
            "課税口座は20.315%を単純控除した概算です。実際の税額は口座区分や申告方法で異なります。"
        )
    else:
        st.info("取得済み決算サマリーに利用可能な年間配当情報がありません。")

    # Human decision support: organize evidence without claiming that a profit is certain.
    try:
        decision_analyst = _latest_analyst_snapshot(str(company["code"]))
    except Exception:
        decision_analyst = {}
    benchmark_available = str(metrics.get("benchmark_source", "none")) in {"official_topix", "topix_etf_proxy"}
    historical_trend_snapshot = build_price_trend_snapshot(prices)
    if external_history is not None and not external_history.empty:
        trend_transition = build_trend_transition(external_history, lookback_days=90)
        trend_snapshot = trend_transition["current"]
        trend_data_label = "外部最新日足（Yahoo Finance系）"
    else:
        trend_transition = {
            "previous_state": "比較不能",
            "current_state": historical_trend_snapshot.get("trend_state", "データ不足"),
            "transition_state": "J-Quants基準日のみ",
            "escaped_downtrend": False,
            "summary": "外部最新日足を取得できず、J-Quants分析基準日の履歴で判定しています。",
        }
        trend_snapshot = historical_trend_snapshot
        trend_data_label = "J-Quants分析基準日"
    readiness_metrics = dict(metrics)
    readiness_metrics["forecast_dividend_yield"] = dividend_yield
    readiness = build_buy_readiness(
        readiness_metrics,
        analyst=decision_analyst,
        external_quote_available=bool(external_quote),
        benchmark_available=benchmark_available,
        trend=trend_snapshot,
    )

    intuitive_signal = build_intuitive_signal(readiness, trend_transition)
    st.markdown("## 購入判断の整理")
    st.markdown(f"### {intuitive_signal['symbol']} {intuitive_signal['label']}")
    st.caption(intuitive_signal["detail"])
    if intuitive_signal.get("star"):
        st.success("☆ 主要な財務・業績・トレンド確認項目がすべて良好です。ただし、未取得情報や将来の悪材料がないことを保証するものではありません。")
    level = readiness["decision_level"]
    if level == "consider":
        st.success(f"**現在の整理結果：{readiness['decision']}** — {readiness['reason']}")
    elif level == "research":
        st.warning(f"**現在の整理結果：{readiness['decision']}** — {readiness['reason']}")
    else:
        st.error(f"**現在の整理結果：{readiness['decision']}** — {readiness['reason']}")
    st.caption("これは買い推奨や利益保証ではありません。定量データと確認状況を整理し、見落としを減らすための判断補助です。")

    summary_cols = st.columns(4)
    summary_cols[0].metric("定量根拠の充足度", f"{readiness['evidence_score']}%", help="利用可能な定量項目のうち、買付検討に有利な条件がどの程度揃っているかを重み付きで表した参考値です。将来の利益確率ではありません。")
    summary_cols[1].metric("有利な材料", f"{len(readiness['positives'])}件", help="現在の取得済みデータで、買付検討を支える方向に働く確認項目数です。")
    summary_cols[2].metric("注意・不足", f"{len(readiness['warnings'])}件", help="データ不足や追加の人手確認が必要な項目数です。")
    summary_cols[3].metric("反対材料", f"{len(readiness['failures'])}件", help="現在の投資仮説に反する、または買付を止める方向の項目数です。")

    current_price_for_plan = float(external_quote["price"]) if external_quote and external_quote.get("price") else (float(jq_close) if not pd.isna(jq_close) else 0.0)
    entry_guidance = build_entry_price_guidance(current_price_for_plan, trend_snapshot, trend_transition)

    st.markdown("### 株価トレンドと売買タイミング")
    st.caption(f"トレンド判定データ: {trend_data_label}")
    transition_cols = st.columns(4)
    transition_cols[0].metric("約3カ月前", trend_transition.get("previous_state", "-"), help="最新外部日足から約90日前までの履歴で計算したトレンド状態です。")
    transition_cols[1].metric("現在", trend_transition.get("current_state", "-"), help="取得可能な最新の日足系列によるトレンド状態です。")
    transition_cols[2].metric("トレンド変化", trend_transition.get("transition_state", "-"), help="3カ月前の状態と現在の状態を比較し、下降継続・底打ち兆候・下降脱出・上昇転換を整理します。")
    transition_cols[3].metric("下降トレンド脱出", "可能性あり" if trend_transition.get("escaped_downtrend") else "未確認", help="過去が下降基調で、現在のトレンドスコアが中立以上へ改善した場合に表示します。")
    if trend_transition.get("escaped_downtrend"):
        st.success(trend_transition.get("summary", "下降トレンドから改善しています。"))
    else:
        st.info(trend_transition.get("summary", "トレンド変化を確認してください。"))

    st.markdown("#### 株価・移動平均線グラフ")
    trend_chart_history = external_history if external_history is not None and not external_history.empty else prices
    _render_trend_price_chart(
        trend_chart_history,
        entry_guidance=entry_guidance,
        title=f"{display_tse_code(company['code'])} {company['name']} — 株価と20日・50日・200日移動平均線",
    )

    trend_cols = st.columns(6)
    trend_cols[0].metric("トレンド判定", trend_snapshot.get("trend_state", "データ不足"), help="20日・50日・200日移動平均線、直近騰落率、RSIなどから現在の方向性を整理した参考判定です。")
    trend_cols[1].metric("20日線", f"¥{trend_snapshot['sma20']:,.1f}" if trend_snapshot.get("sma20") is not None else "-", help="短期の平均的な株価水準です。現在値が上なら短期的に強く、下なら弱い傾向です。")
    trend_cols[2].metric("50日線", f"¥{trend_snapshot['sma50']:,.1f}" if trend_snapshot.get("sma50") is not None else "-", help="約2～3か月の中期的な平均株価です。")
    trend_cols[3].metric("200日線", f"¥{trend_snapshot['sma200']:,.1f}" if trend_snapshot.get("sma200") is not None else "-", help="長期トレンドを確認する代表的な移動平均線です。")
    trend_cols[4].metric("RSI(14)", f"{trend_snapshot['rsi14']:.1f}" if trend_snapshot.get("rsi14") is not None else "-", help="0～100で短期の過熱感を示します。一般に70以上は買われ過ぎ、30以下は売られ過ぎの目安ですが、それだけで反転は確定しません。")
    trend_cols[5].metric("出来高20日比", f"{trend_snapshot['volume_ratio_20d']:.2f}倍" if trend_snapshot.get("volume_ratio_20d") is not None else "-", help="当日の出来高を直近20日の平均出来高と比較します。価格変化を伴う出来高増加はトレンド確認材料です。")

    trend_left, trend_right = st.columns(2)
    with trend_left:
        st.markdown("#### 買いタイミングを支える兆候")
        if trend_snapshot.get("signals"):
            for text in trend_snapshot["signals"]:
                st.write(f"✅ {text}")
        else:
            st.info("現在の株価履歴から明確な上昇・反転兆候は検出されませんでした。")
    with trend_right:
        st.markdown("#### 待つ・売る判断につながる兆候")
        if trend_snapshot.get("warnings"):
            for text in trend_snapshot["warnings"]:
                st.write(f"⚠️ {text}")
        else:
            st.success("主要なトレンド警告は検出されませんでした。")

    st.markdown("#### 売却・撤退条件の例")
    st.caption("以下は自動注文条件ではありません。購入前に自分の撤退ルールとして選び、決算・事業仮説と併せて判断します。")
    exit_rows = [
        {"種類": "価格", "確認条件": "終値が50日移動平均線を明確に下回り、数日戻せない", "意味": "中期上昇トレンドが崩れた可能性"},
        {"種類": "トレンド", "確認条件": "20日線が50日線を下抜け、両方が下向き", "意味": "下落トレンドへの転換に注意"},
        {"種類": "業績", "確認条件": "下方修正、営業赤字、営業CFの継続悪化", "意味": "当初の投資仮説が崩れた可能性"},
        {"種類": "配当", "確認条件": "減配発表または配当性向の急上昇", "意味": "配当の持続性低下"},
        {"種類": "過熱", "確認条件": "RSIが75超かつ急騰・大出来高", "意味": "一部利益確定を検討する材料"},
        {"種類": "損失管理", "確認条件": "事前に決めた最大損失額へ到達", "意味": "感情ではなく資金管理を優先"},
    ]
    _analysis_dataframe(pd.DataFrame(exit_rows), width="stretch", hide_index=True)

    status_icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "unknown": "❓"}
    check_rows = [{
        "判定": status_icon.get(item["status"], ""),
        "確認項目": item["label"],
        "現在の内容": item["detail"],
    } for item in readiness["checks"]]
    _analysis_dataframe(pd.DataFrame(check_rows), width="stretch", hide_index=True)

    left_decision, right_decision = st.columns(2)
    with left_decision:
        st.markdown("### 買付を支える材料")
        if readiness["positives"]:
            for item in readiness["positives"]:
                st.write(f"✅ **{item['label']}** — {item['detail']}")
        else:
            st.info("現在のデータでは明確な有利材料を確認できません。")
    with right_decision:
        st.markdown("### 見送り・再確認材料")
        combined_cautions = readiness["failures"] + readiness["warnings"]
        if combined_cautions:
            for item in combined_cautions:
                icon = "❌" if item["status"] == "fail" else "⚠️" if item["status"] == "warn" else "❓"
                st.write(f"{icon} **{item['label']}** — {item['detail']}")
        else:
            st.success("定量項目上の大きな注意材料は検出されませんでした。")

    st.markdown("### 外的要因レビュー")
    code_key = display_tse_code(company["code"])
    try:
        external_review = load_external_event_review(
            EXTERNAL_REVIEW_DIR, code_key, str(company["name"])
        )
        review_load_error = ""
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        external_review = {
            "code": code_key,
            "name": str(company["name"]),
            "evaluation_date": "",
            "reviewer": "",
            "decline_factor": "",
            "primary_source": {},
            "assessment": {},
            "recovery_catalyst_and_deadline": "",
            "invalidation_conditions": "",
            "structured_invalidation_conditions": [],
            "approval_status": "pending",
        }
        review_load_error = str(exc)
    if review_load_error:
        st.error("保存済み外的要因レビューを読み込めませんでした。安全側に倒して pending として扱います。 " + review_load_error)
    source_doc = external_review.get("primary_source") if isinstance(external_review.get("primary_source"), dict) else {}
    assessment_doc = external_review.get("assessment") if isinstance(external_review.get("assessment"), dict) else {}
    status_options = ["pending", "approved", "rejected"]
    saved_status = str(external_review.get("approval_status", "pending"))
    if saved_status not in status_options:
        saved_status = "pending"
    # Keep the structured data editor outside st.form. Streamlit forms can submit
    # the editor's previous value when a cell edit and submit happen in the same
    # browser interaction. A normal container lets each editor commit trigger a
    # rerun before the save button is processed, so the saved value is current.
    with st.container():
        st.caption("各入力項目は任意です。薄い例文を参考に必要な範囲だけ記録してください。人が承認ステータスを approved にして保存したレビューだけが注文直前プレビューの外的要因レビュー条件を満たします。")
        with st.expander("入力例・ガイドライン", expanded=False):
            st.markdown("**下落要因**: 何が株価下落を起こしたと考えるか。事実と推測を分ける。\n\n**一次資料**: 決算短信・適時開示・有価証券報告書など、後から再確認できる情報があれば記録する。\n\n**一時性確率**: 1.0に近いほど一過性と判断。**構造リスク**: 1.0に近いほど長期問題を警戒。\n\n**回復カタリスト**: 何を・いつまでに確認するか。**仮説無効化条件**: どの事実が出たら見方を撤回するか。")
        identity_cols = st.columns(4)
        identity_cols[0].text_input("銘柄コード", value=code_key, disabled=True)
        identity_cols[1].text_input("企業名", value=str(company["name"]), disabled=True)
        evaluation_date = identity_cols[2].text_input("評価日", value=str(external_review.get("evaluation_date", "")), placeholder="YYYY-MM-DD")
        reviewer = identity_cols[3].text_input("レビュアー", value=str(external_review.get("reviewer", "")), placeholder="例: hnama（任意）")
        decline_factor = st.text_area("下落要因", value=str(external_review.get("decline_factor", "")), height=100, placeholder="例: 原材料価格上昇と一時的な需給悪化。会社業績そのものの構造悪化かは未確認。", help="任意項目です。株価下落の主因を、推測と一次資料で確認できた事実を分けて記載します。")
        st.markdown("##### 一次資料")
        src1, src2 = st.columns(2)
        document_id = src1.text_input("文書ID", value=str(source_doc.get("document_id", "")), placeholder="例: 2026年8月 第1四半期決算短信（任意）", help="任意項目です。TDnet、EDINET、企業IR等で後から同じ文書を特定できる識別子です。")
        published_at = src2.text_input("公開日時", value=str(source_doc.get("published_at", "")), placeholder="例: 2026-08-07 15:30（任意）")
        source_location = st.text_input("該当ページ・箇所", value=str(source_doc.get("location", "")), placeholder="例: 3ページ『業績予想』欄（任意）", help="任意項目です。ページ番号、章、表題など、根拠箇所を再確認できる情報です。")
        source_summary = st.text_area("引用ではなく要約", value=str(source_doc.get("summary", "")), height=100, placeholder="例: 通期予想は据え置き。一時的なコスト増を会社が説明している。（任意）", help="任意項目です。一次資料の内容を自分の言葉で要約します。長い引用文は保存しません。")
        st.markdown("##### 評価（0 = 低い / 1 = 高い）")
        score_cols = st.columns(4)
        external_factor_degree = score_cols[0].slider("外的要因度", 0.0, 1.0, float(assessment_doc.get("external_factor_degree", 0.5)), 0.05, help="業績そのものより市場・制度・需給など外部要因が下落へ寄与している程度です。")
        temporariness_probability = score_cols[1].slider("一時性確率", 0.0, 1.0, float(assessment_doc.get("temporariness_probability", 0.5)), 0.05, help="下落要因が恒久的ではなく、時間とともに解消する可能性の主観評価です。")
        catalyst_probability = score_cols[2].slider("カタリスト確率", 0.0, 1.0, float(assessment_doc.get("catalyst_probability", 0.5)), 0.05, help="想定した回復材料が期限内に実現する可能性の主観評価です。")
        structural_risk = score_cols[3].slider("構造リスク", 0.0, 1.0, float(assessment_doc.get("structural_risk", 0.5)), 0.05, help="競争力低下、需要縮小、財務悪化など長期的な問題である可能性です。高いほど注意します。")
        recovery_catalyst = st.text_area("回復カタリストと期限", value=str(external_review.get("recovery_catalyst_and_deadline", "")), height=100, placeholder="例: 次回決算までに粗利率の回復を確認。期限: 2026年11月決算発表（任意）", help="任意項目です。何が起きれば株価・業績の再評価につながるかと、確認期限を具体的に記載します。")
        invalidation = st.text_area("仮説無効化条件", value=str(external_review.get("invalidation_conditions", "")), height=100, placeholder="例: 通期会社予想の下方修正、営業CFの継続悪化、減配発表のいずれか（任意）", help="自由記述は自動判定せず『要目視確認』として表示します。財務指標で表せる条件は下の構造化条件にも登録してください。")
        st.markdown("##### 財務指標で自動照合する仮説無効化条件")
        st.caption("例: 営業利益率が8%未満になったら仮説を無効化 → 『営業利益率 / < / 8』。閾値の%項目は 8 と入力すると8%として扱います。行は必要な分だけ追加できます。")
        metric_label_by_key = {key: spec["label"] for key, spec in METRIC_DEFINITIONS.items()}
        metric_key_by_label = {label: key for key, label in metric_label_by_key.items()}
        structured_saved = normalize_structured_conditions(external_review.get("structured_invalidation_conditions", []))
        structured_rows = [{
            "有効": bool(item.get("enabled", True)),
            "指標": metric_label_by_key.get(str(item.get("metric", "")), str(item.get("metric", ""))),
            "比較": str(item.get("operator", "<")),
            "閾値": float(item.get("threshold", 0.0)),
            "メモ": str(item.get("note", "")),
        } for item in structured_saved]
        # Do not use st.data_editor for these rows. Its grid edit event and a Save
        # button click can arrive on different reruns, especially when multiple rows
        # are edited. That allowed row 1 to commit while row 2 still exposed the
        # previous value. Each condition now uses ordinary keyed widgets, so every
        # row has an independent value in st.session_state and Save reads all rows
        # from that single authoritative state.
        structured_draft_key = f"structured_invalidation_rows_{code_key}"
        structured_counter_key = f"structured_invalidation_next_row_{code_key}"
        if structured_draft_key not in st.session_state:
            st.session_state[structured_draft_key] = [
                {**row, "_row_id": f"saved_{idx}"}
                for idx, row in enumerate(structured_rows)
            ]
            st.session_state[structured_counter_key] = len(structured_rows)

        def _structured_widget_key(row_id: str, field: str) -> str:
            return f"structured_invalidation_{code_key}_{row_id}_{field}"

        def _drop_structured_widget_state(row_id: str) -> None:
            for field in ("enabled", "metric", "operator", "threshold", "note"):
                st.session_state.pop(_structured_widget_key(row_id, field), None)

        structured_conditions_input = []
        rows_to_delete = []
        for row in list(st.session_state[structured_draft_key]):
            row_id = str(row["_row_id"])
            enabled_key = _structured_widget_key(row_id, "enabled")
            metric_key = _structured_widget_key(row_id, "metric")
            operator_key = _structured_widget_key(row_id, "operator")
            threshold_key = _structured_widget_key(row_id, "threshold")
            note_key = _structured_widget_key(row_id, "note")
            if enabled_key not in st.session_state:
                st.session_state[enabled_key] = bool(row.get("有効", True))
            if metric_key not in st.session_state:
                st.session_state[metric_key] = str(row.get("指標", next(iter(metric_key_by_label))))
            if operator_key not in st.session_state:
                st.session_state[operator_key] = str(row.get("比較", "<"))
            if threshold_key not in st.session_state:
                st.session_state[threshold_key] = format_threshold_input_value(row.get("閾値", 0.0))
            if note_key not in st.session_state:
                st.session_state[note_key] = str(row.get("メモ", ""))

            row_cols = st.columns([0.7, 2.0, 1.0, 1.2, 2.4, 0.7])
            enabled_value = row_cols[0].checkbox("有効", key=enabled_key, label_visibility="collapsed")
            metric_value = row_cols[1].selectbox(
                "指標", list(metric_key_by_label.keys()), key=metric_key, label_visibility="collapsed"
            )
            operator_value = row_cols[2].selectbox(
                "比較", ["<", "<=", ">", ">=", "=="], key=operator_key, label_visibility="collapsed"
            )
            threshold_value = row_cols[3].text_input(
                "閾値",
                key=threshold_key,
                label_visibility="collapsed",
                placeholder="例: 50 / 7.5 / 8.25",
                help="数値を入力します。不要な小数0は表示しません。例: 50、7.5、8.25",
            )
            note_value = row_cols[4].text_input(
                "メモ", key=note_key, label_visibility="collapsed", placeholder="例: 次回決算で確認"
            )
            if row_cols[5].button("削除", key=f"delete_structured_invalidation_{code_key}_{row_id}"):
                rows_to_delete.append(row_id)
            structured_conditions_input.append({
                "有効": enabled_value,
                "指標": metric_value,
                "比較": operator_value,
                "閾値": threshold_value,
                "メモ": note_value,
                "_row_id": row_id,
            })

        if rows_to_delete:
            st.session_state[structured_draft_key] = [
                row for row in st.session_state[structured_draft_key]
                if str(row["_row_id"]) not in rows_to_delete
            ]
            for row_id in rows_to_delete:
                _drop_structured_widget_state(row_id)
            st.rerun()

        if st.button("条件を追加", key=f"add_structured_invalidation_{code_key}"):
            next_row = int(st.session_state.get(structured_counter_key, 0))
            new_row_id = f"new_{next_row}"
            st.session_state[structured_counter_key] = next_row + 1
            st.session_state[structured_draft_key].append({
                "有効": True,
                "指標": next(iter(metric_key_by_label)),
                "比較": "<",
                "閾値": 0.0,
                "メモ": "",
                "_row_id": new_row_id,
            })
            st.rerun()
        approval_status = st.selectbox("承認ステータス", status_options, index=status_options.index(saved_status), help="approved のみ注文直前プレビューの必要条件を満たします。pending / rejected は必ずブロックします。")
        save_review = st.button(
            "外的要因レビューを保存",
            type="primary",
            key=f"save_external_event_review_{code_key}",
        )
    if save_review:
        # Serialize the complete set of current row widgets in one pass. Each row is
        # backed by its own Streamlit widget state, so a single Save captures row 1,
        # row 2, ... without depending on data_editor's grid commit timing.
        structured_conditions = structured_conditions_from_ui_rows(structured_conditions_input)
        review_document = {
            "schema_version": "1.0",
            "code": code_key,
            "name": str(company["name"]),
            "evaluation_date": evaluation_date.strip(),
            "reviewer": reviewer.strip(),
            "decline_factor": decline_factor.strip(),
            "primary_source": {
                "document_id": document_id.strip(),
                "published_at": published_at.strip(),
                "location": source_location.strip(),
                "summary": source_summary.strip(),
            },
            "assessment": {
                "external_factor_degree": external_factor_degree,
                "temporariness_probability": temporariness_probability,
                "catalyst_probability": catalyst_probability,
                "structural_risk": structural_risk,
            },
            "recovery_catalyst_and_deadline": recovery_catalyst.strip(),
            "invalidation_conditions": invalidation.strip(),
            "structured_invalidation_conditions": structured_conditions,
            "approval_status": approval_status,
        }
        saved_path = save_external_event_review(EXTERNAL_REVIEW_DIR, review_document)
        external_review = load_external_event_review(EXTERNAL_REVIEW_DIR, code_key, str(company["name"]))
        # Refresh only the draft metadata after saving; widget values remain the
        # authoritative edited values until the security is changed/reloaded.
        st.session_state[structured_draft_key] = [
            {
                "有効": bool(item.get("有効", True)),
                "指標": str(item.get("指標", "")),
                "比較": str(item.get("比較", "<")),
                "閾値": float(item.get("閾値", 0.0)),
                "メモ": str(item.get("メモ", "")),
                "_row_id": str(item.get("_row_id", f"saved_{idx}")),
            }
            for idx, item in enumerate(structured_conditions_input)
        ]
        st.success(f"外的要因レビューを保存しました: {saved_path.relative_to(ROOT)}")
    review_status = str(external_review.get("approval_status", "pending"))
    if external_event_review_is_approved(external_review):
        st.success("外的要因レビュー: approved — 人による承認済みレビューとして条件を満たしています。")
        optional_blanks = approval_completeness_issues(external_review)
        if optional_blanks:
            st.caption("未入力の任意項目: " + " / ".join(optional_blanks) + "。必要に応じて追記できます。")
    elif review_status == "rejected":
        st.error("外的要因レビュー: rejected — この銘柄は注文直前プレビューへ進めません。")
    else:
        st.warning("外的要因レビュー: pending — 承認されるまで注文直前プレビューへ進めません。")

    st.markdown("#### 仮説無効化条件の最新財務データ照合")
    invalidation_result = evaluate_hypothesis_invalidation(external_review, metrics)
    if invalidation_result["status"] == "breached":
        st.error("🚨 保存済みの仮説無効化条件に最新財務データが抵触しています。投資仮説を再確認してください。")
        for item in invalidation_result["breached"]:
            st.write(f"❌ {item['label']}: 現在 {item['actual_display']} / 無効化条件 {item['operator']} {item['threshold_display']}")
    elif invalidation_result["status"] == "unevaluable":
        st.warning("⚠️ 一部の構造化条件は最新財務データで評価できません。要目視確認です。")
        for item in invalidation_result["unevaluable"]:
            st.write(f"⚠️ {item['label']}: 最新値を取得できません")
    elif invalidation_result["status"] == "clear":
        st.success("✅ 構造化した仮説無効化条件には、最新の取得済み財務データは抵触していません。")
    elif invalidation_result["status"] == "manual_review":
        st.info("👁 自由記述の仮説無効化条件があります。自動判定対象外のため要目視確認です。")
    else:
        st.caption("構造化した仮説無効化条件は未登録です。")
    if invalidation_result.get("manual_review_required"):
        st.warning("👁 自由記述条件は要目視確認: " + invalidation_result.get("free_text", ""))

    st.markdown("### 注文前に人が確認する項目")
    manual_items = {
        "latest_ir": "最新の決算短信・適時開示を確認した",
        "external_cause": "株価下落の主因が一時的な外的要因だと一次資料で確認した",
        "catalyst": "回復カタリストと想定時期を説明できる",
        "failure_case": "投資仮説が崩れたと判断する条件を決めた",
        "sbi_quote": "SBI証券で現在値・板・最新ニュースを確認した",
        "earnings_risk": "次回決算日と決算跨ぎのリスクを確認した",
    }
    manual_results = {}
    manual_cols = st.columns(2)
    for idx, (key, label_text) in enumerate(manual_items.items()):
        with manual_cols[idx % 2]:
            manual_results[key] = st.checkbox(
                label_text,
                key=f"decision_{code_key}_{key}",
                help="自動判定できない重要事項です。実際に確認した場合だけチェックしてください。",
            )
    manual_done = sum(bool(v) for v in manual_results.values())
    if manual_done == len(manual_results):
        st.success("注文前の人手確認がすべて完了しています。最終的な価格・数量・損失許容額を確認してください。")
    else:
        st.warning(f"注文前確認は {manual_done}/{len(manual_results)} 件完了です。未確認のまま『今が買い』とは判断しないでください。")

    run_status = _read_json(REAL_OUTPUT / "run_status_latest.json")
    runtime_cfg = load_config(REAL_CONFIG).get("runtime", {})
    maximum_order_preview_age = int(runtime_cfg.get("max_data_age_days_for_order_preview", 7))
    yahoo_freshness = assess_yahoo_history_freshness(
        external_history, max_age_days=maximum_order_preview_age
    )
    data_fresh = bool(yahoo_freshness.get("fresh", False))
    preview_allowed, preview_blockers = candidate_order_preview_allowed(
        external_review,
        data_fresh=data_fresh,
        manual_checks_complete=(manual_done == len(manual_results)),
    )
    st.markdown("### 注文直前プレビュー・ゲート")
    latest_market_date = yahoo_freshness.get("latest_market_date")
    if data_fresh:
        st.caption(
            f"最新市場データ: Yahoo Finance系 / 最終取引日 {latest_market_date} / "
            f"経過 {yahoo_freshness.get('age_days')}日（許容 {maximum_order_preview_age}日以内）。"
            "J-Quantsの遅延スナップショットは定量分析用として分離しています。"
        )
    else:
        st.warning(
            "Yahoo Finance系の最新日足を取得できない、または鮮度条件を満たさないため、"
            "注文直前プレビューの市場データ条件を通過できません。"
        )
    if preview_allowed:
        st.success("外的要因レビュー、データ鮮度、人手確認の必須条件を満たしています。注文送信は行いません。")
    else:
        st.error("注文直前プレビューはブロックされています: " + " / ".join(preview_blockers))
    if st.button("注文直前プレビューへ進む（未送信）", disabled=not preview_allowed, key=f"order_preview_gate_{code_key}"):
        st.info("この画面はプレビューのみです。SBI証券への接続・ログイン・注文送信は実装していません。")

    st.markdown("### 買い検討価格帯")
    price_cols = st.columns(4)
    price_cols[0].metric("現在の整理", entry_guidance.get("status", "-"), help="最新トレンド、移動平均、RSI、直近安値を使った参考分類です。注文推奨ではありません。")
    zone_low = entry_guidance.get("zone_low")
    zone_high = entry_guidance.get("zone_high")
    price_cols[1].metric("買い検討価格帯", f"¥{zone_low:,.1f}～¥{zone_high:,.1f}" if zone_low is not None and zone_high is not None else "-", help="20日・50日移動平均線や直近安値を基準にした参考帯です。価格到達だけで買わず、反転や出来高も確認します。")
    price_cols[2].metric("追いかけ買い上限", f"¥{entry_guidance['chase_limit']:,.1f}" if entry_guidance.get("chase_limit") is not None else "-", help="短期的に価格を追い過ぎないための参考上限です。強い上昇時でも一括購入を意味しません。")
    price_cols[3].metric("再評価ライン", f"¥{entry_guidance['reconsider_below']:,.1f}" if entry_guidance.get("reconsider_below") is not None else "-", help="この水準を下回ったら、安易に買い増さず投資仮説とトレンドを再確認する参考ラインです。")
    st.info(entry_guidance.get("rationale", "価格帯を算出できませんでした。"))
    if entry_guidance.get("support_levels"):
        st.caption("参考支持水準: " + " / ".join(f"¥{v:,.1f}" for v in entry_guidance["support_levels"]))
    st.caption("買い検討価格帯は最新外部株価を優先して計算します。実際の注文前にはSBI証券の現在値・板・最新開示を確認してください。")

    st.markdown("### 分割買いの参考案")
    plan_col1, plan_col2, plan_col3 = st.columns(3)
    with plan_col1:
        decision_budget = float(st.number_input("この銘柄への投資上限（円）", min_value=0, max_value=100_000_000, value=int(st.session_state.get(f"budget_{code_key}", 300_000)), step=50_000, key=f"budget_{code_key}", help="この銘柄へ投入してよいと自分で決めた最大金額です。買付推奨額ではありません。"))
    with plan_col2:
        max_loss_pct = float(st.number_input("許容損失率（%）", min_value=1.0, max_value=50.0, value=15.0, step=1.0, key=f"loss_pct_{code_key}", help="投資上限に対して、事前に許容すると決める最大損失率の目安です。"))
    with plan_col3:
        st.metric("上限損失額の目安", f"¥{decision_budget * max_loss_pct / 100:,.0f}", help="投資上限×許容損失率で計算した資金管理上の参考額です。")
    split_plan = build_split_entry_plan(current_price_for_plan, decision_budget)
    if split_plan:
        _analysis_dataframe(pd.DataFrame(split_plan), width="stretch", hide_index=True)
        if sum(int(row["株数"]) for row in split_plan) == 0:
            st.info("100株単位では投資上限内に収まりません。投資上限を増やすか、S株を別途検討してください。")
    else:
        st.info("株価または投資上限が取得できないため、分割買い案を作成できません。")

    decision_packet = {
        "code": code_key,
        "name": str(company["name"]),
        "generated_at": pd.Timestamp.now(tz="Asia/Tokyo").isoformat(),
        "decision_summary": readiness,
        "trend_snapshot": trend_snapshot,
        "trend_transition": trend_transition,
        "intuitive_signal": intuitive_signal,
        "entry_price_guidance": entry_guidance,
        "external_event_review": external_review,
        "order_preview_allowed": preview_allowed,
        "order_preview_blockers": preview_blockers,
        "manual_checks": manual_results,
        "manual_checks_completed": manual_done,
        "investment_limit_yen": decision_budget,
        "maximum_loss_rate": max_loss_pct / 100,
        "split_entry_plan": split_plan,
        "notice": "This is decision support, not a buy recommendation or profit guarantee.",
    }
    st.download_button(
        "購入判断メモをJSONで保存",
        data=json.dumps(decision_packet, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"buy_decision_{code_key}.json",
        mime="application/json",
    )

    st.markdown("#### J-Quants分析基準日の株価情報")
    st.caption(f"J-Quants最終株価日: {pd.Timestamp(prices['date'].max()).date()}。最新トレンドのグラフは上段で外部最新日足を優先表示しています。")
    left, right = st.columns(2)
    with left:
        st.markdown("#### 決算サマリー")
        show_cols = [
            "disclosure_date", "period_end", "statement_type", "sales",
            "operating_profit", "operating_cf", "equity", "total_assets",
            "forecast_operating_profit", "eps", "book_value_per_share",
            "actual_annual_dividend_per_share",
            "forecast_annual_dividend_per_share",
            "next_forecast_annual_dividend_per_share",
            "actual_payout_ratio", "forecast_payout_ratio", "next_forecast_payout_ratio",
        ]
        available = [c for c in show_cols if c in financials.columns]
        _analysis_dataframe(
            financials[available].sort_values("disclosure_date", ascending=False).head(12),
            width="stretch",
            hide_index=True,
        )
    with right:
        st.markdown("#### 決算発表予定")
        if upcoming.empty:
            st.info("取得範囲に今後の決算発表予定はありません。")
        else:
            _analysis_dataframe(upcoming, width="stretch", hide_index=True)

    st.markdown("#### アナリスト評価・目標株価")
    try:
        analyst = _latest_analyst_snapshot(str(company["code"]))
    except Exception as exc:
        analyst = {}
        st.warning(f"外部アナリスト情報を取得できませんでした: {exc}")
    if analyst and any(analyst.get(key) is not None for key in ("recommendation_mean", "target_mean", "analyst_count")):
        rating_cols = st.columns(5)
        rating_text = analyst.get("recommendation_key") or "-"
        rating_mean = analyst.get("recommendation_mean")
        rating_cols[0].metric(
            "外部評価", str(rating_text),
            help="Yahoo Finance系データにある総合的な推奨区分です。buy、hold、sellなどで表示されます。SBI証券の評価とは別物です。",
        )
        rating_cols[1].metric(
            "評価平均", f"{float(rating_mean):.2f}" if rating_mean is not None else "-",
            help="アナリスト推奨を数値化した平均です。一般に小さいほど強気寄りですが、提供元の定義を確認し、単独では判断しないでください。",
        )
        rating_cols[2].metric(
            "対象アナリスト数", f"{int(analyst['analyst_count'])}人" if analyst.get("analyst_count") is not None else "-",
            help="評価や目標株価の集計対象になったアナリスト数です。人数が少ない場合、1人の予想による影響が大きくなります。",
        )
        rating_cols[3].metric(
            "平均目標株価", f"¥{float(analyst['target_mean']):,.0f}" if analyst.get("target_mean") is not None else "-",
            help="複数のアナリストが予想した目標株価の算術平均です。達成を保証する価格ではなく、予想時点や前提も異なります。",
        )
        rating_cols[4].metric(
            "平均目標株価への乖離", _format_pct(analyst.get("upside_to_mean_target")),
            help="平均目標株価が外部取得の現在株価より何%上または下にあるかを示します。プラスは上方余地、マイナスは下方余地ですが、予測精度を保証しません。",
        )
        target_cols = st.columns(3)
        target_cols[0].metric(
            "目標株価・低値", f"¥{float(analyst['target_low']):,.0f}" if analyst.get("target_low") is not None else "-",
            help="取得できたアナリスト目標株価のうち最も低い値です。弱気シナリオの参考になります。",
        )
        target_cols[1].metric(
            "目標株価・中央値", f"¥{float(analyst['target_median']):,.0f}" if analyst.get("target_median") is not None else "-",
            help="目標株価を順番に並べた中央の値です。極端に高い・低い予想の影響を平均値より受けにくい指標です。",
        )
        target_cols[2].metric(
            "目標株価・高値", f"¥{float(analyst['target_high']):,.0f}" if analyst.get("target_high") is not None else "-",
            help="取得できたアナリスト目標株価のうち最も高い値です。楽観シナリオであり、実現可能性を別途確認してください。",
        )
        st.caption("Yahoo Finance系の公開情報をyfinance経由で表示した参考値です。SBI証券のレーティングとは算定主体・基準日・対象アナリストが異なります。")
    else:
        st.info("外部から取得可能なアナリスト評価・目標株価がありません。")

    st.markdown("#### 関連ニュース・市場コメント（最大10件）")
    st.caption(
        "Yahoo!ファイナンス掲示板の投稿本文は、規約・著作権・安定性の観点から自動取得しません。"
        "ここにはYahoo Finance系で取得可能な関連ニュースや市場解説を表示し、日本語以外は機械翻訳します。"
    )
    try:
        news_items = _latest_market_news(str(company["code"]))
    except Exception as exc:
        news_items = []
        st.warning(f"関連ニュースを取得できませんでした: {exc}")
    if not news_items:
        st.info("現在取得可能な関連ニュース・市場コメントはありません。")
    else:
        for index, item in enumerate(news_items, start=1):
            title = item.get("title_ja") or item.get("title") or "（タイトルなし）"
            publisher = item.get("publisher") or "配信元不明"
            published = str(item.get("published_at") or "-")[:16].replace("T", " ")
            summary = item.get("summary_ja") or item.get("summary")
            url = item.get("url")
            st.markdown(f"**{index}. {title}**")
            translation_note = " / 機械翻訳" if item.get("was_translated") else ""
            st.caption(f"{publisher} / {published}{translation_note}")
            if summary:
                st.write(summary)
            if item.get("was_translated") and (item.get("original_title") or item.get("original_summary")):
                with st.expander("原文を表示"):
                    if item.get("original_title"):
                        st.write(item["original_title"])
                    if item.get("original_summary"):
                        st.write(item["original_summary"])
            if url:
                st.link_button("記事を開く", url)

    display_code = display_tse_code(company["code"])
    link_cols = st.columns(3)
    link_cols[0].link_button("Yahoo!ファイナンス銘柄ページ", f"https://finance.yahoo.co.jp/quote/{display_code}.T")
    link_cols[1].link_button("Yahoo!ファイナンス掲示板を確認", f"https://finance.yahoo.co.jp/quote/{display_code}.T/bbs")
    link_cols[2].link_button("SBI証券でレーティングを確認", "https://www.sbisec.co.jp/ETGate/")
    st.caption(
        "SBI証券の評価・レーティングはログイン後の個別銘柄『分析／アナリスト予想』で確認してください。"
        "このアプリはSBI証券の認証情報や契約データを取得・転記しません。"
    )


def render_demo() -> None:
    st.warning("このタブは架空のサンプルデータです。投資判断には使用できません。")
    candidates_path = DEMO_OUTPUT / "candidates_latest.csv"
    orders_path = DEMO_OUTPUT / "order_proposals_latest.csv"
    if candidates_path.exists():
        st.subheader("デモ候補")
        _analysis_dataframe(pd.read_csv(candidates_path, dtype={"code": str}), width="stretch", hide_index=True)
    else:
        st.info("`run_demo.cmd` を実行するとデモ結果が生成されます。")
    if orders_path.exists():
        st.subheader("デモ注文案")
        _analysis_dataframe(pd.read_csv(orders_path, dtype={"code": str}), width="stretch", hide_index=True)


DATA_PAGE = st.Page(render_data_status_and_update, title="データ更新", icon=":material/sync:", default=True)
CONDITION_PAGE = st.Page(render_condition_builder, title="条件設定・候補", icon=":material/tune:")
STOCK_DETAIL_PAGE = st.Page(render_stock_search, title="個別銘柄検索", icon=":material/search:", url_path=STOCK_DETAIL_URL_PATH)
HISTORY_PAGE = st.Page(render_history_and_validation, title="履歴・検証", icon=":material/history:")
SBI_IMPORT_PAGE = st.Page(render_sbi_csv_import, title="SBI CSV取込", icon=":material/upload_file:")
DEMO_PAGE = st.Page(render_demo, title="デモ", icon=":material/science:")


def render_safety_boundary() -> None:
    st.markdown(
        """
- SBI証券にはアクセスしません。
- SBI証券のログインID・パスワード・取引パスワードを入力しないでください。
- 条件変更は取得済みデータだけで再計算し、J-Quants APIを再呼び出しません。
- 定量候補は外的要因を調査するための一覧で、買付候補ではありません。
- TOPIXが取得できない場合、相対騰落率を別の値で代用しません。
- データが古い場合、注文直前用途には不適格と表示します。
- 注文案の生成・SBI証券への送信は無効です。
"""
    )


SAFETY_PAGE = st.Page(render_safety_boundary, title="安全境界", icon=":material/security:")
CURRENT_PAGE = st.navigation(
    [DATA_PAGE, CONDITION_PAGE, STOCK_DETAIL_PAGE, HISTORY_PAGE, SBI_IMPORT_PAGE, DEMO_PAGE, SAFETY_PAGE],
    position="top",
)
CURRENT_PAGE.run()
