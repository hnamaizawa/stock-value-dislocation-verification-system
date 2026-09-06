# Development Harness

## 目的

このハーネスは、実データを扱う日本株調査アプリを安全かつ再生成可能な形で継続開発するためのものです。

## canonical artifacts

- `harness/app_blueprint.yaml`: 機能、安全境界、必須ファイル、除外対象
- `scripts/generate_app.py`: 現在の検証済みリポジトリからクリーンな同型アプリを生成
- `generation_manifest.json`: 生成物のblueprint版、継承した安全境界、ファイルハッシュ
- `scripts/harness_check.py`: 文書、設定、実データ契約、provenance、安全性、generator、テストを検査

## 標準開発ループ

1. `tasks/CURRENT.md` から1作業を選ぶ。
2. 関連MDとblueprintを読む。
3. 小さく実装し、実データ列は正規化層に閉じ込める。
4. fake clientでAPI依存テストを追加する。
5. 実アカウント確認時はRawとmanifestを保存するが、配布物へ含めない。
6. `check_harness.cmd` を実行する。
7. `CHANGELOG.md`、Current Status、Decision Log、Source Registerを更新する。

## ハーネス検査項目

- 必須MD・コード・Windows起動ファイル
- デモデータの `data/sample/` 隔離
- 実データ設定が `data/curated/latest/` のみを参照
- J-Quantsが有効でAPIキーを環境変数から読む
- `actual_data=true`、`sample_data=false`、provider、cutoff、SHA-256の実装
- ダッシュボードが実データ取得・会社名/コード検索を実装
- SBI認証情報、SBI画面自動操作、注文送信がない
- 注文案生成が実データ設定で無効
- blueprintの安全不変条件
- generator self-test
- J-Quants全銘柄同期が直列・429 backoff・日別再開cacheを持つこと
- J-Quants契約期間外400を解析し、株価・財務・TOPIXを契約範囲へ調整すること
- requested/effective期間と契約上限日をmanifestと画面へ残すこと
- 公式の並列 `get_eq_bars_daily_range` / `get_fin_summary_range` をfull syncで呼ばないこと
- Python compile、pytest
- TOPIX欠損時に銘柄自身の騰落率を相対値へ代用しないこと
- 候補ごとの合格理由・不合格理由・注意点と選別ファネルが生成されること
- データ鮮度が注文プレビュー適格性を制御すること
- 安全重視・標準・割安重視プリセットが存在すること
- 必須条件をUIから変更し、保存済みsnapshotで即時再計算すること
- 条件設定の保存・読込・JSON/CSV出力があること
- `config/user_profiles` が同型アプリ生成時にコピーされないこと

## 実行

```bat
check_harness.cmd
```

または:

```powershell
.\.venv\Scripts\python.exe scripts\harness_check.py
```

## 同型アプリ生成

```powershell
.\.venv\Scripts\python.exe scripts\generate_app.py `
  --name "My Japanese Equity Research" `
  --destination C:\temp\my-japanese-equity-research
```

生成後のアプリでも `setup_windows.cmd`、`check_harness.cmd`、`run_real.cmd` の順で確認します。

### J-Quants V2取得契約

ハーネスは、全銘柄同期が `get_eq_bars_daily(date_yyyymmdd=...)` を直列実行し、429時の待機、保守的な要求間隔への切替、株価・決算の日別cacheを持つことを確認します。`get_eq_bars_daily(from,to)` の無コード呼出しと、公式range helperの並列実行をfull syncへ戻す変更を失敗扱いにします。

さらに、契約期間外HTTP 400の本文から `開始日 ~ 終了日` を抽出し、価格開始、価格終了、財務開始、TOPIX終了を同じ実効期間へ調整する実装を必須とします。生成アプリもこの挙動を継承します。

## v0.5.0 performance and SBI CSV invariants

- Screening widgets are inside a form and must not recompute until `条件を適用` is pressed.
- `run_real.cmd` must precompute `security_features.parquet` with a CSV fallback.
- Interactive screening must use the certified feature snapshot when available.
- Completed J-Quants dates remain resumable from the raw daily cache.
- SBI integration is limited to user-exported CSV import and matching.
- SBI credentials, browser automation, and order transmission remain forbidden.

## UI navigation requirements (v0.5.2)

- A preset selection must immediately populate all editable screening parameters.
- Screening calculation must still run only after the apply button is pressed.
- Candidate code and company name must be actionable controls.
- Activating either control must navigate to stock detail and preselect the same security.


## v0.5.3 UI navigation checks

The harness requires Streamlit top navigation (`st.navigation(..., position="top")`), rejects the previous horizontal `st.radio` selector, verifies candidate-to-detail navigation with `st.switch_page`, and verifies dividend output in the individual stock page.


## v0.5.6 benchmark policy
正式TOPIXを優先し、取得できない場合だけTOPIX連動ETF（1306、1475、1305）の調整後終値を明示的な代理指標として利用する。代理値は正式TOPIXと表示上・監査上で区別し、両方なければ市場相対条件を保留する。

### v0.5.8 初心者向け指標目安
`tests/test_dashboard_metric_guides.py` は、個別銘柄画面に同業中央値または一般目安が表示されることを検査します。


### v0.5.10 指標ヘルプ・外部情報

- 主要指標にホバー説明があること。
- 関連ニュースは最大10件で、出典リンクを持つこと。
- Yahoo!ファイナンス掲示板本文をスクレイピングしないこと。
- SBI証券のレーティングは手動確認とし、認証情報・契約データを取得しないこと。
- 外部評価を定量スコアや注文へ混入させないこと。


### v0.5.10 翻訳・評価ヘルプ

- アナリスト評価がニュースより先に表示されること。
- 日本語以外のニュースを機械翻訳し、原文を保持すること。
- 翻訳失敗時に原文へフォールバックすること。
- アナリスト評価・目標株価の全主要項目にホバー説明があること。

### v0.6.0 購入判断補助

ハーネスは、購入判断の整理、有利・反対材料、注文前人手チェック、分割買い参考案、JSON判断メモが存在することを確認します。「利益保証ではありません」の安全表示と、注文送信禁止設定を維持します。


### v0.6.1 トレンド判断

ハーネスは、拡大ナビゲーション、トレンド判定モジュール、買い兆候・待機警告、売却・撤退条件表示を検査します。


### v0.6.2 最新トレンド再判定

- スコア通過銘柄は外部最新日足で再判定すること。
- 約3カ月前と現在の状態を比較し、下降継続・底打ち・下降脱出・上昇転換を区別すること。
- 外部最新トレンドはJ-Quantsの定量スコア、バックテスト、候補抽出へ混入させないこと。
- 外部取得失敗時はJ-Quants基準日の判定へ安全にフォールバックすること。
