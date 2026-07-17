"""
Telegram connector -- pulls recent channel posts via the official Telegram Bot API's
`getUpdates` method. Requires a free bot token (from @BotFather) via TELEGRAM_BOT_TOKEN.

Never scrapes `t.me/s/*` with a spoofed User-Agent -- that path violates Telegram's terms of
service, which is exactly the failure mode this connector exists to not repeat (see
github.com/calesthio/Crucix issue #110).

Real API constraint, not a workaround: the Bot API only surfaces updates for chats the bot has
been added to as a member/admin, via long-polling `getUpdates`. Posts from a chat with no
public @username are skipped rather than linked with a fabricated URL -- every item this
connector emits must have a real, dereferenceable t.me link.

Direct port of src/truesignal/connectors/telegram.ts.
"""
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .. import http
from .._util import format_iso8601
from ..provenance.stamp import fetch_with_fallback
from ..types import Connector, ConnectorNotConfiguredError, FeedItem, UnstampedItem

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MAX_ITEMS = 25
_TITLE_MAX_LENGTH = 120

_TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"


def _is_configured() -> bool:
    return bool(os.environ.get(_TOKEN_ENV_VAR, "").strip())


def _truncate(text: str) -> str:
    return f"{text[:_TITLE_MAX_LENGTH - 1]}…" if len(text) > _TITLE_MAX_LENGTH else text


def _to_unstamped_item(message: Dict[str, Any]) -> Optional[UnstampedItem]:
    chat = message.get("chat") or {}
    username = chat.get("username")
    body = message.get("text") or message.get("caption")
    # Only chats with a public username produce a real, dereferenceable link -- private chats are
    # skipped rather than given a fabricated URL.
    if not username or not body:
        return None
    message_id = message.get("message_id")
    date = message.get("date")
    if message_id is None or date is None:
        return None
    parsed = datetime.fromtimestamp(float(date), tz=timezone.utc)
    chat_title = chat.get("title")
    return UnstampedItem(
        id=f"telegram:{chat.get('id')}:{message_id}",
        source="telegram",
        title=_truncate(body),
        url=f"https://t.me/{username}/{message_id}",
        timestamp=format_iso8601(parsed),
        summary=chat_title if chat_title is not None else None,
    )


def get_json(url: str) -> Any:
    """Thin wrapper over http.get_json -- gives tests a stable module-level attribute to
    monkeypatch, mirroring the TS suite's `vi.stubGlobal('fetch', ...)`."""
    return http.get_json(url)


def _fetch_live() -> List[UnstampedItem]:
    token = os.environ.get(_TOKEN_ENV_VAR)
    if not token:
        raise ConnectorNotConfiguredError("telegram")

    params = {"limit": str(TELEGRAM_MAX_ITEMS)}
    url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates?{urllib.parse.urlencode(params)}"
    data = get_json(url)
    if not isinstance(data, dict) or not data.get("ok"):
        description = (data or {}).get("description", "unknown error") if isinstance(data, dict) else "unknown error"
        raise ValueError(f"Telegram Bot API error: {description}")

    updates = data.get("result") or []
    items: List[UnstampedItem] = []
    for update in updates:
        message = update.get("channel_post") or update.get("message")
        if not message:
            continue
        item = _to_unstamped_item(message)
        if item is not None:
            items.append(item)
    return items


class TelegramConnector(Connector):
    name = "telegram"
    label = "Telegram"
    requires_config = True
    config_env_vars = (_TOKEN_ENV_VAR,)

    def is_configured(self) -> bool:
        return _is_configured()

    def fetch_items(self) -> List[FeedItem]:
        if not _is_configured():
            raise ConnectorNotConfiguredError("telegram")
        return fetch_with_fallback("telegram", _fetch_live)


telegram_connector = TelegramConnector()
