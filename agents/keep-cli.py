#!/usr/bin/env python3
"""CLI tool to access Google Keep via Chrome CDP."""

import asyncio
import json
import random
import sys
import urllib.parse
import urllib.request

import websockets


CDP_URL = "http://localhost:9222"
KEEP_URL = "https://keep.google.com/"


def _js_string(value):
    return json.dumps(value, ensure_ascii=False)


async def get_keep_page_ws():
    """Find the Keep page WebSocket URL."""
    resp = urllib.request.urlopen(f"{CDP_URL}/json/list")
    pages = json.loads(resp.read())
    for page in pages:
        if page.get("type") != "page":
            continue
        url = page.get("url", "")
        if "keep.google.com" in url:
            return page["webSocketDebuggerUrl"]
    raise RuntimeError(
        "Google Keep page not found in Chrome. Run ~/keep-start.sh and log in first."
    )


class KeepCDP:
    def __init__(self):
        self.ws = None
        self.pending = {}
        self.reader_task = None

    async def connect(self):
        ws_url = await get_keep_page_ws()
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

    async def evaluate(self, expression, timeout=20):
        mid = random.randint(10000, 99999)
        req = {
            "id": mid,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        }
        fut = asyncio.get_event_loop().create_future()
        self.pending[mid] = fut
        await self.ws.send(json.dumps(req))
        resp = await asyncio.wait_for(fut, timeout=timeout)
        self.pending.pop(mid, None)
        if "exceptionDetails" in resp.get("result", {}):
            raise RuntimeError(json.dumps(resp["result"]["exceptionDetails"], ensure_ascii=False))
        return resp.get("result", {}).get("result", {}).get("value")

    async def close(self):
        if self.reader_task:
            self.reader_task.cancel()
        if self.ws:
            await self.ws.close()


async def ensure_keep_ready(cdp):
    """Ensure Keep is open and loaded."""
    status = await cdp.evaluate(
        """
        (async () => {
            if (!location.href.startsWith('https://keep.google.com')) {
                location.href = 'https://keep.google.com/';
                return 'navigating';
            }
            if (document.body.innerText.includes('Google Keep')) {
                return 'ready';
            }
            return 'loading';
        })()
        """
    )
    if status == "navigating":
        await asyncio.sleep(5)
    for _ in range(20):
        ready = await cdp.evaluate(
            """
            (() => {
                const body = document.body.innerText || '';
                if (body.includes('Sign in') && body.includes('Google')) return 'signin';
                if (
                    body.includes('Take a note') ||
                    body.includes('メモを入力') ||
                    body.includes('検索') ||
                    body.includes('Search') ||
                    body.includes('Keep') ||
                    document.querySelector('[role="textbox"]') ||
                    document.querySelector('input[aria-label*="検索"], input[aria-label*="Search"]')
                ) return 'ready';
                return 'loading';
            })()
            """
        )
        if ready == "ready":
            return
        if ready == "signin":
            raise RuntimeError("Google Keep is not logged in. Use VNC and sign in first.")
        await asyncio.sleep(1)
    raise RuntimeError("Google Keep did not finish loading.")


async def list_notes(cdp, limit=20):
    result = await cdp.evaluate(
        f"""
        (() => {{
            const textboxes = [...document.querySelectorAll('[role="textbox"]')];
            const notes = [];
            for (const box of textboxes) {{
                const title = (box.innerText || '').trim();
                if (!title) continue;
                const root = box.closest('[jscontroller], [style*="transform"], [tabindex]') || box.parentElement;
                const text = root ? (root.innerText || '').trim() : title;
                const lines = text.split(/\\n+/).map(s => s.trim()).filter(Boolean);
                if (!lines.length) continue;
                const preview = lines.slice(1, 5).join(' | ');
                notes.push({{ title, preview }});
                if (notes.length >= {limit}) break;
            }}
            return notes;
        }})()
        """
    )
    print("=== Notes ===")
    for i, note in enumerate(result or [], 1):
        preview = f" :: {note['preview']}" if note.get("preview") else ""
        print(f"  {i}. {note['title']}{preview}")


async def search_notes(cdp, query):
    safe_query = _js_string(query)
    await cdp.evaluate(
        f"""
        (async () => {{
            const query = {safe_query};
            const input = document.querySelector('input[aria-label*="Search"], input[aria-label*="検索"]');
            if (!input) return 'search_input_not_found';
            input.focus();
            input.value = query;
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', bubbles: true }}));
            input.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', bubbles: true }}));
            return 'ok';
        }})()
        """
    )
    await asyncio.sleep(2)
    await list_notes(cdp, limit=20)


async def reset_view(cdp):
    await cdp.evaluate(
        """
        (() => {
            const search = document.querySelector('input[aria-label*="検索"], input[aria-label*="Search"]');
            if (search) {
                search.focus();
                search.value = '';
                search.dispatchEvent(new Event('input', { bubbles: true }));
            }
            return 'ok';
        })()
        """
    )


async def open_note(cdp, target):
    await reset_view(cdp)
    safe_target = _js_string(target)
    result = await cdp.evaluate(
        f"""
        (async () => {{
            const target = {safe_target};
            const activeTitle = [...document.querySelectorAll('[role="textbox"][contenteditable="true"]')]
                .find(e => getComputedStyle(e).display !== 'none' && (e.innerText || '').trim());
            if (activeTitle && (activeTitle.innerText || '').trim() === target) {{
                return target;
            }}
            const closeBtn = [...document.querySelectorAll('div[role="button"],button')].find(
                e => /閉じる|Close/.test((e.getAttribute('aria-label') || '') + ' ' + (e.innerText || ''))
            );
            if (closeBtn) {{
                closeBtn.click();
                await new Promise(r => setTimeout(r, 500));
            }}

            const cards = [...document.querySelectorAll('[role="textbox"][contenteditable="false"]')];
            let best = null;
            let bestText = '';
            for (const card of cards) {{
                const title = (card.innerText || '').trim();
                if (!title) continue;
                const root = card.closest('[jscontroller], [style*="transform"], [tabindex]') || card.parentElement;
                const text = ((root && root.innerText) || card.innerText || '').trim();
                if (!text) continue;
                if (title === target) {{
                    best = root || card;
                    bestText = text;
                    break;
                }}
                if (!best && text.includes(target) && (!bestText || text.length < bestText.length)) {{
                    best = root || card;
                    bestText = text;
                }}
            }}
            if (!best) return 'not_found';
            best.click();
            await new Promise(r => setTimeout(r, 800));
            return bestText;
        }})()
        """
    )
    if result == "not_found":
        raise RuntimeError(f"Note not found: {target}")
    await asyncio.sleep(1)


async def read_current_note(cdp):
    result = await cdp.evaluate(
        """
        (() => {
            const activeTitle = [...document.querySelectorAll('[role="textbox"][contenteditable="true"]')]
                .find(e => getComputedStyle(e).display !== 'none' && (e.innerText || '').trim());
            if (!activeTitle) return null;

            const root = activeTitle.closest('.IZ65Hb-s2gQvd') ||
                activeTitle.closest('[jscontroller]') ||
                activeTitle.parentElement;
            const title = (activeTitle.innerText || '').trim();

            const listItems = [...root.querySelectorAll('[contenteditable="true"][aria-label="リストアイテム"]')].map(item => {
                const row = item.closest('.MPu53c-bN97Pc-sM5MNb') || item.parentElement;
                const checkbox = row ? row.querySelector('[role="checkbox"]') : null;
                return {
                    text: (item.innerText || '').trim(),
                    checked: checkbox ? checkbox.getAttribute('aria-checked') === 'true' : false,
                };
            }).filter(item => item.text);

            const body = listItems.length
                ? listItems.map(item => (item.checked ? '[x] ' : '[ ] ') + item.text).join('\\n')
                : (root.innerText || '')
                    .split(/\\n+/)
                    .map(s => s.trim())
                    .filter(Boolean)
                    .filter(s => s !== title && s !== '固定済み' && s !== 'その他' && s !== '閉じる')
                    .join('\\n');

            return { title, body };
        })()
        """
    )
    if not result:
        print("(note not open)")
        return
    print(f"=== {result.get('title') or '(untitled)'} ===")
    if result.get("body"):
        print(result["body"])


async def create_note(cdp, title, body):
    note_text = title if not body else f"{title}\n\n{body}"
    safe_text = _js_string(note_text)
    result = await cdp.evaluate(
        f"""
        (async () => {{
            if (!location.href.startsWith('https://keep.google.com')) {{
                location.href = 'https://keep.google.com/';
                await new Promise(r => setTimeout(r, 3000));
            }}

            const closeBtn = [...document.querySelectorAll('div[role="button"],button')].find(
                e => /閉じる|Close/.test((e.getAttribute('aria-label') || '') + ' ' + (e.innerText || ''))
            );
            if (closeBtn) {{
                closeBtn.click();
                await new Promise(r => setTimeout(r, 500));
            }}

            const search = document.querySelector('input[aria-label*="検索"], input[aria-label*="Search"]');
            if (search) {{
                search.value = '';
                search.dispatchEvent(new Event('input', {{ bubbles: true }}));
                await new Promise(r => setTimeout(r, 300));
            }}
            const takeNote = [...document.querySelectorAll('div, button')].find(
                el => /Take a note|メモを入力/.test((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || ''))
            );
            if (!takeNote) return 'take_note_not_found';
            takeNote.click();
            await new Promise(r => setTimeout(r, 500));

            const visibleEditors = [...document.querySelectorAll('[contenteditable="true"]')]
                .filter(el => getComputedStyle(el).display !== 'none');
            const bodyBox = visibleEditors[0];
            const closeButton = [...document.querySelectorAll('button, div[role="button"]')].find(
                el => /Close|閉じる/.test((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || ''))
            );

            if (!bodyBox || !closeButton) return 'editor_not_found';

            bodyBox.focus();
            bodyBox.innerText = {safe_text};
            bodyBox.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: {safe_text} }}));

            await new Promise(r => setTimeout(r, 800));
            closeButton.click();
            return 'created';
        }})()
        """
    )
    if result != "created":
        raise RuntimeError(f"Failed to create note: {result}")
    print(f"Created: {title}")


async def dump_page(cdp):
    result = await cdp.evaluate("document.body.innerText.substring(0, 15000)")
    print(result or "")


async def main():
    if len(sys.argv) < 2:
        print("Usage: keep-cli.py <command> [args]")
        print()
        print("Commands:")
        print("  list [--limit N]            List visible notes")
        print("  search <query>              Search notes")
        print("  open <query>                Open a note by partial match")
        print("  read                        Read currently open note")
        print("  create <title> [body]       Create a text note")
        print("  dump                        Dump page text (debug)")
        print()
        print("Start Chrome first: ~/keep-start.sh")
        return

    cmd = sys.argv[1]
    cdp = KeepCDP()
    await cdp.connect()
    try:
        await ensure_keep_ready(cdp)
        if cmd == "list":
            limit = 20
            if len(sys.argv) >= 4 and sys.argv[2] == "--limit":
                limit = int(sys.argv[3])
            await list_notes(cdp, limit=limit)
        elif cmd == "search" and len(sys.argv) >= 3:
            await search_notes(cdp, " ".join(sys.argv[2:]))
        elif cmd == "open" and len(sys.argv) >= 3:
            await open_note(cdp, " ".join(sys.argv[2:]))
            await read_current_note(cdp)
        elif cmd == "read":
            await read_current_note(cdp)
        elif cmd == "create" and len(sys.argv) >= 3:
            title = sys.argv[2]
            body = sys.argv[3] if len(sys.argv) >= 4 else ""
            await create_note(cdp, title, body)
        elif cmd == "dump":
            await dump_page(cdp)
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)
    finally:
        await cdp.close()


if __name__ == "__main__":
    asyncio.run(main())
