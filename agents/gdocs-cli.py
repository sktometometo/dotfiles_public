#!/usr/bin/env python3
"""CLI tool to access Google Docs via Google APIs."""

import json
import os
import sys

CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")
TOKEN_FILE = os.path.expanduser("~/.config/agent-tools/gdocs-token.json")

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.readonly",
]


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("gdocs", {})


AUTH_PORT = 8085


def get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    config = load_config()
    client_id = config.get("client_id", "")
    client_secret = config.get("client_secret", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "gdocs.client_id and gdocs.client_secret required in "
            "~/.config/agent-tools/config.json"
        )

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            print(f"Listening on http://localhost:{AUTH_PORT}/ for OAuth callback.")
            print(
                f"If on a remote server, run:  ssh -L {AUTH_PORT}:localhost:{AUTH_PORT} <host>"
            )
            print()
            creds = flow.run_local_server(
                port=AUTH_PORT, open_browser=False, timeout_seconds=120
            )

        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def get_docs_service():
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build("docs", "v1", credentials=creds)


def get_drive_service():
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build("drive", "v3", credentials=creds)


def extract_text(doc):
    """Extract plain text from a Google Docs document."""
    body = doc.get("body", {})
    content = body.get("content", [])
    parts = []
    for element in content:
        if "paragraph" in element:
            for pe in element["paragraph"].get("elements", []):
                text_run = pe.get("textRun")
                if text_run:
                    parts.append(text_run.get("content", ""))
        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                cells = []
                for cell in row.get("tableCells", []):
                    cell_text = []
                    for cell_content in cell.get("content", []):
                        if "paragraph" in cell_content:
                            for pe in cell_content["paragraph"].get("elements", []):
                                text_run = pe.get("textRun")
                                if text_run:
                                    cell_text.append(text_run.get("content", "").strip())
                    cells.append(" ".join(cell_text))
                parts.append("\t".join(cells) + "\n")
    return "".join(parts)


def cmd_auth():
    """Authenticate and store token."""
    get_credentials()
    print("Authentication successful. Token saved.")


def cmd_list(args):
    """List recent Google Docs."""
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    drive = get_drive_service()
    results = (
        drive.files()
        .list(
            q="mimeType='application/vnd.google-apps.document'",
            pageSize=limit,
            orderBy="modifiedTime desc",
            fields="files(id, name, modifiedTime)",
        )
        .execute()
    )
    files = results.get("files", [])

    if "--json" in args:
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return

    print("=== Google Docs ===")
    for i, f in enumerate(files):
        print(f"  {i+1}. {f['name']}  ({f['id']})  [{f.get('modifiedTime', '')}]")
    if not files:
        print("  (no documents found)")


def cmd_read(doc_id, args):
    """Read a document by ID."""
    docs = get_docs_service()
    doc = docs.documents().get(documentId=doc_id).execute()

    if "--json" in args:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return

    title = doc.get("title", "(untitled)")
    text = extract_text(doc)
    print(f"=== {title} ===")
    print(f"ID: {doc_id}")
    print()
    print(text)


def cmd_search(query, args):
    """Search Google Docs by name."""
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    drive = get_drive_service()
    q = (
        f"mimeType='application/vnd.google-apps.document' and "
        f"name contains '{query.replace(chr(39), chr(92) + chr(39))}'"
    )
    results = (
        drive.files()
        .list(
            q=q,
            pageSize=limit,
            orderBy="modifiedTime desc",
            fields="files(id, name, modifiedTime)",
        )
        .execute()
    )
    files = results.get("files", [])

    if "--json" in args:
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return

    print(f"=== Search: '{query}' ===")
    for i, f in enumerate(files):
        print(f"  {i+1}. {f['name']}  ({f['id']})  [{f.get('modifiedTime', '')}]")
    if not files:
        print("  (no results)")


def cmd_create(title, body_text=""):
    """Create a new Google Doc."""
    docs = get_docs_service()
    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    if body_text:
        requests = [
            {"insertText": {"location": {"index": 1}, "text": body_text}}
        ]
        docs.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()

    print(f"Created: {title}  ({doc_id})")


def cmd_append(doc_id, text):
    """Append text to a document."""
    docs = get_docs_service()
    doc = docs.documents().get(documentId=doc_id).execute()

    # Find the end index of the body
    body = doc.get("body", {})
    content = body.get("content", [])
    end_index = 1
    if content:
        end_index = content[-1].get("endIndex", 1) - 1

    requests = [{"insertText": {"location": {"index": end_index}, "text": text}}]
    docs.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests}
    ).execute()

    print(f"Appended text to document {doc_id}")


def usage():
    print("""Usage: gdocs-cli.py <command> [args]

Commands:
  auth                                   Authenticate (browser OAuth flow)
  list [--limit N] [--json]              List recent documents
  read <doc_id> [--json]                 Read document content
  search <query> [--limit N] [--json]    Search documents by name
  create <title> [body]                  Create a new document
  append <doc_id> <text>                 Append text to a document

Config: ~/.config/agent-tools/config.json (gdocs.client_id, gdocs.client_secret)""")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]

    if cmd == "auth":
        cmd_auth()
    elif cmd == "list":
        cmd_list(sys.argv[2:])
    elif cmd == "read":
        if len(sys.argv) < 3:
            usage()
        cmd_read(sys.argv[2], sys.argv[3:])
    elif cmd == "search":
        if len(sys.argv) < 3:
            usage()
        cmd_search(sys.argv[2], sys.argv[3:])
    elif cmd == "create":
        if len(sys.argv) < 3:
            usage()
        title = sys.argv[2]
        body = sys.argv[3] if len(sys.argv) > 3 else ""
        cmd_create(title, body)
    elif cmd == "append":
        if len(sys.argv) < 4:
            usage()
        cmd_append(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")
        usage()


if __name__ == "__main__":
    main()
