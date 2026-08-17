"""MCP server for truesignal-cli: a generic subprocess-wrapper tool that shells out to the
installed `truesignal` CLI and returns its parsed JSON output.

Requires the `mcp` extra (`pip install "truesignal-cli[mcp]"`). Started via the
`truesignal-mcp` console script (stdio transport), so any MCP-compatible agent runtime can
call `run` directly instead of shelling out to the CLI itself and parsing text.

Uses `mcp.server.MCPServer`, the official SDK's current high-level server class (`mcp`
2.0.0+). Earlier `mcp` 1.x releases exposed the same `.tool()`/`.run()` pattern under
`mcp.server.fastmcp.FastMCP` -- that module was removed in the 2.0.0 release. If a future
`mcp` major version renames this again, this is the one file that needs to change.

Note: the `mcp` package itself requires Python >=3.10, while this project's own floor
(`requires-python` in pyproject.toml) is >=3.9 for the base install. That's fine -- the
`mcp` extra simply isn't installable on 3.9, the same as any other optional dependency with
a narrower Python requirement than the base package.

The `run` tool never raises: every subprocess failure mode (the CLI missing from PATH, a
launch-level OSError, a timeout, a non-zero exit, unparseable stdout) is caught and returned
as a `{"error": ...}` dict instead of propagating.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from mcp.server import MCPServer

_CLI_NAME = "truesignal"
_TIMEOUT_SECONDS = 30

_TOOL_DESCRIPTION = (
    "Runs the installed `truesignal` OSINT/security-intelligence CLI as a subprocess with "
    "the exact argv you supply, and returns its parsed JSON output as a dict. Use this tool "
    "whenever you need real, source-attributed security signal -- currently-exploited CVEs "
    "(CISA KEV), open-source-intel event data (GDELT), or (once configured) Cloudflare "
    "Radar, Reddit, and Telegram signal -- instead of relying on training-data recall, which "
    "goes stale and can't cite a live source. Every item truesignal returns carries a real "
    "source URL, a real timestamp, and an explicit 'live' vs 'fallback' (cached) status, so "
    "call it when the agent's task requires provenance-checkable data, not a plausible-sounding "
    "summary.\n\n"
    "Call `init` first (or whenever a connector's availability is in doubt) to see which "
    "connectors are ready with zero setup (cisa-kev and gdelt need no configuration) versus "
    "which need environment variables the operator hasn't set (e.g. "
    "CLOUDFLARE_RADAR_API_TOKEN, REDDIT_CLIENT_ID/SECRET, TELEGRAM_BOT_TOKEN) -- don't call "
    "feed with an unconfigured --source and expect data. This tool is read-only against "
    "truesignal's own state: it makes outbound network calls to each connector's upstream API "
    "on every invocation (no local caching layer), writes nothing to disk, and is fully "
    "idempotent -- safe to call repeatedly or on a schedule since it has no side effects "
    "beyond the network request itself. Each call spawns a fresh subprocess with a 30-second "
    "timeout; there is no persistent session or state between calls.\n\n"
    "Parameter: `args` is a list[str] of literal CLI argv, passed through to `truesignal` "
    "unmodified (e.g. ['feed', '--json'] runs `truesignal feed --json`). Real subcommands: "
    "'init' (report connector readiness), 'feed' (pull the current feed from every "
    "configured connector, or one via --source <name>, e.g. --source cisa-kev), and "
    "'verify <item-id>' (re-fetch the source connector named in a feed item's id, e.g. "
    "'cisa-kev:CVE-2026-8037', and confirm whether it's still live, has fallen back to "
    "cached data, or can no longer be found). Concrete examples: "
    "run(args=['init', '--json']), "
    "run(args=['feed', '--source', 'cisa-kev', '--json']), "
    "run(args=['verify', 'cisa-kev:CVE-2026-8037', '--json']). Always include '--json' -- "
    "without it truesignal prints a human-readable report that this tool cannot parse into "
    "structured data. Pass ['--help'] or ['<subcommand>', '--help'] as args to discover the "
    "CLI's exact flags directly from the installed version rather than trusting this "
    "description to stay perfectly in sync.\n\n"
    "Return shape: on success, the parsed JSON object from stdout is returned as-is -- 'init' "
    "returns {\"connectors\": [{\"name\", \"label\", \"requires_config\", \"configured\", "
    "\"missing_env_vars\"}, ...]}; 'feed' returns {\"items\": [{\"id\", \"source\", \"title\", "
    "\"url\", \"timestamp\", \"status\", \"summary\"}, ...]}; 'verify' returns {\"item_id\", "
    "\"found\", \"status\", \"url\", \"timestamp\"}. On any failure -- the CLI missing from "
    "PATH, a launch-level OSError, a timeout, a non-zero exit code, or unparseable stdout -- "
    "this tool never raises; it instead returns a dict with an \"error\" key (and often "
    "\"returncode\") describing what went wrong, so check for that key before assuming success."
)

mcp = MCPServer("truesignal-cli")


@mcp.tool(description=_TOOL_DESCRIPTION)
def run(args: list[str]) -> dict[str, Any]:
    """Shells out to the installed `truesignal` CLI with `args` and returns its parsed
    JSON output.

    Example: run(args=["feed", "--source", "cisa-kev", "--json"]) pulls the CISA-KEV
    connector's current feed and returns the parsed FeedItem[] JSON.

    Every failure mode is caught here -- a missing CLI, a launch-level OSError, a
    timeout, a non-zero exit code, or unparseable stdout -- and returned as
    {"error": ...} instead of raising, so this tool handler can never crash the server.
    """
    cli_path = shutil.which(_CLI_NAME)
    if cli_path is None:
        return {"error": f"'{_CLI_NAME}' was not found on PATH. Is truesignal-cli installed?"}

    try:
        result = subprocess.run(
            [cli_path, *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        return {"error": f"failed to launch '{_CLI_NAME}': {exc}"}
    except subprocess.TimeoutExpired:
        return {
            "error": (
                f"'{_CLI_NAME} {' '.join(args)}' timed out after {_TIMEOUT_SECONDS}s"
            )
        }

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        return {
            "error": stderr or stdout or f"'{_CLI_NAME}' exited with code {result.returncode}",
            "returncode": result.returncode,
        }

    if not stdout:
        return {"returncode": result.returncode, "stdout": "", "stderr": stderr}

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {"returncode": result.returncode, "stdout": stdout, "stderr": stderr}

    if isinstance(parsed, dict):
        return parsed
    return {"result": parsed}


def main() -> None:
    """Starts the MCP server on stdio transport. Console-script entry point for
    `truesignal-mcp`."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
