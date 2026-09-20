from pathlib import Path

path = Path("tests/test_sort_performance_and_readme_structure.py")
text = path.read_text(encoding="utf-8")
wrong = '''        "### v0.6.61 旧実績データの期間列後方互換修正",
        "### v0.6.59 実績検証の短中期評価期間を拡張",'''
right = '''        "### v0.6.61 ◎☆を反転確認済みの最上位評価へ厳格化",
        "### v0.6.60 旧実績データの期間列後方互換修正",
        "### v0.6.59 実績検証の短中期評価期間を拡張",'''
count = text.count(wrong)
if count != 1:
    raise RuntimeError(f"expected one README history expectation block, found {count}")
path.write_text(text.replace(wrong, right, 1), encoding="utf-8")
print("v0.6.61 README structure expectation fixed")
