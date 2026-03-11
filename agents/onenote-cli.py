#!/usr/bin/env python3
"""CLI tool to access OneNote via Microsoft Graph API."""

import json
import os
import sys
import time
import html
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")
SCOPES = "Notes.Read Notes.ReadWrite Notes.Create User.Read offline_access"
GRAPH_BASE = "https://graph.microsoft.com/v1.0/me/onenote"
LOGIN_BASE = "https://login.microsoftonline.com/consumers/oauth2/v2.0"


def load_config():
    """Load configuration from config file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("onenote", {})


_config = load_config()
CLIENT_ID = _config.get("client_id", "")
TOKEN_FILE = os.path.expanduser(
    os.environ.get("ONENOTE_TOKEN_FILE", _config.get("token_file", "~/onenotemcp/.access-token.txt"))
)
KNOWN_NOTEBOOKS = _config.get("notebooks", {})
KNOWN_SECTIONS = _config.get("sections", {})


class HTMLToText(HTMLParser):
    """Simple HTML to plain text converter."""

    def __init__(self):
        super().__init__()
        self.lines = []
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table"):
            self._flush()
        elif tag == "td":
            self.current.append("\t")

    def handle_data(self, data):
        self.current.append(data)

    def _flush(self):
        text = "".join(self.current).strip()
        if text:
            self.lines.append(text)
        self.current = []

    def get_text(self):
        self._flush()
        return "\n".join(self.lines)


def html_to_text(html):
    parser = HTMLToText()
    parser.feed(html)
    return parser.get_text()


def encode_id(oid):
    """URL-encode '!' in OneNote IDs."""
    return oid.replace("!", "%21")


def text_to_html(text):
    """Convert plain text to HTML paragraphs."""
    paragraphs = []
    for line in text.split("\n"):
        escaped = html.escape(line) if line.strip() else ""
        paragraphs.append(f"<p>{escaped}</p>" if escaped else "<p><br/></p>")
    return "\n".join(paragraphs)


def read_content(text_arg, is_html=False):
    """Read content from argument or stdin. Convert to HTML if needed."""
    if text_arg == "-":
        raw = sys.stdin.read()
    else:
        raw = text_arg
    if is_html:
        return raw
    return text_to_html(raw)


class OneNoteAPI:
    def __init__(self):
        self.token_data = None

    def _load_token(self):
        if self.token_data:
            return self.token_data["token"]
        with open(TOKEN_FILE) as f:
            self.token_data = json.load(f)
        return self.token_data["token"]

    def _save_token(self, data):
        self.token_data = data
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _refresh_token(self):
        rt = self.token_data.get("refresh_token", "")
        if not rt:
            raise RuntimeError("No refresh token. Run: onenote-cli.py auth")
        params = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "scope": SCOPES,
        }).encode()
        req = urllib.request.Request(f"{LOGIN_BASE}/token", data=params)
        resp = json.loads(urllib.request.urlopen(req).read())
        if "access_token" not in resp:
            raise RuntimeError(f"Token refresh failed: {resp}")
        new_data = {
            "token": resp["access_token"],
            "clientId": CLIENT_ID,
            "scopes": SCOPES.split(),
            "refresh_token": resp.get("refresh_token", rt),
        }
        self._save_token(new_data)
        return new_data["token"]

    def _api_get(self, path, params=None, accept="application/json"):
        token = self._load_token()
        url = f"{GRAPH_BASE}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(2):
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", accept)
            try:
                resp = urllib.request.urlopen(req)
                if accept == "application/json":
                    return json.loads(resp.read())
                return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = self._refresh_token()
                    continue
                body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {e.code}: {body}")

    def _api_post(self, path, body, content_type="application/json", accept="application/json"):
        token = self._load_token()
        url = f"{GRAPH_BASE}/{path}"
        for attempt in range(2):
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", content_type)
            req.add_header("Accept", accept)
            try:
                resp = urllib.request.urlopen(req)
                if accept == "application/json":
                    return json.loads(resp.read())
                return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = self._refresh_token()
                    continue
                body_text = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {e.code}: {body_text}")

    def _api_patch(self, path, body, content_type="application/json", accept="application/json"):
        token = self._load_token()
        url = f"{GRAPH_BASE}/{path}"
        for attempt in range(2):
            req = urllib.request.Request(url, data=body, method="PATCH")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", content_type)
            req.add_header("Accept", accept)
            try:
                resp = urllib.request.urlopen(req)
                if accept == "application/json":
                    payload = resp.read()
                    return json.loads(payload) if payload else None
                return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = self._refresh_token()
                    continue
                body_text = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {e.code}: {body_text}")

    def list_notebooks(self):
        data = self._api_get("notebooks", {"$select": "id,displayName"})
        return data.get("value", [])

    def list_sections(self, notebook_id):
        nid = encode_id(notebook_id)
        data = self._api_get(f"notebooks/{nid}/sections", {"$select": "id,displayName"})
        return data.get("value", [])

    def list_pages(self, section_id, top=20):
        sid = encode_id(section_id)
        data = self._api_get(f"sections/{sid}/pages", {
            "$select": "id,title,createdDateTime,lastModifiedDateTime",
            "$orderby": "createdDateTime desc",
            "$top": str(top),
        })
        return data.get("value", [])

    def get_page_content(self, page_id):
        pid = encode_id(page_id)
        html = self._api_get(f"pages/{pid}/content", accept="text/html")
        return html_to_text(html)

    def create_page(self, section_id, title, body_html, created_iso):
        sid = encode_id(section_id)
        doc = f"""<!DOCTYPE html>
<html>
  <head>
    <title>{html.escape(title)}</title>
    <meta name="created" content="{html.escape(created_iso)}" />
  </head>
  <body>
{body_html}
  </body>
</html>
"""
        return self._api_post(
            f"sections/{sid}/pages",
            doc.encode("utf-8"),
            content_type="application/xhtml+xml",
        )

    def _api_delete(self, path):
        token = self._load_token()
        url = f"{GRAPH_BASE}/{path}"
        for attempt in range(2):
            req = urllib.request.Request(url, method="DELETE")
            req.add_header("Authorization", f"Bearer {token}")
            try:
                resp = urllib.request.urlopen(req)
                return
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = self._refresh_token()
                    continue
                if e.code == 204:
                    return
                body_text = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {e.code}: {body_text}")

    def get_page_html(self, page_id):
        """Get raw HTML content of a page."""
        pid = encode_id(page_id)
        return self._api_get(f"pages/{pid}/content", accept="text/html")

    def patch_page(self, page_id, commands):
        """Send PATCH commands to a page.

        commands: list of dicts with keys: target, action, content, [position]
        Actions: append, replace, insert, prepend
        Targets: body, #<data-id>
        Position (for insert only): before, after
        """
        pid = encode_id(page_id)
        self._api_patch(
            f"pages/{pid}/content",
            json.dumps(commands).encode("utf-8"),
            content_type="application/json",
        )

    def append_to_page_body(self, page_id, body_html):
        self.patch_page(page_id, [
            {"target": "body", "action": "append", "content": body_html}
        ])

    def replace_element(self, page_id, target, content_html):
        self.patch_page(page_id, [
            {"target": target, "action": "replace", "content": content_html}
        ])

    def insert_element(self, page_id, target, content_html, position="after"):
        self.patch_page(page_id, [
            {"target": target, "action": "insert", "position": position,
             "content": content_html}
        ])

    def delete_page(self, page_id):
        pid = encode_id(page_id)
        self._api_delete(f"pages/{pid}")

    def resolve_notebook(self, name):
        """Resolve notebook name/alias to ID."""
        low = name.lower()
        if low in KNOWN_NOTEBOOKS:
            return KNOWN_NOTEBOOKS[low]
        # Might be a raw ID
        if "-" in name and "!" in name:
            return name
        # Search by displayName
        for nb in self.list_notebooks():
            if low in nb.get("displayName", "").lower():
                return nb["id"]
        raise RuntimeError(f"Notebook not found: {name}")

    def resolve_section(self, name, notebook_id=None):
        """Resolve section name to ID."""
        if name in KNOWN_SECTIONS:
            return KNOWN_SECTIONS[name]
        if "-" in name and "!" in name:
            return name
        if notebook_id:
            for sec in self.list_sections(notebook_id):
                if name.lower() in sec.get("displayName", "").lower():
                    return sec["id"]
        else:
            # Search all notebooks
            for nb in self.list_notebooks():
                for sec in self.list_sections(nb["id"]):
                    if name.lower() in sec.get("displayName", "").lower():
                        return sec["id"]
        raise RuntimeError(f"Section not found: {name}")


def cmd_auth():
    """Interactive device code authentication flow."""
    if not CLIENT_ID:
        raise RuntimeError("client_id not configured. Set it in ~/.config/agent-tools/config.json")
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "scope": SCOPES,
    }).encode()
    req = urllib.request.Request(f"{LOGIN_BASE}/devicecode", data=params)
    resp = json.loads(urllib.request.urlopen(req).read())

    print(f"Open: {resp['verification_uri']}")
    print(f"Code: {resp['user_code']}")
    print("Waiting for authentication...")

    device_code = resp["device_code"]
    interval = resp.get("interval", 5)

    while True:
        time.sleep(interval)
        poll_params = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": CLIENT_ID,
            "device_code": device_code,
        }).encode()
        poll_req = urllib.request.Request(f"{LOGIN_BASE}/token", data=poll_params)
        try:
            poll_resp = json.loads(urllib.request.urlopen(poll_req).read())
        except urllib.error.HTTPError as e:
            err = json.loads(e.read())
            if err.get("error") == "authorization_pending":
                continue
            if err.get("error") == "slow_down":
                interval += 5
                continue
            raise RuntimeError(f"Auth failed: {err}")

        if "access_token" in poll_resp:
            token_data = {
                "token": poll_resp["access_token"],
                "clientId": CLIENT_ID,
                "scopes": SCOPES.split(),
                "refresh_token": poll_resp.get("refresh_token", ""),
            }
            api = OneNoteAPI()
            api._save_token(token_data)
            print("Authentication successful. Token saved.")
            return


def cmd_notebooks(api):
    notebooks = api.list_notebooks()
    print("=== Notebooks ===")
    for i, nb in enumerate(notebooks, 1):
        print(f"  {i}. {nb.get('displayName', '???')}  ({nb['id']})")


def cmd_sections(api, notebook_name):
    nid = api.resolve_notebook(notebook_name)
    sections = api.list_sections(nid)
    print(f"=== Sections ===")
    for i, sec in enumerate(sections, 1):
        print(f"  {i}. {sec.get('displayName', '???')}  ({sec['id']})")


def cmd_pages(api, section_name, notebook_name=None, top=20):
    nid = api.resolve_notebook(notebook_name) if notebook_name else None
    sid = api.resolve_section(section_name, nid)
    pages = api.list_pages(sid, top)
    print(f"=== Pages ===")
    for i, p in enumerate(pages, 1):
        modified = p.get("lastModifiedDateTime", "")[:16]
        print(f"  {i}. {p.get('title', '???')}  (modified: {modified})  ({p['id']})")


def cmd_read(api, page_id):
    text = api.get_page_content(page_id)
    print(text)


def cmd_search(api, query, notebook_name=None):
    """Search pages by title across notebooks."""
    if notebook_name:
        notebooks = [{"id": api.resolve_notebook(notebook_name)}]
    else:
        notebooks = api.list_notebooks()

    results = []
    for nb in notebooks:
        try:
            sections = api.list_sections(nb["id"])
        except RuntimeError:
            continue
        for sec in sections:
            try:
                pages = api.list_pages(sec["id"], top=50)
            except RuntimeError:
                continue
            for p in pages:
                title = p.get("title", "")
                if query.lower() in title.lower():
                    results.append({
                        "title": title,
                        "section": sec.get("displayName", ""),
                        "modified": p.get("lastModifiedDateTime", "")[:16],
                        "id": p["id"],
                    })

    print(f"=== Search results for '{query}' ({len(results)} found) ===")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['section']}] {r['title']}  (modified: {r['modified']})  ({r['id']})")


def cmd_create_page(api, section_name, title, notebook_name=None, body_file=None):
    nid = api.resolve_notebook(notebook_name) if notebook_name else None
    sid = api.resolve_section(section_name, nid)
    if body_file:
        with open(os.path.expanduser(body_file)) as f:
            body_html = f.read()
    else:
        body_html = "<p></p>"
    created_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    page = api.create_page(sid, title, body_html, created_iso)
    print(f"Created page: {page.get('title', title)}  ({page.get('id', '?')})")


def cmd_append_body(api, page_id, body_file):
    with open(os.path.expanduser(body_file)) as f:
        body_html = f.read()
    api.append_to_page_body(page_id, body_html)
    print(f"Updated page: {page_id}")


def cmd_read_html(api, page_id):
    raw = api.get_page_html(page_id)
    print(raw)


def cmd_append(api, page_id, text, is_html=False):
    content = read_content(text, is_html)
    api.append_to_page_body(page_id, content)
    print(f"Appended to page: {page_id}")


def cmd_replace(api, page_id, target, text, is_html=False):
    content = read_content(text, is_html)
    api.replace_element(page_id, target, content)
    print(f"Replaced {target} in page: {page_id}")


def cmd_insert(api, page_id, target, text, position="after", is_html=False):
    content = read_content(text, is_html)
    api.insert_element(page_id, target, content, position)
    print(f"Inserted {position} {target} in page: {page_id}")


def cmd_delete_page(api, page_id):
    api.delete_page(page_id)
    print(f"Deleted page: {page_id}")


def cmd_patch(api, page_id, commands_json):
    if commands_json == "-":
        commands_json = sys.stdin.read()
    commands = json.loads(commands_json)
    if isinstance(commands, dict):
        commands = [commands]
    api.patch_page(page_id, commands)
    print(f"Patched page: {page_id}")


def _parse_opts(argv, known_flags=None):
    """Parse --key value options from argv. Returns (opts_dict, positional_args).

    known_flags: dict of flag_name -> True for boolean flags (no value needed).
    """
    if known_flags is None:
        known_flags = {}
    opts = {}
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--") and "=" in arg:
            key, val = arg[2:].split("=", 1)
            opts[key] = val
            i += 1
        elif arg.startswith("--"):
            key = arg[2:]
            if key in known_flags and known_flags[key] is True:
                opts[key] = True
                i += 1
            elif i + 1 < len(argv):
                opts[key] = argv[i + 1]
                i += 2
            else:
                positional.append(arg)
                i += 1
        else:
            positional.append(arg)
            i += 1
    return opts, positional


def usage():
    print("""Usage: onenote-cli.py <command> [args]

Commands:
  auth                              Device code authentication
  notebooks                         List notebooks
  sections <notebook>               List sections (name or ID)
  pages <section> [--notebook NB]   List pages (name or ID)
  read <page_id>                    Read page content as text
  read-html <page_id>               Read page raw HTML (shows data-id attrs)
  search <query> [--notebook NB]    Search pages by title
  create-page <section> <title> [--notebook NB] [--body-file PATH]
                                    Create a page from HTML body content

  Editing commands:
  append <page_id> <text|->  [--html]
                                    Append text to page body (- for stdin)
  replace <page_id> <target> <text|-> [--html]
                                    Replace element content (target: #data-id)
  insert <page_id> <target> <text|-> [--position before|after] [--html]
                                    Insert before/after element (default: after)
  delete-page <page_id>             Delete a page
  patch <page_id> <json|->          Send raw PATCH commands as JSON

  Legacy:
  append-body <page_id> --body-file PATH
                                    Append HTML file to page body

Targets for replace/insert:
  body                              The page body element
  #<data-id>                        Element by data-id (use read-html to find)

Config: ~/.config/agent-tools/config.json
Environment:
  ONENOTE_TOKEN_FILE    Override token file path""")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]

    if cmd == "auth":
        cmd_auth()
        return

    api = OneNoteAPI()

    if cmd == "notebooks":
        cmd_notebooks(api)
    elif cmd == "sections":
        if len(sys.argv) < 3:
            usage()
        cmd_sections(api, sys.argv[2])
    elif cmd == "pages":
        if len(sys.argv) < 3:
            usage()
        opts, pos = _parse_opts(sys.argv[3:])
        cmd_pages(api, sys.argv[2], opts.get("notebook"), int(opts.get("top", 20)))
    elif cmd == "read":
        if len(sys.argv) < 3:
            usage()
        cmd_read(api, sys.argv[2])
    elif cmd == "read-html":
        if len(sys.argv) < 3:
            usage()
        cmd_read_html(api, sys.argv[2])
    elif cmd == "search":
        if len(sys.argv) < 3:
            usage()
        opts, pos = _parse_opts(sys.argv[3:])
        cmd_search(api, sys.argv[2], opts.get("notebook"))
    elif cmd == "create-page":
        if len(sys.argv) < 4:
            usage()
        opts, pos = _parse_opts(sys.argv[4:])
        cmd_create_page(api, sys.argv[2], sys.argv[3], opts.get("notebook"),
                        opts.get("body-file"))
    elif cmd == "append":
        if len(sys.argv) < 3:
            usage()
        opts, pos = _parse_opts(sys.argv[3:], {"html": True})
        text = pos[0] if pos else "-"
        cmd_append(api, sys.argv[2], text, is_html="html" in opts)
    elif cmd == "replace":
        if len(sys.argv) < 4:
            usage()
        opts, pos = _parse_opts(sys.argv[3:], {"html": True})
        target = pos[0] if pos else "body"
        text = pos[1] if len(pos) > 1 else "-"
        cmd_replace(api, sys.argv[2], target, text, is_html="html" in opts)
    elif cmd == "insert":
        if len(sys.argv) < 4:
            usage()
        opts, pos = _parse_opts(sys.argv[3:], {"html": True})
        target = pos[0] if pos else "body"
        text = pos[1] if len(pos) > 1 else "-"
        position = opts.get("position", "after")
        cmd_insert(api, sys.argv[2], target, text, position, is_html="html" in opts)
    elif cmd == "delete-page":
        if len(sys.argv) < 3:
            usage()
        cmd_delete_page(api, sys.argv[2])
    elif cmd == "patch":
        if len(sys.argv) < 3:
            usage()
        commands_json = sys.argv[3] if len(sys.argv) > 3 else "-"
        cmd_patch(api, sys.argv[2], commands_json)
    elif cmd == "append-body":
        if len(sys.argv) < 5 or sys.argv[3] != "--body-file":
            usage()
        cmd_append_body(api, sys.argv[2], sys.argv[4])
    else:
        print(f"Unknown command: {cmd}")
        usage()


if __name__ == "__main__":
    main()
