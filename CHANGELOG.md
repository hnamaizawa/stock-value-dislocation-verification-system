## v0.6.63


## v0.6.64

- Walk-Forwardの将来リターンを暦日ではなく取引セッション基準へ変更。
- 類似非選択銘柄を同業種優先で保持し、不足分だけ同市場から補完。
- 価格・財務を再現日時点で事前切断し、将来データ混入防止E2Eテストを追加。
- 会社マスターのカバレッジと欠落数を記録し、生存者バイアスの限界を画面表示。
- Walk-Forward固有の不変条件と必須ファイルをHarnessで検査。
- point-in-time Walk-Forward過去検証を追加。選定時点より後の価格・開示は選定に使用しない。
- 同業種優先の類似非選択銘柄マッチングを追加し、候補リターンとの差を選択効果として10/20/30/60/90/180日で評価。
- 6カ月騰落を市場・業種・企業固有要因へ分解する外因説明率を追加。因果証明ではなく外的要因レビューを置換しない。
- Walk-Forwardはローカルcertifiedデータの明示実行のみで、追加API取得を行わない。

## v0.6.62
- 利益現金化率（営業CF÷営業利益）、営業利益率の直近最大3期変化、同一対象年度の会社予想修正率、6か月騰落率の業種中央値比を追加。
- 4指標を「構造悪化ガード」として候補抽出へ追加。欠損は警告扱い、既知の悪化だけを除外する。
- 個別の購入判断整理と◎☆品質判定にも新指標を反映し、既知の構造悪化が最上位評価へ上がらないようにした。
- 新指標をpoint-in-time履歴、外的要因レビューキュー、仮説無効化条件へ追加。追加API取得は行わない。
- 有利子負債はJ-Quants決算サマリーでは欠損のため、レバレッジ必須判定はEDINET補完まで保留。

## v0.6.61
- ◎☆を「品質条件を満たす」だけでなく短期反転を確認した最上位評価へ厳格化。
- 追加必須条件: trend_score>=5、20日騰落率>=0、株価>MA20、MA20上向き、MA20>MA50。
- 旧◎☆相当だが反転未確認の銘柄は◎へ降格し、「反転確認待ち」と明示。
- v0.6.61以降の評価履歴に旧ルール/新ルール双方の適格フラグを保存し、実績サマリで新旧のイベント数と20日成績を前向き比較。
- 過去の◎☆履歴は推測で再分類せず、そのまま保持。

## v0.6.60
- 旧 `star_outcomes.csv(.gz)` に新設の10/20/60日列が無い場合、空の数値Seriesとして扱う後方互換処理を追加。
- `condition_performance()` の `numpy.float64` に対する `.dropna()` AttributeErrorを修正。
- ◎☆確定件数表示とルール学習側にも同じ欠損列ガードを追加し、旧履歴を削除・再作成せず利用可能にした。
- 「履歴・実績検証」の日次分析履歴・評価履歴・◎☆実績検証に、表示中データだけで生成する簡潔な分析結果サマリを追加。

## v0.6.59
- 「履歴・実績検証 > ◎☆実績検証」の評価期間に10日・20日・60日を追加し、10/20/30/60/90/180日の順で表示。
- Yahoo日足による実績更新、銘柄別平均、イベント詳細、条件別実績集計を同一の共通期間定義へ統一。
- 既存30/90/180日データとの後方互換を維持し、新期間は再評価・Yahoo実績更新で段階的に補完。

## v0.6.58
- 通常の `load_config()` から重いルール学習更新を分離し、保存済みルールの適用だけを行う軽量パスへ変更。ルール学習は実データ更新時に明示的に1回実行。
- ルール学習の将来リターン照合を、各銘柄ごとの全株価DataFrame再フィルタから、1回だけ構築する銘柄別株価ルックアップへ変更。
- `prepare_quantitative_universe()` を更新1回につき1度だけ実行し、特徴量スナップショット保存と定量判定で同じ結果を再利用。
- Streamlit の大規模 curated bundle を `st.cache_resource` で共有し、画面遷移・別タブセッションでの巨大DataFrameのシリアライズ／コピーを削減。
- 性能最適化の回帰テストと設計ドキュメントを追加。データ取得契約、安全境界、外的要因レビューの意味論は変更なし。

## v0.6.57
- 「条件設定・候補」の候補一覧と統合候補一覧で、銘柄コード／企業名を新しいブラウザタブで開くよう変更。
- v0.6.56 で導入したURLクエリ方式を共通化し、新しいStreamlitセッションで対象銘柄を個別銘柄検索へ自動設定。
- 元の候補一覧、条件、ソート状態を維持し、個別確認後は新しいタブを閉じるだけで一覧作業へ戻れるようにした。
- 抽出ロジック、データ取得、外的要因レビュー、SBI安全境界は変更なし。

## v0.6.56
- 「履歴・実績検証」の日次分析履歴・評価履歴・◎☆銘柄サマリ・◎☆イベント詳細で、銘柄コード／企業名を新しいブラウザタブで開くよう変更。
- `st.link_button` とURLクエリの銘柄コードを使い、新しいStreamlitセッションでも対象銘柄を個別銘柄検索へ自動設定。
- 元の履歴タブの検索条件・ページ・ソート状態を維持し、個別確認後は新しいタブを閉じるだけで一覧作業へ戻れるようにした。
- 条件設定・候補画面の既存の同一タブ遷移、分析ロジック、データ取得、安全境界は変更なし。

## v0.6.55
- 「履歴・実績検証」の期間初期値で残っていた `pd.Timedelta(days=30).to_pytimedelta()` を Python 標準の `datetime.timedelta(days=30)` へ変更。
- NumPy の generic timedelta DeprecationWarning が Streamlit 再実行時に大量出力される問題を解消。
- 警告の抑制ではなく原因式を除去し、同じ非推奨表現が dashboard.py に再導入されない回帰テストを追加。
- 抽出条件、履歴データ、J-Quants / Yahoo データ取得、安全境界は変更なし。

## v0.6.53
- 一覧のソート状態更新を `on_click` コールバックへ移し、明示的な追加 `st.rerun()` を廃止して1クリックあたりの再実行回数を削減。
- 候補一覧、統合候補一覧、履歴一覧を `st.fragment` 化し、ソート時の再実行範囲を表部分へ限定。統合候補一覧ではYahoo最新トレンド取得・再判定をソート時に再実行しない構成へ変更。
- DataFrameへ一時ソート列を追加する方式をやめ、`sort_values(..., key=...)` で直接ソートする軽量実装へ変更。
- READMEをタイトル／現行バージョン／開発履歴（新しい順）／Windows・WSL運用／GitHub・CI／データ取得／安全境界へ再構成し、散在していたバージョン履歴を上段へ集約。
- 分析ロジック、候補抽出、Yahoo/J-Quantsデータ契約、安全境界は変更なし。

## v0.6.52
- ボタン式一覧の列見出しをクリック可能にし、同じ列を押すたびに昇順／降順を切り替えるソート機能を復活。
- 統合候補一覧、候補ボタン一覧、履歴・検証の各銘柄一覧へ共通ソート操作を適用。
- 履歴一覧はページング前にソートし、検索結果全体の並び順へ反映。
- 銘柄コード／企業名ボタンによる個別銘柄遷移、分析ロジック、データ取得、安全境界は変更なし。

## v0.6.51
- Streamlit 1.53.0 互換性修正として、個別銘柄ニュースの `st.link_button()` から未対応の `key=` 引数を削除。
- `TypeError: ButtonMixin.link_button() got an unexpected keyword argument 'key'` の再発防止テストを追加。
- 分析ロジック、データ取得、テーマ、安全境界は変更なし。

## v0.6.50
- テスト用の「やわらかパステル」テーマを、ピンク／オレンジ／ラベンダー／水色／ミントの多色パステルへ大幅に強調。
- 背景・サイドバー・メトリクス・カード・タブ・ボタン・入力欄・表・アラート・プログレス表示の彩度、境界線、影を強化。
- パステルテーマ分岐内のCSSだけを変更し、標準テーマと分析・スコア・データ取得ロジックは変更なし。

## v0.6.41
- アプリ名を `Stock Value Dislocation Verification System` へ変更し、README、Streamlit画面タイトル、セットアップ表示、Python配布名、Harnessのcanonical projectを統一。
- `SBI CSV取込` やSBI証券への自動ログイン・自動発注禁止など、実機能・安全境界として必要なSBI表記は維持。
- GitHub Actions CIを追加し、push / pull request時に `python -m pytest tests/` とHarness検査を自動実行。
- GitHub公開前提のメタデータから旧アプリ名を除去。

## v0.6.40
- 「履歴・実績検証」の日次分析履歴・評価履歴・◎☆銘柄サマリ・◎☆イベント詳細の個別銘柄遷移を、統合候補一覧と同じ「銘柄コード／企業名ボタン」に統一。
- Streamlit dataframe の行選択チェックボックスによる遷移を廃止。
- ボタン描画による性能低下を抑えるため、履歴一覧は25/50/100/200件のページングを利用し、標準50件表示。全列は折りたたみ表で確認可能。

## v0.6.39
- 履歴・実績検証の日次分析履歴・評価履歴・◎☆銘柄サマリ・◎☆イベント詳細で、銘柄行をクリックすると個別銘柄検索へ遷移できるようにしました。
- 大量履歴の性能を維持するため、個別ボタンを大量生成せず Streamlit dataframe の単一行選択を利用します。

## v0.6.38
- 「履歴・実績検証」の3セクションに、既読データだけで描く軽量な可視化を追加。
- 日次分析履歴に最終評価件数の時系列、評価履歴に最終評価構成、◎☆実績検証に30/90/180日平均リターンを追加。
- 条件別実績には30/90/180日を切り替えられる平均リターン比較グラフを追加。
- グラフ描画ではYahoo/J-Quantsを追加取得せず、既存の遅延読込み・キャッシュ・ページングを維持。

## v0.6.37
- 「履歴・実績検証 > ◎☆実績検証」の一覧を銘柄コード単位でサマリし、同一銘柄を1行表示に変更。
- 初回◎☆日、最新◎☆日、◎☆回数、最新entry_price、確定済み30/90/180日平均リターンと件数を表示。
- 必要時のみイベント単位の詳細一覧を展開でき、元のイベント履歴・実績計算は保持。

## v0.6.36
- 履歴・実績検証で累積履歴の `selected_for_review` が重複列／非標準形になった場合でも、必ず1次元booleanマスクへ正規化して処理するよう修正。
- `out.loc[...]` へ渡す対象外マスクを位置ベースのboolean配列に固定し、`TypeError: unhashable type: 'Series'` を防止。
- 重複 `selected_for_review` 列と非標準indexを再現する回帰テストを追加。

## v0.6.35

- 履歴・実績検証で `selected_for_review=False` の銘柄を「未評価」ではなく「評価対象外（定量候補外）」として分類。
- 「評価状態=未評価」は、本当に最終評価が未解決の定量候補だけを返すよう修正。
- 金曜に未評価候補を全件補完済みで週末に新規分析がない場合、未評価件数が原則0件になる意味論へ修正。
- 過去履歴も画面読込時に `selected_for_review` から再分類するため、既存42,447行を削除せず表示を正常化。

## v0.6.34

- Fixed history rows appearing as unassessed again after a completed slow backfill when a later non-market run produced an identical analysis snapshot.
- Suppress new daily analysis history files when `data_as_of` and the complete analytical payload are unchanged from the prior saved day.
- Collapse already-saved identical consecutive snapshots at history-read time, preserving genuinely changed criteria/results.
- Harden `selected_for_review` parsing so persisted string values such as `False` are never treated as truthy.

## v0.6.33

- 「履歴・実績検証」の◎☆実績一覧を評価履歴と再同期し、初期の◎☆イベントを含む全件を表示対象に修正。
- 保存済み30/90/180日リターンはイベントキー（code + star_date）で保持し、再同期で失わない。
- ◎☆一覧に25/50/100/200件の表示件数、前へ／次へ、ページ番号、全件数表示を追加。
- 新しい順／古い順を切り替え可能にし、古い◎☆銘柄へ直接たどりやすくした。
- `harness/app_blueprint.yaml` は変更なし。

## 0.6.32

- 「履歴・実績検証」を遅延読込み化し、選択中セクションだけを実行する構造へ変更。
- 日次分析履歴・評価履歴・◎☆実績のファイル更新時刻/サイズをキーに Streamlit キャッシュを利用し、通常の検索やページ移動でgzip CSVを再読込しない。
- ◎☆実績のYahoo日足更新を自動実行から明示ボタン実行へ変更し、履歴画面を開いただけでは外部アクセスしない。
- 日次履歴・評価履歴・◎☆イベントに100/200/500/1000件のページングを追加し、大量行を一度にブラウザへ送らない。
- 条件別実績集計を履歴ファイル署名でキャッシュし、履歴が変わらない限り全履歴スキャンを繰り返さない。
- 保存済み `star_outcomes.csv.gz` を直接読み込む `load_star_outcomes` を追加。

## 0.6.31

- 100銘柄以上の未評価に対する低速再評価へ「全件を最後まで自動ループ」モードを追加。
- 10/20/50銘柄の選択バッチ境界ごとに追加ウェイトを入れつつ、全未評価ユニーク銘柄を1回ずつ順番に試行。
- 各銘柄の結果は従来どおり都度upsertし、途中終了しても完了分を保持。
- Yahoo取得失敗銘柄は同一実行内で無限再試行せず未評価のまま残し、後日の再実行対象とする。
- 通常の一括Yahoo取得100銘柄制限は変更なし。
- `harness/app_blueprint.yaml` は変更なし。

## 0.6.30

- 100銘柄以上の未評価に対して、通常の一括Yahoo再評価は引き続きブロックしつつ、明示操作の低速バッチ再評価を追加。
- 低速バッチは10/20/50銘柄から選択し、既定20銘柄を約0.75秒間隔で順次処理。
- 各銘柄の後日補完結果をその都度履歴へupsertするため、中断・再読み込み後も未評価分から続行可能。
- 1銘柄に複数の分析日がある場合はYahoo日足を1回だけ取得し、対象日の全未評価行をpoint-in-timeで再評価。
- 通常の候補一覧・一括Yahoo取得の100銘柄制限は変更なし。
- `harness/app_blueprint.yaml` は変更なし。

## 0.6.29

- 履歴・実績検証の「未評価」を理由別（評価履歴なし / Yahoo取得失敗 / Yahoo100件制限 / 旧履歴 / 履歴不足・再現不能 / その他）に細分化。
- 統合候補評価の保存時に評価状態と未評価理由を記録し、日次分析履歴へ結合表示。
- 表示中の未評価を明示操作で後日再評価する機能を追加。Yahoo過去日足は元の分析日で切り、未来データを使わないpoint-in-time再評価とした。
- 後日補完では original_final_evaluation / original_unassessed_reason / evaluated_at / evaluation_as_of を保持。
- 後日再評価でもYahoo対象100銘柄以上は取得を開始しない。
- 履歴スナップショットへ benchmark_source / forecast_dividend_change_rate を追加し、今後の再現性を改善。
- `harness/app_blueprint.yaml` は変更なし。

## 0.6.28
- 「履歴・検証」の日次分析履歴に「当日の最終評価（◎☆ / ◎ / ○ / △ / × / 未評価）」検索条件を追加。
- `selected_for_review`（定量条件通過）と `final_evaluation`（最新トレンド等を含む最終評価）を明確に分離して表示。
- 同日・同銘柄・同抽出ルールの評価履歴を日次分析履歴へ結合し、過去履歴にも後方互換で適用。
- `harness/app_blueprint.yaml` は変更なし。

## 0.6.27
- 「履歴・検証」ページをトップナビゲーションへ登録し、実装済み画面がメニューに表示されない不具合を修正。
- 履歴ページ定義だけでなく `st.navigation` への登録まで検証する回帰テストを追加。

## 0.6.26

- Fixed pandas/NumPy generic timedelta deprecation warnings in history forward-return calculations.
- Replaced `pd.Timedelta(days=int(horizon))` with explicit-day `pd.to_timedelta(int(horizon), unit="D")`.
- No behavior change to 30/90/180-day return calculations.

## 0.6.25
- 日次の定量分析を `data/history/analysis/YYYY-MM-DD.csv.gz` へ保存し、同日再実行は上書き。
- 統合候補一覧の◎☆/◎/○/△/×と最新Yahoo株価を日次評価履歴として保存。
- ◎☆への遷移をイベント化し、保存済み評価から30/90/180日後リターンを自動更新。
- 履歴・検証ページを追加し、期間・銘柄・評価・抽出ルールで検索可能。
- ◎☆イベントについて標準条件別の平均リターン・プラス率を探索的に集計。
- 履歴データは生成アプリへコピーしない。

## 0.6.24

- v0.6.23 patch was inadvertently based on v0.6.21 and omitted the v0.6.22 ☆-only display filter. Restored the ☆-only unified-candidate filter while preserving the v0.6.23 Yahoo bulk-fetch guard and Streamlit compatibility changes.
- ☆ filtering is performed only after the latest Yahoo Finance trend recheck and never triggers J-Quants refetch.
- Unified-list integrity is always checked against the unfiltered `all_result`; ☆ filtering only changes the displayed rows.
- Updated harness regression tests to validate the current unified-list function shape instead of obsolete literal call text.

## 0.6.23

- Yahoo Finance系の一括最新株価・日足取得は対象が100銘柄以上の場合に開始せず、統合候補一覧へ警告と「未実施」を表示。
- 個別銘柄のYahoo Finance系取得は従来どおり利用可能。
- 保留対応: Streamlit `use_container_width=True` を `width="stretch"` へ移行。
- 保留対応: Dashboard依存のStreamlitを `1.53.0` に固定。

## 0.6.21
- 外的要因レビューの未保存初期値を、編集可能な標準サンプルで事前入力。承認ステータスは安全のため pending を維持。
- 「定量候補」と「最新トレンド再判定」を単一の統合候補一覧へ統合。スコア通過全銘柄を同一母集団としてリンク・直感評価・最新Yahooトレンド・仮説警告を同じ行に表示。
- Yahoo取得失敗銘柄も統合一覧から除外せず判定不能として保持。

## 0.6.20

- Persist the selected UI theme in `config/ui_preferences.json` so refresh/new Streamlit sessions restore the same theme.
- Keep UI preferences out of generated applications to avoid copying local personalization.
- Theme changes remain presentation-only and never trigger J-Quants fetches.

## v0.6.19

- 「やわらかパステル」テーマをより淡く可愛らしい配色へ調整。
- 背景、サイドバー、カード、タブ、ボタン、入力欄、メトリクス、表枠、プログレス表示をパステル調で統一。
- 標準テーマおよび分析・スコアリングロジックには変更なし。

## v0.6.18

- 画面テーマを「標準」「やわらかパステル」から切り替え可能に追加。分析ロジックはテーマに依存しない。
- 大まかな抽出ルールへ「外的要因で下落 × 経営良好」と「値動き活発（デイトレ候補）」を追加。
- 値動き活発型では60日年率ボラティリティ、20日平均日中値幅、20日平均売買代金から値動き活発度スコアを算出。
- 値動き活発型の条件変更は取得済みfeature snapshotだけを再評価し、J-Quants取得を誘発しない。
- 旧snapshotに新しい値動き特徴量がない場合も、curatedローカルデータからメモリ上で再構築する。
- 候補後の最新トレンド確認ではYahoo Finance系の日足を使い、候補スコアには混入させない。
- `harness/app_blueprint.yaml` は変更なし。

## v0.6.17

- Structured hypothesis invalidation threshold input no longer forces four decimal places.
- Replaced the threshold `number_input(format="%.4f")` with a keyed numeric-text input so values display naturally (for example `50`, `7.5`, `8.25`) while preserving the v0.6.16 per-row session-state save fix.
- Added regression coverage for natural threshold formatting and numeric parsing.

## v0.6.16
- Replaced the structured invalidation-condition `st.data_editor` with stable per-row Streamlit widgets.
- Fixed multi-row edits where the second or later condition could save the previous value on the first Save click.
- Added one-pass serialization of all current structured-condition rows and regression coverage for two-row saves.
- `harness/app_blueprint.yaml` remains unchanged.

# Changelog

## 0.6.14
- Fixed structured hypothesis-invalidation edits sometimes saving the previous value when the data editor and submit button were inside the same Streamlit form.
- Moved the review editor to normal Streamlit rerun semantics and save with a dedicated button.
- Added a regression guard preventing the structured editor from being placed back inside the review form.


## 0.6.13
- Added structured financial hypothesis-invalidation conditions to saved external-event reviews.
- Re-evaluate saved conditions from the newest local feature snapshot after every real-data update without triggering additional J-Quants fetches.
- Show breach/manual-review warnings in candidate trend lists and individual stock details.
- Preserve free-text invalidation conditions as manual-review items.

## v0.6.10
- Fixed the latest-trend recheck list so its row count matches every stock that passed the quantitative score.
- Removed the hidden 20-stock cap from latest external trend re-evaluation.
- External-history failures now remain visible as 判定不能 rows rather than disappearing.
- Added explicit counts for score-passed, recheck rows, successful external-history fetches, and failures.
- Kept the separate max-review-queue limit only for the main clickable candidate list.

## 0.6.9
- 個別銘柄検索を日本語向けのあいまい検索へ改善。全半角・英字大小・ひらがな/カタカナ・企業種別表記を正規化。
- 部分一致に加えて軽い入力ミスを SequenceMatcher で候補化。
- 複数候補がある場合は先頭銘柄を自動採用せず、ダイアログで利用者が明示選択する方式へ変更。
- 候補ダイアログは初期未選択とし、選択するまで個別銘柄を表示しない。
- あいまい検索と候補選択の回帰テスト、ハーネス検査を追加。

## 0.6.8
- 個別銘柄検索に株価・20日/50日/200日移動平均線のPlotlyグラフを追加。
- 約3カ月前の位置、最新株価、買い検討価格帯、追いかけ買い上限、再評価ラインをグラフ上に可視化。
- 主要な財務・業績・トレンド項目に明確な欠点がない買い候補へ「☆」を付与。
- グラフ用移動平均データ生成と☆判定の回帰テストを追加。

## 0.6.7
- Fixed root package `__init__.py` corruption that caused `ModuleNotFoundError: value_dislocation.buy_readiness`.
- Added regression tests that distinguish the root package initializer from `decision/__init__.py`.
- Added a repair patch containing both initializer files at their exact paths.

## 0.6.5
- NumPy timedeltaのgeneric unit警告を避けるため、日数差分を `pd.to_timedelta(..., unit="D")` で明示。
- DeprecationWarningをエラー扱いにする回帰テストを維持。


## 0.6.4
- Cast trend lookback days to a Python int before constructing pandas Timedelta.
- Added a regression test that treats DeprecationWarning as an error for NumPy integer lookback values.

## 0.6.2 - 2026-08-07

- スコア通過銘柄をYahoo Finance系の最新日足系列で再判定。
- 約3カ月前と最新時点のトレンドを比較し、下降継続、底打ち兆候、下降脱出可能性、上昇転換確認へ分類。
- 個別銘柄画面のトレンド判定を、取得可能な場合は外部最新日足へ切替。
- 外部最新トレンドは候補スコアやポイント・イン・タイム分析値へ混入させない。
- テスト、ハーネス、blueprint、生成仕様を更新。

## v0.6.1

- 上部ナビゲーションのフォントと高さを拡大。
- 個別銘柄画面に20日・50日・200日移動平均、RSI、20日騰落率、出来高比を追加。
- 上昇トレンド、上昇転換、もみ合い、下向きトレンドを判定。
- 落ちるナイフ、下落加速、買われ過ぎ、20日安値圏を警告。
- 買いタイミングを支える兆候と、待つ・売る判断につながる兆候を分離表示。
- 売却・撤退条件の例を表示し、購入判断JSONにもトレンド情報を保存。

# Changelog

## v0.6.0

- 個別銘柄画面へ「購入判断の整理」を追加。定量根拠の充足度、有利材料、注意・不足、反対材料を一画面に集約。
- 財務・営業CF・会社予想の重要な弱点がある場合は「見送り優先」とする説明可能な判定を追加。
- 最新IR、外的要因、一時性、回復カタリスト、失敗条件、SBI現在値、決算日を人が確認する注文前チェックリストを追加。
- 投資上限と許容損失率を入力し、100株単位の3段階分割買い参考案と上限損失額を表示。
- 判断内容、未確認項目、分割買い案をJSONの購入判断メモとして保存可能。
- 「買い推奨」や利益保証ではなく、追加確認後の条件付き検討までに限定する安全境界を維持。

## v0.5.10

- 個別銘柄画面の表示順を、アナリスト評価・目標株価を先、関連ニュース・市場コメントを最後へ変更。
- 日本語以外のニュース見出し・要約を機械翻訳し、翻訳表示と原文展開を追加。
- 翻訳失敗時は原文を維持し、画面全体を停止しないフォールバックを追加。
- 外部評価、評価平均、対象アナリスト数、平均目標株価、目標株価乖離、低値・中央値・高値へホバー説明を追加。
- 翻訳処理のテスト、表示順とヘルプ項目のハーネス検査を追加。

## v0.5.9

- 個別銘柄の主要指標タイトルへマウスホバー説明を追加。
- Yahoo Finance系の関連ニュース・市場解説を最大10件表示。
- Yahoo Finance系のアナリスト評価、対象人数、目標株価レンジを表示。
- Yahoo!ファイナンス掲示板の本文は規約・著作権・安定性のため自動取得せず、確認リンクを表示。
- SBI証券のレーティングはログイン後の確認リンクと操作案内を表示し、認証情報や契約データは取得しない。

## 0.5.6

- Fixed crash when the official TOPIX value column is absent but ETF proxy data is available.
- Optional benchmark columns are now always normalized to index-aligned pandas Series.
- Added regression tests for auto and official-only benchmark modes with missing columns.

# Changelog

## v0.5.5
- Fixed `NameError: benchmark_mode is not defined` in the condition builder.
- Added the market benchmark selector inside the screening form.
- Added disabled-state handling when market comparison is turned off.
- Added regression coverage for benchmark_mode definition and use.

## 0.5.4 - 2026-08-04

- 正式TOPIXを最優先する市場比較ロジックを追加。
- 正式TOPIXがない場合は1306、1475、1305の順で、J-Quants株価キャッシュ内の調整後終値を代理利用。
- 代理利用中は画面、候補監査、実行ステータスへ明示し、正式TOPIXとは区別。
- 条件画面から「自動・正式TOPIXのみ・ETF代理のみ・無効」を選択可能。
- 正式TOPIXとETF代理値がどちらもない場合は、従来どおり相対条件を保留。
- 注文前にはSBI証券の最新株価・開示確認が必要という安全境界を維持。

## 0.5.3 - 2026-08-04

- Replaced the horizontal radio-style screen selector with Streamlit top navigation tabs.
- Preserved candidate-code and company-name navigation to the selected stock detail page.
- Added dividend metrics, arbitrary-share gross/after-tax/NISA estimates, and investment amount to individual stock search.
- Added dividend fields to the individual company financial summary table.
- Raised the Streamlit minimum version to 1.46 for top navigation support.
- Updated tests, harness, documentation, and generator blueprint.

## 0.5.2

- J-Quants financial summary dividend fields are normalized and aggregated per security.
- Added mandatory dividend filters: dividend availability, annual dividend per share, forecast yield range, payout ratio, and forecast dividend cut.
- Added clear gross, taxable-account after-tax estimate, NISA estimate, and required investment for any share count.
- Added dividend data source and disclosure date to candidate explanations.
- Updated presets, profiles, tests, harness, and generator blueprint.

## 0.5.1 - 2026-08-04

- 投資スタイルの選択をフォーム外へ移し、選択直後に各条件パラメータへ反映。
- 候補一覧の証券コードと企業名をクリック可能なボタンへ変更。
- 候補クリック時に「個別銘柄検索」画面へ移動し、対象銘柄を自動選択。
- 画面切替を状態管理可能な横並びナビゲーションへ変更。
- 即時プリセット反映と候補→個別銘柄遷移をハーネス要件へ追加。

## 0.5.0 - 2026-08-03

- 条件UIをStreamlitフォーム化し、「条件を適用」時だけ再計算
- 株価・財務の銘柄別特徴量を更新時に事前計算しParquetへ保存
- ダッシュボードは約4,000行の特徴量スナップショットを優先読込
- CSVフォールバックを維持し、データ来歴と安全境界を継続
- 既存の日別キャッシュによる増分・中断再開取得を明文化
- SBI証券スクリーナーCSVの文字コード・列名自動判定と候補突合を追加
- generator、blueprint、harness、testsを更新


## 0.4.0 - 2026-08-02

- 初心者向け3プリセットと動的条件設定UIを追加
- 閾値非依存の指標計算と高速な条件適用を分離
- 選別ファネル、候補理由、近似不合格理由を即時更新
- 条件プロファイル保存・読込・JSON/CSV出力を追加
- 保存済みユーザープロファイルをgenerator除外対象へ追加
- tests、harness、blueprint、generator、運用文書を更新

## 0.3.4 - 2026-08-02

- TOPIX欠損時の相対リターン代用を廃止し、NaNと明示警告へ変更
- 説明可能な必須条件監査、選別ファネル、候補理由カードを追加
- データ鮮度と注文プレビュー適格性ゲートを追加
- 営業CF、売上CAGR、営業利益率の必須条件を追加
- harnessとgeneratorへ回帰防止条件を追加

## 0.3.3 - 2026-08-02

- Fixed HTTP 400 failures when the requested end date is newer than the active J-Quants subscription coverage.
- Added parsing of the API-provided subscription date window and automatic clamping of price, financial, and TOPIX requests.
- Added requested/effective date windows and detected subscription coverage to the provenance manifest and run status.
- Added dashboard visibility for the subscription data cutoff and date-adjustment warnings.
- Preserved the resumable daily cache and 429 backoff behavior from 0.3.2.
- Added regression tests, harness checks, blueprint invariants, and generator inheritance for subscription-window handling.

## 0.3.2 - 2026-08-02

- Fixed repeated HTTP 429 failures caused by the official concurrent range helpers.
- Replaced full-sync price and financial range calls with serial per-date retrieval.
- Added adaptive 429 backoff and a conservative post-429 request interval.
- Added resumable compressed daily caches for prices and financial summaries, including empty-day markers.
- Added optional endpoint degradation for plan-restricted TOPIX and earnings-calendar access.
- Added regression tests and harness checks for serial retrieval, backoff, cache resume, and generator inheritance.

## 0.3.1 - 2026-08-02

- Fixed HTTP 400 from J-Quants V2 `/equities/bars/daily` when retrieving all stocks by date range.
- Replaced the invalid no-code `get_eq_bars_daily(from,to)` call with the official `get_eq_bars_daily_range(start_dt,end_dt)` utility.
- Added a safe per-date fallback that always supplies `date_yyyymmdd`.
- Added regression tests and a harness check that reject from/to-only all-stock calls.
- Updated the application blueprint and generator version so newly generated apps retain the fix.

## 0.2.0 - 2026-08-02

- Added a development harness for continuing toward a real-data, order-preview system.
- Added project charter, current status, target architecture, data sources, data contracts, strategy, risk gates, security, testing, operations, roadmap, decision log, known issues, definition of done, and official source register.
- Added `AGENTS.md`, `HARNESS.md`, task files, review templates, and a real-data example configuration.
- Added executable safety and consistency checks through `check_harness.cmd` and `scripts/harness_check.py`.
- Explicitly separated demo, paper, and live-preview modes; automatic SBI order transmission remains prohibited.

## 0.1.2

- Fixed `run_demo.cmd` so it starts the Streamlit dashboard after generating demo outputs.
- Added `start_dashboard.cmd` to reopen the dashboard without rerunning the analysis.
- Switched Windows launch commands to `python -m ...` for more reliable virtual-environment execution.

## 0.1.1 - 2026-08-02

- Replaced the Windows setup PowerShell script with an ASCII-only version.
- Removed the requirement for the `py` command.
- Added direct `python.exe` detection and a WinGet Python 3.12 fallback.
- Added the missing `.env.example` file.
- Changed the daily script to use the project virtual environment directly.

## 0.5.7
- 個別銘柄検索の主要指標名に初心者向け比較目安を追加。
- 同業種の有効データが5社以上ある場合は、固定値より同業中央値を優先表示。
- 同業中央値を算出できない場合は、営業利益率10%、自己資本比率40%、配当利回り3%などの一般目安を表示。
- 配当受取額と概算投資額の項目名に計算内容を明示。

## v0.5.8
- 欠損する予想配当利回りを予想年間配当と表示株価から再計算。
- Yahoo Finance系の最新取得値をyfinance経由で参考表示し、J-Quants分析値と分離。
- 同業中央値・一般目安の括弧内表示を小さいフォントへ変更。

## v0.6.6
- スコア通過銘柄の最新トレンド再判定へ、◎ 買い候補／○ 条件付き候補／△ 様子見／× 見送りの直感判定を追加。
- 個別銘柄画面へ買い検討価格帯、追いかけ買い上限、再評価ラインを追加。
- 価格帯は最新外部株価、20日・50日移動平均、20日・60日安値、RSI、下降トレンド脱出状況から説明可能な形で算出。
- 判断は利益保証・売買推奨・自動注文ではなく、SBI証券での最終確認前の調査補助として維持。

## v0.6.11

- 個別銘柄詳細に外的要因レビュー入力・保存フォームを追加。
- `config/external_event_reviews/<code>.json` にレビューを保存し、未保存・pending・rejected・破損・根拠不足は注文直前プレビューをブロック。
- approvedでもデータ鮮度と既存人手確認を満たさなければ注文直前プレビューをブロック。
- 保存済み外的要因レビューを生成アプリへコピーしないようgeneratorを更新。
- ADR、CURRENT task、known issues、テスト、harnessを更新。
- `harness/app_blueprint.yaml` は変更なし。


## v0.6.12

- 外的要因レビューの各記述項目を任意入力化。approvedは人の明示承認として扱い、空欄は補足ガイドとして表示。
- 外的要因レビューにプレースホルダー形式の入力例とガイドラインを追加。
- 個別銘柄の注文直前プレビューにおける市場鮮度をYahoo Finance系の日足最終取引日で判定。
- Yahoo日足が取得不能・空・許容日数超過なら注文直前プレビューをブロック。
- J-Quantsの分析スナップショットとYahoo最新市場データの役割を分離したまま維持。
- `harness/app_blueprint.yaml` は変更なし。


## v0.6.15

- 構造化仮説無効化条件の data_editor 編集内容を銘柄単位の session_state draft に保持。
- Enter キーやフォーカス移動で Streamlit が rerun しても、保存済みJSONの旧値で編集内容を上書きしないよう修正。
- 保存時は同じ draft / editor 結果を保存し、保存後も draft と同期。
- Enter確定→フォーカス移動→保存の回帰を静的テストで固定。
- `harness/app_blueprint.yaml` は変更なし。
