#!/usr/bin/env python3
"""CLI tool to access OneNote via Microsoft Graph API."""

import json
import os
import stat
import sys
import time
import html
import base64
import hashlib
import secrets
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from html.parser import HTMLParser

CONFIG_FILE = os.path.expanduser(
    os.environ.get("ONENOTE_CONFIG_FILE", "~/.config/agent-tools/config.json")
)
GRAPH_BASE = "https://graph.microsoft.com/v1.0/me/onenote"
HTTP_TIMEOUT = 30


def load_config():
    """Load configuration from config file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("onenote", {})


_config = load_config()
CLIENT_ID = _config.get("client_id", "")
TENANT = os.environ.get("ONENOTE_TENANT", _config.get("tenant", "consumers"))
LOGIN_BASE = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0"
SCOPES = " ".join(_config.get("scopes", ["Notes.ReadWrite", "offline_access"]))
TOKEN_FILE = os.path.expanduser(
    os.environ.get(
        "ONENOTE_TOKEN_FILE",
        _config.get("token_file", "~/.config/agent-tools/onenote-token.json"),
    )
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
    """URL-encode a OneNote ID as one path segment."""
    return urllib.parse.quote(oid, safe="")


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
        try:
            with open(TOKEN_FILE, encoding="utf-8") as f:
                self.token_data = json.load(f)
            token = self.token_data.get("token") or self.token_data.get("access_token")
            if not token:
                raise RuntimeError("token file does not contain an access token")
            self.token_data["token"] = token
            return token
        except FileNotFoundError as exc:
            raise RuntimeError(f"Token not found: {TOKEN_FILE}. Run: onenote-cli.py auth") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid token JSON: {TOKEN_FILE}") from exc

    def _save_token(self, data):
        self.token_data = data
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(TOKEN_FILE, 0o600)

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
        resp = json.loads(urllib.request.urlopen(req, timeout=HTTP_TIMEOUT).read())
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
            req.add_header("User-Agent", "dotfiles-public-onenote-cli/1.0")
            try:
                resp = urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
                if accept == "application/json":
                    return json.loads(resp.read())
                return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = self._refresh_token()
                    continue
                body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {e.code}: {body}")
            except urllib.error.URLError as e:
                raise RuntimeError(f"Network error: {e.reason}") from e

    def _api_post(self, path, body, content_type="application/json", accept="application/json"):
        token = self._load_token()
        url = f"{GRAPH_BASE}/{path}"
        for attempt in range(2):
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", content_type)
            req.add_header("Accept", accept)
            req.add_header("User-Agent", "dotfiles-public-onenote-cli/1.0")
            try:
                resp = urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
                if accept == "application/json":
                    return json.loads(resp.read())
                return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = self._refresh_token()
                    continue
                body_text = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {e.code}: {body_text}")
            except urllib.error.URLError as e:
                raise RuntimeError(f"Network error: {e.reason}") from e

    def _api_patch(self, path, body, content_type="application/json", accept="application/json"):
        token = self._load_token()
        url = f"{GRAPH_BASE}/{path}"
        for attempt in range(2):
            req = urllib.request.Request(url, data=body, method="PATCH")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", content_type)
            req.add_header("Accept", accept)
            req.add_header("User-Agent", "dotfiles-public-onenote-cli/1.0")
            try:
                resp = urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
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
            except urllib.error.URLError as e:
                raise RuntimeError(f"Network error: {e.reason}") from e

    def _api_get_all(self, path, params=None, limit=None):
        """Return all collection rows while following Graph pagination."""
        data = self._api_get(path, params)
        values = list(data.get("value", []))
        next_link = data.get("@odata.nextLink")
        while next_link and (limit is None or len(values) < limit):
            token = self._load_token()
            for attempt in range(2):
                req = urllib.request.Request(next_link)
                req.add_header("Authorization", f"Bearer {token}")
                req.add_header("Accept", "application/json")
                req.add_header("User-Agent", "dotfiles-public-onenote-cli/1.0")
                try:
                    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                        data = json.loads(resp.read())
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code == 401 and attempt == 0:
                        token = self._refresh_token()
                        continue
                    body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"API error {exc.code}: {body}") from exc
                except urllib.error.URLError as exc:
                    raise RuntimeError(f"Network error: {exc.reason}") from exc
            values.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
        return values[:limit] if limit is not None else values

    def list_notebooks(self):
        return self._api_get_all("notebooks", {"$select": "id,displayName"})

    def list_sections(self, notebook_id):
        nid = encode_id(notebook_id)
        return self._api_get_all(
            f"notebooks/{nid}/sections", {"$select": "id,displayName"}
        )

    def list_pages(self, section_id, top=20):
        sid = encode_id(section_id)
        return self._api_get_all(f"sections/{sid}/pages", {
            "$select": "id,title,createdDateTime,lastModifiedDateTime",
            "$orderby": "createdDateTime desc",
            "$top": str(top),
        }, limit=top)

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
            req.add_header("User-Agent", "dotfiles-public-onenote-cli/1.0")
            try:
                resp = urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
                return
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = self._refresh_token()
                    continue
                if e.code == 204:
                    return
                body_text = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API error {e.code}: {body_text}")
            except urllib.error.URLError as e:
                raise RuntimeError(f"Network error: {e.reason}") from e

    def get_page_html(self, page_id):
        """Get raw HTML content of a page."""
        pid = encode_id(page_id)
        return self._api_get(
            f"pages/{pid}/content", {"includeIDs": "true"}, accept="text/html"
        )

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
        notebooks = self.list_notebooks()
        exact = [nb for nb in notebooks if low == nb.get("displayName", "").lower()]
        if len(exact) == 1:
            return exact[0]["id"]
        partial = [nb for nb in notebooks if low in nb.get("displayName", "").lower()]
        if len(partial) == 1:
            return partial[0]["id"]
        if len(partial) > 1:
            names = ", ".join(nb.get("displayName", "?") for nb in partial)
            raise RuntimeError(f"Ambiguous notebook '{name}': {names}")
        raise RuntimeError(f"Notebook not found: {name}")

    def resolve_section(self, name, notebook_id=None):
        """Resolve section name to ID."""
        if name in KNOWN_SECTIONS:
            return KNOWN_SECTIONS[name]
        if "-" in name and "!" in name:
            return name
        if notebook_id:
            sections = self.list_sections(notebook_id)
        else:
            sections = []
            for nb in self.list_notebooks():
                sections.extend(self.list_sections(nb["id"]))
        low = name.lower()
        exact = [sec for sec in sections if low == sec.get("displayName", "").lower()]
        if len(exact) == 1:
            return exact[0]["id"]
        partial = [sec for sec in sections if low in sec.get("displayName", "").lower()]
        if len(partial) == 1:
            return partial[0]["id"]
        if len(partial) > 1:
            names = ", ".join(sec.get("displayName", "?") for sec in partial)
            raise RuntimeError(f"Ambiguous section '{name}': {names}")
        raise RuntimeError(f"Section not found: {name}")


def _save_auth_response(response):
    if "access_token" not in response:
        raise RuntimeError(f"Authentication did not return an access token: {response}")
    token_data = {
        "token": response["access_token"],
        "clientId": CLIENT_ID,
        "scopes": response.get("scope", SCOPES).split(),
        "refresh_token": response.get("refresh_token", ""),
        "expires_in": response.get("expires_in"),
    }
    OneNoteAPI()._save_token(token_data)


def cmd_auth():
    """Authorization code flow with PKCE for personal or organizational accounts."""
    if not CLIENT_ID:
        raise RuntimeError("client_id not configured. Set it in ~/.config/agent-tools/config.json")
    result = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result["code"] = query.get("code", [None])[0]
            result["error"] = query.get("error_description", query.get("error", [None]))[0]
            message = "OneNote CLI authentication received. You can close this tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode("utf-8"))

        def log_message(self, *_):
            return

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    server.timeout = 300
    redirect_uri = f"http://localhost:{server.server_port}"
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    auth_url = f"{LOGIN_BASE}/authorize?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    print(f"Open this URL in a browser on this computer:\n{auth_url}")
    webbrowser.open(auth_url)
    print("Waiting up to 5 minutes for the browser callback...")
    server.handle_request()
    server.server_close()
    if result.get("error"):
        raise RuntimeError(f"Authentication failed: {result['error']}")
    if not result.get("code"):
        raise RuntimeError("Authentication timed out or returned no authorization code")

    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": result["code"],
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "code_verifier": verifier,
    }).encode()
    request = urllib.request.Request(f"{LOGIN_BASE}/token", data=params)
    try:
        response = json.loads(
            urllib.request.urlopen(request, timeout=HTTP_TIMEOUT).read()
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Token exchange failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Token exchange network error: {exc.reason}") from exc
    _save_auth_response(response)
    print("Authentication successful. Token saved.")


def cmd_auth_device():
    """Device code authentication flow for supported organizational tenants."""
    if not CLIENT_ID:
        raise RuntimeError("client_id not configured. Set it in ~/.config/agent-tools/config.json")
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "scope": SCOPES,
    }).encode()
    req = urllib.request.Request(f"{LOGIN_BASE}/devicecode", data=params)
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=HTTP_TIMEOUT).read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Auth failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Auth network error: {exc.reason}") from exc

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
            poll_resp = json.loads(
                urllib.request.urlopen(poll_req, timeout=HTTP_TIMEOUT).read()
            )
        except urllib.error.HTTPError as e:
            err = json.loads(e.read())
            if err.get("error") == "authorization_pending":
                continue
            if err.get("error") == "slow_down":
                interval += 5
                continue
            raise RuntimeError(f"Auth failed: {err}")

        if "access_token" in poll_resp:
            _save_auth_response(poll_resp)
            print("Authentication successful. Token saved.")
            return


def cmd_doctor():
    """Validate local configuration without calling Microsoft Graph."""
    checks = []
    config_ok = os.path.isfile(CONFIG_FILE)
    checks.append((config_ok, "config", CONFIG_FILE if config_ok else f"not found: {CONFIG_FILE}"))
    client_ok = bool(CLIENT_ID and CLIENT_ID != "YOUR_CLIENT_ID")
    checks.append((client_ok, "client_id", "configured" if client_ok else "not configured"))
    token_ok = os.path.isfile(TOKEN_FILE)
    checks.append((token_ok, "token", TOKEN_FILE if token_ok else f"not found: {TOKEN_FILE}"))
    if token_ok:
        try:
            with open(TOKEN_FILE, encoding="utf-8") as handle:
                token_data = json.load(handle)
            access_ok = bool(token_data.get("token") or token_data.get("access_token"))
            refresh_ok = bool(token_data.get("refresh_token"))
            checks.append((access_ok, "access token", "present" if access_ok else "missing"))
            checks.append((refresh_ok, "refresh token", "present" if refresh_ok else "missing"))
            mode = stat.S_IMODE(os.stat(TOKEN_FILE).st_mode)
            checks.append((not mode & 0o077, "token permissions", f"{mode:04o}"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append((False, "token JSON", str(exc)))
    checks.append((True, "tenant", TENANT))
    checks.append((True, "scopes", SCOPES))
    for ok, name, detail in checks:
        print(f"{'OK' if ok else 'NG'} {name}: {detail}")
    if not all(ok for ok, _, _ in checks):
        raise RuntimeError("OneNote setup is incomplete")


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


def cmd_delete_page(api, page_id, confirmed=False):
    if not confirmed:
        raise RuntimeError("delete-page requires --yes")
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
  doctor                            Validate config/token without API access
  auth                              Browser authentication with localhost + PKCE
  auth-device                       Device code flow (organizational tenants only)
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
  delete-page <page_id> --yes       Delete a page (explicit confirmation)
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


def _main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]

    if cmd == "doctor":
        cmd_doctor()
        return

    if cmd == "auth":
        cmd_auth()
        return

    if cmd == "auth-device":
        cmd_auth_device()
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
        opts, pos = _parse_opts(sys.argv[3:], {"yes": True})
        cmd_delete_page(api, sys.argv[2], confirmed="yes" in opts)
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


def main():
    try:
        _main()
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
