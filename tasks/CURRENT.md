## v0.6.63 walk-forward / matched controls / attribution

- [x] point-in-time Walk-Forward検証を追加する。
- [x] 類似非選択銘柄とのリターン比較と選択効果を追加する。
- [x] 市場・業種・企業固有へ分解する外因説明率を追加する。
- [x] 通常表示・条件変更では追加データ取得しない。

## v0.6.62 structural deterioration guards

- [x] 利益現金化率（営業CF÷営業利益）を追加する。
- [x] 営業利益率の直近最大3期の悪化幅を追加する。
- [x] 同一対象年度の会社予想営業利益の修正率を追加する。
- [x] 6か月騰落率の業種中央値比を追加する。
- [x] 欠損は警告、既知の明確な悪化だけを除外する構造悪化ガードを追加する。
- [x] 履歴・仮説無効化・購入判断整理へ新指標を連携する。
- [x] 追加API取得やSBI安全境界の変更を行わない。

## v0.6.61 reversal-confirmed star

- [x] ◎☆を短期反転確認済みの最上位評価へ厳格化する。
- [x] trend_score>=5 / 20日騰落率>=0 / 株価>MA20 / MA20上向き / MA20>MA50 をすべて必須にする。
- [x] 旧◎☆相当だが反転未確認の銘柄は◎として残す。
- [x] 旧ルールと新ルールの適格フラグを同時保存し、実績サマリで前向き比較する。
- [x] 過去の評価を将来情報で再分類しない。

## v0.6.60 legacy outcome compatibility

- [x] 旧star_outcomesに10/20/60日列が無くても条件別実績集計を失敗させない。
- [x] 欠損期間列は未確定（0件）として扱い、既存30/90/180日データを保持する。
- [x] 画面の確定件数とルール学習にも欠損列ガードを追加する。
- [x] 実データ再作成を要求せず、回帰テストで後方互換を固定する。
- [x] 履歴・実績検証の3画面に、表示中データに応じた簡潔な分析結果サマリを表示する。

## v0.6.59 extended validation horizons

- [x] ◎☆実績検証に10日・20日・60日を追加する。
- [x] 10/20/30/60/90/180日の順序を画面・集計・Yahoo更新で統一する。
- [x] 既存30/90/180日の保存結果を保持する。
- [x] 回帰テストを追加する。

## v0.6.58 large-data performance optimization

- [x] 画面遷移・通常設定読込でルール学習本体を実行しない。
- [x] ルール学習の将来リターン計算で全株価表を銘柄ごとに再走査しない。
- [x] データ更新時の全銘柄特徴量計算を1回に統合する。
- [x] 大規模 curated bundle を Streamlit プロセス内で共有し、ページ遷移時のコピーを避ける。
- [x] 回帰テスト・Harness契約・設計文書を追加する。

## v0.6.57 candidate stock detail new tab

- [x] 条件設定・候補の候補一覧で銘柄コード／企業名を新しいブラウザタブで開く。
- [x] 統合候補一覧（抽出条件 + 最新トレンド）でも同じ新タブ動作に統一する。
- [x] 元の候補一覧・条件・ソート状態を保持する。
- [x] v0.6.56 のURLクエリ方式を共通利用し、新しいStreamlitセッションで対象銘柄を自動表示する。
- [x] 回帰テストとHarness契約を追加する。

## v0.6.56 history stock detail new tab

- [x] 履歴・実績検証の銘柄コード／企業名を新しいブラウザタブで開く。
- [x] 元の履歴タブの検索・ページ・ソート状態を保持する。
- [x] URLクエリで銘柄コードを新しいStreamlitセッションへ引き渡し、自動表示する。
- [x] 条件設定・候補画面の既存の同一タブ遷移を維持する。
- [x] 回帰テストとHarness契約を追加する。

## v0.6.19 stronger soft-pastel theme

- [x] Increase pastel feel with pink, lavender, pale blue, and cream background layers.
- [x] Apply the pastel treatment to sidebar, metrics, expanders, tabs, buttons, inputs, alerts, tables, and progress bars.
- [x] Keep the standard theme and all screening/analysis logic unchanged.
- [x] Add a regression test that pastel CSS stays scoped behind the theme guard.
- [x] Verify `harness/app_blueprint.yaml` remains unchanged.

## v0.6.17 natural threshold input display

- [x] Remove forced four-decimal display (`50.0000`) from structured hypothesis invalidation thresholds.
- [x] Preserve v0.6.16 independent per-row widget/session-state behavior so multi-row one-click save remains correct.
- [x] Accept numeric text values and persist them as numeric JSON thresholds.
- [x] Add regression tests for `50`, `7.5`, and `8.25` display/parse behavior.
- [x] Verify `harness/app_blueprint.yaml` remains unchanged.

## v0.6.16 multi-row structured invalidation save fix
- [x] Remove `st.data_editor` from the structured invalidation editor.
- [x] Give every condition row stable per-field widget keys in `st.session_state`.
- [x] Serialize all current rows in one pass when Save is clicked.
- [x] Add regression tests for two-condition single-click save semantics.
- [x] Confirm `harness/app_blueprint.yaml` has no diff.
- [ ] User validation on Windows/Streamlit UI.

# Current task

## v0.6.0

購入判断の整理画面を実装済み。次の優先作業は、外的要因レビューを一次資料と紐づけ、承認済みレビューだけを注文直前パケットへ進めること。

# Current work

Version 0.5.1 implements the immediate performance and SBI CSV bridge improvements.

## Completed

- Explicit `条件を適用` screening form
- One-row-per-security precomputed feature snapshot
- Parquet fast path and CSV fallback
- Resumable incremental J-Quants cache retained
- SBI screening CSV import, encoding detection, column mapping, and shortlist matching
- Harness and generator inheritance

## Next

1. Add scheduled after-market data refresh.
2. Add monthly compaction of raw daily cache files.
3. Add external-event review workflow based on primary disclosures.
4. Add HYPER SBI 2 watchlist export after confirming a stable official CSV layout.
5. Add portfolio and execution-result CSV imports without broker credentials.


## v0.5.4 benchmark policy
正式TOPIXを優先し、取得できない場合だけTOPIX連動ETF（1306、1475、1305）の調整後終値を明示的な代理指標として利用する。代理値は正式TOPIXと表示上・監査上で区別し、両方なければ市場相対条件を保留する。

- [x] v0.6.9: 個別銘柄のあいまい検索と複数候補ダイアログ選択。

- [x] v0.6.10: スコア通過全銘柄と最新トレンド再判定一覧の件数を一致させる。

## v0.6.11 external-event review gate

- [x] `templates/EXTERNAL_EVENT_REVIEW.md` の項目を個別銘柄詳細へ入力フォームとして統合。
- [x] `config/external_event_reviews/<code>.json` に銘柄単位で保存・再読込。
- [x] `approved` 以外、レビュー欠損・破損、必須根拠不足では注文直前プレビューをブロック。
- [x] approvedでもデータ鮮度と既存の人手確認を満たさなければ注文直前プレビューをブロック。
- [x] `scripts/generate_app.py` で保存済み外的要因レビューを生成アプリへコピーしない。
- [x] 外的要因レビューのユニットテスト、生成除外テスト、ハーネス検査を追加。
- [x] `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。


## v0.6.12 optional review fields + Yahoo freshness

- [x] 外的要因レビューの記述項目を任意入力へ変更し、approvedは明示的な人手承認のみを必須条件とする。
- [x] 各入力欄へ薄いプレースホルダー例と入力ガイドを追加。
- [x] 個別銘柄の注文直前プレビュー鮮度判定をYahoo Finance系の日足最終取引日で判定。
- [x] Yahoo取得不能・古い日足では安全側に倒して注文直前プレビューをブロック。
- [x] J-Quantsのpoint-in-timeスコアにはYahooデータを混入させない。
- [x] `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。


## v0.6.13 hypothesis invalidation monitoring

- [x] 外的要因レビューへ構造化仮説無効化条件（指標・比較演算子・閾値・有効/無効・メモ）を追加。
- [x] 既存の自由記述 `invalidation_conditions` は後方互換のまま保持し、自動判定せず要目視確認として表示。
- [x] 最新のcurated feature snapshotに対して構造化条件を毎回再計算。
- [x] `run_real_pipeline` のデータ更新後に `hypothesis_invalidation_latest.csv` を上書き生成し、古い判定結果を入力に使わない。
- [x] 条件照合モジュールからJ-Quants取得を完全分離し、条件変更でfetchを誘発しない。
- [x] 候補一覧と個別銘柄詳細へ抵触・評価不能・要目視確認の警告を表示。
- [x] 抵触/非抵触/再計算/自由記述/取得不能をテスト。
- [x] `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。


## v0.6.14 structured invalidation save timing fix

- [x] `st.data_editor` を外的要因レビューの `st.form` から分離し、編集値を通常rerunで確定してから保存する方式へ変更。
- [x] 保存ボタンを `st.button` に変更し、1回前の構造化条件が保存される事象を修正。
- [x] 保存スキーマと注文前ゲートは変更しない。
- [x] 再発防止テストを追加。
- [x] `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。


## v0.6.15 structured invalidation editor rerun fix

- [x] 構造化仮説無効化条件を銘柄単位の session_state draft で保持。
- [x] Enter / フォーカス移動によるrerun時に保存済みJSONから旧値を再投入しない。
- [x] 保存時・保存後とも最新editor値をdraftと同期。
- [x] 回帰テストを追加。
- [x] `harness/app_blueprint.yaml` の `non_negotiable_invariants` は変更しない。


## v0.6.18 theme + selectable extraction base

- [x] 標準/やわらかパステルのUIテーマ切替を追加。
- [x] 大まかな抽出ルールにvalue_dislocation / active_tradingを追加。
- [x] 60日年率ボラティリティ、20日平均日中値幅、平均絶対騰落率をprice featureへ追加。
- [x] active_tradingの値動き活発度スコアと専用screening funnelを追加。
- [x] 候補後の最新Yahoo日足再確認を維持し、候補スコアへ混入させない。
- [x] 条件変更だけでJ-Quants取得が発生しないことをテスト。
- [x] `harness/app_blueprint.yaml` の差分なしを確認。

- [x] v0.6.24: restore v0.6.22 ☆-only unified candidate filter omitted from v0.6.23 patch; preserve Yahoo >=100 guard and Streamlit width/version fixes; update regression tests.

## v0.6.25 完了
- [x] 日次分析スナップショット履歴
- [x] 統合候補の評価履歴
- [x] ◎☆ 30/90/180日リターン追跡
- [x] 条件別実績集計
- [x] 履歴検索・閲覧ページ

## v0.6.27
- [x] 「履歴・検証」ページをトップナビゲーションへ登録。
- [x] ナビゲーション登録漏れの回帰テストを追加。


## v0.6.28
- [x] 日次分析履歴へ当日の最終評価フィルタを追加。
- [x] selected_for_review と最終評価を別概念として表示。
- [x] 履歴結合・検索の回帰テストを追加。
- [x] app_blueprint.yaml 無変更を確認。


## v0.6.29 未評価理由 + 後日再評価
- [x] 未評価理由を理由別に細分化。
- [x] 当日評価済み / 後日補完 / 未評価を評価状態として履歴表示。
- [x] 表示中の未評価をYahoo過去日足で後日補完。
- [x] 評価対象日より後の株価を切り捨てるpoint-in-timeガードを追加。
- [x] 元の未評価・未評価理由・補完日時・評価対象日を保存。
- [x] 100銘柄以上では後日補完Yahoo取得を開始しない。
- [x] 回帰テスト追加、app_blueprint.yaml無変更を確認。

- [x] v0.6.30: 100件以上の未評価を低速・再開可能な小分けYahooバッチで後日補完する。


## v0.6.31 全件低速ループ再評価
- [x] 100件以上の未評価を最後まで自動ループする明示操作を追加。
- [x] バッチ単位の追加ウェイトと銘柄単位のウェイトを維持。
- [x] 各銘柄の後日補完結果を都度保存し、中断時も完了分を保持。
- [x] 取得失敗銘柄を同一実行内で無限再試行しない。
- [x] 通常の100銘柄以上一括Yahoo取得禁止を維持。
- [x] app_blueprint.yaml 無変更を確認。

## v0.6.32 履歴・実績検証の性能改善

- [x] 履歴画面をセクション単位の遅延読込みへ変更
- [x] 日次分析・評価・◎☆実績・条件別実績をファイル署名ベースでキャッシュ
- [x] ◎☆Yahoo実績更新を明示操作へ変更
- [x] 大量履歴表示をページング
- [x] 通常の検索・ページ移動でJ-Quants/Yahoo外部取得を誘発しない
- [x] app_blueprint.yaml を変更しない


## v0.6.33 ◎☆全履歴の再同期とページャー
- [x] 評価履歴を正本として保存済みstar_outcomesと再同期
- [x] 既存の30/90/180日実績を保持
- [x] ◎☆一覧へ専用ページャーと古い順切替を追加
- [x] 全件対象であることを画面に明示

- [x] v0.6.38 履歴・実績検証3画面へ軽量可視化（評価推移、評価構成、◎☆リターン、条件別リターン）を追加。

- [x] v0.6.39 履歴・実績検証3画面の銘柄一覧から個別銘柄検索へ直接遷移。


## v0.6.64 Walk-Forward hardening

- [x] 同業種の対照群を保持し、不足分だけ同市場から補完する
- [x] 将来リターンを取引セッション基準へ変更する
- [x] 価格・開示のpoint-in-time切断をE2Eテストする
- [x] 会社マスターのカバレッジと生存者バイアス警告を記録・表示する
- [x] 新規不変条件と必須ファイルをHarnessで検査する


## v0.6.65 Walk-Forward performance

- [x] 結果キャッシュをデータ・条件・設定・バージョンで無効化する
- [x] 過去時点の定量特徴量を再利用する
- [x] 将来リターンを銘柄別索引と二分探索で取得する
- [x] 簡易・標準・詳細モードを追加する
- [x] 再現時点と基準日の進捗を表示する
- [x] キャッシュ・索引・進捗の回帰テストとHarness検査を追加する


## v0.6.66 analysis item hover help

- [x] 条件設定・候補・履歴・実績検証・Walk-Forward・個別銘柄の主要項目へ短い説明を追加する
- [x] 分析表の全列へ共通のホバー説明を追加する
- [x] クリック可能な表の列見出しで意味とソート操作を説明する
- [x] 回帰テストとHarness不変条件を追加する


## v0.6.67 historical security master

- [x] J-Quants更新時の銘柄マスターを日付別・不変ファイルへ保存する
- [x] 既存certified curated runから追加API取得なしで履歴を復元する
- [x] Walk-Forwardで評価日以前の最新マスターを使用する
- [x] 履歴未取得時の現在マスターフォールバックとカバレッジを明示する
- [x] 上場廃止相当銘柄の再現、履歴選択、復元境界の回帰テストを追加する
- [x] 履歴マスターを生成アプリへコピーしない


## v0.6.68 analytical history visualizations

- [x] 条件×評価期間の平均リターンヒートマップを追加する
- [x] 平均リターン×プラス率×確定件数の条件別バブル図を追加する
- [x] 任意2期間リターン×◎☆回数の銘柄別バブル図を追加する
- [x] 2期間比較は両期間が確定した同一イベントだけを使う
- [x] 少数観測への注意と確定件数を表示する
- [x] 外部取得を誘発しない回帰テストとHarness契約を追加する
