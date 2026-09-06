# Test and Validation Strategy

## 現在自動化済み

- 4桁/5桁東証コード正規化
- J-Quants V2列から会社、株価、TOPIX、決算への正規化
- fake J-Quants clientによるRaw -> Curated -> manifest -> 検索の統合テスト
- 429発生後のbackoff、再試行、要求間隔切替
- 日別cacheによる再実行時のAPI呼出し省略
- 契約期間外HTTP 400から開始日・終了日を抽出する単体テスト
- 株価・決算・TOPIXの全要求が契約範囲へ調整される統合テスト
- requested/effective期間とsubscription coverageのmanifest記録
- full syncで公式並列range helperを使用しないsource-level検査
- manifestのactual/sampleフラグとSHA-256
- 会社名/コード検索と個別詳細
- scoringとriskの既存単体テスト
- 実データ設定とデモ設定の分離
- SBI秘密情報・ブラウザー自動操作・注文送信禁止
- blueprint必須項目
- generatorが秘密・runtime stateをコピーしないこと
- compileall、pytest、generator self-test

## 実アカウントで必要な検証

- 契約プランごとの取得可能期間とエンドポイント
- 実契約で表示された契約上限日とmanifestの一致
- 実契約での429待機時間、長時間実行、途中停止後の再開
- 連続10営業日の件数・重複・欠損・最終株価日
- 実際の決算列の欠損率と業種差
- 株式分割・併合の調整値
- 休日、週末、将来日を終了日に指定した場合

## 注文直前版までに必要

- ポイント・イン・タイム検証
- 上場廃止を含む過去ユニバース
- 開示訂正・後知恵イベントの防止
- 売買単位、呼値、値幅、流動性、手数料、スリッページ
- 3か月以上のペーパートレード
