# Data Sources

確認日: 2026-08-02

## J-Quants API V2 — 現在の主データ源

実装済み:

- `get_list`: 上場銘柄一覧と業種・市場
- `get_eq_bars_daily(date_yyyymmdd=...)`: 全銘柄の日足OHLCVを日別・直列・再開可能に取得
- `get_fin_summary_cursor(date_yyyymmdd=...)`: 決算サマリーを日別・直列・再開可能に取得
- `get_idx_bars_daily_topix`: TOPIX日足
- `get_eq_earnings_cal`: 決算発表予定
- `get_td_list`: 銘柄別適時開示インデックス（アドオン契約時）

APIキーは `JQUANTS_API_KEY` だけから読む。公式 `_range` utilityは複数日を並列要求するためfull syncでは使用しない。株価と決算を直列取得し、429時は待機・再試行・要求間隔拡大を行い、日別cacheから再開する。

## EDINET API V2 — 次段階

法定開示、XBRL、営業CF、負債、現金、セグメント、リスク情報を補完する。APIキーは `EDINET_API_KEY` を使用予定。訂正報告書と提出日時をポイント・イン・タイムで管理する。

## TDnet / 企業IR — 外的要因の一次資料

J-Quants TDnet Document Add-onは、開示インデックスと文書取得の候補。未契約時は企業IR URLとローカル保存文書を人手登録する。ニュースやSNSは発見補助に限定し、承認根拠は一次資料へ置き換える。

## SBI証券

市場データ源として使わない。将来利用するのはユーザーが手動出力した保有・約定CSVと、ユーザーが確認した買付余力だけ。認証情報、Webスクレイピング、ブラウザー自動操作、注文送信は対象外。


## v0.5.4 benchmark policy
正式TOPIXを優先し、取得できない場合だけTOPIX連動ETF（1306、1475、1305）の調整後終値を明示的な代理指標として利用する。代理値は正式TOPIXと表示上・監査上で区別し、両方なければ市場相対条件を保留する。
