# Current status

## Version 0.5.1

The application now precomputes security-level features after each actual-data update, uses an explicit apply-button form for interactive screening, and imports SBI screening CSV files for local matching. J-Quants raw retrieval remains serial, rate-limited, cached, and resumable. SBI login and order transmission remain out of scope.

# Current Status

最終更新: 2026-08-02  
対象バージョン: 0.4.0

## 現在動作するもの

- J-Quants API V2の実データ取得
- 上場銘柄、調整済み日足、決算サマリー、TOPIX、決算発表予定の正規化
- Raw/Curatedスナップショット、manifest、SHA-256
- 実際の最終株価日を `data_cutoff_at` として保存
- 会社名・4桁/5桁コードによる日本株検索
- 個別銘柄の株価チャート、価格乖離、TOPIX相対値、財務指標表示
- 実データの定量候補と外的要因レビュー待ち生成
- 株価・決算の直列取得、429自動backoff、日別再開cache
- 契約期間外HTTP 400から取得可能期間を検出し、株価・決算・TOPIXを同じ実効期間へ調整
- requested/effective期間と契約上限日をmanifest・実行状態・画面へ表示
- デモ/実データ分離とmanifest検証
- StreamlitからAPIキーをファイル保存せず実行時だけ使用
- TDnetアドオン契約時の銘柄別開示インデックス検索CLI
- blueprintとgeneratorによる同型アプリ生成
- Windowsセットアップ、起動、ハーネス



## 0.4.0 interactive screening

- 3種類の初心者向けプリセットとカスタム設定を実装。
- `prepare_quantitative_universe` をキャッシュし、UI操作では `apply_quantitative_criteria` だけを実行する。
- 条件変更はJ-Quants APIを呼ばず、認証済みcurated snapshotを変更しない。
- 条件プロファイルは `config/user_profiles` に保存し、generatorではコピーしない。
- 候補CSV、設定JSON、近似不合格理由を画面から取得できる。

## 0.3.4 explainability and benchmark correction

- TOPIX欠損時の `relative_return_6m` はNaNとし、銘柄自身のリターンを代用しない。
- TOPIXがない場合は相対条件を `skip_with_warning` として保留し、候補にデータ制約を付与する。
- `quantitative_audit_latest.csv` に全銘柄の必須条件合否、理由、警告を保存する。
- `screening_funnel_latest.json` と画面で選別件数を表示する。
- 株価基準日の経過日数が設定上限を超える場合、注文プレビュー適格性をfalseにする。

## 実データに関する重要事項

- 配布ZIPにJ-Quants APIキーと取得済み実データは含まれない。
- 実アカウントでのエンドツーエンド確認は、ユーザーのAPIキーと契約プランで行う必要がある。
- 初回同期は多数の日別要求を伴うため長時間かかり得る。429時は自動待機し、取得済み日を保持して再開する。
- 契約プランに遅延期間がある場合、画面で本日を指定しても契約上の最新取得可能日までのデータとなる。
- 取得成功後も、現在の候補は定量レビュー対象であり注文候補ではない。

## 未実装

- EDINETによる有利子負債、詳細CF、セグメント、注記の補完
- TDnet/IR文書の本文保存、根拠箇所抽出、レビューUI
- 外的要因承認済み候補への最終スコアリング
- 上場廃止・市場変更・銘柄コード変更の履歴
- SBI証券から手動出力した保有・約定・未約定CSVの取込
- 買付余力、既存保有、セクター集中を反映した注文前ゲート
- 日本の呼値、値幅制限、売買停止、権利落ち、決算直前チェック
- 承認ハッシュ、有効期限、注文直前パケット
- 実データのポイント・イン・タイムバックテストと3か月のペーパートレード

## 現在の完成段階

**実データ調査版のコードは実装済み。実アカウントでの連続運転検証は未完了。注文直前版ではない。**

## 0.3.3 subscription-window correction

J-Quantsが契約期間外要求に対して返す `Your subscription covers the following dates: ...` を解析し、価格開始・価格終了・財務開始を契約範囲へ調整する。調整前後の期間をmanifestへ残し、画面に契約データ上限日と警告を表示する。

## 0.3.2 rate-limit correction

公式 `get_eq_bars_daily_range` と `get_fin_summary_range` は内部で並列要求するためfull syncでは使用しない。低水準APIを日付指定で直列実行し、HTTP 429後はbackoffと要求間隔拡大を行う。株価・決算の完了日は即時cacheへ保存し、プロセス停止後も再実行で続行する。


## v0.5.3 UI status

- Main views use Streamlit top navigation tabs instead of a radio/check selector.
- Candidate code and company-name buttons open the corresponding individual security page.
- Individual security output includes forecast dividend per share, yield, payout ratio, forecast change, arbitrary-share gross dividend, taxable-account estimate, NISA estimate, and estimated investment amount.


## v0.5.4 benchmark policy
正式TOPIXを優先し、取得できない場合だけTOPIX連動ETF（1306、1475、1305）の調整後終値を明示的な代理指標として利用する。代理値は正式TOPIXと表示上・監査上で区別し、両方なければ市場相対条件を保留する。

## v0.5.8
個別銘柄検索の主要指標には、同業中央値または初心者向け一般目安を括弧内に表示する。これは投資判断の保証値ではなく比較の出発点である。


## v0.5.10

個別銘柄画面に指標ツールチップ、関連ニュース最大10件、Yahoo Finance系の公開アナリスト評価を追加。Yahoo!ファイナンス掲示板本文とSBI証券の契約レーティングは自動取得せず、外部確認リンクのみ提供する。


## v0.6.8
- 個別銘柄画面で最新外部日足を優先した株価+20/50/200日移動平均線グラフを表示。
- 買い検討価格帯・追いかけ買い上限・再評価ラインを同グラフに重ねる。
- 主要チェックが良好な候補に☆を付ける。☆は利益保証ではない。

## v0.6.9 個別銘柄検索
- 会社名の正規化＋部分一致＋軽い誤記のあいまい検索を実装。
- 複数候補は必ず利用者選択を要求し、暗黙の先頭選択を禁止。


## v0.6.10 最新トレンド再判定件数
- 「スコア通過銘柄の最新トレンド再判定」はスコア通過した全銘柄を対象にする。
- 旧実装の20銘柄上限を撤廃。
- Yahoo Finance系の履歴取得に失敗した銘柄も「判定不能」として一覧に残し、件数を減らさない。
- スコア通過、再判定一覧、取得成功、取得失敗の件数を画面に明示する。
