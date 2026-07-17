"""Port of src/truesignal/connectors/telegram.test.ts."""
import pytest

from truesignal.connectors.telegram import telegram_connector
from truesignal.types import ConnectorNotConfiguredError


def test_is_unconfigured_with_no_bot_token_and_raises_rather_than_fetching(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert telegram_connector.is_configured() is False
    with pytest.raises(ConnectorNotConfiguredError):
        telegram_connector.fetch_items()


def test_uses_the_official_get_updates_bot_api_method_never_t_me_s_scraping(monkeypatch, cache_dir):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    called_urls = []

    def _get_json(url):
        called_urls.append(url)
        return {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "channel_post": {
                        "message_id": 5,
                        "date": 1750000000,
                        "chat": {"id": 111, "title": "Example Channel", "username": "examplechan"},
                        "text": "A real channel post",
                    },
                }
            ],
        }

    monkeypatch.setattr("truesignal.connectors.telegram.get_json", _get_json)

    items = telegram_connector.fetch_items()
    assert len(items) == 1
    assert items[0].url == "https://t.me/examplechan/5"
    assert "api.telegram.org" in called_urls[0]
    assert "getUpdates" in called_urls[0]
    assert "t.me/s/" not in called_urls[0]


def test_skips_messages_from_chats_with_no_public_username(monkeypatch, cache_dir):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(
        "truesignal.connectors.telegram.get_json",
        lambda url: {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "message_id": 9,
                        "date": 1750000000,
                        "chat": {"id": 222, "title": "Private group"},
                        "text": "private message with no public username",
                    },
                }
            ],
        },
    )
    assert telegram_connector.fetch_items() == []


def test_skips_messages_with_no_text_or_caption(monkeypatch, cache_dir):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(
        "truesignal.connectors.telegram.get_json",
        lambda url: {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "channel_post": {"message_id": 9, "date": 1750000000, "chat": {"id": 1, "username": "chan"}},
                }
            ],
        },
    )
    assert telegram_connector.fetch_items() == []


def test_falls_back_rather_than_fabricating_when_the_bot_api_reports_ok_false(monkeypatch, cache_dir):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(
        "truesignal.connectors.telegram.get_json",
        lambda url: {"ok": False, "description": "Unauthorized"},
    )
    assert telegram_connector.fetch_items() == []


def test_truncates_very_long_message_text_rather_than_emitting_an_unbounded_title(monkeypatch, cache_dir):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    long_text = "a" * 200
    monkeypatch.setattr(
        "truesignal.connectors.telegram.get_json",
        lambda url: {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "channel_post": {
                        "message_id": 1,
                        "date": 1750000000,
                        "chat": {"id": 1, "username": "chan"},
                        "text": long_text,
                    },
                }
            ],
        },
    )

    [item] = telegram_connector.fetch_items()
    assert len(item.title) <= 120
    assert item.title.endswith("…")
