import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from review_harness.openalex import OpenAlexClient, load_openalex_api_key


class OpenAlexCredentialTests(unittest.TestCase):
    def test_reads_single_line_key_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "OPENALEX_API_KEY.txt"
            path.write_text("test-key-from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_openalex_api_key(path), "test-key-from-file")

    def test_environment_takes_precedence_over_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "OPENALEX_API_KEY.txt"
            path.write_text("file-key\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENALEX_API_KEY": " environment-key "}, clear=True):
                self.assertEqual(load_openalex_api_key(path), "environment-key")

    def test_rejects_multiple_nonempty_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "OPENALEX_API_KEY.txt"
            path.write_text("first\nsecond\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "exactly one non-empty line"):
                    load_openalex_api_key(path)

    def test_sends_key_in_authorization_header_not_url(self) -> None:
        payload = io.BytesIO(json.dumps({"meta": {"next_cursor": None}, "results": []}).encode("utf-8"))
        client = OpenAlexClient(api_key="secret-test-key")
        with patch("review_harness.openalex.urlopen", return_value=payload) as mocked_urlopen:
            pages = list(client.search_works(query="test", max_pages=1, per_page=1))
        self.assertEqual(len(pages), 1)
        request = mocked_urlopen.call_args.args[0]
        self.assertNotIn("secret-test-key", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-test-key")


if __name__ == "__main__":
    unittest.main()
