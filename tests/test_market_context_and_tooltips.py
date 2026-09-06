from pathlib import Path

from value_dislocation.data.market_context import fetch_analyst_snapshot, fetch_market_news


class FakeTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.info = {
            "recommendationKey": "buy",
            "recommendationMean": 2.1,
            "numberOfAnalystOpinions": 8,
            "currentPrice": 1000,
        }
        self.analyst_price_targets = {
            "low": 900,
            "mean": 1250,
            "median": 1200,
            "high": 1500,
            "current": 1000,
        }

    def get_news(self, count=10, tab="news"):
        return [
            {
                "content": {
                    "title": f"Article {i}",
                    "summary": f"Summary {i}",
                    "provider": {"displayName": "Example News"},
                    "pubDate": "2026-08-05T10:00:00Z",
                    "canonicalUrl": {"url": f"https://example.com/{i}"},
                }
            }
            for i in range(12)
        ]


def test_market_news_is_limited_to_ten_and_normalised():
    items = fetch_market_news("8136", limit=10, ticker_factory=FakeTicker)
    assert len(items) == 10
    assert items[0].title == "Article 0"
    assert items[0].publisher == "Example News"
    assert items[0].url == "https://example.com/0"


def test_analyst_snapshot_calculates_target_upside():
    snapshot = fetch_analyst_snapshot("8136", ticker_factory=FakeTicker)
    assert snapshot.recommendation_key == "buy"
    assert snapshot.analyst_count == 8
    assert snapshot.target_mean == 1250
    assert snapshot.upside_to_mean_target == 0.25


def test_dashboard_has_metric_tooltips_and_no_board_scraping():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert "METRIC_DESCRIPTIONS" in text
    assert 'title="{tooltip}"' in text
    assert "Yahoo!ファイナンス掲示板の投稿本文" in text
    assert "fetch_market_news" in text
    assert "fetch_analyst_snapshot" in text
    assert "requests.get(" not in text
    assert "BeautifulSoup" not in text


def test_non_japanese_news_is_machine_translated_and_original_retained():
    from value_dislocation.data.market_context import MarketNewsItem, translate_market_news_to_japanese

    class FakeTranslator:
        def __init__(self, source="auto", target="ja"):
            assert target == "ja"

        def translate(self, text):
            return text.replace("Article", "記事").replace("Summary", "要約")

    rows = translate_market_news_to_japanese(
        [MarketNewsItem("Article 1", "Example", None, "Summary 1", "https://example.com")],
        translator_factory=FakeTranslator,
    )
    assert rows[0]["title_ja"] == "記事 1"
    assert rows[0]["summary_ja"] == "要約 1"
    assert rows[0]["was_translated"] is True
    assert rows[0]["original_title"] == "Article 1"


def test_japanese_news_is_not_translated():
    from value_dislocation.data.market_context import MarketNewsItem, translate_market_news_to_japanese

    class FailTranslator:
        def __init__(self, **kwargs):
            raise AssertionError("translator must not be called")

    rows = translate_market_news_to_japanese(
        [MarketNewsItem("日本語の記事", "Example", None, "日本語の要約", None)],
        translator_factory=FailTranslator,
    )
    assert rows[0]["title_ja"] == "日本語の記事"
    assert rows[0]["was_translated"] is False


def test_analyst_section_precedes_news_and_has_help_tooltips():
    text = Path("dashboard.py").read_text(encoding="utf-8")
    assert text.index('st.markdown("#### アナリスト評価・目標株価")') < text.index(
        'st.markdown("#### 関連ニュース・市場コメント（最大10件）")'
    )
    for label in [
        "外部評価", "評価平均", "対象アナリスト数", "平均目標株価",
        "平均目標株価への乖離", "目標株価・低値", "目標株価・中央値", "目標株価・高値",
    ]:
        assert f'"{label}"' in text
    assert "help=\"Yahoo Finance系データにある総合的な推奨区分" in text
    assert "機械翻訳" in text
    assert "原文を表示" in text
