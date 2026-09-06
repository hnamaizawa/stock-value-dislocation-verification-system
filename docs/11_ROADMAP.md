# Roadmap

## Phase 0: Harness and Baseline — 完了

文書、安全境界、デモ隔離、Windows実行、テスト。

## Phase 1A: J-Quants Actual Data Implementation — 完了

- 実データ取得・正規化
- Raw/Curated/manifest/hash
- TOPIX比較
- 会社検索・個別画面
- 定量候補・レビュー待ち
- API日別キャッシュ
- 実データ注文案無効
- blueprint/generator

## Phase 1B: Actual Account Operational Validation — 次の作業

- ユーザー契約プランとAPIキーで初回取得
- 429・欠損・件数・実際の列を検証
- 連続10営業日以上運転
- 取得失敗・再開手順を調整

## Phase 2: Disclosure Evidence

- EDINET API V2
- TDnet add-onまたは企業IR文書
- PDF/XBRLスナップショット
- 根拠箇所、外的要因、一時性、カタリスト、構造リスクのレビューUI

## Phase 3: Point-in-time Research

- 開示日時、訂正、過去ユニバース、コーポレートアクション
- 現実的バックテスト

## Phase 4: Portfolio Integration

- SBI証券の手動CSV取込
- 保有、約定、未約定、買付余力
- 集中度、重複、残余現金

## Phase 5: Live Preview

- Gate 0-6
- 注文プレビュー、有効期限、内容ハッシュ、再承認
- 決算・権利・売買停止・値幅・呼値チェック
- 3か月以上のペーパートレード

完全自動発注はロードマップに含めない。
