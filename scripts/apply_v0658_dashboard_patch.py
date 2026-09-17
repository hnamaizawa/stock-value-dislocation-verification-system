from pathlib import Path

path = Path("dashboard.py")
text = path.read_text(encoding="utf-8")
old = """@st.cache_data(show_spinner=False)\ndef _load_bundle(manifest_mtime_ns: int) -> dict:\n    del manifest_mtime_ns\n"""
new = """@st.cache_resource(show_spinner=False, max_entries=2)\ndef _load_bundle(manifest_mtime_ns: int) -> dict:\n    # The curated market bundle can contain millions of price rows. cache_resource\n    # shares the same read-only object across Streamlit reruns/sessions instead of\n    # serializing and copying the full DataFrames on every page navigation.\n    del manifest_mtime_ns\n"""
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one _load_bundle cache block, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
