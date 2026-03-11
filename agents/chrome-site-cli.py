#!/usr/bin/env python3
"""Generic CLI for browsing and operating arbitrary sites via Chrome CDP."""

import asyncio
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from chrome_cdp import ChromeCDP, fetch_cdp_targets


CDP_URL = os.environ.get("CHROME_SITE_CDP_URL", "http://localhost:9222")
MATCH_URL = os.environ.get("CHROME_SITE_MATCH_URL", "")


def usage():
    print("""Usage: chrome-site-cli.py <command> [args]

Commands:
  targets                              List current page targets
  title                                Print current page title and URL
  goto <url>                           Navigate current target to URL
  dump [--limit N]                     Print visible page text
  html [--limit N]                     Print page HTML
  eval <js>                            Evaluate JavaScript and print JSON/value
  click-text <text>                    Click shortest visible element matching text
  type <text>                          Insert text at current focus

Env:
  CHROME_SITE_CDP_URL   Chrome CDP base URL (default: http://localhost:9222)
  CHROME_SITE_MATCH_URL URL substring used to choose the target page
""")


def build_client():
    if not MATCH_URL:
        raise RuntimeError("Set CHROME_SITE_MATCH_URL to choose which tab to control.")
    return ChromeCDP(CDP_URL, lambda page: MATCH_URL in page.get("url", ""))


async def cmd_targets():
    pages = fetch_cdp_targets(CDP_URL)
    for i, page in enumerate(pages, 1):
        if page.get("type") != "page":
            continue
        title = page.get("title", "").replace("\n", " ")
        url = page.get("url", "")
        print(f"{i}. {title}\n   {url}")


async def cmd_with_client(action):
    cdp = build_client()
    await cdp.connect()
    try:
        await action(cdp)
    finally:
        await cdp.close()


def parse_limit(args, default):
    if len(args) >= 2 and args[0] == "--limit":
        return int(args[1])
    return default


async def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "targets":
        await cmd_targets()
        return

    if cmd == "title":
        await cmd_with_client(
            lambda cdp: _print_value(
                cdp.evaluate("({title: document.title, url: location.href})")
            )
        )
    elif cmd == "goto" and args:
        url = json.dumps(args[0], ensure_ascii=False)

        async def _goto(cdp):
            await cdp.evaluate(f"window.location.href = {url}")
            await asyncio.sleep(3)
            value = await cdp.evaluate("({title: document.title, url: location.href})")
            _render(value)

        await cmd_with_client(_goto)
    elif cmd == "dump":
        limit = parse_limit(args, 12000)
        await cmd_with_client(
            lambda cdp: _print_value(
                cdp.evaluate(f"(document.body.innerText || '').substring(0, {limit})")
            )
        )
    elif cmd == "html":
        limit = parse_limit(args, 12000)
        await cmd_with_client(
            lambda cdp: _print_value(
                cdp.evaluate(
                    f"(document.documentElement.outerHTML || '').substring(0, {limit})"
                )
            )
        )
    elif cmd == "eval" and args:
        expression = " ".join(args)
        await cmd_with_client(lambda cdp: _print_value(cdp.evaluate(expression)))
    elif cmd == "click-text" and args:
        target = json.dumps(" ".join(args), ensure_ascii=False)

        async def _click(cdp):
            result = await cdp.evaluate(
                f"""
                (() => {{
                    const target = {target};
                    const candidates = [...document.querySelectorAll('a, button, [role="button"], [role="link"], [role="treeitem"], [role="listitem"], div, span')];
                    let best = null;
                    let bestText = '';
                    for (const el of candidates) {{
                        const text = (el.innerText || el.textContent || '').trim();
                        const rect = el.getBoundingClientRect();
                        if (!text || !text.includes(target) || rect.width <= 0 || rect.height <= 0) continue;
                        if (!best || text.length < bestText.length) {{
                            best = el;
                            bestText = text;
                        }}
                    }}
                    if (!best) return {{ok: false, message: 'not found'}};
                    best.click();
                    return {{ok: true, message: bestText.substring(0, 200)}};
                }})()
                """
            )
            _render(result)

        await cmd_with_client(_click)
    elif cmd == "type" and args:
        text = " ".join(args)

        async def _type(cdp):
            await cdp.insert_text(text)
            print(f"Inserted {len(text)} chars")

        await cmd_with_client(_type)
    else:
        usage()
        sys.exit(1)


async def _print_value(awaitable):
    _render(await awaitable)


def _render(value):
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value if value is not None else "")


if __name__ == "__main__":
    asyncio.run(main())
