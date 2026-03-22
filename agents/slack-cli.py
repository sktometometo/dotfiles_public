#!/usr/bin/env python3
"""CLI tool to read/write Slack messages via Chrome CDP."""

import asyncio
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from chrome_cdp import ChromeCDP

CDP_URL = os.environ.get("SLACK_CDP_URL", "http://localhost:9223")
CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")


def _load_slack_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("slack", {})


SLACK_CONFIG = _load_slack_config()


class SlackCDP(ChromeCDP):
    def __init__(self):
        super().__init__(
            CDP_URL,
            lambda page: "slack" in page.get("url", "").lower()
            or "slack" in page.get("title", "").lower(),
        )


async def ensure_slack_ready(cdp):
    """Wait until the Slack shell is visible enough for DOM scraping."""
    for _ in range(20):
        state = await cdp.evaluate(
            """
            (() => {
                const body = document.body.innerText || '';
                const title = document.title || '';
                if (/sign in|サインイン|ログイン/i.test(body) && body.length < 2000) return 'signin';
                if (document.querySelector('[data-qa="channel_sidebar"]')
                    || document.querySelector('.p-channel_sidebar')
                    || document.querySelector('[class*="channel_sidebar"]')) return 'ready';
                if (/Slack/i.test(title) && body.length > 500) return 'ready';
                return 'loading';
            })()
            """
        )
        if state == "ready":
            return
        if state == "signin":
            raise RuntimeError("Slack is not logged in. Use VNC and sign in first.")
        await asyncio.sleep(1)
    raise RuntimeError("Slack did not finish loading.")


async def reload_page(cdp, wait=5):
    """Reload the current page and wait for it to settle."""
    await cdp.evaluate("location.reload()")
    await asyncio.sleep(wait)
    await ensure_slack_ready(cdp)


# ── Channel listing ──


async def list_channels(cdp):
    """List channels and DMs from the sidebar."""
    items = await cdp.evaluate(
        """
        (() => {
            const results = [];
            const seen = new Set();
            // Sidebar channel/DM items
            const els = document.querySelectorAll(
                '[data-qa-channel-sidebar-channel-type], ' +
                '.p-channel_sidebar__channel, ' +
                '[class*="channel_sidebar"] [role="treeitem"], ' +
                '[role="treeitem"]'
            );
            for (const el of els) {
                const text = (el.textContent || '').trim().replace(/\\n+/g, ' | ');
                if (text && text.length < 120 && !seen.has(text)) {
                    seen.add(text);
                    results.push(text);
                }
            }
            return results.slice(0, 60);
        })()
        """
    )
    print("=== Channels & DMs ===")
    if not items:
        print("  (no channels found; Slack UI may still be loading)")
        return
    for i, ch in enumerate(items, 1):
        print(f"  {i}. {ch}")


# ── Open channel/DM ──


async def open_channel(cdp, name):
    """Open a channel or DM using Ctrl+K quick switcher."""
    # Open quick switcher with Ctrl+K
    await cdp.shortcut("k")
    await asyncio.sleep(1)

    # Type channel name
    await cdp.insert_text(name)
    await asyncio.sleep(1.5)

    # Select the first result
    await cdp.press_enter()
    await asyncio.sleep(2)

    print(f"Opened: {name}")
    await read_messages(cdp)


# ── Read messages ──


async def read_messages(cdp):
    """Read messages from the currently open channel/DM."""
    result = await cdp.evaluate(
        """
        (() => {
            // Try the message pane / virtual list
            const selectors = [
                '.c-message_list',
                '.p-workspace__primary_view_body',
                '.p-message_pane__message_list',
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.innerText.trim().length > 50) {
                    return el.innerText.substring(0, 15000);
                }
            }
            // Fallback: primary view (excludes sidebar)
            const primary = document.querySelector(
                '.p-workspace__primary_view_body, ' +
                '.p-workspace__primary_view, ' +
                'main, [role="main"]'
            );
            if (primary) {
                return primary.innerText.substring(0, 15000);
            }
            // Last resort: extract from body, skip sidebar
            const body = document.body.innerText;
            const lines = body.split('\\n');
            // Find first message-like line (contains time pattern like HH:MM)
            const start = lines.findIndex(l => /\\d{1,2}:\\d{2}/.test(l));
            if (start > 0) {
                return lines.slice(Math.max(0, start - 2)).join('\\n').substring(0, 15000);
            }
            return body.substring(0, 10000);
        })()
        """
    )
    print(result)


# ── Post message ──


async def post_message(cdp, body):
    """Post a message to the currently open channel/DM."""
    focus_result = await cdp.evaluate(
        """
        (() => {
            const editor = document.querySelector(
                '[data-qa="message_input"] [role="textbox"], ' +
                '.ql-editor[contenteditable="true"], ' +
                '[role="textbox"][contenteditable="true"], ' +
                '[data-qa="message_compose_input"]'
            );
            if (!editor) return 'no_editor';
            editor.focus();
            return 'ok';
        })()
        """
    )
    if focus_result == "no_editor":
        print("Error: message editor not found. Is a channel open?", file=sys.stderr)
        return False

    await asyncio.sleep(0.3)
    await cdp.insert_text(body)
    await asyncio.sleep(0.5)

    # Verify text was inserted
    editor_len = await cdp.evaluate(
        """
        (() => {
            const editors = document.querySelectorAll(
                '[role="textbox"][contenteditable="true"], .ql-editor'
            );
            for (const e of editors) {
                if (e.textContent.trim().length > 0) return String(e.textContent.length);
            }
            return '0';
        })()
        """
    )
    if editor_len == "0":
        print("Error: message text was not inserted into editor", file=sys.stderr)
        return False

    await cdp.press_enter()
    await asyncio.sleep(2)

    # Verify editor cleared (= message was sent)
    editor_after = await cdp.evaluate(
        """
        (() => {
            const editors = document.querySelectorAll(
                '[role="textbox"][contenteditable="true"], .ql-editor'
            );
            for (const e of editors) {
                if (e.textContent.trim().length > 0) return 'still_has_text';
            }
            return 'cleared';
        })()
        """
    )
    if editor_after == "still_has_text":
        print("Warning: editor still has text — message might not have been sent", file=sys.stderr)
        return False

    print("Message sent")
    return True


# ── Thread ──


async def read_thread(cdp, query):
    """Open a thread by matching message text, then read replies."""
    safe_query = query.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    click_result = await cdp.evaluate(f"""
        (() => {{
            const target = '{safe_query}';
            const msgs = document.querySelectorAll(
                '[data-qa="message_container"], ' +
                '.c-message_kit__message, ' +
                '[class*="message_kit"]'
            );
            let best = null;
            let bestLen = Infinity;
            for (const msg of msgs) {{
                const text = msg.textContent?.trim();
                if (!text?.includes(target)) continue;
                if (text.length >= bestLen) continue;
                // Prefer the reply button if available
                const replyBtn = msg.querySelector(
                    '[data-qa="reply_bar_button"], ' +
                    'button[aria-label*="返信"], ' +
                    'button[aria-label*="reply"], ' +
                    'button[aria-label*="Reply"], ' +
                    '[class*="reply"]'
                );
                best = replyBtn || msg;
                bestLen = text.length;
            }}
            if (best) {{
                best.click();
                return 'clicked';
            }}
            return 'not_found';
        }})()
    """)

    if "not_found" in click_result:
        print(f"Thread not found: {query}")
        return

    await asyncio.sleep(3)
    await _read_thread_panel(cdp)


async def _read_thread_panel(cdp):
    """Read the thread panel content."""
    result = await cdp.evaluate(
        """
        (() => {
            const panel = document.querySelector(
                '[data-qa="thread_view"], ' +
                '.p-flexpane__inside, ' +
                '.p-workspace__secondary_view, ' +
                '[class*="thread_view"], ' +
                '[aria-label*="スレッド"], ' +
                '[aria-label*="Thread"]'
            );
            if (panel) return panel.innerText.substring(0, 15000);
            return document.body.innerText.substring(0, 10000);
        })()
        """
    )
    print(result)


async def reply_to_thread(cdp, body):
    """Reply to the currently open thread."""
    focus_result = await cdp.evaluate(
        """
        (() => {
            // Thread reply editor is inside the secondary view / flexpane
            const threadPanel = document.querySelector(
                '[data-qa="thread_view"], ' +
                '.p-flexpane__inside, ' +
                '.p-workspace__secondary_view'
            );
            if (threadPanel) {
                const editor = threadPanel.querySelector(
                    '[role="textbox"][contenteditable="true"], .ql-editor'
                );
                if (editor) {
                    editor.focus();
                    return 'ok_thread';
                }
            }
            // Fallback: use the last visible editor (often the thread one)
            const editors = document.querySelectorAll(
                '[role="textbox"][contenteditable="true"]'
            );
            const visible = [...editors].filter(e => {
                const r = e.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            });
            if (visible.length > 1) {
                visible[visible.length - 1].focus();
                return 'ok_last';
            }
            return 'not_found';
        })()
        """
    )
    if focus_result == "not_found":
        print("Error: thread reply editor not found. Is a thread open?", file=sys.stderr)
        return False

    await asyncio.sleep(0.3)
    await cdp.insert_text(body)
    await asyncio.sleep(0.5)
    await cdp.press_enter()
    await asyncio.sleep(2)
    print("Replied to thread")
    return True


# ── Search ──


async def search_messages(cdp, query):
    """Search for messages using Slack's search UI."""
    # Open search
    await cdp.evaluate(
        """
        (() => {
            const btn = document.querySelector(
                '[data-qa="top_nav_search"], ' +
                'button[aria-label*="検索"], ' +
                'button[aria-label*="Search"]'
            );
            if (btn) btn.click();
            return 'ok';
        })()
        """
    )
    await asyncio.sleep(1)

    # Focus search input and type query
    await cdp.evaluate(
        """
        (() => {
            const input = document.querySelector(
                '[data-qa="search_input"] input, ' +
                '[data-qa="focusable_search_input"], ' +
                'input[aria-label*="検索"], ' +
                'input[aria-label*="Search"], ' +
                '[role="combobox"]'
            );
            if (input) { input.focus(); input.value = ''; return 'ok'; }
            return 'no_input';
        })()
        """
    )
    await asyncio.sleep(0.3)
    await cdp.insert_text(query)
    await asyncio.sleep(0.5)
    await cdp.press_enter()
    await asyncio.sleep(3)

    # Read results
    result = await cdp.evaluate(
        """
        (() => {
            const results = document.querySelector(
                '[data-qa="search_results"], ' +
                '.p-search_results, ' +
                '[class*="search_results"]'
            );
            if (results) return results.innerText.substring(0, 15000);
            const main = document.querySelector('main, [role="main"]');
            if (main) return main.innerText.substring(0, 10000);
            return document.body.innerText.substring(0, 10000);
        })()
        """
    )
    print(result)


# ── Workspace switch ──


async def switch_workspace(cdp, workspace_name):
    """Switch Slack workspace via the workspace menu."""
    safe_name = workspace_name.replace("'", "\\'")

    result = await cdp.evaluate(f"""
        (() => {{
            const switcher = document.querySelector(
                '[data-qa="team-menu-trigger"], ' +
                '.p-ia__sidebar_header__team_name, ' +
                'button[aria-label*="ワークスペース"], ' +
                'button[aria-label*="workspace"]'
            );
            if (switcher) {{
                switcher.click();
                return 'opened_menu';
            }}
            return 'no_switcher';
        }})()
    """)
    if result == "no_switcher":
        print("Error: workspace switcher not found", file=sys.stderr)
        return

    await asyncio.sleep(2)

    click_result = await cdp.evaluate(f"""
        (() => {{
            const target = '{safe_name}';
            const items = document.querySelectorAll(
                '[role="menuitem"], [role="option"], a, button'
            );
            for (const item of items) {{
                const text = (item.textContent || '').trim();
                if (text.includes(target)) {{
                    item.click();
                    return 'switching';
                }}
            }}
            document.body.click();
            return 'not_found';
        }})()
    """)

    if click_result == "switching":
        print(f"Switching to {workspace_name}...")
        await asyncio.sleep(8)
        await ensure_slack_ready(cdp)
        print("Switched successfully")
    else:
        print(f"Workspace not found: {workspace_name}")


async def list_workspaces():
    """List configured workspace aliases."""
    workspaces = SLACK_CONFIG.get("workspaces", {})
    if not workspaces:
        print("No workspaces configured in config.json")
        return
    print("=== Workspaces ===")
    for key, name in workspaces.items():
        print(f"  {key:15s}  {name}")


# ── Navigation ──


async def goto_url(cdp, url, wait=5):
    """Navigate to a Slack URL and read the content."""
    safe_url = url.replace("'", "\\'")
    await cdp.evaluate(f"window.location.href = '{safe_url}'")
    await asyncio.sleep(wait)
    await ensure_slack_ready(cdp)
    await read_messages(cdp)


async def get_page_text(cdp):
    """Dump the full page text (debug)."""
    result = await cdp.evaluate("document.body.innerText.substring(0, 15000)")
    print(result)


# ── Main ──


async def main():
    if len(sys.argv) < 2:
        print("Usage: slack-cli.py <command> [args]")
        print()
        print("Commands:")
        print("  workspaces               List configured workspaces")
        print("  workspace <name>         Switch workspace")
        print("  channels                 List channels/DMs from sidebar")
        print("  open <name>              Open a channel/DM by name and read it")
        print("  read                     Read messages in the current channel")
        print("  post <body>              Post a message to the current channel")
        print("  thread <query>           Open a thread by matching text and read replies")
        print("  reply <body>             Reply to the currently open thread")
        print("  search <query>           Search for messages")
        print("  goto <url>               Navigate to a Slack URL and read it")
        print("  reload                   Reload the current page")
        print("  dump                     Dump full page text (debug)")
        print()
        print("The post/reply commands read body from argument or stdin (if '-').")
        print()
        print("Config: ~/.config/agent-tools/config.json")
        return

    cmd = sys.argv[1]

    # Commands that don't need CDP connection
    if cmd == "workspaces":
        await list_workspaces()
        return

    cdp = SlackCDP()
    await cdp.connect()

    try:
        await ensure_slack_ready(cdp)
        if cmd == "workspace" and len(sys.argv) >= 3:
            name = " ".join(sys.argv[2:])
            ws_name = SLACK_CONFIG.get("workspaces", {}).get(name, name)
            await switch_workspace(cdp, ws_name)
        elif cmd == "channels":
            await list_channels(cdp)
        elif cmd == "open" and len(sys.argv) >= 3:
            name = " ".join(sys.argv[2:])
            await open_channel(cdp, name)
        elif cmd == "read":
            await read_messages(cdp)
        elif cmd == "post" and len(sys.argv) >= 3:
            body_arg = " ".join(sys.argv[2:])
            if body_arg == "-":
                body_arg = sys.stdin.read()
            await post_message(cdp, body_arg)
        elif cmd == "thread" and len(sys.argv) >= 3:
            query = " ".join(sys.argv[2:])
            await read_thread(cdp, query)
        elif cmd == "reply" and len(sys.argv) >= 3:
            body_arg = " ".join(sys.argv[2:])
            if body_arg == "-":
                body_arg = sys.stdin.read()
            await reply_to_thread(cdp, body_arg)
        elif cmd == "search" and len(sys.argv) >= 3:
            query = " ".join(sys.argv[2:])
            await search_messages(cdp, query)
        elif cmd == "goto" and len(sys.argv) >= 3:
            url = sys.argv[2]
            await goto_url(cdp, url)
        elif cmd == "reload":
            await reload_page(cdp)
            print("Page reloaded")
        elif cmd == "dump":
            await get_page_text(cdp)
        else:
            print(f"Unknown command: {cmd}")
    finally:
        await cdp.close()


if __name__ == "__main__":
    asyncio.run(main())
