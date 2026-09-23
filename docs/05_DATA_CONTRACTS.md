# Data Contracts

東証コードは内部で5桁文字列へ正規化する。一般的な4桁コード `7203` はJ-Quants形式 `72030` とし、画面では `7203` と表示する。

## Dataset Manifest

実データCuratedディレクトリに必須:

- `schema_version`
- `run_id`
- `provider=J-Quants API V2`
- `actual_data=true`
- `sample_data=false`
- `retrieved_at`
- `data_cutoff_at`: 要求終了日ではなく実際の最終株価日
- `request`: requested/effectiveの価格開始・終了、財務開始、APIキー環境変数名、利用メソッド
- `subscription_coverage`: APIが返した契約開始日・終了日。検出できなかった場合はnull
- `warnings`: 契約期間への調整、任意APIの利用不可など
- `raw_files` / `curated_files`: path、rows、columns、SHA-256

manifestがない、壊れている、フラグが一致しない場合は検索処理を停止する。

## CompanyMaster

`code,name,sector,sector33_code,market,master_date,shares_outstanding`

## HistoricalSecurityMaster

J-Quants実データ更新時のCompanyMasterを、`data/history/security_master/YYYY-MM-DD.csv.gz`
へ日付別・追記型で保存する。既存のcertified curated runに残るCompanyMasterもAPIを
呼ばずに復元する。sample dataまたはmanifestで実データと確認できないrunは復元対象外とする。

元のCompanyMaster列に次を追加する。

`security_master_snapshot_date,security_master_source_run_id`

同名日付ファイルは上書きしない。隣接するJSONには`schema_version`、`snapshot_date`、
`run_id`、`rows`を記録する。Walk-Forwardは評価日以前で最も新しいスナップショットを使い、
存在しない場合だけ現在のCompanyMasterへフォールバックして、その事実を結果へ記録する。

## MarketDaily

`date,code,open,high,low,close,volume,turnover_yen,adjustment_factor,topix_close`

価格特徴量はJ-Quantsの調整済みOHLCVを優先する。

## FinancialSnapshot

`disclosure_date,disclosure_time,code,document_id,statement_type,period_end,fiscal_year,sales,operating_profit,ordinary_profit,net_income,operating_cf,investing_cf,financing_cf,total_assets,equity,interest_bearing_debt,cash,eps,book_value_per_share,forecast_sales,forecast_operating_profit,forecast_eps,shares_outstanding,is_full_year_actual,is_revision,source_type`

J-Quants決算サマリーにない有利子負債は現段階で欠損とし、ゼロとみなさない。EDINETで補完予定。

## EarningsCalendar

`date,code,name,fiscal_year,quarter,market`

## ExternalEventReviewQueue

`run_id,data_cutoff_at,code,name,sector,market,close,quantitative_score,drawdown_52w,relative_return_6m,sales_cagr_3y,operating_margin,equity_ratio,forecast_op_growth,event_date,category,externality,temporary_probability,catalyst_probability,evidence,source_url,review_status,reviewer,reviewed_at,expires_at`

現段階の初期値は `review_status=pending`。注文プレビューには利用できない。
