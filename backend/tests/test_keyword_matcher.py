from backend.matcher.keyword_matcher import get_keywords, load_keywords, match_keywords


def test_load_keywords_from_csv():
    keywords = load_keywords()
    texts = {k.text for k in keywords}
    assert "BMTC" in texts
    assert "KSRTC" in texts
    assert any(k.category == "Transport Body / STU" for k in keywords)


def test_case_insensitive_match():
    keywords = get_keywords()
    matches = match_keywords("The bmtc board approved a new route today.", keywords)
    matched_texts = {m.keyword for m in matches}
    assert "BMTC" in matched_texts


def test_word_boundary_avoids_partial_match():
    keywords = get_keywords()
    # "IAS" should NOT match inside an unrelated longer word like "BIAS" or "IASbc"
    matches = match_keywords("There was clear bias in the committee's decision.", keywords)
    matched_texts = {m.keyword for m in matches}
    assert "IAS" not in matched_texts


def test_multiple_keyword_matches_in_one_article():
    keywords = get_keywords()
    text = "MoRTH and KSRTC jointly announced a new EV bus policy."
    matches = match_keywords(text, keywords)
    matched_texts = {m.keyword for m in matches}
    assert "MoRTH" in matched_texts
    assert "KSRTC" in matched_texts
    assert len(matches) >= 2


def test_multiword_keyword_with_punctuation_matches():
    keywords = get_keywords()
    text = "Adil Khan, IAS has been appointed Transport Commissioner."
    matches = match_keywords(text, keywords)
    matched_texts = {m.keyword for m in matches}
    assert "Adil Khan, IAS" in matched_texts


def test_no_match_returns_empty_list():
    keywords = get_keywords()
    matches = match_keywords("A completely unrelated article about cricket scores.", keywords)
    assert matches == []


def test_empty_text_returns_empty_list():
    assert match_keywords("") == []
    assert match_keywords(None) == []
