from pathlib import Path

p = Path("scripts/apply_v063_patch.py")
text = p.read_text(encoding="utf-8")
old = '''for path in ["tests/test_package_init.py", "tests/test_sort_performance_and_readme_structure.py"]:
    p = Path(path)
    p.write_text(p.read_text(encoding="utf-8").replace("0.6.62", "0.6.63"), encoding="utf-8")
'''
new = '''p = Path("tests/test_package_init.py")
t = p.read_text(encoding="utf-8")
t = t.replace('assert value_dislocation.__version__ == "0.6.62"', 'assert value_dislocation.__version__ == "0.6.63"', 1)
p.write_text(t, encoding="utf-8")

p = Path("tests/test_sort_performance_and_readme_structure.py")
t = p.read_text(encoding="utf-8")
t = t.replace('assert lines[2] == "Version: **0.6.62**"', 'assert lines[2] == "Version: **0.6.63**"', 1)
t = t.replace(
    '        "### v0.6.62 構造悪化ガードでバリュートラップを識別",\\n',
    '        "### v0.6.63 Walk-Forward・類似非選択比較・外因説明率",\\n        "### v0.6.62 構造悪化ガードでバリュートラップを識別",\\n',
    1,
)
p.write_text(t, encoding="utf-8")
'''
if old not in text:
    raise SystemExit("version-test patch block not found")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
