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

The first provider checkpoint adds conservative Instagram extraction from
metadata exposed in an unauthenticated public HTML response. It does not use
cookies, log in, download media, or bypass access controls. Provider failures
preserve the minimal capture.

When Instagram includes public `video_versions`, the provider records the first
HTTPS media reference from an allow-listed Instagram/Facebook CDN in
`media_url`. This URL is temporary processing input, never a replacement for
`source_url`, and must not be treated as the durable Notion source link.

The next isolated checkpoint adds a provider-neutral transcript result and a
PLAUD Developer API adapter. Transcripts remain separate from captions and
captured metadata. The adapter submits a public media URL, polls boundedly,
maps time-aligned segments, redacts credentials from representations, and does
not log response bodies or authentication headers. Non-idempotent submit calls
are not retried because the provider does not expose an idempotency-key contract;
read-only polling requests use bounded retry.

The PLAUD Developer API currently documents M4A, MP3, and WAV inputs. Instagram
Reels expose MP4 video, so a production live path needs a temporary audio
conversion and public HTTPS object-storage URL (or the PLAUD File Upload API
with a separate user token). Direct MP4 submission is not considered reliable.

No Telegram polling, LLM request, Notion write, or VPS deployment is enabled by
this checkpoint.

## Module Structure

```text
services/link_capture/
├── models.py
├── url_detection.py
├── config.py
├── extraction/
│   ├── base.py
│   ├── http.py
│   ├── registry.py
│   └── providers/instagram.py
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

Run one live Instagram-to-PLAUD transcription through the isolated adapter,
then add the OpenAI-compatible text classifier. Do not connect Telegram or
write to Notion until those units pass.
