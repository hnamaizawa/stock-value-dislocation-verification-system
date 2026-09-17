from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one occurrence of {old!r}, found {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
text = text.replace("Version: **0.6.57**", "Version: **0.6.58**", 1)
marker = "### v0.6.57 条件設定・候補から個別銘柄を新しいタブで確認\n"
section = """### v0.6.58 大規模データ更新・画面遷移の高速化

- 通常の `load_config()` では自動ルール学習本体を実行せず、保存済み学習ルールの読込だけにしました。重い学習は実データ更新時に1回だけ実行します。
- ルール学習の30/90/180日後リターン照合を、銘柄ごとの全株価再走査から、最初に作る銘柄別株価インデックスの直接参照へ変更しました。
- データ更新時の全銘柄特徴量計算を1回に統合し、特徴量スナップショット保存と候補抽出で同じ計算結果を再利用します。
- 大きな curated DataFrame は `st.cache_resource` でプロセス内共有し、画面遷移や別タブのStreamlitセッションで巨大DataFrameを毎回コピーしない構成にしました。
- データ更新後は共有キャッシュを明示的にクリアし、最新スナップショットを次の画面表示で読み込みます。

"""
if text.count(marker) != 1:
    raise SystemExit("README v0.6.57 marker missing")
readme.write_text(text.replace(marker, section + marker, 1), encoding="utf-8")

changelog = Path("CHANGELOG.md")
text = changelog.read_text(encoding="utf-8")
entry = """## v0.6.58
- 通常の `load_config()` から重いルール学習更新を分離し、保存済みルールの適用だけを行う軽量パスへ変更。ルール学習は実データ更新時に明示的に1回実行。
- ルール学習の将来リターン照合を、各銘柄ごとの全株価DataFrame再フィルタから、1回だけ構築する銘柄別株価ルックアップへ変更。
- `prepare_quantitative_universe()` を更新1回につき1度だけ実行し、特徴量スナップショット保存と定量判定で同じ結果を再利用。
- Streamlit の大規模 curated bundle を `st.cache_resource` で共有し、画面遷移・別タブセッションでの巨大DataFrameのシリアライズ／コピーを削減。
- 性能最適化の回帰テストと設計ドキュメントを追加。データ取得契約、安全境界、外的要因レビューの意味論は変更なし。

"""
if text.startswith("## v0.6.58"):
    raise SystemExit("CHANGELOG already patched")
changelog.write_text(entry + text, encoding="utf-8")

blueprint = Path("harness/app_blueprint.yaml")
text = blueprint.read_text(encoding="utf-8")
text = text.replace("blueprint_version: 0.6.57", "blueprint_version: 0.6.58", 1)
cap_marker = "- candidate_stock_detail_new_tab_navigation\n"
cap_add = cap_marker + "- shared_large_curated_bundle_cache\n- single_pass_quantitative_feature_preparation\n- explicit_data_refresh_rule_learning\n- indexed_rule_learning_forward_return_lookup\n"
if text.count(cap_marker) != 1:
    raise SystemExit("blueprint capability marker missing")
text = text.replace(cap_marker, cap_add, 1)
inv_marker = "- candidate_stock_detail_must_open_new_tab_without_mutating_candidate_session\n"
inv_add = inv_marker + "- screen_navigation_must_not_refresh_rule_learning\n- large_curated_bundle_must_not_be_copied_per_rerun\n- quantitative_features_must_be_prepared_once_per_data_refresh\n- rule_learning_must_not_rescan_all_prices_per_security\n"
if text.count(inv_marker) != 1:
    raise SystemExit("blueprint invariant marker missing")
text = text.replace(inv_marker, inv_add, 1)
req_marker = "- docs/17_BEGINNER_CONDITION_UI.md\n"
if req_marker in text and "- docs/19_PERFORMANCE_OPTIMIZATION.md\n" not in text:
    text = text.replace(req_marker, req_marker + "- docs/19_PERFORMANCE_OPTIMIZATION.md\n", 1)
blueprint.write_text(text, encoding="utf-8")

tasks = Path("tasks/CURRENT.md")
text = tasks.read_text(encoding="utf-8")
entry = """## v0.6.58 large-data performance optimization

- [x] 画面遷移・通常設定読込でルール学習本体を実行しない。
- [x] ルール学習の将来リターン計算で全株価表を銘柄ごとに再走査しない。
- [x] データ更新時の全銘柄特徴量計算を1回に統合する。
- [x] 大規模 curated bundle を Streamlit プロセス内で共有し、ページ遷移時のコピーを避ける。
- [x] 回帰テスト・Harness契約・設計文書を追加する。

"""
if not text.startswith("## v0.6.58"):
    tasks.write_text(entry + text, encoding="utf-8")
