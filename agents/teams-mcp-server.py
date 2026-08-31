#!/usr/bin/env python3
"""MCP server exposing Teams access via Chrome CDP DOM scraping.

Wraps the same functions used by teams-cli.py so both the CLI and any
MCP client (Claude Code, Claude Desktop, other agents) share one
implementation. Useful for tenants where Teams Graph API scopes are not
available — this talks to the Teams web client's DOM instead.

Run as a stdio MCP server:
    python3 ~/teams-mcp-server.py

Register in an MCP client config, e.g. Claude Code's mcpServers:
    {
      "mcpServers": {
        "teams": {
          "command": "python3",
          "args": ["/home/shinjo/teams-mcp-server.py"]
        }
      }
    }
"""

import contextlib
import importlib.util
import io
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from mcp.server.fastmcp import FastMCP


def _load_teams_cli():
    """Load teams-cli.py as a module (hyphenated filename blocks plain import)."""
    path = os.path.join(SCRIPT_DIR, "teams-cli.py")
    spec = importlib.util.spec_from_file_location("teams_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tc = _load_teams_cli()

mcp = FastMCP("teams")


async def _run(fn, *args, **kwargs):
    """Call a teams_cli async command function, capturing its stdout.

    teams_cli's functions print results rather than returning them, so we
    connect to Chrome fresh for each call and capture printed output as the
    tool result. Keeping one connection per call avoids stale-state bugs
    from a long-lived CDP session across tool invocations.
    """
    cdp = tc.TeamsCDP()
    await cdp.connect()
    buf = io.StringIO()
    try:
        await tc.ensure_teams_ready(cdp)
        with contextlib.redirect_stdout(buf):
            result = await fn(cdp, *args, **kwargs)
        text = buf.getvalue()
        if result is not None and not text:
            text = str(result)
        return text or "(no output)"
    finally:
        await cdp.close()


@mcp.tool()
async def teams_orgs() -> str:
    """List Teams organizations configured in ~/.config/agent-tools/config.json."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        await tc.list_orgs()
    return buf.getvalue()


@mcp.tool()
async def teams_switch_org(org_key: str) -> str:
    """Switch the active Teams organization/tenant by its configured key."""
    return await _run(tc.switch_org, org_key)


@mcp.tool()
async def teams_list_chats() -> str:
    """List recent Teams chats in the left-hand chat list."""
    return await _run(tc.list_chats)


@mcp.tool()
async def teams_list_teams() -> str:
    """List Teams and their channels from the left-hand navigation tree."""
    return await _run(tc.list_teams)


@mcp.tool()
async def teams_open_channel(team_name: str, channel_name: str = "") -> str:
    """Open a channel within a team and read its messages.

    Args:
        team_name: Exact team name as shown in the Teams navigation tree.
        channel_name: Channel name; defaults to the general channel (一般) if omitted.
    """
    return await _run(tc.open_channel, team_name, channel_name or None)


@mcp.tool()
async def teams_read_current() -> str:
    """Read messages from whichever chat/channel is currently open."""
    return await _run(tc.read_current_chat)


@mcp.tool()
async def teams_open_chat(name: str) -> str:
    """Open a chat or channel by fuzzy name match and read its messages."""
    return await _run(tc.click_chat, name)


@mcp.tool()
async def teams_goto(url: str) -> str:
    """Navigate to a Teams deep link URL and read the resulting page content."""
    return await _run(tc.goto_url, url)


@mcp.tool()
async def teams_post(body: str, subject: str = "") -> str:
    """Post a message to the currently open channel.

    If a thread is currently open, replies to that thread instead of
    posting a new top-level message.

    Args:
        body: Message text to post.
        subject: Optional subject line to create a titled post (channels only).
    """
    return await _run(tc.post_to_channel, body, subject=subject or None)


@mcp.tool()
async def teams_read_thread(query: str) -> str:
    """Open a thread matched by text and read its replies.

    Args:
        query: Substring to match against the thread's root message text.
    """
    return await _run(tc.read_thread, query)


@mcp.tool()
async def teams_copy_message_link(query: str) -> str:
    """Find a message by text match and return its Teams deep link URL.

    Args:
        query: Substring to match against the target message's text.
    """
    return await _run(tc.copy_message_link, query)


@mcp.tool()
async def teams_reload() -> str:
    """Reload the current Teams page and wait for it to become ready."""
    return await _run(tc.reload_page)


@mcp.tool()
async def teams_dump_page() -> str:
    """Dump the current page's full visible text (debug aid)."""
    return await _run(tc.get_page_text)


@mcp.tool()
async def teams_screenshot(out_path: str, full_page: bool = False) -> str:
    """Save a PNG screenshot of the current Teams page.

    Args:
        out_path: Destination file path for the screenshot (.png/.jpg).
        full_page: Capture beyond the viewport when True.
    """
    saved = await _run(tc.take_screenshot, out_path, full_page=full_page)
    return f"Saved: {saved}" if not saved.startswith("Traceback") else saved


@mcp.tool()
async def teams_save_images(out_dir: str) -> str:
    """Save all message-attached images from the currently open chat/channel.

    Args:
        out_dir: Directory to write downloaded images into.
    """
    return await _run(tc.save_message_images, out_dir)


if __name__ == "__main__":
    mcp.run(transport="stdio")
