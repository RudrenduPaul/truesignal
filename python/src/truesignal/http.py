"""
Minimal HTTP helpers shared by every connector.

Uses only the standard library (``urllib.request``) so the package has zero third-party runtime
dependencies -- there is nothing here to pin or audit beyond Python itself. Every connector calls
``get_json`` or ``post_form_json`` instead of touching ``urllib`` directly, which is also what
makes the connectors easy to unit test: tests monkeypatch these two functions at the connector's
import site instead of mocking a whole HTTP stack.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_TIMEOUT_SECONDS = 10.0


class HttpError(Exception):
    """Raised when an upstream HTTP call returns a non-2xx status or an unreadable body."""

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        self.status = status
        super().__init__(message)


def _origin_only(url: str) -> str:
    """
    Reduces a URL to just its scheme and host for use in error messages. The Telegram connector
    embeds its bot token directly in the request path (``/bot{token}/getUpdates``, required by
    Telegram's own API shape) -- if a caller ever logs or surfaces an HttpError's message
    verbatim, the full URL would leak that credential. Every current call site swallows the
    exception before it reaches a log (see ``provenance/stamp.py``'s ``fetch_with_fallback``),
    so this isn't exploitable today, but error messages shouldn't rely on that as the only
    safeguard.
    """
    parsed = urllib.parse.urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else url


def get_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Performs a GET request and parses the response body as JSON. Raises HttpError on any
    non-2xx status or unparseable response -- callers never receive a partial/fabricated result."""
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 -- fixed https URLs only, see connectors
            status = getattr(response, "status", 200)
            body = response.read()
    except urllib.error.HTTPError as error:
        raise HttpError(f"HTTP request to {_origin_only(url)} returned HTTP {error.code}", status=error.code) from error
    except urllib.error.URLError as error:
        raise HttpError(f"HTTP request to {_origin_only(url)} failed: {error.reason}") from error

    if status >= 300:
        raise HttpError(f"HTTP request to {_origin_only(url)} returned HTTP {status}", status=status)

    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HttpError(f"HTTP request to {_origin_only(url)} returned a body that is not valid JSON") from error


def post_form_json(
    url: str,
    form_data: Dict[str, str],
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Performs a POST with a urlencoded form body and parses the JSON response. Used for the
    Reddit OAuth token exchange."""
    encoded = urllib.parse.urlencode(form_data).encode("utf-8")
    request_headers = dict(headers or {})
    request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    request = urllib.request.Request(url, data=encoded, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 -- fixed https URLs only, see connectors
            status = getattr(response, "status", 200)
            body = response.read()
    except urllib.error.HTTPError as error:
        raise HttpError(f"HTTP request to {_origin_only(url)} returned HTTP {error.code}", status=error.code) from error
    except urllib.error.URLError as error:
        raise HttpError(f"HTTP request to {_origin_only(url)} failed: {error.reason}") from error

    if status >= 300:
        raise HttpError(f"HTTP request to {_origin_only(url)} returned HTTP {status}", status=status)

    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HttpError(f"HTTP request to {_origin_only(url)} returned a body that is not valid JSON") from error
