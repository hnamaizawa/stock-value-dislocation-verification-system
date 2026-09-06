from pathlib import Path

from value_dislocation.data.latest_quote import (
    YAHOO_BULK_FETCH_BLOCK_THRESHOLD,
    yahoo_bulk_fetch_allowed,
)


def test_bulk_yahoo_fetch_is_blocked_at_100_or_more():
    assert YAHOO_BULK_FETCH_BLOCK_THRESHOLD == 100
    assert yahoo_bulk_fetch_allowed(0)
    assert yahoo_bulk_fetch_allowed(99)
    assert not yahoo_bulk_fetch_allowed(100)
    assert not yahoo_bulk_fetch_allowed(101)
    assert not yahoo_bulk_fetch_allowed(500)


def test_dashboard_has_pre_fetch_bulk_gate_and_warning():
    source = Path('dashboard.py').read_text(encoding='utf-8')
    gate = source.index('bulk_yahoo_allowed = yahoo_bulk_fetch_allowed(total)')
    fetch = source.index('history = _latest_external_history(code)', gate)
    assert gate < fetch
    assert '銘柄以上の場合は外部取得を実施しません' in source
    assert '未実施（100件以上）' in source
