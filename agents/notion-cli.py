#!/usr/bin/env python3
"""CLI tool to access Notion via the official REST API."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")
DEFAULT_TOKEN_FILE = "~/.config/agent-tools/notion-token.txt"
DEFAULT_VERSION = "2025-09-03"
API_BASE = "https://api.notion.com/v1"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("notion", {})


CONFIG = load_config()
TOKEN_FILE = os.path.expanduser(
    os.environ.get("NOTION_TOKEN_FILE", CONFIG.get("token_file", DEFAULT_TOKEN_FILE))
)
NOTION_VERSION = os.environ.get("NOTION_VERSION", CONFIG.get("version", DEFAULT_VERSION))


def usage():
    print(
        """Usage:
  notion-cli.py auth [TOKEN]
  notion-cli.py whoami
  notion-cli.py list [--limit N] [--json]
  notion-cli.py search QUERY [--limit N] [--json]
  notion-cli.py read PAGE_ID [--json]
  notion-cli.py create --parent PAGE_ID --title TITLE [--body TEXT | --body-file FILE]
  notion-cli.py append PAGE_OR_BLOCK_ID --text TEXT [--start]
  notion-cli.py update-title PAGE_ID TITLE

Environment:
  NOTION_TOKEN       Use this token instead of the token file
  NOTION_TOKEN_FILE  Override token file path
  NOTION_VERSION     Override Notion-Version header
"""
    )


def read_token():
    env_token = os.environ.get("NOTION_TOKEN", "").strip()
    if env_token:
        return env_token
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "Notion token not found. Run `notion-cli.py auth <token>` or set NOTION_TOKEN."
        )
    with open(TOKEN_FILE) as f:
        token = f.read().strip()
    if not token:
        raise RuntimeError(f"Token file is empty: {TOKEN_FILE}")
    return token


def write_token(token):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(token.strip() + "\n")


class NotionAPI:
    def __init__(self):
        self.token = read_token()

    def _request(self, method, path, body=None, params=None):
        url = f"{API_BASE}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Notion-Version", NOTION_VERSION)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                err = json.loads(raw)
            except json.JSONDecodeError:
                err = raw
            raise RuntimeError(f"API error {e.code}: {err}")
        if not payload:
            return None
        return json.loads(payload)

    def get_me(self):
        return self._request("GET", "/users/me")

    def search_pages(self, query="", limit=20):
        body = {
            "page_size": limit,
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "filter": {"property": "object", "value": "page"},
        }
        if query:
            body["query"] = query
        return self._request("POST", "/search", body=body)

    def get_page(self, page_id):
        return self._request("GET", f"/pages/{page_id}")

    def get_block(self, block_id):
        return self._request("GET", f"/blocks/{block_id}")

    def list_block_children(self, block_id):
        blocks = []
        cursor = None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = self._request("GET", f"/blocks/{block_id}/children", params=params)
            blocks.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return blocks

    def create_page(self, parent_page_id, title, children=None):
        body = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
        }
        if children:
            body["children"] = children
        return self._request("POST", "/pages", body=body)

    def append_children(self, block_id, children, start=False):
        body = {"children": children}
        if start:
            body["position"] = {"type": "start"}
        return self._request("PATCH", f"/blocks/{block_id}/children", body=body)

    def update_page_title(self, page_id, title):
        body = {
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            }
        }
        return self._request("PATCH", f"/pages/{page_id}", body=body)


def get_arg_value(args, name, default=None):
    for i, arg in enumerate(args):
        if arg == name and i + 1 < len(args):
            return args[i + 1]
    return default


def require_arg_value(args, name):
    value = get_arg_value(args, name)
    if value is None:
        raise RuntimeError(f"Missing required option: {name}")
    return value


def parse_limit(args, default=20):
    value = get_arg_value(args, "--limit")
    return int(value) if value is not None else default


def rich_text_plain(rich_text):
    return "".join(item.get("plain_text", "") for item in rich_text or [])


def page_title(page):
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return rich_text_plain(prop.get("title", [])) or "(untitled)"
    return "(untitled)"


def text_to_blocks(text):
    lines = text.splitlines()
    blocks = []
    paragraph_lines = []

    def flush_paragraph():
        if not paragraph_lines:
            return
        content = "\n".join(paragraph_lines).strip()
        if content:
            blocks.append(make_paragraph_block(content))
        paragraph_lines.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            blocks.append(make_heading_block("heading_1", stripped[2:].strip()))
        elif stripped.startswith("## "):
            flush_paragraph()
            blocks.append(make_heading_block("heading_2", stripped[3:].strip()))
        elif stripped.startswith("### "):
            flush_paragraph()
            blocks.append(make_heading_block("heading_3", stripped[4:].strip()))
        elif stripped.startswith("- "):
            flush_paragraph()
            blocks.append(make_list_block("bulleted_list_item", stripped[2:].strip()))
        elif ". " in stripped and stripped.split(". ", 1)[0].isdigit():
            flush_paragraph()
            blocks.append(
                make_list_block("numbered_list_item", stripped.split(". ", 1)[1].strip())
            )
        else:
            paragraph_lines.append(line)
    flush_paragraph()
    return blocks


def split_rich_text(content, chunk_size=1800):
    chunks = []
    for start in range(0, len(content), chunk_size):
        chunks.append(
            {
                "type": "text",
                "text": {"content": content[start : start + chunk_size]},
            }
        )
    return chunks or [{"type": "text", "text": {"content": ""}}]


def make_paragraph_block(content):
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": split_rich_text(content)},
    }


def make_heading_block(kind, content):
    return {
        "object": "block",
        "type": kind,
        kind: {"rich_text": split_rich_text(content)},
    }


def make_list_block(kind, content):
    return {
        "object": "block",
        "type": kind,
        kind: {"rich_text": split_rich_text(content)},
    }


def block_summary(block):
    btype = block.get("type", "unknown")
    data = block.get(btype, {})
    if btype in {
        "paragraph",
        "heading_1",
        "heading_2",
        "heading_3",
        "quote",
        "bulleted_list_item",
        "numbered_list_item",
        "toggle",
        "callout",
    }:
        return rich_text_plain(data.get("rich_text", []))
    if btype == "to_do":
        text = rich_text_plain(data.get("rich_text", []))
        prefix = "[x] " if data.get("checked") else "[ ] "
        return prefix + text
    if btype == "code":
        return rich_text_plain(data.get("rich_text", []))
    if btype == "child_page":
        return data.get("title", "(child page)")
    if btype == "divider":
        return "---"
    return f"<{btype}>"


def render_blocks(api, block_id, indent=0):
    lines = []
    blocks = api.list_block_children(block_id)
    for block in blocks:
        btype = block.get("type", "unknown")
        prefix = "  " * indent
        marker = ""
        if btype == "bulleted_list_item":
            marker = "- "
        elif btype == "numbered_list_item":
            marker = "1. "
        elif btype == "to_do":
            checked = block.get("to_do", {}).get("checked")
            marker = "[x] " if checked else "[ ] "
        elif btype == "heading_1":
            marker = "# "
        elif btype == "heading_2":
            marker = "## "
        elif btype == "heading_3":
            marker = "### "
        elif btype == "quote":
            marker = "> "
        text = block_summary(block)
        if text:
            lines.append(prefix + marker + text)
        if block.get("has_children"):
            child_lines = render_blocks(api, block["id"], indent + 1)
            if child_lines:
                lines.extend(child_lines)
    return lines


def cmd_auth(args):
    token = args[0].strip() if args else os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Provide a token or set NOTION_TOKEN.")
    write_token(token)
    print(f"Saved token to {TOKEN_FILE}")


def cmd_whoami():
    api = NotionAPI()
    data = api.get_me()
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_list(args):
    api = NotionAPI()
    limit = parse_limit(args)
    data = api.search_pages("", limit=limit)
    if "--json" in args:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print("=== Notion Pages ===")
    for idx, page in enumerate(data.get("results", []), 1):
        title = page_title(page)
        print(
            f"  {idx}. {title}  ({page.get('id')})  [{page.get('last_edited_time', '')}]"
        )


def cmd_search(query, args):
    api = NotionAPI()
    limit = parse_limit(args)
    data = api.search_pages(query, limit=limit)
    if "--json" in args:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(f"=== Search: {query} ===")
    for idx, page in enumerate(data.get("results", []), 1):
        title = page_title(page)
        print(
            f"  {idx}. {title}  ({page.get('id')})  [{page.get('last_edited_time', '')}]"
        )


def cmd_read(page_id, args):
    api = NotionAPI()
    page = api.get_page(page_id)
    blocks = api.list_block_children(page_id)
    if "--json" in args:
        print(
            json.dumps(
                {"page": page, "blocks": blocks},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    print(f"=== {page_title(page)} ===")
    print(f"ID: {page_id}")
    print()
    lines = render_blocks(api, page_id)
    print("\n".join(lines))


def cmd_create(args):
    parent = require_arg_value(args, "--parent")
    title = require_arg_value(args, "--title")
    body_text = get_arg_value(args, "--body", "")
    body_file = get_arg_value(args, "--body-file")
    if body_file:
        with open(os.path.expanduser(body_file)) as f:
            body_text = f.read()
    children = text_to_blocks(body_text) if body_text else None
    api = NotionAPI()
    page = api.create_page(parent, title, children=children)
    print(f"Created: {page_title(page)}  ({page.get('id')})")


def cmd_append(target_id, args):
    text = require_arg_value(args, "--text")
    blocks = text_to_blocks(text)
    if not blocks:
        raise RuntimeError("No content to append.")
    api = NotionAPI()
    api.append_children(target_id, blocks, start="--start" in args)
    print(f"Appended {len(blocks)} block(s) to {target_id}")


def cmd_update_title(page_id, title):
    api = NotionAPI()
    page = api.update_page_title(page_id, title)
    print(f"Updated: {page_title(page)}  ({page.get('id')})")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help", "help"}:
        usage()
        return 0

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == "auth":
            cmd_auth(args)
        elif cmd == "whoami":
            cmd_whoami()
        elif cmd == "list":
            cmd_list(args)
        elif cmd == "search":
            if not args:
                raise RuntimeError("Usage: notion-cli.py search QUERY [--limit N] [--json]")
            cmd_search(args[0], args[1:])
        elif cmd == "read":
            if not args:
                raise RuntimeError("Usage: notion-cli.py read PAGE_ID [--json]")
            cmd_read(args[0], args[1:])
        elif cmd == "create":
            cmd_create(args)
        elif cmd == "append":
            if not args:
                raise RuntimeError("Usage: notion-cli.py append PAGE_OR_BLOCK_ID --text TEXT [--start]")
            cmd_append(args[0], args[1:])
        elif cmd == "update-title":
            if len(args) < 2:
                raise RuntimeError("Usage: notion-cli.py update-title PAGE_ID TITLE")
            cmd_update_title(args[0], args[1])
        else:
            raise RuntimeError(f"Unknown command: {cmd}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
