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
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.labels",
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


def get_sheets_service():
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build("sheets", "v4", credentials=creds)


def get_slides_service():
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build("slides", "v1", credentials=creds)


def get_gmail_service():
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


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


MIME_TYPES = {
    "docs": "application/vnd.google-apps.document",
    "sheets": "application/vnd.google-apps.spreadsheet",
    "slides": "application/vnd.google-apps.presentation",
}


def _list_drive_files(mime_type, limit, args):
    drive = get_drive_service()
    results = (
        drive.files()
        .list(
            q=f"mimeType='{mime_type}'",
            pageSize=limit,
            orderBy="modifiedTime desc",
            fields="files(id, name, modifiedTime)",
        )
        .execute()
    )
    return results.get("files", [])


def cmd_list(args):
    """List recent Google Docs."""
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    files = _list_drive_files(MIME_TYPES["docs"], limit, args)

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
    """Search Google Docs/Sheets/Slides by name.

    --type docs|sheets|slides|all  (default: all)
    """
    limit = 20
    file_type = "all"
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        elif a == "--type" and i + 1 < len(args):
            file_type = args[i + 1]

    safe_query = query.replace("'", "\\'")
    if file_type == "all":
        mime_filter = (
            f"(mimeType='{MIME_TYPES['docs']}' or "
            f"mimeType='{MIME_TYPES['sheets']}' or "
            f"mimeType='{MIME_TYPES['slides']}')"
        )
    else:
        if file_type not in MIME_TYPES:
            print(f"Unknown type: {file_type}. Choose from: docs, sheets, slides, all", file=sys.stderr)
            sys.exit(1)
        mime_filter = f"mimeType='{MIME_TYPES[file_type]}'"

    drive = get_drive_service()
    q = f"{mime_filter} and name contains '{safe_query}'"
    results = (
        drive.files()
        .list(
            q=q,
            pageSize=limit,
            orderBy="modifiedTime desc",
            fields="files(id, name, mimeType, modifiedTime)",
        )
        .execute()
    )
    files = results.get("files", [])

    if "--json" in args:
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return

    type_label = {"application/vnd.google-apps.document": "Doc",
                  "application/vnd.google-apps.spreadsheet": "Sheet",
                  "application/vnd.google-apps.presentation": "Slide"}
    print(f"=== Search: '{query}' ===")
    for i, f in enumerate(files):
        label = type_label.get(f.get("mimeType", ""), "?")
        print(f"  {i+1}. [{label}] {f['name']}  ({f['id']})  [{f.get('modifiedTime', '')}]")
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


# ---- Spreadsheets -------------------------------------------------------


def cmd_sheets_list(args):
    """List recent Google Spreadsheets."""
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    files = _list_drive_files(MIME_TYPES["sheets"], limit, args)

    if "--json" in args:
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return

    print("=== Google Spreadsheets ===")
    for i, f in enumerate(files):
        print(f"  {i+1}. {f['name']}  ({f['id']})  [{f.get('modifiedTime', '')}]")
    if not files:
        print("  (no spreadsheets found)")


def cmd_sheets_info(spreadsheet_id, args):
    """Show spreadsheet metadata and sheet names."""
    sheets = get_sheets_service()
    spreadsheet = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

    if "--json" in args:
        print(json.dumps(spreadsheet, ensure_ascii=False, indent=2))
        return

    title = spreadsheet.get("properties", {}).get("title", "(untitled)")
    print(f"=== {title} ({spreadsheet_id}) ===")
    for s in spreadsheet.get("sheets", []):
        props = s["properties"]
        grid = props.get("gridProperties", {})
        print(
            f"  {props['title']}  "
            f"({grid.get('rowCount', '?')} rows x {grid.get('columnCount', '?')} cols)"
        )


def cmd_sheets_read(spreadsheet_id, args):
    """Read cell values from a spreadsheet.

    --sheet <name>   Sheet tab name (default: first sheet)
    --range <A1>     A1 notation range (default: entire sheet)
    """
    range_notation = None
    sheet_name = None
    for i, a in enumerate(args):
        if a == "--range" and i + 1 < len(args):
            range_notation = args[i + 1]
        elif a == "--sheet" and i + 1 < len(args):
            sheet_name = args[i + 1]

    sheets = get_sheets_service()
    spreadsheet = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    title = spreadsheet.get("properties", {}).get("title", "(untitled)")
    sheet_names = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

    if "--json" in args:
        print(json.dumps(spreadsheet, ensure_ascii=False, indent=2))
        return

    if range_notation is None:
        target_sheet = sheet_name or (sheet_names[0] if sheet_names else "Sheet1")
        range_notation = target_sheet

    result = (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_notation)
        .execute()
    )
    values = result.get("values", [])

    print(f"=== {title} — {range_notation} ===")
    print(f"Sheets: {', '.join(sheet_names)}")
    print()
    for row in values:
        print("\t".join(str(c) for c in row))
    if not values:
        print("  (empty)")


# ---- Presentations (Slides) ---------------------------------------------


def _extract_slides_text(presentation):
    """Extract plain text from all slides."""
    parts = []
    for i, slide in enumerate(presentation.get("slides", [])):
        parts.append(f"--- Slide {i + 1} ---")
        for element in slide.get("pageElements", []):
            text_content = element.get("shape", {}).get("text", {})
            for te in text_content.get("textElements", []):
                content = te.get("textRun", {}).get("content", "")
                if content.strip():
                    parts.append(content.rstrip("\n"))
        parts.append("")
    return "\n".join(parts)


def cmd_slides_list(args):
    """List recent Google Presentations."""
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    files = _list_drive_files(MIME_TYPES["slides"], limit, args)

    if "--json" in args:
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return

    print("=== Google Slides ===")
    for i, f in enumerate(files):
        print(f"  {i+1}. {f['name']}  ({f['id']})  [{f.get('modifiedTime', '')}]")
    if not files:
        print("  (no presentations found)")


def cmd_slides_read(presentation_id, args):
    """Read text content from a presentation."""
    slides_svc = get_slides_service()
    presentation = (
        slides_svc.presentations().get(presentationId=presentation_id).execute()
    )

    if "--json" in args:
        print(json.dumps(presentation, ensure_ascii=False, indent=2))
        return

    title = presentation.get("title", "(untitled)")
    num_slides = len(presentation.get("slides", []))
    text = _extract_slides_text(presentation)
    print(f"=== {title} ===")
    print(f"ID: {presentation_id}  |  Slides: {num_slides}")
    print()
    print(text)


# ---- Gmail Filters & Labels ---------------------------------------------


def cmd_gmail_labels_list(args):
    """List all Gmail labels."""
    gmail = get_gmail_service()
    result = gmail.users().labels().list(userId="me").execute()
    labels = result.get("labels", [])

    if "--json" in args:
        print(json.dumps(labels, ensure_ascii=False, indent=2))
        return

    print("=== Gmail Labels ===")
    for label in sorted(labels, key=lambda x: x.get("name", "")):
        print(f"  {label['id']:40s}  {label['name']}")


def cmd_gmail_filters_list(args):
    """List all Gmail filters."""
    gmail = get_gmail_service()
    result = gmail.users().settings().filters().list(userId="me").execute()
    filters = result.get("filter", [])

    if "--json" in args:
        print(json.dumps(filters, ensure_ascii=False, indent=2))
        return

    # Build label id -> name map for display
    labels_result = gmail.users().labels().list(userId="me").execute()
    label_map = {lb["id"]: lb["name"] for lb in labels_result.get("labels", [])}

    print("=== Gmail Filters ===")
    for f in filters:
        fid = f.get("id", "?")
        criteria = f.get("criteria", {})
        action = f.get("action", {})
        add_labels = [label_map.get(lid, lid) for lid in action.get("addLabelIds", [])]
        remove_labels = [label_map.get(lid, lid) for lid in action.get("removeLabelIds", [])]
        print(f"  [{fid}]")
        for k, v in criteria.items():
            print(f"    criteria.{k}: {v}")
        if add_labels:
            print(f"    action.add: {', '.join(add_labels)}")
        if remove_labels:
            print(f"    action.remove: {', '.join(remove_labels)}")
        print()


def cmd_gmail_filter_create(args):
    """Create a Gmail filter.

    --from <addr>       Match sender address
    --to <addr>         Match recipient address
    --subject <text>    Match subject text
    --query <str>       Raw Gmail query string
    --label <name>      Apply this label (by name; creates if not exists)
    --archive           Remove from INBOX (skip inbox)
    --mark-read         Mark as read
    """
    from_addr = None
    to_addr = None
    subject = None
    query = None
    label_name = None
    archive = False
    mark_read = False

    i = 0
    while i < len(args):
        if args[i] == "--from" and i + 1 < len(args):
            from_addr = args[i + 1]; i += 2
        elif args[i] == "--to" and i + 1 < len(args):
            to_addr = args[i + 1]; i += 2
        elif args[i] == "--subject" and i + 1 < len(args):
            subject = args[i + 1]; i += 2
        elif args[i] == "--query" and i + 1 < len(args):
            query = args[i + 1]; i += 2
        elif args[i] == "--label" and i + 1 < len(args):
            label_name = args[i + 1]; i += 2
        elif args[i] == "--archive":
            archive = True; i += 1
        elif args[i] == "--mark-read":
            mark_read = True; i += 1
        else:
            i += 1

    criteria = {}
    if from_addr:
        criteria["from"] = from_addr
    if to_addr:
        criteria["to"] = to_addr
    if subject:
        criteria["subject"] = subject
    if query:
        criteria["query"] = query

    if not criteria:
        print("Error: at least one criteria option (--from, --to, --subject, --query) is required.", file=sys.stderr)
        sys.exit(1)

    gmail = get_gmail_service()

    add_label_ids = []
    remove_label_ids = []

    if label_name:
        # Find or create label
        labels_result = gmail.users().labels().list(userId="me").execute()
        label_map = {lb["name"]: lb["id"] for lb in labels_result.get("labels", [])}
        if label_name in label_map:
            add_label_ids.append(label_map[label_name])
        else:
            new_label = (
                gmail.users()
                .labels()
                .create(userId="me", body={"name": label_name})
                .execute()
            )
            add_label_ids.append(new_label["id"])
            print(f"Created label: {label_name} ({new_label['id']})")

    if archive:
        remove_label_ids.append("INBOX")
    if mark_read:
        remove_label_ids.append("UNREAD")

    filter_body = {"criteria": criteria, "action": {}}
    if add_label_ids:
        filter_body["action"]["addLabelIds"] = add_label_ids
    if remove_label_ids:
        filter_body["action"]["removeLabelIds"] = remove_label_ids

    result = (
        gmail.users()
        .settings()
        .filters()
        .create(userId="me", body=filter_body)
        .execute()
    )
    print(f"Filter created: {result.get('id')}")
    print(f"  criteria: {criteria}")
    print(f"  add labels: {add_label_ids}")
    print(f"  remove labels: {remove_label_ids}")


def cmd_gmail_filter_delete(filter_id):
    """Delete a Gmail filter by ID."""
    gmail = get_gmail_service()
    gmail.users().settings().filters().delete(userId="me", id=filter_id).execute()
    print(f"Filter deleted: {filter_id}")


# -------------------------------------------------------------------------


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

=== Google Docs ===
  auth                                        Authenticate (browser OAuth flow)
  list [--limit N] [--json]                   List recent documents
  read <doc_id> [--json]                      Read document content
  search <query> [--type docs|sheets|slides|all] [--limit N] [--json]
                                              Search by name (default: all types)
  create <title> [body]                       Create a new document
  append <doc_id> <text>                      Append text to a document

=== Google Spreadsheets ===
  sheets-list [--limit N] [--json]            List recent spreadsheets
  sheets-info <spreadsheet_id> [--json]       Show sheet names and dimensions
  sheets-read <spreadsheet_id> [--sheet <name>] [--range <A1>] [--json]
                                              Read cell values (tab-separated)

=== Google Slides ===
  slides-list [--limit N] [--json]            List recent presentations
  slides-read <presentation_id> [--json]      Extract text from all slides

=== Gmail Filters ===
  gmail-labels                                List all Gmail labels (with IDs)
  gmail-filters                               List all Gmail filters
  gmail-filter-create --from <addr> [--to <addr>] [--subject <text>] [--query <str>]
                      [--label <name>] [--archive] [--mark-read]
                                              Create a Gmail filter
  gmail-filter-delete <filter_id>             Delete a Gmail filter

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
    # Spreadsheets
    elif cmd == "sheets-list":
        cmd_sheets_list(sys.argv[2:])
    elif cmd == "sheets-info":
        if len(sys.argv) < 3:
            usage()
        cmd_sheets_info(sys.argv[2], sys.argv[3:])
    elif cmd == "sheets-read":
        if len(sys.argv) < 3:
            usage()
        cmd_sheets_read(sys.argv[2], sys.argv[3:])
    # Slides
    elif cmd == "slides-list":
        cmd_slides_list(sys.argv[2:])
    elif cmd == "slides-read":
        if len(sys.argv) < 3:
            usage()
        cmd_slides_read(sys.argv[2], sys.argv[3:])
    # Gmail
    elif cmd == "gmail-labels":
        cmd_gmail_labels_list(sys.argv[2:])
    elif cmd == "gmail-filters":
        cmd_gmail_filters_list(sys.argv[2:])
    elif cmd == "gmail-filter-create":
        cmd_gmail_filter_create(sys.argv[2:])
    elif cmd == "gmail-filter-delete":
        if len(sys.argv) < 3:
            usage()
        cmd_gmail_filter_delete(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        usage()


if __name__ == "__main__":
    main()
