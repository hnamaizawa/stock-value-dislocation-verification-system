# Target Architecture

## 現在実装済み

```text
J-Quants API V2
  -> Raw snapshot
  -> normalization
  -> Curated snapshot + manifest/hash
  -> company search / stock detail
  -> quantitative shortlist
  -> external-event review queue
```

## 目標

```text
J-Quants / EDINET / TDnet / company IR
  -> immutable raw snapshots
  -> point-in-time normalization and quality gates
  -> price / financial / disclosure feature store
  -> quantitative screen
  -> external-event evidence extraction
  -> mandatory human evidence approval
  -> thesis and invalidation conditions
  -> manually imported SBI portfolio / buying power
  -> portfolio, liquidity, event and order-risk gates
  -> order-ready packet (preview only)
  -> human final review
  -> manual entry in SBI Securities
```

## ゴールに対する分析レーン

- **回復候補（中長期）**: 営業・財務の健全性、株価の下落と市場・業種との差、配当の水準と持続性、外的要因の根拠を合わせて候補を整理する。日々の価格と移動平均・トレンド遷移を示し、反転の兆候と未確認のリスクを分ける。外的要因は価格指標だけで確定せず、一次資料を人がレビューする。
- **予測の事後検証**: 各選定時点で当時利用可能だった価格・財務・銘柄母集団のみから候補を固定し、その後の10/20/30/60/90/120/240/365取引日リターンを別途採点する。各期間の確定件数・未確定件数・中央値・プラス率・下落率を表示し、データ不足や比較可能性の制約も開示する。
- **デイトレード分析**: 流動性、ボラティリティ、日中値幅など短期の値動きに関する情報を独立して整理する。中長期の企業価値・配当スコアや回復候補の成績へ混ぜず、自動売買や利益保証を行わない。

## 現行実装とのギャップ

現在の◎☆実績検証とWalk-Forwardは10/20/30/60/90/180取引日が基本であり、目標の120/240/365取引日は未対応である。保存済み日足の期間に応じて評価できない長期 horizon を省略する既存の制約を維持し、必要データがない期間を推定値で埋めない。外的要因の一次資料レビューや営業実態の確認も、完全自動判定済みとは扱わない。

## モード

- `demo`: 架空データのみ
- `paper`: 実市場データ、注文送信なし。現在の実データモード
- `live-preview`: 実市場データと手動取込した実保有を使う注文直前表示。未実装

`live-auto` は定義しない。

## 再生成アーキテクチャ

canonical repositoryを実行可能テンプレートとし、`app_blueprint.yaml` が必須能力と安全不変条件を定義する。generatorはruntime stateを除外してcloneし、生成manifestで出自とハッシュを記録する。
