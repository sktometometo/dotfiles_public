#!/usr/bin/env python3
"""CLI tool to read Teams chat/channel content via Chrome CDP."""

import asyncio
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from chrome_cdp import ChromeCDP


CDP_URL = os.environ.get("TEAMS_CDP_URL", "http://localhost:9222")
CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")


def _load_teams_orgs():
    """Load Teams organizations from config file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("teams", {}).get("orgs", {})


TEAMS_ORGS = _load_teams_orgs()


class TeamsCDP(ChromeCDP):
    def __init__(self):
        super().__init__(
            CDP_URL,
            lambda page: "teams" in page.get("url", "") or "teams" in page.get("title", "").lower(),
        )


async def ensure_teams_ready(cdp):
    """Wait until the Teams shell is visible enough for DOM scraping."""
    for _ in range(20):
        state = await cdp.evaluate(
            """
            (() => {
                const body = document.body.innerText || '';
                const title = document.title || '';
                if (/sign in|login|サインイン/i.test(body) && !/Chat|Teams/i.test(title)) return 'signin';
                if (body.includes('Chat') || body.includes('Chats') || body.includes('Teams and channels') || body.includes('チャット')) return 'ready';
                return 'loading';
            })()
            """
        )
        if state == "ready":
            return
        if state == "signin":
            raise RuntimeError("Teams is not logged in. Use VNC and sign in first.")
        await asyncio.sleep(1)
    raise RuntimeError("Teams did not finish loading.")


def _normalize_name(text):
    return (text or "").strip()


def _is_chat_section(text):
    return _normalize_name(text).startswith(("Chats", "Chat", "チャット"))


def _is_teams_section(text):
    return _normalize_name(text).startswith(("Teams and channels", "Teams とチャネル"))


async def _get_treeitems(cdp):
    return await cdp.evaluate(
        """
        (() => {
            return [...document.querySelectorAll('[role="treeitem"]')].map((item, index) => ({
                index,
                level: item.getAttribute('aria-level'),
                expanded: item.getAttribute('aria-expanded'),
                text: (item.innerText || '').trim().replace(/\\n+/g, ' | ')
            }));
        })()
        """
    )


async def _ensure_teams_expanded(cdp):
    """Expand the 'Teams とチャネル' section if collapsed."""
    await cdp.evaluate(
        """
        (() => {
            const items = document.querySelectorAll('[role="treeitem"]');
            for (const item of items) {
                const text = (item.innerText || '').trim();
                if (text.startsWith('Teams とチャネル') || text.startsWith('Teams and channels')) {
                    if (item.getAttribute('aria-expanded') === 'false') {
                        item.click();
                    }
                    return true;
                }
            }
            return false;
        })()
        """
    )
    await asyncio.sleep(1)


async def list_chats(cdp):
    """List recent chats."""
    items = await _get_treeitems(cdp)
    chats = []
    in_chats = False
    for item in items:
        text = _normalize_name(item.get("text"))
        level = item.get("level")
        if not text:
            continue
        if level == "1" and _is_chat_section(text):
            in_chats = True
            continue
        if level == "1" and in_chats:
            break
        if in_chats and level == "2":
            chats.append(text)

    if not chats:
        chats = [
            _normalize_name(item.get("text"))
            for item in items
            if item.get("level") == "2" and _normalize_name(item.get("text")) and not _normalize_name(item.get("text")).startswith("See all your teams")
        ][:30]

    print("=== Recent Chats ===")
    if not chats:
        print("  (no chats found; Teams UI may still be loading)")
        return
    for i, chat in enumerate(chats, 1):
        print(f"  {i}. {chat}")


async def list_teams(cdp):
    """List teams and channels from treeitem DOM."""
    await _ensure_teams_expanded(cdp)
    treeitems = await _get_treeitems(cdp)
    items = []
    in_teams = False
    for item in treeitems:
        text = _normalize_name(item.get("text", "").split("|")[0])
        level = item.get("level")
        if not text:
            continue
        if level == "1" and _is_teams_section(item.get("text")):
            in_teams = True
            continue
        if level == "1" and in_teams:
            break
        if not in_teams:
            continue
        if level == "2":
            items.append({"type": "team", "name": text, "expanded": item.get("expanded")})
        elif level == "3" and text not in ("すべてのチャネルを表示する", "See all your teams"):
            items.append({"type": "channel", "name": text})

    print("=== Teams & Channels ===")
    if not items:
        print("  (no teams found; Teams UI may still be loading)")
        return
    for item in items:
        if item["type"] == "team":
            exp = "+" if item.get("expanded") == "false" else "-"
            print(f"\n  [{exp}] {item['name']}")
        else:
            print(f"      #{item['name']}")


async def open_channel(cdp, team_name, channel_name=None):
    """Open a team channel. If channel_name is None, open '一般'."""
    await _ensure_teams_expanded(cdp)
    ch = channel_name or "一般"
    safe_team = team_name.replace("\\", "\\\\").replace("'", "\\'")
    safe_ch = ch.replace("\\", "\\\\").replace("'", "\\'")

    result = await cdp.evaluate(f"""
        (() => {{
            const items = document.querySelectorAll('[role="treeitem"]');
            let inTeams = false;
            let foundTeam = false;

            for (const item of items) {{
                const level = item.getAttribute('aria-level');
                const text = item.innerText?.trim().split('\\n')[0]?.trim();
                if (!text) continue;

                if (text === 'Teams とチャネル' || text === 'Teams and Channels') {{
                    inTeams = true;
                    continue;
                }}
                if (!inTeams) continue;

                // Find the team
                if (level === '2' && text === '{safe_team}') {{
                    // Expand if collapsed
                    if (item.getAttribute('aria-expanded') === 'false') {{
                        item.click();
                    }}
                    foundTeam = true;
                    continue;
                }}

                // After finding the team, find the channel
                if (foundTeam && level === '3') {{
                    if (text === '{safe_ch}') {{
                        item.click();
                        return 'Opened: {safe_team} > ' + text;
                    }}
                }}
                // If we hit another team, stop
                if (foundTeam && level === '2') {{
                    break;
                }}
            }}

            if (!foundTeam) return 'Team not found: {safe_team}';
            return 'Channel not found: {safe_ch} in {safe_team}';
        }})()
    """)
    print(result)
    await asyncio.sleep(3)
    await read_current_chat(cdp)


async def read_current_chat(cdp):
    """Read the currently open chat/channel messages."""
    result = await cdp.evaluate("""
        (() => {
            // Try specific message containers
            const messageArea = document.querySelector('[data-tid*="message"], [class*="message-list"], [role="log"], [class*="chat-pane"]');
            if (messageArea) {
                return messageArea.innerText.substring(0, 10000);
            }
            // Fallback: full body
            return document.body.innerText.substring(0, 10000);
        })()
    """)
    print(result)


async def click_chat(cdp, name):
    """Click on a chat or channel by name."""
    safe_name = name.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    result = await cdp.evaluate(f"""
        (() => {{
            const target = '{safe_name}';
            const items = document.querySelectorAll('[role="treeitem"], [role="listitem"], [role="link"], a, button');
            let best = null;
            let bestLen = Infinity;
            for (const item of items) {{
                const text = item.textContent.trim();
                if (text.includes(target) && text.length < bestLen) {{
                    best = item;
                    bestLen = text.length;
                }}
            }}
            if (best) {{
                best.click();
                return 'Clicked: ' + best.textContent.trim().substring(0, 80);
            }}
            return 'Not found: ' + target;
        }})()
    """)
    print(result)
    await asyncio.sleep(3)
    await read_current_chat(cdp)


async def switch_org(cdp, org_key):
    """Switch Teams organization via profile menu."""
    org_name = TEAMS_ORGS.get(org_key)
    if not org_name:
        print(f"Unknown org: {org_key}")
        print(f"Available: {', '.join(f'{k} ({v})' for k, v in TEAMS_ORGS.items())}")
        return

    safe_name = org_name.replace("'", "\\'")

    # Check if already on the target org
    current_label = await cdp.evaluate("""
        (() => {
            const btn = document.querySelector('[data-tid="me-control-avatar-trigger"]');
            return btn ? btn.getAttribute('aria-label') || '' : '';
        })()
    """)
    if org_name in current_label:
        print(f"Already on {org_name}")
        return

    print(f"Switching to {org_name}...")

    # Click profile button, wait for menu, click target org (tenant item)
    result = await cdp.evaluate(f"""
        (async () => {{
            const btn = document.querySelector('[data-tid="me-control-avatar-trigger"]');
            if (!btn) return 'profile_button_not_found';
            btn.click();
            await new Promise(r => setTimeout(r, 3000));

            // Find tenant item by data-tid pattern
            const tenantItems = document.querySelectorAll('[data-tid^="me-control-tenant-item"]');
            for (const item of tenantItems) {{
                const text = item.textContent?.trim();
                if (text?.includes('{safe_name}')) {{
                    item.click();
                    return 'switching';
                }}
            }}
            // Fallback: menuitem with matching text
            const menuItems = document.querySelectorAll('[role="menuitem"]');
            for (const item of menuItems) {{
                const text = item.textContent?.trim();
                if (text?.includes('{safe_name}')) {{
                    item.click();
                    return 'switching';
                }}
            }}
            // Close menu if org not found
            document.body.click();
            return 'org_not_found_in_menu';
        }})()
    """)

    if 'switching' in result:
        print(f"  Switching... waiting for page reload")
        await asyncio.sleep(10)
        new_label = await cdp.evaluate("""
            (() => {
                const btn = document.querySelector('[data-tid="me-control-avatar-trigger"]');
                return btn ? btn.getAttribute('aria-label') || '' : '';
            })()
        """)
        print(f"  Current org: {new_label}")
    else:
        print(f"  {result}")


async def list_orgs():
    """List available Teams organizations."""
    print("=== Available Teams Organizations ===")
    for key, name in TEAMS_ORGS.items():
        print(f"  {key:10s}  {name}")


async def reload_page(cdp, wait=5):
    """Reload the current page and wait for it to settle."""
    await cdp.evaluate("location.reload()")
    await asyncio.sleep(wait)
    await ensure_teams_ready(cdp)


async def open_thread_reply_panel(cdp, max_retries=3):
    """Try to open the thread reply panel by clicking 'スレッドで返信'.

    Returns True if the reply editor becomes available, False otherwise.
    """
    for attempt in range(max_retries):
        # Check if reply editor is already open
        editor_count = await cdp.evaluate("""
            (() => {
                const editors = document.querySelectorAll('[role="textbox"][contenteditable="true"]');
                let count = 0;
                for (const e of editors) {
                    const rect = e.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) count++;
                }
                return String(count);
            })()
        """)
        if int(editor_count or "0") > 0:
            return True

        # Click 'スレッドで返信' - pick the last visible one (closest to the target thread)
        click_result = await cdp.evaluate("""
            (() => {
                const candidates = [];
                const els = document.querySelectorAll('a, button, span, div');
                for (const el of els) {
                    if (el.children.length > 3) continue;
                    const t = el.textContent.trim();
                    if (t === 'スレッドで返信' || t === 'Reply in thread') {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            candidates.push({el, y: rect.y});
                        }
                    }
                }
                if (candidates.length === 0) return 'not_found';
                // Click the last (bottom-most) one
                const target = candidates[candidates.length - 1];
                target.el.click();
                return 'clicked';
            })()
        """)
        if click_result == "not_found":
            # Try reload and retry
            await reload_page(cdp, wait=4)
            continue

        await asyncio.sleep(3)

    return False


async def goto_url(cdp, url, wait=8):
    """Navigate to a Teams URL and read the content.

    If the URL contains parentMessageId (thread URL), automatically
    opens the thread reply panel.
    """
    safe_url = url.replace("'", "\\'")
    await cdp.evaluate(f"window.location.href = '{safe_url}'")
    await asyncio.sleep(wait)
    # Reload to ensure thread reply UI is fully rendered
    await reload_page(cdp, wait=5)

    # If this is a thread URL, open the reply panel
    is_thread = "parentMessageId" in url
    if is_thread:
        opened = await open_thread_reply_panel(cdp)
        if opened:
            print("Thread reply panel opened", file=sys.stderr)
        else:
            print("Warning: could not open thread reply panel", file=sys.stderr)

    await read_current_chat(cdp)


async def reply_to_thread(cdp, body):
    """Reply to the currently open thread.

    Looks for the thread reply textbox specifically inside the thread panel.
    Will NOT fall back to chat editors or channel compose editors.
    Returns True if successful, False otherwise.
    """
    # Try to find and focus the thread reply editor
    focus_result = await cdp.evaluate(
        "(() => {"
        "  const editors = document.querySelectorAll('[contenteditable=true]');"
        "  for (const e of editors) {"
        "    const label = e.getAttribute('aria-label') || '';"
        "    if (/返信|reply/i.test(label)) {"
        "      const rect = e.getBoundingClientRect();"
        "      if (rect.width > 0 && rect.height > 0) {"
        "        e.focus();"
        "        return 'ok_reply';"
        "      }"
        "    }"
        "  }"
        "  return 'not_found';"
        "})()"
    )

    if focus_result == "not_found":
        return False

    await asyncio.sleep(0.3)
    await cdp.insert_text(body)
    await asyncio.sleep(1)

    # Verify content was inserted
    editor_len = await cdp.evaluate("""
        (() => {
            const editors = document.querySelectorAll('[role="textbox"][contenteditable="true"]');
            for (const e of editors) {
                if (e.textContent.length > 0) return String(e.textContent.length);
            }
            return '0';
        })()
    """)
    if editor_len == "0":
        print("Error: body text was not inserted into thread reply editor", file=sys.stderr)
        return False

    # Click send button - find by aria-label containing 送信/send
    btn_info = await cdp.evaluate(
        "(() => {"
        "  const buttons = document.querySelectorAll('button');"
        "  for (const b of buttons) {"
        "    const label = b.getAttribute('aria-label') || '';"
        "    if (/送信|send/i.test(label)) {"
        "      const rect = b.getBoundingClientRect();"
        "      if (rect.width > 0 && rect.height > 0) {"
        "        return JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2});"
        "      }"
        "    }"
        "  }"
        "  return '';"
        "})()"
    )
    if not btn_info:
        print("Error: send/reply button not found in thread", file=sys.stderr)
        return False

    coords = json.loads(btn_info)
    await cdp.click_at(coords["x"], coords["y"])
    await asyncio.sleep(3)
    print("Replied to thread successfully")
    return True


async def post_to_channel(cdp, body, subject=None):
    """Post a message to the currently open channel or reply to thread.

    If a thread is open, replies to the thread instead.

    Args:
        cdp: TeamsCDP instance.
        body: Message body text.
        subject: Optional subject line (creates a titled post).
    """
    # First, try to reply to an open thread (if we're in thread view)
    if not subject:
        thread_ok = await reply_to_thread(cdp, body)
        if thread_ok:
            return True

    # Click "チャネルで投稿" to open compose area
    result = await cdp.evaluate("""
        (() => {
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                if (b.textContent.trim() === 'チャネルで投稿') {
                    b.click();
                    return 'ok';
                }
            }
            return 'not_found';
        })()
    """)
    if result == "not_found":
        print("Error: 'チャネルで投稿' button not found. Is a channel open?", file=sys.stderr)
        return False

    await asyncio.sleep(2)

    # Set subject if provided
    if subject:
        await cdp.evaluate("""
            (() => {
                const s = document.querySelector('input[placeholder*="件名"]');
                if (s) { s.focus(); return 'ok'; }
                return 'no_subject_field';
            })()
        """)
        await asyncio.sleep(0.3)
        await cdp.insert_text(subject)
        await asyncio.sleep(0.5)

    # Focus editor and insert body
    focus_result = await cdp.evaluate("""
        (() => {
            const editor = document.querySelector('[role="textbox"][contenteditable="true"]');
            if (!editor) return 'no_editor';
            editor.focus();
            return 'ok';
        })()
    """)
    if focus_result == "no_editor":
        print("Error: compose editor not found", file=sys.stderr)
        return False

    await asyncio.sleep(0.3)
    await cdp.insert_text(body)
    await asyncio.sleep(1)

    # Verify content was inserted
    editor_len = await cdp.evaluate("""
        (() => {
            const editor = document.querySelector('[role="textbox"][contenteditable="true"]');
            return editor ? String(editor.textContent.length) : '0';
        })()
    """)
    if editor_len == "0":
        print("Error: body text was not inserted into editor", file=sys.stderr)
        return False

    # Click the send button (non-MenuButton 投稿)
    btn_info = await cdp.evaluate("""
        (() => {
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                if (b.textContent.trim() === '投稿' && !b.className.includes('MenuButton')) {
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2});
                    }
                }
            }
            return '';
        })()
    """)
    if not btn_info:
        print("Error: send button not found", file=sys.stderr)
        return False

    coords = json.loads(btn_info)
    await cdp.click_at(coords["x"], coords["y"])
    await asyncio.sleep(3)

    # Verify compose area closed (= post was sent)
    still_open = await cdp.evaluate("""
        (() => {
            const s = document.querySelectorAll('input[placeholder*="件名"]');
            const e = document.querySelector('[role="textbox"][contenteditable="true"]');
            return (s.length > 0 || (e && e.textContent.length > 0)) ? 'open' : 'closed';
        })()
    """)
    if still_open == "open":
        print("Warning: compose area may still be open — post might not have been sent", file=sys.stderr)
        return False

    print("Posted successfully")
    return True


async def read_thread(cdp, query):
    """Open a thread by matching query text, then read its replies."""
    safe_query = query.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

    # Click the matching thread or "N 件の返信" link
    click_result = await cdp.evaluate(f"""
        (() => {{
            const target = '{safe_query}';
            // First try to find a clickable "N 件の返信" element near matching text
            const allEls = document.querySelectorAll('*');
            let threadButton = null;
            let threadButtonLen = Infinity;
            for (const el of allEls) {{
                const text = el.textContent?.trim();
                if (!text) continue;
                // Match "件の返信" links
                if (text.match(/^\\d+ 件の返信/) && el.closest && el.closest('[role="treeitem"], [class*="thread"], [data-tid*="thread"]')) {{
                    // Check if a parent/sibling contains the query
                    const parent = el.closest('[role="treeitem"]') || el.parentElement?.parentElement?.parentElement;
                    if (parent && parent.textContent?.includes(target) && parent.textContent.length < threadButtonLen) {{
                        threadButton = el;
                        threadButtonLen = parent.textContent.length;
                    }}
                }}
            }}
            if (threadButton) {{
                threadButton.click();
                return 'clicked_reply_link';
            }}
            // Fallback: click on the thread post itself
            const items = document.querySelectorAll('[role="treeitem"], [role="listitem"], [role="link"], a, button');
            let best = null;
            let bestLen = Infinity;
            for (const item of items) {{
                const text = item.textContent?.trim();
                if (text?.includes(target) && text.length < bestLen) {{
                    best = item;
                    bestLen = text.length;
                }}
            }}
            if (best) {{
                best.click();
                return 'clicked_thread';
            }}
            return 'not_found';
        }})()
    """)

    if 'not_found' in click_result:
        print(f"Thread not found: {query}")
        return

    await asyncio.sleep(3)

    # Read thread panel content - it appears after the main channel content in the DOM
    result = await cdp.evaluate("""
        (() => {
            const body = document.body.innerText;
            // Thread panel typically appears as a second copy of content
            // Find the thread panel area by looking for repeated content or specific markers
            const maxLen = 30000;
            return body.substring(0, maxLen);
        })()
    """)

    # Extract thread panel content (appears after the main channel view)
    # In threaded layout, the side panel content follows "コンテキスト メニューあり" markers
    lines = result.split('\n')
    # Find where the thread panel starts (after channel content ends)
    panel_start = -1
    context_menu_count = 0
    for i, line in enumerate(lines):
        if 'コンテキスト メニューあり' in line:
            context_menu_count += 1
            if context_menu_count >= 2:
                panel_start = i + 1
                break

    if panel_start >= 0 and panel_start < len(lines):
        panel_text = '\n'.join(lines[panel_start:])
        # Remove trailing context menu markers
        for marker in ['コンテキスト メニューあり', '送信先: スレッドのみ']:
            panel_text = panel_text.replace(marker, '').strip()
        print(panel_text)
    else:
        # Fallback: print everything
        print(result)


async def get_page_text(cdp):
    """Dump the full page text (debug)."""
    result = await cdp.evaluate("document.body.innerText.substring(0, 10000)")
    print(result)


async def main():
    if len(sys.argv) < 2:
        print("Usage: teams-cli.py <command> [args]")
        print()
        print("Commands:")
        print("  orgs                     List available organizations")
        print("  org <name>               Switch Teams organization")
        print("  chats                    List recent chats")
        print("  teams                    List teams and channels")
        print("  team <team> [channel]    Open a team channel (default: 一般)")
        print("  read                     Read current chat/channel messages")
        print("  open <name>              Open a chat by name and read it")
        print("  post <body>              Post a message to the current channel")
        print("  post -s <subject> <body> Post with a subject line")
        print("  thread <query>           Open a thread by matching text and read replies")
        print("  goto <url>               Navigate to a Teams URL and read it")
        print("  reload                   Reload the current page")
        print("  dump                     Dump full page text (debug)")
        print()
        print("The post command reads body from argument or stdin (if '-').")
        print()
        print("Config: ~/.config/agent-tools/config.json")
        return

    cmd = sys.argv[1]

    # Commands that don't need CDP connection
    if cmd == "orgs":
        await list_orgs()
        return

    cdp = TeamsCDP()
    await cdp.connect()

    try:
        await ensure_teams_ready(cdp)
        if cmd == "org" and len(sys.argv) >= 3:
            await switch_org(cdp, sys.argv[2])
        elif cmd == "chats":
            await list_chats(cdp)
        elif cmd == "teams":
            await list_teams(cdp)
        elif cmd == "channels":
            await list_teams(cdp)
        elif cmd == "team" and len(sys.argv) >= 3:
            team = sys.argv[2]
            channel = sys.argv[3] if len(sys.argv) >= 4 else None
            await open_channel(cdp, team, channel)
        elif cmd == "read":
            await read_current_chat(cdp)
        elif cmd == "open" and len(sys.argv) >= 3:
            name = " ".join(sys.argv[2:])
            await click_chat(cdp, name)
        elif cmd == "goto" and len(sys.argv) >= 3:
            url = sys.argv[2]
            await goto_url(cdp, url)
        elif cmd == "post" and len(sys.argv) >= 3:
            subject = None
            args = sys.argv[2:]
            if args[0] == "-s" and len(args) >= 3:
                subject = args[1]
                args = args[2:]
            body_arg = " ".join(args)
            if body_arg == "-":
                body_arg = sys.stdin.read()
            await post_to_channel(cdp, body_arg, subject=subject)
        elif cmd == "thread" and len(sys.argv) >= 3:
            query = " ".join(sys.argv[2:])
            await read_thread(cdp, query)
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
