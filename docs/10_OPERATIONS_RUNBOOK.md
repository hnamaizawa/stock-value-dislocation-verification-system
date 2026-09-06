# Operations Runbook

## 初回

1. `setup_windows.cmd`
2. `check_harness.cmd`
3. `start_dashboard.cmd`
4. `http://localhost:8501`
5. 実データタブでJ-Quants APIキーを入力
6. 実データ更新
7. manifestの `actual_data=true`、最終株価日、件数を確認
8. manifestの `subscription_coverage` と `request.effective_price_end` を確認
9. 会社名またはコードで検索

## `.env` 運用

`.env` の `JQUANTS_API_KEY` を設定して `run_real.cmd` を実行する。`.env` を共有、Git登録、生成アプリへコピーしない。

## 更新時

- 株価と決算は日別cacheを再利用し、未取得日のみAPIへ要求する。
- 429時は自動待機し、その後は保守的な要求間隔へ切り替える。
- 各runは `data/raw/jquants/<run_id>` と `data/curated/runs/<run_id>` に残す。
- 取得失敗時は以前のlatestを実データとして更新したふりをしない。
- 契約期間外の日付が指定された場合、APIが返した契約範囲へ自動調整し、manifestと画面へ警告を残す。
- 上限回数後も429が続いて停止した場合、黒い画面を閉じ、十分待ってから同じコマンドを再実行する。完了済みの日は再取得しない。

## 週次レビュー

- `outputs/real/quantitative_shortlist_latest.csv`
- `outputs/real/external_event_review_queue_latest.csv`
- `outputs/real/run_status_latest.json`
- `data/curated/latest/manifest.json`

定量候補は注文候補ではない。一次資料を確認し、外的要因、一時性、回復条件、構造リスクを記録する。

## 現段階でSBI証券について行うこと

なし。アプリへSBI認証情報を入力しない。注文も行わない。保有CSV取込と注文前ゲートが完成するまでは調査専用とする。

## 429対応

- 初回同期中に `HTTP 429` が表示されても、0.3.2では自動的に待機して再試行する。
- `Waiting ... seconds, then resuming from cache` は正常な制御メッセージ。
- エラー終了した場合も `data/raw/jquants/_cache/` を削除しない。
- 更新ボタンや `run_real.cmd` を同時に複数起動しない。

## 契約期間外HTTP 400対応

- `Your subscription covers the following dates: YYYY-MM-DD ~ YYYY-MM-DD` はAPIキー不良ではなく、現在の契約で取得できる日付範囲を示す。
- 0.3.3では、その開始日・終了日を自動検出し、株価・決算・TOPIXの要求期間を調整する。
- 画面の「契約データ上限日」と `data/curated/latest/manifest.json` の `subscription_coverage` を確認する。
- 最新日が本日より古い場合、その差はアプリ障害ではなく契約プランのデータ遅延である可能性が高い。
