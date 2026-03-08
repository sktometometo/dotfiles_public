#!/usr/bin/env python3
"""CLI tool to access Google Keep via gkeepapi."""

import json
import os
import sys

CONFIG_FILE = os.path.expanduser("~/.config/agent-tools/config.json")
STATE_FILE = os.path.expanduser("~/.config/agent-tools/keep-state.json")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f).get("keep", {})


def get_keep():
    import gkeepapi

    config = load_config()
    email = config.get("email", "")
    master_token = config.get("master_token", "")
    if not email or not master_token:
        raise RuntimeError(
            "keep.email and keep.master_token required in ~/.config/agent-tools/config.json"
        )

    keep = gkeepapi.Keep()

    state = None
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)

    keep.authenticate(email, master_token, state=state)

    return keep


def save_state(keep):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(keep.dump(), f)


def cmd_list(keep, args):
    """List notes."""
    pinned_only = "--pinned" in args
    include_archived = "--archived" in args
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    notes = keep.find(
        pinned=True if pinned_only else None,
        archived=True if include_archived else False,
        trashed=False,
    )

    print("=== Notes ===")
    for i, note in enumerate(notes):
        if i >= limit:
            break
        kind = "list" if hasattr(note, "items") and callable(getattr(note, "items", None)) is False else "note"
        try:
            items = note.items if hasattr(note, "items") else None
            if items:
                kind = "list"
        except Exception:
            pass
        pinned = " [pinned]" if note.pinned else ""
        print(f"  {i+1}. {note.title or '(untitled)'}{pinned}  ({note.id})")


def cmd_read(keep, note_id):
    """Read a note by ID."""
    note = keep.get(note_id)
    if not note:
        raise RuntimeError(f"Note not found: {note_id}")

    print(f"=== {note.title or '(untitled)'} ===")
    print(f"ID: {note.id}")
    print(f"Pinned: {note.pinned}")

    # Check if it's a list
    try:
        items = list(note.items)
        if items:
            print()
            for item in items:
                check = "[x]" if item.checked else "[ ]"
                print(f"  {check} {item.text}")
            return
    except (AttributeError, TypeError):
        pass

    if note.text:
        print()
        print(note.text)


def cmd_search(keep, query, args):
    """Search notes by text."""
    limit = 20
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    notes = keep.find(query=query, archived=False, trashed=False)

    print(f"=== Search: '{query}' ===")
    count = 0
    for note in notes:
        if count >= limit:
            break
        pinned = " [pinned]" if note.pinned else ""
        preview = (note.text or "")[:60].replace("\n", " ")
        print(f"  {count+1}. {note.title or '(untitled)'}{pinned}  ({note.id})")
        if preview:
            print(f"     {preview}")
        count += 1
    if count == 0:
        print("  (no results)")


def cmd_create(keep, title, body=""):
    """Create a new note."""
    note = keep.createNote(title, body)
    keep.sync()
    save_state(keep)
    print(f"Created: {note.title}  ({note.id})")


def cmd_create_list(keep, title, items_str):
    """Create a checklist. Items separated by comma."""
    items = [(item.strip(), False) for item in items_str.split(",") if item.strip()]
    note = keep.createList(title, items)
    keep.sync()
    save_state(keep)
    print(f"Created list: {note.title}  ({note.id})")


def usage():
    print("""Usage: keep-cli.py <command> [args]

Commands:
  list [--pinned] [--archived] [--limit N]   List notes
  read <note_id>                              Read a note
  search <query> [--limit N]                  Search notes
  create <title> [body]                       Create a text note
  create-list <title> "item1, item2, ..."     Create a checklist

Config: ~/.config/agent-tools/config.json (keep.email, keep.master_token)""")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]
    keep = get_keep()

    try:
        if cmd == "list":
            cmd_list(keep, sys.argv[2:])
        elif cmd == "read":
            if len(sys.argv) < 3:
                usage()
            cmd_read(keep, sys.argv[2])
        elif cmd == "search":
            if len(sys.argv) < 3:
                usage()
            cmd_search(keep, sys.argv[2], sys.argv[3:])
        elif cmd == "create":
            if len(sys.argv) < 3:
                usage()
            title = sys.argv[2]
            body = sys.argv[3] if len(sys.argv) > 3 else ""
            cmd_create(keep, title, body)
        elif cmd == "create-list":
            if len(sys.argv) < 4:
                usage()
            cmd_create_list(keep, sys.argv[2], sys.argv[3])
        else:
            print(f"Unknown command: {cmd}")
            usage()
    finally:
        save_state(keep)


if __name__ == "__main__":
    main()
