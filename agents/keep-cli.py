#!/usr/bin/env python3
"""CLI tool to access Google Keep via gkeepapi."""

import getpass
import json
import os
import sys

import gkeepapi


CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")
DEFAULT_STATE_FILE = "~/.config/agent-tools/keep-state.json"


def load_full_config():
    """Load full config file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_full_config(data):
    """Persist full config file."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config():
    """Load Keep configuration from config file."""
    return load_full_config().get("keep", {})


def expand_path(path):
    return os.path.expanduser(path)


class KeepAPI:
    def __init__(self):
        self.full_config = load_full_config()
        self.config = self.full_config.get("keep", {})
        self.email = self.config.get("email") or os.environ.get("KEEP_EMAIL", "")
        self.master_token = self.config.get("master_token") or os.environ.get("KEEP_MASTER_TOKEN", "")
        self.device_id = self.config.get("device_id") or os.environ.get("KEEP_DEVICE_ID")
        self.state_file = expand_path(
            os.environ.get("KEEP_STATE_FILE", self.config.get("state_file", DEFAULT_STATE_FILE))
        )
        self.keep = gkeepapi.Keep()
        self.state = self._load_state_file()

    def _load_state_file(self):
        if not os.path.exists(self.state_file):
            return {}
        with open(self.state_file) as f:
            return json.load(f)

    def _save_state_file(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def save_credentials(self, email, master_token, device_id=None):
        keep_config = dict(self.full_config.get("keep", {}))
        keep_config["email"] = email
        keep_config["master_token"] = master_token
        if device_id:
            keep_config["device_id"] = device_id
        if "state_file" not in keep_config:
            keep_config["state_file"] = self.state_file
        self.full_config["keep"] = keep_config
        save_full_config(self.full_config)
        self.config = keep_config
        self.email = email
        self.master_token = master_token
        if device_id:
            self.device_id = device_id

    def login(self):
        if not self.email or not self.master_token:
            raise RuntimeError(
                "Keep credentials are not configured. "
                "Set keep.email and keep.master_token in ~/.config/agent-tools/config.json"
            )

        keep_state = self.state.get("keep_state")
        try:
            self.keep.authenticate(
                self.email,
                self.master_token,
                state=keep_state,
                sync=True,
                device_id=self.device_id,
            )
        except gkeepapi.exception.LoginException as exc:
            raise RuntimeError(
                "Keep authentication failed. "
                "The configured master_token may be invalid or expired."
            ) from exc
        self.state["keep_state"] = self.keep.dump()
        self._save_state_file()

    def sync(self):
        self.keep.sync()
        self.state["keep_state"] = self.keep.dump()
        self._save_state_file()

    def active_notes(self):
        notes = list(self.keep.all())
        notes.sort(
            key=lambda note: getattr(note.timestamps, "updated", None) or getattr(note.timestamps, "created", None),
            reverse=True,
        )
        return [note for note in notes if not note.trashed]

    def _preview(self, note):
        body = note.text.strip()
        if not body:
            return ""
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        return " | ".join(lines[:4])

    def _match_score(self, note, query):
        q = query.casefold()
        title = (note.title or "").casefold()
        text = (note.text or "").casefold()

        if title == q:
            return (0, len(title))
        if q in title:
            return (1, len(title))
        if q in text:
            return (2, len(text))
        return None

    def find_note(self, query, include_archived=True):
        candidates = []
        for note in self.active_notes():
            if note.archived and not include_archived:
                continue
            score = self._match_score(note, query)
            if score is not None:
                candidates.append((score, note))

        if not candidates:
            raise RuntimeError(f"Note not found: {query}")

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def remember_note(self, note):
        self.state["last_opened_id"] = note.id
        self.state["keep_state"] = self.keep.dump()
        self._save_state_file()

    def get_last_opened(self):
        note_id = self.state.get("last_opened_id")
        if not note_id:
            raise RuntimeError("No note selected. Run: keep-cli.py open <query>")
        note = self.keep.get(note_id)
        if note is None or note.trashed:
            raise RuntimeError("Previously selected note is no longer available.")
        return note

    def refresh_master_token(self, email, password):
        keep = gkeepapi.Keep()
        try:
            keep.login(email, password, sync=True, device_id=self.device_id)
        except gkeepapi.exception.LoginException as exc:
            raise RuntimeError(
                "Keep login failed while refreshing master_token. "
                "Check email/password and Google account security settings."
            ) from exc

        master_token = keep.getMasterToken()
        self.keep = keep
        self.email = email
        self.master_token = master_token
        self.state["keep_state"] = keep.dump()
        self._save_state_file()
        self.save_credentials(email, master_token, self.device_id)
        return master_token


def format_timestamp(value):
    if value is None:
        return ""
    text = getattr(value, "isoformat", lambda: str(value))()
    return text.replace("+00:00", "Z")


def print_note(note):
    title = note.title.strip() if note.title else "(untitled)"
    print(f"=== {title} ===")
    if note.archived:
        print("[archived]")
    if note.text.strip():
        print(note.text.strip())


def cmd_list(api, limit=20, include_archived=False):
    notes = [
        note for note in api.active_notes()
        if include_archived or not note.archived
    ][:limit]

    print("=== Notes ===")
    for i, note in enumerate(notes, 1):
        title = note.title.strip() if note.title else "(untitled)"
        flags = []
        if note.archived:
            flags.append("archived")
        meta = f" [{' '.join(flags)}]" if flags else ""
        preview = api._preview(note)
        suffix = f" :: {preview}" if preview else ""
        print(f"  {i}. {title}{meta}{suffix}")


def cmd_search(api, query, limit=20, include_archived=True):
    hits = []
    q = query.casefold()
    for note in api.active_notes():
        if not include_archived and note.archived:
            continue
        title = (note.title or "").casefold()
        text = (note.text or "").casefold()
        if q in title or q in text:
            hits.append(note)

    print(f"=== Search results for '{query}' ({len(hits)} found) ===")
    for i, note in enumerate(hits[:limit], 1):
        title = note.title.strip() if note.title else "(untitled)"
        preview = api._preview(note)
        suffix = f" :: {preview}" if preview else ""
        print(f"  {i}. {title}{suffix}")


def cmd_open(api, query):
    note = api.find_note(query)
    api.remember_note(note)
    print_note(note)


def cmd_read(api, query=None):
    note = api.find_note(query) if query else api.get_last_opened()
    api.remember_note(note)
    print_note(note)


def cmd_create(api, title, body=""):
    note = api.keep.createNote(title, body)
    api.sync()
    api.remember_note(note)
    print(f"Created: {note.title or '(untitled)'}")


def cmd_archive(api, query):
    note = api.find_note(query, include_archived=False)
    note.archived = True
    api.sync()
    print(f"Archived: {note.title or '(untitled)'}")


def cmd_dump(api, query=None):
    note = api.find_note(query) if query else api.get_last_opened()
    payload = {
        "id": note.id,
        "title": note.title,
        "text": note.text,
        "archived": note.archived,
        "trashed": note.trashed,
        "created": format_timestamp(getattr(note.timestamps, "created", None)),
        "updated": format_timestamp(getattr(note.timestamps, "updated", None)),
        "labels": [label.name for label in getattr(note, "labels", [])],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_auth(api, email=None, password=None):
    resolved_email = email or api.email
    if not resolved_email:
        raise RuntimeError("Email is required. Pass it as: keep-cli.py auth <email>")

    resolved_password = password or os.environ.get("KEEP_PASSWORD")
    if not resolved_password:
        resolved_password = getpass.getpass("Google password: ")

    api.refresh_master_token(resolved_email, resolved_password)
    print(f"Saved new Keep master_token for: {resolved_email}")


def usage():
    print("""Usage: keep-cli.py <command> [args]

Commands:
  auth <email>                      Refresh and save master_token
  list [--limit N] [--include-archived]
                                    List notes
  search <query> [--limit N] [--include-archived]
                                    Search notes by title/body
  open <query>                      Open a note by exact/partial match
  read [query]                      Read a note or the last opened note
  create <title> [body]             Create a text note
  archive <query>                   Archive a note by exact/partial match
  dump [query]                      Dump note metadata as JSON

Config: ~/.config/agent-tools/config.json
Environment:
  KEEP_EMAIL            Override configured email
  KEEP_PASSWORD         Password used by `auth`
  KEEP_MASTER_TOKEN     Override configured master token
  KEEP_DEVICE_ID        Override Android device id used by gkeepapi
  KEEP_STATE_FILE       Override cached state file path""")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]

    try:
        api = KeepAPI()

        if cmd == "auth":
            if len(sys.argv) >= 3:
                cmd_auth(api, sys.argv[2])
            else:
                cmd_auth(api)
            return

        api.login()

        if cmd == "list":
            limit = 20
            include_archived = False
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                    limit = int(sys.argv[i + 1])
                    i += 2
                elif sys.argv[i] == "--include-archived":
                    include_archived = True
                    i += 1
                else:
                    i += 1
            cmd_list(api, limit, include_archived)
        elif cmd == "search":
            if len(sys.argv) < 3:
                usage()
            limit = 20
            include_archived = False
            query_parts = []
            i = 3
            query_parts.append(sys.argv[2])
            while i < len(sys.argv):
                if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                    limit = int(sys.argv[i + 1])
                    i += 2
                elif sys.argv[i] == "--include-archived":
                    include_archived = True
                    i += 1
                else:
                    query_parts.append(sys.argv[i])
                    i += 1
            cmd_search(api, " ".join(query_parts), limit, include_archived)
        elif cmd == "open":
            if len(sys.argv) < 3:
                usage()
            cmd_open(api, " ".join(sys.argv[2:]))
        elif cmd == "read":
            query = " ".join(sys.argv[2:]) if len(sys.argv) >= 3 else None
            cmd_read(api, query)
        elif cmd == "create":
            if len(sys.argv) < 3:
                usage()
            title = sys.argv[2]
            body = sys.argv[3] if len(sys.argv) >= 4 else ""
            cmd_create(api, title, body)
        elif cmd == "archive":
            if len(sys.argv) < 3:
                usage()
            cmd_archive(api, " ".join(sys.argv[2:]))
        elif cmd == "dump":
            query = " ".join(sys.argv[2:]) if len(sys.argv) >= 3 else None
            cmd_dump(api, query)
        else:
            print(f"Unknown command: {cmd}")
            usage()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
