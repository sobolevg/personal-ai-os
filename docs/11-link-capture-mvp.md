# Hermes Link Capture — Phase 1 MVP

## Scope

The service captures links shared with Hermes in Telegram, enriches and
classifies them, and stores them in Notion. Work is intentionally incremental.

This checkpoint implements only:

- normalized data contracts;
- immutable original-source handling;
- URL extraction;
- platform detection;
- provider/client boundaries;
- unit tests for this foundation.

No Telegram polling, network metadata extraction, LLM request, Notion write,
or VPS deployment is enabled by this checkpoint.

## Module Structure

```text
services/link_capture/
├── models.py
├── url_detection.py
├── config.py
├── extraction/
│   └── base.py
├── classification.py
├── notion.py
└── telegram.py
```

Concrete platform providers will be added behind `ContentExtractor`. A provider
failure must result in an empty `ContentEnrichment`, not loss of the captured
record.

## Source Integrity Contract

1. Capture `source_url` and `saved_at` before redirects or network calls.
2. Never pass `source_url` as extractor-owned enrichment data.
3. Store redirect/canonical output in `canonical_url`.
4. Store downloadable or mirrored media in `media_url`.
5. Always map Notion `Original URL` to the captured `source_url`.
6. Always render a visible link to `source_url` in the Notion page body.
7. Continue with the minimal captured record when extraction fails.

## Planned Pipeline

```text
Telegram message
  -> exact URL capture + platform detection
  -> provider registry + metadata extraction
  -> normalized content
  -> OpenAI-compatible structured classification
  -> Notion persistence
  -> Telegram confirmation
```

## Configuration

The future runtime reads the required variables documented in `.env.example`.
Secrets remain outside git. `LinkCaptureSettings` redacts tokens/API keys from
its representation and fails clearly when required values are missing.

## Next Checkpoint

Add the generic web/YouTube metadata providers and extractor registry. Test
fallback behavior first, including successful record creation when metadata is
unavailable. Then add the OpenAI-compatible classifier; do not connect Telegram
or write to Notion until those units pass.
