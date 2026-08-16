from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "agents" / "onenote-cli.py"
SPEC = importlib.util.spec_from_file_location("onenote_cli", MODULE_PATH)
onenote = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(onenote)


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def read(self):
        return json.dumps(self.value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class OneNoteTests(unittest.TestCase):
    def test_encode_id_quotes_complete_path_segment(self):
        self.assertEqual("abc%21def%2Fghi", onenote.encode_id("abc!def/ghi"))

    def test_token_is_saved_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token.json"
            with mock.patch.object(onenote, "TOKEN_FILE", str(path)):
                onenote.OneNoteAPI()._save_token({"token": "secret"})
            self.assertEqual(0o600, os.stat(path).st_mode & 0o777)

    def test_raw_html_requests_update_ids(self):
        api = onenote.OneNoteAPI()
        with mock.patch.object(api, "_api_get", return_value="<html/>") as request:
            api.get_page_html("page!id")
        request.assert_called_once_with(
            "pages/page%21id/content", {"includeIDs": "true"}, accept="text/html"
        )

    def test_ambiguous_notebook_is_rejected(self):
        api = onenote.OneNoteAPI()
        notebooks = [
            {"id": "1", "displayName": "Project Alpha"},
            {"id": "2", "displayName": "Project Beta"},
        ]
        with mock.patch.object(api, "list_notebooks", return_value=notebooks):
            with self.assertRaisesRegex(RuntimeError, "Ambiguous notebook"):
                api.resolve_notebook("Project")

    def test_collection_pagination_is_followed(self):
        api = onenote.OneNoteAPI()
        api.token_data = {"token": "test"}
        first = {"value": [{"id": "1"}], "@odata.nextLink": "https://next"}
        second = {"value": [{"id": "2"}]}
        with mock.patch.object(api, "_api_get", return_value=first), mock.patch.object(
            onenote.urllib.request, "urlopen", return_value=FakeResponse(second)
        ):
            self.assertEqual([{"id": "1"}, {"id": "2"}], api._api_get_all("pages"))

    def test_delete_requires_explicit_confirmation(self):
        api = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "requires --yes"):
            onenote.cmd_delete_page(api, "page")
        api.delete_page.assert_not_called()


if __name__ == "__main__":
    unittest.main()
