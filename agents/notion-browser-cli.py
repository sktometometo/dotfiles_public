#!/usr/bin/env python3
"""CLI tool to operate Notion through Chrome CDP."""

import asyncio
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from chrome_cdp import ChromeCDP


CDP_URL = os.environ.get("NOTION_CDP_URL", "http://localhost:9225")
NOTION_URL = os.environ.get("NOTION_URL", "https://www.notion.com/")


def usage():
    print(
        """Usage: notion-browser-cli.py <command> [args]

Commands:
  status                               Print login/page readiness
  open                                 Navigate to Notion
  title                                Print current page title and URL
  dump [--limit N]                     Print visible page text
  html [--limit N]                     Print page HTML
  pages [--limit N]                    List visible sidebar pages
  open-page <text>                     Open the shortest visible page match
  read                                 Print current page body text
  new-page <title>                     Create a new page from sidebar
  append <text>                        Append text to current page
  append-heading <level> <text>        Append a new heading block at page end
  delete-block <text>                  Delete the shortest matching text block
  heading <level> <text>               Convert matching block to heading 1/2/3
  insert-heading-before <level> <match> <heading>
                                       Insert a heading block before the matching block
  eval <js>                            Evaluate JavaScript and print JSON/value

Env:
  NOTION_CDP_URL   Chrome CDP URL (default: http://localhost:9225)
  NOTION_URL       Target URL (default: https://www.notion.so/)
"""
    )


class NotionCDP(ChromeCDP):
    def __init__(self):
        super().__init__(
            CDP_URL,
            lambda page: any(
                host in page.get("url", "")
                for host in ("notion.com", "notion.so", "notion.site")
            ),
        )


def _js_string(value):
    return json.dumps(value, ensure_ascii=False)


def _parse_limit(args, default):
    if len(args) >= 2 and args[0] == "--limit":
        return int(args[1])
    return default


def _render(value):
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value if value is not None else "")


async def with_client(action):
    cdp = NotionCDP()
    await cdp.connect()
    try:
        await ensure_notion_ready(cdp)
        await action(cdp)
    finally:
        await cdp.close()


async def ensure_notion_ready(cdp):
    initial = await cdp.evaluate(
        f"""
        (() => {{
            const target = {json.dumps(NOTION_URL)};
            const href = location.href;
            if (!href.startsWith('https://www.notion.com') &&
                !href.startsWith('https://www.notion.so') &&
                !href.startsWith('https://notion.site')) {{
                location.href = target;
                return {{ state: 'navigating', url: location.href }};
            }}
            const body = document.body?.innerText || '';
            const title = document.title || '';
            if (/log in|sign up|continue with google|メールアドレス|login/i.test(body)) {{
                return {{ state: 'signin', title, url: href }};
            }}
            if (document.querySelector('[contenteditable="true"], nav, [role="main"]')) {{
                return {{ state: 'ready', title, url: href }};
            }}
            return {{ state: 'loading', title, url: href }};
        }})()
        """
    )
    if initial["state"] == "navigating":
        await asyncio.sleep(4)

    current = initial
    for _ in range(20):
        current = await cdp.evaluate(
            """
            (() => {
                const body = document.body?.innerText || '';
                const title = document.title || '';
                const href = location.href;
                if (/log in|sign up|continue with google|メールアドレス|login/i.test(body)) {
                    return { state: 'signin', title, url: href };
                }
                if (document.querySelector('[contenteditable="true"], nav, [role="main"]')) {
                    return { state: 'ready', title, url: href };
                }
                return { state: 'loading', title, url: href };
            })()
            """
        )
        if current["state"] in ("ready", "signin"):
            return current
        await asyncio.sleep(1)
    return current


async def cmd_status(cdp):
    _render(await ensure_notion_ready(cdp))


async def cmd_open(cdp):
    await cdp.evaluate(f"location.href = {json.dumps(NOTION_URL)}")
    await asyncio.sleep(4)
    _render(await ensure_notion_ready(cdp))


async def cmd_title(cdp):
    _render(await cdp.evaluate("({title: document.title, url: location.href})"))


async def cmd_dump(cdp, limit):
    _render(await cdp.evaluate(f"(document.body.innerText || '').substring(0, {limit})"))


async def cmd_html(cdp, limit):
    _render(
        await cdp.evaluate(
            f"(document.documentElement.outerHTML || '').substring(0, {limit})"
        )
    )


async def cmd_pages(cdp, limit):
    result = await cdp.evaluate(
        f"""
        (() => {{
            const isVisible = el => {{
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            }};
            const seen = new Set();
            const items = [];
            const nodes = document.querySelectorAll('nav [role="treeitem"], nav a, nav div');
            for (const el of nodes) {{
                if (!isVisible(el)) continue;
                const text = (el.innerText || el.textContent || '').trim().replace(/\\n+/g, ' ');
                if (!text || text.length > 120) continue;
                if (/search|inbox|home|設定|templates|trash/i.test(text)) continue;
                const key = text.toLowerCase();
                if (seen.has(key)) continue;
                seen.add(key);
                items.push(text);
                if (items.length >= {limit}) break;
            }}
            return items;
        }})()
        """
    )
    print("=== Visible Notion Pages ===")
    for i, item in enumerate(result or [], 1):
        print(f"  {i}. {item}")


async def cmd_open_page(cdp, query):
    safe_query = _js_string(query)
    result = await cdp.evaluate(
        f"""
        (() => {{
            const target = {safe_query}.toLowerCase();
            const isVisible = el => {{
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            }};
            let best = null;
            let bestText = '';
            const candidates = document.querySelectorAll('nav [role="treeitem"], nav a, [data-block-id] a, [data-block-id] div');
            for (const el of candidates) {{
                if (!isVisible(el)) continue;
                const text = (el.innerText || el.textContent || '').trim().replace(/\\n+/g, ' ');
                if (!text) continue;
                const lower = text.toLowerCase();
                if (!lower.includes(target)) continue;
                if (!best || text.length < bestText.length) {{
                    best = el.closest('a, [role="treeitem"], div') || el;
                    bestText = text;
                }}
            }}
            if (!best) return {{ ok: false, message: 'not found' }};
            best.click();
            return {{ ok: true, message: bestText }};
        }})()
        """
    )
    _render(result)
    await asyncio.sleep(2)


async def _focus_page_editor(cdp):
    result = await cdp.evaluate(
        """
        (() => {
            const isVisible = el => {
                if (!el) return false;
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            };
            const candidates = [...document.querySelectorAll('[contenteditable="true"][role="textbox"][data-content-editable-leaf="true"]')]
                .filter(isVisible)
                .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
            const el = candidates[candidates.length - 1] ||
                [...document.querySelectorAll('[contenteditable="true"]')].filter(isVisible).pop();
            if (!el) return 'editor_not_found';
            el.focus();
            el.click();
            const range = document.createRange();
            range.selectNodeContents(el);
            range.collapse(false);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            return 'ok';
        })()
        """
    )
    if result != "ok":
        raise RuntimeError("Could not focus Notion editor.")


async def _focus_block_by_text(cdp, text):
    result = await cdp.evaluate(
        f"""
        (() => {{
            const target = {_js_string(text)};
            const isVisible = el => {{
                if (!el) return false;
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            }};
            let best = null;
            let bestText = '';
            const blocks = [...document.querySelectorAll('[contenteditable="true"][role="textbox"][data-content-editable-leaf="true"]')]
                .filter(isVisible);
            for (const el of blocks) {{
                const value = (el.innerText || '').trim();
                if (!value || !value.includes(target)) continue;
                if (!best || value.length < bestText.length) {{
                    best = el;
                    bestText = value;
                }}
            }}
            if (!best) return {{ ok: false, message: 'not found' }};
            best.focus();
            best.click();
            const range = document.createRange();
            range.selectNodeContents(best);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            return {{ ok: true, message: bestText }};
        }})()
        """
    )
    if not result.get("ok"):
        raise RuntimeError(f"Could not find block containing: {text}")
    return result["message"]


async def _focus_block_start_by_text(cdp, text):
    result = await cdp.evaluate(
        f"""
        (() => {{
            const target = {_js_string(text)};
            const isVisible = el => {{
                if (!el) return false;
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            }};
            let best = null;
            let bestText = '';
            const blocks = [...document.querySelectorAll('[contenteditable="true"][role="textbox"][data-content-editable-leaf="true"]')]
                .filter(isVisible);
            for (const el of blocks) {{
                const value = (el.innerText || '').trim();
                if (!value || !value.includes(target)) continue;
                if (!best || value.length < bestText.length) {{
                    best = el;
                    bestText = value;
                }}
            }}
            if (!best) return {{ ok: false, message: 'not found' }};
            best.focus();
            best.click();
            const range = document.createRange();
            range.selectNodeContents(best);
            range.collapse(true);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            return {{ ok: true, message: bestText }};
        }})()
        """
    )
    if not result.get("ok"):
        raise RuntimeError(f"Could not find block containing: {text}")
    return result["message"]


async def cmd_read(cdp):
    result = await cdp.evaluate(
        """
        (() => {
            const main = document.querySelector('[role="main"]') || document.querySelector('main');
            return (main?.innerText || document.body?.innerText || '').trim();
        })()
        """
    )
    print(result)


async def cmd_new_page(cdp, title):
    result = await cdp.evaluate(
        """
        (() => {
            const selectors = [
                'nav [aria-label*="New page"]',
                'nav [aria-label*="新規ページ"]',
                'nav [role="button"]',
                'nav button',
            ];
            for (const selector of selectors) {
                for (const el of document.querySelectorAll(selector)) {
                    const text = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).trim();
                    if (/new page|新規ページ/i.test(text)) {
                        el.click();
                        return 'clicked';
                    }
                }
            }
            return 'new_page_button_not_found';
        })()
        """
    )
    if result != "clicked":
        raise RuntimeError("Could not find Notion 'New page' button.")
    await asyncio.sleep(2)
    await _focus_page_editor(cdp)
    await cdp.insert_text(title)
    await cdp.press_enter()
    print(f"Created draft page: {title}")


async def cmd_append(cdp, text):
    await _focus_page_editor(cdp)
    await cdp.press_enter()
    await asyncio.sleep(0.15)
    await _focus_page_editor(cdp)
    chunks = text.split("\n")
    for i, chunk in enumerate(chunks):
        if chunk:
            await cdp.insert_text(chunk)
        if i != len(chunks) - 1:
            await cdp.press_enter()
            await asyncio.sleep(0.1)
    print(f"Inserted {len(text)} chars")


async def cmd_append_heading(cdp, level, text):
    if level not in {"1", "2", "3"}:
        raise RuntimeError("Heading level must be 1, 2, or 3.")
    await _focus_page_editor(cdp)
    await cdp.press_enter()
    await asyncio.sleep(0.15)
    prefix = "#" * int(level) + " "
    await cdp.type_text_keys(prefix)
    await asyncio.sleep(0.1)
    await cdp.type_text_keys(text)
    await asyncio.sleep(0.1)
    await cdp.press_enter()
    print(f"Inserted heading {level}: {text}")


async def cmd_delete_block(cdp, text):
    matched = await _focus_block_by_text(cdp, text)
    await cdp.press_key("Backspace", code="Backspace", windows_virtual_key_code=8)
    await asyncio.sleep(0.1)
    await cdp.press_key("Backspace", code="Backspace", windows_virtual_key_code=8)
    print(f"Deleted block matching: {matched}")


async def cmd_heading(cdp, level, text):
    if level not in {"1", "2", "3"}:
        raise RuntimeError("Heading level must be 1, 2, or 3.")
    matched = await _focus_block_by_text(cdp, text)
    cleaned = matched
    if cleaned.startswith("# "):
        cleaned = cleaned[2:]
    elif cleaned.startswith("## "):
        cleaned = cleaned[3:]
    elif cleaned.startswith("### "):
        cleaned = cleaned[4:]
    await cdp.press_key("Backspace", code="Backspace", windows_virtual_key_code=8)
    await asyncio.sleep(0.1)
    await cdp.type_text_keys(f"/heading {level}")
    await asyncio.sleep(0.4)
    await cdp.press_enter()
    await asyncio.sleep(0.3)
    await cdp.insert_text(cleaned)
    print(f"Converted to heading {level}: {cleaned}")


async def cmd_insert_heading_before(cdp, level, match_text, heading_text):
    await _focus_block_start_by_text(cdp, match_text)
    await cdp.press_enter()
    await asyncio.sleep(0.2)
    await cdp.insert_text(heading_text)
    await asyncio.sleep(0.2)
    await cmd_heading(cdp, level, heading_text)
    print(f"Inserted heading {level} before block matching: {match_text}")


async def cmd_eval(cdp, expression):
    _render(await cdp.evaluate(expression))


async def main():
    if len(sys.argv) < 2:
        usage()
        return 1

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "status":
        await with_client(cmd_status)
    elif cmd == "open":
        await with_client(cmd_open)
    elif cmd == "title":
        await with_client(cmd_title)
    elif cmd == "dump":
        await with_client(lambda cdp: cmd_dump(cdp, _parse_limit(args, 12000)))
    elif cmd == "html":
        await with_client(lambda cdp: cmd_html(cdp, _parse_limit(args, 12000)))
    elif cmd == "pages":
        await with_client(lambda cdp: cmd_pages(cdp, _parse_limit(args, 30)))
    elif cmd == "open-page" and args:
        await with_client(lambda cdp: cmd_open_page(cdp, " ".join(args)))
    elif cmd == "read":
        await with_client(cmd_read)
    elif cmd == "new-page" and args:
        await with_client(lambda cdp: cmd_new_page(cdp, " ".join(args)))
    elif cmd == "append" and args:
        await with_client(lambda cdp: cmd_append(cdp, " ".join(args)))
    elif cmd == "append-heading" and len(args) >= 2:
        await with_client(lambda cdp: cmd_append_heading(cdp, args[0], " ".join(args[1:])))
    elif cmd == "delete-block" and args:
        await with_client(lambda cdp: cmd_delete_block(cdp, " ".join(args)))
    elif cmd == "heading" and len(args) >= 2:
        await with_client(lambda cdp: cmd_heading(cdp, args[0], " ".join(args[1:])))
    elif cmd == "insert-heading-before" and len(args) >= 3:
        await with_client(
            lambda cdp: cmd_insert_heading_before(cdp, args[0], args[1], " ".join(args[2:]))
        )
    elif cmd == "eval" and args:
        await with_client(lambda cdp: cmd_eval(cdp, " ".join(args)))
    else:
        usage()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
