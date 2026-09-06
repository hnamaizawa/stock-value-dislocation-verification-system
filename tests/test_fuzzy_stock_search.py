import pandas as pd

from value_dislocation.data.search import normalize_company_search_text, search_companies


def _companies():
    return pd.DataFrame([
        {"code": "72030", "name": "トヨタ自動車", "market": "Prime", "sector": "輸送用機器"},
        {"code": "31160", "name": "トヨタ紡織", "market": "Prime", "sector": "輸送用機器"},
        {"code": "80150", "name": "豊田通商", "market": "Prime", "sector": "卸売業"},
        {"code": "83060", "name": "三菱ＵＦＪフィナンシャル・グループ", "market": "Prime", "sector": "銀行業"},
        {"code": "94320", "name": "日本電信電話株式会社", "market": "Prime", "sector": "情報・通信業"},
    ])


def test_normalization_handles_width_kana_and_corporate_suffix():
    assert normalize_company_search_text("トヨタ 株式会社") == "とよた"
    assert normalize_company_search_text("ﾄﾖﾀ") == "とよた"


def test_partial_search_returns_multiple_ranked_candidates():
    result = search_companies(_companies(), "トヨタ", limit=10)
    assert len(result) >= 2
    assert "72030" in set(result["code"])
    assert "31160" in set(result["code"])
    assert "match_type" in result.columns
    assert "search_score" in result.columns


def test_typo_search_finds_likely_company():
    result = search_companies(_companies(), "トヨダ", limit=10)
    assert not result.empty
    assert "72030" in set(result["code"])


def test_halfwidth_and_casefold_search():
    result = search_companies(_companies(), "三菱ufj", limit=10)
    assert not result.empty
    assert result.iloc[0]["code"] == "83060"


def test_exact_stock_code_is_ranked_first():
    result = search_companies(_companies(), "7203", limit=10)
    assert not result.empty
    assert result.iloc[0]["code"] == "72030"
    assert result.iloc[0]["match_type"] == "証券コード完全一致"
