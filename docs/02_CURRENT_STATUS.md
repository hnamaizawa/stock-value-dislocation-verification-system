# Current status

## プロダクトゴールと未達項目（2026-10-04再定義）

目標は「営業実態が大きく崩れていないのに外的要因で低迷する銘柄を探し、回復の兆候を日次で観察し、予測成績を複数期間で検証する」こと。詳細は `docs/01_PROJECT_CHARTER.md` を参照。

現行実装には企業・財務条件、構造悪化ガード、外的要因の人手レビュー、配当指標、日次トレンド、point-in-time Walk-Forward、デイトレード用の値動き抽出がある。ただし各機能はゴール全体の完成を意味しない。

- 実績検証の現行期間は10/20/30/60/90/180取引日。新ゴールの120/240/365取引日は未実装。
- 外的要因が一時的か、営業実態が本当に健全かを自動的に確定する機能はない。一次資料と不確実性を人が確認する。
- デイトレード分析は流動性・ボラティリティ・日中値幅を使う候補抽出であり、約定品質やイントラデイ時系列を使った売買戦略・バックテストではない。
- 新しい長期 horizon はローカルに十分な将来日足がある場合だけ確定値を出し、足りない場合は未確定として扱う。

## Version 0.6.74

Walk-Forwardは設定ファイルだけでなく、このセッションで最後に適用した条件設定も使用する。
条件設定画面の値はセッション内で管理されるため、Walk-Forward実行条件の由来も画面に表示する。

## Version 0.6.73

Walk-Forwardが候補0件の場合、各過去時点の評価銘柄数と不通過条件の延べ回数を表示する。
価格と財務データの結合後に評価対象行が0件の場合は、価格・財務の共通銘柄や過去開示履歴の
確認を案内する。空結果の再実行時も診断を作るため、特徴量キャッシュを再利用して抽出判定を行う。

## Version 0.6.72

Walk-Forwardはローカル日足の件数で評価可能な最大取引日数を判定し、要求期間を
自動で短縮する。最短期間にも満たない場合は必要日数と実データ日数を表示し、
候補が0件の場合はデータ不足と抽出条件による候補不在を区別して案内する。

## Version 0.6.71

Walk-Forwardは定量候補全体だけでなく、本番画面と同じ判定関数で旧◎☆条件と
反転確認済み◎☆をpoint-in-time再現する。各段階を平均、中央値、プラス率、
5%以上下落率、確定件数で比較し、反転確認済み◎☆は即時・3日待機・5日待機も比較する。
待機期間の将来値は成績計算だけに使い、候補資格へは混入させない。

## Version 0.6.70

Walk-Forward成績は、候補平均と類似非選択平均を横並び棒で比較し、そこから算出する
選択効果を独立した菱形マーカーと点線で表示する。選択効果を積み上げず、0%基準と
各値を明記することで、派生値を合計値として読む誤解を防ぐ。

## Version 0.6.69

実績検証の単純な期間別・条件別縦棒グラフを多軸バブル図へ置換した。期間別は
取引日数、平均リターン、プラス率、確定件数を同時表示し、条件別は平均リターン、
プラス率、確定件数を同時表示する。v0.6.68で追加した条件バブルとの重複は解消した。

## Version 0.6.68

履歴・実績検証の◎☆実績へ、条件×期間ヒートマップ、条件別の平均リターン×プラス率×
確定件数バブル図、銘柄別の任意2期間リターン×◎☆回数バブル図を追加した。
すべて保存済みローカル履歴から描画し、画面表示や軸変更による外部取得は行わない。
確定件数を常に併記し、少数観測や相関を因果関係として扱わない。

## Version 0.6.67

J-Quants実データ更新ごとの銘柄マスターを日付別に保存し、既存certified curated runからも
復元する。Walk-Forwardは評価日以前の最新マスターを用い、保存済み履歴に存在する
上場廃止相当銘柄を過去母集団へ含める。履歴がない期間の現在マスターフォールバックは
監査列と画面で明示する。未保存の過去母集団までは再構成できないため、生存者バイアスの
完全排除ではない。

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
