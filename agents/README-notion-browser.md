Notion browser automation

This path is for guest access where the official Notion API cannot be used.

Start the dedicated browser session:

  python3 ~/notion-start.sh

Then connect by VNC and log in to Notion once:

  vncviewer localhost:5904

After login, use the CLI:

  python3 ~/notion-browser-cli.py status
  python3 ~/notion-browser-cli.py pages --limit 20
  python3 ~/notion-browser-cli.py open-page 日記
  python3 ~/notion-browser-cli.py read
  python3 ~/notion-browser-cli.py append "CLI から追記"

Notes

- This is DOM automation, not the official API.
- Notion UI changes can break selectors.
- Keep the dedicated Chrome profile alive to preserve login state.
