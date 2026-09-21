from pathlib import Path

source = Path("scripts/apply_v062_patch.py").read_text(encoding="utf-8")
core = source.split("# --- changelog and task note ---", 1)[0]
exec(compile(core, "scripts/apply_v062_patch.py", "exec"))

changelog = Path("CHANGELOG.md")
text = changelog.read_text(encoding="utf-8")
if not text.startswith("## v0.6.62\n"):
    block = (
        "## v0.6.62\n"
        "- `Recovery Quality（回復の質）` を追加し、利益のキャッシュ転換性・営業利益の中期方向・会社予想の修正方向・ネットキャッシュ/総資産を複合評価。\n"
        "- 最低2成分が観測できる場合だけ標準55点以上を必須化し、データ不足では機械的に候補を除外しない。\n"
        "- 銀行・保険・証券等では営業CFの意味が一般事業会社と異なるためキャッシュ転換成分を除外。\n"
        "- 既存curatedデータだけで計算し、条件変更や画面遷移でJ-Quants/Yahoo追加取得を行わない。\n\n"
    )
    changelog.write_text(block + text, encoding="utf-8")

print("v0.6.62 patch applied")
