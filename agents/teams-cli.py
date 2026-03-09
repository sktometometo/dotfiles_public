#!/usr/bin/env python3
"""CLI tool to read Teams chat/channel content via Chrome CDP."""

import asyncio
import json
import os
import random
import sys
import websockets


CDP_URL = "http://localhost:9222"
CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")


def _load_teams_orgs():
    """Load Teams organizations from config file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("teams", {}).get("orgs", {})


TEAMS_ORGS = _load_teams_orgs()


async def get_teams_page_ws():
    """Find the Teams page WebSocket URL."""
    import urllib.request
    resp = urllib.request.urlopen(f"{CDP_URL}/json/list")
    pages = json.loads(resp.read())
    for p in pages:
        if p["type"] == "page" and "teams" in p["url"]:
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("Teams page not found in Chrome. Is Chrome running with --remote-debugging-port=9222?")


class TeamsCDP:
    def __init__(self):
        self.ws = None
        self.pending = {}
        self.reader_task = None

    async def connect(self):
        ws_url = await get_teams_page_ws()
        self.ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
        self.reader_task = asyncio.create_task(self._reader())

    async def _reader(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                mid = msg.get("id")
                if mid and mid in self.pending:
                    self.pending[mid].set_result(msg)
        except Exception:
            pass

    async def evaluate(self, expression, timeout=15):
        mid = random.randint(10000, 99999)
        req = {"id": mid, "method": "Runtime.evaluate",
               "params": {"expression": expression, "awaitPromise": True}}
        fut = asyncio.get_event_loop().create_future()
        self.pending[mid] = fut
        await self.ws.send(json.dumps(req))
        resp = await asyncio.wait_for(fut, timeout=timeout)
        del self.pending[mid]
        return resp.get("result", {}).get("result", {}).get("value", "")

    async def cdp_call(self, method, params=None, timeout=15):
        """Send a raw CDP command."""
        mid = random.randint(10000, 99999)
        req = {"id": mid, "method": method, "params": params or {}}
        fut = asyncio.get_event_loop().create_future()
        self.pending[mid] = fut
        await self.ws.send(json.dumps(req))
        resp = await asyncio.wait_for(fut, timeout=timeout)
        del self.pending[mid]
        return resp

    async def insert_text(self, text):
        """Insert text at the current focus using CDP Input.insertText."""
        await self.cdp_call("Input.insertText", {"text": text})

    async def click_at(self, x, y):
        """Click at coordinates using CDP Input.dispatchMouseEvent."""
        for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
            params = {"type": event_type, "x": x, "y": y, "button": "left"}
            if event_type in ("mousePressed", "mouseReleased"):
                params["clickCount"] = 1
            await self.cdp_call("Input.dispatchMouseEvent", params)

    async def close(self):
        if self.reader_task:
            self.reader_task.cancel()
        if self.ws:
            await self.ws.close()


async def _ensure_teams_expanded(cdp):
    """Expand the 'Teams とチャネル' section if collapsed."""
    await cdp.evaluate("""
        (() => {
            const items = document.querySelectorAll('[role="treeitem"]');
            for (const item of items) {
                const text = item.innerText?.trim();
                if (text === 'Teams とチャネル' || text === 'Teams and Channels') {
                    if (item.getAttribute('aria-expanded') === 'false') {
                        item.click();
                    }
                    return;
                }
            }
        })()
    """)
    await asyncio.sleep(1)


async def list_chats(cdp):
    """List recent chats."""
    result = await cdp.evaluate("""
        (() => {
            const items = document.querySelectorAll('[role="treeitem"]');
            const chats = [];
            let inChat = false;
            for (const item of items) {
                const level = item.getAttribute('aria-level');
                const text = item.innerText?.trim().replace(/\\n+/g, ' | ');
                if (!text) continue;
                // Chat section is level 2 under "チャット" parent
                if (level === '1' && (text.startsWith('チャット') || text.startsWith('Chat'))) {
                    inChat = true;
                    continue;
                }
                if (level === '1' && inChat) break;
                if (inChat && level === '2' && text.length < 200) {
                    chats.push(text);
                }
                if (chats.length >= 30) break;
            }
            // Fallback if level-based didn't work
            if (chats.length === 0) {
                for (const item of items) {
                    const text = item.innerText?.trim().replace(/\\n+/g, ' | ');
                    if (text && text.length > 2 && text.length < 200) chats.push(text);
                    if (chats.length >= 30) break;
                }
            }
            return JSON.stringify(chats);
        })()
    """)
    chats = json.loads(result)
    print("=== Recent Chats ===")
    for i, chat in enumerate(chats, 1):
        print(f"  {i}. {chat}")


async def list_teams(cdp):
    """List teams and channels from treeitem DOM."""
    await _ensure_teams_expanded(cdp)
    result = await cdp.evaluate("""
        (() => {
            const items = document.querySelectorAll('[role="treeitem"]');
            const teams = [];
            let inTeams = false;
            for (const item of items) {
                const level = item.getAttribute('aria-level');
                const expanded = item.getAttribute('aria-expanded');
                const text = item.innerText?.trim().split('\\n')[0]?.trim();
                if (!text) continue;
                if (text === 'Teams とチャネル' || text === 'Teams and Channels') {
                    inTeams = true;
                    continue;
                }
                if (!inTeams) continue;
                // level 2 = team, level 3 = channel
                if (level === '2') {
                    teams.push({type: 'team', name: text, expanded});
                } else if (level === '3' && text !== 'すべてのチャネルを表示する') {
                    teams.push({type: 'channel', name: text});
                }
            }
            return JSON.stringify(teams);
        })()
    """)
    items = json.loads(result)
    print("=== Teams & Channels ===")
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


async def goto_url(cdp, url, wait=8):
    """Navigate to a Teams URL and read the content."""
    safe_url = url.replace("'", "\\'")
    await cdp.evaluate(f"window.location.href = '{safe_url}'")
    await asyncio.sleep(wait)
    await read_current_chat(cdp)


async def post_to_channel(cdp, body, subject=None):
    """Post a message to the currently open channel.

    Args:
        cdp: TeamsCDP instance.
        body: Message body text.
        subject: Optional subject line (creates a titled post).
    """
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
        print("  goto <url>               Navigate to a Teams URL and read it")
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
        elif cmd == "dump":
            await get_page_text(cdp)
        else:
            print(f"Unknown command: {cmd}")
    finally:
        await cdp.close()


if __name__ == "__main__":
    asyncio.run(main())
