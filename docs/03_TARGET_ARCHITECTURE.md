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

## モード

- `demo`: 架空データのみ
- `paper`: 実市場データ、注文送信なし。現在の実データモード
- `live-preview`: 実市場データと手動取込した実保有を使う注文直前表示。未実装

`live-auto` は定義しない。

## 再生成アーキテクチャ

canonical repositoryを実行可能テンプレートとし、`app_blueprint.yaml` が必須能力と安全不変条件を定義する。generatorはruntime stateを除外してcloneし、生成manifestで出自とハッシュを記録する。
