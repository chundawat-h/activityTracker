from backend.parser.article_parser import parse_article, parse_articles
from backend.scraper.base import ScrapedArticle


def test_parse_article_basic_fields():
    raw = ScrapedArticle(
        source="indianbureaucracy",
        url="https://www.indianbureaucracy.com/some-post/",
        title="  Some Officer IAS appointed as Secretary  ",
        published_date="July 28, 2026",
        body="Paragraph one.\n\n\nParagraph two.",
        summary=None,
    )
    parsed = parse_article(raw)
    assert parsed is not None
    assert parsed.title == "Some Officer IAS appointed as Secretary"
    assert parsed.summary is not None
    assert "Paragraph one." in parsed.summary


def test_parse_article_missing_title_returns_none():
    raw = ScrapedArticle(source="x", url="https://example.com/a", title="", body="body")
    assert parse_article(raw) is None


def test_parse_article_missing_url_returns_none():
    raw = ScrapedArticle(source="x", url="", title="Title")
    assert parse_article(raw) is None


def test_parse_articles_filters_invalid_entries():
    raw_list = [
        ScrapedArticle(source="x", url="https://example.com/a", title="Valid Title"),
        ScrapedArticle(source="x", url="", title="Invalid - no url"),
    ]
    parsed = parse_articles(raw_list)
    assert len(parsed) == 1
    assert parsed[0].title == "Valid Title"


def test_summary_is_truncated_when_long():
    long_body = "word " * 300  # > SUMMARY_MAX_LEN
    raw = ScrapedArticle(source="x", url="https://example.com/a", title="T", body=long_body)
    parsed = parse_article(raw)
    assert parsed is not None
    assert len(parsed.summary) <= 500
