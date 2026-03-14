#!/usr/bin/env python3
"""CLI tool to access Money Forward via Chrome CDP."""

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from chrome_cdp import ChromeCDP


CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")
CDP_URL = os.environ.get("MONEYFORWARD_CDP_URL", "http://localhost:9225")
MONEYFORWARD_URL = os.environ.get("MONEYFORWARD_URL", "https://moneyforward.com/")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("moneyforward", {})


CONFIG = load_config()
OPENAI_MODEL = os.environ.get("MONEYFORWARD_OPENAI_MODEL", CONFIG.get("openai_model", "gpt-4.1-mini"))
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
SNAPSHOT_LINE_LIMIT = int(os.environ.get("MONEYFORWARD_LINE_LIMIT", "250"))
TABLE_ROW_LIMIT = int(os.environ.get("MONEYFORWARD_TABLE_ROW_LIMIT", "20"))
CARD_LIMIT = int(os.environ.get("MONEYFORWARD_CARD_LIMIT", "80"))


def usage():
    print(
        """Usage: moneyforward-cli.py <command> [args]

Commands:
  status                               Print login/page readiness
  title                                Print current page title and URL
  open                                 Navigate to Money Forward home
  dump [--limit N]                     Print visible page text
  snapshot                             Print structured JSON snapshot
  net-worth                            Print detected asset summary
  accounts [--limit N]                 Print detected account-like items
  transactions [--limit N]             Print detected transaction-like items
  ask <question>                       Answer a question from current Money Forward data
  eval <js>                            Evaluate JavaScript and print JSON/value

Env:
  MONEYFORWARD_CDP_URL         Chrome CDP URL (default: http://localhost:9225)
  MONEYFORWARD_URL             Target URL (default: https://moneyforward.com/)
  MONEYFORWARD_OPENAI_MODEL    Model used by ask (default: gpt-4.1-mini)
  OPENAI_API_KEY               Required for ask
"""
    )


class MoneyForwardCDP(ChromeCDP):
    def __init__(self):
        super().__init__(
            CDP_URL,
            lambda page: any(
                domain in page.get("url", "")
                for domain in ("moneyforward.com", "id.moneyforward.com")
            ),
        )


def _js_string(value):
    return json.dumps(value, ensure_ascii=False)


async def ensure_moneyforward_ready(cdp):
    status = await cdp.evaluate(
        f"""
        (() => {{
            const target = {json.dumps(MONEYFORWARD_URL)};
            if (!location.href.startsWith('https://moneyforward.com') &&
                !location.href.startsWith('https://id.moneyforward.com')) {{
                location.href = target;
                return {{ state: 'navigating', url: location.href }};
            }}

            const body = document.body?.innerText || '';
            const lower = body.toLowerCase();
            const title = document.title || '';
            const href = location.href;
            const signedOutHints = [
                'ログイン',
                'メールアドレス',
                'パスワード',
                'sign in',
                'login',
            ];
            if (signedOutHints.some(text => body.includes(text) || title.toLowerCase().includes(text))) {{
                return {{ state: 'signin', title, url: href }};
            }}

            const readyHints = [
                '資産',
                '家計簿',
                '口座',
                '入出金',
                '収支',
                'money forward me',
            ];
            if (readyHints.some(text => lower.includes(String(text).toLowerCase())) ||
                document.querySelector('table, [role="table"], nav, main')) {{
                return {{ state: 'ready', title, url: href }};
            }}
            return {{ state: 'loading', title, url: href }};
        }})()
        """
    )

    if status["state"] == "navigating":
        await asyncio.sleep(5)

    for _ in range(20):
        current = await cdp.evaluate(
            """
            (() => {
                const body = document.body?.innerText || '';
                const lower = body.toLowerCase();
                const title = document.title || '';
                const href = location.href;
                const signedOutHints = ['ログイン', 'メールアドレス', 'パスワード', 'sign in', 'login'];
                if (signedOutHints.some(text => body.includes(text) || title.toLowerCase().includes(text))) {
                    return { state: 'signin', title, url: href };
                }
                const readyHints = ['資産', '家計簿', '口座', '入出金', '収支', 'money forward me'];
                if (readyHints.some(text => lower.includes(text)) || document.querySelector('table, [role="table"], nav, main')) {
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


async def collect_snapshot(cdp):
    return await cdp.evaluate(
        f"""
        (() => {{
            const isVisible = el => {{
                if (!el) return false;
                const s = getComputedStyle(el);
                if (s.visibility === 'hidden' || s.display === 'none') return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
            }};

            const normalize = text => (text || '')
                .replace(/\\u00a0/g, ' ')
                .replace(/[ \\t]+/g, ' ')
                .split(/\\n+/)
                .map(line => line.trim())
                .filter(Boolean);

            const bodyLines = normalize(document.body?.innerText || '').slice(0, {SNAPSHOT_LINE_LIMIT});

            const tables = [...document.querySelectorAll('table, [role="table"]')]
                .filter(isVisible)
                .slice(0, 12)
                .map(table => {{
                    const headers = [...table.querySelectorAll('th')]
                        .map(th => (th.innerText || '').trim())
                        .filter(Boolean)
                        .slice(0, 12);
                    const rows = [...table.querySelectorAll('tr,[role="row"]')]
                        .slice(0, {TABLE_ROW_LIMIT})
                        .map(row => [...row.querySelectorAll('th,td,[role="cell"],[role="gridcell"],[role="rowheader"],[role="columnheader"]')]
                            .map(cell => (cell.innerText || '').trim())
                            .filter(Boolean)
                            .slice(0, 12))
                        .filter(row => row.length > 0);
                    return {{ headers, rows }};
                }})
                .filter(table => table.headers.length > 0 || table.rows.length > 0);

            const cards = [];
            const seen = new Set();
            for (const el of document.querySelectorAll('li, article, section, div')) {{
                if (!isVisible(el)) continue;
                const text = (el.innerText || '').trim();
                if (!text || text.length < 8 || text.length > 500) continue;
                if (!/[¥\\$€]/.test(text) && !/\\b\\d{{1,3}}(?:,\\d{{3}})+(?:\\.\\d+)?\\b/.test(text)) continue;
                const lines = normalize(text);
                if (lines.length < 2) continue;
                const key = lines.slice(0, 4).join('|');
                if (seen.has(key)) continue;
                seen.add(key);
                cards.push(lines.slice(0, 8));
                if (cards.length >= {CARD_LIMIT}) break;
            }}

            const yenLines = bodyLines.filter(line => /[¥￥]/.test(line)).slice(0, 120);
            const dateAmountLines = bodyLines.filter(line =>
                (/(\\d{{4}}[\\/.-]\\d{{1,2}}[\\/.-]\\d{{1,2}}|\\d{{1,2}}[\\/.-]\\d{{1,2}})/.test(line)) &&
                /[¥￥]|-?\\d{{1,3}}(?:,\\d{{3}})+/.test(line)
            ).slice(0, 120);

            return {{
                title: document.title,
                url: location.href,
                capturedAt: new Date().toISOString(),
                lines: bodyLines,
                yenLines,
                dateAmountLines,
                tables,
                cards,
            }};
        }})()
        """,
        timeout=30,
    )


def parse_limit(args, default):
    if len(args) >= 2 and args[0] == "--limit":
        return int(args[1])
    return default


def parse_amount(value):
    if not isinstance(value, str):
        return None
    text = value.replace("¥", "").replace("￥", "").replace(",", "").replace(" ", "")
    for token in (text, text.replace("+", "")):
        try:
            return float(token)
        except ValueError:
            continue
    return None


def extract_net_worth(snapshot):
    labels = ("資産", "純資産", "総資産", "金融資産", "net worth", "balance")
    found = []
    for line in snapshot.get("yenLines", []):
        lower = line.lower()
        if any(label in line or label in lower for label in labels):
            found.append(line)
    return found[:10]


def extract_accounts(snapshot, limit=20):
    results = []
    seen = set()
    for card in snapshot.get("cards", []):
        joined = " | ".join(card)
        if joined in seen:
            continue
        if not any(("¥" in line or "￥" in line) for line in card):
            continue
        if any(("/" in line or "-" in line) and ("¥" in line or "￥" in line) for line in card):
            continue
        results.append(card)
        seen.add(joined)
        if len(results) >= limit:
            return results

    for table in snapshot.get("tables", []):
        rows = table.get("rows", [])
        headers = table.get("headers", [])
        for row in rows:
            joined = " | ".join(row)
            if joined in seen:
                continue
            if headers and any("日付" in h or "date" in h.lower() for h in headers):
                continue
            if any(("¥" in cell or "￥" in cell) for cell in row):
                results.append(row)
                seen.add(joined)
            if len(results) >= limit:
                return results
    return results[:limit]


def extract_transactions(snapshot, limit=20):
    results = []
    seen = set()

    for line in snapshot.get("dateAmountLines", []):
        if line in seen:
            continue
        results.append([line])
        seen.add(line)
        if len(results) >= limit:
            return results

    for table in snapshot.get("tables", []):
        headers = table.get("headers", [])
        date_like = any("日付" in h or "date" in h.lower() for h in headers)
        amount_like = any("金額" in h or "amount" in h.lower() for h in headers)
        if not (date_like or amount_like):
            continue
        for row in table.get("rows", []):
            joined = " | ".join(row)
            if joined in seen:
                continue
            if any(("¥" in cell or "￥" in cell) for cell in row):
                results.append(row)
                seen.add(joined)
            if len(results) >= limit:
                return results
    return results[:limit]


def render_list(items):
    if not items:
        print("(no data)")
        return
    for i, item in enumerate(items, 1):
        if isinstance(item, list):
            print(f"{i}. " + " | ".join(item))
        else:
            print(f"{i}. {item}")


def call_openai(question, snapshot):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for ask")

    prompt = {
        "question": question,
        "moneyforward_snapshot": snapshot,
        "instructions": [
            "Answer only from the snapshot.",
            "If the data is insufficient, say what is missing.",
            "Be concise and cite the concrete rows/lines you relied on.",
            "If a calculation is needed, show the arithmetic briefly.",
        ],
    }

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You answer questions about Money Forward household finance data extracted from a browser page.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(prompt, ensure_ascii=False)}],
            },
        ],
    }

    req = urllib.request.Request(
        f"{OPENAI_BASE_URL}/responses",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {e.code}: {body_text}")

    if payload.get("output_text"):
        return payload["output_text"].strip()

    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


async def cmd_with_client(action):
    cdp = MoneyForwardCDP()
    await cdp.connect()
    try:
        await action(cdp)
    finally:
        await cdp.close()


async def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "status":
        async def _status(cdp):
            result = await ensure_moneyforward_ready(cdp)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        await cmd_with_client(_status)
        return

    if cmd == "title":
        await cmd_with_client(
            lambda cdp: _print_value(
                cdp.evaluate("({title: document.title, url: location.href})")
            )
        )
        return

    if cmd == "open":
        async def _open(cdp):
            await cdp.evaluate(f"location.href = {_js_string(MONEYFORWARD_URL)}")
            await asyncio.sleep(4)
            print(json.dumps(await ensure_moneyforward_ready(cdp), ensure_ascii=False, indent=2))

        await cmd_with_client(_open)
        return

    if cmd == "dump":
        limit = parse_limit(args, 12000)
        await cmd_with_client(
            lambda cdp: _print_value(
                cdp.evaluate(f"(document.body.innerText || '').substring(0, {limit})")
            )
        )
        return

    if cmd == "snapshot":
        async def _snapshot(cdp):
            await ensure_moneyforward_ready(cdp)
            print(json.dumps(await collect_snapshot(cdp), ensure_ascii=False, indent=2))

        await cmd_with_client(_snapshot)
        return

    if cmd == "net-worth":
        async def _net_worth(cdp):
            await ensure_moneyforward_ready(cdp)
            snapshot = await collect_snapshot(cdp)
            render_list(extract_net_worth(snapshot))

        await cmd_with_client(_net_worth)
        return

    if cmd == "accounts":
        limit = parse_limit(args, 20)

        async def _accounts(cdp):
            await ensure_moneyforward_ready(cdp)
            snapshot = await collect_snapshot(cdp)
            render_list(extract_accounts(snapshot, limit=limit))

        await cmd_with_client(_accounts)
        return

    if cmd == "transactions":
        limit = parse_limit(args, 20)

        async def _transactions(cdp):
            await ensure_moneyforward_ready(cdp)
            snapshot = await collect_snapshot(cdp)
            render_list(extract_transactions(snapshot, limit=limit))

        await cmd_with_client(_transactions)
        return

    if cmd == "ask" and args:
        question = " ".join(args)

        async def _ask(cdp):
            await ensure_moneyforward_ready(cdp)
            snapshot = await collect_snapshot(cdp)
            answer = await asyncio.to_thread(call_openai, question, snapshot)
            print(answer)

        await cmd_with_client(_ask)
        return

    if cmd == "eval" and args:
        expression = " ".join(args)
        await cmd_with_client(lambda cdp: _print_value(cdp.evaluate(expression)))
        return

    usage()
    sys.exit(1)


async def _print_value(awaitable):
    value = await awaitable
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value if value is not None else "")


if __name__ == "__main__":
    asyncio.run(main())
