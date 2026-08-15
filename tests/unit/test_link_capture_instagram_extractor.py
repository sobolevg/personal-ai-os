from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError

from services.link_capture.extraction.base import (
    ExtractionError,
    ExtractionRequest,
    UnsupportedPlatformError,
)
from services.link_capture.extraction.http import (
    TextHttpResponse,
    UrllibTextTransport,
)
from services.link_capture.extraction.providers.instagram import (
    InstagramOpenGraphExtractor,
)
from services.link_capture.extraction.registry import ExtractorRegistry
from services.link_capture.models import NormalizedContent, SourcePlatform


SOURCE_URL = (
    "https://www.instagram.com/example/reel/ABC123/"
    "?utm_source=telegram#shared"
)
SAVED_AT = "2026-08-16T09:00:00Z"
PUBLIC_HTML = """
<!doctype html>
<html>
  <head>
    <title>Fallback page title</title>
    <link rel="canonical" href="https://www.instagram.com/example/reel/ABC123/">
    <meta property="og:title" content="Example Creator on Instagram">
    <meta property="og:description" content="A public caption &amp; details">
    <meta property="og:image" content="/media/public-thumbnail.jpg">
    <meta property="og:type" content="video.other">
    <meta property="article:published_time" content="2026-08-15T10:20:30Z">
  </head>
</html>
"""


class StubTextTransport:
    def __init__(self, response: TextHttpResponse | None = None) -> None:
        self.response = response
        self.requested_urls: list[str] = []

    async def get_text(self, url: str) -> TextHttpResponse:
        self.requested_urls.append(url)
        if self.response is None:
            raise URLError("public page unavailable")
        return self.response


class InstagramOpenGraphExtractorTest(unittest.IsolatedAsyncioTestCase):
    async def test_maps_public_metadata_without_rewriting_source(self) -> None:
        transport = StubTextTransport(
            TextHttpResponse(
                final_url=SOURCE_URL,
                body=PUBLIC_HTML,
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        )
        extractor = InstagramOpenGraphExtractor(transport=transport)
        original = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.INSTAGRAM,
            saved_at=SAVED_AT,
        )

        outcome = await ExtractorRegistry([extractor]).enrich(original)

        self.assertTrue(outcome.extracted)
        self.assertEqual(outcome.provider, "instagram_open_graph")
        self.assertEqual(transport.requested_urls, [SOURCE_URL])
        self.assertEqual(outcome.content.source_url, SOURCE_URL)
        self.assertEqual(outcome.content.saved_at, SAVED_AT)
        self.assertEqual(
            outcome.content.canonical_url,
            "https://www.instagram.com/example/reel/ABC123/",
        )
        self.assertEqual(outcome.content.author, "Example Creator")
        self.assertEqual(
            outcome.content.author_url,
            "https://www.instagram.com/example/",
        )
        self.assertEqual(outcome.content.title, "Example Creator on Instagram")
        self.assertEqual(outcome.content.text, "A public caption & details")
        self.assertEqual(outcome.content.media_type, "video")
        self.assertEqual(
            outcome.content.thumbnail_url,
            "https://www.instagram.com/media/public-thumbnail.jpg",
        )
        self.assertEqual(outcome.content.published_at, "2026-08-15T10:20:30Z")
        self.assertIsNone(outcome.content.media_url)

    async def test_private_or_unavailable_page_preserves_minimal_capture(self) -> None:
        transport = StubTextTransport()
        original = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.INSTAGRAM,
            saved_at=SAVED_AT,
        )

        outcome = await ExtractorRegistry(
            [InstagramOpenGraphExtractor(transport=transport)]
        ).enrich(original)

        self.assertFalse(outcome.extracted)
        self.assertEqual(outcome.content, original)
        self.assertEqual(outcome.content.source_url, SOURCE_URL)
        self.assertIn("public page unavailable", outcome.error or "")

    async def test_derives_author_profile_from_standard_public_description(self) -> None:
        source_url = "https://www.instagram.com/reel/ABC123/?igsh=shared"
        html = """
        <meta property="og:title" content="Display Name on Instagram">
        <meta property="og:description"
              content="4,886 likes, 139 comments - yurlov.move on August 14, 2026: caption">
        """
        transport = StubTextTransport(
            TextHttpResponse(
                final_url=source_url,
                body=html,
                headers={},
            )
        )
        original = NormalizedContent.captured(
            source_url=source_url,
            platform=SourcePlatform.INSTAGRAM,
            saved_at=SAVED_AT,
        )

        outcome = await ExtractorRegistry(
            [InstagramOpenGraphExtractor(transport=transport)]
        ).enrich(original)

        self.assertTrue(outcome.extracted)
        self.assertEqual(outcome.content.author, "Display Name")
        self.assertEqual(
            outcome.content.author_url,
            "https://www.instagram.com/yurlov.move/",
        )
        self.assertEqual(outcome.content.source_url, source_url)

    async def test_login_redirect_is_not_treated_as_post_metadata(self) -> None:
        transport = StubTextTransport(
            TextHttpResponse(
                final_url="https://www.instagram.com/accounts/login/",
                body='<meta property="og:title" content="Instagram login">',
                headers={},
            )
        )
        original = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.INSTAGRAM,
            saved_at=SAVED_AT,
        )

        outcome = await ExtractorRegistry(
            [InstagramOpenGraphExtractor(transport=transport)]
        ).enrich(original)

        self.assertFalse(outcome.extracted)
        self.assertEqual(outcome.content, original)
        self.assertIn("login or challenge", outcome.error or "")

    async def test_page_without_public_metadata_uses_fallback(self) -> None:
        transport = StubTextTransport(
            TextHttpResponse(
                final_url=SOURCE_URL,
                body="<html><body>JavaScript required</body></html>",
                headers={},
            )
        )
        original = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.INSTAGRAM,
            saved_at=SAVED_AT,
        )

        outcome = await ExtractorRegistry(
            [InstagramOpenGraphExtractor(transport=transport)]
        ).enrich(original)

        self.assertFalse(outcome.extracted)
        self.assertEqual(outcome.content.source_url, SOURCE_URL)
        self.assertIn("no public post metadata", outcome.error or "")

    async def test_provider_rejects_other_platforms(self) -> None:
        extractor = InstagramOpenGraphExtractor(transport=StubTextTransport())

        with self.assertRaises(UnsupportedPlatformError):
            await extractor.extract(
                ExtractionRequest(
                    source_url="https://example.com/article",
                    platform=SourcePlatform.WEB,
                )
            )

    async def test_provider_rejects_non_instagram_host_before_request(self) -> None:
        transport = StubTextTransport()
        extractor = InstagramOpenGraphExtractor(transport=transport)

        with self.assertRaisesRegex(
            ExtractionError,
            "requires an Instagram source URL",
        ):
            await extractor.extract(
                ExtractionRequest(
                    source_url="http://127.0.0.1/private",
                    platform=SourcePlatform.INSTAGRAM,
                )
            )

        self.assertEqual(transport.requested_urls, [])

    async def test_registry_without_provider_keeps_capture(self) -> None:
        original = NormalizedContent.captured(
            source_url="https://example.com/article",
            platform=SourcePlatform.WEB,
            saved_at=SAVED_AT,
        )

        outcome = await ExtractorRegistry().enrich(original)

        self.assertFalse(outcome.extracted)
        self.assertIsNone(outcome.provider)
        self.assertEqual(outcome.content, original)


class UrllibTextTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_retries_transient_network_failure(self) -> None:
        expected = TextHttpResponse(
            final_url=SOURCE_URL,
            body=PUBLIC_HTML,
            headers={},
        )
        transport = UrllibTextTransport(retries=1, backoff_seconds=0)

        with patch.object(
            UrllibTextTransport,
            "_get_text_sync",
            side_effect=[URLError("temporary"), expected],
        ) as mocked_request:
            response = await transport.get_text(SOURCE_URL)

        self.assertEqual(response, expected)
        self.assertEqual(mocked_request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
