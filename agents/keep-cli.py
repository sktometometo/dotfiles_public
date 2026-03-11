#!/usr/bin/env python3
"""CLI tool to access Google Keep via Chrome CDP."""

import asyncio
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from chrome_cdp import ChromeCDP


CDP_URL = os.environ.get("KEEP_CDP_URL", "http://localhost:9223")
KEEP_URL = "https://keep.google.com/"


def _js_string(value):
    return json.dumps(value, ensure_ascii=False)


class KeepCDP(ChromeCDP):
    def __init__(self):
        super().__init__(
            CDP_URL,
            lambda page: "keep.google.com" in page.get("url", ""),
        )


async def ensure_keep_ready(cdp):
    """Ensure Keep is open and loaded."""
    status = await cdp.evaluate(
        f"""
        (() => {{
            if (!location.href.startsWith({json.dumps(KEEP_URL)})) {{
                location.href = {json.dumps(KEEP_URL)};
                return 'navigating';
            }}
            return 'ok';
        }})()
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


async def _close_open_note(cdp):
    button = await cdp.evaluate(
        """
        (() => {
            const isVisible = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            };
            const el = [...document.querySelectorAll('button, div[role="button"]')].find(
                node => isVisible(node) && /閉じる|Close/.test(((node.getAttribute('aria-label') || '') + ' ' + (node.innerText || '')).trim())
            );
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        })()
        """
    )
    if button:
        await cdp.click_at(button["x"], button["y"])
        await asyncio.sleep(0.8)


async def _goto_notes_tab(cdp):
    target = await cdp.evaluate(
        """
        (() => {
            const isVisible = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            };
            const tab = [...document.querySelectorAll('[role="tab"]')].find(
                el => isVisible(el) && ((el.getAttribute('aria-label') || '') === 'メモ' || (el.innerText || '').trim() === 'メモ')
            );
            if (!tab) return null;
            const r = tab.getBoundingClientRect();
            return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        })()
        """
    )
    if target:
        await cdp.click_at(target["x"], target["y"])
        await asyncio.sleep(0.5)


async def reset_view(cdp):
    await _goto_notes_tab(cdp)
    await _close_open_note(cdp)
    await cdp.evaluate(
        """
        (() => {
            window.scrollTo(0, 0);
            const input = document.querySelector('input[aria-label*="検索"], input[aria-label*="Search"]');
            if (!input) return 'no_search';
            input.focus();
            input.value = '';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            return 'ok';
        })()
        """
    )
    await asyncio.sleep(0.5)


async def list_notes(cdp, limit=20):
    await reset_view(cdp)
    result = await cdp.evaluate(
        f"""
        (() => {{
            const isVisible = el => {{
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 80 && r.top < window.innerHeight;
            }};
            const seen = new Set();
            const notes = [];
            const titles = [...document.querySelectorAll('[role="textbox"][contenteditable="false"]')];
            for (const titleEl of titles) {{
                if (!isVisible(titleEl)) continue;
                const title = (titleEl.innerText || '').trim();
                if (!title || seen.has(title)) continue;
                const root = titleEl.closest('[jscontroller], [tabindex]') || titleEl.closest('.IZ65Hb-s2gQvd') || titleEl.parentElement;
                if (!root || !isVisible(root)) continue;
                const text = (root.innerText || '').trim();
                const lines = text.split(/\\n+/).map(s => s.trim()).filter(Boolean);
                notes.push({{ title, preview: lines.slice(1, 5).join(' | ') }});
                seen.add(title);
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
    await _close_open_note(cdp)
    result = await cdp.evaluate(
        f"""
        (() => {{
            const input = document.querySelector('input[aria-label*="Search"], input[aria-label*="検索"]');
            if (!input) return 'search_input_not_found';
            input.focus();
            input.value = {safe_query};
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            return 'ok';
        }})()
        """
    )
    if result != "ok":
        raise RuntimeError(f"Search failed: {result}")
    await asyncio.sleep(1.5)
    await list_notes(cdp, limit=20)


async def open_note(cdp, target):
    await reset_view(cdp)
    safe_target = _js_string(target)
    result = await cdp.evaluate(
        f"""
        (async () => {{
            const target = {safe_target};
            const sleep = ms => new Promise(r => setTimeout(r, ms));
            const isVisible = el => {{
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 80 && r.top < window.innerHeight;
            }};
            const findCard = () => {{
                const exact = [];
                const partial = [];
                for (const titleEl of document.querySelectorAll('[role="textbox"][contenteditable="false"]')) {{
                    const title = (titleEl.innerText || '').trim();
                    if (!title || !isVisible(titleEl)) continue;
                    const root = titleEl.closest('[tabindex="0"]') || titleEl.closest('[jscontroller], [tabindex]') || titleEl.closest('.IZ65Hb-n0tgWb') || titleEl.parentElement;
                    if (!root || !isVisible(root)) continue;
                    const text = (root.innerText || '').trim();
                    const item = {{ title, text }};
                    if (title === target) exact.push(item);
                    else if (title.includes(target) || text.includes(target)) partial.push(item);
                }}
                return exact[0] || partial.sort((a, b) => a.text.length - b.text.length)[0] || null;
            }};

            const search = document.querySelector('input[aria-label*="Search"], input[aria-label*="検索"]');
            if (search) {{
                search.focus();
                search.value = target;
                search.dispatchEvent(new Event('input', {{ bubbles: true }}));
                await sleep(1200);
            }}

            window.scrollTo(0, 0);
            await sleep(300);
            for (let i = 0; i < 40; i++) {{
                const hit = findCard();
                if (hit) {{
                    for (const titleEl of document.querySelectorAll('[role="textbox"][contenteditable="false"]')) {{
                        const title = (titleEl.innerText || '').trim();
                        if (!title) continue;
                        const root = titleEl.closest('[tabindex="0"]') || titleEl.closest('[jscontroller], [tabindex]') || titleEl.closest('.IZ65Hb-n0tgWb') || titleEl.parentElement;
                        if (!root || !isVisible(root)) continue;
                        const text = (root.innerText || '').trim();
                        if (title !== hit.title && text !== hit.text) continue;
                        root.focus();
                        root.click();
                        await sleep(900);
                        return [...document.querySelectorAll('[contenteditable="true"][role="textbox"], [contenteditable="true"][role="combobox"]')].some(isVisible)
                            ? 'opened'
                            : 'clicked';
                    }}
                }}
                window.scrollBy(0, Math.max(400, window.innerHeight - 200));
                await sleep(400);
            }}
            return null;
        }})()
        """
    )
    if not result:
        raise RuntimeError(f"Note not found: {target}")
    if result not in ("opened", "clicked"):
        raise RuntimeError(f"Failed to open note: {result}")
    await asyncio.sleep(0.5)


async def read_current_note(cdp):
    result = await cdp.evaluate(
        r"""
        (() => {
            const isVisible = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            };
            const titleEditor = [...document.querySelectorAll('[contenteditable="true"][role="textbox"]')]
                .find(isVisible);
            const bodyEditor = [...document.querySelectorAll('[contenteditable="true"][role="combobox"]')]
                .find(isVisible);
            if (!titleEditor && !bodyEditor) return null;

            const titleText = (titleEditor ? titleEditor.innerText : '').trim();
            const title = titleText.split(/\n+/)[0].trim();

            const root = (bodyEditor || titleEditor).closest('.IZ65Hb-s2gQvd') ||
                (bodyEditor || titleEditor).closest('[jscontroller]') ||
                (bodyEditor || titleEditor).parentElement;

            const listItems = [...root.querySelectorAll('[role="checkbox"]')].map(box => {
                const row = box.closest('.bVEB4e-rymPhb-ibnC6b') ||
                    box.closest('.MPu53c-bN97Pc-sM5MNb') ||
                    box.parentElement;
                const textNode = row ? row.querySelector('.vIzZGf-fmcmS, .rymPhb-ibnC6b-bVEB4e-fmcmS-haAclf') : null;
                return {
                    text: textNode ? (textNode.innerText || '').trim() : '',
                    checked: box.getAttribute('aria-checked') === 'true',
                };
            }).filter(item => item.text);

            let body = '';
            if (listItems.length) {
                body = listItems.map(item => (item.checked ? '[x] ' : '[ ] ') + item.text).join('\\n');
            } else if (bodyEditor) {
                body = (bodyEditor.innerText || '').trim();
            } else if (titleText) {
                const lines = titleText.split(/\\n+/).map(s => s.trim()).filter(Boolean);
                body = lines.slice(1).join('\\n');
            }

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
    await ensure_keep_ready(cdp)
    await reset_view(cdp)
    composer = await cdp.evaluate(
        """
        (() => {
            const isVisible = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            };
            window.scrollTo(0, 0);
            const blankTitle = [...document.querySelectorAll('[contenteditable="true"][role="textbox"]')].find(
                el => isVisible(el) && !(el.innerText || '').trim()
            );
            const blankBody = [...document.querySelectorAll('[contenteditable="true"][role="combobox"]')].find(
                el => isVisible(el) && !((el.innerText || '').trim())
            );
            if (blankTitle && blankBody) return { status: 'ready' };

            const placeholder = [...document.querySelectorAll('.h1U9Be-xhiy4.qAWA2, .IZ65Hb-s2gQvd, .IZ65Hb-TBnied')].find(
                el => isVisible(el) && (el.innerText || '').trim() === 'メモを入力…'
            );
            if (!placeholder) return { status: 'composer_not_found' };
            const r = placeholder.getBoundingClientRect();
            return { status: 'click', x: r.x + r.width / 2, y: r.y + r.height / 2 };
        })()
        """
    )
    if composer and composer.get("status") == "click":
        await cdp.click_at(composer["x"], composer["y"])
        await asyncio.sleep(0.8)
    elif not composer or composer.get("status") != "ready":
        status = composer.get("status") if isinstance(composer, dict) else composer
        raise RuntimeError(f"Failed to find Keep composer: {status}")

    result = await cdp.evaluate(
        """
        (() => {
            const isVisible = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            };
            const titleEditor = [...document.querySelectorAll('[contenteditable="true"][role="textbox"]')].find(
                el => isVisible(el) && (el.getAttribute('aria-label') || '') === 'タイトル'
            ) || [...document.querySelectorAll('[contenteditable="true"][role="textbox"]')].find(
                el => isVisible(el) && !(el.innerText || '').trim()
            );
            const bodyEditor = [...document.querySelectorAll('[contenteditable="true"][role="combobox"]')].find(
                el => isVisible(el)
            );
            if (!titleEditor || !bodyEditor) return 'editor_not_found';
            titleEditor.focus();
            return 'ok';
        })()
        """
    )
    if result != "ok":
        raise RuntimeError(f"Failed to open note editor: {result}")

    await cdp.insert_text(title)
    await asyncio.sleep(0.2)

    body_target = await cdp.evaluate(
        """
        (() => {
            const isVisible = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            };
            const titleEditor = [...document.querySelectorAll('[contenteditable="true"][role="textbox"]')].find(isVisible);
            const root = titleEditor
                ? titleEditor.closest('.IZ65Hb-s2gQvd') || titleEditor.parentElement
                : null;
            const bodyEditor = root
                ? [...root.querySelectorAll('[role="combobox"]')].find(isVisible)
                : null;
            if (!bodyEditor) return null;
            const r = bodyEditor.getBoundingClientRect();
            return { x: r.x + Math.min(40, r.width / 2), y: r.y + Math.min(20, r.height / 2) };
        })()
        """
    )
    if not body_target:
        raise RuntimeError("Failed to focus note body: body_not_found")
    await cdp.click_at(body_target["x"], body_target["y"])
    await asyncio.sleep(0.1)
    if body:
        await cdp.insert_text(body)
        await asyncio.sleep(0.2)

    await _close_open_note(cdp)
    await asyncio.sleep(0.8)
    print(f"Created: {title}")


async def archive_note(cdp, target):
    await open_note(cdp, target)
    result = await cdp.evaluate(
        """
        (() => {
            const isVisible = el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            };
            const editor = [...document.querySelectorAll('[contenteditable="true"][role="textbox"], [contenteditable="true"][role="combobox"]')]
                .filter(isVisible)
                .sort((a, b) => (b.getBoundingClientRect().width * b.getBoundingClientRect().height) - (a.getBoundingClientRect().width * a.getBoundingClientRect().height))[0];
            if (!editor) return null;
            const er = editor.getBoundingClientRect();
            const button = [...document.querySelectorAll('button, div[role="button"]')].find(el => {
                if (!isVisible(el) || (el.getAttribute('aria-label') || '') !== 'アーカイブ') return false;
                const r = el.getBoundingClientRect();
                return r.x >= er.x - 20 && r.x <= er.right + 20 && r.y >= er.y - 20 && r.y <= er.bottom + 80;
            });
            if (!button) return null;
            const r = button.getBoundingClientRect();
            return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
        })()
        """
    )
    if not result:
        raise RuntimeError(f"Note not found for archive: {target}")
    await cdp.click_at(result["x"], result["y"])
    await asyncio.sleep(0.8)
    print(f"Archived: {target}")


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
        print("  open <query>                Open a note by exact/partial match")
        print("  read                        Read currently open note")
        print("  create <title> [body]       Create a text note")
        print("  archive <title>             Archive a note by exact title")
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
        elif cmd == "archive" and len(sys.argv) >= 3:
            await archive_note(cdp, " ".join(sys.argv[2:]))
        elif cmd == "dump":
            await dump_page(cdp)
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)
    finally:
        await cdp.close()


if __name__ == "__main__":
    asyncio.run(main())
