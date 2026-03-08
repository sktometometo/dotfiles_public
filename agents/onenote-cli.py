#!/usr/bin/env python3
"""CLI tool to access OneNote via Microsoft Graph API."""

import json
import os
import sys
import time
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


def usage():
    print("""Usage: onenote-cli.py <command> [args]

Commands:
  auth                              Device code authentication
  notebooks                         List notebooks
  sections <notebook>               List sections (name or ID)
  pages <section> [--notebook NB]   List pages (name or ID)
  read <page_id>                    Read page content as text
  search <query> [--notebook NB]    Search pages by title

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
        nb = None
        top = 20
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--notebook" and i + 1 < len(sys.argv):
                nb = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--top" and i + 1 < len(sys.argv):
                top = int(sys.argv[i + 1])
                i += 2
            else:
                i += 1
        cmd_pages(api, sys.argv[2], nb, top)
    elif cmd == "read":
        if len(sys.argv) < 3:
            usage()
        cmd_read(api, sys.argv[2])
    elif cmd == "search":
        if len(sys.argv) < 3:
            usage()
        nb = None
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--notebook" and i + 1 < len(sys.argv):
                nb = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        cmd_search(api, sys.argv[2], nb)
    else:
        print(f"Unknown command: {cmd}")
        usage()


if __name__ == "__main__":
    main()
