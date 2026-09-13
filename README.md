# Stock Value Dislocation Verification System

Version: **0.6.56**

日本株について、株価・決算・市場比較と最新外部日足を組み合わせ、「業績が大きく崩れていない一方で株価が低迷している可能性がある企業」を調査・検証するローカルアプリです。

## 開発履歴（新しい順）

> README の開発履歴は必ずこのセクションの先頭へ新しいバージョンを追加します。詳細な変更履歴は `CHANGELOG.md` を正本とします。

### v0.6.56 履歴一覧から個別銘柄を新しいタブで確認

- 「履歴・実績検証」の銘柄コード／企業名をクリックすると、元の履歴一覧を残したまま個別銘柄検索を新しいブラウザタブで開くようにしました。
- 新しいタブは別Streamlitセッションになるため、銘柄コードをURLクエリで引き渡し、自動的に対象銘柄を表示します。
- 条件設定・候補画面の既存の同一タブ遷移は変更していません。

### v0.6.55 履歴画面の generic timedelta 警告修正

- 「履歴・実績検証」の直近30日初期値を Python 標準の `datetime.timedelta` で計算し、NumPy の generic timedelta DeprecationWarning を解消しました。
- 警告を隠すのではなく原因式を除去し、再発防止テストを追加しました。

### v0.6.54 履歴実績から定量抽出ルールを安全に自動改善

- point-in-time の分析履歴と取得済み株価を使い、定量抽出条件を時系列の学習期間／検証期間で安全に自動校正する仕組みを追加しました。
- 外的要因レビューや人の承認、安全境界は自動変更の対象外です。

### v0.6.53 ソート高速化・README再構成

- 一覧のソート見出しは `on_click` コールバックで状態を先に更新し、従来の明示的な追加 `st.rerun()` を廃止しました。
- 候補一覧、統合候補一覧、履歴一覧を `st.fragment` で部分再描画し、ソート時に画面全体やYahoo最新トレンド判定を再実行しない構成へ変更しました。
- ソート処理は一時列をDataFrameへ追加せず、`sort_values(..., key=...)` で直接並べ替える方式へ軽量化しました。
- README の開発履歴をこの上段セクションへ集約し、新しい順に整理しました。

### v0.6.52 一覧表の列クリックソート復活

- ボタン式一覧で列名クリックによる昇順／降順ソートを復活しました。
- 未選択列は `↕`、昇順は `▲`、降順は `▼` を表示します。
- 銘柄コード／企業名のクリックによる個別銘柄検索への遷移を維持しました。
- 履歴一覧はページング前の検索結果全体を対象にソートします。

### v0.6.51 Streamlit 1.53.0 互換性修正

- 個別銘柄ニュースの `st.link_button()` から Streamlit 1.53.0 で未対応の `key=` を削除しました。
- 同じ互換性問題の再発防止テストを追加しました。

### v0.6.50 パステルモード強調

- 「やわらかパステル」をピンク／オレンジ／ラベンダー／水色／ミントの多色パステルへ強化しました。
- 背景、サイドバー、カード、タブ、ボタン、入力欄、表、プログレス表示の彩度・輪郭・影を強めました。

### v0.6.23 運用上限

- 統合候補が100銘柄以上の場合、Yahoo Finance系の一括最新株価・日足取得を開始しない安全上限を追加しました。
- Dashboard を Streamlit 1.53.0 に固定しました。

### v0.6.19 やわらかパステルテーマ強化

- 淡いピンク／ラベンダー／水色中心のパステルテーマを強化しました。

### v0.6.18 画面テーマと2種類の抽出ルール

- 「標準」「やわらかパステル」の画面テーマ切替を追加しました。
- 「外的要因で下落 × 経営良好」と「値動き活発（デイトレ候補）」の2種類の抽出ルールを追加しました。
- 条件変更だけではJ-Quants APIを呼ばず、取得済みcuratedデータで再評価します。

### v0.6.12 外的要因レビューと最新市場鮮度

- 外的要因レビューは任意入力とし、人が `approved` に保存したレビューのみ注文直前条件を満たします。
- 注文直前の市場データ鮮度はYahoo Finance系の日足最終取引日で判定し、J-Quantsのpoint-in-timeスコアには混入させません。

### v0.6.8 見える化

- 個別銘柄に株価・20日・50日・200日移動平均線グラフを追加しました。
- 約3カ月前との比較、買い検討価格帯、追いかけ買い上限、再評価ラインを表示します。
- 明確な欠点が見当たらない買い候補を `◎☆` で表示します。

### v0.6.6 直感判定と買い検討価格帯

- 最新外部日足で ◎／○／△／× の直感判定を表示します。
- 移動平均・直近安値・RSI・トレンド変化から買い検討価格帯等を表示します。

### v0.6.5 NumPy timedelta警告の完全修正

- `pd.to_timedelta(int(lookback_days), unit="D")` を使い時間単位を明示しました。

### v0.6.4 NumPy timedelta警告の修正

- トレンド比較の日数をPython標準整数へ明示変換し、警告の回帰テストを追加しました。

### v0.6.3 パッチ整合性修正

- `decision/trend.py` の差分漏れによる `build_trend_transition` import error を防止しました。

### v0.6.2 最新株価によるトレンド再判定

- スコア通過銘柄をYahoo Finance系の最新日足でも再確認し、下降継続／底打ち／下降脱出／上昇転換を整理します。

### v0.6.1 トレンド・売却判断

- MA20/50/200、RSI(14)、20日騰落率、出来高20日平均比で現在の株価方向を整理します。
- 売却・撤退条件例を表示します。

### v0.6.0 購入判断の整理

- 「買付を支える材料」「見送り・再確認材料」を整理する判断補助を追加しました。
- 投資上限と許容損失率から100株単位の3段階分割買い参考案を作成できます。注文送信は行いません。

### v0.5.10 個別銘柄の補助情報・外部評価

- 指標ツールチップ、Yahoo Finance系ニュース、アナリスト評価・目標株価、機械翻訳を追加しました。
- Yahoo!ファイナンス掲示板本文やSBI証券の契約コンテンツは自動取得しません。

### v0.5.8 個別銘柄画面

- 予想配当利回りの再計算、Yahoo Finance系最新株価の参考表示、同業中央値・一般目安を追加しました。

### v0.5.6 市場比較データの自動フォールバック

- 正式TOPIXが利用できない場合に1306→1475→1305の順でTOPIX連動ETFを代理利用する機能を追加しました。
- 正式TOPIXとETF代理値は画面上で明確に区別します。

### v0.5.3 画面操作・配当表示改善

- 投資スタイル変更の即時反映、候補から個別銘柄への遷移、配当条件・配当金額表示を改善しました。

### v0.5.0 高速化とSBI CSV連携

- 条件適用時だけ再計算する方式、Parquet事前計算、J-Quants増分更新を導入しました。
- SBI CSV取込を追加しましたが、SBIのID・パスワード・取引パスワードは使用しません。

### v0.4.0 条件設定・説明性の強化

- 初心者向けプリセット、条件変更UI、ファネル表示、通過理由・不合格理由、条件保存・CSV/JSON出力を追加しました。

### v0.3.4 TOPIX欠損時の安全性改善

- TOPIX未取得時に銘柄自身の騰落率を代理使用する誤りを修正し、相対条件を保留する方式へ変更しました。
- データ鮮度ゲート、監査CSV、必須条件ごとの合否表示を追加しました。

### v0.3.3 J-Quants契約期間対応

- APIが返す契約開始日・終了日を自動検出し、要求期間を取得可能範囲へ調整します。
- requested/effective期間と契約期間をmanifestへ保存します。

### v0.3.2 J-Quantsレート制限制御

- 日単位の直列・再開可能取得、429時の待機・バックオフ、週末省略、日別キャッシュを導入しました。

## 主な機能

- J-Quantsの財務・株価スナップショットによる定量候補抽出
- Yahoo Finance系の最新日足によるトレンド再確認
- 外的要因レビューと仮説無効化条件の保存・自動照合
- ◎／○／△／× と `◎☆` による直感的な候補整理
- MA20/50/200、RSI、価格帯などの可視化
- 履歴・実績検証、30/90/180日リターン追跡
- SBI CSVとの手動突合

## Windows / WSL での利用

### 初回

WSL Ubuntu でGitHubから取得します。

```bash
cd /mnt/c/temp
git clone https://github.com/hnamaizawa/stock-value-dislocation-verification-system.git
cd stock-value-dislocation-verification-system
```

Windows側の `C:\temp\stock-value-dislocation-verification-system` に、必要に応じて既存の `.env` とローカルデータをコピーします。その後、初回だけ `setup_windows.cmd` を実行します。

### 通常起動

取得済みデータを使う場合は Windows で `start_dashboard.cmd` を実行します。ブラウザーは `http://localhost:8501` を開きます。

データ更新も行う場合は `run_real.cmd` を実行します。

### 新バージョン反映

WSL Ubuntu で次を実行します。

```bash
cd /mnt/c/temp/stock-value-dislocation-verification-system
git pull origin main
```

依存関係が変更されたバージョンだけ `setup_windows.cmd` を再実行します。

## GitHub / CI

- リポジトリはPrivate運用を前提とします。
- `.env`、取得済み市場データ、ユーザープロファイル、実行時出力は `.gitignore` の対象です。
- 開発は `feature branch → Pull Request → GitHub Actions CI → merge` を基本フローとします。
- push / pull request 時に `python -m pytest tests/` と `python scripts/harness_check.py` を実行します。
- `main` をローカル実行環境の正本とします。

## データ取得と保存

### 主な取得元

- 上場銘柄一覧: `ClientV2.get_list`
- 株価日足: `ClientV2.get_eq_bars_daily(date_yyyymmdd=...)`
- 決算サマリー: `ClientV2.get_fin_summary_cursor(date_yyyymmdd=...)`
- TOPIX日足: `ClientV2.get_idx_bars_daily_topix`
- 決算発表予定: `ClientV2.get_eq_earnings_cal`
- 任意の適時開示検索: `ClientV2.get_td_list`（TDnetアドオン契約時）
- 最新株価・最新日足・関連情報: Yahoo Finance系（`yfinance`）

### J-Quants取得方針

- 全銘柄同期では `*_range` の並列要求を使わず、日単位で直列取得します。
- HTTP 429時は待機・バックオフし、取得済み日はキャッシュして再実行時に続きから再開します。
- 契約期間外の日付は取得可能範囲へ調整し、manifestへ記録します。

### cache保存先

```text
data/raw/jquants/_cache/equity_bars/<year>/
data/raw/jquants/_cache/fin_summary/<year>/
```

### 実データ保存先

```text
data/raw/jquants/<run_id>/          加工前レスポンス
data/curated/runs/<run_id>/        正規化した実行単位データ
data/curated/latest/                最新の検索対象
outputs/real/                       定量候補・レビュー待ち・実行状態
```

実データ、cache、APIキーはGitHubへ登録しません。

## 安全境界

- SBI証券へ自動アクセス、ログイン、注文送信しません。
- SBI証券の認証情報を要求・保存しません。
- SBI証券画面をブラウザー自動操作しません。
- Yahoo Finance系データは最新市場確認・トレンド用途に限定し、J-Quantsのpoint-in-time定量スコアへ混入させません。
- 外的要因レビュー、保有・買付余力、注文前ゲートは人が確認します。
- 表示される評価・価格帯・☆は利益保証や自動売買推奨ではありません。

## 開発・検証コマンド

```powershell
# 実データ取得と定量候補生成
.\.venv\Scripts\python.exe -m value_dislocation.cli run-real --config config/real_data.yaml

# 取得済み実データを検索
.\.venv\Scripts\python.exe -m value_dislocation.cli search-stock 7203

# テスト
.\.venv\Scripts\python.exe -m pytest tests/

# Harness
.\.venv\Scripts\python.exe scripts/harness_check.py
```

## デモ・再生成

- `run_demo.cmd` は架空データ専用です。
- `generate_similar_app.cmd` は検証済みコード・文書・安全境界を継承したアプリを `generated/` に作成します。
- APIキー、cache、取得済み実データ、仮想環境、ユーザープロファイルは再生成アプリへコピーしません。

## 詳細な変更履歴

完全な変更履歴は [`CHANGELOG.md`](CHANGELOG.md) を参照してください。
