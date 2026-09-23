# Decision Log

## ADR-001: SBI証券への自動発注を行わない

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 国内現物株の一般公開発注APIを前提にできず、Web自動操作には誤発注・認証変更・規約・保守上のリスクがある。
- 結果: システムの最終出力は注文直前案。発注はユーザー本人が行う。

## ADR-002: J-Quantsを主市場データ源とする

- 日付: 2026-08-02
- 状態: Proposed
- 理由: JPX系の個人向け公式APIで、株価・財務・銘柄情報を分析しやすい形式で提供する。
- 未決: 契約プラン、利用料金、取得可能な期間と列の最終確認。

## ADR-003: EDINETを詳細財務の補完に使う

- 日付: 2026-08-02
- 状態: Proposed
- 理由: 営業CF、負債、注記等を法定開示から取得できる。
- 未決: XBRLマッピング方式と対象書類。

## ADR-004: 外的要因は人間承認を必須とする

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 一時要因と構造問題の区別は定量値やLLMだけでは誤判定しやすい。

## ADR-005: デモ、ペーパー、実運用プレビューを分離する

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 合成データを実データと誤認して注文案へ使用する事故を防ぐ。

## ADR-006: 注文案は内容ハッシュに対して承認する

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 承認後の価格・数量・根拠変更を検出し、再承認を強制するため。

## ADR-007: J-Quants実データにはmanifestを必須とする

- 日付: 2026-08-02
- 状態: Accepted
- 理由: デモ混入、古いデータ、部分取得、出所不明を画面上で実データと誤認しないため。
- 結果: manifest不在、`actual_data`/`sample_data`不一致では検索を停止する。

## ADR-008: canonical repositoryとblueprintから同型アプリを生成する

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 実装・文書・Windows起動・安全検査を別々の雛形で管理すると乖離するため。
- 結果: 現在の検証済みリポジトリをcanonical templateとし、runtime stateを除外して生成する。

## ADR-009: Streamlit入力のAPIキーは保存しない

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 初回利用を簡単にしつつ、秘密をファイルや生成物へ残さないため。
- 結果: 入力値は起動中プロセスの環境変数にだけ設定する。永続化はユーザーが明示的に `.env` へ行う。

## ADR-010: J-Quants全銘柄同期は直列・再開可能にする

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 公式range utilityは内部で複数日を並列要求し、長い期間ではHTTP 429を起こしやすい。
- 結果: 株価と決算を日付指定で直列取得し、429 backoff、要求間隔の適応、圧縮日別cache、空日markerを必須とする。
- Guard: source-level harness、429 regression test、cache resume test、blueprint invariant。

## ADR-011: J-Quants要求期間を契約期間へ明示的に調整する

- 日付: 2026-08-02
- 状態: Accepted
- 理由: 契約プランによって最新取得可能日が本日より古く、日別同期の終盤でHTTP 400となる。単に例外を無視すると、データ欠損の理由と実際の基準日が不明になる。
- 結果: 株価APIへの事前probeでエラー本文の契約開始日・終了日を解析し、価格、財務、TOPIXを同じ期間へclampする。要求期間、実効期間、契約期間、警告をmanifestへ残す。
- Guard: parser単体テスト、全データセットclamp統合テスト、dashboard表示検査、blueprint invariant。

## ADR: TOPIX欠損時は代用しない

- Decision: TOPIXがない場合、相対騰落率をNaNとし条件を保留する。
- Reason: 銘柄自身のリターンはベンチマーク相対値と意味が異なり、候補数を誤って変えるため。

## ADR: 古いデータは調査のみ許可

- Decision: データ鮮度上限を超えた場合、検索と学習用途は維持するが注文プレビュー適格性を停止する。
- Reason: 遅延データでの注文直前判断を防ぐため。


## v0.5.4 benchmark policy
正式TOPIXを優先し、取得できない場合だけTOPIX連動ETF（1306、1475、1305）の調整後終値を明示的な代理指標として利用する。代理値は正式TOPIXと表示上・監査上で区別し、両方なければ市場相対条件を保留する。

## ADR-012: 外的要因レビューを銘柄単位のローカル状態として保存し、注文直前プレビューの必須ゲートにする

- 日付: 2026-08-11
- 状態: Accepted
- 背景: 定量スコアだけでは、株価下落が一時的な外的要因か構造的な問題かを証明できない。既存blueprintは `external_event_review_required_before_order_preview` を不変条件としている。
- Decision: 個別銘柄詳細に `templates/EXTERNAL_EVENT_REVIEW.md` と同等の入力フォームを追加し、レビューを `config/external_event_reviews/<4桁銘柄コード>.json` に保存する。承認状態が `approved` で、必要な一次資料・仮説・無効化条件が記入済みの場合のみ外的要因レビューゲートを通過させる。
- Order gate: `pending`、`rejected`、未保存、壊れたJSONは安全側に倒して注文直前プレビューをブロックする。各記述項目は任意であり、approvedは人による明示的な承認を表す。approvedでもデータ鮮度や他の人手確認を上書きしない。
- Generated apps: `config/external_event_reviews` は runtime state とし、`scripts/generate_app.py` で保存済みJSONをコピーしない。生成先には空ディレクトリだけを作成する。
- Blueprint: `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。
- Guard: 保存・再読込、approved/pending/rejected、壊れたJSON、生成時の非コピー、ダッシュボード導線、ハーネス検査を自動テストする。


## ADR-013: Yahoo Finance系の日足を注文プレビューの市場鮮度判定に利用する

- 日付: 2026-08-11
- 状態: Accepted
- 背景: J-Quants無料プランでは分析スナップショットが約3か月遅延し、`stale_data_must_block_order_preview_eligibility` を満たしたまま注文直前の市場鮮度を評価できない。
- Decision: 個別銘柄について `yfinance` 経由のYahoo Finance系日足の最終取引日を市場鮮度ゲートへ使用する。J-Quantsは財務・定量スクリーニングのpoint-in-timeデータとして引き続き分離する。
- Safety: Yahoo Finance系の取得不能・空データ・許容日数超過は鮮度NGとしてブロックする。SBI証券で現在値・板・最新ニュースを確認する既存の人手チェックは維持する。
- Invariant: `external_latest_trend_must_not_modify_point_in_time_screening_score` と `stale_data_must_block_order_preview_eligibility` を維持し、`harness/app_blueprint.yaml` は変更しない。


## ADR-014: 仮説無効化条件は構造化可能な財務条件を最新スナップショットへ再照合する

- 日付: 2026-08-11
- 状態: Accepted
- 背景: 外的要因レビューに保存した仮説無効化条件は、決算更新後に再確認しなければ投資仮説の崩れを見逃す。自由記述だけでは機械判定できない。
- Decision: 既存の `invalidation_conditions` 自由記述を維持し、任意の `structured_invalidation_conditions` を追加する。構造化条件は `metric / operator / threshold / enabled / note` で表し、最新の `security_features` に対して毎回再計算する。
- Recalculation: `run_real_pipeline` が新しいcuratedデータとfeature snapshotを生成した後、保存済みレビューをローカル照合し `hypothesis_invalidation_latest.csv` を上書きする。判定結果はレビューJSONへ保存せず、過去判定をキャッシュしない。ダッシュボードでも現在ロード中のfeature値から再評価する。
- Free text: 自由記述条件は自動判定せず「要目視確認」として表示する。
- Safety: 照合モジュールはネットワークI/OやJ-Quantsクライアントを持たず、条件編集や照合だけでJ-Quants取得を発生させない。`condition_changes_must_not_trigger_jquants_fetch` を維持する。
- Blueprint: `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。


## ADR-015: 構造化仮説条件の編集は Streamlit form 外で確定してから保存する

- 日付: 2026-08-11
- 状態: Accepted
- 背景: `st.data_editor` を `st.form` 内に置くと、セル編集直後の送信で一つ前の editor 値が返り、2回に1回旧値を保存する再現性のある事象があった。
- Decision: 外的要因レビューの入力領域を通常の `st.container` とし、保存操作を `st.button` に変更する。`st.data_editor` の編集は通常のStreamlit rerunで先に確定し、その後の保存クリックで現在値をJSON化する。
- Safety: 保存スキーマ、外的要因レビュー承認ゲート、J-Quants取得条件、生成アプリ除外規則は変更しない。
- Blueprint: `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。
- Guard: ダッシュボードソース回帰テストで、構造化条件editorが外的要因レビュー用 `st.form` に戻されないことを検査する。


## ADR-016: 候補抽出ルールを価値乖離型と値動き活発型に分離する

- 日付: 2026-08-12
- 状態: Accepted
- 背景: 従来は「外的要因で下落しているが経営状況は良い会社」だけを候補化していたが、値動きの大きさと流動性を重視する短期調査用途も必要になった。
- Decision: `screen.selection_strategy` に `value_dislocation` / `active_trading` を追加する。active_tradingは市場・最低株価・20日平均売買代金に加え、60日年率ボラティリティと20日平均日中値幅をハード条件にし、両指標と売買代金のpercentileから値動き活発度スコアを計算する。
- Data boundary: 条件変更は既存のcertified curated snapshotだけを再評価し、J-Quants取得を発生させない。旧snapshotに新特徴量がなければcuratedローカルファイルからメモリ上で再計算する。
- Latest data: Yahoo Finance系の最新日足は候補後の再確認にのみ使い、point-in-time候補スコアへ混入させない。
- Risk: 値動きが大きいことは収益性を意味せず、損失拡大リスクも高い。画面上でも売買推奨ではないことを明示する。
- UI: 分析ロジックと独立した「やわらかパステル」テーマを追加し、標準テーマとの切替を可能にする。
- Blueprint: `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。

## ADR-017: Walk-Forwardは評価日以前の履歴銘柄マスターを使用する

- 日付: 2026-09-23
- 状態: Accepted
- 背景: 現在のCompanyMasterだけで過去を再現すると、後に上場廃止となった銘柄が母集団から落ち、生存者バイアスが生じる。
- Decision: J-Quants実データ更新ごとに日付別CompanyMasterを追記保存し、既存certified curated runからもAPIなしで復元する。Walk-Forwardは評価日以前で最新のマスターを選ぶ。
- Fallback: 該当履歴がなければ現在マスターを使用するが、`universe_source`、利用可否、スナップショット日、経過日数、カバレッジ、警告を結果と画面へ明示する。
- Limitation: 保存・復元された全マスターに存在しない銘柄は再構成できないため、生存者バイアスの完全排除とは表現しない。
- Runtime: 履歴マスターは利用者固有の実データであり、同型アプリ生成物へコピーしない。
- Guard: 履歴選択、certified run限定復元、上場廃止相当銘柄の再現、フォールバック開示を回帰テストとHarnessで固定する。
