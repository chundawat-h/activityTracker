from backend.database.models import compute_title_hash


def test_title_hash_is_case_and_whitespace_insensitive():
    h1 = compute_title_hash("BMTC announces new routes")
    h2 = compute_title_hash("  bmtc   ANNOUNCES new routes  ")
    assert h1 == h2


def test_title_hash_differs_for_different_titles():
    h1 = compute_title_hash("BMTC announces new routes")
    h2 = compute_title_hash("KSRTC announces new routes")
    assert h1 != h2
