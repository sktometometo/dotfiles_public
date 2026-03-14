Notion CLI setup

1. Create an internal integration in Notion:
   https://www.notion.so/profile/integrations

2. Give the integration these capabilities:
   - Read content
   - Insert content
   - Update content

3. Copy the internal integration token.

4. Share the target top-level page with the integration in the Notion UI.
   If a page is not shared with the integration, the API cannot read or edit it.

5. Save the token:
   notion-cli.py auth ntn_xxxxx

6. Test access:
   notion-cli.py whoami
   notion-cli.py list --limit 10

Examples

- Search pages:
  notion-cli.py search 日記 --limit 10

- Read a page:
  notion-cli.py read 01234567-89ab-cdef-0123-456789abcdef

- Create a child page:
  notion-cli.py create --parent PARENT_PAGE_ID --title "2026/03 日記" --body "# 2026-03-14\n本文"

- Append text to a page:
  notion-cli.py append PAGE_ID --text "- 追記1\n- 追記2"
