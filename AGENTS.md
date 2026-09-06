# AGENTS.md

このリポジトリを人間・AI・自動化ツールが変更するときの最上位ルールです。

## 1. プロジェクトの目的

日本株について、業績・財務が大きく崩れていない一方で、一時的な外的要因により株価が低迷している可能性のある企業を、実データから調査・比較し、**SBI証券で人間が発注する直前の注文案**まで作成する。

## 2. 絶対に越えない境界

- SBI証券へ自動ログインしない。
- SBI証券のID、ログインパスワード、取引パスワード、ワンタイム認証情報を保存しない。
- 国内株式の注文をSBI証券へ自動送信しない。
- SBI証券Web画面をSelenium、Playwright、RPA、画像認識等で無人操作しない。
- 信用取引、空売り、レバレッジ商品を初期対象にしない。
- LLMの判断だけで外的要因を承認しない。
- 将来情報を過去時点の分析へ混入させない。

公式な国内現物株の発注APIが将来提供された場合でも、自動接続は新しい設計判断（ADR）、規約確認、テスト環境、明示的なユーザー承認を経るまで実装しない。

## 3. 実装前に必ず読むファイル

1. `HARNESS.md`
2. `docs/02_CURRENT_STATUS.md`
3. `docs/03_TARGET_ARCHITECTURE.md`
4. `docs/07_RISK_AND_ORDER_GATES.md`
5. `tasks/CURRENT.md`

## 4. 変更時の必須作業

- 仕様や境界を変えたら、該当するMDと `docs/12_DECISIONS.md` を更新する。
- 実データ列を追加・変更したら `docs/05_DATA_CONTRACTS.md` を更新する。
- 外部APIの契約期間や遅延により要求日を調整する場合、要求期間と実効期間をmanifestへ両方残す。
- 外部サービス仕様を利用したら `docs/15_SOURCE_REGISTER.md` に確認日と公式根拠を記録する。
- コード変更後は `check_harness.cmd` または `python scripts/harness_check.py` を実行する。
- テストを追加し、既存テストをすべて通す。
- 出力には `run_id`、`as_of`、`data_cutoff_at`、`generated_at`、`source_snapshot` を残す。
- J-Quantsの契約期間外400を無視せず、APIが返した期間を解析して全データセットへ一貫して適用する。

## 5. 完了の定義

`docs/14_DEFINITION_OF_DONE.md` を満たすまで「実用版」「本番対応」「注文可能」と表現しない。

## Performance and broker bridge rules added in v0.5.0

1. Do not compute security features from the full daily-price table during every UI rerun.
2. Condition controls must be submitted explicitly before screening is recalculated.
3. Preserve the resumable per-date J-Quants cache and rebuild the feature snapshot only after data update.
4. SBI Securities integration is file-based CSV import only unless an official supported API is later verified and approved.
5. Never request or store SBI login credentials or trading passwords.

## Interactive UI invariant

- Preset selection updates parameter widgets immediately, without calling J-Quants.
- Candidate navigation preserves the selected security code and opens the individual-stock view.
- Do not replace these behaviors with static tables that cannot navigate.


## v0.5.6 benchmark policy
正式TOPIXを優先し、取得できない場合だけTOPIX連動ETF（1306、1475、1305）の調整後終値を明示的な代理指標として利用する。代理値は正式TOPIXと表示上・監査上で区別し、両方なければ市場相対条件を保留する。

## v0.5.8 external quote boundary
外部最新株価は参考表示専用とし、J-Quants分析スナップショット・バックテスト・注文案へ混入させない。Yahoo!ファイナンス日本版HTMLのスクレイピングは実装しない。


## v0.5.10 external commentary and ratings boundary

- Do not scrape or reproduce Yahoo! Finance Japan message-board posts.
- Related-news display may use yfinance public article metadata and must link to the source.
- SBI Securities ratings are authenticated/proprietary data and must not be scraped, copied, or fetched with user credentials. Provide a manual verification link only.
- External analyst data must be labelled unofficial and must not enter screening, scoring, backtests, or order generation.

## v0.6.0 purchase-decision boundary

The application may organize evidence, blockers, missing checks and a manual split-entry preview. It must never state that profit is certain, label a security as an unconditional buy, transmit an order, or treat analyst targets as facts. A conditional-consideration state requires human checks for current SBI price, latest disclosures, temporary external cause, catalyst, failure scenario and earnings risk.


## v0.6.1 trend boundary

- Trend indicators are decision support, never a guaranteed buy/sell signal.
- A strong downtrend is a blocking condition for buy readiness.
- Trend data must be derived from historical daily prices and stored in the decision packet.


## v0.6.2 latest-trend boundary

- Re-check score-passed securities using latest available external daily history.
- Keep external trend data display-only and separate from point-in-time screening scores.
- Compare the current state with approximately three months earlier before claiming that a downtrend may have ended.
- Never describe a possible trend escape as a guaranteed rise or unconditional buy.

## v0.6.3 patch integrity boundary
- `src/value_dislocation/decision/__init__.py` が公開する関数は、差分パッチにも実装ファイルを必ず含める。
- `build_trend_transition` の import を回帰テストで検証する。
