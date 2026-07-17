"""Port of src/truesignal/connectors/reddit.test.ts."""
import pytest

from truesignal.connectors.reddit import REDDIT_DEFAULT_SUBREDDIT, reddit_connector
from truesignal.types import ConnectorNotConfiguredError


def _mock_token(monkeypatch):
    monkeypatch.setattr(
        "truesignal.connectors.reddit.post_form_json",
        lambda url, form_data, headers=None: {
            "access_token": "fake-access-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )


def test_is_unconfigured_with_no_credentials_and_raises_rather_than_fetching(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    assert reddit_connector.is_configured() is False
    with pytest.raises(ConnectorNotConfiguredError):
        reddit_connector.fetch_items()


def test_uses_the_official_oauth_api_never_unauthenticated_json_scraping(monkeypatch, cache_dir):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "fake-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "fake-secret")
    _mock_token(monkeypatch)

    called_urls = []

    def _get_json(url, headers=None):
        called_urls.append(url)
        assert headers is not None and headers.get("Authorization") == "Bearer fake-access-token"
        return {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Sample post",
                            "permalink": "/r/netsec/comments/abc123/sample_post/",
                            "created_utc": 1750000000,
                            "subreddit": "netsec",
                        }
                    }
                ]
            }
        }

    monkeypatch.setattr("truesignal.connectors.reddit.get_json", _get_json)

    [item] = reddit_connector.fetch_items()
    assert item.id == "reddit:abc123"
    assert item.url == "https://reddit.com/r/netsec/comments/abc123/sample_post/"
    assert item.summary == "r/netsec"
    assert "oauth.reddit.com" in called_urls[0]
    assert REDDIT_DEFAULT_SUBREDDIT in called_urls[0]


def test_honors_a_reddit_subreddit_override(monkeypatch, cache_dir):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "fake-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("REDDIT_SUBREDDIT", "netsecstudents")
    _mock_token(monkeypatch)

    called_urls = []

    def _get_json(url, headers=None):
        called_urls.append(url)
        return {"data": {"children": []}}

    monkeypatch.setattr("truesignal.connectors.reddit.get_json", _get_json)
    reddit_connector.fetch_items()
    assert "netsecstudents" in called_urls[0]


def test_falls_back_rather_than_fabricating_when_the_token_exchange_fails(monkeypatch, cache_dir):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "fake-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "fake-secret")

    def _raise(url, form_data, headers=None):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr("truesignal.connectors.reddit.post_form_json", _raise)
    assert reddit_connector.fetch_items() == []


def test_skips_a_single_post_with_a_missing_created_utc(monkeypatch, cache_dir):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "fake-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "fake-secret")
    _mock_token(monkeypatch)
    monkeypatch.setattr(
        "truesignal.connectors.reddit.get_json",
        lambda url, headers=None: {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "good",
                            "title": "Good post",
                            "permalink": "/r/netsec/comments/good/",
                            "created_utc": 1750000000,
                            "subreddit": "netsec",
                        }
                    },
                    {
                        "data": {
                            "id": "bad",
                            "title": "Bad post",
                            "permalink": "/r/netsec/comments/bad/",
                            "subreddit": "netsec",
                        }
                    },
                ]
            }
        },
    )

    items = reddit_connector.fetch_items()
    assert len(items) == 1
    assert items[0].id == "reddit:good"
