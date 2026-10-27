import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from gutenberg_downloader import (
    BOOK_URL,
    download_id_range,
    parse_id_range,
)


class GutenbergDownloaderTests(unittest.TestCase):
    def test_parses_valid_single_id_and_range(self):
        self.assertEqual(parse_id_range("16328", "16328"), (16328, 16328))
        self.assertEqual(parse_id_range("10", "12"), (10, 12))

    def test_rejects_reversed_or_oversized_ranges(self):
        with self.assertRaisesRegex(ValueError, "ending ID"):
            parse_id_range("20", "10")
        with self.assertRaisesRegex(ValueError, "Limit each run"):
            parse_id_range("1", "1001")

    @patch("gutenberg_downloader.urllib.request.urlopen")
    def test_downloads_text_using_expected_url_and_skips_existing(
        self, mock_urlopen
    ):
        response = io.BytesIO(b"Sample Gutenberg text.")
        mock_urlopen.return_value.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "pg16329.txt").write_text("Keep existing file", encoding="utf-8")

            summary = download_id_range(
                16328, 16329, folder, request_delay=0
            )

            self.assertEqual(
                (folder / "pg16328.txt").read_text(encoding="utf-8"),
                "Sample Gutenberg text.",
            )
            self.assertEqual(
                (folder / "pg16329.txt").read_text(encoding="utf-8"),
                "Keep existing file",
            )

        self.assertEqual(summary.downloaded, 1)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.missing, 0)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, BOOK_URL.format(book_id=16328))

    @patch("gutenberg_downloader.urllib.request.urlopen")
    def test_404_is_counted_as_missing(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            BOOK_URL.format(book_id=5), 404, "Not Found", {}, None
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = download_id_range(5, 5, Path(temp_dir), request_delay=0)
        self.assertEqual(summary.missing, 1)
        self.assertEqual(summary.errors, ())

    @patch("gutenberg_downloader.urllib.request.urlopen")
    def test_rejects_html_response_instead_of_saving_it(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = io.BytesIO(
            b"<html>not a text download</html>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            summary = download_id_range(7, 7, folder, request_delay=0)
            self.assertFalse((folder / "pg7.txt").exists())
        self.assertEqual(len(summary.errors), 1)
        self.assertIn("web page", summary.errors[0])


if __name__ == "__main__":
    unittest.main()
