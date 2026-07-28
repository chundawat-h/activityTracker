from backend.database.article_repository import is_duplicate, save_article
from backend.matcher.keyword_matcher import KeywordMatchResult
from backend.parser.article_parser import ParsedArticle


def _sample_article(url="https://example.com/post-1", title="BMTC announces new routes"):
    return ParsedArticle(
        source="indianbureaucracy",
        url=url,
        title=title,
        published_date="July 28, 2026",
        body="Full article body here.",
        summary="Full article body here.",
    )


def test_is_duplicate_false_for_new_article(db_session):
    assert is_duplicate(db_session, "https://example.com/new", "Brand new title") is False


def test_save_article_then_detected_as_duplicate_by_url(db_session):
    article = _sample_article()
    save_article(db_session, article, matches=[])
    db_session.commit()

    assert is_duplicate(db_session, article.url, "A completely different title") is True


def test_save_article_then_detected_as_duplicate_by_title_hash(db_session):
    article = _sample_article(url="https://example.com/post-original")
    save_article(db_session, article, matches=[])
    db_session.commit()

    # Same title, republished under a different URL -> still a duplicate.
    assert is_duplicate(db_session, "https://example.com/post-republished", article.title) is True


def test_save_article_persists_keyword_matches(db_session):
    article = _sample_article()
    matches = [KeywordMatchResult(keyword="BMTC", category="Transport Body / STU")]
    stored = save_article(db_session, article, matches=matches)
    db_session.commit()

    assert stored.has_keyword_match is True
    assert len(stored.keyword_matches) == 1
    assert stored.keyword_matches[0].keyword == "BMTC"
