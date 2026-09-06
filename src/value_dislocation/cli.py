from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from .backtest import run_signal_backtest
from .codes import display_tse_code
from .config import load_config, project_root_from_config, resolve_path
from .data.jquants import fetch_jquants_v2, search_tdnet_by_code
from .data.search import load_curated_latest, search_companies, stock_detail
from .io import load_all, write_csv
from .real_pipeline import run_real_pipeline
from .risk import create_order_proposals
from .strategy.screen import build_screen

app = typer.Typer(no_args_is_help=True, help="日本株の一時的な価格低迷を調査する半自動システム")
console = Console()


def _paths(config_path: Path, cfg: dict):
    p = cfg["paths"]
    return (
        resolve_path(config_path, p["companies"]),
        resolve_path(config_path, p["prices"]),
        resolve_path(config_path, p["financials"]),
        resolve_path(config_path, p["events"]),
        resolve_path(config_path, p["output_dir"]),
    )


@app.command()
def screen(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True),
    as_of: str = typer.Option("2026-07-31", help="評価日 YYYY-MM-DD"),
):
    """候補銘柄と外的要因レビュー待ち銘柄を出力する。"""
    cfg = load_config(config)
    companies_path, prices_path, financials_path, events_path, output_dir = _paths(config, cfg)
    companies, prices, financials, events = load_all(
        companies_path, prices_path, financials_path, events_path
    )
    candidates, review_queue = build_screen(
        companies, prices, financials, events, pd.Timestamp(as_of), cfg
    )
    write_csv(candidates, output_dir / "candidates_latest.csv")
    write_csv(review_queue, output_dir / "external_event_review_queue.csv")

    table = Table(title=f"候補銘柄 {as_of}")
    for col in ["code", "name", "score", "drawdown_52w", "relative_return_6m", "category"]:
        table.add_column(col)
    for _, r in candidates.iterrows():
        table.add_row(
            display_tse_code(r["code"]),
            str(r["name"]),
            f"{r['score']:.1f}",
            f"{r['drawdown_52w']:.1%}",
            f"{r['relative_return_6m']:.1%}",
            str(r.get("category", "")),
        )
    console.print(table)
    console.print(f"候補: {len(candidates)}件 / レビュー待ち: {len(review_queue)}件")


@app.command("run-real")
def run_real(
    config: Path = typer.Option(Path("config/real_data.yaml"), exists=True),
    end: str | None = typer.Option(None, help="取得終了日 YYYY-MM-DD。省略時は本日。"),
):
    """J-Quantsから実在する日本株データを取得し、定量候補まで生成する。"""
    result = run_real_pipeline(config, end=end)
    console.print_json(data={k: str(v) for k, v in result.items()})
    console.print("[bold green]実データの取得と定量候補作成が完了しました。[/bold green]")
    console.print("[yellow]注文案は生成していません。外的要因の人手レビューが必要です。[/yellow]")


@app.command("search-stock")
def search_stock(
    query: str = typer.Argument(..., help="銘柄コードまたは会社名"),
    config: Path = typer.Option(Path("config/real_data.yaml"), exists=True),
):
    """取得済みのJ-Quants実データから日本株を検索する。"""
    root = project_root_from_config(config)
    data = load_curated_latest(root)
    matches = search_companies(data["companies"], query)
    if matches.empty:
        console.print("該当銘柄がありません。")
        raise typer.Exit(code=1)
    if len(matches) > 1 and not query.isdigit():
        table = Table(title=f"検索結果: {query}")
        for col in ["display_code", "name", "sector", "market"]:
            table.add_column(col)
        for _, row in matches.iterrows():
            table.add_row(str(row["display_code"]), str(row["name"]), str(row["sector"]), str(row["market"]))
        console.print(table)
        return
    detail = stock_detail(data, str(matches.iloc[0]["code"]))
    company = detail["company"]
    metrics = detail["metrics"]
    console.print(f"[bold]{display_tse_code(company['code'])} {company['name']}[/bold]")
    for key in ["as_of", "close", "drawdown_52w", "relative_return_6m", "sales_cagr_3y", "operating_margin", "equity_ratio", "forecast_op_growth"]:
        if key in metrics:
            console.print(f"{key}: {metrics[key]}")


@app.command("search-tdnet")
def search_tdnet(
    code: str = typer.Argument(...),
    from_date: str = typer.Option(..., help="YYYY-MM-DD"),
    to_date: str = typer.Option(..., help="YYYY-MM-DD"),
):
    """J-Quants TDnet add-onで適時開示を検索する。契約が必要。"""
    df = search_tdnet_by_code(code, from_date=from_date, to_date=to_date)
    if df.empty:
        console.print("開示は見つかりませんでした。")
        return
    console.print(df.to_string(index=False))


@app.command("propose-orders")
def propose_orders(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True),
    candidates_file: Path | None = typer.Option(None),
):
    """デモ候補からSBI証券へ手入力するための未承認注文案を作る。"""
    cfg = load_config(config)
    if cfg.get("mode") in {"paper", "live-preview"} and not cfg.get("orders", {}).get("generation_enabled", False):
        raise typer.BadParameter("実データ設定では注文案生成が無効です。外的要因レビューとポートフォリオ取込を実装後に有効化します。")
    _, _, _, _, output_dir = _paths(config, cfg)
    source = candidates_file or output_dir / "candidates_latest.csv"
    if not source.exists():
        raise typer.BadParameter(f"候補CSVがありません: {source}. 先に screen を実行してください")
    candidates = pd.read_csv(source, dtype={"code": str})
    proposals = create_order_proposals(candidates, cfg["risk"])
    write_csv(proposals, output_dir / "order_proposals_latest.csv")
    console.print(f"注文案を作成しました: {output_dir / 'order_proposals_latest.csv'} ({len(proposals)}件)")
    console.print("[bold yellow]注意:[/bold yellow] SBI証券への自動送信は行いません。本人が注文内容を再確認してください。")


@app.command("fetch-jquants")
def fetch_jquants(
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(..., help="YYYY-MM-DD"),
    output_dir: Path = typer.Option(Path("data/raw")),
):
    """互換用: J-Quants V2から生CSVを保存する。"""
    paths = fetch_jquants_v2(start, end, output_dir)
    for name, path in paths.items():
        console.print(f"{name}: {path}")


@app.command()
def backtest(
    signals_file: Path = typer.Option(Path("data/sample/signals.csv"), exists=True),
    prices_file: Path = typer.Option(Path("data/sample/prices.csv"), exists=True),
    config: Path = typer.Option(Path("config/default.yaml"), exists=True),
):
    """過去に作成済みのシグナルCSVを使うポイントインタイム簡易バックテスト。"""
    cfg = load_config(config)
    _, _, _, _, output_dir = _paths(config, cfg)
    signals = pd.read_csv(signals_file, dtype={"code": str})
    prices = pd.read_csv(prices_file, dtype={"code": str})
    curve, metrics = run_signal_backtest(
        signals,
        prices,
        top_n=cfg["backtest"]["top_n"],
        initial_capital=cfg["backtest"]["initial_capital_yen"],
        transaction_cost_bps=cfg["backtest"]["transaction_cost_bps"],
    )
    write_csv(curve, output_dir / "backtest_equity_curve.csv")
    metrics_path = output_dir / "backtest_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print_json(data=metrics)


if __name__ == "__main__":
    app()
