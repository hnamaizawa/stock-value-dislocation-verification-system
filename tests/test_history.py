from pathlib import Path
import pandas as pd

from value_dislocation.history import (
    select_slow_revaluation_batch,
    attach_daily_final_evaluations, build_star_events, condition_performance, enrich_star_events_with_market_histories, load_analysis_history,
    load_evaluation_history, reconcile_star_outcomes, summarize_star_outcomes_by_code, upsert_daily_evaluations, write_daily_analysis_snapshot,
)


def test_daily_analysis_snapshot_overwrites_same_day(tmp_path: Path):
    one = pd.DataFrame([{"code":"72030","name":"A","selected_for_review":True,"strategy_score":60.0,"operating_margin":0.12}])
    two = pd.DataFrame([{"code":"72030","name":"A","selected_for_review":True,"strategy_score":70.0,"operating_margin":0.13}])
    write_daily_analysis_snapshot(tmp_path, one, analysis_date="2026-08-17", run_id="r1")
    write_daily_analysis_snapshot(tmp_path, two, analysis_date="2026-08-17", run_id="r2")
    loaded=load_analysis_history(tmp_path)
    assert len(loaded)==1
    assert loaded.iloc[0]["strategy_score"]==70.0


def test_evaluation_upsert_and_star_forward_returns(tmp_path: Path):
    def save(day, symbol, price):
        frame=pd.DataFrame([{"raw_code":"72030","企業名":"A","市場":"Prime","直感判定":f"{symbol} 買い候補","最新株価":price,"selection_strategy":"value_dislocation"}])
        upsert_daily_evaluations(tmp_path,frame,evaluation_date=day,analysis_as_of=day)
    save("2026-01-01","○",100)
    save("2026-01-02","◎☆",110)
    save("2026-02-02","◎☆",121)
    save("2026-04-03","○",132)
    events=build_star_events(load_evaluation_history(tmp_path))
    assert len(events)==1
    assert round(events.iloc[0]["return_30d"],6)==0.1
    assert round(events.iloc[0]["return_90d"],6)==0.2
    assert pd.isna(events.iloc[0]["return_180d"])


def test_condition_performance_uses_analysis_snapshot(tmp_path: Path):
    audit=pd.DataFrame([{"code":"72030","name":"A","selected_for_review":True,"strategy_score":70,"sales_cagr_3y":0.05,"operating_margin":0.12,"equity_ratio":0.5}])
    write_daily_analysis_snapshot(tmp_path,audit,analysis_date="2026-01-02",run_id="r")
    evals=[]
    for day,symbol,price in [("2026-01-02","◎☆",100),("2026-02-02","◎☆",110)]:
        f=pd.DataFrame([{"raw_code":"72030","企業名":"A","直感判定":f"{symbol} 買い候補","最新株価":price,"selection_strategy":"value_dislocation"}])
        upsert_daily_evaluations(tmp_path,f,evaluation_date=day,analysis_as_of="2026-01-02")
    perf=condition_performance(tmp_path)
    row=perf.loc[perf["条件"]=="営業利益率 10%以上"].iloc[0]
    assert row["該当イベント数"]==1
    assert round(row["30日平均"],6)==0.1


def test_market_history_enrichment_fills_return_even_if_candidate_not_seen_again():
    events=pd.DataFrame([{"code":"72030","star_date":"2026-01-02","entry_price":100.0,"return_30d":None,"actual_days_30d":None}])
    history=pd.DataFrame({"date":pd.to_datetime(["2026-01-02","2026-02-03"]),"close":[100.0,115.0]})
    out=enrich_star_events_with_market_histories(events,{"72030":history},horizons=(30,))
    assert round(out.iloc[0]["return_30d"],6)==0.15
    assert out.iloc[0]["actual_days_30d"]==32


def test_analysis_history_can_attach_same_day_final_evaluation():
    analysis = pd.DataFrame([
        {"analysis_date":"2026-08-18","code":"72030","name":"A","selection_strategy":"value_dislocation","selected_for_review":True},
        {"analysis_date":"2026-08-18","code":"83060","name":"B","selection_strategy":"value_dislocation","selected_for_review":True},
    ])
    evaluations = pd.DataFrame([
        {"evaluation_date":"2026-08-18","code":"72030","selection_strategy":"value_dislocation","intuitive_symbol":"◎☆"},
    ])
    out = attach_daily_final_evaluations(analysis, evaluations)
    assert out.loc[out["code"]=="72030", "final_evaluation"].iloc[0] == "◎☆"
    assert out.loc[out["code"]=="83060", "final_evaluation"].iloc[0] == "未評価"


def test_unassessed_reason_is_preserved_and_final_evaluation_stays_unassessed():
    analysis = pd.DataFrame([{
        "analysis_date":"2026-08-18", "code":"72030", "name":"A",
        "selection_strategy":"value_dislocation", "selected_for_review":True,
    }])
    evaluations = pd.DataFrame([{
        "evaluation_date":"2026-08-18", "code":"72030", "selection_strategy":"value_dislocation",
        "intuitive_symbol":"△", "latest_price":None, "latest_trend":"未実施（100件以上）",
        "evaluation_status":"未評価", "unassessed_reason":"Yahoo100件制限で未実施",
    }])
    out = attach_daily_final_evaluations(analysis, evaluations)
    row = out.iloc[0]
    assert row["final_evaluation"] == "未評価"
    assert row["evaluation_status"] == "未評価"
    assert row["unassessed_reason"] == "Yahoo100件制限で未実施"


def test_missing_old_evaluation_is_classified_as_legacy():
    analysis = pd.DataFrame([
        {"analysis_date":"2026-08-17", "code":"72030", "selection_strategy":"value_dislocation"},
        {"analysis_date":"2026-08-20", "code":"83060", "selection_strategy":"value_dislocation"},
    ])
    evaluations = pd.DataFrame([{
        "evaluation_date":"2026-08-19", "code":"99990", "selection_strategy":"value_dislocation",
        "intuitive_symbol":"○", "latest_price":100, "latest_trend":"方向感なし・もみ合い",
    }])
    out = attach_daily_final_evaluations(analysis, evaluations)
    assert out.loc[out["code"]=="72030", "unassessed_reason"].iloc[0] == "旧履歴"
    assert out.loc[out["code"]=="83060", "unassessed_reason"].iloc[0] == "評価履歴なし"


def test_revaluation_uses_only_prices_available_by_original_analysis_day():
    from value_dislocation.history import revaluate_unassessed_rows

    dates = pd.bdate_range(end="2026-08-18", periods=260)
    closes = pd.Series(range(100, 100 + len(dates)), dtype=float)
    history = pd.DataFrame({
        "date": list(dates) + [pd.Timestamp("2026-08-19")],
        "close": list(closes) + [9999.0],
        "high": list(closes + 1) + [10000.0],
        "low": list(closes - 1) + [9998.0],
        "volume": [1_000_000] * (len(dates) + 1),
    })
    analysis = pd.DataFrame([{
        "analysis_date":"2026-08-18", "data_as_of":"2026-08-18", "code":"72030", "name":"A",
        "market":"Prime", "selection_strategy":"value_dislocation", "selected_for_review":True,
        "drawdown_52w":-0.25, "relative_return_6m":-0.10, "sales_cagr_3y":0.05,
        "operating_margin":0.12, "equity_ratio":0.55, "operating_cf_positive_ratio_3y":1.0,
        "forecast_op_growth":0.05, "forecast_dividend_yield":0.03, "payout_ratio":0.4,
        "forecast_dividend_change_rate":0.0, "strategy_score":80,
    }])
    out = revaluate_unassessed_rows(analysis, {"72030": history}, evaluated_at="2026-08-22T09:00:00+09:00")
    row = out.iloc[0]
    assert row["evaluation_status"] == "後日補完"
    assert row["original_final_evaluation"] == "未評価"
    assert row["evaluation_as_of"] == "2026-08-18"
    assert row["latest_market_date"] == "2026-08-18"
    assert row["latest_price"] != 9999.0


def test_revaluation_without_yahoo_history_remains_unassessed():
    from value_dislocation.history import revaluate_unassessed_rows
    analysis = pd.DataFrame([{
        "analysis_date":"2026-08-18", "code":"72030", "selection_strategy":"value_dislocation",
    }])
    out = revaluate_unassessed_rows(analysis, {}, evaluated_at="2026-08-22T09:00:00+09:00")
    row = out.iloc[0]
    assert row["evaluation_status"] == "未評価"
    assert row["unassessed_reason"] == "Yahoo取得失敗"


def test_select_slow_revaluation_batch_limits_unique_codes_and_keeps_all_dates():
    frame = pd.DataFrame([
        {"analysis_date":"2026-08-01","code":"72030"},
        {"analysis_date":"2026-08-02","code":"72030"},
        {"analysis_date":"2026-08-01","code":"83060"},
        {"analysis_date":"2026-08-01","code":"99840"},
    ])
    out = select_slow_revaluation_batch(frame, batch_size=2)
    assert set(out["code"]) == {"72030", "83060"}
    assert len(out.loc[out["code"] == "72030"]) == 2
    assert "99840" not in set(out["code"])


def test_reconcile_star_outcomes_restores_old_events_and_preserves_returns():
    evaluations = pd.DataFrame([
        {"evaluation_date":"2026-01-02","code":"11110","name":"Old","intuitive_symbol":"◎☆","latest_price":100,"latest_market_date":"2026-01-02","latest_trend":"上昇"},
        {"evaluation_date":"2026-02-10","code":"22220","name":"New","intuitive_symbol":"◎☆","latest_price":200,"latest_market_date":"2026-02-10","latest_trend":"上昇"},
    ])
    saved = pd.DataFrame([{
        "code":"22220","star_date":"2026-02-10","entry_price":200,
        "return_30d":0.12,"actual_days_30d":31,
    }])
    out = reconcile_star_outcomes(evaluations, saved)
    assert set(out["code"]) == {"11110", "22220"}
    new = out.loc[out["code"] == "22220"].iloc[0]
    assert round(float(new["return_30d"]), 6) == 0.12
    assert int(new["actual_days_30d"]) == 31
    assert out.iloc[0]["code"] == "11110"


def test_selected_only_does_not_treat_string_false_as_true(tmp_path):
    root = tmp_path
    folder = root / "data" / "history" / "analysis"
    folder.mkdir(parents=True)
    pd.DataFrame([
        {"analysis_date": "2026-09-04", "data_as_of": "2026-06-04", "run_id": "a", "code": "11110", "selected_for_review": "False"},
        {"analysis_date": "2026-09-04", "data_as_of": "2026-06-04", "run_id": "a", "code": "22220", "selected_for_review": "True"},
    ]).to_csv(folder / "2026-09-04.csv.gz", index=False, compression="gzip")
    got = load_analysis_history(root, selected_only=True)
    assert got["code"].tolist() == ["22220"]


def test_identical_next_day_snapshot_is_not_created_and_old_duplicate_is_collapsed(tmp_path):
    audit = pd.DataFrame([
        {"code": "72030", "name": "A", "selection_strategy": "value_dislocation", "selected_for_review": True, "strategy_score": 70.0},
        {"code": "83060", "name": "B", "selection_strategy": "value_dislocation", "selected_for_review": False, "strategy_score": 20.0},
    ])
    first = write_daily_analysis_snapshot(tmp_path, audit, analysis_date="2026-09-04", run_id="fri", data_as_of="2026-06-04")
    second = write_daily_analysis_snapshot(tmp_path, audit, analysis_date="2026-09-05", run_id="sat", data_as_of="2026-06-04")
    assert second == first
    assert not (tmp_path / "data" / "history" / "analysis" / "2026-09-05.csv.gz").exists()

    # Simulate an already-existing duplicate from an older app version; loader collapses it.
    dup = pd.read_csv(first, dtype={"code": str}, compression="gzip")
    dup["analysis_date"] = "2026-09-05"
    dup["run_id"] = "sat-old-version"
    dup.to_csv(tmp_path / "data" / "history" / "analysis" / "2026-09-05.csv.gz", index=False, compression="gzip")
    loaded = load_analysis_history(tmp_path)
    assert set(loaded["analysis_date"].astype(str)) == {"2026-09-04"}


def test_changed_snapshot_same_data_as_of_is_preserved(tmp_path):
    first = pd.DataFrame([{"code": "72030", "selection_strategy": "value_dislocation", "selected_for_review": True, "strategy_score": 70.0}])
    changed = pd.DataFrame([{"code": "72030", "selection_strategy": "value_dislocation", "selected_for_review": True, "strategy_score": 71.0}])
    p1 = write_daily_analysis_snapshot(tmp_path, first, analysis_date="2026-09-04", run_id="r1", data_as_of="2026-06-04")
    p2 = write_daily_analysis_snapshot(tmp_path, changed, analysis_date="2026-09-05", run_id="r2", data_as_of="2026-06-04")
    assert p1 != p2
    loaded = load_analysis_history(tmp_path)
    assert set(loaded["analysis_date"].astype(str)) == {"2026-09-04", "2026-09-05"}


def test_non_selected_analysis_is_not_counted_as_unassessed():
    analysis = pd.DataFrame([
        {"analysis_date":"2026-09-04", "code":"11110", "selection_strategy":"value_dislocation", "selected_for_review":False},
        {"analysis_date":"2026-09-04", "code":"22220", "selection_strategy":"value_dislocation", "selected_for_review":True},
    ])
    evaluations = pd.DataFrame([
        {"evaluation_date":"2026-09-04", "code":"22220", "selection_strategy":"value_dislocation",
         "intuitive_symbol":"◎", "latest_price":100, "latest_trend":"上昇"},
    ])
    out = attach_daily_final_evaluations(analysis, evaluations)
    outside = out.loc[out["code"] == "11110"].iloc[0]
    selected = out.loc[out["code"] == "22220"].iloc[0]
    assert outside["final_evaluation"] == "対象外"
    assert outside["evaluation_status"] == "評価対象外"
    assert outside["unassessed_reason"] == "定量候補外"
    assert selected["evaluation_status"] == "当日評価済み"
    assert int((out["evaluation_status"] == "未評価").sum()) == 0


def test_attach_daily_final_evaluations_accepts_duplicate_selected_for_review_columns():
    # Regression for real accumulated history where duplicate column labels can
    # surface after mixed-version CSV concatenation.  The selection mask must be
    # normalized to 1-D and must not raise ``unhashable type: Series``.
    analysis = pd.DataFrame(
        [
            ["2026-09-04", "11110", "value_dislocation", False, False],
            ["2026-09-04", "22220", "value_dislocation", False, True],
        ],
        columns=[
            "analysis_date", "code", "selection_strategy",
            "selected_for_review", "selected_for_review",
        ],
    )
    evaluations = pd.DataFrame([
        {
            "evaluation_date": "2026-09-04",
            "code": "22220",
            "selection_strategy": "value_dislocation",
            "intuitive_symbol": "◎",
            "latest_price": 100,
            "latest_trend": "上昇",
        }
    ])

    out = attach_daily_final_evaluations(analysis, evaluations)

    outside = out.loc[out["code"] == "11110"].iloc[0]
    selected_row = out.loc[out["code"] == "22220"].iloc[0]
    assert outside["evaluation_status"] == "評価対象外"
    assert selected_row["evaluation_status"] == "当日評価済み"
    assert selected_row["final_evaluation"] == "◎"


def test_coerce_selected_for_review_mask_is_positional_after_merge():
    # A non-default/duplicate index must not be used as a label-aligned .loc mask
    # after the evaluation merge resets the DataFrame index.
    analysis = pd.DataFrame([
        {"analysis_date": "2026-09-04", "code": "11110", "selection_strategy": "value_dislocation", "selected_for_review": False},
        {"analysis_date": "2026-09-04", "code": "22220", "selection_strategy": "value_dislocation", "selected_for_review": True},
    ], index=[10, 10])
    evaluations = pd.DataFrame([
        {"evaluation_date": "2026-09-04", "code": "22220", "selection_strategy": "value_dislocation", "intuitive_symbol": "○", "latest_price": 100, "latest_trend": "上昇"}
    ])

    out = attach_daily_final_evaluations(analysis, evaluations)
    assert list(out["evaluation_status"]) == ["評価対象外", "当日評価済み"]


def test_summarize_star_outcomes_by_code_collapses_duplicate_codes_and_averages_matured_returns():
    events = pd.DataFrame([
        {"code":"96990","name":"ニシオホールディングス","star_date":"2026-08-25","entry_price":4640,"return_30d":0.10,"return_90d":None,"return_180d":None},
        {"code":"96990","name":"ニシオホールディングス","star_date":"2026-08-28","entry_price":4665,"return_30d":0.20,"return_90d":0.30,"return_180d":None},
        {"code":"97950","name":"ステップ","star_date":"2026-08-28","entry_price":2314,"return_30d":None,"return_90d":None,"return_180d":None},
    ])
    out = summarize_star_outcomes_by_code(events)
    assert len(out) == 2
    row = out.loc[out["code"] == "96990"].iloc[0]
    assert row["first_star_date"] == "2026-08-25"
    assert row["latest_star_date"] == "2026-08-28"
    assert int(row["star_count"]) == 2
    assert float(row["latest_entry_price"]) == 4665
    assert round(float(row["return_30d_avg"]), 6) == 0.15
    assert int(row["completed_30d"]) == 2
    assert round(float(row["return_90d_avg"]), 6) == 0.30
    assert int(row["completed_90d"]) == 1
    assert pd.isna(row["return_180d_avg"])
    assert int(row["completed_180d"]) == 0
