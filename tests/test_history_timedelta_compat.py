from pathlib import Path


def test_history_uses_explicit_timedelta_unit():
    text = Path("src/value_dislocation/history.py").read_text(encoding="utf-8")
    assert "pd.Timedelta(days=int(horizon))" not in text
    assert 'searchsorted(start.normalize(), side="right")' in text
    assert 'first_future + int(horizon) - 1' in text
