# Definition of Done

## Demo — 完了

合成データ、画面、テスト、安全な未送信デモ注文案。

## Actual-data code implementation — 完了

- J-Quants Raw -> Curated
- manifest、実データフラグ、最終株価日、SHA-256
- 実在銘柄検索と個別表示
- 定量候補とレビュー待ち
- デモ混入拒否
- 注文案無効
- fake-client統合テスト
- blueprint/generator self-test

## Actual-data operational validation — 未完了

- ユーザー契約で正常取得
- 連続10営業日以上成功
- 429、部分取得、再開、欠損率の確認
- 主要業種・代表銘柄の目視照合

## Evidence-backed research — 未完了

- EDINET/TDnet/IR文書
- 根拠箇所、文書ハッシュ
- 外的要因の人手承認、期限、再評価
- 仮説無効化条件

## Order-ready preview — 未完了

- 最新保有、買付余力、未約定取込
- Gate 0-6
- 呼値、値幅、決算、権利、売買停止
- 一意ID、有効期限、内容ハッシュ、再承認
- 3か月以上のペーパートレード
- SBI注文送信コードが存在しない

最後の条件を満たすまで、実注文の入力資料として使用しない。
