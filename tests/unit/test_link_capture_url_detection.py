from __future__ import annotations

import unittest

from services.link_capture.models import SourcePlatform
from services.link_capture.url_detection import (
    InvalidSourceUrlError,
    detect_platform,
    detect_urls,
    extract_urls,
)


class UrlExtractionTest(unittest.TestCase):
    def test_preserves_exact_shared_url(self) -> None:
        source_url = "https://x.com/User/status/123?utm_source=telegram#reply"

        self.assertEqual(extract_urls(f"Save this {source_url}"), (source_url,))

    def test_extracts_multiple_urls_in_order(self) -> None:
        message = (
            "First https://youtu.be/abc123, then "
            "https://example.com/article?q=one%20two."
        )

        self.assertEqual(
            extract_urls(message),
            (
                "https://youtu.be/abc123",
                "https://example.com/article?q=one%20two",
            ),
        )

    def test_removes_only_unmatched_prose_delimiter(self) -> None:
        message = "Read (https://example.com/a_(useful)_page)."

        self.assertEqual(
            extract_urls(message),
            ("https://example.com/a_(useful)_page",),
        )

    def test_empty_message_has_no_urls(self) -> None:
        self.assertEqual(extract_urls(None), ())
        self.assertEqual(extract_urls("No link here"), ())


class PlatformDetectionTest(unittest.TestCase):
    def test_detects_supported_platforms(self) -> None:
        cases = {
            "https://www.instagram.com/reel/ABC/": SourcePlatform.INSTAGRAM,
            "https://threads.net/@author/post/ABC": SourcePlatform.THREADS,
            "https://www.threads.com/@author/post/ABC": SourcePlatform.THREADS,
            "https://x.com/author/status/1": SourcePlatform.X,
            "https://mobile.twitter.com/author/status/1": SourcePlatform.X,
            "https://t.co/short": SourcePlatform.X,
            "https://t.me/channel/123": SourcePlatform.TELEGRAM,
            "https://telegram.me/channel/123": SourcePlatform.TELEGRAM,
            "https://www.youtube.com/watch?v=abc": SourcePlatform.YOUTUBE,
            "https://youtu.be/abc": SourcePlatform.YOUTUBE,
            "https://news.example.org/story": SourcePlatform.WEB,
        }

        for source_url, expected in cases.items():
            with self.subTest(source_url=source_url):
                self.assertEqual(detect_platform(source_url), expected)

    def test_does_not_trust_deceptive_suffixes(self) -> None:
        self.assertEqual(
            detect_platform("https://instagram.com.evil.example/post/1"),
            SourcePlatform.WEB,
        )

    def test_detection_does_not_rewrite_source_url(self) -> None:
        source_url = "https://WWW.YouTube.com/watch?v=abc&utm_source=Telegram#chapter"

        detected = detect_urls(f"watch {source_url}")[0]

        self.assertEqual(detected.source_url, source_url)
        self.assertEqual(detected.platform, SourcePlatform.YOUTUBE)

    def test_invalid_source_url_is_rejected(self) -> None:
        with self.assertRaises(InvalidSourceUrlError):
            detect_platform("not-a-url")


if __name__ == "__main__":
    unittest.main()
