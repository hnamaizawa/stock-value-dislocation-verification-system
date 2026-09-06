# Known Issues

## Critical before investment use

1. ユーザーのJ-Quants実契約でのエンドツーエンド検証が未実施。
2. 外的要因の人手承認UIは実装済み。一次資料本文の自動取込・保存は未実装。
3. SBI保有、買付余力、未約定注文を反映しない。
4. 実データ設定では注文案生成を無効化している。

## Data

1. 初回全銘柄同期は契約プランによって長時間かかる。429は自動制御するが、即時完了は保証できない。
2. J-Quants決算サマリーだけでは有利子負債等が不足し、net cashを確定できない。
3. 上場廃止、市場変更、コード変更の履歴は未対応。
4. 企業による会計・連結/非連結差の検証が不足。
5. TDnet文書本文の取得と保存は未実装。

## Analysis

1. 業種PER/PBR中央値は欠損や赤字企業の影響を受ける。
2. 定量候補は外的要因を証明していない。
3. 現在のバックテストは実データ版戦略の完成検証ではない。
4. 呼値、値幅制限、決算直前、権利落ち、売買停止を考慮しない。

## Operations

1. WindowsセットアップはWinGetまたは既存Pythonに依存する。
2. Streamlitの黒い画面を閉じるとサーバーも停止する。
3. 大規模初回取得中は画面が長時間spinner状態になる。詳細進捗は黒い起動画面へ表示される。
4. 契約プランによっては最新取得可能日が本日より古い。0.3.3は自動調整するが、遅延そのものは解消しない。

## Resolved in 0.3.1: J-Quants daily bars HTTP 400

The V2 daily-bars endpoint requires `date` or `code`. The previous all-stock request sent only
`from` and `to`, which returned HTTP 400. The pipeline now uses the official range utility and
the harness rejects regressions to the invalid call form.

## Resolved in 0.3.2: concurrent range helper HTTP 429

公式range helperが複数日を並列取得し、短時間に429となっていた。full syncは日付単位の直列取得へ変更し、backoffと再開cacheを追加した。なお、契約上の呼出し上限自体はなくならないため、初回同期時間はプラン依存である。

## Resolved in 0.3.3: subscription coverage HTTP 400

画面やCLIの終了日が契約上の最新取得可能日より新しい場合、日別取得の終盤でHTTP 400となっていた。APIエラー本文の契約開始日・終了日を事前に検出し、価格・財務・TOPIXの全要求を同じ実効期間へ調整するよう変更した。要求期間、実効期間、契約期間はmanifestへ記録する。


## v0.5.4 benchmark policy
正式TOPIXを優先し、取得できない場合だけTOPIX連動ETF（1306、1475、1305）の調整後終値を明示的な代理指標として利用する。代理値は正式TOPIXと表示上・監査上で区別し、両方なければ市場相対条件を保留する。

## Resolved in 0.6.11: 外的要因レビューの人手承認UI

候補銘柄の個別詳細から外的要因レビューを保存できるようにし、approved以外は注文直前プレビューをブロックする。保存済みレビューはruntime stateとして生成アプリへコピーしない。一次資料本文の自動取得・保存自体は引き続き未実装。


## Resolved in 0.6.12: delayed J-Quants data and candidate market freshness

個別銘柄の注文直前プレビューでは、Yahoo Finance系の日足最終取引日を市場鮮度判定に利用する。J-Quantsの遅延データは定量分析用として分離し、Yahooデータはpoint-in-timeスコアを変更しない。Yahoo取得不能または鮮度超過時は注文直前プレビューをブロックする。
