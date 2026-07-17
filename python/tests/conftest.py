import tempfile
from pathlib import Path

import pytest

#: Every environment variable a connector reads credentials from. Cleared before every test so
#: test behavior is deterministic regardless of what happens to be set in the ambient shell or CI
#: runner -- a test that wants a connector "configured" sets these explicitly via monkeypatch.
_CONNECTOR_ENV_VARS = (
    "CLOUDFLARE_RADAR_API_TOKEN",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_SUBREDDIT",
    "TELEGRAM_BOT_TOKEN",
)


@pytest.fixture(autouse=True)
def _clear_connector_env(monkeypatch):
    for env_var in _CONNECTOR_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


@pytest.fixture()
def cache_dir(monkeypatch):
    """A fresh, isolated cache directory for every test, wired via TRUESIGNAL_CACHE_DIR -- mirrors
    the TypeScript suite's mkdtemp() + TRUESIGNAL_CACHE_DIR pattern in every *.test.ts file that
    touches the provenance layer."""
    with tempfile.TemporaryDirectory(prefix="truesignal-pytest-") as d:
        monkeypatch.setenv("TRUESIGNAL_CACHE_DIR", d)
        yield Path(d)
