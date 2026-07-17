"""
Reddit connector -- pulls new posts from a security/OSINT-relevant subreddit via Reddit's
official OAuth API (application-only "client_credentials" grant, read-only, public data).

Requires a free Reddit developer app (script or web app type) via REDDIT_CLIENT_ID and
REDDIT_CLIENT_SECRET. Never scrapes the unauthenticated .json endpoints -- that path violates
Reddit's API terms of service, which is exactly the failure mode this connector exists to not
repeat (see github.com/calesthio/Crucix issue #108).

Direct port of src/truesignal/connectors/reddit.ts.
"""
from __future__ import annotations

import base64
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .. import http
from .._util import format_iso8601
from ..provenance.stamp import fetch_with_fallback
from ..types import Connector, ConnectorNotConfiguredError, FeedItem, UnstampedItem

REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_BASE = "https://oauth.reddit.com"
REDDIT_DEFAULT_SUBREDDIT = "netsec"
REDDIT_MAX_ITEMS = 25
REDDIT_USER_AGENT = "truesignal-cli-python/0.1 (by /u/truesignal-oss)"

_CLIENT_ID_ENV_VAR = "REDDIT_CLIENT_ID"
_CLIENT_SECRET_ENV_VAR = "REDDIT_CLIENT_SECRET"
_SUBREDDIT_ENV_VAR = "REDDIT_SUBREDDIT"


def _is_configured() -> bool:
    return bool(
        os.environ.get(_CLIENT_ID_ENV_VAR, "").strip()
        and os.environ.get(_CLIENT_SECRET_ENV_VAR, "").strip()
    )


def _target_subreddit() -> str:
    return os.environ.get(_SUBREDDIT_ENV_VAR, "").strip() or REDDIT_DEFAULT_SUBREDDIT


def get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Any:
    """Thin wrapper over http.get_json -- gives tests a stable module-level attribute to
    monkeypatch, mirroring the TS suite's `vi.stubGlobal('fetch', ...)`."""
    return http.get_json(url, headers=headers)


def post_form_json(url: str, form_data: Dict[str, str], headers: Optional[Dict[str, str]] = None) -> Any:
    """Thin wrapper over http.post_form_json for the same reason as get_json above."""
    return http.post_form_json(url, form_data, headers=headers)


def _fetch_access_token(client_id: str, client_secret: str) -> str:
    basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    data = post_form_json(
        REDDIT_TOKEN_URL,
        {"grant_type": "client_credentials"},
        headers={
            "Authorization": f"Basic {basic_auth}",
            "User-Agent": REDDIT_USER_AGENT,
        },
    )
    access_token = data.get("access_token") if isinstance(data, dict) else None
    if not access_token:
        raise ValueError("Reddit token endpoint did not return an access_token")
    return access_token


def _to_unstamped_item(post: Dict[str, Any]) -> Optional[UnstampedItem]:
    # created_utc is expected to be a real Unix timestamp. A single post with a missing or
    # malformed created_utc is skipped rather than raised on -- one bad record in an
    # otherwise-good batch must not take down every other real item alongside it.
    post_id = post.get("id")
    permalink = post.get("permalink")
    created_utc = post.get("created_utc")
    if not post_id or not permalink or created_utc is None:
        return None
    try:
        parsed = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return UnstampedItem(
        id=f"reddit:{post_id}",
        source="reddit",
        title=post.get("title", ""),
        url=f"https://reddit.com{permalink}",
        timestamp=format_iso8601(parsed),
        summary=f"r/{post.get('subreddit', '')}",
    )


def _fetch_live() -> List[UnstampedItem]:
    client_id = os.environ.get(_CLIENT_ID_ENV_VAR)
    client_secret = os.environ.get(_CLIENT_SECRET_ENV_VAR)
    if not client_id or not client_secret:
        raise ConnectorNotConfiguredError("reddit")

    token = _fetch_access_token(client_id, client_secret)
    params = {"limit": str(REDDIT_MAX_ITEMS)}
    url = f"{REDDIT_API_BASE}/r/{_target_subreddit()}/new?{urllib.parse.urlencode(params)}"
    data = get_json(
        url,
        headers={"Authorization": f"Bearer {token}", "User-Agent": REDDIT_USER_AGENT},
    )
    children = ((data or {}).get("data") or {}).get("children") or []
    items = []
    for child in children:
        post = child.get("data") or {}
        item = _to_unstamped_item(post)
        if item is not None:
            items.append(item)
    return items


class RedditConnector(Connector):
    name = "reddit"
    label = "Reddit"
    requires_config = True
    config_env_vars = (_CLIENT_ID_ENV_VAR, _CLIENT_SECRET_ENV_VAR)

    def is_configured(self) -> bool:
        return _is_configured()

    def fetch_items(self) -> List[FeedItem]:
        if not _is_configured():
            raise ConnectorNotConfiguredError("reddit")
        return fetch_with_fallback("reddit", _fetch_live)


reddit_connector = RedditConnector()
