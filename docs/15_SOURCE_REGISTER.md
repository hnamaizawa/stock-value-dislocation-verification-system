# Official Source Register

確認日: 2026-08-02

| ID | 公式ソース | 確認内容 | 実装 |
|---|---|---|---|
| SRC-001 | J-Quants official Python client README | V2はAPIキー認証。`ClientV2`、環境変数 `JQUANTS_API_KEY`、上場銘柄・日足・決算・決算予定・TOPIXを提供 | `create_client`、実データpipeline |
| SRC-002 | J-Quants `client_v2.py` | `get_eq_bars_daily_range` と `get_fin_summary_range` は `ThreadPoolExecutor` で日別要求を並列実行。低水準APIは `date_yyyymmdd` を受ける | full syncでrange helperを避け、直列取得 |
| SRC-003 | J-Quants official client README / FAQ | `_range` は広い期間や連続実行で429となり得る。429時は待機または期間分割。閾値は非公開 | adaptive backoff、要求間隔、再開cache |
| SRC-004 | J-Quants `client_v2.py` | `get_td_list(code,from_date,to_date)` と `get_td_files` | 銘柄別TDnetインデックス検索CLI。文書取得は次段階 |
| SRC-005 | JPX TDnet Document Add-on release 2026-05-18 | J-QuantsのTDnet文書アドオン | 外的要因一次資料の候補 |
| SRC-006 | EDINET API guidance | EDINET API V2はAPIキーが必要 | 次段階の詳細財務・法定開示 |
| SRC-007 | SBI証券公式API/国内株案内 | 国内現物株の一般公開発注APIを本設計の前提にしない | 手動発注、安全境界 |
| SRC-008 | J-Quants API HTTP 400 response from actual subscription | 契約期間外の日付要求では `Your subscription covers the following dates: start ~ end` が返る | 契約期間解析、全データセットclamp、manifest警告 |

## URLs

- https://github.com/J-Quants/jquants-api-client-python/blob/main/README.md
- https://github.com/J-Quants/jquants-api-client-python/raw/refs/heads/main/jquantsapi/client_v2.py
- https://www.jpx.co.jp/english/markets/other-data-services/j-quants-api/index.html
- https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260518-01.html
- https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0110.html

## 再確認

APIクライアント更新、契約変更、取得エラー、90日経過、SBI証券の新しい公式現物株API発表時。

## External latest quote (v0.5.8)
- yfinance official repository/docs; unofficial Yahoo Finance access, research/display only.
- Yahoo!ファイナンス日本版HTMLの自動取得は禁止されているため実装しない。
- External quote is never persisted into J-Quants snapshots and is never an order source.
