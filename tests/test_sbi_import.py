from value_dislocation.data.sbi_import import parse_sbi_screening_csv


def test_parse_sbi_csv_cp932():
    text = "銘柄コード,銘柄名,市場,現在値,PER,PBR\n7203,トヨタ自動車,東証P,3000,10.2,1.1\n"
    result = parse_sbi_screening_csv(text.encode("cp932"))
    assert result.encoding == "cp932"
    assert result.rows.iloc[0]["code"].startswith("7203")
    assert result.rows.iloc[0]["name"] == "トヨタ自動車"


def test_sbi_csv_requires_code():
    try:
        parse_sbi_screening_csv("銘柄名\nテスト\n".encode("utf-8"))
    except ValueError as exc:
        assert "銘柄コード" in str(exc)
    else:
        raise AssertionError("ValueError expected")
