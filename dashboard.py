Warning: truncated output (original token count: 57908)
Total output lines: 3753

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
    supported_walk_forward_horizons,
    walk_forward_cohort_summary,
    walk_forward_entry_timing_summary,
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
    "close": "分析に使った日の終値です。新しい株価とは別に保存し、当時の候補選びに使います。",
    "drawdown_52w": "今の分析株価が、過去約1年間の最高値からどれだけ下がったかです。マイナスの数字が大きいほど大きく下がっています。",
    "return_6m": "約6か月前と比べた株価の上げ下げです。",
    "relative_return_6m": "銘柄の過去6か月の値動きと、市場全体の値動きの差です。マイナスが大きいほど市場より弱い動きでした。",
    "sales_cagr_3y": "過去約3年間で、売上が年平均どれだけ増減したかです。プラスは増加、マイナスは縮小を表します。",
    "operating_margin": "売上のうち、本業の利益として残った割合です。同じ業種の会社と比べると見やすくなります。",
    "equity_ratio": "会社の資産のうち、返済の必要がない自己資本の割合です。一般に高いほど財務に余裕があります。",
    "forecast_annual_dividend_per_share": "会社が予想している1株あたりの年間配当です。予想がない場合は直近の実績を使うことがあります。",
    "forecast_dividend_yield": "1株あたりの年間配当を株価で割った割合です。高い場合は、配当が減る可能性も確認してください。",
    "payout_ratio": "利益のうち配当に回す割合です。高すぎる場合、配当を続ける余裕が少ないことがあります。",
    "forecast_dividend_change_rate": "前の年度と比べて、会社が配当を増やすか減らすかの予想です。プラスは増配、マイナスは減配です。",
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
    "quantitative_score": "財務や株価など、設定した条件にどれだけ当てはまるかを点数にしたものです。高得点でも値上がりを保証しません。",
    "strategy_score": "選んだ探し方の条件にどれだけ当てはまるかを示す点数です。利益が出る確率ではありません。",
    "定量スコア": "財務や株価の条件への当てはまりを示す0〜85点の点数です。外的要因の人手レビューや根拠URLの有無では減点せず、財務上の問題は減点します。高得点でも値上がりを保証しません。",
    "スコア": "設定した条件への当てはまりを比べる目安です。高いほど将来の利益が大きいという意味ではありません。",
    "selected_for_review": "定量条件を通過し、人が詳しく確認する候補になったかを示します。",
    "selection_strategy": "銘柄を探すときに選んだ方法です。「株価が下がった企業を探す」か「値動きが大きい銘柄を探す」かを表します。",
    "抽出ルール": "銘柄を探すときに選んだ方法です。「株価が下がった企業を探す」か「値動きが大きい銘柄を探す」かを表します。",
    "final_evaluation": "財務や業績、最近の株価の動きをまとめた目安です。記号だけで売買を決めないでください。",
    "intuitive_symbol": "財務や業績、最近の株価の動きをまとめた目安です。評価記号は将来の値上がりを約束しません。",
    "評価": "財務や業績、最近の株価の動きをまとめた目安です。単独で売買を決めるものではありません。",
    "最新判定": "取得できた新しい日足を見て、株価の動きをもう一度確認した結果です。候補抽出の点数は変えません。",
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
    "期間": "候補になった日から、何営業日後までの値動きを見ているかです。",
    "十分な株価下落": "過去の高値と比べて、株価がどれだけ下がっているかを見ます。下落が大きくても、会社の問題が原因の場合があります。",
    "市場以上の下落": "市場全体よりもこの銘柄の下落が大きかったかを見ます。市場の数字がない場合は比較できません。",
    "売上トレンド": "会社の売上が過去数年で増えているか、減っているかを見ます。",
    "本業の収益性": "売上から本業の利益がどれだけ残っているかを見ます。",
    "財務余力": "会社の資産に対して、返済不要の自己資本がどれだけあるかを見ます。",
    "現金創出の継続性": "過去の決算で、本業から現金を得られているかを見ます。",
    "利益の質": "帳簿上の本業の利益に見合う現金が入っているかを見ます。",
    "採算の安定性": "本業の利益率が、過去数年で大きく下がっていないかを見ます。",
    "会社予想の修正方向": "会社が同じ年度について出した利益予想が、前回より上がったか下がったかを見ます。",
    "同業他社対比": "同じ業種の会社と比べて、株価の動きが極端に弱くないかを見ます。",
    "会社予想": "会社が発表した今後の本業の利益見込みです。会社の予想は後で変わることがあります。",
    "配当の魅力": "会社が予想する配当額を株価と比べた目安です。高いだけで配当が続くとは限りません。",
    "配当の持続性": "会社の利益に対して配当が大きすぎず、続けられそうかを見る目安です。",
    "減配リスク": "会社が予想する配当が前より減っていないかを見ます。",
    "価格トレンド": "最近の株価が上向きか下向きかを、過去の値動きから見た目安です。",
    "直近20日モメンタム": "直近20営業日の株価が上がったか下がったかです。",
    "短期の過熱感": "短い期間で株価が急に上がりすぎたり下がりすぎたりしていないかを見る目安です。",
    "出来高の確認": "最近の売買量がいつもより増えているかを見ます。売買量だけで上昇が続くとは判断できません。",
    "平均リターン": "対象になった記録すべての値上がり・値下がりを平均した値です。大きな上げ下げに影響されるため、中央値や件数も合わせて見てください。",
    "平均リターン(%)": "対象になった記録すべての値上がり・値下がりを平均した値です。大きな上げ下げに影響されるため、中央値や件数も合わせて見てください。",
    "中央値": "値動きを順に並べたときの真ん中の値です。平均よりも、一部の極端な上げ下げに左右されにくい見方です。",
    "プラス率": "対象の記録のうち、株価が上がった割合です。何件を調べた結果かも確認してください。",
    "プラス率(%)": "対象の記録のうち、株価が上がった割合です。何件を調べた結果かも確認してください。",
    "5%以上下落率": "対象の記録のうち、株価が5%以上下がった割合です。大きな下落がどの程度あったかを見る目安です。",
    "確定件数": "選んだ日数分の株価データがそろい、成績を計算できた記録数です。候補全体の件数とは異なります。",
    "候補平均": "過去に候補として選ばれた銘柄の平均的な株価変化です。",
    "候補プラス率": "過去に候補として選ばれた銘柄のうち、株価が上がった割合です。",
    "類似非選択平均": "候補には選ばれませんでしたが、条件が似ていた銘柄の平均的な株価変化です。",
    "選択効果": "選ばれた銘柄と、条件が似ていた非候補の成績の差です。プラスなら候補側が上でしたが、選び方が差の原因だと証明するものではありません。",
    "選択効果プラス率": "候補銘柄の成績が、条件の似た非候補を上回った割合です。候補と比較銘柄の両方で株価データがそろった記録だけを数えます。",
    "判定方式": "どの候補条件を使ったかを示します。条件が異なる結果は、同じ期間・同じ記録数かを確かめて比べてください。",
    "selected_return": "過去に候補として選ばれた銘柄の、その後の平均的な株価変化です。",
    "control_return": "候補には選ばれなかったものの、似た条件だった銘柄の、その後の平均的な株価変化です。",
    "selection_effect": "候補と、条件が似ていた非候補との成績の差です。プラスなら候補の方が上でした。ただし、選び方が差を生んだと証明するものではありません。",
    "external_shock_ratio": "株価の下落のうち、市場全体や同じ業種の値動きと重なっていた割合の目安です。外的要因が原因だと証明する数字ではありません。",
    "外因説明率": "株価の下落のうち、市場全体や同じ業種の値動きと重なっていた割合の目安です。外的要因が原因だと証明する数字ではありません。",
    "master_coverage_ratio": "過去に上場していた銘柄のうち、保存済みの会社一覧で確認できた割合です。",
    "survivorship_bias_warning": "現在は上場していない会社など、保存した過去の会社一覧から漏れた銘柄があるかもしれないという注意です。",
    "候補イベント": "過去の各日に候補条件を満たした記録の合計です。同じ銘柄でも日が違えば別々に数えます。",
    "再現時点": "過去の候補選びを何日分再現したかを示します。",
    "検証期間": "過去の候補選びを再現した最初の日から最後の日までです。",
    "会社マスター最低カバレッジ": "検証期間中、過去の上場銘柄をどれだけ記録で確認できたかの最低割合です。低い場合、過去の候補や成績が偏るおそれがあります。",
    "fail_reasons": "候補条件を満たさなかった理由です。",
    "warning_reasons": "候補からは外していませんが、追加で確認した方がよい点です。",
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
    "operating_cf": "本業で現金が増えたか減ったかを示します。帳簿上の利益が実際の現金になっているかを見る材料です。",
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
    return ANALYSIS_ITEM_HELP.get(str(item), fallback or f"{item}についての情報です。単位や対象期間を確認し、ほかの項目と合わせて見てください。")


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
    …37908 tokens truncated…20']:,.1f}" if trend_snapshot.get("sma20") is not None else "-", help="短期の平均的な株価水準です。現在値が上なら短期的に強く、下なら弱い傾向です。")
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
