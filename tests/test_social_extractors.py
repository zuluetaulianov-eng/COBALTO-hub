# tests/test_social_extractors.py
import sys

sys.path.insert(0, ".")

from social_hub import fetch_bluesky, fetch_mastodon, fetch_twitterwebviewer


def test_fetch_bluesky_returns_list():
    res = fetch_bluesky("venezuela", max_items=3)
    assert isinstance(res, list)
    for item in res:
        assert "title" in item
        assert "link" in item
        assert "source" in item
        assert "Bluesky" in item["source"]


def test_fetch_mastodon_returns_list():
    res = fetch_mastodon("venezuela", max_items=3)
    assert isinstance(res, list)
    for item in res:
        assert "title" in item
        assert "link" in item
        assert "source" in item
        assert "Mastodon" in item["source"]


def test_fetch_twitterwebviewer_returns_list():
    res = fetch_twitterwebviewer("venezuela", max_items=3)
    assert isinstance(res, list)
    for item in res:
        assert "title" in item
        assert "link" in item
        assert "source" in item
