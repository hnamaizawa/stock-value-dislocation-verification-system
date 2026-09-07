from pathlib import Path


def test_dashboard_history_period_uses_python_timedelta():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "from datetime import timedelta" in text
    assert "pd.Timedelta(days=30).to_pytimedelta()" not in text
    assert "last_day - timedelta(days=30)" in text
